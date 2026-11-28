import pytest

from bs_database.glossary import Entry, FamilyEntry, Glossary
from bs_database.translate.protect import (
    GlossaryResolver,
    Span,
    SpanKind,
    kakasi_romaniser,
    protect,
    restore,
    span_pattern,
    split_sentences,
    validate,
)

PAT = span_pattern(["赤", "青"])


@pytest.mark.parametrize(
    ("text", "kind", "inner"),
    [
        ("【ダブルシンボル】", SpanKind.KEYWORD, "ダブルシンボル"),
        ("《契約煌臨》", SpanKind.GUILLEMET, "契約煌臨"),
        ("〔赤〕", SpanKind.QUALIFIER, "赤"),
        ("『アタック時』", SpanKind.TIMING, "アタック時"),
        ("「ミカド」", SpanKind.NAME, "ミカド"),
        ("系統：", SpanKind.FAMILY_LABEL, ""),
        ("赤青赤", SpanKind.SYMBOLS, "赤青赤"),
    ],
)
def test_each_class_is_masked(text: str, kind: SpanKind, inner: str) -> None:
    masked, spans = protect(f"あ{text}い", PAT)
    assert masked == "あ<k0/>い"
    assert spans == [Span(kind, text, inner)]


def test_numbering_restarts_per_line_and_spans_can_touch() -> None:
    assert protect("【A】「B」", PAT) == ("<k0/><k1/>", [_s("【A】"), _s("「B」")])
    assert protect("「C」", PAT)[0] == "<k0/>"


def test_nested_outer_wins() -> None:
    masked, spans = protect("【あ「い」う】え", PAT)
    assert masked == "<k0/>え"
    assert spans == [Span(SpanKind.KEYWORD, "【あ「い」う】", "あ「い」う")]


def test_single_glyph_is_not_masked_and_plain_text_untouched() -> None:
    assert protect("赤を得る", PAT) == ("赤を得る", [])
    assert protect("赤赤", PAT)[0] == "<k0/>"


def test_no_glyphs_pattern() -> None:
    assert protect("赤赤", span_pattern([])) == ("赤赤", [])


def _s(text: str) -> Span:
    return protect(text, PAT)[1][0]


SP2 = [_s("【A】"), _s("「B」")]


@pytest.mark.parametrize(
    ("out", "expected"),
    [
        ("Gain <k0/> and <k1/>.", "Gain <k0/> and <k1/>."),
        ("<k1/> then <k0/>", "<k1/> then <k0/>"),  # order is free
        ('Gain "<k0/>" and “ <k1/> ”.', "Gain <k0/> and <k1/>."),
        ("Gain 「<k0/>」 and <k1/>", "Gain <k0/> and <k1/>"),
        ("Gain < k0 / > and <k1/>", "Gain <k0/> and <k1/>"),
        ("It's <k0/> and <k1/>", "It's <k0/> and <k1/>"),
        ("'<k0/> and <k1/>", "'<k0/> and <k1/>"),  # asymmetric quote kept
        ("\"<k0/>' and <k1/>", "\"<k0/>' and <k1/>"),  # mismatched pair kept
    ],
)
def test_valid_lines(out: str, expected: str) -> None:
    assert validate(out, SP2) == expected


@pytest.mark.parametrize(
    "out",
    [
        "Gain <k0/> only",  # lost
        "<k0/> <k0/> <k1/>",  # duplicated
        "<k0/> <k1/> <k9/>",  # foreign
        "<k0/> <k1/> <k",  # garbled
        "<k0/> <k1/> />",  # garbled
        "",
        "   ",
    ],
)
def test_invalid_lines(out: str) -> None:
    assert validate(out, SP2) is None


def test_no_span_line() -> None:
    assert validate("Hello.", []) == "Hello."
    assert validate("Hello <k0/>", []) is None


# --- restore and resolver ---------------------------------------------------------------


def _entry(jp: str, en: str) -> Entry:
    return Entry(jp, jp, en, "")


def _glossary() -> Glossary:
    fam = FamilyEntry("悪魔契約", "akuma", "Demon Contract", "", (), False)
    return Glossary(
        entries={
            "keywords": (_entry("ダブルシンボル", "Double Symbol"), _entry("空", "")),
            "card_types": (_entry("スピリット", "Spirit"),),
            "families": (fam,),
            "symbols": (_entry("赤", "Red"), _entry("青", "Blue")),
        },
        legacy_family_aliases=(),
    )


def _resolver() -> GlossaryResolver:
    return GlossaryResolver(
        _glossary(),
        card_names={"ミカド": "Mikado"},
        timings={"アタック時": "When Attacking"},
        romanise=lambda jp: f"rom({jp})",
    )


@pytest.mark.parametrize(
    ("jp", "expected"),
    [
        ("【ダブルシンボル】", "【Double Symbol】"),
        ("【スピリット】", "【Spirit】"),
        ("【未知】", "【未知】"),  # unresolved keeps its Japanese
        ("【空】", "【空】"),  # empty English counts as unknown
        ("『アタック時』", "『When Attacking』"),
        ("《ダブルシンボル》", "《Double Symbol》"),
        ("〔スピリット〕", "〔Spirit〕"),
        ("「悪魔契約」", "「Demon Contract」"),
        ("「ミカド」", "「Mikado」"),
        ("「未登録」", "「rom(未登録)」"),
        ("系統：", "Family:"),
        ("赤青", "Red Blue"),
        ("赤黒", "赤黒"),
    ],
)
def test_restore_renders_each_class(jp: str, expected: str) -> None:
    masked, spans = protect(jp, span_pattern(["赤", "青", "黒"]))
    assert restore(masked, spans, _resolver()) == expected


def test_restore_puts_tokens_back_in_place() -> None:
    masked, spans = protect("【ダブルシンボル】を持つ「ミカド」", PAT)
    out = validate("Has <k1/> with <k0/>.", spans)
    assert out is not None
    assert restore(out, spans, _resolver()) == "Has 「Mikado」 with 【Double Symbol】."


def test_default_resolver_romanise_is_identity() -> None:
    r = GlossaryResolver(_glossary())
    assert r.resolve(SpanKind.NAME, "未登録") == "未登録"
    assert r.resolve(SpanKind.KEYWORD, "未知") is None


def test_pykakasi_romaniser() -> None:
    pytest.importorskip("pykakasi")
    romanise = kakasi_romaniser()
    assert romanise("ミカド") == "Mikado"
    assert romanise("ABC") == "ABC"


@pytest.mark.parametrize("jp", ["あ。い", "あ い", "あ　い", "あ" * 21])
def test_name_that_is_not_name_like_keeps_its_japanese(jp: str) -> None:
    r = _resolver()
    assert r.resolve(SpanKind.NAME, jp) is None
    assert r.fallbacks == 0
    masked, spans = protect(f"「{jp}」", PAT)
    assert restore(masked, spans, r) == f"「{jp}」"


def test_name_at_the_limit_is_romanised_and_counted() -> None:
    r = _resolver()
    assert r.resolve(SpanKind.NAME, "あ" * 20) == f"rom({'あ' * 20})"
    assert r.resolve(SpanKind.NAME, "ミカド") == "Mikado"  # name map: not a fallback
    assert r.fallbacks == 1


def test_split_sentences_ignores_the_stop_inside_a_span() -> None:
    assert split_sentences("「あ。い」を得る。次。", PAT) == ["「あ。い」を得る。", "次。"]
    assert split_sentences("あ。【い。う】", PAT) == ["あ。", "【い。う】"]
    assert split_sentences("あ", PAT) == ["あ"]
    assert split_sentences("", PAT) == []


def test_uppercase_token_is_not_accepted() -> None:
    assert validate("Gain <K0/>", [_s("【A】")]) is None


def test_family_label_gets_a_space_before_a_non_space() -> None:
    r = _resolver()
    masked, spans = protect("系統：「悪魔契約」", PAT)
    assert restore(masked, spans, r) == "Family: 「Demon Contract」"
    assert restore("<k0/> x", protect("系統：", PAT)[1], r) == "Family: x"
    assert restore("<k0/>", protect("系統：", PAT)[1], r) == "Family:"
