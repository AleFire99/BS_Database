# Source dossier: official Bandai site (battlespirits.com)

The official Japanese Battle Spirits site run by Bandai, `www.battlespirits.com`. **Verdict: survey only, possible future gap filler.** Survey task: [#52](https://github.com/AleFire99/BS_Database/issues/52). All facts below were observed on **2026-11-14** with a generic user agent (`Mozilla/5.0 (compatible; bs-database-research)`), spaced at least 4 s apart. Access and terms can change, so re-check before relying on any row. batspi JP is authoritative for card data; images are never redistributed.

## 1. URLs and policy status (2026-11-14)

| URL | Result | Note |
| --- | --- | --- |
| `/robots.txt` | HTTP 302 redirect to `/404/` | No crawl policy is published |
| `/cardlist/?search=true` | HTTP 200, server-rendered HTML | The card list, GET search form |
| `/cardlist/?search=true&freewords=BS01` | HTTP 200, 1.1 MB HTML | 405 results in one page, see section 3 |
| `/cardlist/guide.php` | HTTP 200 | Contains the no-reprint note, section 2 |
| `/terms/`, `/sitepolicy/` | HTTP 404 | No terms of use found at these paths |
| Footer link | `https://www.bandai.co.jp/site/privacy/` only | A privacy page, not a terms-of-use page |

No JSON API was found, and no English version of the site was found (an unverified assumption: only a limited survey was done).

## 2. Reuse note

The footer text of `/cardlist/guide.php` (the same text appears in the card list footer) reads:

> 当ホームページに掲載されている全ての画像・文字情報・その他の無断転載・使用はご遠慮ください。

Meaning: unauthorised reprinting or use of all images, text and other information on the site is discouraged ("please refrain"). No terms of use were found that grant any permission, so **this dossier claims no permission** to copy, store or redistribute the site's content.

## 3. Rendering and card markup

- The page is **server-rendered**: all results are in the HTML, no JavaScript is needed to read them.
- The search is a **GET form** at `/cardlist/index.php?search=true`. Observed parameters: `freewords`, `prodid` (product id, for example `62003` for BS01), `category[]`, `attribute[]` (colour), `system[]` (family, 351 options), `cost[min]`, `cost[max]`, `rarity[]`, `block_icon[]`, `collabo[]`, `sort`.
- `freewords=BS01` is a substring search: the 405 results include `BS01-001` and also `26RBS01-001` (a reprint set).
- **Pagination is client side.** The page lists all results in one HTML document (`<li class="cardCol js-detail">`, 405 of them for the query). The `pagerCol` element is empty and filled by `pager.js`. The result count is shown in `<label class="count">`.
- Each card is a `li.cardCol` with a link `./detail_iframe.php?card_no=<number>` (a detail view loaded in an iframe; **not fetched** in this survey).

Abridged markup of one result (`BS01-001` has the same shape):

```html
<li class="cardCol js-detail">
  <a data-src="./detail_iframe.php?card_no=26RBS01-001&card_no2=26RBS01-001">
    <div class="listItem">
      <div class="detail">
        <p class="number"><span class="num">26RBS01-001</span> | <span class="rarity">C</span></p>
        <h3 class="name">ペトリスター</h3>
        <dl class="detailInner">
          <dt class="costName">コスト</dt><dd class="costVal">3</dd>
          <dt class="alleviationName">軽減コスト</dt>
          <dd class="alleviationVal"><img src="/renewal/images/cardlist/ico_red.png" alt="赤"></dd>
          <dd class="type"><span class="attribute">赤</span> | <span class="category">スピリット</span>
              <span class="system">紅雲・風炎</span></dd>
        </dl>
      </div>
    </div>
  </a>
</li>
```

Card images are served from `/images/cardlist/<number>.webp`. They are listed here as a location only; this project never redistributes images.

## 4. Fields offered, mapped to the field inventory

Compared with [field-inventory.md](../data-model/field-inventory.md). The result list gives only the summary fields; effect text and flavor text were not observed (they may be in the unfetched detail view).

| Official site field | Markup | Inventory field | Note |
| --- | --- | --- | --- |
| Card number | `.number .num` | `card_number` | Includes reprint prefixes such as `26R` |
| Rarity | `.number .rarity` | rarity of the printing | batspi has it in the "収録" section |
| Name | `h3.name` | `name_jp` | Japanese only |
| Cost | `.costVal` | `cost` | Plain number |
| Reduction | `.alleviationVal` icons (`alt` = colour) | `reduction` | Colour icons, counts not checked |
| Colour | `.type .attribute` | `colors` | Also a search filter |
| Card type | `.type .category` | `card_type` | Also a search filter (`category[]`) |
| Family | `.type .system` | `families` | Also a search filter (`system[]`) |
| Set (product) | `prodid` filter | set membership | Product names such as `[CB31]...` |
| Effect text, symbols, illustrators, flavor text | not in the result list | `effect_blocks`, `symbols`, `illustrators`, `flavor_text` | Unknown: detail view not surveyed |

## 5. Verdict

- **Survey only.** No scraper is planned for v1 and nothing is fetched by the pipeline.
- Possible future use: a gap filler for rarity, reduction or family cross-checks, **only after** the terms question is resolved with the owner and the polite-scraping policy ([#53](https://github.com/AleFire99/BS_Database/issues/53)) covers it.
