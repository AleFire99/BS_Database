"""Regenerate ``tests/goldens/build_counts.json`` from the normalized goldens.

Usage: ``uv run python tests/tools/regen_build_goldens.py``

An explicit script, never a pytest flag: tests only read the golden. Review the diff before
committing.
"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from build_support import BUILD_GOLDEN, build_summary  # noqa: E402


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        summary = build_summary(Path(tmp) / "golden.db")
    BUILD_GOLDEN.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {BUILD_GOLDEN}")


if __name__ == "__main__":
    main()
