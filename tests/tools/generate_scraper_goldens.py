"""Generate scraper goldens by running the untouched legacy batspi scrapers on saved HTML.

Run from the repo root: ``uv run python tests/tools/generate_scraper_goldens.py``.
``requests.get`` serves the fixtures in ``tests/fixtures/html`` and the translator is replaced
by a deterministic stub (``EN<text>``). Deleted together with the legacy modules in #23; the
goldens stay. The fandom pages are synthetic (the wiki sits behind a bot challenge).
"""

import hashlib
import importlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[2]
HTML = ROOT / "tests" / "fixtures" / "html"
GOLDENS = ROOT / "tests" / "goldens" / "scrapers"


class FakeResponse:
    def __init__(self, content: bytes) -> None:
        self.content = content
        self.status_code = 200
        self.encoding = "utf-8"

    @property
    def text(self) -> str:
        return self.content.decode("utf-8")

    def raise_for_status(self) -> None:
        return None


class StubTranslator:
    def __init__(self, source: str = "ja", target: str = "en") -> None:
        pass

    def translate(self, text: str) -> str:
        return f"EN{text}"


def write(name: str, data: Any) -> None:
    GOLDENS.mkdir(parents=True, exist_ok=True)
    (GOLDENS / name).write_text(
        json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> None:
    raw: dict[str, Any] = json.loads((HTML / "fixtures.json").read_text(encoding="utf-8"))
    sources: dict[str, str] = {k: v if isinstance(v, str) else v["url"] for k, v in raw.items()}
    by_url = {url: (HTML / name).read_bytes() for name, url in sources.items()}

    def fake_get(url: str, *args: Any, **kwargs: Any) -> FakeResponse:
        return FakeResponse(by_url[url])

    requests.get = fake_get  # type: ignore[assignment]  # BEFORE the legacy imports below
    sys.path.insert(0, str(ROOT))
    index_url = sources["index.html"]
    set_url = sources["set.html"]

    with tempfile.TemporaryDirectory() as tmp:
        old_cwd = os.getcwd()
        os.chdir(tmp)  # set_link_extractor fetches and writes at import time
        try:
            importlib.import_module("scripts.set_link_extractor")
            lines = Path("extracted_urls.txt").read_text(encoding="utf-8").splitlines()
            write("set_urls.json", lines)

            links_mod: Any = importlib.import_module("scripts.extract_card_links")
            links = links_mod.extract_links(set_url)
            write("card_links.json", [list(t) for t in links])

            card_mod: Any = importlib.import_module("scripts.scraper.card_scraper")
            card_mod.GoogleTranslator = StubTranslator
            card_ids = {
                "card_spirit.html": "BS72-007",
                "card_nexus.html": "BS72-069",
                "card_magic.html": "BS72-075",
            }
            for fixture, card_id in card_ids.items():
                card_mod.scrape_card_data(card_id, sources[fixture], "out")
                data = json.loads(
                    Path("out", "card_json", "BS72", f"{card_id}.json").read_text(encoding="utf-8")
                )
                write(f"card_{card_id}.json", data)

            fandom_mod: Any = importlib.import_module("scripts.scraper.json_set_scraper")
            fandom_mod.scrape_battle_spirits(sources["fandom_set_BS47.html"], "set_out/BS47.json")
            write("fandom_set.json", json.loads(Path("set_out/BS47.json").read_text("utf-8")))

            images_mod: Any = importlib.import_module("scripts.scraper.image_scraper")
            infos = images_mod.extract_card_infos(sources["fandom_set_BS47.html"])
            write("fandom_card_infos.json", [list(t) for t in infos])

            Path("images/BS47").mkdir(parents=True)
            downloads: dict[str, Any] = {}
            for fixture, card_id in {
                "fandom_card.html": "BS47-001",
                "fandom_card_base64.html": "BS47-002",
            }.items():
                images_mod.download_card_image(sources[fixture], card_id, "images/BS47")
                file = Path("images/BS47", f"{card_id}.jpg")
                downloads[card_id] = (
                    {
                        "path": f"BS47/{card_id}.jpg",
                        "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
                    }
                    if file.exists()
                    else None
                )
            write("fandom_images.json", downloads)
        finally:
            os.chdir(old_cwd)
    assert index_url in by_url
    print("goldens written to", GOLDENS)


if __name__ == "__main__":
    main()
