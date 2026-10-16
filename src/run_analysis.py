"""Run every SQL query, save the results, draw the charts and write the findings.

    python src/run_analysis.py

Outputs (all in outputs/):
  <query_name>.csv      one CSV per file in sql/queries/
  figures/*.png         7 presentation-ready charts
  findings.md           auto-written findings, recommendations, caveats, resume bullet
  order_facts.csv.gz    order-level table the dashboard filters on
  meta.json             data-source flag (real vs sample) read by the dashboard
"""
from __future__ import annotations

import json
import math
import sqlite3
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "olist.db"
QUERIES = ROOT / "sql" / "queries"
OUT = ROOT / "outputs"
FIG = OUT / "figures"

IS_SAMPLE = (ROOT / "data" / "raw" / "SAMPLE_DATA.txt").exists()
SOURCE = ("SYNTHETIC SAMPLE DATA - pipeline test only, not real results" if IS_SAMPLE
          else "Source: Olist Brazilian E-Commerce public dataset (Kaggle), 2016-2018")
MIN_MONTH_ORDERS = 100   # the real data has a few near-empty months at both ends of the range

# validated categorical slots 1-3 + neutrals + one-hue sequential ramp
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
SURFACE, INK, INK2, MUTED, GRID, BASE = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]


# ----------------------------------------------------------------------------- helpers
def style() -> None:
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "text.color": INK, "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED,
        "axes.edgecolor": BASE, "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
        "xtick.labelsize": 9, "ytick.labelsize": 9,
    })


def mi(month: str) -> int:
    return int(month[:4]) * 12 + int(month[5:7])


def finish(fig, ax, title: str, subtitle: str, name: str) -> None:
    ax.set_title(title, loc="left", fontsize=13, fontweight="bold", color=INK, pad=26)
    ax.annotate(subtitle, xy=(0, 1), xycoords="axes fraction", xytext=(0, 7),
                textcoords="offset points", fontsize=9.5, color=INK2, va="bottom")
    fig.text(0.01, 0.01, SOURCE, fontsize=8, color=("#b3261e" if IS_SAMPLE else MUTED),
             ha="left", va="bottom")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(FIG / f"{name}.png", dpi=160)
    plt.close(fig)


def money(v: float) -> str:
    return f"R${v:,.0f}"


def run_queries(con: sqlite3.Connection) -> dict[str, pd.DataFrame]:
    results = {}
    for f in sorted(QUERIES.glob("*.sql")):
        df = pd.read_sql_query(f.read_text(), con)
        df.to_csv(OUT / f"{f.stem}.csv", index=False)
        results[f.stem] = df
        print(f"  {f.stem:42s} {len(df):>6,} rows")
    return results


# ----------------------------------------------------------------------------- charts
def chart_revenue(df: pd.DataFrame) -> None:
    d = df[df.orders >= MIN_MONTH_ORDERS].copy()
    x = pd.to_datetime(d.purchase_month + "-01")
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.plot(x, d.revenue / 1e3, color=BLUE, lw=2, label="Monthly revenue")
    ax.plot(x, d.revenue_3m_avg / 1e3, color=MUTED, lw=1.6, ls="--", label="3-month average")
    pk = d.loc[d.revenue.idxmax()]
    px = pd.to_datetime(pk.purchase_month + "-01")
    ax.scatter([px], [pk.revenue / 1e3], s=45, color=BLUE, zorder=3, edgecolor=SURFACE, linewidth=2)
    ax.annotate(f"Peak {pk.purchase_month}: {money(pk.revenue / 1e3)}k", xy=(px, pk.revenue / 1e3),
                xytext=(-10, 10), textcoords="offset points", ha="right", fontsize=9, color=INK2)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"R${v:,.0f}k"))
    ax.set_ylim(0, d.revenue.max() / 1e3 * 1.12)
    ax.legend(frameon=False, loc="upper left")
    first, last = d.iloc[0], d.iloc[-1]
    finish(fig, ax, f"Monthly revenue grew {last.revenue / first.revenue:.1f}x from "
                    f"{first.purchase_month} to {last.purchase_month}",
           f"Revenue = item prices of valid orders (freight excluded); months under "
           f"{MIN_MONTH_ORDERS} orders hidden", "01_revenue_trend")


def chart_pareto(df: pd.DataFrame) -> None:
    top = df.head(12).iloc[::-1]
    fig, ax = plt.subplots(figsize=(9, 5.2))
    ax.barh(top.category.str.replace("_", " "), top.revenue_share_pct, color=BLUE, height=0.62)
    for y, (s, c) in enumerate(zip(top.revenue_share_pct, top.cumulative_share_pct)):
        ax.text(s + 0.2, y, f"{s:.1f}%   (cumulative {c:.0f}%)", va="center", fontsize=9, color=INK2)
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, top.revenue_share_pct.max() * 1.55)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
    n80 = int((df.cumulative_share_pct < 80).sum()) + 1
    finish(fig, ax, f"{n80} of {len(df)} categories generate 80% of revenue",
           "Share of revenue by product category (top 12 shown)", "02_category_pareto")


def chart_late_reviews(df: pd.DataFrame) -> None:
    ok = df.delivery_bucket.str[0].isin(list("12"))
    labels = [textwrap.fill(b.split(". ", 1)[1], 14) for b in df.delivery_bucket]
    fig, ax = plt.subplots(figsize=(9, 4.8))
    bars = ax.bar(labels, df.avg_review, color=[BLUE if o else ORANGE for o in ok], width=0.62)
    for b, v, n in zip(bars, df.avg_review, df.orders):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.06, f"{v:.2f}", ha="center", fontsize=10, color=INK)
        ax.text(b.get_x() + b.get_width() / 2, 0.12, f"n={n:,}", ha="center", fontsize=8, color=SURFACE)
    ax.set_ylim(0, 5.3)
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("Average review score (1-5)")
    ax.legend(handles=[Patch(color=BLUE, label="On time or early"), Patch(color=ORANGE, label="Late")],
              frameon=False, loc="upper right")
    on = np.average(df.avg_review[ok], weights=df.orders[ok])
    lt = np.average(df.avg_review[~ok], weights=df.orders[~ok])
    finish(fig, ax, f"Late orders score {lt:.1f} on average vs {on:.1f} for on-time orders",
           "Average review score by delivery timing vs the promised date", "03_late_vs_reviews")


def chart_cohort(df: pd.DataFrame, last_month: str) -> None:
    cohorts = sorted(c for c in df.cohort_month.unique()
                     if c >= "2017-01" and mi(c) + 6 <= mi(last_month))
    if len(cohorts) < 2:
        print("  (cohort chart skipped: fewer than 2 cohorts with 6 months of follow-up)")
        return
    lookup = df.set_index(["cohort_month", "month_number"]).retention_pct
    mat = np.array([[lookup.get((c, m), 0.0) for m in range(1, 7)] for c in cohorts])
    vmax = max(float(mat.max()), 0.5)
    fig, ax = plt.subplots(figsize=(8.5, 0.34 * len(cohorts) + 2.6))
    ax.imshow(mat, cmap=LinearSegmentedColormap.from_list("seq", SEQ), aspect="auto", vmin=0, vmax=vmax)
    for r in range(mat.shape[0]):
        for c in range(mat.shape[1]):
            ax.text(c, r, f"{mat[r, c]:.1f}", ha="center", va="center", fontsize=8,
                    color=SURFACE if mat[r, c] > 0.55 * vmax else INK)
    ax.set_xticks(range(6), [f"Month +{m}" for m in range(1, 7)])
    size = df.drop_duplicates("cohort_month").set_index("cohort_month").cohort_customers
    ax.set_yticks(range(len(cohorts)), [f"{c}  (n={int(size[c]):,})" for c in cohorts])
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)
    finish(fig, ax, f"Retention is very low: only {mat[:, 0].mean():.1f}% of a cohort buys again next month",
           "% of each monthly acquisition cohort that places another order, 1-6 months later",
           "04_cohort_retention")


def chart_states(df: pd.DataFrame, national_late: float) -> None:
    top = df.head(10).iloc[::-1]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.barh(top.customer_state, top.late_pct, color=BLUE, height=0.62)
    for y, (v, n) in enumerate(zip(top.late_pct, top.delivered_orders)):
        ax.text(v + 0.3, y, f"{v:.1f}%   ({n:,} orders)", va="center", fontsize=9, color=INK2)
    ax.axvline(national_late, color=MUTED, lw=1.5, ls="--", label=f"National average ({national_late:.1f}%)")
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, top.late_pct.max() * 1.4)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.legend(frameon=False, loc="lower right")
    worst = df.iloc[0]
    finish(fig, ax, f"{worst.customer_state} has the highest late-delivery rate ({worst.late_pct:.0f}% vs "
                    f"{national_late:.0f}% nationally)",
           "% of delivered orders arriving after the promised date (states with 30+ orders)",
           "05_late_by_state")


def headline_segment(df: pd.DataFrame) -> pd.Series:
    """Segment to headline: the biggest revenue holder that over-indexes vs its customer share."""
    big = df[df.pct_customers >= 1].copy()
    big["ratio"] = big.pct_revenue / big.pct_customers
    over = big[big.ratio > 1.2]
    return over.loc[over.pct_revenue.idxmax()] if len(over) else big.loc[big.ratio.idxmax()]


def chart_rfm(df: pd.DataFrame) -> None:
    d = df.sort_values("pct_revenue")
    y = np.arange(len(d))
    h = 0.38
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.barh(y + h / 2, d.pct_customers, height=h, color=BLUE, label="% of customers")
    ax.barh(y - h / 2, d.pct_revenue, height=h, color=ORANGE, label="% of revenue")
    for yy, a, b in zip(y, d.pct_customers, d.pct_revenue):
        ax.text(a + 0.4, yy + h / 2, f"{a:.1f}%", va="center", fontsize=8.5, color=INK2)
        ax.text(b + 0.4, yy - h / 2, f"{b:.1f}%", va="center", fontsize=8.5, color=INK2)
    ax.set_yticks(y, d.segment)
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, max(d.pct_customers.max(), d.pct_revenue.max()) * 1.18)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.legend(frameon=False, loc="lower right")
    best = headline_segment(df)
    finish(fig, ax, f"{best.segment}: {best.pct_customers:.0f}% of customers, {best.pct_revenue:.0f}% of revenue",
           "RFM segments: share of customers vs share of revenue", "06_rfm_segments")


def chart_repeat(df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.8))
    labels = [f"{int(s)} star" for s in df.first_order_review]
    bars = ax.bar(labels, df.repeat_rate_pct, color=BLUE, width=0.6)
    for b, v, n in zip(bars, df.repeat_rate_pct, df.customers):
        ax.text(b.get_x() + b.get_width() / 2, v + df.repeat_rate_pct.max() * 0.02, f"{v:.1f}%",
                ha="center", fontsize=10, color=INK)
        ax.text(b.get_x() + b.get_width() / 2, df.repeat_rate_pct.max() * 0.03, f"n={n:,}",
                ha="center", fontsize=8, color=SURFACE)
    ax.set_ylim(0, df.repeat_rate_pct.max() * 1.18)
    ax.grid(axis="x", visible=False)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.set_xlabel("Review score on the customer's FIRST order")
    r1 = float(df.loc[df.first_order_review == 1, "repeat_rate_pct"].iloc[0]) if (df.first_order_review == 1).any() else 0
    r5 = float(df.loc[df.first_order_review == 5, "repeat_rate_pct"].iloc[0]) if (df.first_order_review == 5).any() else 0
    title = (f"Customers whose first order got 5 stars are {r5 / r1:.1f}x as likely to return as 1-star customers"
             if r1 > 0 else "Repeat-purchase rate by first-order review score")
    finish(fig, ax, title, "% of customers who placed at least one more order", "07_first_order_vs_repeat")


# ----------------------------------------------------------------------------- statistics
def review_gap(delivered: pd.DataFrame) -> dict | None:
    late = delivered.loc[delivered.is_late == 1, "review_score"]
    ok = delivered.loc[delivered.is_late == 0, "review_score"]
    if len(late) < 2 or len(ok) < 2:
        return None
    diff = ok.mean() - late.mean()
    se = math.sqrt(ok.var(ddof=1) / len(ok) + late.var(ddof=1) / len(late))
    return dict(on_time=ok.mean(), late=late.mean(), n_on_time=len(ok), n_late=len(late),
                diff=diff, lo=diff - 1.96 * se, hi=diff + 1.96 * se)


def repeat_gap(r12: pd.DataFrame) -> dict | None:
    lo, hi = r12[r12.first_order_review <= 2], r12[r12.first_order_review >= 4]
    n1, n2 = lo.customers.sum(), hi.customers.sum()
    if n1 == 0 or n2 == 0:
        return None
    p1 = (lo.customers * lo.repeat_rate_pct / 100).sum() / n1
    p2 = (hi.customers * hi.repeat_rate_pct / 100).sum() / n2
    se = math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    d = p2 - p1
    return dict(p_low=p1 * 100, p_high=p2 * 100, n_low=int(n1), n_high=int(n2),
                diff=d * 100, lo=(d - 1.96 * se) * 100, hi=(d + 1.96 * se) * 100)


# ----------------------------------------------------------------------------- findings
def write_findings(R: dict, valid: pd.DataFrame, delivered: pd.DataFrame, repeat_rate: float,
                   nat_freight_pct: float) -> str:
    kpi = R["01_kpi_summary"].iloc[0]
    monthly, cat = R["02_monthly_revenue_growth"], R["03_category_pareto"]
    state, bucket = R["04_delivery_by_state"], R["05_late_delivery_vs_reviews"]
    rfm, sellers, pay = R["07_rfm_segments"], R["08_seller_scorecard"], R["09_payment_mix"]
    freight, r12 = R["11_freight_burden_by_state"], R["12_first_order_experience_vs_repeat"]
    rg, pg = review_gap(delivered), repeat_gap(r12)
    first_m, last_m = valid.purchase_month.min(), valid.purchase_month.max()

    L: list[str] = ["# Findings: Olist e-commerce analysis", ""]
    if IS_SAMPLE:
        L += ["> **WARNING: these numbers come from SYNTHETIC SAMPLE DATA.** They only prove the pipeline "
              "runs. Re-run on the real Kaggle data before quoting anything.", ""]
    L += ["## Headline numbers",
          f"- **{int(kpi.orders):,}** valid orders from **{int(kpi.unique_customers):,}** unique customers, "
          f"{first_m} to {last_m}",
          f"- GMV **{money(kpi.gmv)}**, average order value **{money(kpi.avg_order_value)}**",
          f"- **{kpi.late_pct:.1f}%** of delivered orders arrived late; average review **{kpi.avg_review_score:.2f}/5**",
          ""]

    L += ["## What the data says"]
    n = 1
    if len(cat):
        n80 = int((cat.cumulative_share_pct < 80).sum()) + 1
        names = ", ".join(cat.head(3).category.str.replace("_", " "))
        L.append(f"{n}. **Revenue is concentrated.** {n80} of {len(cat)} categories generate 80% of revenue; "
                 f"the top three are {names}.")
        n += 1
    if rg:
        neg_late = bucket.iloc[-1]
        ok_b = bucket[bucket.delivery_bucket.str[0].isin(list("12"))]
        neg_ok = np.average(ok_b.pct_negative_reviews, weights=ok_b.orders) if len(ok_b) else float("nan")
        L.append(f"{n}. **Late delivery is associated with much lower satisfaction.** On-time orders average "
                 f"{rg['on_time']:.2f} stars vs {rg['late']:.2f} for late orders (gap {rg['diff']:.2f}, "
                 f"95% CI [{rg['lo']:.2f}, {rg['hi']:.2f}]). In the worst bucket ({neg_late.delivery_bucket[3:]}), "
                 f"{neg_late.pct_negative_reviews:.0f}% of reviews are 1-2 stars vs {neg_ok:.0f}% for on-time orders.")
        n += 1
    if len(state):
        w = state.iloc[0]
        early = w.avg_days_vs_estimate < 0
        L.append(f"{n}. **Delivery problems are geographic.** {w.customer_state} has the highest late rate "
                 f"({w.late_pct:.1f}% vs {kpi.late_pct:.1f}% overall); on average orders there arrive "
                 f"{abs(w.avg_days_vs_estimate):.1f} days {'earlier' if early else 'later'} than promised"
                 f"{', so the problem is the late tail, not the average' if early else ''}.")
        n += 1
    if pg:
        if pg["lo"] > 0:
            L.append(f"{n}. **Customers rarely come back, and first impressions matter.** Only {repeat_rate:.1f}% "
                     f"of customers ordered more than once. Customers whose first order got 1-2 stars repeat at "
                     f"{pg['p_low']:.1f}% vs {pg['p_high']:.1f}% for 4-5 stars (difference {pg['diff']:.1f} pts, "
                     f"95% CI [{pg['lo']:.1f}, {pg['hi']:.1f}]).")
        else:
            L.append(f"{n}. **Customers rarely come back, and a good first review does not change that.** Only "
                     f"{repeat_rate:.1f}% of customers ordered more than once. Repeat rates are "
                     f"{pg['p_low']:.1f}% after a 1-2 star first order vs {pg['p_high']:.1f}% after 4-5 stars "
                     f"(difference {pg['diff']:.1f} pts, 95% CI [{pg['lo']:.1f}, {pg['hi']:.1f}], which includes "
                     f"zero), so first-order satisfaction does not explain who returns. Low retention looks "
                     f"structural, not a service-quality problem.")
        n += 1
    if len(rfm):
        b = headline_segment(rfm)
        L.append(f"{n}. **RFM segmentation.** The '{b.segment}' segment is {b.pct_customers:.1f}% of customers but "
                 f"{b.pct_revenue:.1f}% of revenue (average spend {money(b.avg_spend)}).")
        n += 1
    fix = sellers[sellers.action_flag.str.startswith("Fix first")] if len(sellers) else sellers
    if len(sellers):
        share = 100 * fix.revenue.sum() / sellers.revenue.sum()
        L.append(f"{n}. **A short list of sellers carries a lot of risk.** Of {len(sellers)} sellers with "
                 f"20+ delivered orders, {len(fix)} are in the top revenue quartile with poor reviews or "
                 f"frequent late deliveries; they account for {share:.0f}% of scored seller revenue.")
        n += 1
    if len(pay):
        cc = pay[pay.payment_type == "credit_card"]
        if len(cc):
            L.append(f"{n}. **Payments.** Credit cards are {cc.value_share_pct.iloc[0]:.0f}% of payment value "
                     f"with {cc.avg_installments.iloc[0]:.1f} instalments on average.")
            n += 1
    if len(freight):
        f0 = freight.iloc[0]
        L.append(f"{n}. **Shipping is a bigger burden far from the hub.** Freight is {f0.freight_pct_of_item_value:.0f}% "
                 f"of item value in {f0.customer_state} vs {nat_freight_pct:.0f}% across all orders.")
        n += 1

    L += ["", "## Recommendations (with illustrative sizing)"]
    if len(state):
        worst5 = state.head(5)
        excess = sum(max(0.0, r.late_pct - kpi.late_pct) / 100 * r.delivered_orders for r in worst5.itertuples())
        L.append(f"1. **Fix the delivery promise in the five worst states** ({', '.join(worst5.customer_state)}): "
                 f"bringing them to the national late rate would remove about **{excess:,.0f}** late deliveries "
                 f"over the period, via better carriers or more realistic estimates.")
    if len(sellers):
        L.append(f"2. **Run a seller-performance programme** starting with the {len(fix)} flagged sellers "
                 f"(see `outputs/08_seller_scorecard.csv`): delivery SLAs, coaching, or reduced search "
                 f"ranking until they improve.")
    if pg and pg["lo"] > 0:
        extra = pg["n_low"] * max(0.0, pg["p_high"] - pg["p_low"]) / 100
        L.append(f"3. **Recover bad first experiences.** {pg['n_low']:,} customers had a 1-2 star first order. If "
                 f"proactive outreach lifted their repeat rate to that of happy customers, that is about "
                 f"**{extra:,.0f}** extra repeat customers, roughly **{money(extra * kpi.avg_order_value)}** "
                 f"(an upper bound: it assumes the gap is causal).")
    elif pg:
        L.append(f"3. **Treat retention as its own problem.** Only {repeat_rate:.1f}% of customers return, and "
                 f"review scores do not predict who does, so fixing service alone will not move repeat rate. "
                 f"Test a second-purchase incentive (voucher or reminder) on a random half of new customers "
                 f"and compare repeat rates; this is an A/B test, not something this data can size.")

    L += ["", "## Caveats",
          "- These are associations, not proven causes: unhappy customers may differ in ways the data does not capture.",
          "- Review scores exist only for customers who responded; non-response bias is possible.",
          "- Customer identity is `customer_unique_id`; one person using different accounts would look like two customers.",
          "- Revenue excludes freight and cancelled/unavailable orders; retention windows near the end of the data are incomplete.",
          ""]

    if rg and pg:
        if pg["lo"] > 0:
            tail = (f"and that customers with a poor first order repeat {pg['p_low']:.1f}% vs "
                    f"{pg['p_high']:.1f}%; ")
        else:
            tail = (f"and that only {repeat_rate:.1f}% of customers ever reorder regardless of first-order "
                    f"satisfaction; ")
        L += ["## Resume bullet (check every number against outputs/ before using)",
              f"> Analysed {int(kpi.orders):,} marketplace orders ({money(kpi.gmv)} GMV) with SQL (CTEs, window "
              f"functions, cohort and RFM analysis) and Python; showed late deliveries cut average review scores "
              f"from {rg['on_time']:.1f} to {rg['late']:.1f} {tail}"
              f"shipped a Streamlit dashboard and a prioritised fix list for {len(fix)} high-risk sellers.", ""]

    text = "\n".join(L)
    (OUT / "findings.md").write_text(text)
    return text


# ----------------------------------------------------------------------------- main
def safe(fn, *args) -> None:
    try:
        fn(*args)
    except Exception as e:   # one bad chart should not stop the whole run
        print(f"  WARNING: {fn.__name__} skipped ({type(e).__name__}: {e})")


def main() -> None:
    if not DB.exists():
        raise SystemExit("Database not found. Run: python src/load_db.py")
    OUT.mkdir(exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    style()
    con = sqlite3.connect(DB)

    print("Running SQL queries:")
    R = run_queries(con)

    valid = pd.read_sql_query("SELECT * FROM order_facts WHERE order_status NOT IN "
                              "('canceled','unavailable') AND n_items > 0", con)
    delivered = pd.read_sql_query("SELECT * FROM order_facts WHERE order_status = 'delivered' AND "
                                  "delivered_ts IS NOT NULL AND review_score IS NOT NULL", con)
    cols = ("customer_unique_id, customer_state, order_status, purchase_month, purchase_ts, n_items, "
            "items_value, freight_value, review_score, delivery_days, days_vs_estimate, is_late")
    of = pd.read_sql_query(f"SELECT {cols} FROM order_facts", con).round(3)
    of.to_csv(OUT / "order_facts.csv.gz", index=False, compression="gzip")
    con.close()

    kpi = R["01_kpi_summary"].iloc[0]
    repeat_rate = 100 * (valid.groupby("customer_unique_id").size() > 1).mean()
    nat_freight = 100 * valid.freight_value.sum() / valid.items_value.sum()

    print("Drawing charts:")
    safe(chart_revenue, R["02_monthly_revenue_growth"])
    safe(chart_pareto, R["03_category_pareto"])
    safe(chart_late_reviews, R["05_late_delivery_vs_reviews"])
    safe(chart_cohort, R["06_cohort_retention"], valid.purchase_month.max())
    safe(chart_states, R["04_delivery_by_state"], float(kpi.late_pct))
    safe(chart_rfm, R["07_rfm_segments"])
    safe(chart_repeat, R["12_first_order_experience_vs_repeat"])

    text = write_findings(R, valid, delivered, repeat_rate, nat_freight)
    (OUT / "meta.json").write_text(json.dumps({"is_sample": IS_SAMPLE, "source": SOURCE,
                                               "repeat_rate_pct": round(repeat_rate, 2)}))
    print("\n" + text)
    print(f"\nDone. Charts in {FIG}. NEXT: streamlit run dashboard/app.py")


if __name__ == "__main__":
    main()