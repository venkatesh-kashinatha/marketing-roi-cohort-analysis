"""Command line.

    python -m mroi generate          simulate the raw data into data/raw
    python -m mroi build             run the SQL, export the marts, write the Excel report
    python -m mroi query "SELECT ..." run any SQL against output/marketing.duckdb
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import duckdb
import pandas as pd

from .config import DEFAULT_HORIZON
from .database import build_database, export_marts, params, row_counts, run_checks, table
from .excel_report import ReportData, write_report
from .generate import generate, write_csvs
from .insights import add_actions, build_findings, default_changes, money, pct

log = logging.getLogger("mroi")


def cmd_generate(args) -> None:
    tables = generate(args.start, args.end, args.seed)
    counts = write_csvs(tables, Path(args.out))
    log.info("Wrote %s to %s", ", ".join(f"{n:,} {k.replace('_', ' ')}" for k, n in counts.items()), args.out)


def cmd_build(args) -> None:
    out = Path(args.out)
    db_path = out / "marketing.duckdb"
    con = build_database(Path(args.data), db_path, args.horizon)
    p = params(con)
    counts = row_counts(con)
    log.info("Loaded %d campaigns, %s spend rows, %s sign-ups and %s orders (data ends %s)",
             counts["stg_campaigns"], f"{counts['stg_spend']:,}", f"{counts['stg_signups']:,}",
             f"{counts['stg_orders']:,}", f"{p['end_date']:%Y-%m-%d}")

    checks = run_checks(con)
    failed = checks[checks["failing_rows"] > 0]
    if len(failed):
        for row in failed.itertuples():
            log.warning("Data check failed: %s (%d rows)", row.check_name, row.failing_rows)
    else:
        log.info("Data checks: all %d passed", len(checks))
    log.info("Measured window: sign-ups %s to %s, outcomes within %d days",
             f"{p['first_signup']:%Y-%m-%d}", f"{p['mature_cutoff']:%Y-%m-%d}", p["horizon"])

    scorecard = add_actions(table(con, "SELECT * FROM mart_campaign_scorecard"))
    cohorts = table(con, "SELECT * FROM mart_cohort_conversion")
    cohort_signups = table(con, "SELECT cohort_month, channel, COUNT(*) AS signups FROM int_users "
                                "GROUP BY cohort_month, channel")
    payback = table(con, "SELECT * FROM mart_payback")
    monthly = table(con, "SELECT * FROM mart_channel_monthly")
    for df, cols in ((cohorts, ["cohort_month"]), (cohort_signups, ["cohort_month"]), (monthly, ["month"])):
        for c in cols:
            df[c] = pd.to_datetime(df[c])
    findings = build_findings(scorecard, cohorts, payback, p)

    marts = export_marts(con, out / "marts")
    report = write_report(out / "Marketing_ROI_Report.xlsx", ReportData(
        scorecard=scorecard, cohort_signups=cohort_signups, cohorts=cohorts, payback=payback,
        monthly=monthly, checks=checks, changes=default_changes(scorecard), findings=findings,
        params=p, counts=counts, source=str(Path(args.data).resolve()),
    ))
    con.close()

    judged = scorecard[scorecard["action"] != "Too early to judge"]
    spend, customers, gp = judged["spend"].sum(), judged["customers"].sum(), judged["gross_profit"].sum()
    if customers:
        log.info("Spend %s | customers %s | blended CAC %s | ROI %s", money(spend), f"{customers:,.0f}",
                 money(spend / customers), pct((gp - spend) / spend, signed=True))
    else:
        log.warning("No campaign has enough measured sign-ups to judge yet.")
    log.info("Excel report: %s", report)
    log.info("Power BI feed: %s (%d CSV files)", out / "marts", len(marts))
    log.info("Database: %s", db_path)
    print("\nKey findings:")
    for line in findings:
        print(f"  - {line}")


def cmd_query(args) -> None:
    db_path = Path(args.out) / "marketing.duckdb"
    if not db_path.exists():
        raise FileNotFoundError(f"{db_path} not found. Run 'python -m mroi build' first.")
    con = duckdb.connect(str(db_path), read_only=True)
    with pd.option_context("display.max_rows", 200, "display.max_columns", 50, "display.width", 200):
        print(con.execute(args.sql).df().to_string(index=False))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m mroi", description="Marketing ROI and cohort analysis.")
    sub = parser.add_subparsers(dest="command", required=True)

    g = sub.add_parser("generate", help="simulate the raw data")
    g.add_argument("--out", default="data/raw")
    g.add_argument("--start", default="2024-01-01")
    g.add_argument("--end", default="2025-12-31")
    g.add_argument("--seed", type=int, default=42)

    b = sub.add_parser("build", help="run the SQL and build the report")
    b.add_argument("--data", default="data/raw", help="folder with the four raw CSV files")
    b.add_argument("--out", default="output")
    b.add_argument("--horizon", type=int, default=DEFAULT_HORIZON, help="days of outcomes per sign-up (default 180)")

    q = sub.add_parser("query", help="run SQL against the built database")
    q.add_argument("sql")
    q.add_argument("--out", default="output")

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s",
                        handlers=[logging.StreamHandler(sys.stdout)])
    try:
        {"generate": cmd_generate, "build": cmd_build, "query": cmd_query}[args.command](args)
        return 0
    except PermissionError as exc:
        log.error("Couldn't write %s. Close it if it's open in Excel, then run again.", exc.filename)
    except (FileNotFoundError, ValueError, duckdb.Error) as exc:
        log.error("%s", exc)
    return 1


if __name__ == "__main__":
    sys.exit(main())
