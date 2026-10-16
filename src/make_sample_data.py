"""Generate a SYNTHETIC dataset with the exact Olist schema.

Purpose: test the whole pipeline (load -> SQL -> charts -> dashboard) before you
download the real data. The numbers it produces are NOT real findings. A marker
file (data/raw/SAMPLE_DATA.txt) makes every output label itself as sample data.
To switch to real data: delete data/raw/, drop the Kaggle CSVs in, rerun.

    python src/make_sample_data.py --orders 30000
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw"
FMT = "%Y-%m-%d %H:%M:%S"

# customer-state mix, rough delivery distance from the main seller hub (SP), late-risk multiplier
STATE_W = {"SP": 41.8, "RJ": 12.9, "MG": 11.7, "RS": 5.5, "PR": 5.1, "SC": 3.7, "BA": 3.4,
           "DF": 2.1, "ES": 2.0, "GO": 2.0, "PE": 1.6, "CE": 1.3, "PA": 1.0, "MT": 1.0,
           "MA": 0.7, "MS": 0.7, "PB": 0.5, "PI": 0.5, "RN": 0.5, "AL": 0.4, "SE": 0.35,
           "TO": 0.3, "RO": 0.25, "AM": 0.15, "AC": 0.08, "AP": 0.07, "RR": 0.05}
DIST = {"SP": 0, "RJ": 3, "MG": 3, "ES": 4, "PR": 2, "SC": 3, "RS": 5, "DF": 5, "GO": 5,
        "MT": 8, "MS": 6, "BA": 8, "PE": 11, "CE": 11, "MA": 12, "PB": 11, "PI": 12,
        "RN": 11, "AL": 10, "SE": 9, "PA": 14, "TO": 11, "RO": 15, "AM": 17, "AC": 18,
        "AP": 17, "RR": 18}
LATE_F = {"SP": 0.7, "RJ": 1.1, "MG": 0.9, "ES": 1.1, "PR": 0.9, "SC": 0.9, "RS": 0.9,
          "DF": 1.1, "GO": 1.1, "MT": 1.1, "MS": 1.1}  # everything else: 1.8

# (portuguese name, english name, median price, popularity weight)
CATS = [
    ("cama_mesa_banho", "bed_bath_table", 75, 11), ("beleza_saude", "health_beauty", 95, 9.5),
    ("esporte_lazer", "sports_leisure", 90, 8.5),
    ("informatica_acessorios", "computers_accessories", 110, 8),
    ("moveis_decoracao", "furniture_decor", 80, 8), ("utilidades_domesticas", "housewares", 65, 7),
    ("relogios_presentes", "watches_gifts", 190, 6), ("telefonia", "telephony", 45, 4.5),
    ("automotivo", "auto", 85, 4), ("brinquedos", "toys", 80, 4),
    ("cool_stuff", "cool_stuff", 110, 3.5), ("ferramentas_jardim", "garden_tools", 70, 3.5),
    ("perfumaria", "perfumery", 75, 3.2), ("bebes", "baby", 80, 3),
    ("eletronicos", "electronics", 60, 2.7), ("papelaria", "stationery", 50, 2.4),
    ("fashion_bolsas_e_acessorios", "fashion_bags_accessories", 90, 2.2),
    ("pet_shop", "pet_shop", 85, 1.9), ("eletrodomesticos", "home_appliances", 120, 1.8),
    ("livros_tecnicos", "books_technical", 50, 0.3), ("pcs", "computers", 1400, 0.2),
    ("telefonia_fixa", "fixed_telephony", 150, 0.25),
]
STATUS = ["delivered", "shipped", "canceled", "unavailable", "invoiced", "processing",
          "approved", "created"]
STATUS_P = [0.968, 0.011, 0.007, 0.006, 0.003, 0.003, 0.001, 0.001]
P_OK = [0.03, 0.02, 0.07, 0.20, 0.68]      # review-score mix, on-time orders
P_LATE = [0.40, 0.17, 0.13, 0.14, 0.16]    # review-score mix, late orders
SAT_W = {0: 0.8, 1: 0.15, 2: 0.30, 3: 0.60, 4: 1.00, 5: 1.30}  # chance of buying again
SPIKES = [(pd.Timestamp("2017-11-20"), pd.Timestamp("2017-12-05"), 2.5),
          (pd.Timestamp("2018-02-01"), pd.Timestamp("2018-03-15"), 1.5)]


def fmt(ts):
    return None if ts is None else ts.strftime(FMT)


def make(n_orders: int, seed: int) -> None:
    rng = np.random.default_rng(seed)

    def hid() -> str:
        return f"{int(rng.integers(0, 2**62)):016x}{int(rng.integers(0, 2**62)):016x}"

    states = list(STATE_W)
    st_p = np.array([STATE_W[s] for s in states])
    st_p = st_p / st_p.sum()

    # ---- sellers: heavy-tailed volume, a few big sellers with bad delivery performance
    n_sellers = max(60, n_orders // 50)
    seller_ids = [hid() for _ in range(n_sellers)]
    seller_state = rng.choice(states, n_sellers, p=st_p)
    seller_w = np.minimum(rng.pareto(1.5, n_sellers) + 1.0, 25.0)
    seller_w = seller_w / seller_w.sum()
    seller_late = np.clip(rng.normal(0.07, 0.03, n_sellers), 0.01, 0.20)
    top = np.argsort(-seller_w)[: max(6, n_sellers // 10)]
    bad_top = rng.choice(top, size=max(2, len(top) // 4), replace=False)
    seller_late[bad_top] = rng.uniform(0.22, 0.35, len(bad_top))
    bad_any = rng.choice(n_sellers, size=max(3, n_sellers // 12), replace=False)
    seller_late[bad_any] = np.maximum(seller_late[bad_any], rng.uniform(0.18, 0.30, len(bad_any)))
    sellers = pd.DataFrame({
        "seller_id": seller_ids,
        "seller_zip_code_prefix": rng.integers(1000, 99999, n_sellers),
        "seller_city": [f"city_{s.lower()}_{int(rng.integers(1, 15))}" for s in seller_state],
        "seller_state": seller_state,
    })

    # ---- products
    n_products = max(600, n_orders // 4)
    cat_w = np.array([c[3] for c in CATS], dtype=float)
    cat_w = cat_w / cat_w.sum()
    prod_cat = rng.choice(len(CATS), n_products, p=cat_w)
    prod_price = np.array([CATS[c][2] for c in prod_cat]) * rng.lognormal(0, 0.45, n_products)
    product_ids = [hid() for _ in range(n_products)]
    products = pd.DataFrame({
        "product_id": product_ids,
        "product_category_name": [CATS[c][0] for c in prod_cat],
        "product_name_lenght": rng.integers(20, 70, n_products),
        "product_description_lenght": rng.integers(100, 2000, n_products),
        "product_photos_qty": rng.integers(1, 8, n_products),
        "product_weight_g": rng.integers(100, 8000, n_products),
        "product_length_cm": rng.integers(10, 60, n_products),
        "product_height_cm": rng.integers(2, 40, n_products),
        "product_width_cm": rng.integers(8, 50, n_products),
    })
    products.loc[rng.random(n_products) < 0.02, "product_category_name"] = np.nan

    # ---- purchase timeline: growth over time plus a Black-Friday style spike
    start, end = pd.Timestamp("2017-01-05"), pd.Timestamp("2018-08-20")
    n_days = (end - start).days + 1
    t = np.linspace(0, 1, n_days)
    w = 0.25 + 1.8 * t ** 1.3
    dates = start + pd.to_timedelta(np.arange(n_days), unit="D")
    w = np.where((dates >= pd.Timestamp("2017-11-20")) & (dates <= pd.Timestamp("2017-11-30")),
                 w * 3.0, w)
    w = w / w.sum()
    day_idx = rng.choice(n_days, n_orders, p=w).astype("int64")
    secs = rng.integers(0, 86400, n_orders)
    purchase = (start + pd.to_timedelta(day_idx * 86400 + secs, unit="s")).sort_values()

    # ---- customer pool: repeat buyers are likelier after a good experience
    last_day = np.full(n_orders, -1e9)
    sat_w = np.ones(n_orders)
    uniq_ids: list[str] = []
    uniq_state: list[str] = []
    n_uniq = 0

    seller_draw = rng.choice(n_sellers, size=n_orders * 2, p=seller_w)
    prod_draw = rng.integers(0, n_products, size=n_orders * 2)
    L = len(seller_draw)
    sp = 0

    orders, items, pays, reviews, custs = [], [], [], [], []

    for i in range(n_orders):
        ts = purchase[i]
        day = (ts - start).days

        j = -1
        if n_uniq > 0 and rng.random() < 0.045:
            elig = last_day[:n_uniq] <= day - 45
            if elig.any():
                p = sat_w[:n_uniq] * elig
                j = int(rng.choice(n_uniq, p=p / p.sum()))
        if j < 0:
            j = n_uniq
            uniq_ids.append(hid())
            uniq_state.append(str(rng.choice(states, p=st_p)))
            n_uniq += 1
        state = uniq_state[j]

        status = STATUS[int(rng.choice(len(STATUS), p=STATUS_P))]
        delivered = status == "delivered"

        # lateness: seller quality x region x seasonal peaks
        s0 = int(seller_draw[sp % L])
        spike = 1.0
        for a, b, m in SPIKES:
            if a <= ts <= b:
                spike = m
        p_late = min(0.75, seller_late[s0] * LATE_F.get(state, 1.8) * spike)
        late = bool(rng.random() < p_late)
        est_days = 14 + DIST[state] + float(rng.uniform(0, 6))
        if late:
            act_days = est_days + 1.0 + float(rng.exponential(5.0))
        else:
            act_days = max(2.5, est_days - float(rng.uniform(3, 11)))

        approved = None if status == "created" else ts + pd.Timedelta(minutes=float(rng.exponential(600)))
        carrier = (approved + pd.Timedelta(days=float(rng.uniform(1, 3)))
                   if status in ("delivered", "shipped") else None)
        delivered_ts = ts + pd.Timedelta(days=act_days) if delivered else None
        est_ts = (ts + pd.Timedelta(days=est_days)).normalize()

        oid, cid = hid(), hid()
        orders.append({
            "order_id": oid, "customer_id": cid, "order_status": status,
            "order_purchase_timestamp": fmt(ts), "order_approved_at": fmt(approved),
            "order_delivered_carrier_date": fmt(carrier),
            "order_delivered_customer_date": fmt(delivered_ts),
            "order_estimated_delivery_date": fmt(est_ts),
        })
        custs.append({
            "customer_id": cid, "customer_unique_id": uniq_ids[j],
            "customer_zip_code_prefix": int(rng.integers(1000, 99999)),
            "customer_city": f"city_{state.lower()}_{int(rng.integers(1, 15))}",
            "customer_state": state,
        })

        if status != "created":
            k = int(rng.choice([1, 2, 3, 4], p=[0.88, 0.08, 0.03, 0.01]))
            total = 0.0
            for n in range(1, k + 1):
                s = int(seller_draw[sp % L])
                pi = int(prod_draw[sp % L])
                sp += 1
                price = max(5.0, round(float(prod_price[pi] * rng.lognormal(0, 0.1)), 2))
                freight = round(float((6 + 0.05 * price) * (1 + DIST[state] / 12)
                                      * rng.uniform(0.8, 1.2)), 2)
                total += price + freight
                items.append({
                    "order_id": oid, "order_item_id": n, "product_id": product_ids[pi],
                    "seller_id": seller_ids[s], "shipping_limit_date": fmt(ts + pd.Timedelta(days=3)),
                    "price": price, "freight_value": freight,
                })
            total = round(total, 2)
            ptype = str(rng.choice(["credit_card", "boleto", "voucher", "debit_card"],
                                   p=[0.74, 0.19, 0.055, 0.015]))
            inst = (int(rng.choice([1, 2, 3, 4, 5, 6, 8, 10],
                                   p=[0.5, 0.1, 0.1, 0.07, 0.05, 0.07, 0.05, 0.06]))
                    if ptype == "credit_card" else 1)
            if ptype == "credit_card" and rng.random() < 0.05:   # part paid by voucher
                v = round(total * float(rng.uniform(0.2, 0.5)), 2)
                pays.append({"order_id": oid, "payment_sequential": 1, "payment_type": "voucher",
                             "payment_installments": 1, "payment_value": v})
                pays.append({"order_id": oid, "payment_sequential": 2, "payment_type": ptype,
                             "payment_installments": inst, "payment_value": round(total - v, 2)})
            else:
                pays.append({"order_id": oid, "payment_sequential": 1, "payment_type": ptype,
                             "payment_installments": inst, "payment_value": total})

        score = 0
        if delivered and rng.random() < 0.985:
            score = int(rng.choice([1, 2, 3, 4, 5], p=P_LATE if late else P_OK))
            created = (delivered_ts + pd.Timedelta(days=1)).normalize()
            answered = created + pd.Timedelta(hours=float(rng.exponential(30)))
            reviews.append({
                "review_id": hid(), "order_id": oid, "review_score": score,
                "review_comment_title": None, "review_comment_message": None,
                "review_creation_date": fmt(created), "review_answer_timestamp": fmt(answered),
            })
            if rng.random() < 0.01:   # a few orders get a second review (real data has these too)
                reviews.append({
                    "review_id": hid(), "order_id": oid,
                    "review_score": int(rng.integers(1, 6)),
                    "review_comment_title": None, "review_comment_message": None,
                    "review_creation_date": fmt(created),
                    "review_answer_timestamp": fmt(answered + pd.Timedelta(days=2)),
                })
        sat_w[j] = SAT_W[score]
        last_day[j] = day

    OUT.mkdir(parents=True, exist_ok=True)
    tables = {
        "olist_orders_dataset.csv": pd.DataFrame(orders),
        "olist_customers_dataset.csv": pd.DataFrame(custs),
        "olist_order_items_dataset.csv": pd.DataFrame(items),
        "olist_order_payments_dataset.csv": pd.DataFrame(pays),
        "olist_order_reviews_dataset.csv": pd.DataFrame(reviews),
        "olist_products_dataset.csv": products,
        "olist_sellers_dataset.csv": sellers,
        "product_category_name_translation.csv": pd.DataFrame(
            [{"product_category_name": c[0], "product_category_name_english": c[1]} for c in CATS]),
    }
    for name, df in tables.items():
        df.to_csv(OUT / name, index=False)
        print(f"  {name:42s} {len(df):>8,} rows")
    (OUT / "SAMPLE_DATA.txt").write_text(
        "This folder holds SYNTHETIC data generated by src/make_sample_data.py.\n"
        "Delete the folder and add the real Olist CSVs from Kaggle to get real results.\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--orders", type=int, default=30000)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    print(f"Generating {args.orders:,} synthetic orders into {OUT} ...")
    make(args.orders, args.seed)
    print("Done. NEXT: python src/load_db.py")
