import os
import json
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Table
from sqlalchemy.orm import relationship, sessionmaker, declarative_base

Base = declarative_base()

# Association Tables
card_colors = Table(
    'card_colors', Base.metadata,
    Column('card_id', ForeignKey('cards.id'), primary_key=True),
    Column('color_id', ForeignKey('colors.id'), primary_key=True)
)

card_families = Table(
    'card_families', Base.metadata,
    Column('card_id', ForeignKey('cards.id'), primary_key=True),
    Column('family_id', ForeignKey('families.id'), primary_key=True)
)

# Tables
class CardType(Base):
    __tablename__ = 'card_types'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)

class Color(Base):
    __tablename__ = 'colors'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)

class Family(Base):
    __tablename__ = 'families'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)

class Card(Base):
    __tablename__ = 'cards'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    card_id = Column(String, unique=True)
    cost = Column(Integer)
    symbol = Column(String)
    image = Column(String)

    type_id = Column(Integer, ForeignKey('card_types.id'))
    type = relationship('CardType')

    colors = relationship('Color', secondary=card_colors, backref='cards')
    families = relationship('Family', secondary=card_families, backref='cards')
    core_requirements = relationship('CoreRequirement', back_populates='card')

class CoreRequirement(Base):
    __tablename__ = 'core_requirements'
    id = Column(Integer, primary_key=True)
    level = Column(Integer)
    battlePoints = Column(Integer)
    cores = Column(Integer)

    card_id = Column(Integer, ForeignKey('cards.id'))
    card = relationship('Card', back_populates='core_requirements')


# Helper function to get or create a record
def get_or_create(session, model, **kwargs):
    """Checks if an object exists, creates and commits it if not."""
    instance = session.query(model).filter_by(**kwargs).first()
    if not instance:
        instance = model(**kwargs)
        session.add(instance)
        session.commit()
    return instance


# Function to load cards from JSON and insert into database
def load_json_cards(root_folder, session):
    for subdir, _, files in os.walk(root_folder):
        for file in files:
            if file.endswith('.json'):
                with open(os.path.join(subdir, file), 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    insert_card(data, session)

def get_colors_from_symbol(symbol):
    # Mapping symbol to colors
    color_map = {
        "purple": ["Purple"],
        "red": ["Red"],
        "blue": ["Blue"],
        "green": ["Green"],
        "yellow": ["Yellow"],
        "black": ["Black"],
        # You can add more mappings here as needed
    }
    return color_map.get(symbol.lower(), [])  # Default to empty list if no mapping

def insert_card(data, session):
    # Check if the card already exists by its card_id
    existing_card = session.query(Card).filter_by(card_id=data['card_id']).first()
    
    # If the card already exists, return it and don't insert again
    if existing_card:
        print(f"Card with card_id {data['card_id']} already exists. Skipping insert.")
        return existing_card

    # Card type
    type_obj = get_or_create(session, CardType, name=data['type'])

    # Create a new card
    card = Card(
        name=data['name'],
        card_id=data['card_id'],
        cost=data['cost'],
        symbol=data['symbol'],
        image=data.get('image'),
        type=type_obj
    )

    # Colors derived from symbol
    colors = get_colors_from_symbol(data['symbol'])
    for color_name in colors:
        color = get_or_create(session, Color, name=color_name.strip())
        # Ensure no duplicate card-color relationship
        if color not in card.colors:
            card.colors.append(color)

    # Families - only process if 'family' key exists and is not empty
    if 'family' in data and data['family']:
        for fam_name in data['family']:
            family = get_or_create(session, Family, name=fam_name)
            
            # Check if the card already has this family associated
            if family not in card.families:
                card.families.append(family)


    # Core Requirements
    for req in data.get('core_requirements', []):
        requirement = CoreRequirement(
            level=req['level'],
            battlePoints=req['battlePoints'],
            cores=req['cores'],
            card=card
        )
        session.add(requirement)

    # Add card to session and commit
    session.add(card)
    session.commit()

    return card


# Main function
if __name__ == '__main__':
    # Set up the database engine and session
    engine = create_engine('sqlite:///data/battle_spirits.db')
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    session = Session()

    # Path to the root folder containing JSON files
    root_folder = 'path_to_your_jsons_here'  # Update this path
    load_json_cards(root_folder, session)

    print("✅ Done!")
