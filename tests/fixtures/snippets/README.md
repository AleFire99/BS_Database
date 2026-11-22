# Snippets

Partial batspi HTML, cut from the raw cache, that reproduces one parser edge case. They are not full pages, so they are not in the `html/fixtures.json` manifest.

| File | Source page | Case |
| --- | --- | --- |
| `section_unclosed_link.html` | `咲月帝アルティメット・ウィステリア` (fetched 2026-11) | #138: an unclosed `<a>` nests the next sections inside the 収録 list |
| `printing_detail_paren.html` | `スターリードロー` (fetched 2026-11) | #144: a parenthetical in the detail before the rarity |
| `printing_two_notes.html` | `北斗七星龍ジーク・アポロドラゴン` | #144: two parentheticals after the rarity |
| `printing_empty_rarity.html` | `ぱーぷるとーく` | #144: an empty `<>` |
| `printing_no_rarity_detail_paren.html` | `オラクル二十一柱 XX ザ・ジャッジメント` | #144: no rarity, a parenthetical in the detail and one note |
| `printing_nested_link.html` | `ブリザードウォール` | #144: a product link nested in `「」` and an illustrator link in the note |
| `printing_note_starts_with_link.html` | `スワロウテイル` | #144: a note starting with a link |
| `printing_unlinked_dates.html` | `ローヤルポーション` | #144: a row without a product link, a bare date run after `(3on3)` |
| `printing_unlinked_date_paren.html` | `フレイムチャージ` | #144: a row without a product link, a date in parentheses |
| `printing_unlinked_date_note.html` | `大切なもの` | #144: a row without a product link, a date and a note |
