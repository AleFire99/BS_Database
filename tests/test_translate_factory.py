import logging
from pathlib import Path

import pytest

from bs_database.glossary import Glossary
from bs_database.settings import Settings
from bs_database.translate import (
    GlossaryResolver,
    NullTranslator,
    ProtectedTranslator,
    ProtectionConfig,
    make_translator,
)
from bs_database.translate.cached import CachedTranslator
from bs_database.translate.quickmt import MODEL_FILES


def _model(tmp_path: Path) -> Path:
    model = tmp_path / "model"
    model.mkdir()
    for name in MODEL_FILES:
        (model / name).write_bytes(b"x")
    return model


def test_missing_model_gives_null_and_no_file(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    s = Settings(data_dir=tmp_path, mt_model_dir=tmp_path / "nope")
    with caplog.at_level(logging.INFO):
        t = make_translator(s)
    assert isinstance(t, NullTranslator)
    assert t.translate(["あ"])[0].status == "pending"
    assert "model files missing" in caplog.text
    assert list(tmp_path.iterdir()) == []


def test_partial_model_dir_gives_null(tmp_path: Path) -> None:
    model = _model(tmp_path)
    (model / "tgt.spm.model").unlink()
    assert isinstance(
        make_translator(Settings(data_dir=tmp_path, mt_model_dir=model)), NullTranslator
    )


def test_missing_libraries_give_null_and_no_cache_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    model = _model(tmp_path)
    monkeypatch.setattr("bs_database.translate.factory.find_spec", lambda name: None)
    with caplog.at_level(logging.INFO):
        t = make_translator(Settings(data_dir=tmp_path / "data", mt_model_dir=model))
    assert isinstance(t, NullTranslator)
    assert "uv sync --group mt" in caplog.text
    assert not (tmp_path / "data").exists()


def test_model_and_libraries_give_cached_quickmt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = _model(tmp_path)
    monkeypatch.setattr("bs_database.translate.factory.find_spec", lambda name: object())
    t = make_translator(Settings(data_dir=tmp_path / "data", mt_model_dir=model), max_chars=10)
    assert isinstance(t, CachedTranslator)
    assert t.name == "quickmt-ja-en"


def _protect() -> ProtectionConfig:
    glossary = Glossary(entries={}, legacy_family_aliases=())
    return ProtectionConfig(GlossaryResolver(glossary), ("赤",))


def test_protect_wraps_the_cached_engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    model = _model(tmp_path)
    monkeypatch.setattr("bs_database.translate.factory.find_spec", lambda name: object())
    s = Settings(data_dir=tmp_path / "data", mt_model_dir=model)
    t = make_translator(s, protect=_protect())
    assert isinstance(t, ProtectedTranslator)
    assert t.name == "quickmt-ja-en+prot1"
    assert not isinstance(make_translator(s), ProtectedTranslator)


def test_protect_leaves_null_alone(tmp_path: Path) -> None:
    s = Settings(data_dir=tmp_path, mt_model_dir=tmp_path / "nope")
    assert isinstance(make_translator(s, protect=_protect()), NullTranslator)
