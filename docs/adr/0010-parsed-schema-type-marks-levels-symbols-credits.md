# 0010. Parsed schema additions for type marks, levels, symbols and credits

- Status: Accepted
- Date: 2026-11-16

## Context

The full batspi scrape ([#96](https://github.com/AleFire99/BS_Database/issues/96)) left 638 pages that the card parser rejected ([#108](https://github.com/AleFire99/BS_Database/issues/108)). Most of them are fixed by relaxing a regex. About 440 pages, counted by the shapes below, print facts that the parsed schema 2.0.0 has no field for. Dropping them silently loses data, and rejecting the page loses the whole card.

| Printed on the page | Pages (about) | Where it appears |
| --- | ---: | --- |
| `契約スピリット`, `契約ネクサス`, `契約アルティメット`, `トークンネクサス` | 125 | type line |
| `(禁止カード)`, `(光)`, `(闇)` after the type | 217 | type line |
| `<C2>Lv2` instead of a core count | 40 | level line |
| `<5>Lv2/真界放 10000`, `<4>真界放` | 25 | level line |
| `<1>Lv1 X0000` (a battle point printed as text) | 2 | level line |
| `シンボル：EX赤` | 23 | symbol line |
| `シンボル：神(青)神(白)` | 45 | symbol line |
| `プロデュース：`, `ペイント：`, `書：`, `写真：`, `コラボレート：` | 44 | credit lines |

Facts that shape the choice:

- [ADR 0003](0003-naming-and-schema-versioning.md) versions the parsed schema; a change of fields is a minor bump (2.0.0 to 2.1.0). The parsed tree is a derived artefact: every document can be rebuilt from the raw HTML cache with no request.
- [ADR 0007](0007-source-of-truth.md) makes batspi the authority and keeps Japanese values as printed. Mapping to codes is the job of normalize ([ADR 0008](0008-normalization-and-translation.md)).
- The page does not say what `光`, `闇`, `<C2>` or `EX` mean. Inventing a meaning would put a guess in the data.

## Decision drivers

- Keep every printed fact; never guess what the source does not state.
- Keep the five base card types, which the rest of the pipeline relies on.
- Additive change only: older readers and the existing goldens keep working apart from the version string.
- The owner, not the parser, decides what a mark means.

## Options considered

1. **Reject or skip the new shapes.** No schema change. Cons: those cards stay missing, which defeats the purpose of the scrape.
2. **Fold the new facts into existing fields** (for example `契約スピリット` as a sixth `card_type`, `EX赤` as an ordinary symbol). Cons: it changes the closed set of card types that the glossary and the loader assume, and it hides a distinction the page makes.
3. **Add narrow, optional fields (recommended)** and keep the values as printed Japanese literals. Pros: nothing lost, nothing interpreted, additive. Cons: a minor schema bump and a rebuild of the parsed tree.

For the rebuild of option 3:

- **A (chosen): bump the version and add a cache-only `--reparse`** that re-parses every page from the raw cache with 0 requests. The tree is uniform.
- **B: accept both versions when reading.** Cons: a mixed tree with two shapes for the same field.

## Decision

Use **option 3 with rebuild A**. The parsed schema goes from **2.0.0 to 2.1.0**. Every new field has a default (`None`, or an empty tuple), so the change is additive in the model. The reader stays strict: `parsed_store` accepts only 2.1.0, so a 2.0.0 tree is rebuilt from the cache with `bsdb scrape --offline --reparse` (0 requests). The normalized schema follows, from 1.1.0 to 1.2.0, and the review reader likewise accepts only the new version. A type mark is read as any parenthesised literal after the type; only `禁止カード`, `光` and `闇` occur today, and an unknown mark is stored as is instead of failing the page.

### New fields

| Model | Field | Type | Meaning, as printed |
| --- | --- | --- | --- |
| `Gameplay` | `card_class` | `str \| None` | `契約` or `トークン`, the prefix of the type line (`契約スピリット`). `card_type` stays one of the five base types. |
| `Gameplay` | `type_mark` | `str \| None` | The bracket after the type: `禁止カード`, `光` or `闇`. `(制限カード<n>)` stays in `deck_limit`. |
| `Level` | `count_condition` | `str \| None` | The token that replaces the core count, for example `C2` in `<C2>Lv2`. `cores` is `None` for such a level. |
| `Level` | `note` | `str \| None` | A remark attached to the level: `真界放` in `<5>Lv2/真界放 10000`, or the text of a battle point that is not a number (`X0000`, then `battle_points` is `None`). |
| `SymbolCount` | `variant` | `str \| None` | `EX` in `EX赤`. |
| `SymbolCount` | `color` | `str \| None` | The colour of a god symbol: `青` in `神(青)`. |
| `CardText` | `other_credits` | `tuple[RoleCredit, ...]` | Credits other than the illustrator and the concept: `プロデュース`, `ペイント`, `書`, `写真`, `コラボレート`. |
| `RoleCredit` (new) | `role`, `name`, `note` | `str`, `str`, `str \| None` | The printed label, the name, and the parenthesised note. |

Other rules:

- All values are the Japanese literals of the page. Codes and English names are assigned in normalize and the glossary, never in the parser.
- An empty `イラスト：` (no name) is tolerated and gives no credit, with a warning, instead of failing the page.
- Normalize carries the new fields through as literals ([#108](https://github.com/AleFire99/BS_Database/issues/108)). Glossary rows for the new classes and marks are a follow-up, as is the SQLite loader ([#12](https://github.com/AleFire99/BS_Database/issues/12)).

### Assumptions (not stated by the source)

These stay open until the owner confirms them; the data does not depend on them because the literals are kept.

- `光` and `闇` after the type are a rule mark of the card (a special rule), not a colour.
- `<C2>` in a level line is a count condition of the contract line, not a number of cores.
- `EX` before a symbol marks an extra symbol of that colour.
- `神(青)` is a god symbol of the colour blue.

### Run

`bsdb scrape --reparse` resets every parsed card row to `fetched`, so the run parses it again from the cache. Combined with `--offline` it makes no request at all.

## Consequences

- Positive:
  - Those cards become readable, with every printed fact kept.
  - Additive in the model: every new field has a default. The parsed and normalized goldens gain the new fields and the new versions (parsed 2.1.0, normalized 1.2.0).
  - The rebuild needs no network and gives a uniform tree.
- Negative and follow-up work:
  - Readers are strict on the version: an old parsed (2.0.0) or normalized (1.1.0) tree must be rebuilt (`bsdb scrape --offline --reparse`, then `bsdb normalize`).
  - New terms (contract families, the marks, the credit roles) make `bsdb normalize --strict` fail until they are curated in the glossary. That curation is a follow-up.
  - The meaning of the marks stays an open question for the owner.

## Links

- Issue: [#108](https://github.com/AleFire99/BS_Database/issues/108)
- Builds on [0003](0003-naming-and-schema-versioning.md), [0007](0007-source-of-truth.md) and [0008](0008-normalization-and-translation.md).
