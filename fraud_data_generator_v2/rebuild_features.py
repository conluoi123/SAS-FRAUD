from __future__ import annotations
from datetime import datetime, timedelta
from statistics import median
from generators.engine import M, read, write


def rebuild():
    tx = read("transactions")
    sessions = {x["session_id"]: x for x in read("login_sessions")}
    bens = {x["beneficiary_id"]: x for x in read("beneficiaries")}
    changes = read("account_change_events")
    auth = read("auth_events")
    byacc = {}
    for x in tx:
        byacc.setdefault(x["account_id"], []).append(x)
    chby = {}
    for x in changes:
        chby.setdefault(x["account_id"], []).append(x)
    aby = {}
    for x in auth:
        aby.setdefault(x["account_id"], []).append(x)
    out = []
    for acc, lst in byacc.items():
        lst.sort(key=lambda x: x["transaction_at"])
        for x in lst:
            t = datetime.fromisoformat(x["transaction_at"])
            prior_amounts = [
                float(z["amount"])
                for z in lst
                if datetime.fromisoformat(z["transaction_at"]) < t
            ]
            prior_median = max(median(prior_amounts), 1) if prior_amounts else None
            recent = [
                z
                for z in lst
                if timedelta(0)
                <= t - datetime.fromisoformat(z["transaction_at"])
                <= timedelta(minutes=10)
            ]
            hour = [
                z
                for z in lst
                if timedelta(0)
                <= t - datetime.fromisoformat(z["transaction_at"])
                <= timedelta(hours=1)
            ]
            day = [
                z
                for z in lst
                if timedelta(0)
                <= t - datetime.fromisoformat(z["transaction_at"])
                <= timedelta(hours=24)
            ]
            b = bens.get(x["beneficiary_id"])
            bmins = (
                int((t - datetime.fromisoformat(b["added_at"])).total_seconds() / 60)
                if b
                else None
            )
            prior = [
                z
                for z in chby.get(acc, [])
                if datetime.fromisoformat(z["changed_at"]) <= t
            ]
            cmins = (
                int(
                    (
                        t - max(datetime.fromisoformat(z["changed_at"]) for z in prior)
                    ).total_seconds()
                    / 60
                )
                if prior
                else None
            )
            fails = sum(
                1
                for z in aby.get(acc, [])
                if z["auth_result"] == "failed"
                and timedelta(0)
                <= t - datetime.fromisoformat(z["auth_at"])
                <= timedelta(minutes=30)
            )
            ses = sessions.get(x["session_id"], {})
            out.append(
                dict(
                    transaction_id=x["transaction_id"],
                    feature_version="v2_scenario_enriched",
                    computed_at=x["transaction_at"],
                    is_new_device=ses.get("is_new_device") == "true",
                    is_new_beneficiary=bmins is not None and bmins <= 60,
                    is_after_sensitive_change=cmins is not None and cmins <= 30,
                    txn_count_10m=len(recent),
                    txn_count_1h=len(hour),
                    txn_amount_sum_24h=sum(float(z["amount"]) for z in day),
                    amount_to_median_ratio=(
                        round(float(x["amount"]) / prior_median, 4)
                        if prior_median is not None
                        else ""
                    ),
                    failed_auth_count_30m=fails,
                    time_since_beneficiary_added_minutes=bmins
                    if bmins is not None
                    else "",
                    time_since_sensitive_change_minutes=cmins
                    if cmins is not None
                    else "",
                    features={
                        "generator_version": "2.0.0",
                        "amount_to_balance_ratio": round(
                            float(x["amount"]) / max(float(x["balance_before"]), 1), 4
                        ),
                        "is_night_hour": t.hour < 5,
                        "has_prior_amount_history": bool(prior_amounts),
                    },
                )
            )
    write("transaction_features", M["transaction_features"], out)
    print("[FEATURE] rebuilt", len(out), "transaction features")


if __name__ == "__main__":
    rebuild()
