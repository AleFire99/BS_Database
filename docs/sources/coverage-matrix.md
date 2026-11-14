# Field coverage matrix

For every column of the [target schema](../data-model/target-schema.md) (the [DDL draft](../data-model/target-schema.md#ddl-draft) is the authoritative column list), this matrix records what each source offers, with a sample value and the fixture it was read from. It is evidence for the source-of-truth decision ([#56](https://github.com/AleFire99/BS_Database/issues/56), ADR 0007) and the scraper rewrite ([#10](https://github.com/AleFire99/BS_Database/issues/10)). It makes no modelling decision and proposes no schema change. Terms are defined in the [glossary](../domain/glossary.md). Task: [#55](https://github.com/AleFire99/BS_Database/issues/55).

## How to read this document

### Evidence base

- **batspi.com** is the live source. Its cells are read from the committed fixtures in [tests/fixtures/html/](../../tests/fixtures/html/) (manifest: [fixtures.json](../../tests/fixtures/html/fixtures.json), overview: [README](../../tests/fixtures/html/README.md)). No page was fetched for this document.
- **official** (`battlespirits.com`) is a survey only ([official.md §4](official.md#4-fields-offered-mapped-to-the-field-inventory)). There is no official fixture: its cells come from the documented result-list markup, and the detail view was never fetched.
- **fandom** is dropped for v1 ([fandom.md](fandom.md)). Its fixtures are synthetic, so no fandom cell is confirmed.
- The policy for images is URLs only ([policy.md §3.6](policy.md#36-images), [ADR 0006](../adr/0006-scraping-and-redistribution-policy.md)).

### Status vocabulary

| Status | Meaning |
| --- | --- |
| `confirmed` | Seen in a committed fixture. The cell names the fixture, and the sample can be found in that file by `grep` (see the note below). |
| `derived` | Not printed as such; computed from other fields (for example a set code from a card number). |
| `absent` | The source was checked and does not carry the field (or does not for the cases named). |
| `unknown` | The source may carry it, but no fixture and no survey shows it. |
| `not fetched` | The source was not fetched at all (fandom, dropped for v1). |

Notation in the cells: `` `sample` @ `file.html` `` is a value found in that fixture. Samples are matched against the decoded text of the file: `<` and `>` appear as `&lt;` and `&gt;` in the HTML, `<br />` is a line break, and a name that carries ruby readings is split by `<rb>`/`<rt>` elements. Official cells never cite a fixture, so the best status they can have is `unknown (listed in the result list)`.

Scope rule: every column of the DDL draft is covered. Surrogate `id` columns and foreign keys are `derived` by the build and are listed only where the link itself needs a source (for example which printing an image shows). Lookup tables seeded by the project (`code`/`name` pairs) are `derived`.

### The fixtures used

| File | Page | Notes |
| --- | --- | --- |
| `card_spirit.html` | `光爪の武芸者ヘルハウンド`, `BS72-007` | Spirit, contract era, untrimmed |
| `card_nexus.html` | `ゼウスの雷火山`, `BS72-069` | Nexus, untrimmed |
| `card_magic.html` | `ジャベリンドロー`, `BS72-075` | Magic, untrimmed |
| `card_brave.html` | `砲凰竜フェニック・キャノン`, `BS10-062` and `BS38-RV022` | Brave, two numbers, pre-erratum blocks |
| `card_ultimate.html` | `アルティメット・ジークフリード`, `SD19-X01` and `SD67-CP01` | Ultimate |
| `card_nexus_soukaishin.html` | `創界神アポローン`, `BS44-X07` | 創界神 Nexus |
| `card_flip.html` | `赤の世界／赤き神龍皇`, `BS52-TX01` and `BS73-TCP01` | Flip (転醒) card, faces `(A)` and `(B)` |
| `card_spirit_bs01.html` | `ゴラドン`, `BS01-001` and `BSC22-001` | Oldest era |
| `card_spirit_xx_bs31.html` | `六絶神 鉄壁のクロム・リゼルファー`, `BS31-XX02` | XX rare |
| `card_promo.html` | `焔竜翼人マ・ドー`, `P001`, `EX001`, `P20-19` | Promo numbers |
| `card_magic_flash.html` | `ダブルドロー`, `BS01-117` and `BSC22-117` | Magic with `メイン：` and `フラッシュ：` |
| `set.html`, `set_bs01.html`, `set_bs52.html`, `set_sd54.html`, `set_wafer.html`, `set_cb34.html` | Set (product) pages | BS72, BS01, BS52, SD54, a wafer set, CB34 |
| `list_promo.html` | `プロモーションカード` | Partial listing page |

### Page facts that shape many cells

- **Trimmed pages.** Every batspi fixture except `card_spirit.html`, `card_nexus.html`, `card_magic.html`, `set.html` and `index.html` is trimmed ([README](../../tests/fixtures/html/README.md#trimming)): the header is removed, so `<h1 class="title">` is gone and the page name is read from `<title>` (for example `<title>砲凰竜フェニック・キャノン - バトルスピリッツ wiki` in `card_brave.html`). The untrimmed pages keep the `<h1>` and the `Last-modified` stamp (for example `Last-modified: 2025-06-24` @ `card_spirit.html`).
- **Several `<pre>` blocks per page.** A card block is a `<pre>` whose first line is a type. One page serves every number that shares the card name, so a page has one block and one `<h3>` heading `<…>` per number, paired by position. Other `<pre>` blocks are not printed numbers: pre-erratum blocks under `(エラッタ前) ▼` and Q&A answers, and in `card_magic_flash.html` a collapsed block under `体験会でのスペック ▼` that starts with a type line but has no heading.
- **Related-card listings** (`card_magic.html`, `card_magic_flash.html`, `card_brave.html`, `card_flip.html`, `card_spirit_xx_bs31.html`) repeat the text of other cards in flattened form. They show more cost lines and colours than the card's own block, but they are not the card's own data. The table marks such samples "related listing".

## 1. Identity

Tables: `cards`, `card_numbers`, `printings`, `products`, `product_types`, `rarities`, `variants`. Notes for #10 are parse hints, not decisions.

### cards

| Column | batspi | official | fandom | Notes for #10 |
| --- | --- | --- | --- | --- |
| `name_ja` | `confirmed`: `<title>` of the page, `光爪の武芸者ヘルハウンド - バトルスピリッツ wiki` @ `card_spirit.html`; `ゼウスの雷火山` @ `card_nexus.html`; also the `<h3>` of each number (ruby: `<rb>砲凰竜</rb>` @ `card_brave.html`) | `unknown` (listed): `h3.name`, Japanese only | `not fetched` | Read the name from `<title>` without the suffix `バトルスピリッツ wiki` and its dash (the `<h1>` is missing on trimmed pages). The `<h3>` splits the name with ruby and spaces. A flip page names two cards: `赤の世界／赤き神龍皇` @ `card_flip.html`, one `<h3>` per face |
| `name_en` | `confirmed` on older cards, in the `<h3>` after `/`: `The GunDragon Phoenix-Cannon` @ `card_brave.html`; `Goradon` @ `card_spirit_bs01.html`; `Double Draw` @ `card_magic_flash.html`; `The FlameWingDragon Ma-Dwo` @ `card_promo.html`. `absent` on `card_spirit.html`, `card_nexus.html`, `card_magic.html`, `card_ultimate.html`, `card_nexus_soukaishin.html`, `card_flip.html` and `card_spirit_xx_bs31.html` (no `/<EN>` part) | `absent`: the result list is Japanese only | `not fetched`: the legacy scraper read a `Name` column from the set table ([fandom.md §2](fandom.md#2-what-the-wiki-offers)); the only fixture is synthetic (`Alpha Dragon` @ `fandom_set_BS47.html`) | The English name is only on some pages and some `<h3>` (the `<h3>` of `card_ultimate.html` has none). Never treat a missing English name as an error. Machine translation is the fallback (#11) |
| `flavor_text_ja` | `confirmed`: line `フレーバーテキスト：` followed by the text @ `card_spirit.html`. `absent` on `card_magic.html`, `card_nexus_soukaishin.html` and the `SD67-CP01` block of `card_ultimate.html` | `unknown`: effect and flavor text are not in the result list | `not fetched` | The text is hard-wrapped by the wiki: `その武器` and `で戦うのは大型のスピリット。` @ `card_spirit.html` are one sentence on two lines. It may end with an attribution `―星文学者リリア『八十八星夜話』鳳凰座―` @ `card_brave.html`. It can carry a product note on the same line, `フレーバーテキスト：(バトルスピリッツ メモリアルカードダスセット Hero Ver.)` @ `card_magic_flash.html`, and it differs between the two numbers of that page (the second block has none), so it is per printed number |
| `flavor_text_en` | `absent` (Japanese only) | `absent` | `not fetched` | Machine translation in #11 |
| `en_source_id`, `en_status_id` | `derived` by the build (see section 4, multilingual text) | `absent` | `not fetched` | Not source data |
| `block_icon` | `confirmed`: `ブロックアイコン:<12>` @ `card_spirit.html`, in the line `[BS72]` + product + icon + date. It is per product, not per card: `ブロックアイコン:<5>` for `BS44` and `ブロックアイコン:<6>` for `SD51` on the same number @ `card_nexus_soukaishin.html`. `absent` on older entries: `(BS01-001)` followed by `2008年09月13日` and no icon @ `card_spirit_bs01.html`; and on distributions such as `バトスピショップバトル` @ `card_promo.html` | `unknown`: `block_icon[]` is a search filter ([official.md §3](official.md#3-rendering-and-card-markup)), the value per card was not read | `not fetched` | The icon is on the product line of the `h4 収録/掲載/配布 ブロックアイコン` section. The icon is optional on that line |
| `id`, `card_type_id` | `derived` | | | `id` is a surrogate key; `card_type_id` is covered by [card_types](#cards-gameplay-columns-and-card_types) |

### card_numbers

| Column | batspi | official | fandom | Notes for #10 |
| --- | --- | --- | --- | --- |
| `number` | `confirmed`: `<span class="cardno">BS72-007</span>` @ `card_spirit.html`. Other forms: `P001`, `EX001`, `P20-19` @ `card_promo.html`; `BS31-XX02` @ `card_spirit_xx_bs31.html`; `SD19-X01` @ `card_ultimate.html`; `BS38-RV022` @ `card_brave.html`; `BS44-X07` @ `card_nexus_soukaishin.html`; faces `BS52-TX01(A)` @ `card_flip.html` | `unknown` (listed): `.number .num`, includes reprint prefixes such as `26R` | `not fetched`: legacy `Number` column | The `<h3>` heading carries the number only on pages with several numbers (`<BS10-062>` @ `card_brave.html`); a single-number page has a bare name heading with no number (`card_nexus.html`, `card_spirit.html`). The `cardno` spans also occur in the related-card listing (`card_brave.html` has nine), so take the first span per print, or the number in the image caption (`BS72-007`, a line break, then `契約編：環 第1章：廻帰再醒`). A flip number has a face suffix `(A)`/`(B)` that the `収録` list drops (`転醒編 第1章：輪廻転生 <転醒X>` follows `BS52-TX01` @ `card_flip.html`) |
| `id`, `card_id` | `derived` | | | `card_id` comes from the pairing of `<h3>` and card block by position, then from [ADR 0004](../adr/0004-card-printing-identity.md) |

### printings

| Column | batspi | official | fandom | Notes for #10 |
| --- | --- | --- | --- | --- |
| `card_number_id`, `product_id` | `confirmed`: the `h4 収録` section lists, per number, the products that contain it: `契約編：環 第1章：廻帰再醒` and `契約編：環 第3章：覇極来臨` for `BS72-069` @ `card_nexus.html` | `unknown` (listed): `prodid` filter, product names such as `[CB31]...` | `not fetched` | One page lists many products for one number (`card_brave.html` has eight images for `BS10-062`). Each product with a rarity is a printing candidate |
| `variant_id` | `confirmed`, but only as free-text notes after the rarity: `(SECRETあり)` @ `card_spirit.html`; `(フルアート版)` @ `card_nexus.html`; `(パラレルあり)` @ `card_flip.html`; `(特別仕様)` @ `card_spirit_xx_bs31.html`; `(金色仕様・2013/11/28頃発送)` @ `card_ultimate.html`; image caption `シークレット` @ `card_spirit.html` | `unknown` | `not fetched` | The note list is open-ended, so the loader maps known notes and leaves the rest as `normal`. A note such as `(SECRETあり)` says a secret print exists, not which image it is |
| `rarity_id` | `confirmed`: `<R>` after the product name `契約編：環 第1章：廻帰再醒 <R> (SECRETあり)` @ `card_spirit.html`; `<C>` @ `card_nexus.html`; on set pages the token follows the name, `BS72-005 サンダー・Z・チュウレオン R` @ `set.html`. `absent` on set pages for commons: `(※以下、カード名の隣にレアリティの記述がないものはコモンです)` @ `set.html` | `unknown` (listed): `.number .rarity`, for example `C` | `not fetched`: legacy `Rarity` column; the fixture is synthetic | On a set page a missing token means common. The distribution line `バトルスキーイベント提供記念品` @ `card_magic.html` appears in the block-icon list with no rarity token, so the column must stay nullable |
| `illustrator` | `confirmed`: `イラスト：伊藤正市` @ `card_spirit.html`. Several lines per block, optionally tied to a product: `イラスト：平坂康也(契約編：環 第3章：覇極来臨)` @ `card_nexus.html`; `イラスト：SUNRISE D.I.D.` @ `card_brave.html`. `absent` on the first block of `card_magic_flash.html` (flavor text but no `イラスト：` line) | `unknown`: not in the result list | `not fetched` | `イラスト：` can repeat inside one block. A product in brackets ties the credit to a printing; a line with none applies to the first print |
| `id` | `derived` | | | Surrogate key |

### products

| Column | batspi | official | fandom | Notes for #10 |
| --- | --- | --- | --- | --- |
| `code` | `confirmed` on set pages: `ブースターパック第72弾(BS72)` @ `set.html`; `SD54(スターターデッキ54)` @ `set_sd54.html`; `コラボブースター第34弾(CB34)` @ `set_cb34.html`; on card pages `[BS72]` @ `card_spirit.html`. `derived` when the page has no code line: `set_bs01.html` and `set_bs52.html` show no `(BS01)`/`(BS52)`, the code is the number prefix of `BS01-001`. `absent` for distributions (`バトスピショップバトル` @ `card_promo.html`) and for the wafer set `バトルスピリッツ ウエハース ～蛇皇襲来～` @ `set_wafer.html` | `unknown` (listed): `prodid` filter, names like `[CB31]...` | `not fetched` | The code text differs by product kind. A product with no code gets a NULL `code` |
| `name_ja` | `confirmed`: `契約編：環 第1章：廻帰再醒` @ `set.html` (`<title>`); the same text is the link text of the `収録` list @ `card_spirit.html` | `unknown` (listed): the product name in the `prodid` filter | `not fetched` | The `<h2>` carries ruby and spaces (`契約編(けいやくへん):環(かん)` @ `set.html`); use `<title>` |
| `name_en` | `absent` | `unknown` | `not fetched` | Machine translation in #11 |
| `product_type_id` | `derived` from the header line and the code prefix: `ブースターパック第72弾(BS72)` @ `set.html`; `コラボブースター第34弾(CB34)` @ `set_cb34.html`; `1パックカード1枚+ウエハース1枚` @ `set_wafer.html`; the page `プロモーションカード` @ `list_promo.html` | `unknown` | `not fetched` | No page prints a type name as a field. The planned codes (`booster`, `starter`, `promo`, `magazine`, `collab`, `other`) are the loader's reading of the header line |
| `release_date` | `confirmed`: `2025年5月17日発売` @ `set.html`; `2008年9月13日発売` @ `set_bs01.html`; per product on card pages `2025年05月17日` @ `card_spirit.html` (zero padded). `absent` for distributions: `バトスピショップバトル` has no date @ `card_promo.html` | `unknown` | `not fetched` | Two formats: `YYYY年M月D日発売` on set pages, `YYYY年MM月DD日` on card pages. Convert both to ISO-8601 |
| `series` | `derived` from the name prefix: `契約編` in `契約編：環 第1章：廻帰再醒` @ `set.html`. The neighbours are given by `Before：契約編：真 第4章：神王の帰還` @ `set.html` | `unknown` | `not fetched` | No separate series field exists on the page; the loader splits the name |
| `en_source_id`, `en_status_id` | `derived` by the build | `absent` | `not fetched` | Not source data |
| `id` | `derived` | | | Surrogate key |

### product_types

| Column | batspi | official | fandom | Notes for #10 |
| --- | --- | --- | --- | --- |
| `code`, `name` | `derived`: a lookup seeded by the loader, never read from a page. The header lines that the loader reads are listed under `products.product_type_id` | `absent` | `absent` | The final list of codes is the loader's choice (#12) |

### rarities

| Column | batspi | official | fandom | Notes for #10 |
| --- | --- | --- | --- | --- |
| `code` | `confirmed`: `<R>` @ `card_spirit.html`; `<C>` @ `card_nexus.html`; `<X>` @ `card_ultimate.html`; `<XX>` @ `card_spirit_xx_bs31.html`; `<転醒X>` and `<CP>` @ `card_flip.html`; `<P>` and `<EX>` @ `card_promo.html`. Set-page tokens: `R` and `M` @ `set.html`, `U` @ `set_bs01.html` | `unknown` (listed): `.number .rarity` and a `rarity[]` filter | `not fetched` | The codes are not all ASCII (`転醒X`). The set header names the scale of that set: `コモン(C)=60種、レア(R)=18種、マスターレア(M)=12種、Xレア(X)=9種、契約Xレア(契約X)=3種、AXレア=3種` @ `set.html` |
| `name` | `absent` as English; the Japanese names are in the set header: `マスターレア(M)` @ `set.html`, `アンコモン(U)` @ `set_bs01.html` | `absent` | `not fetched` | The English display names are the loader's |
| `sort_order` | `absent`: no page gives a global order. The set header lists a scale from common to rare, but it differs per set (`アンコモン(U)` only in `set_bs01.html`) | `absent` | `not fetched` | A fixed seed table, not source data |
| `id` | `derived` | | | Surrogate key |

### variants

| Column | batspi | official | fandom | Notes for #10 |
| --- | --- | --- | --- | --- |
| `code`, `name` | `derived` from the notes listed under `printings.variant_id`: `(SECRETあり)`, `(フルアート版)`, `(パラレルあり)`, `(特別仕様)` | `unknown` | `not fetched` | The loader maps the known notes; the full set of notes is not known |
| `id` | `derived` | | | Surrogate key |

## 2. Gameplay

Tables: `card_types`, `colors`, `symbols`, `card_colors`, `card_symbols`, `card_reductions`, `card_levels`, `families`, `family_aliases`, `card_families`, `brave_details`, `ultimate_details`. Line numbers are those of the `<pre>` block with the type line as line 1.

### cards (gameplay columns) and card_types

| Column | batspi | official | fandom | Notes for #10 |
| --- | --- | --- | --- | --- |
| `card_types.code` (via `cards.card_type_id`) | `confirmed`, line 1: `スピリット` @ `card_spirit.html`; `ネクサス` @ `card_nexus.html`; `マジック` @ `card_magic.html`; `ブレイヴ` @ `card_brave.html`; `アルティメット` @ `card_ultimate.html` | `unknown` (listed): `.type .category`, also a `category[]` filter | `not fetched` | The type can carry a restriction suffix: `ネクサス(制限カード<1>)` and `スピリット(制限カード<1>)` @ `card_flip.html`. A trailing space also occurs after the type in `card_spirit_xx_bs31.html` (`スピリット` then a space). Strip both before the lookup. The suffix has no target column (see the gap list) |
| `card_types.name` | `absent` as English | `absent` | `not fetched` | Seed table |
| `cards.cost` | `confirmed`, line 2, the number before `(`: `4(赤2神1)` @ `card_spirit.html`; `0(0)` @ `card_spirit_bs01.html`; `6()` @ `card_flip.html` | `unknown` (listed): `.costVal`, a plain number | `not fetched` | `XX` rares print `0(0)/白/絶晶神` @ `card_spirit_xx_bs31.html` but a text rule sets the cost, `自分の白以外のスピリットがいる間、このカードをコスト8にする。` @ `card_spirit_xx_bs31.html`. Store the printed cost |

### colors, card_colors

| Column | batspi | official | fandom | Notes for #10 |
| --- | --- | --- | --- | --- |
| `card_colors` (segment 2 of line 2) | `confirmed`, single colour: `赤` @ `card_spirit.html`; `0(0)/白/絶晶神` @ `card_spirit_xx_bs31.html`. Several colours are concatenated with no separator; the only samples are in related listings: `4(赤1紫1緑1白1黄1青1)/赤紫緑白黄青/起幻` @ `card_flip.html`; `赤紫` @ `card_magic.html` | `unknown` (listed): `.type .attribute`, also an `attribute[]` filter | `not fetched` | Split the colour token character by character. All six glyphs 赤 紫 緑 白 黄 青 occur in related listings of the fixtures, none of 紫 緑 黄 青 in a card's own colour field |
| `colors.code`, `colors.name` | `derived`: seed table keyed by the six glyphs above | `absent` | `not fetched` | White is a colour in the target and missing in the legacy table |

### symbols, card_symbols

| Column | batspi | official | fandom | Notes for #10 |
| --- | --- | --- | --- | --- |
| `card_symbols` (line `シンボル：`) | `confirmed`: `シンボル：赤` @ `card_spirit.html`; `シンボル：白` @ `card_spirit_xx_bs31.html`; `シンボル：神` @ `card_nexus_soukaishin.html`; `シンボル：極` @ `card_ultimate.html`; `シンボル：なし` @ `card_brave.html`. Two symbols are concatenated, `シンボル：緑青` @ `card_flip.html` (related listing). `absent` on `card_magic.html` | `unknown`: not in the result list | `not fetched` | The line is optional. Two glyphs mean two symbols; a doubled glyph (`赤赤`) was not seen, so the `count` rule is untested. Also seen: `シンボル：EX赤` @ `card_magic_flash.html` (the collapsed `体験会でのスペック` block) |
| `symbols.code`, `symbols.name`, `symbols.color_id` | `derived`: seed table. The glyphs `極` @ `card_ultimate.html`, `全` (`6(全1極3)` @ `card_ultimate.html`) and `EX赤` are not in the planned symbol list | `absent` | `not fetched` | See the gap list |
| `card_symbols.count` | `unknown` for doubles; `derived` as 1 per glyph | `unknown` | `not fetched` | |

### card_reductions

| Column | batspi | official | fandom | Notes for #10 |
| --- | --- | --- | --- | --- |
| `card_reductions` (parentheses of line 2) | `confirmed`: `4(赤2神1)` @ `card_spirit.html`; `5(赤2白2)` @ `card_brave.html`; `3(2)` @ `card_nexus.html`; `4(2)` @ `card_magic.html`; `6(全1極3)` @ `card_ultimate.html`; `6()` @ `card_flip.html`; `0(0)` @ `card_spirit_bs01.html`. In related listings: `5(赤2白1全1)`, `7(白3赤3)` and `5(白2神1)` @ `card_brave.html`; `4(赤1紫1緑1白1黄1青1)` @ `card_flip.html`. The glossary form `3(2 紫, 1 神)` was not seen on any page | `unknown` (listed): `.alleviationVal` icons, `alt` = colour, counts not checked | `not fetched` | Grammar: a plain number `(N)`, or colour glyph + count pairs joined with no separator, or the empty `()`; `全` is "any colour" and `極` the ultimate symbol. The colour order is not fixed (`白3赤3`). A plain `(N)` means N symbols of the card's own colour, per the schema notes |
| `count` | `confirmed`: the digit after each glyph (`赤2` in `4(赤2神1)` @ `card_spirit.html`) | `unknown` | `not fetched` | `(0)` gives no row |

### card_levels

| Column | batspi | official | fandom | Notes for #10 |
| --- | --- | --- | --- | --- |
| `level`, `cores` | `confirmed`, line 3: `<1>Lv1 3000 <3>Lv2 7000` @ `card_spirit.html` (cores 1 and 3); Nexus `<0>Lv1 <1>Lv2` @ `card_nexus.html`; Ultimate levels start at 3, `<1>Lv3 10000 <3>Lv4 14000 <5>Lv5 20000` @ `card_ultimate.html`; three levels `<1>Lv1 5000 <3>Lv2 9000 <4>Lv3 12000` @ `card_flip.html`; one level `<1>Lv1 6000` @ `card_flip.html` | `unknown` | `not fetched` | Magic has no level line (`card_magic.html` goes from the cost line to the effects). The cores `<n>` come before `LvN`. Level 6 was not seen in a card's own block |
| `battle_points` | `confirmed`: `3000` and `7000` above; `NULL` for the Nexus `<0>Lv1 <1>Lv2` @ `card_nexus.html` | `unknown` | `not fetched` | The same number can have different BP per print: `<1>Lv1 1000 <3>Lv2 3000` against `<1>Lv1 2000 <3>Lv2 5000` @ `card_spirit_bs01.html`. Brave: `<1>Lv1 3000 <0>合体+3000` @ `card_brave.html`: the second token is the fusion bonus, not a level (see `brave_details`). Overclock: `OC<5+>+6000` @ `card_ultimate.html` has no column |
| `id`, `card_id` | `derived` | | | Surrogate and foreign key |

### families, family_aliases, card_families

| Column | batspi | official | fandom | Notes for #10 |
| --- | --- | --- | --- | --- |
| `card_families` and `families.name_ja` (segment 3 of line 2) | `confirmed`: `眷属・武迅` @ `card_spirit.html`; `皇獣` @ `card_nexus.html`; `創界神・オリン` @ `card_nexus_soukaishin.html`; `起幻・眷属・古竜` @ `card_flip.html`; `極契約・新生・古竜` @ `card_ultimate.html`. `absent` on `card_magic_flash.html` (`4(2)/赤`, no third segment) | `unknown` (listed): `.type .system`, also a `system[]` filter with 351 options | `not fetched` | Families are separated by `・`. A third segment can be missing (older Magic). A family name can be a placeholder (`系統A` in the `体験会でのスペック` block @ `card_magic_flash.html`) |
| `families.name_en`, `families.code` | `absent` | `absent` | `not fetched` | English names come from `data/family_mapping.txt` and machine translation (#11) |
| `family_aliases.alias`, `family_aliases.lang`, `family_aliases.family_id`, `family_aliases.translation_source_id` | `absent` | `absent` | `not fetched` | Seeded from the legacy mapping (`data/family_mapping.txt`), not from a source |
| `en_source_id`, `en_status_id` | `derived` | | | Not source data |

### brave_details

| Column | batspi | official | fandom | Notes for #10 |
| --- | --- | --- | --- | --- |
| `fusion_condition_ja` | `confirmed`: `合体条件：コスト3以上` @ `card_brave.html`; two lines on `BS38-RV022`, `右合体条件：コスト5以上` and `左合体条件：コスト3以上` @ `card_brave.html` | `unknown` | `not fetched` | One column holds one or two lines. The label is part of the line |
| `fusion_bp_bonus` | `confirmed`: the token `<0>合体+3000` after the level BP @ `card_brave.html`. No separate fusion cost is printed | `unknown` | `not fetched` | Parse `合体+N` from the level line |
| `fusion_condition_en`, `en_source_id`, `en_status_id` | `absent` / `derived` | `absent` | `not fetched` | Machine translation in #11 |

### ultimate_details

| Column | batspi | official | fandom | Notes for #10 |
| --- | --- | --- | --- | --- |
| `summon_condition_ja` | `confirmed`: `【召喚条件：自分の赤スピリット1体以上】` @ `card_ultimate.html`; `【召喚条件：魂状態/煌臨元を含む自分の赤スピリット/アルティメット1体以上】` @ `card_ultimate.html` | `unknown` | `not fetched` | The whole `【…】` line is the value. A related line `OC条件：カウント5以上` @ `card_ultimate.html` has no column |
| `summon_condition_en`, `en_source_id`, `en_status_id` | `absent` / `derived` | `absent` | `not fetched` | Machine translation in #11 |

## 3. Effects and keywords

Tables: `card_effects`, `effect_kinds`, `card_effect_levels`, `keywords`, `card_effect_keywords`. Effects are text-first ([ADR 0005](../adr/0005-text-first-effects-and-translations.md)): a block is stored as printed. The lines between the level line and `シンボル：` are effects; a header line starts with `Lv`, `【`, `《` or `『`, and a block ends at the next header or at `シンボル：`, `イラスト：` or `フレーバーテキスト：`.

### card_effects, effect_kinds

| Column | batspi | official | fandom | Notes for #10 |
| --- | --- | --- | --- | --- |
| `text_ja` | `confirmed`: `自分のネクサスが「ゼウス」だけのとき、自分のデッキを上から3枚オープンできる。` @ `card_nexus.html` (a block of three lines); `自分はデッキから2枚ドローする。` @ `card_magic.html` | `unknown`: effect text is not in the result list | `not fetched` | Join the lines of the block with line breaks. Keep the reminder text in brackets, for example `（Uトリガー：相手のデッキの1枚目をトラッシュに置く。そのカードのコストが、このアルティメットより低ければヒットとする）` @ `card_ultimate.html` |
| `timing_ja` | `confirmed`: `『自分のアタックステップ開始時』` in `Lv1・Lv2『自分のアタックステップ開始時』` @ `card_spirit.html`; `『このスピリットの転醒/アタック時』` @ `card_flip.html`. `absent` on a bare header: `Lv1・Lv2` followed by `このネクサスのシンボルは赤としても扱う。` @ `card_nexus_soukaishin.html` | `unknown` | `not fetched` | Keep the brackets. A timing can follow a keyword: `【Uトリガー】Lv3・Lv4・Lv5『このアルティメットのアタック時』` @ `card_ultimate.html` |
| `effect_kind_id` | `derived` from the header. Seen: a level header with a timing (`Lv1・Lv2『自分のアタックステップ開始時』` @ `card_spirit.html`); a level header with no timing (`Lv2` @ `card_nexus.html`); `メイン：` @ `card_magic.html`; `フラッシュ：` @ `card_magic_flash.html`, in the card's own block (the planned `flash` kind was seen only in related listings before); `【セット中】『自分のアタックステップ開始時』` @ `card_magic.html`; a keyword line `【ミラージュ：コスト2(1)(このカードは手札からセットできる)】` @ `card_magic.html` | `absent` | `not fetched` | Headers with no planned kind (they would be `other`): `Lv1《転醒：自分のカウント5以下(転醒は同時に使えない)》` @ `card_flip.html`; `Lv1【根幻回帰】` @ `card_flip.html`; `【神技：2】Lv1・Lv2：フラッシュ『お互いのアタックステップ』` @ `card_nexus_soukaishin.html`; `【神域】Lv2『自分のアタックステップ』` @ `card_nexus_soukaishin.html`; `Lv4・Lv5：フラッシュ【真・覚醒】『このアルティメットのアタック時』` @ `card_ultimate.html`; `フラッシュ《契約煌臨：極契約＆C3以上》『自分のターン』` @ `card_ultimate.html`; `【OC中】Lv3・Lv4『このアルティメットのアタック時』` @ `card_ultimate.html`; `OC条件：カウント5以上` @ `card_ultimate.html` |
| `position` | `derived`: printed order | | | |
| `text_en`, `timing_en`, `en_source_id`, `en_status_id` | `absent` / `derived` | `absent` | `not fetched` | Machine translation in #11 |
| `effect_kinds.code`, `effect_kinds.name` | `derived`: seed table | `absent` | `absent` | |

Effect lines that come before the first header and have no level scope: `自分の白以外のスピリットがいる間、このカードをコスト8にする。` @ `card_spirit_xx_bs31.html`; `このカードの軽減シンボルは紫/緑/白/黄/青としても扱う。` @ `card_promo.html`; `このブレイヴは、疲労せず、スピリット状態のとき、アタックとブロックができない。` @ `card_brave.html`. Bullets and markers inside a block: `◆` and `〔重複不可〕` @ `card_nexus_soukaishin.html`, `〔ターンに1回：同名〕` @ `card_ultimate.html`.

Pre-erratum blocks sit under a collapsed label `(エラッタ前) ▼` @ `card_brave.html`. They hold the old wording (for example `【合体時】【激突】『このスピリットの合体アタック時』`, two lines) and may not start with a type line. They are not a printing and must not become a second effect list.

### card_effect_levels

| Column | batspi | official | fandom | Notes for #10 |
| --- | --- | --- | --- | --- |
| `card_level_id` (levels of the header) | `confirmed`: `Lv1・Lv2` @ `card_spirit.html`; `Lv3・Lv4・Lv5` @ `card_ultimate.html`; `Lv1・Lv2・Lv3` @ `card_flip.html`; a single `Lv2` @ `card_nexus.html`. The half-width separator `･` (U+FF65) occurs too, but in the fixtures only in related listings: `Lv1･Lv2【超装甲：赤/紫/緑/白/黄/青】` @ `card_spirit_xx_bs31.html` | `unknown` | `not fetched` | Accept both `・` (U+30FB) and `･` (U+FF65). The batspi catalogue says the live pages mix them; the fixtures' own blocks use `・` only. The level can also come after a keyword or before a colon (`【神技：2】Lv1・Lv2：フラッシュ`). A Magic has no level rows |
| `card_effect_id` | `derived` | | | |

### keywords, card_effect_keywords

| Column | batspi | official | fandom | Notes for #10 |
| --- | --- | --- | --- | --- |
| `keywords.code`, `keywords.name` | `derived`: the bracketed name is read from the block, the code and English name are the loader's. Names seen: `ミラージュ` @ `card_magic.html`; `超装甲` @ `card_spirit_xx_bs31.html`; `激突` and `合体時` @ `card_brave.html`; `神技` and `神域` @ `card_nexus_soukaishin.html`; `Uトリガー` and `真・覚醒` @ `card_ultimate.html`; `根幻回帰` @ `card_flip.html` | `unknown` | `not fetched` | Four bracket shapes occur: `【…】`, `《…》`, `〔…〕` and `『…』`. `『…』` is a timing, `〔…〕` holds a cost, a restriction or a filter, `【…】` and `《…》` a keyword or a label. Which of them are keywords is for #11 |
| `card_effect_keywords.parameter_ja` | `confirmed`: `コスト2(1)` in `【ミラージュ：コスト2(1)(このカードは手札からセットできる)】` @ `card_magic.html`; `赤/紫/緑/白/黄/青` in `【超装甲：赤/紫/緑/白/黄/青】` @ `card_spirit_xx_bs31.html`; `2` in `【神技：2】` @ `card_nexus_soukaishin.html`; `自分のカウント5以下` in `《転醒：自分のカウント5以下(転醒は同時に使えない)》` @ `card_flip.html` | `unknown` | `not fetched` | The text after the colon up to the closing bracket. Brave `【合体時】【激突】` has two keywords on one line |

The batspi effect-category tags outside the `<pre>` (カード効果 and 発揮タイミング) are out of scope for v1.

## 4. Multilingual text

Tables: `translation_sources`, `translation_statuses`, and the `_en` columns and status keys of the other tables. The Japanese text comes from batspi and is never overwritten ([target-schema rules](../data-model/target-schema.md#rules)).

| Column | batspi | official | fandom | Notes for #10 |
| --- | --- | --- | --- | --- |
| `cards.name_en` | `confirmed` on some pages only (see [cards](#cards)) | `absent`: Japanese only | `not fetched` | See the gap list |
| `cards.flavor_text_en`, `card_effects.text_en`, `card_effects.timing_en`, `brave_details.fusion_condition_en`, `ultimate_details.summon_condition_en` | `absent`: the pages are Japanese only | `absent` | `not fetched` | Machine translation (#11) is the only route in v1 |
| `families.name_en` | `absent` | `absent` | `not fetched` | `data/family_mapping.txt` (41 `MT = preferred EN` pairs) and machine translation |
| `products.name_en` | `absent` | `unknown` | `not fetched` | Machine translation (#11) |
| `translation_sources.code`, `translation_sources.name` | `derived`: `official`, `fandom`, `manual`, `machine`; the English name on an old batspi `<h3>` has no listed code in the target schema (it comes from the wiki, not from the card maker) | | | See the gap list |
| `translation_statuses.code` | `derived`: `pending`, `machine`, `reviewed`, `failed`, set by the pipeline | | | Not source data |

## 5. Provenance

Tables: `sources`, `source_pages`, `card_source_pages`, `product_source_pages`. These describe the pipeline rather than the pages, so most columns are `derived` at fetch time.

| Column | batspi | official | fandom | Notes for #10 |
| --- | --- | --- | --- | --- |
| `sources.code`, `sources.name` | `derived`: `batspi`. The manifest records `"source": "batspi"` @ `fixtures.json` | no `sources` row planned in v1 (survey only) | `derived`: `fandom` (dropped for v1) | A seed table |
| `sources.base_url` | `confirmed`: URLs start with `https://batspi.com/index.php?` @ `fixtures.json`; image paths are relative (`/card/BS7/BS72-007.jpg` @ `card_spirit.html`) | `unknown`: `https://www.battlespirits.com/cardlist/` ([official.md §1](official.md#1-urls-and-policy-status-2026-11-14)) | `not fetched`: the manifest has the synthetic `https://battle-spirits.fandom.com/wiki/Card_A` @ `fixtures.json` | Resolve relative image links against `base_url` |
| `source_pages.url` | `confirmed`: the `url` field of every batspi entry in `fixtures.json`, percent-encoded (for example `https://batspi.com/index.php?%E5%85%89%E7%88%AA%E3%81%AE%E6%AD%A6%E8%8A%B8%E8%80%85%E3%83%98%E3%83%AB%E3%83%8F%E3%82%A6%E3%83%B3%E3%83%89` @ `fixtures.json`) | `unknown`: a card detail is `./detail_iframe.php?card_no=<number>`, not fetched | `not fetched` | The page name is the card name, so a renamed page changes the URL |
| `source_pages.fetched_at` | `confirmed` as a date only: `"fetched": "2026-11-14"` @ `fixtures.json` | `unknown` | `not fetched` | The manifest has no time; the real cache records an ISO-8601 UTC timestamp |
| `source_pages.content_sha256`, `source_pages.parser_version` | `derived` by the cache and the parser | | | Not on any page |
| `card_source_pages`, `product_source_pages` | `derived` by the build. A card page lists a link to the official card: `cardlist/index.php?search=true&freewords=BS72-007` @ `card_spirit.html` | `unknown` | `not fetched` | The official link is a cross-reference built from the number, present on the untrimmed pages only |
| Page date (no column) | `confirmed` on untrimmed pages: `Last-modified: 2025-06-24 (火) 23:32:36` @ `card_spirit.html`. `absent` on trimmed pages (the `#lastmodified` element is removed) | `unknown` | `not fetched` | The target schema has no column for the wiki's own modification date |
| `schema_meta` (`schema_version`, `data_version`, `built_at`, `source_snapshot`, `generator`) | `derived` by the build | `absent` | `not fetched` | Build metadata, no source. `source_snapshot` can carry the newest `fetched` date of the cached pages |

## 6. Images

Table: `printing_images` and the lookup `image_sizes`. The policy is **URLs only**: the pipeline does not download card images and the artefact does not contain them ([policy.md §3.6](policy.md#36-images), [ADR 0006](../adr/0006-scraping-and-redistribution-policy.md)). So every column that needs the file (`sha256`, `mime_type`, real `width` and `height`) has no value in v1.

| Column | batspi | official | fandom | Notes for #10 |
| --- | --- | --- | --- | --- |
| `source_url` (large) | `confirmed`: `/card/BS7/BS72-007.jpg` @ `card_spirit.html`; `/card/BS5/BS52-TX01A.jpg` @ `card_flip.html`; `/card/ETC/EX001.jpg` @ `card_promo.html`; `/card/SD/SD19-X01-2.jpg` @ `card_ultimate.html`; `/card/BS0/BS01-001.jpg` @ `card_spirit_bs01.html` | `unknown`: `/images/cardlist/<number>.webp` is documented as a location only ([official.md §3](official.md#3-rendering-and-card-markup)) | `not fetched`: the synthetic fixture has `https://static.wikia.nocookie.net/bs/images/a/a1/BS47-001.png/revision/latest` @ `fandom_card.html` | The `<a>` target of the gallery item is the full image. The directory rule is in [batspi.md §7](batspi.md#7-images) |
| `source_url` (small) | `confirmed`: `/card/BS7/small/BS72-007.jpg` @ `card_spirit.html` | `absent` | `not fetched` | The nested `<img>` of the same item |
| `image_size_id`, `image_sizes.code`, `image_sizes.name` | `derived`: `small` is the `<img>`, `large` the linked file | `absent` | `not fetched` | Only these two sizes were seen |
| `printing_id` (which printing an image shows) | `confirmed` as caption text, number then product then optional note: `シークレット` for the second file `/card/BS7/BS72-007-2.jpg` @ `card_spirit.html`; the count `2枚` @ `card_spirit.html`. Some captions have only the number: `SD19-X01-4.jpg` @ `card_ultimate.html` | `unknown` | `not fetched` | The file suffix `-N` is the order in which prints were added to the wiki, not a rarity or era order. A flip face is a letter before the suffix (`BS52-TX01A-2.jpg` @ `card_flip.html`) |
| `width`, `height` | `confirmed` only as the HTML attributes of the small `<img>`: `width="205" height="300"` @ `card_spirit.html`. These are display attributes, not file properties | `unknown` | `not fetched` | Do not store them as the file size. The artefact stores no file |
| `sha256`, `mime_type` | `absent` by policy (no download) | `absent` | `not fetched` | NULL in v1 |
| `path` | `absent`: no file is stored, so there is no path | `absent` | `not fetched` | The DDL draft has `path` NOT NULL; see the gap list |
| `id` | `derived` | | | Surrogate key |

## 7. Gap list

Fields where no source gives a usable value, or only a derived or machine-translated one. Proposed handling uses four options: **derive** (compute it in the loader), **null** (leave it empty and keep it nullable), **translate in #11**, or **later epic** (needs a decision or a source that is out of scope now). None of them changes the schema; where a column or seed value would be needed, the gap says so and leaves the decision open.

| # | Field | Gap | Proposed handling |
| --- | --- | --- | --- |
| 1 | `cards.name_en` | Printed only on older pages and promos (`card_brave.html`, `card_spirit_bs01.html`, `card_magic_flash.html`, `card_promo.html`); absent on the contract-era, flip, XX, Ultimate and 創界神 fixtures. fandom is dropped | Take it from the `<h3>` where present, otherwise null, then translate in #11 |
| 2 | `flavor_text_en`, `card_effects.text_en` and `timing_en`, `brave_details.fusion_condition_en`, `ultimate_details.summon_condition_en`, `families.name_en`, `products.name_en` | No source has English text | Translate in #11 |
| 3 | `translation_sources` for the English `<h3>` name | The codes `official`, `fandom`, `manual`, `machine` do not name "English name printed on batspi" | Later epic: owner choice in ADR 0007 or #11 (a new lookup row, no schema change) |
| 4 | `printings.illustrator` | `absent` on the first block of `card_magic_flash.html`; a credit may be tied to a product (`イラスト：平坂康也(契約編：環 第3章：覇極来臨)` @ `card_nexus.html`) or not | Null when no line; keep the bracketed product as written |
| 5 | `printings.variant_id` | Variants are free-text notes after the rarity, an open list (`(特別仕様)` @ `card_spirit_xx_bs31.html`, `(金色仕様・2013/11/28頃発送)` @ `card_ultimate.html`) | Derive for the known notes; leave others as the default variant and log them for #10 |
| 6 | `printings.rarity_id` | Absent for distributions with no rarity (`バトルスキーイベント提供記念品` @ `card_magic.html`); on set pages a missing token means common | Null for distributions; derive `C` from the set-page rule |
| 7 | `products.code` | Absent for distributions and the wafer set (`set_wafer.html`); not printed on `set_bs01.html` and `set_bs52.html` | Derive from the number prefix where possible, otherwise null |
| 8 | `products.release_date` | Absent for distributions (`バトスピショップバトル` @ `card_promo.html`); two date formats | Convert to ISO-8601, otherwise null |
| 9 | `products.product_type_id`, `series` | Not fields on any page, only header text | Derive in the loader |
| 10 | `cards.block_icon` | Printed per product and absent on older entries (`(BS01-001)` @ `card_spirit_bs01.html`); the target puts it on the card | Null when absent; whether it belongs to `printings` is for a later epic |
| 11 | `symbols` seed | Glyphs `極` (`シンボル：極` @ `card_ultimate.html`), `全` (`6(全1極3)` @ `card_ultimate.html`), `EX赤` (`シンボル：EX赤` @ `card_magic_flash.html`) and `なし` are not in the planned list `red`..`god` | Later epic: extend the seed in #12; `全` is a wildcard in reductions, not an icon |
| 12 | `card_reductions` for plain `(N)` on a multicolour card | The own-colour rule is untested: no multicolour card with a plain number is in the fixtures | Later epic: check with a wider sample in #10 |
| 13 | `card_symbols.count` | A doubled glyph was not seen (`シンボル：緑青` @ `card_flip.html` is two symbols) | Derive 1 per glyph and re-check in #10 |
| 14 | `card_colors` for several colours | Seen only in related listings (`赤紫緑白黄青` @ `card_flip.html`), never in a card's own block | Derive by splitting characters; confirm in #10 |
| 15 | `cards.cost` for `XX` rares | Printed `0(0)`, effective cost 8 by a text rule (`card_spirit_xx_bs31.html`) | Store the printed cost; the rule stays in the effect text |
| 16 | `card_effects.effect_kind_id` | Headers with no planned kind: `《転醒：…》`, `【根幻回帰】`, `【神技：2】`, `【神域】`, `【Uトリガー】`, `【OC中】`, `OC条件：`, and unheaded lines | Derive as `other` ([effect_kinds](../data-model/target-schema.md#effect_kinds)); the keyword list is for #11 |
| 17 | Fields on the page with no column | `コンセプト：` (`card_brave.html`, `card_ultimate.html`, `card_spirit_bs01.html`); the restriction suffix `(制限カード<1>)` (`card_flip.html`); the overclock token `OC<5+>+6000` (`card_ultimate.html`); the wiki's `Last-modified` stamp | Later epic; do not parse them into other columns |
| 18 | Flip cards | Two faces per number, with `(A)` and `(B)` in the number (`BS52-TX01(A)` @ `card_flip.html`); no face concept in the target | Later epic: owner choice in ADR 0007 or a follow-up to ADR 0004 |
| 19 | Pre-erratum and `体験会でのスペック` blocks | `<pre>` blocks that are not a printed number (`card_brave.html`, `card_magic_flash.html`) | Skip them in #10; keep the current wording only |
| 20 | `printing_images.path`, `sha256`, `mime_type`, `width`, `height` | No download under the URL-only policy; the DDL draft has `path` NOT NULL | Null where nullable; `path` is a conflict between the DDL draft and [ADR 0006](../adr/0006-scraping-and-redistribution-policy.md), for #12 and #13 |
| 21 | `printing_images.printing_id` | The link is a caption and a file suffix; some captions have no product (`SD19-X01-4.jpg` @ `card_ultimate.html`) | Derive from the caption where possible, otherwise leave the image unlinked |
| 22 | Official detail view | Effect text, symbols, illustrators and flavor text were never fetched | Later epic (official is survey only) |
| 23 | Products without a set page | Promo number groups, `ナンバーなし` and the special packs were not sampled ([batspi.md §9](batspi.md#9-not-sampled-and-open-risks)) | Later epic: sample before #10 |

## 8. Input for ADR 0007

Fields where the sources overlap or disagree, so that the source-of-truth ADR ([#56](https://github.com/AleFire99/BS_Database/issues/56)) can decide which one wins. This list states the facts; it does not pick a side.

| Field | Sources and values | Conflict |
| --- | --- | --- |
| `cards.name_en` | batspi `<h3>` `Goradon` @ `card_spirit_bs01.html`; fandom `Name` column (legacy, `not fetched`); machine translation of `name_ja` (legacy `cards.name`) | Three possible origins for one value; the fandom text is CC-BY-SA ([fandom.md §3](fandom.md#3-licence)), the batspi wiki has no stated licence |
| `printings.rarity_id` | batspi per product (`<R>` @ `card_spirit.html`) and per set-page token; official `.number .rarity` (one value per number); fandom `Rarity` (legacy) | Per-product against per-number; the sets can disagree for reprints |
| `cards.cost`, `card_colors`, `card_families`, `card_types` | batspi `<pre>` line 2; official `.costVal`, `.type .attribute`, `.type .system`, `.type .category` | Full overlap; the official site is the only independent check, and the markup was only surveyed |
| `card_reductions` | batspi parentheses (`4(赤2神1)` @ `card_spirit.html`); official `.alleviationVal` icons, counts not checked | Same data in two encodings, one unverified |
| `card_numbers.number` | batspi `BS72-007`, faces `BS52-TX01(A)` @ `card_flip.html`; official `.number .num` with reprint prefixes such as `26R` | The number schemes are not the same set; official `freewords=BS01` also returns `26RBS01-001` |
| `products.release_date` | batspi set page `2025年5月17日発売` @ `set.html`; batspi card page `2025年05月17日` @ `card_spirit.html` | Two places and two formats inside batspi; official unknown |
| `products.code`, `products.name_ja` | batspi set page; official `prodid` product names such as `[CB31]...` | Naming of the same product differs between sites |
| Values that differ between numbers of one name | `<1>Lv1 1000 <3>Lv2 3000` against `<1>Lv1 2000 <3>Lv2 5000` @ `card_spirit_bs01.html`; a third print with another family and effect text @ `card_promo.html` | Same name, different gameplay values: input for [ADR 0004](../adr/0004-card-printing-identity.md) rather than for a source choice |
| `flavor_text_ja` per number | The two numbers of `card_magic_flash.html` differ: the first has `フレーバーテキスト：(バトルスピリッツ メモリアルカードダスセット Hero Ver.)`, the second has none | The target keeps it on the card; the page has it per number |
| Current wording against pre-erratum wording | `(エラッタ前) ▼` @ `card_brave.html` | batspi keeps both; only the current one is a card text |
| `printing_images.source_url` | batspi `/card/BS7/BS72-007.jpg` @ `card_spirit.html`; official `/images/cardlist/<number>.webp`; fandom (synthetic fixture only) | Which host the stored URL points to; the policy allows URLs only |
