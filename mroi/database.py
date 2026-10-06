"""Run the SQL pipeline in DuckDB, run the data checks and export the marts."""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb
import pandas as pd

from .config import EXPORTS, SQL_DIR, SQL_PIPELINE

log = logging.getLogger(__name__)
RAW_FILES = ("campaigns.csv", "daily_spend.csv", "signups.csv", "orders.csv")


def build_database(raw_dir: Path, db_path: Path | str, horizon: int) -> duckdb.DuckDBPyConnection:
    """Create (or replace) every table and view by running the numbered SQL files in order."""
    raw_dir = Path(raw_dir).resolve()
    missing = [f for f in RAW_FILES if not (raw_dir / f).exists()]
    if missing:
        raise FileNotFoundError(f"Missing raw file(s) in {raw_dir}: {', '.join(missing)}. "
                                "Run 'python -m mroi generate' first.")
    if db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    for name in SQL_PIPELINE:
        sql = (SQL_DIR / name).read_text(encoding="utf-8")
        sql = sql.replace("{{RAW_DIR}}", raw_dir.as_posix().replace("'", "''"))
        sql = sql.replace("{{HORIZON}}", str(int(horizon)))
        con.execute(sql)
        log.debug("Ran %s", name)
    return con


def run_checks(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    checks = con.execute((SQL_DIR / "checks.sql").read_text(encoding="utf-8")).df()
    checks["failing_rows"] = checks["failing_rows"].astype(int)
    return checks


def export_marts(con: duckdb.DuckDBPyConnection, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, query in EXPORTS.items():
        path = out_dir / f"{name}.csv"
        con.execute(query).df().to_csv(path, index=False)
        paths.append(path)
    return paths


def table(con: duckdb.DuckDBPyConnection, query: str) -> pd.DataFrame:
    return con.execute(query).df()


def params(con: duckdb.DuckDBPyConnection) -> dict:
    row = con.execute("SELECT end_date, horizon_days, mature_cutoff FROM params").fetchone()
    first = con.execute("SELECT MIN(signup_date) FROM stg_signups").fetchone()[0]
    return {"end_date": pd.Timestamp(row[0]), "horizon": int(row[1]),
            "mature_cutoff": pd.Timestamp(row[2]), "first_signup": pd.Timestamp(first)}


def row_counts(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    return {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("stg_campaigns", "stg_spend", "stg_signups", "stg_orders")}
