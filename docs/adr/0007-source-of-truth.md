# 0007. Source of truth per field and conflict resolution

- Status: Proposed
- Date: 2026-11-14

## Context

The source analysis of epic [#9](https://github.com/AleFire99/BS_Database/issues/9) catalogued three sources and mapped every column of the target schema against them in the [coverage matrix](../sources/coverage-matrix.md):

- **batspi.com** is the only reachable and complete source ([batspi.md](../sources/batspi.md)).
- **The official Bandai site** is survey only. Its result list overlaps batspi for number, rarity, name, cost, reduction, colour, type and family. The site asks visitors not to reuse its content ([official.md](../sources/official.md)).
- **The fandom wiki** is dropped for v1. It sits behind a Cloudflare challenge ([fandom.md](../sources/fandom.md)).

Owner decisions so far:

- **Gate A of #9:** batspi JP is authoritative, and other sources only fill gaps.
- **ADR 0006:** fetch only batspi, publish text with attribution, and store image URLs only.

The matrix lists twelve fields where values overlap or disagree ([§8](../sources/coverage-matrix.md#8-input-for-adr-0007)). Most of them are disagreements **inside batspi**:

- A card page holds the own `<pre>` block, a "収録" section, image captions, pre-erratum blocks and a related-cards listing. The set page repeats numbers, rarities and the release date in another format.
- Older pages carry an English name in the `<h3>` heading (`ゴラドン/Goradon`), while modern pages do not.

The pipeline needs one rule per field that the parser (#10), translation (#11) and build (#12) can apply without judgement calls.

## Decision drivers

- One authoritative value per field, chosen by a rule rather than case by case.
- Respect ADR 0006: no requests to fandom or the official site.
- Prefer the most specific block on the page: the card's own text over summaries and listings.
- Never lose data silently. Disagreements are logged, and missing values become NULL rather than guesses.
- Keep the door open for a later cross-check source without a schema change.

## Options considered

1. **batspi only, with a precedence order inside batspi.**
   - Pros: one fetch policy, simple provenance, matches the Gate A and ADR 0006 decisions.
   - Cons: batspi is a single point of failure, and its data is not checked against an independent source.
2. **batspi plus an official-site cross-check of the overlapping fields.**
   - Pros: catches wiki transcription errors.
   - Cons: needs fetches that ADR 0006 excludes, the official site asks visitors not to reuse its content, and the detail view was never surveyed.
3. **Best source per field** (for example official for rarity, fandom for English names).
   - Pros: potentially the richest data.
   - Cons: excluded by ADR 0006 and Gate A; three fetch policies and licence regimes.

## Decision

Option 1. batspi.com is the single source of truth in v1. Inside batspi the following precedence applies, and a lower-precedence value is used only when the higher one is absent.

### Precedence inside batspi

1. The card's **own `<pre>` block**: the first block after each print heading whose first line is a card type.
2. The card page's **"収録" section and image captions**: per-printing data such as product, rarity and alternate art.
3. The **set page**: product name, release date, number list, and the rarity token.
4. **Never used:**
   - the related-cards listing
   - `(エラッタ前)` (pre-erratum) blocks
   - `体験会でのスペック` blocks
   - Q&A blocks
   - wiki edit or action pages

### Field table

| Field group | Authoritative | Fallback | Notes |
| --- | --- | --- | --- |
| `name_ja`, card type, cost, reductions, colours, symbols, families, levels and BP, Brave and Ultimate fields, effects, flavor text | Own `<pre>` (and the page title for `name_ja`) | none, NULL | No official cross-check in v1 |
| `name_en` | The English name in the batspi `<h3>`, with `translation_source = official` (it is the official Bandai English name, transcribed by the wiki) | Machine translation in #11, with `translation_source = machine` | Fandom is not used |
| Other `_en` text (effects, flavor, families) | Machine translation in #11 (`machine`, status `machine`) | NULL with status `failed` | Reviewed text may replace it later (`manual`) |
| Card number | The `cardno` span of the print heading | The image caption | Official prefixes such as `26R` are not adopted |
| Rarity | The "収録" section on the card page, per product | The rarity token on the set page | Rarity is per printing ([ADR 0004](0004-card-printing-identity.md)) |
| Product name and code | The set page title. The code is taken from the card-number prefix | NULL for products without a code (distributions, wafers) | |
| Release date | The set page (`YYYY年M月D日発売`) | The card page "収録" date (`YYYY年MM月DD日`) | Normalised to ISO 8601, otherwise NULL |
| Image URL | The batspi `/card/…` URL from the card page | none | URLs only ([ADR 0006](0006-scraping-and-redistribution-policy.md)) |
| Provenance | The cache sidecar: `url`, `fetched_at`, `status` | | `source_pages` |

### Conflict rule

- When two batspi locations give different values for the same field and printing, the higher-precedence value wins.
- The parser logs a warning with the card number, the field and both values.
- No conflict is resolved silently.
- Some numbers of one card name carry different gameplay values or text (for example two BP lines on `ゴラドン`). That is not a source conflict but an identity question. It is left to [#63](https://github.com/AleFire99/BS_Database/issues/63) (ADR 0004 amendment under #12). Until then the parser keeps the values per number and reports the case.

## Consequences

- Positive:
  - #10, #11 and #12 get a deterministic rule for every column.
  - Provenance has a single source.
  - The fetch policy of ADR 0006 is unchanged.
- Negative:
  - There is no independent check of batspi data in v1.
  - A batspi outage or layout change stops updates. The raw-HTML cache keeps rebuilds possible.
  - English names exist only for the cards whose `<h3>` carries one; the rest are machine translations.
- Follow-up work:
  - #10 implements the precedence and the conflict log.
  - #11 sets the translation sources as above.
  - #63 resolves the per-number values.
  - An official-site cross-check may be proposed later as a new ADR.

## Links

- Issue: [#56](https://github.com/AleFire99/BS_Database/issues/56), epic [#9](https://github.com/AleFire99/BS_Database/issues/9)
- Evidence: [coverage-matrix.md](../sources/coverage-matrix.md), [batspi.md](../sources/batspi.md), [official.md](../sources/official.md), [fandom.md](../sources/fandom.md)
- Related: [ADR 0004](0004-card-printing-identity.md), [ADR 0005](0005-text-first-effects-and-translations.md), [ADR 0006](0006-scraping-and-redistribution-policy.md), [policy.md](../sources/policy.md)
