from __future__ import annotations
from generators.engine import M, read, write


def recompute():
    """Re-chain balance_before/balance_after per account in strict transaction_at order.

    Background rows (engine.py) and scenario-injected rows (scenario_engine.py) are generated
    in two separate passes and each computes its own balance independently, so the combined
    transactions.csv is not chronologically consistent until this runs. Anchors on the earliest
    transaction's own balance_before per account (no need for a separately-tracked "true"
    opening balance) and re-derives every balance_after/balance_before after that in time order.
    """
    by_account = {}
    for x in read("transactions"):
        by_account.setdefault(x["account_id"], []).append(x)
    all_rows = []
    for rows in by_account.values():
        rows.sort(key=lambda x: x["transaction_at"])
        bal = float(rows[0]["balance_before"])
        for row in rows:
            amt = float(row["amount"])
            before = bal
            bal = max(0.0, bal - amt) if row["direction"] == "DEBIT" else bal + amt
            row["balance_before"] = round(before, 2)
            row["balance_after"] = round(bal, 2)
        all_rows.extend(rows)
    write("transactions", M["transactions"], all_rows)
    print(
        f"[BALANCE] recomputed chain for {len(by_account)} accounts, {len(all_rows)} transactions"
    )


if __name__ == "__main__":
    recompute()
