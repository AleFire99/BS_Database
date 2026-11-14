# Battle Spirits glossary

Neutral domain glossary for the Japanese Battle Spirits trading card game (バトルスピリッツ). Statements marked "(to verify in E4)" are not yet confirmed against an authoritative source and must be checked during source analysis ([#9](https://github.com/AleFire99/BS_Database/issues/9)).

## Card types

| Term | JP | Description |
| --- | --- | --- |
| Spirit | スピリット | Creature-like card placed on the field; has cost, BP and levels. |
| Nexus | ネクサス | Persistent non-creature card placed on the field; has levels but typically no BP (to verify in E4). |
| Magic | マジック | One-shot effect card, played and then discarded. |
| Brave | ブレイヴ | Card that is combined with a Spirit to enhance it. |
| Ultimate | アルティメット | Powerful Spirit-like card with special summon conditions (to verify in E4). |

The current database holds exactly these five types (from `Notes.md`).

## Colors and symbols

| Term | JP | Notes |
| --- | --- | --- |
| Red | 赤 | |
| Purple | 紫 | |
| Green | 緑 | |
| White | 白 | Missing from the legacy `colors` table (bug); included in the target `colors` lookup. |
| Yellow | 黄 | |
| Blue | 青 | |
| Multicolor | 多色 | Card with more than one color; the legacy DB shows it as a long symbol string, the target model as several `card_colors` rows. |
| Symbol | シンボル | Icon printed on a card or used to reduce a cost. Distinct from a colour: the god symbol is a symbol without a colour. Modelled in `symbols`, `card_symbols` and `card_reductions`; see [Symbol vs colour](#symbol-vs-colour). The old pipeline used it as the only colour source. |
| God symbol | 神 | Symbol that belongs to no colour; appears in cost reductions such as `4(赤2神1)`. Code `god`, `symbols.color_id` is NULL. See [target-schema.md](../data-model/target-schema.md#symbols). |
| Black / other | | Appears only in code (`black`); existence as a game color is to verify in E4. |

### Symbol vs colour

A **colour** (赤, 紫, 緑, 白, 黄, 青) says which colours a card belongs to; it comes from segment 2 of the cost line (`4(赤2神1)/赤/眷属・武迅`) and is stored in `card_colors`. A **symbol** is an icon: the ones printed on the card (`シンボル：赤`, `card_symbols`) and the ones that reduce its cost (the parentheses of the cost line, `card_reductions`). Symbols include the six colours plus the god symbol 神, which is why reductions are keyed by symbol and not by colour. See [Gameplay attributes](../data-model/target-schema.md#gameplay-attributes). Multi-symbol `シンボル：` lines and plain `(N)` reductions on multicolour cards are pending #9.

## Cost, reduction and cores

| Term | JP | Description |
| --- | --- | --- |
| Cost | コスト | Number of cores paid to play the card. |
| Reduction | 軽減 | Symbols that can offset part of the cost; written in parentheses, e.g. `0(0)`, `2(1)`, `5(赤2白2)`, `4(赤2神1)`: a plain number, or colour glyphs with counts joined without separator (`全` stands for any colour); see [coverage-matrix.md](../sources/coverage-matrix.md#card_reductions). Scraped to JSON by the legacy pipeline (colour only, the god symbol is lost) and not stored in the legacy DB; the target model stores it in `card_reductions`, keyed by symbol. |
| Core | コア | Resource unit; cores are placed on Spirits to raise their level. |
| Core requirement | | Per level: number of cores needed, with the resulting BP. Stored in the legacy DB as `(level, cores, battlePoints)`; the target table is `card_levels` (`level`, `cores`, `battle_points`). |
| Level | レベル (Lv) | Stage of a Spirit or Nexus, unlocked by cores on it. |
| BP | BP (ビーピー) | Battle Points, the combat strength of a Spirit at a given level. |

On batspi.com the scraped line format is `<cores>LvN BP`, e.g. `<3>Lv2 3000`.

## Brave and Ultimate terms

| Term | JP | Description |
| --- | --- | --- |
| Fusion (Brave) | 合体 | Combining a Brave with a Spirit. Modelled as a 1:1 text side table, [brave_details](../data-model/target-schema.md#brave_details) (fusion condition and optional BP bonus). The exact printed fields are pending #9 (to verify in E4). |
| Summon condition (Ultimate) | 召喚条件 | Condition to summon an Ultimate. Modelled as text in [ultimate_details](../data-model/target-schema.md#ultimate_details). Pending #9 (to verify in E4). |

## Families (系統)

A family is a creature-type tag on a card (e.g. "Reptile Beast", 爬獣). A card can have several. The scraper translates Japanese families with a machine translator, producing inconsistent names relative to the English wiki and official English terms. `data/family_mapping.txt` patches known mismatches manually (e.g. `Earth Dragon = Terra Dragon`, `Kidra = Machine Dragon`, `Rebirth = Reptile Beast`). Some are compound or prefixed (`Different X`, `New X`, `Next Generation of X`) and are split heuristically. The JP to EN family mapping must be made explicit and reviewed in E6 ([#11](https://github.com/AleFire99/BS_Database/issues/11)).

## Card IDs

Format `BSNN-NNN`: set code plus collector number, e.g. `BS05-048` is card 48 of set BS05. Other prefixes (promos, starter decks, collaboration sets) exist on the source sites (to verify in E4); the scraper regex only matches `BS\d{2}-\d{3}`.

## Sets and products

| Term | JP | Description |
| --- | --- | --- |
| Set / booster | ブースター | Main numbered expansions, coded `BSNN`. |
| Starter deck | スタートデッキ | Preconstructed deck products (to verify in E4 how they are coded). |
| Promo | プロモーション | Promotional cards distributed outside boosters. Modelled as a printing in a product of the promo distribution type, with the number reused or a P-number (format pending #9); see [ADR 0004](../adr/0004-card-printing-identity.md). |
| Reprint | 再録 | Card printed again in another product. It can keep its number and change finish or art (e.g. BS72-069 in BS72 and BS74). Modelled as a new printing of the same card number; a new number is a new card number of the same card. See [ADR 0004](../adr/0004-card-printing-identity.md). |
| Product | 収録/掲載/配布 | Anything a card is released in: booster, starter deck, promo distribution, magazine, collaboration. A booster set is a product with a code such as `BS72`; distributions may have no code. Has a release date. See [ADR 0004](../adr/0004-card-printing-identity.md). |
| Chapter | 章 | batspi.com groups sets by era and chapter (e.g. `契約編：環 第1章`, the "Contract Saga"). |

Reprints and promos are not modelled in the legacy DB; the target model is in [ADR 0004](../adr/0004-card-printing-identity.md).

## Rarity

Rarity (レアリティ) marks print scarcity (for example C, U, R, M-class labels; batspi writes `<C>`, `<R>`). It belongs to a printing, not to a card, and is a lookup table in the target model ([ADR 0004](../adr/0004-card-printing-identity.md)). Not captured in the legacy DB; the exact rarity scale is pending #9.

## Identity terms

| Term | JP | Description |
| --- | --- | --- |
| Card | | Gameplay identity: name, text and stats. One card can have several card numbers (rule pending #9). See [ADR 0004](../adr/0004-card-printing-identity.md). |
| Card number | カード番号 | Printed number such as `BS72-069`. Belongs to exactly one card and can appear on several printings. |
| Printing | | One physical printing: a card number in one product and variant, with its own rarity, illustrator and image. |
| Variant | | Finish or art version of a printing within a product: normal, secret (`SECRETあり`), full art (`フルアート版`), promo art. The full list is pending #9. |
| Block icon | ブロックアイコン | Era or legality icon on a card (e.g. `12`, `A`); stored on the card by default, per card or per number pending #9. |

## Effects and text

Modelled text-first in [target-schema.md](../data-model/target-schema.md#effects-and-keywords) and [ADR 0005](../adr/0005-text-first-effects-and-translations.md): effect text is stored as printed, not parsed.

| Term | JP | Description |
| --- | --- | --- |
| Effect | 効果 | One effect block of a card's `<pre>`: an optional level scope (`Lv1・Lv2`), an optional timing and the text. Stored in `card_effects`. Block segmentation across eras and in Brave and Ultimate cards is pending #9. |
| Timing | 発揮タイミング | When an effect is used, written in `『…』` after the level scope, e.g. `『自分のアタックステップ開始時』`. Kept as text in `card_effects.timing_ja`; a block can have none (a Nexus `Lv2` constant effect). The batspi 発揮タイミング tags outside the `<pre>` are not modelled. |
| Keyword | | Keyword ability written as `【…】`, e.g. `【ミラージュ：…】` or `【セット中】`. Modelled as the lookup `keywords` plus an optional parameter text. Only Mirage is seen in the fixtures; the full list is pending #9. |
| Mirage | ミラージュ | Keyword seen on the Magic fixture: `【ミラージュ：コスト2(1)(このカードは手札からセットできる)】`. The page Q&A says a card marked Mirage is placed face up in the Burst area and keeps its effects while there. The alternate cost `コスト2(1)` is stored as text, not as numbers. Rules wording to verify in #9. |
| Flavor text | フレーバーテキスト | Story text under `フレーバーテキスト：` in the `<pre>`; no game effect. Seen on the Spirit and Nexus fixtures, absent on the Magic one. Stored on the card (`flavor_text_ja`, `flavor_text_en`); whether it varies per printing is pending #9. |
| Main / Flash | メイン / フラッシュ | Labels of Magic effects (`メイン：`, `フラッシュ：`). `メイン：` is seen in the Magic fixture; `フラッシュ：` only in related-card blocks, so its layout is pending #9. |

## Translation and provenance

| Term | JP | Description |
| --- | --- | --- |
| Provenance | | Which source page a card or product was built from, with fetch time, content hash and parser version. Stored in `sources`, `source_pages` and the `card_source_pages` and `product_source_pages` junctions; see [target-schema.md](../data-model/target-schema.md#provenance). |
| Translation status | | State of an English text: `pending`, `machine`, `reviewed` or `failed`, stored per row with a translation source (`official`, `fandom`, `manual`, `machine`). A failed translation is NULL text with status `failed`, never an error string. See [target-schema.md](../data-model/target-schema.md#multilingual-text). |

## Database versions

| Term | Description |
| --- | --- |
| Schema version | SemVer of the table layout, stored in `schema_meta` and encoded in `PRAGMA user_version` (see [ADR 0003](../adr/0003-naming-and-schema-versioning.md)). |
| Data version | Release tag of a built database (the git tag); independent of the schema version. |

## Sources

| Source | Language | Used for |
| --- | --- | --- |
| battle-spirits.fandom.com | EN | Set lists, images |
| batspi.com | JP | Card pages (name, cost, symbol, family, levels), machine translated |
