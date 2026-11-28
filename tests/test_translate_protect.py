import pytest

from bs_database.translate.protect import (
    Span,
    SpanKind,
    protect,
    span_pattern,
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
