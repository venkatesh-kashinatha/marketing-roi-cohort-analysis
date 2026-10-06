"""Decision rules, the default budget scenario and plain-English findings."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .config import CUT_CHANGE, CUT_ROI, MIN_SIGNUPS, SCALE_CHANGE, SCALE_ROI

TOO_EARLY, SCALE, OPTIMIZE, CUT = "Too early to judge", "Scale", "Optimize", "Cut or rework"


def day(ts) -> str:
    ts = pd.Timestamp(ts)
    return f"{ts:%b} {ts.day}, {ts.year}"


def money(x: float) -> str:
    sign = "-" if x < 0 else ""
    x = abs(x)
    if x >= 1_000_000:
        return f"{sign}${x / 1_000_000:.2f}M"
    if x >= 10_000:
        return f"{sign}${x / 1_000:.0f}K"
    if x >= 1_000:
        return f"{sign}${x / 1_000:.1f}K"
    return f"{sign}${x:,.0f}"


def pct(x: float, signed: bool = False) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "n/a"
    return f"{x:+.0%}" if signed else f"{x:.0%}"


def action(row: pd.Series) -> str:
    """Same rule as the Action column in Excel."""
    if row["signups"] < MIN_SIGNUPS or not row["spend"] or pd.isna(row["roi"]):
        return TOO_EARLY
    if row["roi"] >= SCALE_ROI:
        return SCALE
    if row["roi"] >= CUT_ROI or not pd.isna(row["payback_months"]):
        return OPTIMIZE  # losing money at 180 days but still pays back within 12 months
    return CUT


def add_actions(scorecard: pd.DataFrame) -> pd.DataFrame:
    sc = scorecard.copy()
    sc["action"] = sc.apply(action, axis=1)
    sc["gp_per_customer"] = sc["gross_profit"] / sc["customers"].replace(0, np.nan)
    order = {SCALE: 0, OPTIMIZE: 1, CUT: 2, TOO_EARLY: 3}
    sc["_rank"] = sc["action"].map(order)
    sc = sc.sort_values(["_rank", "roi"], ascending=[True, False]).drop(columns="_rank")
    return sc.reset_index(drop=True)


def default_changes(sc: pd.DataFrame) -> pd.Series:
    """Starting budget changes for the scenario: halve the cuts, grow the winners by half."""
    return sc["action"].map({SCALE: SCALE_CHANGE, CUT: CUT_CHANGE}).fillna(0.0)


def scenario(sc: pd.DataFrame, changes: pd.Series) -> dict:
    """Annual effect of the budget changes, assuming each campaign's CAC and value hold."""
    judged = sc["cac"].notna() & sc["gp_per_customer"].notna()
    current = sc["current_annual_spend"]
    new = current * (1 + changes)
    customers_now = (current / sc["cac"]).where(judged, 0.0)
    customers_new = (new / sc["cac"]).where(judged, 0.0)
    gp_now = customers_now * sc["gp_per_customer"].fillna(0)
    gp_new = customers_new * sc["gp_per_customer"].fillna(0)
    return {
        "spend_change": float((new - current).sum()),
        "extra_customers": float((customers_new - customers_now).sum()),
        "extra_gross_profit": float((gp_new - gp_now).sum()),
        "net_gain": float(((gp_new - new) - (gp_now - current))[judged].sum()),
    }


def build_findings(sc: pd.DataFrame, cohorts: pd.DataFrame, payback: pd.DataFrame, p: dict) -> list[str]:
    judged = sc[sc["action"] != TOO_EARLY]
    if judged.empty or judged["customers"].sum() == 0:
        return [f"No campaign has {MIN_SIGNUPS:,} sign-ups with a full {p['horizon']} days of history yet, "
                "so there's nothing to judge. Add more data or lower the horizon."]
    spend, customers = judged["spend"].sum(), judged["customers"].sum()
    gp, revenue = judged["gross_profit"].sum(), judged["revenue"].sum()
    window = f"{day(p['first_signup'])} to {day(p['mature_cutoff'])}"
    lines = [
        f"Sign-ups from {window}: {money(spend)} of spend brought {customers:,.0f} customers within "
        f"{p['horizon']} days at a blended CAC of {money(spend / customers)}, for a "
        f"{pct((gp - spend) / spend, signed=True)} ROI on {p['horizon']}-day gross profit "
        f"({revenue / spend:.2f}x ROAS)."
    ]

    best = judged.loc[judged["roi"].idxmax()]
    worst = judged.loc[judged["roi"].idxmin()]
    lines.append(f"{best['campaign_name']} is the strongest campaign ({pct(best['roi'], True)} ROI at a "
                 f"{money(best['cac'])} CAC); {worst['campaign_name']} is the weakest "
                 f"({pct(worst['roi'], True)} ROI at a {money(worst['cac'])} CAC).")

    biggest = judged.loc[judged["spend"].idxmax()]
    lines.append(f"The largest budget line, {biggest['campaign_name']} ({biggest['spend'] / spend:.0%} of measured "
                 f"spend), returns {pct(biggest['roi'], True)} at {p['horizon']} days.")

    by_channel = (payback.groupby(["channel", "period"])[["gross_profit_cum", "spend"]].sum()
                  .assign(ratio=lambda d: d["gross_profit_cum"] / d["spend"]).reset_index())
    paid = by_channel[by_channel["ratio"] >= 1].groupby("channel")["period"].min() + 1
    never = sorted(set(by_channel["channel"]) - set(paid.index))
    if len(paid):
        fastest = sorted(paid[paid == paid.min()].index)
        verb = "pay" if len(fastest) > 1 else "pays"
        text = f"{' and '.join(fastest)} {verb} back fastest (within {int(paid.min()) * 30} days)"
        if never:
            text += f"; {' and '.join(never)} {'do' if len(never) > 1 else 'does'} not pay back within 12 months"
        lines.append(text + ".")

    conv = cohorts[cohorts["period"] == 0]
    months = sorted(conv["cohort_month"].unique())
    if len(months) >= 12:
        early, late = months[:6], months[-6:]

        def rates(window):
            part = conv[conv["cohort_month"].isin(window)].groupby("channel")[["customers_cum", "signups"]].sum()
            share = part["signups"] / part["signups"].sum()
            rate = part["customers_cum"] / part["signups"]
            return part["customers_cum"].sum() / part["signups"].sum(), share, rate

        a, share_a, rate_a = rates(early)
        b, share_b, rate_b = rates(late)
        # Mix + rate split: a channel moves the blended rate by changing its share (measured against
        # the old average) and by changing its own rate. The contributions add up to b - a exactly.
        channels = share_a.index.union(share_b.index)
        sa, sb = share_a.reindex(channels).fillna(0), share_b.reindex(channels).fillna(0)
        ra = rate_a.reindex(channels).fillna(rate_b.reindex(channels))
        rb = rate_b.reindex(channels).fillna(ra)
        contribution = (sb - sa) * (ra - a) + sb * (rb - ra)
        driver = contribution.idxmin() if b < a else contribution.idxmax()
        lines.append(
            f"30-day conversion {'fell' if b < a else 'rose'} from {a:.1%} for the first six cohorts "
            f"({pd.Timestamp(early[0]):%b %Y}–{pd.Timestamp(early[-1]):%b %Y}) to {b:.1%} for the latest six "
            f"({pd.Timestamp(late[0]):%b %Y}–{pd.Timestamp(late[-1]):%b %Y}). {driver} explains most of the change: "
            f"its share of sign-ups went from {share_a.get(driver, 0):.0%} to {share_b.get(driver, 0):.0%} and its "
            f"30-day conversion from {rate_a.get(driver, float('nan')):.1%} to {rate_b.get(driver, float('nan')):.1%}."
        )

    for _, row in sc[sc["action"] == TOO_EARLY].iterrows():
        ready = pd.Timestamp(row["start_date"]) + pd.Timedelta(days=p["horizon"] - 1)
        lines.append(f"{row['campaign_name']} started on {day(row['start_date'])}, so it's too new to judge. "
                     f"Its first sign-ups reach {p['horizon']} days of history on {day(ready)}.")

    cuts = sc[sc["action"] == CUT]
    scales = sc[sc["action"] == SCALE]
    if len(cuts) and len(scales):
        s = scenario(sc, default_changes(sc))
        lines.append(
            f"Recommendation: halve the {len(cuts)} campaigns marked 'Cut or rework' and grow the {len(scales)} "
            f"marked 'Scale' by {SCALE_CHANGE:.0%}. If CAC holds, annual spend changes by "
            f"{money(s['spend_change'])} and {p['horizon']}-day gross profit after spend improves by "
            f"{money(s['net_gain'])} a year. Test the increases in steps, because CAC usually rises as "
            f"campaigns scale."
        )
    return lines
