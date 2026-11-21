"""Printing images and source pages of the build (#120)."""

import hashlib
from pathlib import Path

from build_support import as_document, build, golden_documents, golden_json, query

from bs_database.build.images import associate
from bs_database.build.products import Printing
from bs_database.build.reader import Json
from bs_database.ingest.cache import RawCache


def _printing(name: str, variant: str, number: str = "N-1") -> Printing:
    return Printing(number, (0, name), variant, None, names={name})


def _image(*caption: str) -> Json:
    return {"number": "N-1", "large_url": "L", "small_url": "S", "caption": list(caption)}


def test_cascade_levels() -> None:
    a_normal = _printing("A", "normal")
    a_secret = _printing("A", "secret")
    b_normal = _printing("B", "normal")
    assert associate(_image("x"), [a_normal]) == (a_normal, "L0")
    assert associate(_image("B"), [a_normal, b_normal]) == (b_normal, "L1")
    assert associate(_image("A", "シークレット"), [a_normal, a_secret, b_normal]) == (
        a_secret,
        "L2",
    )
    assert associate(_image("zzz", "SECRET"), [a_normal, a_secret, b_normal]) == (a_secret, "L3")
    assert associate(_image("A"), [a_secret, a_normal, b_normal]) == (a_normal, "L4")
    assert associate(_image("zzz"), [a_secret, b_normal]) == (b_normal, "L5")
    assert associate(_image(), [a_secret, a_normal]) == (a_normal, "L5")


def test_golden_images_and_positions(tmp_path: Path) -> None:
    out = tmp_path / "x.db"
    result = build(out, golden_documents())
    rows = query(
        out,
        "SELECT v.code, s.code, i.position, i.source_url FROM printing_images i"
        " JOIN printings p ON p.id = i.printing_id JOIN variants v ON v.id = p.variant_id"
        " JOIN image_sizes s ON s.id = i.image_size_id"
        " JOIN card_numbers n ON n.id = p.card_number_id"
        " WHERE n.number = 'BS72-007' ORDER BY i.id",
    )
    assert [r[:3] for r in rows] == [
        ("secret", "small", 1),
        ("secret", "small", 2),
        ("secret", "large", 1),
        ("secret", "large", 2),
    ]
    assert (
        sum(result.image_levels.values()) * 2
        >= query(out, "SELECT count(*) FROM printing_images")[0][0]
    )


def test_image_without_a_printing_is_skipped(tmp_path: Path) -> None:
    data = golden_json("card_spirit")
    data["page"]["images"].append(
        {"number": "NOPE-1", "large_url": "https://x/l", "small_url": None, "caption": []}
    )
    out = tmp_path / "x.db"
    result = build(out, [as_document(data)])
    assert result.warnings["image_without_printing"] == 1
    assert query(out, "SELECT count(*) FROM printing_images")[0][0] == 4


def test_missing_small_url_and_repeated_url(tmp_path: Path) -> None:
    data = golden_json("card_spirit")
    images = data["page"]["images"]
    images[1]["small_url"] = None
    images.append(dict(images[0]))  # the same file twice for the same printing
    out = tmp_path / "x.db"
    build(out, [as_document(data)])
    assert query(out, "SELECT count(*) FROM printing_images")[0][0] == 3


def test_source_pages_and_links(tmp_path: Path) -> None:
    out = tmp_path / "x.db"
    docs = golden_documents()
    result = build(out, docs)
    assert query(out, "SELECT count(*) FROM source_pages")[0][0] == len(docs)
    assert result.warnings["source_page_without_raw_html"] == len(docs)
    page = query(
        out,
        "SELECT s.code, p.fetched_at, p.parser_version, length(p.content_sha256)"
        " FROM source_pages p JOIN sources s ON s.id = p.source_id LIMIT 1",
    )
    assert page == [("batspi", "2026-11-15T12:00:00+00:00", "2.1.0", 64)]
    cards = query(out, "SELECT count(DISTINCT card_id) FROM card_source_pages")[0][0]
    assert cards == query(out, "SELECT count(*) FROM cards")[0][0]
    assert (
        query(out, "SELECT count(DISTINCT product_id) FROM product_source_pages")[0][0]
        == query(out, "SELECT count(*) FROM products")[0][0]
    )


def test_hash_of_the_cached_raw_html(tmp_path: Path) -> None:
    data = golden_json("card_spirit")
    html = b"<html>raw</html>"
    cache_dir = tmp_path / "cache"
    RawCache(cache_dir).store(data["url"], "batspi", html, {})
    out = tmp_path / "x.db"
    result = build(out, [as_document(data)], cache_dir=cache_dir)
    assert query(out, "SELECT content_sha256 FROM source_pages") == [
        (hashlib.sha256(html).hexdigest(),)
    ]
    assert "source_page_without_raw_html" not in result.warnings
