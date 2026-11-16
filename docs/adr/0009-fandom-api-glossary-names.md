# 0009. Fandom api as a glossary name source

- Status: Accepted
- Date: 2026-11-16

## Context

The glossary review ([#96](https://github.com/AleFire99/BS_Database/issues/96)) needs an English name and a code for every family, keyword and rarity. Today the proposals come from the legacy v0.1.0 snapshot and from machine translation, and both are weak for short proper names.

The Battle Spirits fandom wiki has one page per family and keyword, written by fans, usually opening with `'''English name''' (JP; romaji)`. The Gate A verdict of epic [#9](https://github.com/AleFire99/BS_Database/issues/9) dropped fandom for v1 because the wiki pages and `robots.txt` are behind a Cloudflare challenge ([fandom dossier](../sources/fandom.md)). The same dossier recorded that `api.php` answers with plain JSON, and a probe on 2026-11-16 confirmed it: `api.php` returned 200, `Category:Family` lists 357 pages, `Category:Keywords` 305, and the `Card Rarity` page exists.

Facts that shape the choice:

- [ADR 0006](0006-scraping-and-redistribution-policy.md) requires reading `robots.txt` before fetching. For fandom that file is behind the challenge, so it cannot be read.
- The wiki text is CC-BY-SA, see section 3 of the dossier.
- [ADR 0007](0007-source-of-truth.md) makes batspi the authority for Japanese values.

## Decision drivers

- Better English names and romaji codes for the families and keywords the owner has to review.
- No challenge bypass, ever, and no load on the wiki beyond a few dozen requests.
- Respect the CC-BY-SA licence.
- Keep the owner as the only one who accepts a name.

## Options considered

1. **Keep machine translation and the legacy snapshot only.** No new source. Cons: short names such as `機獣` translate poorly, and codes have no romaji to derive from.
2. **Scrape the fandom HTML pages.** Cons: blocked by Cloudflare, and a bypass is out of the question.
3. **Read names through `api.php` only.** A fixed, narrow use of the one endpoint that answers. Pros: JSON, few requests, no bypass. Cons: a robots exception is needed and the licence must be honoured.

## Decision

Use **option 3**, with these limits.

### What is read

- Only `https://battle-spirits.fandom.com/api.php` with `action=query`.
- `list=categorymembers` for `Category:Family` and `Category:Keywords`, and `prop=revisions` (wikitext) for those pages and for the `Card Rarity` page.
- About 15 requests in total, sequential, at the configured `BSDB_REQUEST_DELAY`; raw responses are cached under the cache directory (git-ignored) and never redistributed.
- Nothing else: no wiki page, no card page, no image.

### Robots exception

`robots.txt` is behind the challenge and cannot be read, so the check of ADR 0006 section 3.1 is replaced by a **fixed allow-list**: the single endpoint above. The client rejects any other URL. A 403 or a challenge response **stops the run** (exit code 3), as for batspi; there is no retry, no header trick and no bypass.

### Licence

- Only short names (English name, Japanese name, romaji) are taken, never page text.
- A glossary row that came from fandom carries `notes` = `fandom: <page title>`. `docs/sources/fandom.md` and the project docs carry an attribution line (CC-BY-SA, Battle Spirits fandom wiki contributors).

### Authority

- batspi Japanese stays authoritative. Fandom Japanese strings are only used to match batspi's (NFKC key, whitespace ignored) and to propose an English name.
- Fandom feeds only the glossary **review** (`bsdb glossary fandom`, then `bsdb glossary review --fandom`). It never feeds `bsdb normalize`, which reads the curated glossary only.
- **No fandom-derived row is committed to `data/glossary/` before the owner accepts this ADR.**

## Consequences

- Positive:
  - Better proposals, and romaji-based codes consistent with the existing keyword codes.
  - Offline reruns after the first fetch (cache), and no network in CI.
- Negative and follow-up work:
  - Partly reverses the Gate A verdict of #9 for names only; the dossier is updated.
  - Hand-written wiki pages vary, so some pages will not parse; they are listed, not guessed.
  - If the API starts returning a challenge, the fetch stops and the review falls back to the other sources.

## Links

- Issue: [#104](https://github.com/AleFire99/BS_Database/issues/104)
- Builds on [0006](0006-scraping-and-redistribution-policy.md) and [0007](0007-source-of-truth.md); see [fandom dossier](../sources/fandom.md).
