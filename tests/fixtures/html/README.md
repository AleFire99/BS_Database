# HTML fixtures

Saved pages that stand in for the network in tests. The manifest [fixtures.json](fixtures.json) records, per file, the source `url`, the `fetched` date, the `source` (`batspi` or `synthetic`), the `kind` (`card`, `set`, `list`, `index`, `image`), the `card_type` (card pages) and whether the file is `trimmed`. [test_fixtures_manifest.py](../../test_fixtures_manifest.py) checks the manifest, the budget and the card pages.

## Files

| File | Page | Notes |
| --- | --- | --- |
| `index.html`, `set.html`, `card_spirit.html`, `card_nexus.html`, `card_magic.html` | Original fixtures (BS72 era) | Untrimmed; kept as the first batspi test pages |
| `card_brave.html` | `砲凰竜フェニック・キャノン` | Brave; reprint `BS38-RV022` |
| `card_ultimate.html` | `アルティメット・ジークフリード` | Ultimate; starter deck `SD19-X01` |
| `card_nexus_soukaishin.html` | `創界神アポローン` | 創界神 Nexus |
| `card_flip.html` | `赤の世界／赤き神龍皇` | Flip (転醒) card, two faces |
| `card_spirit_bs01.html` | `ゴラドン` | Oldest era |
| `card_spirit_xx_bs31.html` | `六絶神 鉄壁のクロム・リゼルファー` | XX rare |
| `card_promo.html` | `焔竜翼人マ・ドー` | Promo numbers |
| `card_magic_flash.html` | `ダブルドロー` | Magic with `メイン：` and `フラッシュ：` |
| `set_bs01.html` | `第一弾` | Oldest set page |
| `set_bs52.html` | `転醒編 第1章：輪廻転生` | Awakening era |
| `set_sd54.html` | Collab starter `ガンダム ～OPERATION UC～` | Copy counts |
| `set_wafer.html` | Wafer set `～蛇皇襲来～` | Reprint-only set |
| `set_cb34.html` | Collab booster `仮面ライダー ～善悪の選択～` | `CB##` prefix |
| `list_promo.html` | `プロモーションカード` | Listing page; **partial** (leading sections only, over 300 KB after trimming) |

## Budget

At most 300 KB per file and 2.5 MB for the folder. The test fails when either is exceeded.

## Trimming

New batspi pages are trimmed by the fetch tool: `script`, `style`, `noscript`, `iframe`, `link`, `meta` and comments are removed, and so are the elements `#menubar`, `#header`, `#footer`, `#navigator`, `#navigator2`, `#toolbar` and `#lastmodified`. Everything else is kept unchanged, so the content DOM is the one a parser sees on the live site. Images are never downloaded.

## Licence and attribution

The card text and names belong to the card maker (Bandai); batspi.com is a fan wiki and states no reuse licence. The pages are included as test data only, under the takedown route of [ADR 0006](../../../docs/adr/0006-scraping-and-redistribution-policy.md) and [policy.md](../../../docs/sources/policy.md#4-redistribution-and-attribution). They are small, trimmed and not part of the release artefact. On a request from a rights holder they are removed.

## Refresh

Fetching follows the [scraping policy](../../../docs/sources/policy.md): robots.txt check, deny list, policy User-Agent, at least 3 s between requests, stop on 403 or a challenge page. It is stricter than the policy: it makes no retries (a 429 or 5xx page is skipped), and it stops if robots.txt is not 200. The manifest is saved even when a run stops early.

```bash
uv run python tests/tools/fixture_fetch.py --raw-dir <dir outside the repo> \
    "card_brave.html|砲凰竜フェニック・キャノン|card|ブレイヴ"
```

Each argument is `FILE|PAGE NAME|KIND|CARD TYPE`. Add `--partial` to allow a partial page, or `--offline` to trim again from the raw pages in `--raw-dir` with no request. The tool is run by hand. Its robots.txt and deny-list logic is in `bs_database.ingest.policy`, covered by `tests/test_ingest_policy.py`.
