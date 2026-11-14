# 0004. Card vs printing identity, ID scheme and rarity

- Status: Proposed
- Date: 2026-11-14

## Context

The data model epic ([#8](https://github.com/AleFire99/BS_Database/issues/8)) needs one rule for what a "card" is, what a "printing" is, and which keys identify them. The legacy schema has one row per `BSnn-nnn` number (`cards.card_id`, see [current-schema.md](../data-model/current-schema.md)): it has no sets table, no link between prints of the same card and no rarity.

The batspi.com card pages show that a number is not a printing. Evidence from the fixtures (see [field-inventory.md](../data-model/field-inventory.md), rows `rarity`, `set_product`, `illustrators`, `image`):

- **The same number is reprinted.** [card_nexus.html](../../tests/fixtures/html/card_nexus.html) (BS72-069) is listed under `[BS72]` 第1章 `<C>` (2025-05-17) and under `[BS74]` 第3章 `<C> (フルアート版)` (2025-11-22). Both entries still read `(BS72-069)`. A reprint can keep its number and change finish or art.
- **A distribution with the same number.** [card_magic.html](../../tests/fixtures/html/card_magic.html) (BS72-075) is listed under `[BS72]` `<C>` and also as `バトルスキーイベント提供記念品 (BS72-075)`. Its illustrator lines are `高梨かりた` and `ikuyoan(プロモーションカード・ルー)`, which names a promo art.
- **Variants within one slot.** [card_spirit.html](../../tests/fixtures/html/card_spirit.html) (BS72-007) is `<R> (SECRETあり)`. The page table says "2枚" and links `BS72-007.jpg` and `BS72-007-2.jpg`.
- **Block icon.** Every `収録` entry carries `ブロックアイコン:<12>`, and the card section lists `ブロックアイコン/12`. It is an era or legality attribute.
- **Product categories.** The heading is `収録/掲載/配布` (included / published in a magazine / distributed), and each product has a release date (for example `2025年05月17日`).
- **Legacy.** Only `BSnn-nnn` numbers exist, one row per number. The same name appears under different numbers: in the legacy database (v0.1.0), Scorpio `BS02-031` is cost 4 with Lv1–3 (1000/3000/6000 BP) and `BS33-056` is cost 5 with Lv1–2 (4000/7000 BP). Same name does not imply same card, so these are two `cards` rows. Whether a card can ever be reprinted under a new number with identical stats and text is **pending [#9](https://github.com/AleFire99/BS_Database/issues/9)**.

This ADR **supersedes the Gate A wording** "printing number UNIQUE on printings" (used in [ADR 0003](0003-naming-and-schema-versioning.md)): the evidence above shows one number on several printings. Owner decision on [#29](https://github.com/AleFire99/BS_Database/issues/29), Gate B, 2026-11-14.

## Decision drivers

- A number must identify one card, and the database should enforce it.
- Reprints, promos and variants of the same number must be representable without duplicating the card.
- A card that exists under several numbers (pending #9) must be reachable directly.
- Naming and keys follow [ADR 0003](0003-naming-and-schema-versioning.md) (surrogate `id`, natural keys as UNIQUE).
- Lookups instead of enum text, so new rarities, variants and product types need no schema change.
- Cheap joins: the database is built in batch and read-mostly.

## Options considered

1. **A. Composite key `UNIQUE(number, product_id, variant_id)` on `printings`.**
   - Pros: one table; mirrors the batspi `収録` entries; simplest joins; no extra table.
   - Cons: the database does not enforce that a number belongs to one card (needs a validation query); a NULL `variant_id` breaks UNIQUE in SQLite; a number lookup returns many rows.
2. **B. `card_numbers(id, number UNIQUE, card_id)` plus `printings(card_number_id, product_id, variant_id, rarity_id)` with `UNIQUE(card_number_id, product_id, variant_id)`.**
   - Pros: the database enforces number to exactly one card; card to numbers is direct (Scorpio case); a number lookup returns one row; there is a home for per-number facts.
   - Cons: one more table and one more join; `card_numbers` is nearly 1:1 with `cards` for most cards.
3. **C. `number UNIQUE` on `printings` plus a `printing_appearances` child table.**
   - Pros: keeps the Gate A wording literally.
   - Cons: really option B with misleading names; "printing" would no longer be a physical print.

## Decision

Use **option B** (owner choice, Gate B). Detailed columns are in [target-schema.md](../data-model/target-schema.md#identity).

- **`cards`**: the gameplay identity, one row per distinct card (name, text, stats) with a surrogate `id`. `block_icon` sits here by default (pending #9 if it turns out to vary per number).
- **`card_numbers`**: `id`, `number` (UNIQUE, e.g. `BS72-069`), `card_id`. A number belongs to exactly one card. A card can have several numbers. Different numbers are linked to one card only if text and stats are identical; otherwise they are separate cards (errata or remake). The final rule is **pending #9**.
- **`products`**: anything a card is released in. `code` is UNIQUE where not null (e.g. `BS72`) and null for distributions without a code; plus `name_ja`, `name_en`, `product_type_id`, `release_date`, and a nullable `series` text for the chapter grouping (契約編：環). A booster set *is* a product; there is no separate `sets` table.
- **`product_types`**: lookup with `code` and an English `name` (no Japanese name column; booster, starter or deck, promo distribution, magazine, collab, other). Exact list pending #9.
- **`printings`**: one physical printing: `card_number_id`, `product_id`, `variant_id` (NOT NULL, default `normal`), `rarity_id` (nullable: distribution entries show no rarity, pending #9), `illustrator` text. Images are not a column: they live in `printing_images` (one row per printing and size, [#31](https://github.com/AleFire99/BS_Database/issues/31), [ADR 0005](0005-text-first-effects-and-translations.md)). `UNIQUE(card_number_id, product_id, variant_id)`.
- **`rarities`**: lookup with `code` (`C` and `R` seen in batspi `<C>`/`<R>`; other codes pending #9), an English `name` (no Japanese name column) and `sort_order`. The Japanese `<C>`/`<R>` text is mapped to the code by the loader. The scale is pending #9.
- **`variants`**: lookup with `code` and an English `name` (no Japanese name column; the loader maps `フルアート版` to `full_art`). Codes: `normal`, `secret`, `full_art`, `promo_art`, parallel, .... The list is pending #9.
- **Reprint**: a new `printings` row for the same `card_numbers` row (another product and/or variant). A reprint under a new number is a new `card_numbers` row for the same card.
- **Promo**: a `printings` row whose product has the promo distribution type. The number is reused or a P-number; the format is pending #9.
- **IDs**: surrogate integer `id` everywhere. Natural keys are UNIQUE: `card_numbers.number`, `products.code`, `rarities.code`, `variants.code`, `product_types.code`, and the composite printing key above.

### Worked examples

Row ids are illustrative. Product types, the mapping of illustrators to printings and the `promo_art` variant are inferred from the fixtures and marked in the notes.

#### BS72-069: reprint with full art (Nexus)

`cards`:

| id | name_ja | block_icon |
| --- | --- | --- |
| 1 | ゼウスの雷火山 | 12 |

`card_numbers`:

| id | number | card_id |
| --- | --- | --- |
| 1 | BS72-069 | 1 |

`products`:

| id | code | name_ja | product_type | release_date | series |
| --- | --- | --- | --- | --- | --- |
| 1 | BS72 | 第1章：廻帰再醒 | booster | 2025-05-17 | 契約編：環 |
| 2 | BS74 | 第3章：覇極来臨 | booster | 2025-11-22 | 契約編：環 |

`printings`:

| id | card_number_id | product_id | variant | rarity | illustrator |
| --- | --- | --- | --- | --- | --- |
| 1 | 1 (BS72-069) | 1 (BS72) | normal | C | 藤原ひさし |
| 2 | 1 (BS72-069) | 2 (BS74) | full_art | C | 平坂康也 |

The page lists `藤原ひさし` and `平坂康也(契約編：環 第3章：覇極来臨)`; assigning them to the two printings follows the parenthesised product and is to be confirmed in #31. The booster product type is assumed.

#### BS72-075: promo distribution (Magic)

`cards`:

| id | name_ja | block_icon |
| --- | --- | --- |
| 2 | ジャベリンドロー | 12 |

`card_numbers`:

| id | number | card_id |
| --- | --- | --- |
| 2 | BS72-075 | 2 |

`products` (BS72 is row 1 above):

| id | code | name_ja | product_type | release_date | series |
| --- | --- | --- | --- | --- | --- |
| 3 | NULL | バトルスキーイベント提供記念品 | promo | NULL | NULL |

The page shows no release date for the distribution entry.

`printings`:

| id | card_number_id | product_id | variant | rarity | illustrator |
| --- | --- | --- | --- | --- | --- |
| 3 | 2 (BS72-075) | 1 (BS72) | normal | C | 高梨かりた |
| 4 | 2 (BS72-075) | 3 (promo) | promo_art | NULL | ikuyoan |

The distribution entry shows no rarity, so `rarity_id` is nullable (pending #9). The illustrator `ikuyoan(プロモーションカード・ルー)` is assumed to belong to the promo printing.

#### BS72-007: secret variant (Spirit)

`cards`:

| id | name_ja | block_icon |
| --- | --- | --- |
| 3 | 光爪の武芸者ヘルハウンド | 12 |

`card_numbers`:

| id | number | card_id |
| --- | --- | --- |
| 3 | BS72-007 | 3 |

`printings` (BS72 is product 1):

| id | card_number_id | product_id | variant | rarity | illustrator |
| --- | --- | --- | --- | --- | --- |
| 5 | 3 (BS72-007) | 1 (BS72) | normal | R | 伊藤正市 |
| 6 | 3 (BS72-007) | 1 (BS72) | secret | pending #9 | 伊藤正市 |

The images `BS72-007.jpg` and `BS72-007-2.jpg` are rows of `printing_images` (see [target-schema.md](../data-model/target-schema.md#images)). The page says `<R> (SECRETあり)` and links two images. Which image is the secret art, and the rarity code of the secret printing, are pending #9 and #31.

## Consequences

- Every printing-to-card query needs one more join (`printings` to `card_numbers` to `cards`). This is cheap in a read-mostly, batch-built database.
- The database guarantees that a number maps to exactly one card. Linking several numbers to one card is a data decision made in the build (pending #9), not a schema change.
- `variant_id` is NOT NULL (default `normal`) so the composite UNIQUE works in SQLite.
- `card_numbers` is near 1:1 with `cards`, so most cards carry one extra row.
- ADR 0003's natural-key example now reads `card_numbers.number` instead of `printings.number` (edited while ADR 0003 is Proposed).
- Open items for #9: card identity across different numbers, the rarity scale, the variant list, the promo number format, and whether `block_icon` is per card or per number.
- DDL is written in [#12](https://github.com/AleFire99/BS_Database/issues/12), gameplay attributes in [#30](https://github.com/AleFire99/BS_Database/issues/30), effects, i18n, provenance and image details (`printing_images`) in [#31](https://github.com/AleFire99/BS_Database/issues/31).

## Links

- Issue: [#29](https://github.com/AleFire99/BS_Database/issues/29) (epic [#8](https://github.com/AleFire99/BS_Database/issues/8))
- Builds on [0003](0003-naming-and-schema-versioning.md) and [0002](0002-storage-technology.md).
- Model: [target-schema.md](../data-model/target-schema.md)
