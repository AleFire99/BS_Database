"""SQLAlchemy models and JSON -> SQLite loader.

Ported from the legacy ``scripts/db/db_manager.py`` with identical table, column and
constraint names. Nothing runs at import time.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any

from sqlalchemy import Column, ForeignKey, Integer, String, Table, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


card_colors = Table(
    "card_colors",
    Base.metadata,
    Column("card_id", ForeignKey("cards.id"), primary_key=True),
    Column("color_id", ForeignKey("colors.id"), primary_key=True),
)

card_families = Table(
    "card_families",
    Base.metadata,
    Column("card_id", ForeignKey("cards.id"), primary_key=True),
    Column("family_id", ForeignKey("families.id"), primary_key=True),
)


class CardType(Base):
    __tablename__ = "card_types"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str | None] = mapped_column(String, unique=True)


class Color(Base):
    __tablename__ = "colors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str | None] = mapped_column(String, unique=True)

    cards: Mapped[list["Card"]] = relationship(secondary=card_colors, back_populates="colors")


class Family(Base):
    __tablename__ = "families"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str | None] = mapped_column(String, unique=True)

    cards: Mapped[list["Card"]] = relationship(secondary=card_families, back_populates="families")


class Card(Base):
    __tablename__ = "cards"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str | None] = mapped_column(String)
    card_id: Mapped[str | None] = mapped_column(String, unique=True)
    cost: Mapped[int | None] = mapped_column(Integer)
    symbol: Mapped[str | None] = mapped_column(String)
    image: Mapped[str | None] = mapped_column(String)

    type_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("card_types.id"))
    type: Mapped[CardType | None] = relationship()

    colors: Mapped[list[Color]] = relationship(secondary=card_colors, back_populates="cards")
    families: Mapped[list[Family]] = relationship(secondary=card_families, back_populates="cards")
    core_requirements: Mapped[list["CoreRequirement"]] = relationship(back_populates="card")


class CoreRequirement(Base):
    __tablename__ = "core_requirements"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    level: Mapped[int | None] = mapped_column(Integer)
    battlePoints: Mapped[int | None] = mapped_column(Integer)
    cores: Mapped[int | None] = mapped_column(Integer)

    card_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("cards.id"))
    card: Mapped[Card | None] = relationship(back_populates="core_requirements")


def get_or_create[M: Base](session: Session, model: type[M], **kwargs: Any) -> M:
    """Return the matching row, creating and committing it if missing."""
    instance = session.query(model).filter_by(**kwargs).first()
    if not instance:
        instance = model(**kwargs)
        session.add(instance)
        session.commit()
    return instance


_COLOR_MAP = {
    "purple": ["Purple"],
    "red": ["Red"],
    "blue": ["Blue"],
    "green": ["Green"],
    "yellow": ["Yellow"],
    "black": ["Black"],
}


def get_colors_from_symbol(symbol: str) -> list[str]:
    """Map a symbol to color names; unknown symbols give an empty list."""
    return _COLOR_MAP.get(symbol.lower(), [])


def insert_card(data: dict[str, Any], session: Session) -> Card:
    """Insert one card; an already-present ``card_id`` is skipped with a warning."""
    existing_card = session.query(Card).filter_by(card_id=data["card_id"]).first()
    if existing_card:
        logger.warning("Card with card_id %s already exists. Skipping insert.", data["card_id"])
        return existing_card

    type_obj = get_or_create(session, CardType, name=data["type"])

    card = Card(
        name=data["name"],
        card_id=data["card_id"],
        cost=data["cost"],
        symbol=data["symbol"],
        image=data.get("image"),
        type=type_obj,
    )

    for color_name in get_colors_from_symbol(data["symbol"]):
        color = get_or_create(session, Color, name=color_name.strip())
        if color not in card.colors:
            card.colors.append(color)

    if data.get("family"):
        for fam_name in data["family"]:
            family = get_or_create(session, Family, name=fam_name)
            if family not in card.families:
                card.families.append(family)

    for req in data.get("core_requirements", []):
        session.add(
            CoreRequirement(
                level=req["level"],
                battlePoints=req["battlePoints"],
                cores=req["cores"],
                card=card,
            )
        )

    session.add(card)
    session.commit()
    return card


def load_json_cards(root: str | Path, session: Session) -> None:
    """Insert every ``*.json`` card under ``root``; invalid JSON raises."""
    for subdir, dirnames, files in os.walk(root):
        dirnames.sort()
        for file in sorted(files):
            if file.endswith(".json"):
                with open(os.path.join(subdir, file), encoding="utf-8") as f:
                    insert_card(json.load(f), session)


def build_db(json_dir: str | Path, db_path: str | Path) -> None:
    """Create the schema in ``db_path`` and load all card JSON from ``json_dir``."""
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            load_json_cards(json_dir, session)
    finally:
        engine.dispose()
