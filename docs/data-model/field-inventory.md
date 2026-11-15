# Card field inventory

Inventory of the card fields each source offers, per card type, compared with what the scraper parses and the database stores today. It is evidence for the modelling work ([#29](https://github.com/AleFire99/BS_Database/issues/29) to [#31](https://github.com/AleFire99/BS_Database/issues/31)), the scraper rewrite ([#10](https://github.com/AleFire99/BS_Database/issues/10)) and the source analysis ([#9](https://github.com/AleFire99/BS_Database/issues/9)). It makes no modelling decisions. Field names in backticks are working names in snake_case ([ADR 0003](../adr/0003-naming-and-schema-versioning.md)), not an accepted schema. Terms are defined in the [glossary](../domain/glossary.md). The stored side is described in [current-schema.md](current-schema.md).

## How to read this document

- **Status `confirmed`**: seen in at least one fixture (or in the code) listed in the row.
- **Status `absent`**: the source was checked in the fixtures and does not carry the field.
- **Eras checked by #9**: the card fixtures now cover BS01 to BS72, every card type and a flip card ([fixtures README](../../tests/fixtures/html/README.md)). The `<pre>` format is stable across them: the cost line, level line and `シンボル：` line have the same shape from BS01 to BS72, only the content varies ([batspi.md §6](../sources/batspi.md#6-card-pages)). The glossary form `3(2 紫, 1 神)` was never seen; the real forms are `4(赤2神1)` and `5(赤2白2)`.
- The field-by-field comparison with the target schema is in the [coverage matrix](../sources/coverage-matrix.md).
- Line references are to [batspi_card.py](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/batspi_card.py) (`parse` column) and [db.py](../../src/bs_database/db.py) (`stored` column).

## 1. Sources overview

| Source | What it provides | Fixture | Code |
| --- | --- | --- | --- |
| batspi.com card page (JP) | Title (`<h1 class="title">`, or `<title>` on trimmed pages), the `<pre>` block (type, cost line, levels, effects, symbol, illustrators, flavor text), image links, an "収録" (included in) section with set and rarity, a card-number table | [card_spirit.html](../../tests/fixtures/html/card_spirit.html), [card_nexus.html](../../tests/fixtures/html/card_nexus.html), [card_magic.html](../../tests/fixtures/html/card_magic.html); added by #54: [card_brave.html](../../tests/fixtures/html/card_brave.html), [card_ultimate.html](../../tests/fixtures/html/card_ultimate.html), [card_nexus_soukaishin.html](../../tests/fixtures/html/card_nexus_soukaishin.html), [card_flip.html](../../tests/fixtures/html/card_flip.html), [card_spirit_bs01.html](../../tests/fixtures/html/card_spirit_bs01.html), [card_spirit_xx_bs31.html](../../tests/fixtures/html/card_spirit_xx_bs31.html), [card_promo.html](../../tests/fixtures/html/card_promo.html), [card_magic_flash.html](../../tests/fixtures/html/card_magic_flash.html) | [batspi_card.py](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/batspi_card.py) |
| batspi.com set page (JP) | Card numbers `BSNN-NNN` with names and links to card pages, release date, product code | [set.html](../../tests/fixtures/html/set.html); added by #54: [set_bs01.html](../../tests/fixtures/html/set_bs01.html), [set_bs52.html](../../tests/fixtures/html/set_bs52.html), [set_sd54.html](../../tests/fixtures/html/set_sd54.html), [set_wafer.html](../../tests/fixtures/html/set_wafer.html), [set_cb34.html](../../tests/fixtures/html/set_cb34.html) | [batspi_links.py](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/batspi_links.py) (regex `BS\d{2}-\d{3}`, line 138) |
| batspi.com card-list index (JP) | Links to set pages | [index.html](../../tests/fixtures/html/index.html) | [batspi_sets.py](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/batspi_sets.py) |
| fandom wiki set page (EN) | Table with `Number`, `Name`, `Rarity` columns | [fandom_set_BS47.html](https://github.com/AleFire99/BS_Database/blob/f90747b/tests/fixtures/html/fandom_set_BS47.html) | [fandom_sets.py](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/fandom_sets.py) (headers from the first row, line 43) |
| fandom wiki card page (EN) | Card image (`img.mw-file-element`) | [fandom_card.html](https://github.com/AleFire99/BS_Database/blob/f90747b/tests/fixtures/html/fandom_card.html), [fandom_image.png](https://github.com/AleFire99/BS_Database/blob/f90747b/tests/fixtures/html/fandom_image.png) | [fandom_images.py:66](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/fandom_images.py#L66) |

Caveats:

- All fandom fixtures are **synthetic** (`fixtures.json`: fandom.com was blocked by a Cloudflare challenge on 2026-11-14). The `Rarity` column and the card page layout are therefore **not verified against the real wiki**.
- The batspi card and set fixtures are real pages, listed with their URLs in [fixtures.json](../../tests/fixtures/html/fixtures.json). The pages added by #54 are trimmed (header and footer removed), so their `<h1>` is missing and the name is read from `<title>`.
- The `<pre>` lines referenced below are numbered from the type line as line 1. The scraper splits `pre.text.strip()` on newlines ([batspi_card.py:125](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/batspi_card.py#L125)).

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
| `name_jp` | Card name in Japanese | 光爪の武芸者ヘルハウンド | batspi `<h1 class="title">` link | Read then immediately machine-translated, JP is not kept ([:31-38](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/batspi_card.py#L31), [:133](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/batspi_card.py#L133)) | no (only the English translation) | confirmed |
| `name_en` | English name | none in fixtures | fandom set table `Name` column; today a Google machine translation of the JP name | Machine translation only ([:133](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/batspi_card.py#L133)); fandom `Name` kept in the set JSON but not used by the loader | `cards.name` (machine-translated) | confirmed on older cards and promos: the `<h3>` of [card_brave.html](../../tests/fixtures/html/card_brave.html) has `The GunDragon Phoenix-Cannon`, [card_spirit_bs01.html](../../tests/fixtures/html/card_spirit_bs01.html) has `Goradon`; absent on contract-era cards (`card_spirit.html`, `card_nexus.html`, `card_magic.html`). fandom `Name`: not fetched (dropped for v1, synthetic fixture only) |
| `card_number` | `BSNN-NNN` identifier | BS72-007 | batspi set page text; card page table and image file name (`BS72-007.jpg`); fandom `Number` column (normalized to `Card_ID`, [fandom_sets.py:53-58](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/fandom_sets.py#L53)) | Passed in by the caller, not read from the card page ([:104](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/batspi_card.py#L104)) | `cards.card_id` (unique) | confirmed |
| `card_type` | Spirit, Nexus, Magic, Brave, Ultimate | スピリット, ネクサス, マジック | `<pre>` line 1 | Yes, machine-translated ([:61](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/batspi_card.py#L61)) then normalized in [normalize.py](../../src/bs_database/normalize.py) (`normalize_type`) | `cards.type_id` -> `card_types.name` | confirmed: `ブレイヴ` in [card_brave.html](../../tests/fixtures/html/card_brave.html), `アルティメット` in [card_ultimate.html](../../tests/fixtures/html/card_ultimate.html), plus Spirit, Nexus and Magic. The type can carry a suffix, `ネクサス(制限カード<1>)` in [card_flip.html](../../tests/fixtures/html/card_flip.html) |
| `cost` | Total cost in cores | 4 | `<pre>` line 2, number before `(` | Yes ([:62](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/batspi_card.py#L62)) | `cards.cost` | confirmed |
| `reduction` | Symbols that can pay part of the cost, per colour plus the god symbol 神 | `(赤2神1)` on Spirit; `(2)` on Nexus `3(2)`, Magic `4(2)` | `<pre>` line 2, text in parentheses | Partly: a plain number gives N copies of the translated colour; a coloured form such as `赤2神1` does not match the regex `(\d+)\s*(.+)` and yields an empty list ([:64-77](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/batspi_card.py#L64)) | no (JSON only) | confirmed |
| `colors` | Card colour(s) | 赤 | `<pre>` line 2, second `/` field | Yes, but stored under the name `symbol` ([:63](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/batspi_card.py#L63)) | `cards.symbol` as free text; `card_colors` only for single colours the map knows ([db.py:98-110](../../src/bs_database/db.py#L98)) | confirmed |
| `symbols` | Colour symbol icons printed on the card (may differ from colour) | `シンボル：赤` | `<pre>` line `シンボル：` (Spirit and Nexus fixtures; absent in the Magic fixture) | no, the line is never read | no | confirmed (Spirit, Nexus) |
| `families` | Family tags (系統), possibly several joined with `・` | 眷属・武迅 | `<pre>` line 2, third `/` field | Yes, translated then split on `/` ([:79](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/batspi_card.py#L79)); names cleaned in [normalize.py](../../src/bs_database/normalize.py) | `families`, `card_families` | confirmed |
| `effect_blocks` | Effect text, each with level scope, timing and text | `Lv1・Lv2『自分のアタックステップ開始時』` followed by the text; Nexus `Lv2` with no timing | `<pre>` lines after the level line | no | no | confirmed (Spirit, Nexus) |
| `keyword_blocks` | Bracketed keyword abilities | `【ミラージュ：コスト2(1)(このカードは手札からセットできる)】`, `【セット中】『自分のアタックステップ開始時』` | `<pre>`, Magic fixture | no | no | confirmed: Magic as above; also `【合体時】【激突】` in [card_brave.html](../../tests/fixtures/html/card_brave.html), `【召喚条件：自分の赤スピリット1体以上】` and `【Uトリガー】` in [card_ultimate.html](../../tests/fixtures/html/card_ultimate.html), `【超装甲：赤/紫/緑/白/黄/青】` in [card_spirit_xx_bs31.html](../../tests/fixtures/html/card_spirit_xx_bs31.html), `【神技：2】` and `【神域】` in [card_nexus_soukaishin.html](../../tests/fixtures/html/card_nexus_soukaishin.html), `【根幻回帰】` in [card_flip.html](../../tests/fixtures/html/card_flip.html) |
| `illustrators` | One or more illustrators, optionally with the product of the alternate art in parentheses | `イラスト：藤原ひさし`, `イラスト：平坂康也(契約編：環 第3章：覇極来臨)`, `イラスト：ikuyoan(プロモーションカード・ルー)` | `<pre>` lines `イラスト：` (several per card in Nexus and Magic) | no | no | confirmed |
| `flavor_text` | Flavor text | ルーの下に集った武芸者たちは… | `<pre>` after `フレーバーテキスト：` (Spirit and Nexus; absent in Magic fixture) | no | no | confirmed (Spirit, Nexus) |
| `rarity` | Rarity per set | `<R> (SECRETあり)`, `<C>`, `<C> … (フルアート版)` | batspi "収録" section; fandom set table `Rarity` column (synthetic fixture) | no (fandom column is kept in the set JSON only, [fandom_sets.py:51](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/fandom_sets.py#L51)) | no | confirmed (batspi: `<R>`, `<C>`, `<X>` in [card_ultimate.html](../../tests/fixtures/html/card_ultimate.html), `<XX>` in [card_spirit_xx_bs31.html](../../tests/fixtures/html/card_spirit_xx_bs31.html), `<転醒X>` in [card_flip.html](../../tests/fixtures/html/card_flip.html)); fandom `Rarity`: not fetched (dropped for v1, synthetic fixture only) |
| `set_product` | Set(s) or product(s) the card is printed in | 契約編：環 第1章：廻帰再醒 (Nexus lists chapters 1 and 3) | batspi "収録" section; set code from the card number prefix | Set code only, derived from the card number ([:115](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/batspi_card.py#L115)) | only inside `image` path and `card_id` prefix | confirmed |
| `image` | Card image(s), including alternate or secret art | `/card/BS7/small/BS72-007.jpg`, `…-2.jpg`; "2枚" in the page table | batspi `<img>`; fandom `img.mw-file-element` | Path is built, not read: `data/images/<set>/<card_id>.jpg` ([:130](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/batspi_card.py#L130)); fandom download in [fandom_images.py:58-88](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/fandom_images.py#L58) | `cards.image` (a path string, stored whether or not a file exists) | confirmed |
| `source_url` | Page the data came from | `fixtures.json` URLs | the scrape input | Received as argument `url`, not written to the JSON ([:104](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/batspi_card.py#L104)) | no | confirmed |

Fields in this table: 17.

## 3. Type-specific fields

### 3.1 Spirit

| Field | Meaning | Example (JP) | Source | Parsed today? | Stored today? | Status |
| --- | --- | --- | --- | --- | --- | --- |
| `level` | Level number | `Lv1`, `Lv2` | `<pre>` level line, `LvN` | Yes ([:83](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/batspi_card.py#L83)) | `core_requirements.level` | confirmed |
| `cores` | Cores needed to reach the level | `<1>`, `<3>` | `<pre>` level line, `<n>` | Yes | `core_requirements.cores` | confirmed |
| `bp` | Battle points at that level | 3000, 7000 | `<pre>` level line, number after `LvN` | Yes (stored as `battlePoints`) | `core_requirements.battlePoints` | confirmed |

Fields: 3. Fixture line: `<1>Lv1 3000 <3>Lv2 7000`.

### 3.2 Nexus

| Field | Meaning | Example (JP) | Source | Parsed today? | Stored today? | Status |
| --- | --- | --- | --- | --- | --- | --- |
| `level` | Level number, no BP | `Lv1`, `Lv2` | `<pre>` level line | No: the regex requires a BP after `LvN`, so a Nexus level line gives no rows ([:83](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/batspi_card.py#L83)) | no (legacy DB has no Nexus levels) | confirmed |
| `cores` | Cores needed to reach the level | `<0>`, `<1>` | `<pre>` level line | No (same reason) | no | confirmed |

Fields: 2. Fixture line: `<0>Lv1 <1>Lv2`. Nexus has no BP in the fixture.

### 3.3 Magic

| Field | Meaning | Example (JP) | Source | Parsed today? | Stored today? | Status |
| --- | --- | --- | --- | --- | --- | --- |
| `main_effect` | Effect used in the main step, label `メイン：` | `メイン：` then the draw text | `<pre>`, Magic fixture | no | no | confirmed |
| `flash_effect` | Effect usable in the flash timing, label `フラッシュ：` | `メイン：` then `フラッシュ：`, each on its own line followed by the text, in the card's own `<pre>` of [card_magic_flash.html](../../tests/fixtures/html/card_magic_flash.html) (`BS01-117`) | batspi `<pre>` | no | no | confirmed |
| `set_keyword` | Set-type keyword (Mirage) with its own cost and reduction | `【ミラージュ：コスト2(1)(このカードは手札からセットできる)】` | `<pre>`, Magic fixture | no | no | confirmed (one card) |
| `set_effects` | Effects active while the card is set, label `【セット中】` plus timing | `【セット中】『自分のアタックステップ開始時』` | `<pre>`, Magic fixture | no | no | confirmed (one card) |

Fields: 4. The Magic page also has an official Q&A section (for example `はい、なります。`). It sits outside the `<pre>` block, so it does not affect card fields, but it is a possible future source for rulings.

### 3.4 Brave

Fixture: [card_brave.html](../../tests/fixtures/html/card_brave.html) (`BS10-062` and the reprint `BS38-RV022`). The legacy DB values are kept for comparison.

| Field | Meaning | Example (JP) | Source | Parsed today? | Stored today? | Status |
| --- | --- | --- | --- | --- | --- | --- |
| `level` / `cores` / `bp` | Brave level row. One level row per Brave (legacy DB: level 1, cores 0 to 2, BP 1000 to 10000) | `<1>Lv1 3000 <0>合体+3000` (`BS10-062`); `<0>Lv1 3000 <0>合体+3000` (`BS38-RV022`) | `<pre>` line 3 | Presumably as for Spirit (not tested) | `core_requirements` (legacy) | confirmed: the first token is the Brave's own level (cores and BP); the second token is the fusion bonus, not a level |
| `fusion_cost` | Cost to combine the Brave with a Spirit | none: no separate cost is printed | `<pre>` | no | no | absent: the only cost is the summon cost on line 2 (`5(赤2白2)`); the `<0>` in the fusion token is a core count |
| `fusion_condition` | Condition the target Spirit must meet | `合体条件：コスト3以上` (`BS10-062`); `右合体条件：コスト5以上` and `左合体条件：コスト3以上` (`BS38-RV022`) | `<pre>` effect lines | no | no | confirmed: one line, or two lines for right and left fusion |
| `fusion_bp` | BP the combined Spirit gains while fused | `合体+3000` | `<pre>` line 3, token after the level | no | no | confirmed: a separate value from the level BP |

Fields: 4 (3 confirmed, `fusion_cost` absent).

### 3.5 Ultimate

Fixture: [card_ultimate.html](../../tests/fixtures/html/card_ultimate.html) (`SD19-X01` and `SD67-CP01`). The legacy DB values are kept for comparison.

| Field | Meaning | Example (JP) | Source | Parsed today? | Stored today? | Status |
| --- | --- | --- | --- | --- | --- | --- |
| `level` / `cores` / `bp` | Ultimate level rows. The legacy DB shows levels 3 to 6, cores 1 to 8, BP 3000 to 30000 | `<1>Lv3 10000 <3>Lv4 14000 <5>Lv5 20000` | `<pre>` line 3 | Presumably as for Spirit (not tested) | `core_requirements` (legacy) | confirmed: levels start at 3. `Lv6` was not seen in a card's own block. `SD67-CP01` adds an overclock token, `OC<5+>+6000` |
| `summon_conditions` | Conditions to summon the Ultimate | `【召喚条件：自分の赤スピリット1体以上】` | `<pre>` effect lines | no | no | confirmed: one bracketed line |
| `ultimate_trigger` | Trigger or timing of the Ultimate-specific ability | `【Uトリガー】Lv3・Lv4・Lv5『このアルティメットのアタック時』` | `<pre>` effect lines | no | no | confirmed: the block exists, with a reminder in full-width brackets `（Uトリガー：…）` |

Fields: 3 (all confirmed).

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

- `reduction`: computed ([:64-77](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/batspi_card.py#L64)) and written to the card JSON, never stored ([db.py:122-150](../../src/bs_database/db.py#L122)).
- Fandom set-table columns (`Name`, `Rarity`, `Card_ID`): written to the set JSON, never read by the card loader.

### Parsed lossily

- `name_jp`: translated, original discarded.
- `colors`: stored in a field called `symbol`; multicolour cards get no `card_colors` rows, and White is missing from the lookup, while Black is mapped but has no `colors` row ([db.py:98-105](../../src/bs_database/db.py#L98)).
- `reduction` with colours and 神 (`赤2神1`): produces an empty list.
- Nexus level lines: no rows, because the regex expects a BP.

### Available in the page but never parsed

- `symbols` (`シンボル：`), `effect_blocks`, `keyword_blocks`, `illustrators` (including alternate-art product), `flavor_text`, `rarity` and its variants (`SECRETあり`, `フルアート版`), the multi-set "収録" list, alternate images, Magic `main_effect`, `set_keyword`, `set_effects`.

### Resolved by the #9 fixtures, and what stays open

- Resolved: Magic `flash_effect`, Brave fusion fields, Ultimate summon and trigger fields, and the Brave and Ultimate `<pre>` layout. The batspi `<pre>` format is stable from BS01 to BS72.
- Resolved: promo and starter-deck numbers are `P001`, `EX001`, `P20-19` ([card_promo.html](../../tests/fixtures/html/card_promo.html)) and `SD19-X01` ([card_ultimate.html](../../tests/fixtures/html/card_ultimate.html)). The link regex only matches `BS\d{2}-\d{3}`, so it still misses them.
- Open: the real fandom `Rarity` and `Name` columns (not fetched, dropped for v1), and the official detail view (never fetched). See the [coverage matrix](../sources/coverage-matrix.md).
