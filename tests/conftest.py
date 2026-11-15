import socket
from typing import Any

import pytest
import requests


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail any test that tries a real network request."""

    def blocked(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("real network access attempted in a test")

    monkeypatch.setattr(requests.Session, "send", blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)
