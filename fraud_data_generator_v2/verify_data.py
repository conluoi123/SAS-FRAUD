import csv
import sys
from datetime import date, datetime
from pathlib import Path
from generators.engine import CFG, M, ORDER, OUT, RUN

ROOT = Path(__file__).resolve().parent
data = {}
err = []
warn = []
for t, cols in M.items():
    p = OUT / f"{t}.csv"
    if not p.exists():
        err.append(f"missing {t}")
        continue
    with p.open(encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        rows = list(r)
    data[t] = rows
    if r.fieldnames != cols:
        err.append(f"{t}: header mismatch")
# pk uniqueness
pks = {
    "simulation_runs": "simulation_run_id",
    "customers": "customer_id",
    "accounts": "account_id",
    "devices": "device_id",
    "login_sessions": "session_id",
    "beneficiaries": "beneficiary_id",
    "account_change_events": "change_event_id",
    "transactions": "transaction_id",
    "transaction_features": "transaction_id",
    "auth_events": "auth_event_id",
    "sales_points": "sales_point_id",
    "sales_agents": "sales_agent_id",
    "loan_applications": "application_id",
    "applicant_declared_profiles": "declared_profile_id",
    "employment_income_profiles": "employment_id",
    "reference_contacts": "reference_id",
    "application_documents": "document_id",
    "credit_bureau_snapshots": "bureau_snapshot_id",
    "disbursement_accounts": "disbursement_id",
    "loan_repayment_outcomes": "loan_outcome_id",
    "rules": "rule_id",
    "decision_outcomes": "decision_outcome_id",
    "rule_hits": "rule_hit_id",
    "alerts": "alert_id",
    "cases": "case_id",
    "verification_results": "verification_id",
    "fraud_ground_truth": "fraud_event_id",
}
for t, pk in pks.items():
    vals = [x[pk] for x in data.get(t, [])]
    if len(vals) != len(set(vals)):
        err.append(f"{t}: duplicate PK")


def ids(t, c):
    return {x[c] for x in data.get(t, []) if x.get(c)}


checks = [
    ("accounts", "customer_id", "customers", "customer_id"),
    ("login_sessions", "account_id", "accounts", "account_id"),
    ("login_sessions", "customer_id", "customers", "customer_id"),
    ("login_sessions", "device_id", "devices", "device_id"),
    ("beneficiaries", "account_id", "accounts", "account_id"),
    ("account_change_events", "account_id", "accounts", "account_id"),
    ("transactions", "account_id", "accounts", "account_id"),
    ("transactions", "customer_id", "customers", "customer_id"),
    ("transactions", "session_id", "login_sessions", "session_id"),
    ("transactions", "device_id", "devices", "device_id"),
    ("transactions", "beneficiary_id", "beneficiaries", "beneficiary_id"),
    ("transaction_features", "transaction_id", "transactions", "transaction_id"),
    ("auth_events", "transaction_id", "transactions", "transaction_id"),
    ("sales_agents", "sales_point_id", "sales_points", "sales_point_id"),
    ("loan_applications", "customer_id", "customers", "customer_id"),
    ("loan_applications", "sales_point_id", "sales_points", "sales_point_id"),
    ("loan_applications", "sales_agent_id", "sales_agents", "sales_agent_id"),
    (
        "applicant_declared_profiles",
        "application_id",
        "loan_applications",
        "application_id",
    ),
    (
        "employment_income_profiles",
        "application_id",
        "loan_applications",
        "application_id",
    ),
    ("reference_contacts", "application_id", "loan_applications", "application_id"),
    ("application_documents", "application_id", "loan_applications", "application_id"),
    (
        "credit_bureau_snapshots",
        "application_id",
        "loan_applications",
        "application_id",
    ),
    ("disbursement_accounts", "application_id", "loan_applications", "application_id"),
    (
        "loan_repayment_outcomes",
        "application_id",
        "loan_applications",
        "application_id",
    ),
    ("decision_outcomes", "transaction_id", "transactions", "transaction_id"),
    ("decision_outcomes", "application_id", "loan_applications", "application_id"),
    ("rule_hits", "decision_outcome_id", "decision_outcomes", "decision_outcome_id"),
    ("rule_hits", "rule_id", "rules", "rule_id"),
    ("alerts", "decision_outcome_id", "decision_outcomes", "decision_outcome_id"),
    ("cases", "primary_alert_id", "alerts", "alert_id"),
    ("verification_results", "alert_id", "alerts", "alert_id"),
    ("verification_results", "case_id", "cases", "case_id"),
]
for ct, cc, pt, pc in checks:
    par = ids(pt, pc)
    bad = [x[cc] for x in data.get(ct, []) if x.get(cc) and x[cc] not in par]
    if bad:
        err.append(f"{ct}.{cc}: {len(bad)} orphan")
for t, rows in data.items():
    if "simulation_run_id" in M[t] and any(x["simulation_run_id"] != RUN for x in rows):
        err.append(f"{t}: wrong run")
for x in data.get("auth_events", []):
    if (
        sum(bool(x.get(k)) for k in ["transaction_id", "session_id", "change_event_id"])
        != 1
    ):
        err.append("auth context invalid")
for x in data.get("loan_repayment_outcomes", []):
    d30 = x["dpd_30_flag"] == "true"
    d60 = x["dpd_60_flag"] == "true"
    d90 = x["dpd_90_flag"] == "true"
    if (d60 and not d30) or (d90 and not d60):
        err.append("DPD invalid")

# Business constraint: a per-transaction transfer limit cannot exceed the
# account's total daily transfer limit.
invalid_account_limits = [
    x["account_id"]
    for x in data.get("accounts", [])
    if float(x["single_txn_limit"]) > float(x["daily_transfer_limit"])
]
if invalid_account_limits:
    err.append(
        "accounts: "
        f"{len(invalid_account_limits)} rows with single_txn_limit "
        "> daily_transfer_limit"
    )

account_open_dates = {
    x["account_id"]: date.fromisoformat(x["open_date"])
    for x in data.get("accounts", [])
    if x.get("open_date")
}
transactions_before_account_open = [
    x["transaction_id"]
    for x in data.get("transactions", [])
    if x.get("account_id") in account_open_dates
    and datetime.fromisoformat(x["transaction_at"]).date()
    < account_open_dates[x["account_id"]]
]
if transactions_before_account_open:
    err.append(
        "transactions: "
        f"{len(transactions_before_account_open)} rows occur before account open_date"
    )
# timeline causality: session must precede/cover the transaction, beneficiary must predate it
ses_by_id = {x["session_id"]: x for x in data.get("login_sessions", [])}
ben_by_id = {x["beneficiary_id"]: x for x in data.get("beneficiaries", [])}
bridge_path = OUT / "scenario_event_entities.csv"
scenario_transaction_ids = set()
if not bridge_path.exists():
    err.append("missing scenario_event_entities.csv")
else:
    with bridge_path.open(encoding="utf-8", newline="") as f:
        entity_links = list(csv.DictReader(f))
    transaction_ids = ids("transactions", "transaction_id")
    transaction_links = [x for x in entity_links if x["entity_type"] == "transaction"]
    unknown_links = [
        x["entity_id"]
        for x in transaction_links
        if x["entity_id"] not in transaction_ids
    ]
    if unknown_links:
        err.append(
            f"scenario_event_entities: {len(unknown_links)} unknown transaction links"
        )
    duplicates = len(transaction_links) - len(
        {(x["event_id"], x["entity_type"], x["entity_id"]) for x in transaction_links}
    )
    if duplicates:
        err.append(f"scenario_event_entities: {duplicates} duplicate links")
    scenario_transaction_ids = {
        x["entity_id"] for x in transaction_links if x["label_scope"] == "fraud"
    }

before_login = []
after_end = []
before_bene = []
for x in data.get("transactions", []):
    s = ses_by_id.get(x.get("session_id"))
    if s:
        if x["transaction_at"] < s["login_at"]:
            before_login.append(x["transaction_id"])
        elif x["transaction_at"] > s["session_end_at"]:
            after_end.append(x["transaction_id"])
    b = ben_by_id.get(x.get("beneficiary_id"))
    if b and x["transaction_at"] < b["added_at"]:
        before_bene.append(x["transaction_id"])

for bad_ids, message in [
    (before_login, "occur before session login_at"),
    (after_end, "occur after session_end_at"),
    (before_bene, "occur before beneficiary added_at"),
]:
    if not bad_ids:
        continue
    scenario_bad = scenario_transaction_ids.intersection(bad_ids)
    detail = f"transactions: {len(bad_ids)} {message}"
    if scenario_bad:
        err.append(f"{detail} ({len(scenario_bad)} fraud scenario rows)")
    else:
        warn.append(f"{detail} (background generator rows only)")

# balance chain continuity per account, sorted by transaction_at
by_acc = {}
for x in data.get("transactions", []):
    by_acc.setdefault(x["account_id"], []).append(x)
chain_bad = 0
for rows in by_acc.values():
    rows = sorted(rows, key=lambda x: x["transaction_at"])
    for a, bnext in zip(rows, rows[1:]):
        if abs(float(a["balance_after"]) - float(bnext["balance_before"])) > 0.01:
            chain_bad += 1
if chain_bad:
    err.append(f"transactions: {chain_bad} consecutive pairs with broken balance chain")

# decision_outcomes entity_type consistency
ent_bad = sum(
    1
    for d in data.get("decision_outcomes", [])
    if d["message_type"] == "transaction"
    and not d["transaction_id"]
    and d["entity_type"] == "transaction"
)
if ent_bad:
    err.append(
        f"decision_outcomes: {ent_bad} rows with empty transaction_id but entity_type=transaction"
    )

# ground truth negative/false-positive coverage
gt = data.get("fraud_ground_truth", [])
if gt:
    fp = sum(1 for x in gt if x["fraud_label"] == "false_positive_seed")
    print(
        f"GROUND TRUTH: {len(gt)} total, {fp} false_positive_seed, {len(gt) - fp} confirmed_fraud"
    )
    if fp == 0:
        err.append(
            "fraud_ground_truth: 0 false-positive/legitimate records (no negative set)"
        )

print("ROW COUNTS")
for t in ORDER:
    print(f"{t:35s}{len(data.get(t, [])):8d}")

# V2 scenario coverage checks
mp = OUT / "scenario_manifest.csv"
if not mp.exists():
    err.append("missing scenario_manifest.csv")
else:
    with mp.open(encoding="utf-8", newline="") as f:
        sc = list(csv.DictReader(f))
    codes = {x["scenario_code"] for x in sc}
    enabled_domains = set(CFG.get("enabled_domains", ["transaction", "loan"]))
    expected = set()
    if "transaction" in enabled_domains:
        expected |= {f"TXN-{i:02d}" for i in range(1, 11)}
    if "loan" in enabled_domains:
        expected |= {f"LOAN-{i:02d}" for i in range(1, 11)}
    miss = expected - codes
    if miss:
        err.append("missing scenario coverage: " + ",".join(sorted(miss)))
    # Verify persona anomaly is not present unless customer is fraud seeded
    for c in data.get("customers", []):
        if (
            c["occupation_group"] == "student"
            and c["income_band"] not in ("<5M", "5-10M")
            and c["is_synthetic_identity_seed"] != "true"
        ):
            err.append("clean student with implausible income band")
    fraud_codes = {code for code in codes if code.startswith(("TXN-", "LOAN-"))}
    negative_codes = codes - fraud_codes
    print("FRAUD SCENARIO COVERAGE:", len(fraud_codes), "/", len(expected))
    print("HARD-NEGATIVE CLASSES:", len(negative_codes))

if err:
    result = f"FAILED ({len(err)})"
elif warn:
    result = f"PASSED WITH WARNINGS ({len(warn)})"
else:
    result = "PASSED"
print("\nRESULT:", result)
for e in err[:30]:
    print("-", e)
for message in warn[:30]:
    print("- WARNING:", message)
sys.exit(1 if err else 0)
