"""Streamlit dashboard for the Olist e-commerce analysis.

    streamlit run dashboard/app.py

Reads only the pre-computed files in outputs/, so it deploys without the raw data.
The sidebar filters drive the Overview and Delivery tabs (computed live from
outputs/order_facts.csv.gz); the other tabs show full-dataset SQL results.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

OUT = Path(__file__).resolve().parents[1] / "outputs"

# validated categorical slots 1-3, neutral, one-hue sequential ramp
BLUE, ORANGE, AQUA, MUTED = "#2a78d6", "#eb6834", "#1baf7a", "#898781"
SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
BUCKETS = ["7+ days early", "On time (0-7 days early)", "1-3 days late", "4-7 days late", "8+ days late"]
INVALID = ("canceled", "unavailable")
MIN_MONTH_ORDERS = 100

st.set_page_config(page_title="Olist E-commerce Analytics", page_icon=":package:", layout="wide")


@st.cache_data
def load() -> dict | None:
    needed = ["order_facts.csv.gz", "meta.json", "findings.md"]
    if any(not (OUT / n).exists() for n in needed):
        return None
    d = {p.stem: pd.read_csv(p) for p in OUT.glob("*.csv")}
    d["order_facts"] = pd.read_csv(OUT / "order_facts.csv.gz")
    d["meta"] = json.loads((OUT / "meta.json").read_text())
    d["findings"] = (OUT / "findings.md").read_text()
    return d


def mi(month: str) -> int:
    return int(month[:4]) * 12 + int(month[5:7])


def money(v: float) -> str:
    return f"R${v:,.0f}"


def show(fig, height: int = 360) -> None:
    fig.update_layout(height=height, margin=dict(l=0, r=10, t=10, b=0), legend_title_text="")
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="rgba(137,135,129,0.25)")
    st.plotly_chart(fig, width="stretch")


def heading(title: str, note: str = "") -> None:
    st.markdown(f"**{title}**")
    if note:
        st.caption(note)


D = load()
if D is None:
    st.error("No analysis outputs found. Run the pipeline first:")
    st.code("python src/load_db.py\npython src/run_analysis.py", language="bash")
    st.stop()

st.title("Olist E-commerce: sales, delivery and customer analysis")
if D["meta"]["is_sample"]:
    st.warning("Showing SYNTHETIC SAMPLE DATA. These numbers only prove the pipeline works; "
               "run it on the real Olist data before drawing conclusions.")
st.caption(D["meta"]["source"])

# ------------------------------------------------------------------ sidebar filters
of = D["order_facts"]
counts = of.groupby("purchase_month").size()
months = sorted(counts.index)
good = [m for m in months if counts[m] >= MIN_MONTH_ORDERS] or months
with st.sidebar:
    st.header("Filters")
    lo, hi = st.select_slider("Purchase months", options=months, value=(good[0], good[-1]))
    sel = st.multiselect("Customer state (empty = all)", sorted(of.customer_state.unique()))
    st.caption("Filters apply to the Overview and Delivery tabs.")

f = of[(of.purchase_month >= lo) & (of.purchase_month <= hi)]
if sel:
    f = f[f.customer_state.isin(sel)]
valid = f[~f.order_status.isin(INVALID) & (f.n_items > 0)]
deliv = f[(f.order_status == "delivered") & f.days_vs_estimate.notna()]
if valid.empty:
    st.info("No orders match these filters.")
    st.stop()

tabs = st.tabs(["Overview", "Delivery and reviews", "Customers", "Sellers and categories",
                "Findings", "Data quality and method"])

# ------------------------------------------------------------------ overview
with tabs[0]:
    gmv = valid.items_value.sum()
    c = st.columns(5)
    c[0].metric("Orders", f"{len(valid):,}")
    c[1].metric("Unique customers", f"{valid.customer_unique_id.nunique():,}")
    c[2].metric("Revenue (GMV)", money(gmv))
    c[3].metric("Avg order value", money(gmv / len(valid)))
    c[4].metric("Avg review", f"{valid.review_score.mean():.2f} / 5")

    left, right = st.columns([3, 2])
    with left:
        heading("Monthly revenue", "Item prices of valid orders; freight and cancelled orders excluded")
        m = valid.groupby("purchase_month", as_index=False).agg(revenue=("items_value", "sum"))
        fig = px.line(m, x="purchase_month", y="revenue", markers=True, color_discrete_sequence=[BLUE])
        fig.update_traces(line_width=3, hovertemplate="%{x}: R$%{y:,.0f}<extra></extra>")
        fig.update_yaxes(tickprefix="R$", tickformat=",.0f", title=None, rangemode="tozero")
        fig.update_xaxes(title=None)
        show(fig)
    with right:
        heading("Order status", "Share of all orders (not affected by filters)")
        s = D["10_order_status_funnel"]
        fig = px.bar(s, x="orders", y="order_status", orientation="h", text="pct_of_orders",
                     color_discrete_sequence=[BLUE])
        fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig.update_yaxes(autorange="reversed", title=None)
        fig.update_xaxes(title=None)
        show(fig)

# ------------------------------------------------------------------ delivery
with tabs[1]:
    st.caption("A late order is one delivered on a later calendar date than the promised date.")
    late_nat = deliv.is_late.mean() * 100
    left, right = st.columns(2)
    with left:
        heading("Late-delivery rate by state", f"% of delivered orders arriving late; overall {late_nat:.1f}%")
        g = (deliv.groupby("customer_state")
             .agg(orders=("is_late", "size"), late_pct=("is_late", lambda s: s.mean() * 100),
                  avg_review=("review_score", "mean")).reset_index())
        g = g[g.orders >= (1 if sel else 30)].sort_values("late_pct", ascending=False).head(12)
        if g.empty:
            st.info("Not enough delivered orders for this selection.")
        else:
            fig = px.bar(g.iloc[::-1], x="late_pct", y="customer_state", orientation="h",
                         hover_data={"orders": ":,", "avg_review": ":.2f", "late_pct": ":.1f"},
                         color_discrete_sequence=[BLUE])
            fig.add_vline(x=late_nat, line_dash="dash", line_color=MUTED,
                          annotation_text=f"overall {late_nat:.1f}%")
            fig.update_xaxes(ticksuffix="%", title=None)
            fig.update_yaxes(title=None)
            show(fig)
    with right:
        heading("Review score by delivery timing", "Average review vs the promised date")
        dd = deliv.dropna(subset=["review_score"]).copy()
        dd["bucket"] = pd.cut(dd.days_vs_estimate, [-float("inf"), -7, 0, 3, 7, float("inf")], labels=BUCKETS)
        b = (dd.groupby("bucket", observed=False)
             .agg(orders=("review_score", "size"), avg_review=("review_score", "mean")).reset_index())
        b["bucket"] = b.bucket.astype(str)
        b["Timing"] = b.bucket.map(lambda x: "Late" if x.endswith("late") else "On time or early")
        fig = px.bar(b, x="bucket", y="avg_review", color="Timing", text="avg_review",
                     hover_data={"orders": ":,"},
                     color_discrete_map={"On time or early": BLUE, "Late": ORANGE})
        fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
        fig.update_yaxes(range=[0, 5.3], title="Average review (1-5)")
        fig.update_xaxes(title=None)
        show(fig)

    heading("Freight as % of item value, by state", "Full dataset; states with 30+ orders, top 10")
    fr = D["11_freight_burden_by_state"].head(10).iloc[::-1]
    fig = px.bar(fr, x="freight_pct_of_item_value", y="customer_state", orientation="h",
                 hover_data={"orders": ":,", "avg_freight": ":.2f"}, color_discrete_sequence=[BLUE])
    fig.update_xaxes(ticksuffix="%", title=None)
    fig.update_yaxes(title=None)
    show(fig, 320)

# ------------------------------------------------------------------ customers
with tabs[2]:
    st.caption("Full dataset (not affected by the sidebar filters).")
    c6 = D["06_cohort_retention"]
    last = D["02_monthly_revenue_growth"].query("orders >= @MIN_MONTH_ORDERS").purchase_month.max()
    size = c6.drop_duplicates("cohort_month").set_index("cohort_month").cohort_customers
    cohorts = sorted(c for c in size.index if size[c] >= MIN_MONTH_ORDERS and mi(c) + 6 <= mi(last))
    heading("Cohort retention", "% of each acquisition cohort ordering again, 1-6 months later")
    if len(cohorts) < 2:
        st.info("Not enough cohorts with 6 months of follow-up.")
    else:
        lookup = c6.set_index(["cohort_month", "month_number"]).retention_pct
        mat = [[float(lookup.get((c, m), 0.0)) for m in range(1, 7)] for c in cohorts]
        fig = px.imshow(mat, x=[f"Month +{m}" for m in range(1, 7)],
                        y=[f"{c} (n={int(size[c]):,})" for c in cohorts],
                        color_continuous_scale=SEQ, text_auto=".1f", aspect="auto",
                        labels=dict(color="Retention %"))
        fig.update_coloraxes(showscale=False)
        show(fig, 120 + 28 * len(cohorts))

    left, right = st.columns(2)
    with left:
        heading("RFM segments", "Share of customers vs share of revenue")
        r = D["07_rfm_segments"].sort_values("pct_revenue").rename(
            columns={"pct_customers": "% of customers", "pct_revenue": "% of revenue"})
        fig = px.bar(r, y="segment", x=["% of customers", "% of revenue"], barmode="group",
                     orientation="h", color_discrete_map={"% of customers": BLUE, "% of revenue": ORANGE})
        fig.update_xaxes(ticksuffix="%", title=None)
        fig.update_yaxes(title=None)
        show(fig, 380)
    with right:
        heading("Repeat rate by first-order review", "% of customers who ordered again")
        r12 = D["12_first_order_experience_vs_repeat"].copy()
        r12["first order"] = r12.first_order_review.astype(int).astype(str) + " star"
        fig = px.bar(r12, x="first order", y="repeat_rate_pct", text="repeat_rate_pct",
                     hover_data={"customers": ":,"}, color_discrete_sequence=[BLUE])
        fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig.update_yaxes(ticksuffix="%", title=None, rangemode="tozero")
        fig.update_xaxes(title=None)
        show(fig, 380)
    st.dataframe(D["07_rfm_segments"], hide_index=True, width="stretch")

# ------------------------------------------------------------------ sellers and categories
with tabs[3]:
    st.caption("Full dataset (not affected by the sidebar filters).")
    heading("Category revenue (Pareto)", "Top 15 categories by revenue share")
    cat = D["03_category_pareto"].head(15).iloc[::-1].copy()
    cat["category"] = cat.category.str.replace("_", " ")
    fig = px.bar(cat, x="revenue_share_pct", y="category", orientation="h",
                 hover_data={"cumulative_share_pct": ":.1f", "avg_review": ":.2f"},
                 color_discrete_sequence=[BLUE])
    fig.update_xaxes(ticksuffix="%", title=None)
    fig.update_yaxes(title=None)
    show(fig, 420)

    heading("Seller scorecard", "Sellers with 20+ delivered orders. 'Fix first' = top revenue quartile with "
                                "avg review < 3.8 or > 15% late")
    sl = D["08_seller_scorecard"]
    flags = sorted(sl.action_flag.unique())
    chosen = st.multiselect("Action flag", flags, default=flags)
    view = sl[sl.action_flag.isin(chosen)]
    if view.empty:
        st.info("No sellers for this selection.")
    else:
        fig = px.scatter(view, x="late_pct", y="avg_review", size="revenue", color="action_flag",
                         hover_data=["seller_id", "seller_state", "orders", "revenue_rank"],
                         color_discrete_map={"Fix first: big seller, poor experience": ORANGE,
                                             "Healthy": AQUA, "Monitor": BLUE}, size_max=28)
        fig.update_xaxes(ticksuffix="%", title="Late deliveries")
        fig.update_yaxes(title="Average review")
        show(fig, 420)
        st.dataframe(view, hide_index=True, width="stretch")

# ------------------------------------------------------------------ findings
with tabs[4]:
    st.markdown(D["findings"])
    figs = sorted((OUT / "figures").glob("*.png"))
    if figs:
        with st.expander("Presentation charts"):
            cols = st.columns(2)
            for i, p in enumerate(figs):
                cols[i % 2].image(str(p))

# ------------------------------------------------------------------ data quality
with tabs[5]:
    heading("Data-quality checks", "Run automatically when the data is loaded")
    st.dataframe(D["data_quality"], hide_index=True, width="stretch")
    st.markdown("""
**Metric definitions**
- **Valid order**: status is not `canceled` or `unavailable`, and it has at least one line item.
- **Revenue / GMV**: sum of item prices; freight is excluded.
- **Late order**: delivered on a later calendar date than the estimate (comparing raw timestamps would
  wrongly flag same-day deliveries, because the estimate is stored as midnight).
- **Review score**: the latest review per order (some orders have more than one).
- **Customer**: `customer_unique_id` (`customer_id` is per order and would hide repeat buyers).
""")
