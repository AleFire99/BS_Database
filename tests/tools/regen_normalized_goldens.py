"""Regenerate ``tests/goldens/normalized/*.json`` from the HTML fixtures.

Usage: ``uv run python tests/tools/regen_normalized_goldens.py``

An explicit script, never a pytest flag: tests only read the goldens. Review the diff
before committing.
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from golden_support import NORMALIZED_GOLDENS, golden_path, normalized_documents  # noqa: E402


def main() -> None:
    NORMALIZED_GOLDENS.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        documents = normalized_documents(Path(tmp))
    for name, text in documents.items():
        golden_path(name).write_text(text, encoding="utf-8")
    print(f"Wrote {len(documents)} goldens to {NORMALIZED_GOLDENS}")


if __name__ == "__main__":
    main()
