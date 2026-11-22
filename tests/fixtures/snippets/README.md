# Snippets

Partial batspi HTML, cut from the raw cache, that reproduces one parser edge case. They are not full pages, so they are not in the `html/fixtures.json` manifest.

| File | Source page | Case |
| --- | --- | --- |
| `section_unclosed_link.html` | `咲月帝アルティメット・ウィステリア` (fetched 2026-11) | #138: an unclosed `<a>` nests the next sections inside the 収録 list |
