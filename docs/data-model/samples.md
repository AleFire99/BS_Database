# Sample cards

Hand-modelled samples that show how real cards land in the [target schema](target-schema.md). Every `sql` block runs, in order, against the [DDL draft](target-schema.md#ddl-draft) in an in-memory SQLite database with `PRAGMA foreign_keys = ON`. The blocks are cumulative: later blocks reference rows inserted by earlier ones.

The ids are explicit and match the worked examples of [ADR 0004](../adr/0004-card-printing-identity.md) and of [target-schema.md](target-schema.md#worked-examples-effects): Nexus BS72-069 is card 1, Magic BS72-075 is card 2, Spirit BS72-007 is card 3. The Brave and Ultimate samples continue with cards 4 and 5.

| Sample | Type | Shows | Data from |
| --- | --- | --- | --- |
| [BS72-007](#spirit-bs72-007) | Spirit | levels, effects per level, secret variant, images | fixture `card_spirit.html` |
| [BS72-069](#nexus-bs72-069) | Nexus | reprint (BS72 normal, BS74 full art), no BP | fixture `card_nexus.html` |
| [BS72-075](#magic-bs72-075) | Magic | promo distribution, Mirage keyword, no levels | fixture `card_magic.html` |
| [BS11-051](#brave-bs11-051-evil-fisher) | Brave | legacy-only data, `brave_details` with placeholders | legacy database |
| [BS24-078](#ultimate-bs24-078-ultimate-randolph) | Ultimate | legacy-only data, levels 3 and 4 | legacy database |

Items that depend on the source analysis are **pending #9**. Values that are placeholders rather than data are written in square brackets, for example `[PENDING #9] ...`, so they cannot be mistaken for real text.

## Lookup seed

Only the rows the samples need. A real build seeds the full lists, which are pending #9. `pending` and `normal` are inserted with id 1 because the DDL defaults `en_status_id` and `variant_id` to 1.

```sql
INSERT INTO translation_statuses (id, code, name) VALUES
    (1, 'pending', 'Pending'),
    (2, 'machine', 'Machine translated');

INSERT INTO translation_sources (id, code, name) VALUES
    (1, 'machine', 'Machine translation');

INSERT INTO card_types (id, code, name) VALUES
    (1, 'spirit', 'Spirit'),
    (2, 'nexus', 'Nexus'),
    (3, 'magic', 'Magic'),
    (4, 'brave', 'Brave'),
    (5, 'ultimate', 'Ultimate');

INSERT INTO colors (id, code, name) VALUES
    (1, 'red', 'Red'),
    (2, 'purple', 'Purple'),
    (3, 'blue', 'Blue');

INSERT INTO symbols (id, code, name, color_id) VALUES
    (1, 'red', 'Red', 1),
    (2, 'god', 'God', NULL);

INSERT INTO rarities (id, code, name, sort_order) VALUES
    (1, 'C', 'Common', 1),
    (2, 'R', 'Rare', 2);

INSERT INTO variants (id, code, name) VALUES
    (1, 'normal', 'Normal'),
    (2, 'secret', 'Secret'),
    (3, 'full_art', 'Full art'),
    (4, 'promo_art', 'Promo art');

INSERT INTO product_types (id, code, name) VALUES
    (1, 'booster', 'Booster'),
    (2, 'promo', 'Promo');

INSERT INTO effect_kinds (id, code, name) VALUES
    (1, 'level', 'Level effect'),
    (2, 'constant', 'Constant effect'),
    (3, 'main', 'Main effect'),
    (4, 'set_active', 'While set'),
    (5, 'keyword_block', 'Keyword block');

INSERT INTO keywords (id, code, name) VALUES
    (1, 'mirage', 'Mirage');

INSERT INTO image_sizes (id, code, name) VALUES
    (1, 'small', 'Small'),
    (2, 'large', 'Large');

INSERT INTO sources (id, code, name, base_url) VALUES
    (1, 'batspi', 'batspi.com', 'https://batspi.com/');
```

## Spirit BS72-007

`光爪の武芸者ヘルハウンド`, from the fixture `card_spirit.html`. The `<pre>` gives cost `4(赤2神1)`, colour red, families `眷属・武迅`, two levels (`<1>Lv1 3000`, `<3>Lv2 7000`) and two effect blocks; the first applies to Lv1 and Lv2, the second to Lv2 only (see [Worked examples](target-schema.md#spirit-bs72-007)).

The page says `<R> (SECRETあり)` and links two images, so the number has two printings in BS72: `normal` (rarity R) and `secret`. The rarity of the secret printing is NULL here and which image is the secret art is an assumption (the `-2` file), both pending #9 (see ADR 0004). The `path` of every image is a placeholder: the file layout is decided in [#13](https://github.com/AleFire99/BS_Database/issues/13). The provenance rows use the real fixture hash; `fetched_at` and `parser_version` are sample values.

```sql
INSERT INTO products (id, code, name_ja, name_en, product_type_id, release_date, series, en_source_id, en_status_id) VALUES
    (1, 'BS72', '第1章：廻帰再醒', NULL, 1, '2025-05-17', '契約編：環', NULL, 1);

INSERT INTO cards (id, card_type_id, cost, name_ja, name_en, flavor_text_ja, flavor_text_en, en_source_id, en_status_id, block_icon) VALUES
    (3, 1, 4, '光爪の武芸者ヘルハウンド', NULL,
     'ルーの下に集った武芸者たちは、各々自慢の武器を携えている。その武器
で戦うのは大型のスピリット。彼らの誉れはスピリットの討伐である。',
     NULL, NULL, 1, '12');

INSERT INTO card_numbers (id, number, card_id) VALUES
    (3, 'BS72-007', 3);

INSERT INTO printings (id, card_number_id, product_id, variant_id, rarity_id, illustrator) VALUES
    (5, 3, 1, 1, 2, '伊藤正市'),
    (6, 3, 1, 2, NULL, '伊藤正市');

INSERT INTO printing_images (id, printing_id, image_size_id, path, source_url, sha256, width, height, mime_type) VALUES
    (1, 5, 1, '[PENDING #13] BS72-007-small', '/card/BS7/small/BS72-007.jpg', NULL, NULL, NULL, NULL),
    (2, 5, 2, '[PENDING #13] BS72-007-large', '/card/BS7/BS72-007.jpg', NULL, NULL, NULL, NULL),
    (3, 6, 1, '[PENDING #13] BS72-007-2-small', '/card/BS7/small/BS72-007-2.jpg', NULL, NULL, NULL, NULL),
    (4, 6, 2, '[PENDING #13] BS72-007-2-large', '/card/BS7/BS72-007-2.jpg', NULL, NULL, NULL, NULL);

INSERT INTO card_colors (card_id, color_id) VALUES (3, 1);
INSERT INTO card_symbols (card_id, symbol_id, count) VALUES (3, 1, 1);
INSERT INTO card_reductions (card_id, symbol_id, count) VALUES
    (3, 1, 2),
    (3, 2, 1);

INSERT INTO families (id, code, name_ja, name_en, en_source_id, en_status_id) VALUES
    (1, NULL, '眷属', NULL, NULL, 1),
    (2, NULL, '武迅', NULL, NULL, 1);
INSERT INTO card_families (card_id, family_id) VALUES (3, 1), (3, 2);

INSERT INTO card_levels (id, card_id, level, cores, battle_points) VALUES
    (1, 3, 1, 1, 3000),
    (2, 3, 2, 3, 7000);

INSERT INTO card_effects (id, card_id, position, effect_kind_id, timing_ja, timing_en, text_ja, text_en, en_source_id, en_status_id) VALUES
    (1, 3, 1, 1, '『自分のアタックステップ開始時』', NULL,
     '自分の「契約神ルー」すべてのブレイヴ1つにつき、自分のトラッシュの[ソウルコア]以外のコア2個を系統：「武迅」を持つスピリット/ネクサスに好きなだけ置く。',
     NULL, NULL, 1),
    (2, 3, 2, 1, '『自分のアタックステップ』', NULL,
     '系統：「武迅」を持つ自分のスピリットがアタックしたとき、自分の創界神ネクサス1つにコア+1できる。',
     NULL, NULL, 1);

-- Lv1・Lv2 gives two rows, Lv2 one row.
INSERT INTO card_effect_levels (card_effect_id, card_level_id) VALUES
    (1, 1),
    (1, 2),
    (2, 2);

INSERT INTO source_pages (id, source_id, url, fetched_at, content_sha256, parser_version) VALUES
    (1, 1,
     'https://batspi.com/index.php?%E5%85%89%E7%88%AA%E3%81%AE%E6%AD%A6%E8%8A%B8%E8%80%85%E3%83%98%E3%83%AB%E3%83%8F%E3%82%A6%E3%83%B3%E3%83%89',
     '2026-11-14T00:00:00Z', 'fa996336725daa4c53a748002685a33b8ae883c00b8d321cc429d8e5aae8c302', 'sample');
INSERT INTO card_source_pages (card_id, source_page_id) VALUES (3, 1);
```

## Nexus BS72-069

`ゼウスの雷火山`, from `card_nexus.html`. This is the **reprint sample**: one card, one number, two printings. The BS72 printing is `normal`; the page also lists the BS74 product with the `フルアート版` variant, which the loader maps to `full_art`. The illustrators follow the parenthesised product on the page (to be confirmed in #31) and the booster product type is assumed. No new `cards` or `card_numbers` row is needed for the reprint.

A Nexus has no BP, so `battle_points` is NULL. The plain reduction `(2)` is resolved to the card's own colour, red (assumed, pending #9). Effect 4 has no timing and therefore the kind `constant`.

```sql
INSERT INTO products (id, code, name_ja, name_en, product_type_id, release_date, series, en_source_id, en_status_id) VALUES
    (2, 'BS74', '第3章：覇極来臨', NULL, 1, '2025-11-22', '契約編：環', NULL, 1);

INSERT INTO cards (id, card_type_id, cost, name_ja, name_en, flavor_text_ja, flavor_text_en, en_source_id, en_status_id, block_icon) VALUES
    (1, 2, 3, 'ゼウスの雷火山', NULL,
     '噴火すると、周囲に雷火を落とすオリン随一の山。その有様は、
ゼウスの怒りと揶揄される。　―『創世書記』神世界図125―',
     NULL, NULL, 1, '12');

INSERT INTO card_numbers (id, number, card_id) VALUES
    (1, 'BS72-069', 1);

INSERT INTO printings (id, card_number_id, product_id, variant_id, rarity_id, illustrator) VALUES
    (1, 1, 1, 1, 1, '藤原ひさし'),
    (2, 1, 2, 3, 1, '平坂康也');

INSERT INTO card_colors (card_id, color_id) VALUES (1, 1);
INSERT INTO card_symbols (card_id, symbol_id, count) VALUES (1, 1, 1);
INSERT INTO card_reductions (card_id, symbol_id, count) VALUES (1, 1, 2);

INSERT INTO families (id, code, name_ja, name_en, en_source_id, en_status_id) VALUES
    (3, NULL, '皇獣', NULL, NULL, 1);
INSERT INTO card_families (card_id, family_id) VALUES (1, 3);

INSERT INTO card_levels (id, card_id, level, cores, battle_points) VALUES
    (3, 1, 1, 0, NULL),
    (4, 1, 2, 1, NULL);

INSERT INTO card_effects (id, card_id, position, effect_kind_id, timing_ja, timing_en, text_ja, text_en, en_source_id, en_status_id) VALUES
    (3, 1, 1, 1, '『このネクサスの配置時』', NULL,
     '自分のネクサスが「ゼウス」だけのとき、自分のデッキを上から3枚オープンできる。
その中の「ゼウスの雷火山」以外の「ゼウス」1枚か、系統：「眷属」/「締皇」と「皇獣」を持つスピリットカード1枚を手札に加える。
残ったカードは破棄する。',
     NULL, NULL, 1),
    (4, 1, 2, 2, NULL, NULL,
     '系統：「眷属」/「締皇」を持つ自分の赤のスピリットすべては、相手の効果でフィールドから手札/デッキに戻らない。',
     NULL, NULL, 1);

INSERT INTO card_effect_levels (card_effect_id, card_level_id) VALUES
    (3, 3),
    (3, 4),
    (4, 4);

INSERT INTO source_pages (id, source_id, url, fetched_at, content_sha256, parser_version) VALUES
    (2, 1,
     'https://batspi.com/index.php?%E3%82%BC%E3%82%A6%E3%82%B9%E3%81%AE%E9%9B%B7%E7%81%AB%E5%B1%B1',
     '2026-11-14T00:00:00Z', '795bd5afce8c45a3f43a9e7eeb3003ecc74ce1badf065ff14e8e1deb701a531b', 'sample');
INSERT INTO card_source_pages (card_id, source_page_id) VALUES (1, 2);
```

## Magic BS72-075

`ジャベリンドロー`, from `card_magic.html`. This is the **promo sample**: besides the BS72 booster printing the page lists a distribution entry (`イラスト：ikuyoan(プロモーションカード・ルー)`). It is a product of type `promo` with no code and no release date (SQLite allows several NULLs in the UNIQUE `code`), and a `promo_art` printing without rarity. The illustrator assignment is assumed (ADR 0004).

The Magic card has no level line and no symbol line, so there are no `card_levels`, `card_effect_levels` or `card_symbols` rows, and no flavor text. The first block is the keyword block `【ミラージュ：コスト2(1)…】`: it is kept as text and the Mirage keyword is linked with its parameter `コスト2(1)` as printed.

```sql
INSERT INTO products (id, code, name_ja, name_en, product_type_id, release_date, series, en_source_id, en_status_id) VALUES
    (3, NULL, 'バトルスキーイベント提供記念品', NULL, 2, NULL, NULL, NULL, 1);

INSERT INTO cards (id, card_type_id, cost, name_ja, name_en, flavor_text_ja, flavor_text_en, en_source_id, en_status_id, block_icon) VALUES
    (2, 3, 4, 'ジャベリンドロー', NULL, NULL, NULL, NULL, 1, '12');

INSERT INTO card_numbers (id, number, card_id) VALUES
    (2, 'BS72-075', 2);

INSERT INTO printings (id, card_number_id, product_id, variant_id, rarity_id, illustrator) VALUES
    (3, 2, 1, 1, 1, '高梨かりた'),
    (4, 2, 3, 4, NULL, 'ikuyoan');

INSERT INTO card_colors (card_id, color_id) VALUES (2, 1);
INSERT INTO card_reductions (card_id, symbol_id, count) VALUES (2, 1, 2);
INSERT INTO card_families (card_id, family_id) VALUES (2, 2);

INSERT INTO card_effects (id, card_id, position, effect_kind_id, timing_ja, timing_en, text_ja, text_en, en_source_id, en_status_id) VALUES
    (5, 2, 1, 5, NULL, NULL,
     '【ミラージュ：コスト2(1)(このカードは手札からセットできる)】',
     NULL, NULL, 1),
    (6, 2, 2, 4, '『自分のアタックステップ開始時』', NULL,
     '相手の手元にあるカードの色3色につき、自分の創界神ネクサスの「契約神ルー」1つにコア+1する。
この効果で対象のコアが3個以上になったとき、自分はデッキから1枚ドローできる。',
     NULL, NULL, 1),
    (7, 2, 3, 3, NULL, NULL,
     '自分はデッキから2枚ドローする。
その後、自分の「契約神ルー」があるとき、自分のデッキを上から4枚オープンできる。
その中の系統：「締皇」と「武迅」を持つスピリットカード1枚を手札に加える。
残ったカードはデッキの下に戻す。',
     NULL, NULL, 1);

INSERT INTO card_effect_keywords (card_effect_id, keyword_id, parameter_ja) VALUES
    (5, 1, 'コスト2(1)');

INSERT INTO source_pages (id, source_id, url, fetched_at, content_sha256, parser_version) VALUES
    (3, 1,
     'https://batspi.com/index.php?%E3%82%B8%E3%83%A3%E3%83%99%E3%83%AA%E3%83%B3%E3%83%89%E3%83%AD%E3%83%BC',
     '2026-11-14T00:00:00Z', 'a93ae0bbbeb37503ab647ea0ee88843de2d6629369a1d066fdb201f8e8c1fd08', 'sample');
INSERT INTO card_source_pages (card_id, source_page_id) VALUES (2, 3);
```

## Brave BS11-051 Evil Fisher

No fixture exists for a Brave card. The only data is the **legacy database**: English name `Evil Fisher` (machine translated by the legacy scraper), cost 4, colour purple, family `Darkling` and one level row (Lv1, 1 core, 2000 BP). Everything else is unknown until the Brave page format is analysed in [#9](https://github.com/AleFire99/BS_Database/issues/9):

- `name_ja` is NOT NULL, so it holds the marked placeholder `[PENDING #9] BS11-051`.
- The family has no Japanese name either (`families.name_ja` is NOT NULL and UNIQUE), so a placeholder is used there too. The legacy English name is stored as `name_en`, status `machine`.
- `brave_details` has a row, because the card is a Brave, but fusion condition and BP bonus are NULL and the translation status is `pending`.
- The BS11 product name is a placeholder, the product type `booster` and the printing without rarity are assumptions. There are no effects, no symbols and no reductions in the legacy data.

```sql
INSERT INTO products (id, code, name_ja, name_en, product_type_id, release_date, series, en_source_id, en_status_id) VALUES
    (4, 'BS11', '[PENDING #9] BS11 name', NULL, 1, NULL, NULL, NULL, 1);

INSERT INTO cards (id, card_type_id, cost, name_ja, name_en, flavor_text_ja, flavor_text_en, en_source_id, en_status_id, block_icon) VALUES
    (4, 4, 4, '[PENDING #9] BS11-051', 'Evil Fisher', NULL, NULL, 1, 2, NULL);

INSERT INTO card_numbers (id, number, card_id) VALUES
    (4, 'BS11-051', 4);

INSERT INTO printings (id, card_number_id, product_id, variant_id, rarity_id, illustrator) VALUES
    (7, 4, 4, 1, NULL, NULL);

INSERT INTO card_colors (card_id, color_id) VALUES (4, 2);

INSERT INTO families (id, code, name_ja, name_en, en_source_id, en_status_id) VALUES
    (4, 'darkling', '[PENDING #9] Darkling', 'Darkling', 1, 2);
INSERT INTO card_families (card_id, family_id) VALUES (4, 4);

INSERT INTO card_levels (id, card_id, level, cores, battle_points) VALUES
    (5, 4, 1, 1, 2000);

INSERT INTO brave_details (card_id, fusion_condition_ja, fusion_condition_en, fusion_bp_bonus, en_source_id, en_status_id) VALUES
    (4, NULL, NULL, NULL, NULL, 1);
```

## Ultimate BS24-078 Ultimate Randolph

Also legacy-only: English name `Ultimate Randolph`, cost 6, colour blue, families `God Of Fighting` and `Incarnate`, and two level rows (Lv3: 1 core, 12000 BP; Lv4: 4 cores, 18000 BP). Ultimate levels start at 3, so `card_levels.level` is not required to start at 1. The same placeholder rules as for the Brave apply: marked `name_ja`, family and product names, the booster product type assumed, and `ultimate_details` with a NULL summon condition, pending #9.

```sql
INSERT INTO products (id, code, name_ja, name_en, product_type_id, release_date, series, en_source_id, en_status_id) VALUES
    (5, 'BS24', '[PENDING #9] BS24 name', NULL, 1, NULL, NULL, NULL, 1);

INSERT INTO cards (id, card_type_id, cost, name_ja, name_en, flavor_text_ja, flavor_text_en, en_source_id, en_status_id, block_icon) VALUES
    (5, 5, 6, '[PENDING #9] BS24-078', 'Ultimate Randolph', NULL, NULL, 1, 2, NULL);

INSERT INTO card_numbers (id, number, card_id) VALUES
    (5, 'BS24-078', 5);

INSERT INTO printings (id, card_number_id, product_id, variant_id, rarity_id, illustrator) VALUES
    (8, 5, 5, 1, NULL, NULL);

INSERT INTO card_colors (card_id, color_id) VALUES (5, 3);

INSERT INTO families (id, code, name_ja, name_en, en_source_id, en_status_id) VALUES
    (5, 'god_of_fighting', '[PENDING #9] God Of Fighting', 'God Of Fighting', 1, 2),
    (6, 'incarnate', '[PENDING #9] Incarnate', 'Incarnate', 1, 2);
INSERT INTO card_families (card_id, family_id) VALUES (5, 5), (5, 6);

INSERT INTO card_levels (id, card_id, level, cores, battle_points) VALUES
    (6, 5, 3, 1, 12000),
    (7, 5, 4, 4, 18000);

INSERT INTO ultimate_details (card_id, summon_condition_ja, summon_condition_en, en_source_id, en_status_id) VALUES
    (5, NULL, NULL, NULL, 1);
```

## Placeholders pending #9

| Where | Placeholder | Needs |
| --- | --- | --- |
| `cards.name_ja` of BS11-051 and BS24-078 | `[PENDING #9] <number>` | Japanese names from the batspi pages. |
| `families.name_ja` of `Darkling`, `God Of Fighting`, `Incarnate` | `[PENDING #9] <English name>` | Japanese family names. |
| `products.name_ja` of BS11 and BS24 | `[PENDING #9] <code> name` | Product names from the set pages. |
| `brave_details`, `ultimate_details` | NULL fields | Fusion and summon condition formats. |
| BS11-051 and BS24-078 effects, symbols, reductions, rarity, illustrator | no rows or NULL | Brave and Ultimate page format. |
| `printing_images.path` | `[PENDING #13] ...` | File layout, decided in #13. |
| Secret printing rarity of BS72-007 | NULL | Rarity code of the secret variant. |
