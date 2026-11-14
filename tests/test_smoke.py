from pathlib import Path


def test_repo_layout() -> None:
    root = Path(__file__).resolve().parent.parent
    assert (root / "pyproject.toml").is_file()
