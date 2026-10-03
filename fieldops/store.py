"""SQLite store of (trap_id, timestamp, species, count) and the contract validator.

    python -m fieldops.store                       # row counts per species
    python -m fieldops.store --load data/season.csv
"""
import argparse
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from . import species as species_cfg

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "fieldops.db"
TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
SCHEMA = """
CREATE TABLE IF NOT EXISTS counts (
    trap_id   TEXT    NOT NULL,
    timestamp TEXT    NOT NULL,
    species   TEXT    NOT NULL,
    count     INTEGER NOT NULL CHECK (count >= 0),
    PRIMARY KEY (trap_id, timestamp, species)
)
"""


def validate(record: dict) -> dict:
    """Return a clean contract record or raise ValueError. Extra fields are dropped."""
    if not isinstance(record, dict):
        raise ValueError(f"record must be an object, got {type(record).__name__}")

    trap_id = record.get("trap_id")
    if not isinstance(trap_id, str) or not trap_id.strip():
        raise ValueError(f"bad trap_id: {trap_id!r}")

    timestamp = record.get("timestamp")
    try:
        datetime.strptime(timestamp, TS_FORMAT)
    except (TypeError, ValueError):
        raise ValueError(f"timestamp must look like 2026-05-12T14:03:00Z, got {timestamp!r}")

    name = record.get("species")
    if not isinstance(name, str):
        raise ValueError(f"bad species: {name!r}")
    name = species_cfg.normalize(name)
    if name not in species_cfg.load()["species"]:
        raise ValueError(f"unknown species: {record['species']!r}")

    count = record.get("count")
    if isinstance(count, str) and count.strip().isdigit():
        count = int(count)
    elif isinstance(count, float) and count.is_integer():
        count = int(count)
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise ValueError(f"count must be a non-negative integer, got {record.get('count')!r}")

    return {"trap_id": trap_id.strip(), "timestamp": timestamp, "species": name, "count": count}


def _connect(path: Path) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute(SCHEMA)
    return conn


def add(records: list, path: Path = DEFAULT_DB) -> int:
    """Validate every record first, then insert all or none. Same key replaces."""
    clean = [validate(r) for r in records]
    with closing(_connect(path)) as conn, conn:
        conn.executemany(
            "INSERT OR REPLACE INTO counts VALUES (:trap_id, :timestamp, :species, :count)", clean
        )
    return len(clean)


def query(path: Path = DEFAULT_DB, trap_id=None, species=None, since=None, until=None) -> list:
    """since/until are inclusive ISO timestamps (or date prefixes like 2026-05-12)."""
    where, args = [], []
    for column, op, value in (
        ("trap_id", "=", trap_id), ("species", "=", species),
        ("timestamp", ">=", since), ("timestamp", "<=", until),
    ):
        if value is not None:
            where.append(f"{column} {op} ?")
            args.append(value)
    sql = "SELECT trap_id, timestamp, species, count FROM counts"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY timestamp, trap_id, species"
    with closing(_connect(path)) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute(sql)]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument("--load", type=Path, help="season CSV to load")
    args = p.parse_args()

    if args.load:
        from .season import load_csv

        records, _ = load_csv(args.load)
        print(f"loaded {add(records, args.db)} rows into {args.db}")

    totals = {}
    for row in query(args.db):
        totals[row["species"]] = totals.get(row["species"], 0) + row["count"]
    print(totals or "store is empty")


if __name__ == "__main__":
    main()
