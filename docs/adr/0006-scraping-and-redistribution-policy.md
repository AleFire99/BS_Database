# 0006. Scraping and redistribution policy

- Status: Proposed
- Date: 2026-11-14

## Context

The project builds a public database of Japanese Battle Spirits cards and publishes it as a release artefact from a public repository. The source survey of epic [#9](https://github.com/AleFire99/BS_Database/issues/9) found three candidate sources:

- **batspi.com** ([batspi.md](../sources/batspi.md)): a fan wiki and the only reachable, complete source.
  - Its robots.txt allows card and set pages.
  - The footer says the rights to images and text belong to the makers.
  - The site runs PukiWiki, whose GPL licence covers the software, not the content.
  - There is no content licence and no terms of use.
- **The official Bandai site** ([official.md](../sources/official.md)) asks visitors not to reprint or use any of its images or text: 「…全ての画像・文字情報・その他の無断転載・使用はご遠慮ください。」
- **The fandom wiki** ([fandom.md](../sources/fandom.md)): CC-BY-SA text. Its pages and images are behind a Cloudflare challenge, and it is dropped for v1.

The legacy scrapers sent requests with no delay, no cache, no robots.txt check, and either no User-Agent or a fake browser one.

The Gate A decision of #9 (owner, 2026-11-14) was "redistribute card text with attribution, no images". The owner confirmed it at Gate B of [#53](https://github.com/AleFire99/BS_Database/issues/53) after seeing the terms above.

## Decision drivers

- The database is only useful with card text: effects drive play and search.
- Respect the source sites: low load, an honest identity, robots.txt, and no bypass of access controls.
- Card artwork is the most clearly protected material and the least needed for a data project.
- Rights holders need a simple way to object.
- Keep a full rebuild possible without hitting the source again (reproducibility).

## Options considered

1. **Publish card data and text with attribution and a takedown route; no images.**
   - Pros: the release is complete and directly usable, and this is common practice for fan card databases.
   - Cons: card text is copyrighted, and batspi grants no licence. This is a residual risk, mitigated by attribution, a non-commercial fan-project notice and takedown.
2. **Publish structured data only (no effect or flavor text).**
   - Pros: lower copyright exposure.
   - Cons: the main value is lost, and users must scrape the text themselves, which spreads the load to many clients.
3. **Publish nothing scraped; ship only the schema and tools.**
   - Pros: minimal exposure.
   - Cons: there is no shared, validated dataset, and every user crawls batspi.com.

## Decision

Option 1. The release may contain card data and Japanese/English card text compiled from batspi.com, with:

- the attribution text from [policy.md §4](../sources/policy.md#4-redistribution-and-attribution)
- an unofficial fan-project notice
- a takedown route through GitHub issues

Images and raw source HTML are never redistributed. Fixtures are the only exception: a small, documented set used for tests.

Fetching follows [policy.md](../sources/policy.md):

- batspi.com only, after a robots.txt check plus a deny list of wiki action pages.
- Sequential requests at least 3 s apart, with a per-run budget.
- A fixed, honest User-Agent.
- A raw-HTML cache, so pages are fetched once.
- Backoff on 429 and 5xx; a hard stop on 403 or any challenge, with no bypass.

## Consequences

- Positive:
  - The release artefact is self-contained.
  - The source sites see a small, identifiable and rate-limited client.
  - Re-parsing never needs the network.
- Negative:
  - The copyright risk on card text remains and is accepted by the owner.
  - A takedown can force content to be removed from a release.
  - A full first crawl takes hours at the default rate.
- Follow-up work:
  - [#10](https://github.com/AleFire99/BS_Database/issues/10) implements the requirements table in [policy.md §5](../sources/policy.md#5-requirements-for-the-scraper-rewrite-10).
  - [#14](https://github.com/AleFire99/BS_Database/issues/14) adds the attribution to the release notes and the database metadata.
  - [#13](https://github.com/AleFire99/BS_Database/issues/13) (images) must stay local-only under this ADR.

## Links

- Issue: [#53](https://github.com/AleFire99/BS_Database/issues/53), epic [#9](https://github.com/AleFire99/BS_Database/issues/9)
- Policy: [docs/sources/policy.md](../sources/policy.md)
