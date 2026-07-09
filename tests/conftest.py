"""Shared fixtures: planted-answer test data."""
import csv
from pathlib import Path

import pytest


@pytest.fixture()
def messy_csv(tmp_path: Path) -> Path:
    """8 rows: 2 null emails, 1 bad email, 1 negative amount, 1 future date,
    2 status case variants, 1 exact duplicate row, 1 reused order id."""
    p = tmp_path / "orders.csv"
    rows = [
        ["O-1", "C-1", "a@x.com",      "2026-06-01 10:00:00", "100.0",  "paid"],
        ["O-2", "C-1", "",             "2026-06-02 10:00:00", "200.0",  "paid"],
        ["O-3", "C-2", "",             "2026-06-03 10:00:00", "-50.0",  "PAID"],
        ["O-4", "C-2", "not-an-email", "2026-06-04 10:00:00", "300.0",  "shipped"],
        ["O-5", "C-3", "b@x.com",      "2099-01-01 10:00:00", "400.0",  " paid"],
        ["O-1", "C-3", "c@x.com",      "2026-06-05 10:00:00", "500.0",  "delivered"],
        ["O-6", "C-9", "d@x.com",      "2026-06-06 10:00:00", "600.0",  "paid"],
        ["O-6", "C-9", "d@x.com",      "2026-06-06 10:00:00", "600.0",  "paid"],
    ]
    with p.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["order_id", "customer_id", "email",
                    "order_date", "amount", "status"])
        w.writerows(rows)
    return p


@pytest.fixture()
def reference_csv(tmp_path: Path) -> Path:
    """Customers C-1..C-4 exist; C-9 in orders is an orphan on purpose."""
    p = tmp_path / "customers.csv"
    with p.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["customer_id", "region"])
        w.writerows([["C-1", "North"], ["C-2", "South"],
                     ["C-3", "East"], ["C-4", "West"]])
    return p
