"""Tests for the ``tests/tools/parity_report.py`` helper (#124): one case per category."""

import hashlib
import importlib.util
import sqlite3
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from bs_database.schema import load_schema_sql

TOOL = Path(__file__).parent / "tools" / "parity_report.py"

LEGACY_DDL = """
CREATE TABLE card_types (id INTEGER PRIMARY KEY, name TEXT UNIQUE);
CREATE TABLE colors (id INTEGER PRIMARY KEY, name TEXT UNIQUE);
CREATE TABLE families (id INTEGER PRIMARY KEY, name TEXT UNIQUE);
CREATE TABLE cards (id INTEGER PRIMARY KEY, name TEXT, card_id TEXT UNIQUE, cost INTEGER,
    symbol TEXT, image TEXT, type_id INTEGER);
CREATE TABLE card_colors (card_id INTEGER, color_id INTEGER, PRIMARY KEY (card_id, color_id));
CREATE TABLE card_families (card_id INTEGER, family_id INTEGER, PRIMARY KEY (card_id, family_id));
CREATE TABLE core_requirements (id INTEGER PRIMARY KEY, level INTEGER, "battlePoints" INTEGER,
    cores INTEGER, card_id INTEGER);
"""

# legacy card: (number, name, cost, type, colours, families, levels)
LEGACY_CARDS = [
    ("BS01-001", "Goladon", 3, "Spirit", ["Red"], ["Dragon"], [(1, 1, 1000)]),
    ("BS01-002", "Fire  Dragon", 3, "Spirit", ["Red"], ["Dragon"], [(1, 1, 1000)]),
    ("BS01-003", "Hammer Drake", 3, "Spirit", ["Red"], ["Dragon"], [(1, 1, 1000)]),
    ("BS01-004", "Completely Other", 3, "Spirit", ["Red"], ["Dragon"], [(1, 1, 1000)]),
    ("BS01-005", "White Thing", 3, "Spirit", [], ["Dragon"], []),
    ("BS01-006", "Lost Colours", 3, "Spirit", [], ["Dragon"], [(1, 1, 1000)]),
    ("BS01-007", "Half Colours", 3, "Spirit", ["Red"], ["Dragon"], [(1, 1, 1000)]),
    ("BS01-008", "Unmapped Fam", 3, "Spirit", ["Red"], ["Moon Thing"], [(1, 1, 1000)]),
    ("BS01-009", "Merged Fam", 3, "Spirit", ["Red"], ["Both Together"], [(1, 1, 1000)]),
    ("BS01-010", "Collision", 3, "Spirit", ["Red"], ["Wyrm"], [(1, 1, 1000)]),
    ("BS01-011", "Extra Frag", 3, "Spirit", ["Red"], ["Dragon", "Year", "Frag"], [(1, 1, 1000)]),
    ("BS01-012", "More Fam", 3, "Spirit", ["Red"], ["Dragon"], [(1, 1, 1000)]),
    ("BS01-013", "Wrong Cost", 3, "Spirit", ["Red"], ["Dragon"], [(1, 1, 1000)]),
    ("BS01-014", "Wrong Type", 3, "Spirit", ["Red"], ["Dragon"], [(1, 1, 1000)]),
    ("BS01-015", "More Levels", 3, "Spirit", ["Red"], ["Dragon"], [(1, 1, 1000)]),
    ("BS01-016", "Diff Levels", 3, "Spirit", ["Red"], ["Dragon"], [(1, 1, 1000)]),
    ("BS01-017", "Level Lost", 3, "Spirit", ["Red"], ["Dragon"], [(1, 1, 1000)]),
    ("BS52-007", "Fighter/Braver", 3, "Spirit", ["Red"], ["Dragon"], []),
    ("BS99-001", "Gone", 3, "Spirit", ["Red"], ["Dragon"], []),
    ("BS98-001", "Renamed", 3, "Spirit", ["Red"], ["Dragon"], []),
]

L1 = [(1, 1, 1000)]


def _new_cards() -> list[dict[str, object]]:
    # number, name_jp, name_en, cost, type, colours, families (jp), levels
    base = {"type": "Spirit", "colors": ["Red"], "fams": ["竜"], "levels": L1, "cost": 3}
    rows: list[tuple[str, str, str | None, dict[str, object]]] = [
        ("BS01-001", "ゴラドン", "Goladon", {}),
        ("BS01-002", "ファイア", "Fire Dragon", {}),
        ("BS01-003", "ハンマー", "Hammer-Drake!", {}),
        ("BS01-004", "別", "Another Wording Entirely", {}),
        ("BS01-005", "白", None, {"colors": ["White"]}),
        ("BS01-006", "二色", "Two Colours", {"colors": ["Blue", "Red"]}),
        ("BS01-007", "半", "Half", {"colors": ["Blue", "Red"]}),
        ("BS01-008", "未", "Unmapped", {"fams": ["月"]}),
        ("BS01-009", "合", "Merged", {"fams": ["竜", "月"]}),
        ("BS01-010", "衝", "Collision", {"fams": ["蛇"]}),
        ("BS01-011", "断", "Extra", {"fams": ["竜"]}),
        ("BS01-012", "増", "More", {"fams": ["竜", "月"]}),
        ("BS01-013", "費", "Wrong Cost", {"cost": 4}),
        ("BS01-014", "種", "Wrong Type", {"type": "Magic"}),
        ("BS01-015", "階", "More Levels", {"levels": [(1, 1, 1000), (2, 3, 2000)]}),
        ("BS01-016", "違", "Diff Levels", {"levels": [(1, 2, 1000)]}),
        ("BS01-017", "無", "Level Lost", {"levels": []}),
        ("BS52-007(A)", "表", "Fighter", {}),
        ("BS52-007(B)", "裏", "Braver", {}),
        ("BS98-001(1)", "改", "Renamed", {}),
        ("BSC01-001", "新", "New", {}),
        ("BSC01-002", "新2", "New 2", {}),
        ("CB01-001", "新3", "New 3", {}),
    ]
    return [{"number": n, "jp": j, "en": e, **base, **extra} for n, j, e, extra in rows]


def make_legacy(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(LEGACY_DDL)
    types = ["Spirit", "Nexus", "Magic", "Brave", "Ultimate"]
    colors = ["Red", "Purple", "Green", "Yellow", "Blue"]
    fams = ["Dragon", "Moon Thing", "Both Together", "Wyrm", "Year", "Frag"]
    conn.executemany("INSERT INTO card_types VALUES (?, ?)", list(enumerate(types, 1)))
    conn.executemany("INSERT INTO colors VALUES (?, ?)", list(enumerate(colors, 1)))
    conn.executemany("INSERT INTO families VALUES (?, ?)", list(enumerate(fams, 1)))
    for cid, (number, name, cost, ctype, cols, fs, levels) in enumerate(LEGACY_CARDS, 1):
        conn.execute(
            "INSERT INTO cards VALUES (?, ?, ?, ?, 'red', '', ?)",
            (cid, name, number, cost, types.index(ctype) + 1),
        )
        for col in cols:
            conn.execute("INSERT INTO card_colors VALUES (?, ?)", (cid, colors.index(col) + 1))
        for f in fs:
            conn.execute("INSERT INTO card_families VALUES (?, ?)", (cid, fams.index(f) + 1))
        for level, cores, bp in levels:
            conn.execute(
                'INSERT INTO core_requirements (level, "battlePoints", cores, card_id) '
                "VALUES (?, ?, ?, ?)",
                (level, bp, cores, cid),
            )
    conn.commit()
    conn.close()


def make_new(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(load_schema_sql())
    types = {"Brave": 1, "Magic": 2, "Nexus": 3, "Spirit": 4, "Ultimate": 5}
    colors = {"Blue": 1, "Green": 2, "Purple": 3, "Red": 4, "White": 5, "Yellow": 6}
    for name, i in types.items():
        conn.execute("INSERT INTO card_types VALUES (?, ?, ?)", (i, name.lower(), name))
    for name, i in colors.items():
        conn.execute("INSERT INTO colors VALUES (?, ?, ?)", (i, name.lower(), name))
    fams = {"竜": (1, "Dragon"), "月": (2, "Moon"), "蛇": (3, "Wyrm Snake")}
    for jp, (i, en) in fams.items():
        conn.execute(
            "INSERT INTO families (id, code, name_jp, name_en) VALUES (?, ?, ?, ?)",
            (i, f"f{i}", jp, en),
        )
    # a legacy English name is the preferred name of another family: collision case
    conn.execute(
        "INSERT INTO family_aliases (family_id, alias, lang, translation_source_id) "
        "VALUES (1, 'Moon Thing', 'en', 4)"
    )
    for cid, card in enumerate(_new_cards(), 1):
        conn.execute(
            "INSERT INTO cards (id, card_type_id, cost, name_jp, name_en) VALUES (?, ?, ?, ?, ?)",
            (cid, types[str(card["type"])], card["cost"], card["jp"], card["en"]),
        )
        conn.execute(
            "INSERT INTO card_numbers (id, number, card_id) VALUES (?, ?, ?)",
            (cid, card["number"], cid),
        )
        for col in card["colors"]:  # type: ignore[attr-defined]
            conn.execute("INSERT INTO card_colors VALUES (?, ?)", (cid, colors[col]))
        for jp in card["fams"]:  # type: ignore[attr-defined]
            conn.execute("INSERT INTO card_families VALUES (?, ?)", (cid, fams[jp][0]))
        for level, cores, bp in card["levels"]:  # type: ignore[attr-defined]
            conn.execute(
                "INSERT INTO card_levels (card_id, level, cores, battle_points) "
                "VALUES (?, ?, ?, ?)",
                (cid, level, cores, bp),
            )
    conn.commit()
    conn.close()


@pytest.fixture(scope="module")
def tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("parity_report", TOOL)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["parity_report"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def dbs(tmp_path: Path) -> tuple[Path, Path]:
    legacy, new = tmp_path / "legacy.db", tmp_path / "new.db"
    make_legacy(legacy)
    make_new(new)
    return legacy, new


def report(tool: ModuleType, dbs: tuple[Path, Path], glossary: Path | None = None) -> str:
    legacy, new = tool.connect_ro(dbs[0]), tool.connect_ro(dbs[1])
    try:
        text: str = tool.build_report(legacy, new, glossary)
    finally:
        legacy.close()
        new.close()
    return text


def row(text: str, section: str, key: str) -> list[str]:
    """Cells of the ``key`` row of the table under the ``### section`` heading."""
    block = text.split(f"### {section}\n", 1)[1].split("\n### ", 1)[0].split("\n## ", 1)[0]
    for line in block.splitlines():
        cells = [c.strip() for c in line.strip("|").split("|")]
        if cells and cells[0] == key:
            return cells
    raise AssertionError(f"no row {key!r} in {section!r}")


def test_table_counts_and_overlap(tool: ModuleType, dbs: tuple[Path, Path]) -> None:
    text = report(tool, dbs)
    assert "| `cards` | 20 | `cards` | 23 |" in text
    assert "| `colors` | 5 | `colors` | 6 |" in text
    assert "| Legacy | 20 |" in text
    assert "| New | 23 |" in text
    assert "| In both | 17 |" in text
    assert "| Only in legacy | 3 |" in text
    assert "| Only in new | 6 |" in text


def test_legacy_only_by_cause(tool: ModuleType, dbs: tuple[Path, Path]) -> None:
    text = report(tool, dbs)
    assert row(text, "Legacy-only numbers by cause", "flip")[1] == "1"
    assert "BS52-007 -> BS52-007(A), BS52-007(B)" in text
    assert row(text, "Legacy-only numbers by cause", "suffix")[1] == "1"
    assert row(text, "Legacy-only numbers by cause", "absent")[1] == "1"
    assert "BS99-001" in text


def test_new_only_grouped_by_prefix(tool: ModuleType, dbs: tuple[Path, Path]) -> None:
    text = report(tool, dbs)
    assert "| BSC01 | 2 |" in text
    assert "| CB01 | 1 |" in text
    assert "| BS52 | 2 |" in text


def test_name_categories(tool: ModuleType, dbs: tuple[Path, Path]) -> None:
    text = report(tool, dbs)
    assert row(text, "Name", "same")[1] != "0"
    assert "BS01-002: 'Fire  Dragon'" in row(text, "Name", "folded")[4]
    assert "BS01-003: 'Hammer Drake'" in row(text, "Name", "folded")[4]
    assert "BS01-004: 'Completely Other'" in row(text, "Name", "far")[4]
    assert row(text, "Name", "no_en")[1] == "1"


def test_cost_and_type_differences(tool: ModuleType, dbs: tuple[Path, Path]) -> None:
    text = report(tool, dbs)
    assert row(text, "Cost", "diff")[1] == "1"
    assert "BS01-013: 3 vs 4" in text
    assert row(text, "Card type", "diff")[1] == "1"
    assert "BS01-014: Spirit vs Magic" in text


def test_colour_categories(tool: ModuleType, dbs: tuple[Path, Path]) -> None:
    text = report(tool, dbs)
    assert row(text, "Colours", "white_added")[1] == "1"
    assert row(text, "Colours", "legacy_empty")[1] == "1"
    assert row(text, "Colours", "legacy_subset")[1] == "1"


def test_family_categories(tool: ModuleType, dbs: tuple[Path, Path]) -> None:
    text = report(tool, dbs, tool.DEFAULT_GLOSSARY)
    assert "BS01-010" in row(text, "Families", "count_same")[4]  # 'Wyrm' has no mapping
    assert "BS01-008" in row(text, "Families", "name_collision")[4]  # alias points elsewhere
    assert "BS01-009" in row(text, "Families", "legacy_merged")[4]
    assert "BS01-011" in row(text, "Families", "legacy_extra")[4]
    assert "BS01-012" in row(text, "Families", "more")[4]
    assert row(text, "Families", "unmapped_names")[1] != "0"


def test_core_level_categories(tool: ModuleType, dbs: tuple[Path, Path]) -> None:
    text = report(tool, dbs)
    assert row(text, "Core levels", "new_only")[1] == "1"
    assert row(text, "Core levels", "superset")[1] == "1"
    assert row(text, "Core levels", "diff")[1] == "1"
    assert row(text, "Core levels", "legacy_only")[1] == "1"


def test_output_is_deterministic_and_read_only(
    tool: ModuleType, dbs: tuple[Path, Path], tmp_path: Path
) -> None:
    before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in dbs]
    out = tmp_path / "report.md"
    cmd = [sys.executable, str(TOOL), str(dbs[0]), str(dbs[1]), "--out", str(out)]
    subprocess.run(cmd, check=True, capture_output=True)
    first = out.read_text(encoding="utf-8")
    subprocess.run(cmd, check=True, capture_output=True)
    assert out.read_text(encoding="utf-8") == first
    assert first == report(tool, dbs, tool.DEFAULT_GLOSSARY)
    assert before == [hashlib.sha256(p.read_bytes()).hexdigest() for p in dbs]


def test_missing_file(tmp_path: Path) -> None:
    out = subprocess.run(
        [sys.executable, str(TOOL), str(tmp_path / "a.db"), str(tmp_path / "b.db")],
        capture_output=True,
    )
    assert out.returncode == 1
