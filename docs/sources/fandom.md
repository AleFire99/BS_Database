# Source dossier: Battle Spirits fandom wiki

The English-language community wiki at `battle-spirits.fandom.com`. **Verdict: dropped for v1** (Gate A decision of epic [#9](https://github.com/AleFire99/BS_Database/issues/9)). This dossier records the access evidence so the decision can be revisited. Survey task: [#52](https://github.com/AleFire99/BS_Database/issues/52). All facts below were observed on **2026-11-14** with a generic user agent (`Mozilla/5.0 (compatible; bs-database-research)`), spaced at least 4 s apart, and **without any Cloudflare bypass**. Access can change, so re-check before relying on any row.

## 1. Access evidence (2026-11-14)

| URL | Result | Note |
| --- | --- | --- |
| Wiki pages (set lists, card pages) | HTTP 403, Cloudflare challenge | Blocks plain HTTP clients |
| `robots.txt` | HTTP 403, Cloudflare challenge | No crawl policy could be read |
| `static.wikia.nocookie.net` (image CDN) | HTTP 403, Cloudflare challenge | Images are blocked too |
| `api.php?action=query&meta=siteinfo&format=json` | HTTP 200, JSON | MediaWiki 1.43.10 |
| `api.php?action=query&meta=siteinfo&siprop=rightsinfo&format=json` | HTTP 200, JSON | Licence, see section 3 |

The `api.php` answer is recorded as an **observation only**. It was not explored beyond `siteinfo`, and it is **not pursued** for v1.

## 2. What the wiki offers

Per the legacy scrapers (not verified against the live wiki, see section 4):

- Set pages with a table of `Number`, `Name` and `Rarity` (English names).
- Card pages with a card image.

batspi.com already provides the card numbers, and Japanese is the authoritative language (batspi JP is authoritative). The wiki's only potential extras are English names and images. Images are never redistributed by this project (owner decision), so even a working image source adds nothing to the artefact.

## 3. Licence

`api.php?action=query&meta=siteinfo&siprop=rightsinfo` returned on 2026-11-14:

```json
{"batchcomplete":"","query":{"rightsinfo":{"url":"https://www.fandom.com/licensing","text":"CC-BY-SA"}}}
```

Wiki **text** is therefore CC-BY-SA (attribution and share-alike would apply to any derived text). This says nothing about card images, which remain Bandai artwork.

## 4. Repository state

- The fandom fixtures in [tests/fixtures/html/](../../tests/fixtures/html/fixtures.json) are **synthetic**: the real site was blocked on 2026-11-14. The `Rarity` column and the card page layout are not verified (see [field-inventory.md](../data-model/field-inventory.md)).
- [fandom_sets.py](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/fandom_sets.py), [fandom_images.py](https://github.com/AleFire99/BS_Database/blob/f90747b/src/bs_database/scrapers/fandom_images.py) are **legacy** code, removed with the fandom settings in [#66](https://github.com/AleFire99/BS_Database/issues/66) (links point at commit `f90747b`).

## 5. Verdict

- **Dropped for v1.** No scraping, no bypass of the Cloudflare challenge, API not pursued.
- Revisit only if a real need for English names appears and access is available through a permitted route; the CC-BY-SA text licence would then have to be honoured.
