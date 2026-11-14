"""Generate golden files from the legacy normalizer and DB loader.

Run from the repo root: ``uv run python tests/tools/generate_goldens.py``.
Deleted together with the legacy modules in #23; the goldens stay.
"""

import importlib
import json
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures"
GOLDENS = ROOT / "tests" / "goldens"

OLD_ROOT_LINE = (
    'root_folder = r"C:\\Users\\AleFire\\Desktop\\Projects\\BS_Database\\data\\json\\card_json"'
)
OLD_MAP_LINE = (
    'family_mapping_file = r"C:\\Users\\AleFire\\Desktop\\Projects\\BS_Database'
    '\\data\\family_mapping.txt"'
)


def run_legacy_normalizer(card_dir: Path, mapping: Path) -> None:
    source = (ROOT / "json_editor.py").read_text(encoding="utf-8")
    assert OLD_ROOT_LINE in source, "legacy root_folder line changed"
    assert OLD_MAP_LINE in source, "legacy family_mapping_file line changed"
    source = source.replace(OLD_ROOT_LINE, f"root_folder = {str(card_dir)!r}")
    source = source.replace(OLD_MAP_LINE, f"family_mapping_file = {str(mapping)!r}")
    exec(compile(source, "json_editor.py", "exec"), {"__name__": "legacy_json_editor"})


def dump_db(card_dir: Path, db_path: Path) -> dict[str, Any]:
    sys.path.insert(0, str(ROOT))
    legacy: Any = importlib.import_module("scripts.db.db_manager")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(f"sqlite:///{db_path}")
    legacy.Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    legacy.load_json_cards(str(card_dir), session)
    session.close()
    engine.dispose()

    out: dict[str, Any] = {}
    con = sqlite3.connect(db_path)
    out["ddl"] = {
        name: sql
        for name, sql in con.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name"
        )
    }
    out["counts"] = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in out["ddl"]}
    for table in ("card_types", "colors", "families"):
        out[f"{table}_names"] = sorted(r[0] for r in con.execute(f"SELECT name FROM {table}"))
    cards: dict[str, Any] = {}
    for pk, name, card_id, cost, symbol, image, type_name in con.execute(
        "SELECT c.id, c.name, c.card_id, c.cost, c.symbol, c.image, t.name "
        "FROM cards c LEFT JOIN card_types t ON t.id = c.type_id"
    ):
        cards[card_id] = {
            "name": name,
            "cost": cost,
            "symbol": symbol,
            "image": image,
            "type": type_name,
            "families": sorted(
                r[0]
                for r in con.execute(
                    "SELECT f.name FROM card_families cf JOIN families f ON f.id = cf.family_id "
                    "WHERE cf.card_id = ?",
                    (pk,),
                )
            ),
            "colors": sorted(
                r[0]
                for r in con.execute(
                    "SELECT c.name FROM card_colors cc JOIN colors c ON c.id = cc.color_id "
                    "WHERE cc.card_id = ?",
                    (pk,),
                )
            ),
            "core_requirements": sorted(
                [
                    list(r)
                    for r in con.execute(
                        "SELECT level, battlePoints, cores "
                        "FROM core_requirements WHERE card_id = ?",
                        (pk,),
                    )
                ]
            ),
        }
    out["cards"] = dict(sorted(cards.items()))
    con.close()
    return out


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        card_dir = tmp_path / "card_json"
        shutil.copytree(FIXTURES / "card_json", card_dir)
        run_legacy_normalizer(card_dir, FIXTURES / "family_mapping.txt")

        target = GOLDENS / "normalized"
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(card_dir, target)
        for path in target.rglob("*.json"):  # legacy family order is a set: sort it
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data.get("family"), list):
                data["family"] = sorted(data["family"], key=str)
            path.write_text(json.dumps(data, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")

        db = dump_db(card_dir, tmp_path / "legacy.db")
        (GOLDENS / "db.json").write_text(
            json.dumps(db, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
        )
    print("goldens written to", GOLDENS)


if __name__ == "__main__":
    main()
