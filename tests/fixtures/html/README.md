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
| `card_nexus_cost_slash.html` | `巨獣の森` | #108: cost line `4(2)/白/` (trailing slash) |
| `card_spirit_header_space.html` | `コジロンド・ゴレム` | #108: header `Lv1・Lv2・Lv3 【粉砕】『…』` (blank after the levels) |
| `card_spirit_header_colon.html` | `紅玉の巨龍ボルガンド` | #108: header `Lv1・Lv2・Lv3:フラッシュ【覚醒】` (ascii colon) |
| `card_spirit_header_timing.html` | `仮面ライダーマリカ ピーチエナジーアームズ` | #108: header `『…』【起動：フラッシュ】〔ターン1回〕` (timing first) |
| `card_magic_printing_note_number.html` | `クリスタルクラック` | #108: 収録 rows without a bold label, the number is in the note `<C> (BS18-076)` |
| `card_spirit_printing_unnumbered.html` | `魔刃将ヘル・ブレド` | #108: 収録 rows with no number on a two-number page (attached to every number, with a warning) |
| `card_spirit_shared_block.html` | `巨人皇子アレクサンダー4世` | #108: one `<pre>` and an h3 without a number, two own numbers (`EX023`, `P027`) |
| `card_magic_image_placeholder.html` | `禁忌のエクストリーム` | #108: gallery `<li>` linking `NOTFOUND.jpg` with no caption |
| `card_spirit_listed_as_set.html` | `拳闘巨人ジャスティン` | #108: a single card page that the index lists as a set |
| `list_year_event_gifts.html` | `バトルスキーイベント提供記念品` | #108: list split by year (h3 title, h4 years, no h2); **partial** (first sections only) |
| `card_spirit_mark_light_limit.html` | `サンピラー・ドラゴン` | #108: type line `スピリット(光)(制限カード<1>)` |
| `card_nexus_token.html` | `菌床` | #108: type line `トークンネクサス` |
| `card_spirit_level_blank.html` | `六絶神 欲望のデス・ガル・ヴァドス` | #108: level line `<3> Lv2` with a blank after `<n>` |
| `card_magic_symbol_ex.html` | `ガードベント` | #108: symbol line `シンボル：EX白` |
| `card_spirit_credit_ascii_colon.html` | `グレムリー` | #108: credit label with an ASCII colon, `イラスト:SUNRIZE D.I.D.(…)` |
| `card_spirit_credit_producer.html` | `新世代最可愛将孫市 黒曜の徒` | #108: credit `プロデュース：杉田智和` |
| `card_brave_credit_paint.html` | `碇シンジ -シンクロ率∞-` | #108: credit `ペイント：…` |
| `card_spirit_credit_collab.html` | `アイドル天使 天海春香` | #108: credit `コラボレート：アイドルマスター` |
| `card_spirit_credit_empty_illustrator.html` | `ビクトリー・ブレイドラ` | #108: empty `イラスト：` (warning, no credit) |
| `card_brave_credit_concept_ascii.html` | `裁きの神剣リ・ジェネシス` | #108: `コンセプト:` with an ASCII colon |
| `card_spirit_contract.html` | `紅蓮の雷皇龍ジークヴルム` | #108: type line `契約スピリット`; rarity `契約X` |
| `card_ultimate_contract.html` | `極相棒ゼッター` | #108: type line `契約アルティメット` |
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

Each argument is `FILE|PAGE NAME|KIND|CARD TYPE`. Add `--partial` to allow a partial page, or `--offline` to trim again from the raw pages in `--raw-dir` with no request. `--from-cache` trims pages already in the local scrape cache (`BSDB_DATA_DIR`), with no request and no `--raw-dir`. The tool is run by hand. Its robots.txt and deny-list logic is in `bs_database.ingest.policy`, covered by `tests/test_ingest_policy.py`.
