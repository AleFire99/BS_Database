import logging
from pathlib import Path

import pytest
from fakes import FakeClock, FakeJsonTransport, ok_response
from pydantic import SecretStr

from bs_database.ingest.http import HttpResponse
from bs_database.settings import Settings
from bs_database.translate import NullTranslator, make_translator
from bs_database.translate.cached import CachedTranslator
from bs_database.translate.deepl import DeepLTranslator


def test_no_key_gives_null_and_no_file(tmp_path: Path) -> None:
    s = Settings(data_dir=tmp_path, deepl_api_key=None)
    t = make_translator(s)
    assert isinstance(t, NullTranslator)
    assert t.translate(["あ"])[0].status == "pending"
    assert list(tmp_path.iterdir()) == []


def test_empty_key_counts_as_unset(tmp_path: Path) -> None:
    s = Settings(data_dir=tmp_path, deepl_api_key=SecretStr(""))
    assert isinstance(make_translator(s), NullTranslator)


def test_key_gives_cached_deepl(tmp_path: Path) -> None:
    s = Settings(data_dir=tmp_path, deepl_api_key=SecretStr("test-key:fx"))
    t = make_translator(s, max_chars=10)
    assert isinstance(t, CachedTranslator)
    assert t.name == "deepl"
    assert "test-key" not in repr(t) and "test-key" not in repr(s)


def test_key_text_never_leaks_in_logs(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    transport = FakeJsonTransport(
        [
            ok_response(["a"]),
            HttpResponse(429, {}, b"{}"),
            ok_response(["b"]),
            HttpResponse(456, {}, b"{}"),
        ]
    )
    engine = DeepLTranslator(SecretStr("test-key:fx"), transport=transport, clock=FakeClock())
    with caplog.at_level(logging.DEBUG):
        for text in ("a", "b", "c"):
            engine.translate([text])
    assert "test-key" not in caplog.text
