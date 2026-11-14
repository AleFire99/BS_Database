-- SQLite
SELECT cards.card_id, cards.name
FROM cards
JOIN card_families ON cards.id = card_families.card_id
JOIN families ON card_families.family_id = families.id
WHERE families.name = 'Different Earth Dragon';

SELECT name
FROM families
WHERE LOWER(name) LIKE LOWER('%Different %');

SELECT c.name, f.name
FROM cards c JOIN card_families cf ON c.id = cf.card_id
JOIN families f ON cf.family_id = f.id
WHERE c.card_id = "BS05-048";
