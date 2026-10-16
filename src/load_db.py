"""Load the Olist CSVs into SQLite, run data-quality checks, create the analysis views.

    python src/load_db.py
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
DB = ROOT / "data" / "olist.db"
OUT = ROOT / "outputs"
VIEWS = ROOT / "sql" / "00_views.sql"

FILES = {
    "customers": "olist_customers_dataset.csv",
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "order_payments": "olist_order_payments_dataset.csv",
    "order_reviews": "olist_order_reviews_dataset.csv",
    "products": "olist_products_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
}

INDEXES = [
    "CREATE INDEX IF NOT EXISTS ix_orders_id    ON orders(order_id)",
    "CREATE INDEX IF NOT EXISTS ix_orders_cust  ON orders(customer_id)",
    "CREATE INDEX IF NOT EXISTS ix_items_order  ON order_items(order_id)",
    "CREATE INDEX IF NOT EXISTS ix_items_seller ON order_items(seller_id)",
    "CREATE INDEX IF NOT EXISTS ix_items_prod   ON order_items(product_id)",
    "CREATE INDEX IF NOT EXISTS ix_pay_order    ON order_payments(order_id)",
    "CREATE INDEX IF NOT EXISTS ix_rev_order    ON order_reviews(order_id)",
    "CREATE INDEX IF NOT EXISTS ix_cust_id      ON customers(customer_id)",
    "CREATE INDEX IF NOT EXISTS ix_prod_id      ON products(product_id)",
    "CREATE INDEX IF NOT EXISTS ix_sell_id      ON sellers(seller_id)",
]


def load_tables(con: sqlite3.Connection) -> None:
    missing = [f for f in FILES.values() if not (RAW / f).exists()]
    if missing:
        print("Missing files in data/raw/:\n  " + "\n  ".join(missing))
        print("\nDownload the 'Brazilian E-Commerce Public Dataset by Olist' from Kaggle and unzip it"
              "\ninto data/raw/ (see README), or run: python src/make_sample_data.py")
        sys.exit(1)
    for table, fname in FILES.items():
        df = pd.read_csv(RAW / fname)
        df.to_sql(table, con, if_exists="replace", index=False)
        print(f"  loaded {table:22s} {len(df):>9,} rows")
    for stmt in INDEXES:
        con.execute(stmt)


def data_quality(con: sqlite3.Connection) -> pd.DataFrame:
    def q(sql: str) -> int:
        return int(con.execute(sql).fetchone()[0])

    n_orders = q("SELECT COUNT(*) FROM orders")
    n_deliv = q("SELECT COUNT(*) FROM orders WHERE order_status = 'delivered'")
    n_prod = q("SELECT COUNT(*) FROM products")
    rows = [
        ("Duplicate order_id rows in orders",
         q("SELECT COUNT(*) - COUNT(DISTINCT order_id) FROM orders"), n_orders,
         "None expected; would be de-duplicated"),
        ("Orders with no line items",
         q("SELECT COUNT(*) FROM orders o WHERE NOT EXISTS "
           "(SELECT 1 FROM order_items i WHERE i.order_id = o.order_id)"), n_orders,
         "Excluded from revenue metrics (n_items > 0)"),
        ("Orders cancelled or unavailable",
         q("SELECT COUNT(*) FROM orders WHERE order_status IN ('canceled','unavailable')"), n_orders,
         "Excluded from revenue, retention and RFM"),
        ("Delivered orders missing a delivery date",
         q("SELECT COUNT(*) FROM orders WHERE order_status = 'delivered' "
           "AND order_delivered_customer_date IS NULL"), n_deliv,
         "Excluded from delivery metrics"),
        ("Delivered before the purchase timestamp",
         q("SELECT COUNT(*) FROM orders WHERE order_delivered_customer_date IS NOT NULL "
           "AND order_delivered_customer_date < order_purchase_timestamp"), n_deliv,
         "Flagged; investigate if non-zero"),
        ("Orders with more than one review",
         q("SELECT COUNT(*) FROM (SELECT order_id FROM order_reviews "
           "GROUP BY order_id HAVING COUNT(*) > 1)"), n_orders,
         "Latest review kept (ROW_NUMBER over answer timestamp)"),
        ("Products with no category",
         q("SELECT COUNT(*) FROM products WHERE product_category_name IS NULL"), n_prod,
         "Labelled 'unknown' in item_facts"),
        ("Categories missing an English translation",
         q("SELECT COUNT(DISTINCT p.product_category_name) FROM products p LEFT JOIN "
           "category_translation t ON t.product_category_name = p.product_category_name "
           "WHERE p.product_category_name IS NOT NULL AND t.product_category_name IS NULL"),
         max(q("SELECT COUNT(DISTINCT product_category_name) FROM products"), 1),
         "Falls back to the Portuguese name"),
    ]
    df = pd.DataFrame(rows, columns=["check", "rows_affected", "out_of", "how_handled"])
    df["pct"] = (100.0 * df.rows_affected / df.out_of.clip(lower=1)).round(2)
    return df


def main() -> None:
    DB.parent.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    if DB.exists():
        DB.unlink()
    con = sqlite3.connect(DB)
    print(f"Loading CSVs from {RAW} into {DB.name}")
    load_tables(con)
    con.executescript(VIEWS.read_text())
    dq = data_quality(con)
    dq.to_csv(OUT / "data_quality.csv", index=False)
    print("\nData-quality checks (saved to outputs/data_quality.csv):")
    print(dq.to_string(index=False))
    con.commit()
    con.close()
    print("\nDone. NEXT: python src/run_analysis.py")


if __name__ == "__main__":
    main()
