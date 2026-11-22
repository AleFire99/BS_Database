import sqlite3
from pathlib import Path

from bs_database.translate.cache import TranslationCache, text_hash


def test_roundtrip_and_persistence(tmp_path: Path) -> None:
    path = tmp_path / "sub" / "t.sqlite"
    cache = TranslationCache(path)
    assert not path.exists()
    assert cache.get_many("engine", "jp", "en", ["あ"]) == {}
    assert not path.exists()  # a read creates nothing
    cache.put_many("engine", "jp", "en", [("あ", "a"), ("い", "i")])
    again = TranslationCache(path)
    assert again.get_many("engine", "jp", "en", ["あ", "い", "う"]) == {"あ": "a", "い": "i"}
    with sqlite3.connect(path) as conn:
        assert conn.execute("PRAGMA user_version").fetchone() == (1,)


def test_key_includes_engine_and_pair(tmp_path: Path) -> None:
    cache = TranslationCache(tmp_path / "t.sqlite")
    cache.put_many("engine", "jp", "en", [("あ", "a")])
    assert cache.get_many("other", "jp", "en", ["あ"]) == {}
    assert cache.get_many("engine", "en", "jp", ["あ"]) == {}


def test_overwrite_and_empty_put(tmp_path: Path) -> None:
    cache = TranslationCache(tmp_path / "t.sqlite")
    cache.put_many("e", "jp", "en", [])
    assert not (tmp_path / "t.sqlite").exists()
    cache.put_many("e", "jp", "en", [("あ", "a")])
    cache.put_many("e", "jp", "en", [("あ", "b")])
    assert cache.get_many("e", "jp", "en", ["あ"]) == {"あ": "b"}


def test_hash_collision_is_a_miss(tmp_path: Path) -> None:
    path = tmp_path / "t.sqlite"
    cache = TranslationCache(path)
    cache.put_many("e", "jp", "en", [("あ", "a")])
    with sqlite3.connect(path) as conn:
        conn.execute(
            "UPDATE translations SET source_text='other' WHERE sha256=?", (text_hash("あ"),)
        )
    assert cache.get_many("e", "jp", "en", ["あ"]) == {}


def test_many_texts_are_chunked(tmp_path: Path) -> None:
    cache = TranslationCache(tmp_path / "t.sqlite")
    texts = [f"t{i}" for i in range(1000)]
    cache.put_many("e", "jp", "en", [(t, t.upper()) for t in texts])
    got = cache.get_many("e", "jp", "en", texts)
    assert len(got) == 1000 and got["t999"] == "T999"
