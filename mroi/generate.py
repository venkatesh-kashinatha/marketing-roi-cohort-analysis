"""Generate a simulated marketing dataset: campaigns, daily spend, sign-ups and orders.

Real campaign spend joined to customer-level revenue isn't publicly available, so this module
simulates a direct-to-consumer brand with 13 campaigns across 7 channels. Each campaign has its
own costs, conversion behaviour, order values, margins and repeat-purchase habits, which is what
makes the analysis interesting: cheap clicks don't always mean cheap customers.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Campaign:
    campaign_id: str
    name: str
    channel: str
    objective: str
    start: str
    end: str | None        # None = runs to the end of the data
    daily_budget: float    # average daily spend in year one
    cpc: float             # cost per click
    ctr: float             # click-through rate (used to back out impressions)
    signup_rate: float     # sign-ups per click
    convert: float         # share of sign-ups who ever buy
    days_to_buy: float     # mean days from sign-up to first order
    aov: float             # average order value
    margin: float          # gross margin on each order
    churn: float           # chance a customer never orders again after each order
    days_between: float    # mean days between repeat orders
    months: tuple = ()     # active months only (empty = all year)
    year2_budget: float = 1.08   # budget multiplier from the second year
    convert_drift: float = 0.0   # yearly change in conversion (audience fatigue)


CAMPAIGNS = [
    Campaign("C01", "Search - Brand", "Paid Search", "Capture demand", "2024-01-01", None,
             90, 1.40, 0.08, 0.18, 0.38, 6, 78, 0.52, 0.38, 45),
    Campaign("C02", "Search - Generic", "Paid Search", "Prospecting", "2024-01-01", None,
             260, 1.80, 0.04, 0.12, 0.28, 12, 72, 0.50, 0.50, 55),
    Campaign("C03", "Search - Competitor", "Paid Search", "Prospecting", "2024-01-01", "2025-06-30",
             105, 3.40, 0.03, 0.08, 0.18, 16, 70, 0.50, 0.58, 60),
    Campaign("C04", "Social - Lookalike Prospecting", "Paid Social", "Prospecting", "2024-01-01", None,
             360, 1.10, 0.012, 0.09, 0.14, 20, 64, 0.48, 0.66, 65, year2_budget=1.30, convert_drift=-0.12),
    Campaign("C05", "Social - Retargeting", "Paid Social", "Retargeting", "2024-01-01", None,
             110, 1.10, 0.015, 0.14, 0.32, 7, 74, 0.50, 0.45, 50),
    Campaign("C06", "Social - Influencer Holiday", "Paid Social", "Seasonal push", "2024-10-01", None,
             560, 1.60, 0.010, 0.10, 0.20, 10, 82, 0.47, 0.60, 70, months=(10, 11, 12)),
    Campaign("C07", "Display - Programmatic", "Display", "Awareness", "2024-01-01", None,
             170, 0.45, 0.004, 0.025, 0.10, 24, 60, 0.48, 0.70, 70),
    Campaign("C08", "Affiliate - Coupon Sites", "Affiliate", "Prospecting", "2024-01-01", None,
             120, 0.70, 0.02, 0.15, 0.40, 4, 52, 0.30, 0.62, 60),
    Campaign("C09", "Affiliate - Content Partners", "Affiliate", "Prospecting", "2024-03-01", None,
             95, 1.00, 0.02, 0.12, 0.30, 9, 80, 0.52, 0.42, 50),
    Campaign("C10", "Email - Partner Newsletters", "Email", "Prospecting", "2024-01-01", None,
             60, 0.90, 0.03, 0.10, 0.24, 8, 70, 0.50, 0.48, 55),
    Campaign("C11", "Referral - Give $20 Get $20", "Referral", "Referral", "2024-01-01", None,
             80, 3.00, 0.10, 0.25, 0.30, 5, 76, 0.50, 0.35, 45),
    Campaign("C12", "Video - Product Demos", "Video", "Awareness", "2024-06-01", None,
             150, 0.90, 0.008, 0.08, 0.20, 14, 88, 0.50, 0.52, 60),
    Campaign("C13", "Social - Short Video Test", "Paid Social", "Test", "2025-09-01", None,
             140, 0.95, 0.010, 0.08, 0.15, 12, 66, 0.48, 0.60, 65),
]

FIRST_ORDER_DISCOUNT = 0.20  # welcome offer on every first order, so repeat orders drive payback
MONTH_FACTOR = np.array([0.85, 0.85, 0.95, 0.95, 1.0, 0.95, 0.90, 0.95, 1.0, 1.05, 1.25, 1.35])


def generate(start: str = "2024-01-01", end: str = "2025-12-31", seed: int = 42) -> dict[str, pd.DataFrame]:
    """Return the four raw tables: campaigns, daily_spend, signups, orders."""
    rng = np.random.default_rng(seed)
    days = pd.date_range(start, end, freq="D")
    first_year = days[0].year
    spend_parts, signup_parts, campaign_rows = [], [], []

    for c in CAMPAIGNS:
        c_end = min(pd.Timestamp(c.end), days[-1]) if c.end else days[-1]
        if pd.Timestamp(c.start) > days[-1]:
            continue
        active = (days >= pd.Timestamp(c.start)) & (days <= c_end)
        if c.months:
            active &= np.isin(days.month, c.months)
        d = days[active]
        campaign_rows.append({
            "campaign_id": c.campaign_id, "campaign_name": c.name, "channel": c.channel,
            "objective": c.objective, "start_date": max(pd.Timestamp(c.start), days[0]).date(),
            "end_date": c_end.date(),
        })
        if len(d) == 0:
            continue
        budget = c.daily_budget * np.where(d.year > first_year, c.year2_budget, 1.0)
        weekday = np.where(d.weekday >= 5, 0.85, 1.0)
        spend = budget * MONTH_FACTOR[d.month - 1] * weekday * rng.lognormal(-0.011, 0.15, len(d))
        clicks = rng.poisson(spend / c.cpc)
        impressions = np.round(clicks / c.ctr * rng.lognormal(0, 0.10, len(d))).astype(int)
        signups = rng.binomial(clicks, c.signup_rate)
        spend_parts.append(pd.DataFrame({
            "spend_date": d.date, "campaign_id": c.campaign_id, "spend": spend.round(2),
            "impressions": impressions, "clicks": clicks,
        }))
        signup_parts.append(pd.DataFrame({
            "signup_date": np.repeat(d.values, signups), "campaign_id": c.campaign_id,
        }))

    users = pd.concat(signup_parts, ignore_index=True)
    users = users.sort_values(["signup_date", "campaign_id"], kind="stable").reset_index(drop=True)
    users.insert(0, "user_id", [f"U{i:06d}" for i in range(1, len(users) + 1)])
    orders = _simulate_orders(users, days[0], days[-1], rng)
    users["signup_date"] = users["signup_date"].dt.date

    return {
        "campaigns": pd.DataFrame(campaign_rows),
        "daily_spend": pd.concat(spend_parts, ignore_index=True),
        "signups": users,
        "orders": orders,
    }


def _simulate_orders(users: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp,
                     rng: np.random.Generator) -> pd.DataFrame:
    """First purchase (with the welcome discount) after a random delay, then repeat purchases until churn."""
    by_id = {c.campaign_id: c for c in CAMPAIGNS}

    def param(name: str) -> np.ndarray:
        return users["campaign_id"].map({k: getattr(v, name) for k, v in by_id.items()}).to_numpy(dtype=float)

    signup = users["signup_date"].to_numpy(dtype="datetime64[D]")
    end_d = np.datetime64(end.date(), "D")
    years_in = (signup - np.datetime64(start.date(), "D")).astype(int) / 365.25
    convert = np.clip(param("convert") * (1 + param("convert_drift") * years_in), 0, 1)

    buys = rng.random(len(users)) < convert
    delay = np.floor(rng.exponential(param("days_to_buy"))).astype(int)
    first = signup + delay.astype("timedelta64[D]")
    who = np.nonzero(buys & (first <= end_d))[0]
    when = first[who]
    order_users, order_dates = [who], [when]

    churn, gap_mean = param("churn"), param("days_between")
    while len(who):
        stays = rng.random(len(who)) >= churn[who]
        gap = 3 + np.floor(rng.exponential(gap_mean[who])).astype(int)
        nxt = when + gap.astype("timedelta64[D]")
        keep = stays & (nxt <= end_d)
        who, when = who[keep], nxt[keep]
        order_users.append(who)
        order_dates.append(when)

    idx = np.concatenate(order_users)
    is_first = np.zeros(len(idx), dtype=bool)
    is_first[: len(order_users[0])] = True
    list_price = param("aov")[idx] * rng.lognormal(-0.06, 0.35, len(idx))
    cogs = list_price * (1 - param("margin")[idx]) * rng.lognormal(0, 0.05, len(idx))
    revenue = np.where(is_first, list_price * (1 - FIRST_ORDER_DISCOUNT), list_price)
    orders = pd.DataFrame({
        "user_id": users["user_id"].to_numpy()[idx],
        "order_date": np.concatenate(order_dates),
        "revenue": revenue.round(2),
        "cost_of_goods": cogs.round(2),
    }).sort_values(["order_date", "user_id"], kind="stable").reset_index(drop=True)
    orders.insert(0, "order_id", [f"O{i:07d}" for i in range(1, len(orders) + 1)])
    orders["order_date"] = pd.to_datetime(orders["order_date"]).dt.date
    return orders


def write_csvs(tables: dict[str, pd.DataFrame], out_dir: Path) -> dict[str, int]:
    out_dir.mkdir(parents=True, exist_ok=True)
    counts = {}
    for name, df in tables.items():
        df.to_csv(out_dir / f"{name}.csv", index=False)
        counts[name] = len(df)
    return counts
