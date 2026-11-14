import json
import socket
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import requests

HTML = Path(__file__).parent / "fixtures" / "html"
SCRAPER_GOLDENS = Path(__file__).parent / "goldens" / "scrapers"


class FakeResponse:
    def __init__(self, content: bytes, status_code: int = 200) -> None:
        self.content = content
        self.status_code = status_code
        self.encoding = "utf-8"

    @property
    def text(self) -> str:
        return self.content.decode(self.encoding)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail any test that tries a real network request."""

    def blocked(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("real network access attempted in a test")

    monkeypatch.setattr(requests.Session, "send", blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)


@pytest.fixture(scope="session")
def fixture_urls() -> dict[str, str]:
    """Fixture file name -> source URL."""
    raw: dict[str, Any] = json.loads((HTML / "fixtures.json").read_text(encoding="utf-8"))
    return {k: v if isinstance(v, str) else v["url"] for k, v in raw.items()}


@pytest.fixture
def serve(
    monkeypatch: pytest.MonkeyPatch, fixture_urls: dict[str, str]
) -> Callable[[dict[str, bytes] | None], list[str]]:
    """Serve saved HTML through ``requests.get``; returns the list of requested URLs.

    Extra ``{url: bytes}`` pages can be passed for synthetic edge cases.
    """
    pages = {url: (HTML / name).read_bytes() for name, url in fixture_urls.items()}
    requested: list[str] = []

    def install(extra: dict[str, bytes] | None = None) -> list[str]:
        pages.update(extra or {})

        def fake_get(url: str, *args: Any, **kwargs: Any) -> FakeResponse:
            requested.append(url)
            return FakeResponse(pages[url])

        monkeypatch.setattr(requests, "get", fake_get)
        return requested

    return install


@pytest.fixture
def stub_translator(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the translator with the deterministic ``EN<text>`` stub used by the goldens."""
    from bs_database.scrapers import batspi_card

    class Stub:
        def __init__(self, source: str = "ja", target: str = "en") -> None:
            pass

        def translate(self, text: str) -> str:
            return f"EN{text}"

    monkeypatch.setattr(batspi_card, "GoogleTranslator", Stub)
