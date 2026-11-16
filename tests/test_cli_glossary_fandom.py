"""``bsdb glossary fandom`` through CliRunner with a fake API (#104), offline."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from bs_database import cli
from bs_database.cli import app
from bs_database.ingest.http import Blocked
from bs_database.review.fandom import FANDOM_JSON, NameSource
from bs_database.settings import Settings

runner = CliRunner()
FIXTURES = Path(__file__).parent / "fixtures" / "fandom"


def fixture_texts(name: str) -> dict[str, str]:
    data = json.loads((FIXTURES / f"{name}.json").read_text("utf-8"))
    return {
        p["title"]: p["revisions"][0]["slots"]["main"]["*"] for p in data["query"]["pages"].values()
    }


class FakeApi:
    def __init__(self) -> None:
        self.requests_made = 7
        self.texts = {
            "Category:Family": fixture_texts("families"),
            "Category:Keywords": fixture_texts("keywords"),
            "Card Rarity": fixture_texts("rarity"),
        }
        self.by_title = {t: x for group in self.texts.values() for t, x in group.items()}

    def category_members(self, category: str) -> list[str]:
        return list(reversed(self.texts[category]))  # unsorted on purpose

    def wikitext(self, titles: list[str]) -> dict[str, str]:
        return {t: self.by_title[t] for t in titles}


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    data = tmp_path / "data"
    monkeypatch.setenv("BSDB_DATA_DIR", str(data))
    return data


def install(monkeypatch: pytest.MonkeyPatch, api: NameSource) -> None:
    monkeypatch.setattr(cli, "_build_fandom_api", lambda settings: api)


def test_fandom_writes_sorted_json(data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    install(monkeypatch, FakeApi())
    result = runner.invoke(app, ["glossary", "fandom"])
    assert result.exit_code == 0, result.output
    doc = json.loads((data_dir / "review" / FANDOM_JSON).read_text("utf-8"))
    assert set(doc) == {"families", "keywords", "rarities", "unmatched", "requests_made"}
    assert doc["requests_made"] == 7
    assert doc["unmatched"] == {"families": [], "keywords": ["AFO"]}
    assert {f["title"] for f in doc["families"]} >= {"Machine Beast", "Armor (Family)"}
    assert {"jp": "機獣", "en": "Machine Beast", "romaji": "kijuu", "title": "Machine Beast"} in (
        doc["families"]
    )
    assert {"jp": "コモン", "en": "Common", "letter": "C"} in doc["rarities"]
    assert "6 families (0 unmatched), 5 keywords (1 unmatched)" in result.output


def test_fandom_output_is_deterministic_and_out_option(
    data_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install(monkeypatch, FakeApi())
    out = tmp_path / "elsewhere"
    first = runner.invoke(app, ["glossary", "fandom", "--out", str(out)])
    assert first.exit_code == 0, first.output
    text = (out / FANDOM_JSON).read_text("utf-8")
    runner.invoke(app, ["glossary", "fandom", "--out", str(out)])
    assert (out / FANDOM_JSON).read_text("utf-8") == text
    assert not (data_dir / "review").exists()


def test_fandom_blocked_exits_3(data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class Blocking(FakeApi):
        def category_members(self, category: str) -> list[str]:
            raise Blocked("403 or challenge page")

    install(monkeypatch, Blocking())
    result = runner.invoke(app, ["glossary", "fandom"])
    assert result.exit_code == 3
    assert "stopped" in result.output
    assert not (data_dir / "review" / FANDOM_JSON).exists()


def test_default_factory_builds_the_real_client(tmp_path: Path) -> None:
    from bs_database.ingest.fandom import FandomApi

    assert isinstance(cli._build_fandom_api(Settings(data_dir=tmp_path)), FandomApi)
