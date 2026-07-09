"""analystkit.demo — generates messy data WITH its printed answer key."""
from __future__ import annotations

import csv
import json
import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path


def cmd_demo(out_dir: Path) -> None:
    """Creates orders.csv (deliberately messy), customers.csv (reference),
    orders.sqlite, and rules.json. Every planted issue is printed so you
    know the right answers before any tool runs — never trust a test you
    cannot independently check."""
    rng = random.Random(7)
    out_dir.mkdir(exist_ok=True)
    statuses_clean = ["paid", "shipped", "delivered", "refunded"]
    now = datetime.now()  # real clock: planted future dates stay future

    customers = [(f"CUST-{i:04d}",
                  f"customer{i}@example.com",
                  rng.choice(["North", "South", "East", "West"]))
                 for i in range(1, 201)]

    orders: list[list[str]] = []
    for i in range(1, 1101):
        cid = f"CUST-{rng.randint(1, 200):04d}"
        odate = now - timedelta(days=rng.randint(0, 89),
                                minutes=rng.randint(0, 1439))
        amount = round(rng.lognormvariate(6, 1.2), 2)
        status = rng.choice(statuses_clean)
        email = f"customer{int(cid[-4:])}@example.com"
        orders.append([f"ORD-{i:05d}", cid, email,
                       odate.strftime("%Y-%m-%d %H:%M:%S"),
                       str(amount), status])

    # ── Planted issues (the answer key) ─────────────────────────────
    for row in rng.sample(orders, 40):        # 40 null emails
        row[2] = ""
    for row in rng.sample(orders, 12):        # 12 negative amounts
        row[4] = str(-abs(float(row[4])))
    for row in rng.sample(orders, 6):         # 6 future dates
        row[3] = (now + timedelta(days=rng.randint(3, 30))
                  ).strftime("%Y-%m-%d %H:%M:%S")
    for row in rng.sample(orders, 25):        # 25 status case/space variants
        row[5] = rng.choice(["Paid", "PAID", " shipped", "Delivered "])
    for row in rng.sample(orders, 8):         # 8 invalid emails
        row[2] = row[2].replace("@", "_at_") if row[2] else "not-an-email"
    for row in rng.sample(orders, 5):         # 5 orphan customer ids
        row[1] = f"CUST-{rng.randint(900, 999):04d}"
    orders.extend([list(r) for r in rng.sample(orders, 7)])   # 7 exact dup rows
    for row in rng.sample(orders, 4):         # 4 reused order ids
        row[0] = orders[rng.randint(0, 50)][0]

    orders_csv = out_dir / "orders.csv"
    with orders_csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["order_id", "customer_id", "email",
                    "order_date", "amount", "status"])
        w.writerows(orders)

    cust_csv = out_dir / "customers.csv"
    with cust_csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["customer_id", "email", "region"])
        w.writerows(customers)

    db = out_dir / "orders.sqlite"
    db.unlink(missing_ok=True)
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE orders (order_id TEXT, customer_id TEXT, "
                     "email TEXT, order_date TEXT, amount REAL, status TEXT)")
        conn.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?)", orders)

    rules = [
        {"column": "order_id", "rule": "unique"},
        {"column": "customer_id", "rule": "not_null"},
        {"column": "email", "rule": "regex",
         "pattern": r"^[\w.+-]+@[\w-]+\.[\w.]+$"},
        {"column": "amount", "rule": "range", "min": 0},
        {"column": "status", "rule": "allowed",
         "values": ["paid", "shipped", "delivered", "refunded"]},
        {"column": "order_date", "rule": "not_future"},
    ]
    rules_path = out_dir / "rules.json"
    rules_path.write_text(json.dumps(rules, indent=2), encoding="utf-8")

    print(f"Created {len(orders):,} orders + {len(customers)} customers with "
          f"PLANTED issues (the answer key):")
    print("  40 null emails · 12 negative amounts · 6 future dates")
    print("  25 status case/space variants · 8 invalid emails")
    print("  5 orphan customer_ids · 7 exact duplicate rows · 4 reused order_ids")
    print(f"Files: {orders_csv}, {cust_csv}, {db}, {rules_path}")
    print("\nNow verify the tool finds what you KNOW is there:")
    print("  python3 analystkit.py profile demo_data/orders.csv")
    print("  python3 analystkit.py validate demo_data/orders.csv "
          "--rules demo_data/rules.json")
    print("  python3 analystkit.py reconcile demo_data/orders.csv "
          "demo_data/customers.csv --key customer_id --total amount")

