# Card field inventory

Inventory of the card fields each source offers, per card type, compared with what the scraper parses and the database stores today. It is evidence for the modelling work ([#29](https://github.com/AleFire99/BS_Database/issues/29) to [#31](https://github.com/AleFire99/BS_Database/issues/31)), the scraper rewrite ([#10](https://github.com/AleFire99/BS_Database/issues/10)) and the source analysis ([#9](https://github.com/AleFire99/BS_Database/issues/9)). It makes no modelling decisions. Field names in backticks are working names in snake_case ([ADR 0003](../adr/0003-naming-and-schema-versioning.md)), not an accepted schema. Terms are defined in the [glossary](../domain/glossary.md). The stored side is described in [current-schema.md](current-schema.md).

## How to read this document

- **Status `confirmed`**: seen in at least one fixture (or in the code) listed in the row.
- **Status `pending #9`**: not verified by any fixture. Only legacy-DB values or domain knowledge exist, so #9 must confirm it against real pages.
- **Risk for #9**: the three batspi card fixtures are recent cards (set BS72, 2025 contract-saga era). The `<pre>` format may differ in older eras. For example, the glossary documents the reduction format `3(2 紫, 1 神)`, while the Spirit fixture uses `4(赤2神1)`.
- Line references are to [batspi_card.py](../../src/bs_database/scrapers/batspi_card.py) (`parse` column) and [db.py](../../src/bs_database/db.py) (`stored` column).

## 1. Sources overview

| Source | What it provides | Fixture | Code |
| --- | --- | --- | --- |
| batspi.com card page (JP) | Title (`<h1 class="title">`), the `<pre>` block (type, cost line, levels, effects, symbol, illustrators, flavor text), image links, an "収録" (included in) section with set and rarity, a card-number table | [card_spirit.html](../../tests/fixtures/html/card_spirit.html), [card_nexus.html](../../tests/fixtures/html/card_nexus.html), [card_magic.html](../../tests/fixtures/html/card_magic.html) | [batspi_card.py](../../src/bs_database/scrapers/batspi_card.py) |
| batspi.com set page (JP) | Card numbers `BSNN-NNN` with names and links to card pages | [set.html](../../tests/fixtures/html/set.html) | [batspi_links.py](../../src/bs_database/scrapers/batspi_links.py) (regex `BS\d{2}-\d{3}`, line 138) |
| batspi.com card-list index (JP) | Links to set pages | [index.html](../../tests/fixtures/html/index.html) | [batspi_sets.py](../../src/bs_database/scrapers/batspi_sets.py) |
| fandom wiki set page (EN) | Table with `Number`, `Name`, `Rarity` columns | [fandom_set_BS47.html](../../tests/fixtures/html/fandom_set_BS47.html) | [fandom_sets.py](../../src/bs_database/scrapers/fandom_sets.py) (headers from the first row, line 43) |
| fandom wiki card page (EN) | Card image (`img.mw-file-element`) | [fandom_card.html](../../tests/fixtures/html/fandom_card.html), [fandom_image.png](../../tests/fixtures/html/fandom_image.png) | [fandom_images.py:66](../../src/bs_database/scrapers/fandom_images.py#L66) |

Caveats:

- All fandom fixtures are **synthetic** (`fixtures.json`: fandom.com was blocked by a Cloudflare challenge on 2026-11-14). The `Rarity` column and the card page layout are therefore **not verified against the real wiki**.
- The batspi card fixtures are real pages, listed with their URLs in [fixtures.json](../../tests/fixtures/html/fixtures.json).
- The `<pre>` lines referenced below are numbered from the type line as line 1. The scraper splits `pre.text.strip()` on newlines ([batspi_card.py:125](../../src/bs_database/scrapers/batspi_card.py#L125)).

Shape of the Spirit `<pre>` block (fixture, abridged):

```text
スピリット
4(赤2神1)/赤/眷属・武迅
<1>Lv1 3000 <3>Lv2 7000
Lv1・Lv2『自分のアタックステップ開始時』
（effect text）
シンボル：赤

イラスト：伊藤正市

フレーバーテキスト：
（flavor text）
```

## 2. Common fields (every type)

| Field | Meaning | Example (JP) | Source | Parsed today? | Stored today? | Status |
| --- | --- | --- | --- | --- | --- | --- |
| `name_jp` | Card name in Japanese | 光爪の武芸者ヘルハウンド | batspi `<h1 class="title">` link | Read then immediately machine-translated, JP is not kept ([:31-38](../../src/bs_database/scrapers/batspi_card.py#L31), [:133](../../src/bs_database/scrapers/batspi_card.py#L133)) | no (only the English translation) | confirmed |
| `name_en` | English name | none in fixtures | fandom set table `Name` column; today a Google machine translation of the JP name | Machine translation only ([:133](../../src/bs_database/scrapers/batspi_card.py#L133)); fandom `Name` kept in the set JSON but not used by the loader | `cards.name` (machine-translated) | pending #9: fandom `Name` column only seen in a synthetic fixture |
| `card_number` | `BSNN-NNN` identifier | BS72-007 | batspi set page text; card page table and image file name (`BS72-007.jpg`); fandom `Number` column (normalized to `Card_ID`, [fandom_sets.py:53-58](../../src/bs_database/scrapers/fandom_sets.py#L53)) | Passed in by the caller, not read from the card page ([:104](../../src/bs_database/scrapers/batspi_card.py#L104)) | `cards.card_id` (unique) | confirmed |
| `card_type` | Spirit, Nexus, Magic, Brave, Ultimate | スピリット, ネクサス, マジック | `<pre>` line 1 | Yes, machine-translated ([:61](../../src/bs_database/scrapers/batspi_card.py#L61)) then normalized in [normalize.py](../../src/bs_database/normalize.py) (`normalize_type`) | `cards.type_id` -> `card_types.name` | confirmed (Spirit, Nexus, Magic); Brave and Ultimate pending #9 |
| `cost` | Total cost in cores | 4 | `<pre>` line 2, number before `(` | Yes ([:62](../../src/bs_database/scrapers/batspi_card.py#L62)) | `cards.cost` | confirmed |
| `reduction` | Symbols that can pay part of the cost, per colour plus the god symbol 神 | `(赤2神1)` on Spirit; `(2)` on Nexus `3(2)`, Magic `4(2)` | `<pre>` line 2, text in parentheses | Partly: a plain number gives N copies of the translated colour; a coloured form such as `赤2神1` does not match the regex `(\d+)\s*(.+)` and yields an empty list ([:64-77](../../src/bs_database/scrapers/batspi_card.py#L64)) | no (JSON only) | confirmed |
| `colors` | Card colour(s) | 赤 | `<pre>` line 2, second `/` field | Yes, but stored under the name `symbol` ([:63](../../src/bs_database/scrapers/batspi_card.py#L63)) | `cards.symbol` as free text; `card_colors` only for single colours the map knows ([db.py:98-110](../../src/bs_database/db.py#L98)) | confirmed |
| `symbols` | Colour symbol icons printed on the card (may differ from colour) | `シンボル：赤` | `<pre>` line `シンボル：` (Spirit and Nexus fixtures; absent in the Magic fixture) | no, the line is never read | no | confirmed (Spirit, Nexus) |
| `families` | Family tags (系統), possibly several joined with `・` | 眷属・武迅 | `<pre>` line 2, third `/` field | Yes, translated then split on `/` ([:79](../../src/bs_database/scrapers/batspi_card.py#L79)); names cleaned in [normalize.py](../../src/bs_database/normalize.py) | `families`, `card_families` | confirmed |
| `effect_blocks` | Effect text, each with level scope, timing and text | `Lv1・Lv2『自分のアタックステップ開始時』` followed by the text; Nexus `Lv2` with no timing | `<pre>` lines after the level line | no | no | confirmed (Spirit, Nexus) |
| `keyword_blocks` | Bracketed keyword abilities | `【ミラージュ：コスト2(1)(このカードは手札からセットできる)】`, `【セット中】『自分のアタックステップ開始時』` | `<pre>`, Magic fixture | no | no | confirmed (Magic only; others pending #9) |
| `illustrators` | One or more illustrators, optionally with the product of the alternate art in parentheses | `イラスト：藤原ひさし`, `イラスト：平坂康也(契約編：環 第3章：覇極来臨)`, `イラスト：ikuyoan(プロモーションカード・ルー)` | `<pre>` lines `イラスト：` (several per card in Nexus and Magic) | no | no | confirmed |
| `flavor_text` | Flavor text | ルーの下に集った武芸者たちは… | `<pre>` after `フレーバーテキスト：` (Spirit and Nexus; absent in Magic fixture) | no | no | confirmed (Spirit, Nexus) |
| `rarity` | Rarity per set | `<R> (SECRETあり)`, `<C>`, `<C> … (フルアート版)` | batspi "収録" section; fandom set table `Rarity` column (synthetic fixture) | no (fandom column is kept in the set JSON only, [fandom_sets.py:51](../../src/bs_database/scrapers/fandom_sets.py#L51)) | no | confirmed (batspi); fandom pending #9 |
| `set_product` | Set(s) or product(s) the card is printed in | 契約編：環 第1章：廻帰再醒 (Nexus lists chapters 1 and 3) | batspi "収録" section; set code from the card number prefix | Set code only, derived from the card number ([:115](../../src/bs_database/scrapers/batspi_card.py#L115)) | only inside `image` path and `card_id` prefix | confirmed |
| `image` | Card image(s), including alternate or secret art | `/card/BS7/small/BS72-007.jpg`, `…-2.jpg`; "2枚" in the page table | batspi `<img>`; fandom `img.mw-file-element` | Path is built, not read: `data/images/<set>/<card_id>.jpg` ([:130](../../src/bs_database/scrapers/batspi_card.py#L130)); fandom download in [fandom_images.py:58-88](../../src/bs_database/scrapers/fandom_images.py#L58) | `cards.image` (a path string, stored whether or not a file exists) | confirmed |
| `source_url` | Page the data came from | `fixtures.json` URLs | the scrape input | Received as argument `url`, not written to the JSON ([:104](../../src/bs_database/scrapers/batspi_card.py#L104)) | no | confirmed |

Fields in this table: 17.

## 3. Type-specific fields

### 3.1 Spirit

| Field | Meaning | Example (JP) | Source | Parsed today? | Stored today? | Status |
| --- | --- | --- | --- | --- | --- | --- |
| `level` | Level number | `Lv1`, `Lv2` | `<pre>` level line, `LvN` | Yes ([:83](../../src/bs_database/scrapers/batspi_card.py#L83)) | `core_requirements.level` | confirmed |
| `cores` | Cores needed to reach the level | `<1>`, `<3>` | `<pre>` level line, `<n>` | Yes | `core_requirements.cores` | confirmed |
| `bp` | Battle points at that level | 3000, 7000 | `<pre>` level line, number after `LvN` | Yes (stored as `battlePoints`) | `core_requirements.battlePoints` | confirmed |

Fields: 3. Fixture line: `<1>Lv1 3000 <3>Lv2 7000`.

### 3.2 Nexus

| Field | Meaning | Example (JP) | Source | Parsed today? | Stored today? | Status |
| --- | --- | --- | --- | --- | --- | --- |
| `level` | Level number, no BP | `Lv1`, `Lv2` | `<pre>` level line | No: the regex requires a BP after `LvN`, so a Nexus level line gives no rows ([:83](../../src/bs_database/scrapers/batspi_card.py#L83)) | no (legacy DB has no Nexus levels) | confirmed |
| `cores` | Cores needed to reach the level | `<0>`, `<1>` | `<pre>` level line | No (same reason) | no | confirmed |

Fields: 2. Fixture line: `<0>Lv1 <1>Lv2`. Nexus has no BP in the fixture.

### 3.3 Magic

| Field | Meaning | Example (JP) | Source | Parsed today? | Stored today? | Status |
| --- | --- | --- | --- | --- | --- | --- |
| `main_effect` | Effect used in the main step, label `メイン：` | `メイン：` then the draw text | `<pre>`, Magic fixture | no | no | confirmed |
| `flash_effect` | Effect usable in the flash timing, label `フラッシュ：` | `フラッシュ：` in related-card text of [card_magic.html](../../tests/fixtures/html/card_magic.html), including one card with both `メイン：` and `フラッシュ：` | batspi `<pre>` | no | no | pending #9: label and main + flash coexistence seen in related-card blocks; confirm the layout in a card's own `<pre>` |
| `set_keyword` | Set-type keyword (Mirage) with its own cost and reduction | `【ミラージュ：コスト2(1)(このカードは手札からセットできる)】` | `<pre>`, Magic fixture | no | no | confirmed (one card) |
| `set_effects` | Effects active while the card is set, label `【セット中】` plus timing | `【セット中】『自分のアタックステップ開始時』` | `<pre>`, Magic fixture | no | no | confirmed (one card) |

Fields: 4. The Magic page also has an official Q&A section (for example `はい、なります。`). It sits outside the `<pre>` block, so it does not affect card fields, but it is a possible future source for rulings.

### 3.4 Brave

No Brave fixture exists. Only legacy-DB values are available.

| Field | Meaning | Example (JP) | Source | Parsed today? | Stored today? | Status |
| --- | --- | --- | --- | --- | --- | --- |
| `level` / `cores` / `bp` | Brave level row. The legacy DB has exactly one level row per Brave (level 1, cores 0 to 2, BP 1000 to 10000) | not available | legacy DB `core_requirements` | Presumably as for Spirit (not tested) | `core_requirements` (legacy) | pending #9: confirm the level line format and whether BP is the Brave's own or granted |
| `fusion_cost` | Cost to combine the Brave with a Spirit | not available | unknown | unknown | no | pending #9: confirm where it is printed and how it differs from `cost` |
| `fusion_condition` | Condition the target Spirit must meet | not available | unknown | unknown | no | pending #9: confirm the wording and structure |
| `fusion_bp` | BP the combined Spirit gains or has while fused | not available | unknown | unknown | no | pending #9: confirm whether it is a separate value from `bp` |

Fields: 4 (all pending #9).

### 3.5 Ultimate

No Ultimate fixture exists. Only legacy-DB values are available.

| Field | Meaning | Example (JP) | Source | Parsed today? | Stored today? | Status |
| --- | --- | --- | --- | --- | --- | --- |
| `level` / `cores` / `bp` | Ultimate level rows. The legacy DB shows levels 3 to 6, cores 1 to 8, BP 3000 to 30000 | not available | legacy DB `core_requirements` | Presumably as for Spirit (not tested) | `core_requirements` (legacy) | pending #9: confirm the level line format and that levels start at 3 |
| `summon_conditions` | Conditions to summon the Ultimate | not available | unknown | unknown | no | pending #9: confirm the wording and structure |
| `ultimate_trigger` | Trigger or timing of the Ultimate-specific ability | not available | unknown | unknown | no | pending #9: confirm that such a block exists and how it is labelled |

Fields: 3 (all pending #9).

## 4. Observed value ranges (legacy DB)

Read-only queries on a copy of the legacy `battle_spirits.db` (6373 cards, sets BS01 to BS72). These describe the legacy data, not the real game rules.

| Type | Cards | Cost range | Level rows | Levels | Cores per level | BP range |
| --- | --- | --- | --- | --- | --- | --- |
| Spirit | 4303 | 0 to 12 | 10548 | 1 to 4 | 1 to 10 | 1000 to 32000 |
| Nexus | 642 | 2 to 7 | 0 | none stored | none stored | none |
| Magic | 891 | 1 to 12 | 0 | none | none | none |
| Brave | 353 | 2 to 8 | 353 | 1 only | 0 to 2 | 1000 to 10000 |
| Ultimate | 184 | 2 to 10 | 476 | 3 to 6 (3 and 4: 184 each, 5: 106, 6: 2) | 1 to 8 | 3000 to 30000 |

Other observations:

- **`symbol` strings** (6373 cards): single colours `red`, `green`, `white`, `yellow` (lowercase, about 1040 to 1070 each) and `Blue`, `Purple` (capitalized, 1035 and 1060), plus 2 cards with `Green`. 71 cards use 26 distinct multicolour strings such as `Red and blue`, `Blue Green`, and one `Red purple green white yellow blue` (14 cards). Casing and word order are inconsistent.
- **Colours stored**: `colors` has Red, Purple, Green, Yellow, Blue and no White. 1137 cards have no `card_colors` row (Spirit 760, Magic 150, Nexus 132, Brave 61, Ultimate 34).
- **Families**: 517 family rows. Cards without any family: Magic 751 of 891, Nexus 511 of 642. Spirit, Brave and Ultimate all have at least one.
- **Names**: 1 card has a null or `Error:` name (a failed translation).
- **Images**: every card has an `image` path.
- The overall ranges cost 0 to 12 and BP 1000 to 32000 hold. The level range 1 to 6 holds only across types: Spirit stops at 4 in the legacy data and Ultimate runs from 3 to 6.

## 5. Gap list

Feeds [#29](https://github.com/AleFire99/BS_Database/issues/29) to [#32](https://github.com/AleFire99/BS_Database/issues/32) and [#10](https://github.com/AleFire99/BS_Database/issues/10).

### Parsed but dropped by the loader

- `reduction`: computed ([:64-77](../../src/bs_database/scrapers/batspi_card.py#L64)) and written to the card JSON, never stored ([db.py:122-150](../../src/bs_database/db.py#L122)).
- Fandom set-table columns (`Name`, `Rarity`, `Card_ID`): written to the set JSON, never read by the card loader.

### Parsed lossily

- `name_jp`: translated, original discarded.
- `colors`: stored in a field called `symbol`; multicolour cards get no `card_colors` rows, and White is missing from the lookup, while Black is mapped but has no `colors` row ([db.py:98-105](../../src/bs_database/db.py#L98)).
- `reduction` with colours and 神 (`赤2神1`): produces an empty list.
- Nexus level lines: no rows, because the regex expects a BP.

### Available in the page but never parsed

- `symbols` (`シンボル：`), `effect_blocks`, `keyword_blocks`, `illustrators` (including alternate-art product), `flavor_text`, `rarity` and its variants (`SECRETあり`, `フルアート版`), the multi-set "収録" list, alternate images, Magic `main_effect`, `set_keyword`, `set_effects`.

### Unknown (needs #9)

- Everything marked `pending #9` above: Magic `flash_effect`, Brave fusion fields, Ultimate summon and trigger fields, the Brave and Ultimate `<pre>` layout, and the real fandom `Rarity` column.
- Whether the batspi `<pre>` format is stable across older eras (the fixtures are all BS72).
- How promo and starter-deck cards are numbered, since the link regex only matches `BS\d{2}-\d{3}`.
