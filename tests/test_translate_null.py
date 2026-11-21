import pytest

from bs_database.translate import NullTranslator, TranslationResult, Translator


def test_null_returns_pending_in_order() -> None:
    t: Translator = NullTranslator()
    out = t.translate(["あ", "い", ""])
    assert out == [TranslationResult(None, "pending", "null")] * 3


def test_null_empty_input() -> None:
    assert NullTranslator().translate([]) == []


@pytest.mark.parametrize(("src", "tgt"), [("jp", "jp"), ("en", "en"), ("fr", "en"), ("jp", "xx")])
def test_unsupported_pair_raises(src: str, tgt: str) -> None:
    with pytest.raises(ValueError, match="unsupported"):
        NullTranslator().translate(["a"], src=src, tgt=tgt)  # type: ignore[arg-type]


def test_reverse_pair_is_supported() -> None:
    assert NullTranslator().translate(["a"], src="en", tgt="jp")[0].status == "pending"
