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
| White | 白 | Missing from the current `colors` table (bug). |
| Yellow | 黄 | |
| Blue | 青 | |
| Multicolor | 多色 | Card with more than one color; in the DB appears as a long symbol string. |
| Symbol | シンボル | Color icon(s) on a card; used today as the only color source. |
| Black / other | | Appears only in code (`black`); existence as a game color is to verify in E4. |

Some Japanese colors in cost reductions (e.g. `神`) are not ordinary colors and are mistranslated (to verify in E4).

## Cost, reduction and cores

| Term | JP | Description |
| --- | --- | --- |
| Cost | コスト | Number of cores paid to play the card. |
| Reduction | 軽減 | Symbols that can offset part of the cost; written in parentheses, e.g. `0(0)`, `2(1)`, `3(2 紫, 1 神)`. Scraped to JSON but not stored in the DB. |
| Core | コア | Resource unit; cores are placed on Spirits to raise their level. |
| Core requirement | | Per level: number of cores needed, with the resulting BP. Stored as `(level, cores, battlePoints)`. |
| Level | レベル (Lv) | Stage of a Spirit or Nexus, unlocked by cores on it. |
| BP | BP (ビーピー) | Battle Points, the combat strength of a Spirit at a given level. |

On batspi.com the scraped line format is `<cores>LvN BP`, e.g. `<3>Lv2 3000`.

## Families (系統)

A family is a creature-type tag on a card (e.g. "Reptile Beast", 爬獣). A card can have several. The scraper translates Japanese families with a machine translator, producing inconsistent names relative to the English wiki and official English terms. `data/family_mapping.txt` patches known mismatches manually (e.g. `Earth Dragon = Terra Dragon`, `Kidra = Machine Dragon`, `Rebirth = Reptile Beast`). Some are compound or prefixed (`Different X`, `New X`, `Next Generation of X`) and are split heuristically. The JP to EN family mapping must be made explicit and reviewed in E6 ([#11](https://github.com/AleFire99/BS_Database/issues/11)).

## Card IDs

Format `BSNN-NNN`: set code plus collector number, e.g. `BS05-048` is card 48 of set BS05. Other prefixes (promos, starter decks, collaboration sets) exist on the source sites (to verify in E4); the scraper regex only matches `BS\d{2}-\d{3}`.

## Sets and products

| Term | JP | Description |
| --- | --- | --- |
| Set / booster | ブースター | Main numbered expansions, coded `BSNN`. |
| Starter deck | スタートデッキ | Preconstructed deck products (to verify in E4 how they are coded). |
| Promo | プロモーション | Promotional cards distributed outside boosters. |
| Reprint | 再録 | Card printed again in another set, possibly with a new ID. |
| Chapter | 章 | batspi.com groups sets by era and chapter (e.g. `契約編：環 第1章`, the "Contract Saga"). |

Reprints and promos are only partially captured by the repository (`Notes` commit history mentions scraped promos and reprints) and are not modelled in the DB.

## Rarity

Rarity (レアリティ) marks print scarcity (for example C, U, R, M-class labels). Not captured today; the exact rarity scale and per-print variation are to verify in E4.

## Sources

| Source | Language | Used for |
| --- | --- | --- |
| battle-spirits.fandom.com | EN | Set lists, images |
| batspi.com | JP | Card pages (name, cost, symbol, family, levels), machine translated |
