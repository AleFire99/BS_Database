# Legacy to target mapping

Maps every item of the legacy pipeline to the [target schema](target-schema.md), or marks it as dropped with a reason. It is the checklist for the legacy-data migration in [#12](https://github.com/AleFire99/BS_Database/issues/12) and, together with the gap list at the end, the input for the scraper rewrite ([#10](https://github.com/AleFire99/BS_Database/issues/10)). The short summary in the [Legacy mapping](target-schema.md#legacy-mapping) subsection of the target schema is consistent with this page; this page is the complete version.

Sources checked: [db.py](../../src/bs_database/db.py), [batspi_card.py](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/batspi_card.py), [fandom_sets.py](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/fandom_sets.py), [fandom_images.py](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/fandom_images.py), [normalize.py](../../src/bs_database/normalize.py), [current-schema.md](current-schema.md) (the legacy schema) and [field-inventory.md](field-inventory.md). Items that depend on the source analysis ([#9](https://github.com/AleFire99/BS_Database/issues/9)) are marked "pending #9".

Reading the tables: **Target** is `table.column` of [target-schema.md](target-schema.md); "dropped" means the item has no target column. Where the legacy value is wrong or lossy, the target is filled from the Japanese source text, not converted from the legacy value.

## 1. Legacy database tables

### cards ([db.py:60-74](../../src/bs_database/db.py#L60))

| Legacy column | Target | Note |
| --- | --- | --- |
| `cards.id` | dropped | Surrogate key of the old table. The target `cards.id` is a new key; the old value is not carried over. |
| `cards.name` | `cards.name_en` | Machine-translated English name, so `en_source_id` = `machine` and `en_status_id` = `machine`. 1 legacy card has an `Error:` name: map it to `NULL` with status `failed`. `cards.name_jp` has no legacy source (gap). |
| `cards.card_id` (unique business string, `BS72-007`) | `card_numbers.number` | Despite its name it is the card number, not a card key. One legacy row per number becomes one `card_numbers` row; linking numbers to one `cards` row is pending #9 ([ADR 0004](../adr/0004-card-printing-identity.md)). It also yields the product code (`BS72`) for `products.code`. |
| `cards.cost` | `cards.cost` | Same meaning. Legacy range 0 to 12. |
| `cards.symbol` | `card_colors` rows | Misnamed: it holds the card **colour** (see [section 2](#2-card-json-keys-batspi_cardpy)). It is free translated text (`Blue and red`), so it is not converted; colours are re-read from segment 2 of the Japanese cost line. |
| `cards.image` | `printing_images.path` | A path string built by the scraper, not a file reference. See [section 5](#5-other-legacy-artefacts). |
| `cards.type_id` | `cards.card_type_id` | FK to `card_types`, same shape. |

### card_types ([db.py:38-41](../../src/bs_database/db.py#L38))

| Legacy column | Target | Note |
| --- | --- | --- |
| `card_types.id` | dropped | Surrogate key; the seed rows get new ids. |
| `card_types.name` (unique, `Spirit`, `Nexus`, `Magic`, `Brave`, `Ultimate`) | `card_types.code` and `card_types.name` | `code` is the lower-case form (`spirit`, ...); `name` keeps the English display name. Same five rows. |

### colors ([db.py:44-49](../../src/bs_database/db.py#L44))

| Legacy column | Target | Note |
| --- | --- | --- |
| `colors.id` | dropped | Surrogate key. |
| `colors.name` (unique; Red, Purple, Green, Yellow, Blue) | `colors.code` and `colors.name` | Lower-case `code`. White is added (missing in the legacy table, which has no White row; the code map has `black` instead, [db.py:98-105](../../src/bs_database/db.py#L98)). The legacy `black` map entry is dropped: it has no `colors` row and is not a game colour in the target. |

### families ([db.py:52-57](../../src/bs_database/db.py#L52))

| Legacy column | Target | Note |
| --- | --- | --- |
| `families.id` | dropped | Surrogate key. |
| `families.name` (unique, machine-translated English, 517 rows) | `family_aliases.alias` with `lang` = `en` | The legacy name is a machine translation, so it becomes an alias with `translation_source_id` = `machine`. It points at the family whose Japanese name is found on the cards that use it. `families.name_jp` (the identity) and `families.name_en` (preferred) have no legacy source (gap); `name_en` can be filled from the `family_mapping.txt` right-hand side. |

### card_colors ([db.py:23-28](../../src/bs_database/db.py#L23))

| Legacy column | Target | Note |
| --- | --- | --- |
| `card_colors.card_id` | `card_colors.card_id` | Re-derived, not copied: 1137 legacy cards have no row, multicolour cards have none and White is missing. Rebuilt from the Japanese colour segment by the loader. |
| `card_colors.color_id` | `card_colors.color_id` | As above. |

### card_families ([db.py:30-35](../../src/bs_database/db.py#L30))

| Legacy column | Target | Note |
| --- | --- | --- |
| `card_families.card_id` | `card_families.card_id` | Same shape; rebuilt from the Japanese family segment because the legacy names are machine translations and may be split or merged wrongly. |
| `card_families.family_id` | `card_families.family_id` | As above. |

### core_requirements ([db.py:77-85](../../src/bs_database/db.py#L77))

| Legacy column | Target | Note |
| --- | --- | --- |
| `core_requirements.id` | dropped | Surrogate key. |
| `core_requirements.level` | `card_levels.level` | Same value. Table renamed to `card_levels`. |
| `core_requirements.battlePoints` | `card_levels.battle_points` | snake_case ([ADR 0003](../adr/0003-naming-and-schema-versioning.md)); NULL for Nexus. |
| `core_requirements.cores` | `card_levels.cores` | Same name and meaning (cores needed to reach the level). |
| `core_requirements.card_id` | `card_levels.card_id` | Now references the target `cards.id`, found through the card number. |

## 2. Card JSON keys ([batspi_card.py](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/batspi_card.py))

The card JSON is built at [batspi_card.py:132-142](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/batspi_card.py#L132) and loaded by [db.py:113-154](../../src/bs_database/db.py#L113). "Loaded" says what the legacy loader did with the key.

| JSON key | Legacy loader | Target | Known parser bug and note |
| --- | --- | --- | --- |
| `name` | `cards.name` | `cards.name_en` (machine) | Machine translation of the JP title ([:133](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/batspi_card.py#L133)); the Japanese title is read ([:31-38](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/batspi_card.py#L31)) and discarded, so `cards.name_jp` must be re-scraped. A failed translation returns `"Error: ..."` ([:23-28](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/batspi_card.py#L23)). |
| `card_id` | `cards.card_id` | `card_numbers.number` | Passed in by the caller, not read from the page ([:104](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/batspi_card.py#L104)). The set prefix is also the source of `products.code`. |
| `type` | `cards.type_id` via `card_types` | `cards.card_type_id` | Machine-translated line 1 ([:61](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/batspi_card.py#L61)), normalized by `normalize_type` ([normalize.py:105-107](../../src/bs_database/normalize.py#L105)). The target maps the Japanese word (`スピリット`) to a code. |
| `cost` | `cards.cost` | `cards.cost` | Number before `(` ([:62](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/batspi_card.py#L62)). |
| `reduction` | **not loaded** | `card_reductions` (`symbol_id`, `count`) | Two bugs. (1) The mixed form `赤2神1` does not match `(\d+)\s*(.+)` and yields an empty list ([:72-77](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/batspi_card.py#L72)), so the god symbol 神 is lost. (2) A plain number is expanded with the translated **colour** string ([:70](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/batspi_card.py#L70)). It is never loaded ([db.py:122-150](../../src/bs_database/db.py#L122)), so there is nothing to migrate: reductions are re-read from the Japanese text. |
| `symbol` | `cards.symbol`, then `card_colors` via `get_colors_from_symbol` | `card_colors` rows | The key is **misnamed**: it holds the colour (segment 2 of the cost line, [:63](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/batspi_card.py#L63)), not the printed symbols. The printed symbols (`シンボル：`) are never read: `card_symbols` has no legacy source (gap). |
| `family` | `families`, `card_families` | `card_families`, `families`, `family_aliases` | Translated, split on `/` ([:79](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/batspi_card.py#L79)), then cleaned by [normalize.py:57-102](../../src/bs_database/normalize.py#L57). See [section 4](#4-family-mapping-datafamily_mappingtxt). |
| `core_requirements[].level` | `core_requirements.level` | `card_levels.level` | Regex `<(\d+)>Lv(\d+)\s+(\d+)` ([:83](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/batspi_card.py#L83)). |
| `core_requirements[].battlePoints` | `core_requirements.battlePoints` | `card_levels.battle_points` | Same regex. |
| `core_requirements[].cores` | `core_requirements.cores` | `card_levels.cores` | Same regex. **Nexus bug**: the regex needs a BP after `LvN`, so a Nexus level line (`<0>Lv1 <1>Lv2`) yields no rows ([field-inventory.md](field-inventory.md#32-nexus)). The legacy DB has no Nexus levels (642 cards), so they are re-scraped. |
| `image` | `cards.image` | `printing_images.path` | A built path `data/images/<set>/<card_id>.jpg` ([:130](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/batspi_card.py#L130)); see [section 5](#5-other-legacy-artefacts). |

Not emitted by the legacy JSON at all (see the [gap list](#6-gap-list)): effects, flavor text, illustrators, rarity, variants, product names and dates, source URL.

## 3. Fandom set JSON keys ([fandom_sets.py](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/fandom_sets.py))

`parse_table` builds one dict per table row, keyed by the table's header cells ([fandom_sets.py:43-51](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/fandom_sets.py#L43)), so the keys are whatever the wiki table headers are. The set JSON is **never read by the loader** ([db.py:157-164](../../src/bs_database/db.py#L157) only walks card JSON), and `fandom_sets` is not wired to the CLI. The real wiki columns are unverified (Cloudflare blocked the fixtures, which are synthetic; see [field-inventory.md](field-inventory.md#1-sources-overview)), so this mapping is **pending #9**.

| JSON key | Target | Note |
| --- | --- | --- |
| `Card_ID` (from `Number`, normalized to `BSNN-NNN`, [:53-58](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/fandom_sets.py#L53)) | `card_numbers.number` | Used to link the fandom row to a number. The `Number` key itself is deleted ([:58](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/fandom_sets.py#L58)), so it never appears in the JSON. |
| `Name` | `cards.name_en` (source `fandom`) | Preferred over the machine translation when verified; status `reviewed`. Pending #9. |
| `Rarity` | `printings.rarity_id` | Mapped to a `rarities.code`. Pending #9: the batspi `収録` list is the confirmed rarity source. |
| any other header | dropped | Unknown columns are kept in the JSON but have no target. Revisit after #9. |
| set URL (`url[-4:]`, [:44](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/fandom_sets.py#L44)) | `products.code` | Used only to build `Card_ID`; the set code is not written to the JSON. |

## 4. Family mapping ([data/family_mapping.txt](../../data/family_mapping.txt))

| Legacy item | Target | Note |
| --- | --- | --- |
| Each `MT = preferred` line (41 non-empty lines: `Rebirth = Reptile Beast`) | `family_aliases` row with `lang` = `en` and `translation_source_id` = `machine`, `alias` = left side | The left side is a machine-translation output; the right side is the preferred English name and goes to `families.name_en`. Keys are matched in lower case ([normalize.py:17-25](../../src/bs_database/normalize.py#L17)); alias lookup keeps the same behaviour. |
| Right side of each line | `families.name_en` | Becomes the preferred display name; `en_status_id` = `reviewed` (a person wrote the pair) and `en_source_id` = `manual`. |
| Hardcoded substring rule: any family containing `snake` becomes `Dark Snake` ([normalize.py:63-64](../../src/bs_database/normalize.py#L63)) | dropped as code; replaced by explicit `family_aliases` rows for the affected names | Rules in code are replaced by data in `family_aliases`. |
| Heuristics: article stripping, `title()` and plural stripping ([normalize.py:70-85](../../src/bs_database/normalize.py#L70)), splitting of `Different X`, `New X`, `Next Generation of X` ([:40-49](../../src/bs_database/normalize.py#L40)) | dropped | Lossy rules that exist only because the source is machine-translated. With the Japanese family as the identity they are not needed; #11 reviews the remaining names. |

## 5. Other legacy artefacts

| Legacy artefact | Target | Note |
| --- | --- | --- |
| Image path `data/images/<set>/<card_id>.jpg` ([batspi_card.py:20](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/batspi_card.py#L20), [:130](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/batspi_card.py#L130)) | `printing_images.path` | Stored whether or not the file exists; one image per number, so the SECRET and full-art variants collide. The path layout of the artefact is decided in [#13](https://github.com/AleFire99/BS_Database/issues/13). Backslash conversion in [normalize.py:116-117](../../src/bs_database/normalize.py#L116) is a Windows leftover and is dropped. |
| Fandom image download `<images_dir>/BS<nn>/<card_id>.jpg` ([fandom_images.py:58-104](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/fandom_images.py#L58)) | `printing_images` (`source_url`, `sha256`) | Source is the fandom card page (`img.mw-file-element`), not batspi. The file hash and size are not recorded; they are new columns. |
| Set prefix of the card number (`BS72`) | `products.code` | The only place a set exists in the legacy data (no `sets` table). Names, dates and type of the product have no legacy source (gap). |
| `data/extracted_urls.txt` | dropped | An intermediate list of set-page links ([cli.py:117](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/cli.py#L117)); the target keeps URLs in `source_pages.url` instead. |
| Card-number regex `BS\d{2}-\d{3}` ([batspi_links.py:22](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/batspi_links.py#L22)) | `card_numbers.number` | Promo and other number formats are not matched; pending #9. |
| SQLite DB without constraints, foreign keys unenforced | `PRAGMA foreign_keys = ON`, constraints | See the DDL draft in [target-schema.md](target-schema.md). |
| `get_or_create` / skip-existing loader ([db.py:88-95](../../src/bs_database/db.py#L88), [:115-118](../../src/bs_database/db.py#L115)) | dropped | Replaced by the #12 loader that builds the whole database from clean input. |

## 6. Gap list

Target tables and columns with no legacy source. Grouped by the work item that must provide them. Tables that are pure seed lookups are listed with their seed rows.

### Needs #10 scraping (the data is on the page but the legacy scraper never read it)

- `cards.name_jp` (the Japanese title is read then discarded)
- `cards.flavor_text_jp`
- `cards.block_icon`
- `card_symbols` (all columns; the `シンボル：` line)
- `card_reductions` (rebuilt from the Japanese cost line; legacy `reduction` was never stored)
- `card_levels` for Nexus, Brave and Ultimate formats (Nexus levels were dropped by the regex; Brave/Ultimate pending #9)
- `card_effects` (all columns), `card_effect_levels`, `card_effect_keywords`
- `printings` (all columns), including `illustrator`, rarity and variant from the `収録` section
- `products.name_jp`, `products.release_date`, `products.series`, `products.product_type_id`
- `printing_images.source_url` (the legacy path is built, not read) and image links per size
- `sources`, `source_pages`, `card_source_pages`, `product_source_pages` (the legacy JSON has no URL, fetch time or hash)
- `brave_details`, `ultimate_details` (all columns, pending #9: no fixture)

### Needs #11 normalization and translation

- `families.name_jp`, `families.code`, `families.name_en` for the 517 machine-translated families (map them back to Japanese)
- `family_aliases` seeding: 41 mapping lines plus the legacy names
- `cards.name_en`, `cards.flavor_text_en`, `card_effects.timing_en`, `card_effects.text_en`, `products.name_en`, `brave_details.fusion_condition_en`, `ultimate_details.summon_condition_en`: English text, preferably from `fandom`; machine output is marked via `en_source_id` and `en_status_id`
- `keywords` list (only `mirage` is seen)
- Cleaning of the legacy `cards.name` entry that is an `Error:` string

### Needs #13 images

- `printing_images.path`, `sha256`, `width`, `height`, `mime_type` (the legacy DB has only a path string to files that are not in the repository)
- `image_sizes` seed (`small`, `large`)

### Derived by the loader (#12)

- All lookup seed rows: `product_types`, `rarities`, `variants`, `translation_sources`, `translation_statuses`, `effect_kinds`, `symbols`, `colors` (incl. White), `card_types`, `image_sizes`, `schema_meta`
- `card_numbers.card_id` (linking numbers to cards, rule pending #9)
- `cards.card_type_id`: from the Japanese type word via the JP-to-code table
- `card_colors` and `card_families` (re-derived from Japanese text)
- `card_effects.effect_kind_id`, `card_effects.position`, `printings.variant_id` (from `SECRETあり`, `フルアート版`)
- `en_status_id` defaults (`pending`)
- `translation_source_id` of aliases (`machine` for the seeded pairs)
