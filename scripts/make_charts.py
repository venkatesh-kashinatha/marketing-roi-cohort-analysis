"""Build the README charts in docs/ from the Power BI feed in output/marts.

Run after `python -m mroi build`:
    python scripts/make_charts.py
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MARTS = ROOT / "output" / "marts"
DOCS = ROOT / "docs"
DOCS.mkdir(exist_ok=True)

GOOD, BAD, MID, INK = "#2E7D5B", "#C0392B", "#8A8F98", "#1F2933"
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.titleweight": "bold", "axes.titlesize": 12, "figure.dpi": 130})


def roi_by_campaign():
    sc = pd.read_csv(MARTS / "mart_campaign_scorecard.csv").dropna(subset=["roi"])
    sc = sc[sc["spend"] > 0].sort_values("roi")
    fig, ax = plt.subplots(figsize=(8, 5))
    colors = [GOOD if r >= 0.25 else (BAD if r < 0 else MID) for r in sc["roi"]]
    names = sc["campaign_name"].str.replace("$", r"\$", regex=False)
    ax.barh(names, sc["roi"], color=colors)
    ax.axvline(0, color=INK, lw=0.8)
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(1.0))
    for y, (r, cac) in enumerate(zip(sc["roi"], sc["cac"])):
        ax.text(max(r, 0) + 0.05, y, f"{r:+.0%}  (CAC \\${cac:,.0f})",
                va="center", ha="left", fontsize=8, color=INK)
    ax.set_xlim(min(sc["roi"].min() - 0.1, -1), sc["roi"].max() + 1.0)
    ax.set_title("180-day ROI on gross profit, by campaign")
    ax.set_xlabel("ROI = (gross profit - spend) / spend")
    fig.tight_layout(); fig.savefig(DOCS / "roi_by_campaign.png"); plt.close(fig)


def payback_by_channel():
    pb = pd.read_csv(MARTS / "mart_payback.csv")
    g = pb.groupby(["channel", "days_since_signup"])[["spend", "gross_profit_cum"]].sum().reset_index()
    g["ratio"] = g["gross_profit_cum"] / g["spend"]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for ch, d in g.groupby("channel"):
        ax.plot(d["days_since_signup"], d["ratio"], marker="o", ms=3, label=ch)
    ax.axhline(1, color=INK, lw=1, ls="--")
    ax.text(g["days_since_signup"].max(), 1.03, "paid back", ha="right", fontsize=8)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0))
    ax.set_xlabel("Days since sign-up"); ax.set_ylabel("Cumulative gross profit / spend")
    ax.set_title("Payback curve by channel")
    ax.legend(fontsize=8, ncol=2, frameon=False)
    fig.tight_layout(); fig.savefig(DOCS / "payback_by_channel.png"); plt.close(fig)


def conversion_trend():
    cc = pd.read_csv(MARTS / "mart_cohort_conversion.csv", parse_dates=["cohort_month"])
    d = cc[cc["within_days"] == 30].dropna(subset=["customers_cum"])
    tot = d.groupby("cohort_month")[["signups", "customers_cum"]].sum()
    tot["rate"] = tot["customers_cum"] / tot["signups"]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(tot.index, tot["rate"], color=INK, marker="o", ms=3)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0, decimals=0))
    ax.set_title("30-day conversion by sign-up month (all channels)")
    ax.set_ylabel("Sign-ups who bought within 30 days")
    fig.autofmt_xdate(); fig.tight_layout(); fig.savefig(DOCS / "conversion_trend.png"); plt.close(fig)


def cac_vs_value():
    sc = pd.read_csv(MARTS / "mart_campaign_scorecard.csv").dropna(subset=["cac"])
    sc = sc[sc["customers"] > 0]
    sc["gp_per_customer"] = sc["gross_profit"] / sc["customers"]
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.scatter(sc["cac"], sc["gp_per_customer"], s=sc["spend"] / 600, alpha=0.6, color="#3366AA")
    xlim = sc["cac"].max() * 1.15; ylim = sc["gp_per_customer"].max() * 1.3
    ax.plot([0, ylim], [0, ylim], color=INK, lw=0.8, ls="--")
    ax.text(ylim * 0.72, ylim * 0.9, "break-even", fontsize=8)
    show = set(sc.nlargest(3, "roi")["campaign_name"]) | set(sc.nsmallest(3, "roi")["campaign_name"]) \
        | set(sc.nlargest(2, "spend")["campaign_name"])
    for _, r in sc.iterrows():
        if r["campaign_name"] in show:
            ax.annotate(r["campaign_name"].replace("$", r"\$"), (r["cac"], r["gp_per_customer"]),
                        fontsize=7, xytext=(5, 4), textcoords="offset points")
    ax.set_xlim(0, xlim); ax.set_ylim(0, ylim)
    ax.set_xlabel("CAC ($)"); ax.set_ylabel("180-day gross profit per customer ($)")
    ax.set_title("Cost to acquire vs value of a customer\n(above the line makes money; bubble = spend)")
    fig.tight_layout(); fig.savefig(DOCS / "cac_vs_value.png"); plt.close(fig)


if __name__ == "__main__":
    roi_by_campaign(); payback_by_channel(); conversion_trend(); cac_vs_value()
    print("Charts written to", DOCS)
