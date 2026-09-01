from __future__ import annotations
import csv
import json
import os
import random
import hashlib
from pathlib import Path
from datetime import datetime, timedelta, date, timezone

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = Path(os.environ.get("FRAUD_CONFIG", ROOT / "config.json"))
if not CONFIG_PATH.is_absolute():
    CONFIG_PATH = ROOT / CONFIG_PATH
CFG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
OUT = ROOT / CFG["output_dir"]
OUT.mkdir(parents=True, exist_ok=True)
RUN = CFG["simulation_run_id"]
SEED = CFG["random_seed"]
BASE = datetime(2026, 8, 6, 3, 0, tzinfo=timezone.utc)
PROV = [
    ("Hà Nội", 21.0285, 105.8542),
    ("TP.HCM", 10.8231, 106.6297),
    ("Đà Nẵng", 16.0544, 108.2022),
    ("Hải Phòng", 20.8449, 106.6881),
    ("Cần Thơ", 10.0452, 105.7469),
    ("Bình Dương", 11.3254, 106.4770),
]
BANKS = ["VCB", "BIDV", "CTG", "TCB", "MB", "ACB", "VPB", "OTHER"]
FIRST = [
    "An",
    "Bình",
    "Chi",
    "Dũng",
    "Hà",
    "Hải",
    "Hạnh",
    "Hiếu",
    "Hùng",
    "Lan",
    "Linh",
    "Long",
    "Mai",
    "Minh",
    "Nam",
    "Ngọc",
    "Phương",
    "Quân",
    "Quốc",
    "Sơn",
    "Thảo",
    "Trang",
    "Tuấn",
    "Vy",
]
LAST = [
    "Nguyễn",
    "Trần",
    "Lê",
    "Phạm",
    "Hoàng",
    "Huỳnh",
    "Phan",
    "Vũ",
    "Võ",
    "Đặng",
    "Bùi",
    "Đỗ",
    "Hồ",
    "Ngô",
    "Dương",
]
OCC = [
    "office",
    "factory",
    "teacher",
    "healthcare",
    "sales",
    "driver",
    "student",
    "self_employed",
    "engineer",
    "finance",
]


def rfor(name):
    return random.Random(SEED ^ int(hashlib.sha256(name.encode()).hexdigest()[:8], 16))


def h(s):
    return hashlib.sha256(s.encode()).hexdigest()


def nm(r):
    return f"{r.choice(LAST)} {r.choice(FIRST)}"


def dt(x):
    return x.isoformat()


def ds(x):
    return x.isoformat()


def arr(xs):
    return "{}" if not xs else "{" + ",".join('"' + x + '"' for x in xs) + "}"


def read(t):
    with (OUT / f"{t}.csv").open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write(t, cols, rows):
    with (OUT / f"{t}.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for row in rows:
            out = {}
            for c in cols:
                v = row.get(c, "")
                if isinstance(v, bool):
                    v = "true" if v else "false"
                elif isinstance(v, (dict, list)):
                    v = json.dumps(v, ensure_ascii=False)
                elif v is None:
                    v = ""
                out[c] = v
            w.writerow(out)


M = {
    "simulation_runs": [
        "simulation_run_id",
        "run_name",
        "dataset_version",
        "random_seed",
        "started_at",
        "completed_at",
        "run_status",
        "configuration",
        "created_by",
    ],
    "customers": [
        "customer_id",
        "simulation_run_id",
        "customer_type",
        "full_name",
        "gender",
        "dob",
        "id_number_hash",
        "phone_hash",
        "email_hash",
        "province",
        "address_cluster_id",
        "phone_cluster_id",
        "occupation_group",
        "income_band",
        "customer_segment",
        "onboarding_channel",
        "onboarding_date",
        "kyc_level",
        "base_risk_level",
        "customer_status",
        "is_synthetic_identity_seed",
        "is_mule_candidate_seed",
        "created_at",
    ],
    "accounts": [
        "account_id",
        "simulation_run_id",
        "customer_id",
        "account_no_hash",
        "account_type",
        "account_currency",
        "open_date",
        "status",
        "branch_code",
        "account_opening_channel",
        "home_province",
        "daily_transfer_limit",
        "single_txn_limit",
        "average_balance",
        "dormant_since",
        "created_at",
    ],
    "devices": [
        "device_id",
        "simulation_run_id",
        "device_fingerprint",
        "device_type",
        "os",
        "first_seen_at",
        "trust_status",
        "is_emulator",
        "is_rooted_or_jailbroken",
        "device_risk_score",
        "account_login_count",
        "created_at",
    ],
    "login_sessions": [
        "session_id",
        "simulation_run_id",
        "account_id",
        "customer_id",
        "device_id",
        "login_at",
        "ip_address",
        "province",
        "country",
        "latitude",
        "longitude",
        "geo_source",
        "vpn_flag",
        "proxy_flag",
        "login_result",
        "failure_reason",
        "auth_method",
        "is_new_device",
        "is_new_location",
        "session_risk_score",
        "session_end_at",
    ],
    "beneficiaries": [
        "beneficiary_id",
        "simulation_run_id",
        "account_id",
        "beneficiary_account_hash",
        "beneficiary_bank",
        "beneficiary_name",
        "added_at",
        "added_channel",
        "status",
        "is_internal_bank",
        "beneficiary_risk_level",
        "mule_cluster_id",
    ],
    "account_change_events": [
        "change_event_id",
        "simulation_run_id",
        "account_id",
        "customer_id",
        "changed_at",
        "change_type",
        "channel",
        "device_id",
        "verification_method",
        "change_result",
        "old_value_hash",
        "new_value_hash",
        "is_sensitive_change",
    ],
    "transactions": [
        "transaction_id",
        "simulation_run_id",
        "account_id",
        "customer_id",
        "session_id",
        "device_id",
        "beneficiary_id",
        "transaction_at",
        "amount",
        "currency",
        "direction",
        "transaction_type",
        "channel",
        "counterparty_account_hash",
        "counterparty_bank",
        "counterparty_internal_account_id",
        "merchant_id",
        "merchant_category_code",
        "ip_address",
        "province",
        "country",
        "vpn_flag",
        "proxy_flag",
        "status",
        "failure_reason",
        "balance_before",
        "balance_after",
        "created_at",
    ],
    "transaction_features": [
        "transaction_id",
        "feature_version",
        "computed_at",
        "is_new_device",
        "is_new_beneficiary",
        "is_after_sensitive_change",
        "txn_count_10m",
        "txn_count_1h",
        "txn_amount_sum_24h",
        "amount_to_median_ratio",
        "failed_auth_count_30m",
        "time_since_beneficiary_added_minutes",
        "time_since_sensitive_change_minutes",
        "features",
    ],
    "auth_events": [
        "auth_event_id",
        "simulation_run_id",
        "transaction_id",
        "session_id",
        "change_event_id",
        "account_id",
        "customer_id",
        "auth_at",
        "auth_method",
        "auth_result",
        "failed_attempt_count",
        "auth_risk_score",
    ],
    "sales_points": [
        "sales_point_id",
        "simulation_run_id",
        "sales_point_name",
        "sales_point_address",
        "province",
        "region",
        "opened_at",
        "monthly_application_baseline",
        "status",
        "created_at",
    ],
    "sales_agents": [
        "sales_agent_id",
        "simulation_run_id",
        "sales_point_id",
        "sales_agent_name",
        "join_date",
        "role",
        "monthly_application_baseline",
        "status",
        "created_at",
    ],
    "loan_applications": [
        "application_id",
        "simulation_run_id",
        "customer_id",
        "application_at",
        "loan_amount",
        "loan_term_months",
        "loan_product",
        "loan_purpose",
        "application_channel",
        "sales_point_id",
        "sales_agent_id",
        "application_status",
        "credit_underwriting_result",
        "decision_at",
        "device_id",
        "ip_address",
        "is_vpn",
        "is_proxy",
        "is_emulator",
        "created_at",
    ],
    "applicant_declared_profiles": [
        "declared_profile_id",
        "simulation_run_id",
        "application_id",
        "customer_id",
        "declared_full_name",
        "declared_id_number_hash",
        "declared_dob",
        "declared_phone_hash",
        "declared_email_hash",
        "declared_permanent_address",
        "declared_current_address",
        "declared_marital_status",
        "declared_dependents",
        "address_cluster_id",
        "profile_similarity_cluster_id",
        "address_quality_score",
        "created_at",
    ],
    "employment_income_profiles": [
        "employment_id",
        "simulation_run_id",
        "application_id",
        "occupation_group",
        "employer_name",
        "employer_phone_hash",
        "employer_phone_cluster_id",
        "employer_phone_verification_status",
        "is_employer_phone_reused",
        "employer_address",
        "employment_start_date",
        "months_at_employer",
        "declared_monthly_income",
        "income_document_type",
        "employer_cluster_id",
        "created_at",
    ],
    "reference_contacts": [
        "reference_id",
        "simulation_run_id",
        "application_id",
        "reference_name",
        "relationship",
        "reference_phone_hash",
        "phone_reuse_count",
        "reference_quality_score",
        "reference_order",
        "verification_status",
        "created_at",
    ],
    "application_documents": [
        "document_id",
        "simulation_run_id",
        "application_id",
        "document_type",
        "document_hash",
        "submitted_at",
        "ocr_quality_score",
        "tamper_score",
        "duplicate_document_hash_count",
        "id_front_back_match_flag",
        "id_expired_flag",
        "face_match_score",
        "liveness_result",
        "document_result",
        "created_at",
    ],
    "credit_bureau_snapshots": [
        "bureau_snapshot_id",
        "simulation_run_id",
        "application_id",
        "bureau_score",
        "active_loan_count",
        "dpd_max_12m",
        "recent_inquiry_count",
        "thin_file_flag",
        "bureau_match_result",
        "snapshot_at",
        "created_at",
    ],
    "disbursement_accounts": [
        "disbursement_id",
        "simulation_run_id",
        "application_id",
        "receiving_account_hash",
        "receiving_account_name",
        "receiving_bank",
        "same_as_applicant",
        "account_reuse_count",
        "linked_account_id",
        "disbursement_status",
        "disbursed_at",
        "disbursed_amount",
        "created_at",
    ],
    "loan_repayment_outcomes": [
        "loan_outcome_id",
        "simulation_run_id",
        "application_id",
        "disbursed_at",
        "first_due_date",
        "first_payment_status",
        "first_payment_days_past_due",
        "contact_status_after_disbursement",
        "dpd_30_flag",
        "dpd_60_flag",
        "dpd_90_flag",
        "installments_due",
        "installments_paid_on_time",
        "total_amount_due",
        "total_amount_paid",
        "outstanding_balance",
        "early_default_flag",
        "writeoff_amount",
        "loan_performance_status",
        "credit_performance_label",
        "fraud_outcome_label",
        "outcome_observed_at",
        "created_at",
    ],
    "rules": [
        "rule_id",
        "rule_code",
        "rule_name",
        "owner_domain",
        "scenario_code",
        "rule_type",
        "description",
        "severity",
        "base_score",
        "decision_flag",
        "status",
        "created_by",
        "created_at",
    ],
    "decision_outcomes": [
        "decision_outcome_id",
        "simulation_run_id",
        "message_type",
        "entity_type",
        "entity_id",
        "transaction_id",
        "application_id",
        "decision_at",
        "decision_flag",
        "risk_score_100",
        "reason_codes",
        "alert_recommended",
        "alert_type",
        "triage_queue",
        "processing_latency_ms",
        "created_at",
    ],
    "rule_hits": [
        "rule_hit_id",
        "simulation_run_id",
        "decision_outcome_id",
        "rule_id",
        "evaluated_at",
        "hit_flag",
        "score_contribution",
        "evaluated_values",
        "reason_code",
        "execution_order",
    ],
    "alerts": [
        "alert_id",
        "simulation_run_id",
        "scenario_code",
        "primary_rule_id",
        "decision_outcome_id",
        "entity_type",
        "entity_id",
        "customer_id",
        "account_id",
        "transaction_id",
        "application_id",
        "triggered_at",
        "final_risk_score_100",
        "severity",
        "alert_status",
        "alert_reason",
        "score_explanation",
        "assigned_to",
        "closed_at",
        "updated_at",
    ],
    "cases": [
        "case_id",
        "simulation_run_id",
        "case_type",
        "primary_customer_id",
        "primary_account_id",
        "primary_application_id",
        "primary_alert_id",
        "created_at",
        "assigned_team",
        "case_priority",
        "case_status",
        "resolution_at",
        "resolution_reason",
        "analyst_id",
        "loss_amount",
        "prevented_loss_amount",
    ],
    "verification_results": [
        "verification_id",
        "simulation_run_id",
        "owner_domain",
        "transaction_id",
        "application_id",
        "alert_id",
        "case_id",
        "verified_at",
        "verification_label",
        "review_outcome",
        "loss_amount",
        "prevented_loss_amount",
    ],
    "fraud_ground_truth": [
        "fraud_event_id",
        "simulation_run_id",
        "owner_domain",
        "scenario_code",
        "primary_customer_id",
        "primary_account_id",
        "primary_transaction_id",
        "primary_application_id",
        "start_at",
        "end_at",
        "fraud_label",
        "fraud_outcome",
        "injection_method",
        "expected_rule_codes",
        "expected_decision_flag",
        "loss_amount",
    ],
}

ORDER = list(M)


def gen(table):
    fn = globals()["g_" + table]
    write(table, M[table], fn())


def g_simulation_runs():
    return [
        dict(
            simulation_run_id=RUN,
            run_name="MVP Fraud Simulation",
            dataset_version="1.0.0",
            random_seed=SEED,
            started_at=dt(BASE),
            completed_at=dt(BASE + timedelta(minutes=5)),
            run_status="COMPLETED",
            configuration=CFG,
            created_by="python_generator",
        )
    ]


def g_customers():
    r = rfor("customers")
    n = CFG["customer_count"]
    synth = set(r.sample(range(n), max(8, int(n * CFG["loan_fraud_rate"]))))
    mule = set(r.sample([i for i in range(n) if i not in synth], max(8, int(n * 0.02))))
    out = []
    for i in range(n):
        p, _, _ = r.choice(PROV)
        typ = "individual" if r.random() < 0.97 else "sme"
        seg = r.choice(
            ["student", "mass", "payroll", "affluent"]
            if typ == "individual"
            else ["sme"]
        )
        dob = date(r.randint(1960, 2004), r.randint(1, 12), r.randint(1, 28))
        on = date(2021, 1, 1) + timedelta(days=r.randint(0, 1900))
        cid = f"{RUN}_CUS_{i + 1:06d}"
        out.append(
            dict(
                customer_id=cid,
                simulation_run_id=RUN,
                customer_type=typ,
                full_name=nm(r),
                gender=r.choice(["M", "F", "U"]),
                dob=ds(dob),
                id_number_hash=h(f"ID{i}"),
                phone_hash=h(f"PH{i}"),
                email_hash=h(f"EM{i}"),
                province=p,
                address_cluster_id=f"ADDR_{i % 180:04d}",
                phone_cluster_id=f"PHC_{i % 260:04d}",
                occupation_group=r.choice(OCC),
                income_band=r.choice(["<5M", "5-10M", "10-20M", "20-40M", ">40M"]),
                customer_segment=seg,
                onboarding_channel=r.choice(
                    ["branch", "ekyc", "partner", "loan_application"]
                ),
                onboarding_date=ds(on),
                kyc_level=r.choice(
                    ["basic", "standard", "biometric_verified", "enhanced"]
                ),
                base_risk_level=r.choices(["Low", "Medium", "High"], [70, 25, 5])[0],
                customer_status=r.choices(
                    ["active", "inactive", "blocked", "closed"], [95, 2, 2, 1]
                )[0],
                is_synthetic_identity_seed=i in synth,
                is_mule_candidate_seed=i in mule,
                created_at=dt(BASE),
            )
        )
    return out


def g_accounts():
    r = rfor("accounts")
    out = []
    j = 1
    for c in read("customers"):
        for _ in range(1 + (r.random() < 0.25)):
            aid = f"{RUN}_ACC_{j:06d}"
            st = r.choices(["active", "dormant", "frozen", "closed"], [95, 3, 1, 1])[0]
            od = date.fromisoformat(c["onboarding_date"]) + timedelta(
                days=r.randint(0, 90)
            )
            daily_transfer_limit = r.choice([50000000, 100000000, 300000000])
            single_txn_limit = r.choice(
                [
                    limit
                    for limit in [20000000, 50000000, 100000000]
                    if limit <= daily_transfer_limit
                ]
            )
            out.append(
                dict(
                    account_id=aid,
                    simulation_run_id=RUN,
                    customer_id=c["customer_id"],
                    account_no_hash=h(aid),
                    account_type=r.choice(["CASA", "payroll", "savings", "business"]),
                    account_currency="VND",
                    open_date=ds(od),
                    status=st,
                    branch_code=r.choice(["HN001", "HCM001", "DN001"]),
                    account_opening_channel=r.choice(
                        ["branch", "ekyc", "partner", "migration"]
                    ),
                    home_province=c["province"],
                    daily_transfer_limit=daily_transfer_limit,
                    single_txn_limit=single_txn_limit,
                    average_balance=r.randint(500000, 200000000),
                    dormant_since=(
                        dt(BASE - timedelta(days=r.randint(190, 500)))
                        if st == "dormant"
                        else ""
                    ),
                    created_at=dt(BASE),
                )
            )
            j += 1
    return out


def g_devices():
    r = rfor("devices")
    out = []
    for i, c in enumerate(read("customers"), 1):
        risk = c["is_synthetic_identity_seed"] == "true"
        out.append(
            dict(
                device_id=f"{RUN}_DEV_{i:06d}",
                simulation_run_id=RUN,
                device_fingerprint=h(f"DEV{i}"),
                device_type=r.choice(["mobile", "desktop", "tablet"]),
                os=r.choice(["Android 14", "iOS 18", "Windows 11"]),
                first_seen_at=dt(BASE - timedelta(days=r.randint(1, 900))),
                trust_status=(
                    "suspicious"
                    if risk
                    else r.choices(["trusted", "new", "blocked"], [85, 14, 1])[0]
                ),
                is_emulator=risk and r.random() < 0.7,
                is_rooted_or_jailbroken=risk and r.random() < 0.5,
                device_risk_score=r.randint(70, 98) if risk else r.randint(0, 35),
                account_login_count=r.randint(1, 100),
                created_at=dt(BASE),
            )
        )
    return out


def g_login_sessions():
    r = rfor("sessions")
    dev = {c["customer_id"]: d for c, d in zip(read("customers"), read("devices"))}
    cust = {c["customer_id"]: c for c in read("customers")}
    out = []
    j = 1
    for a in read("accounts"):
        c = cust[a["customer_id"]]
        for k in range(r.randint(1, 4)):
            fraud = c["is_mule_candidate_seed"] == "true" and k == 0
            p, lat, lon = (
                r.choice(PROV)
                if fraud
                else next(x for x in PROV if x[0] == c["province"])
            )
            t = BASE - timedelta(days=r.randint(0, 30), hours=r.randint(0, 23))
            d = dev[c["customer_id"]]
            out.append(
                dict(
                    session_id=f"{RUN}_SES_{j:07d}",
                    simulation_run_id=RUN,
                    account_id=a["account_id"],
                    customer_id=a["customer_id"],
                    device_id=d["device_id"],
                    login_at=dt(t),
                    ip_address=f"10.{j % 255}.{j * 3 % 255}.{j * 7 % 254 + 1}",
                    province=p,
                    country="VN",
                    latitude=lat,
                    longitude=lon,
                    geo_source="gps",
                    vpn_flag=fraud,
                    proxy_flag=False,
                    login_result="success",
                    failure_reason="",
                    auth_method="password",
                    is_new_device=fraud,
                    is_new_location=fraud,
                    session_risk_score=90 if fraud else r.randint(0, 30),
                    session_end_at=dt(t + timedelta(minutes=r.randint(30, 240))),
                )
            )
            j += 1
    return out


def g_beneficiaries():
    r = rfor("beneficiaries")
    cust = {c["customer_id"]: c for c in read("customers")}
    out = []
    j = 1
    for a in read("accounts"):
        for _ in range(r.randint(1, 3)):
            risk = cust[a["customer_id"]]["is_mule_candidate_seed"] == "true"
            out.append(
                dict(
                    beneficiary_id=f"{RUN}_BEN_{j:07d}",
                    simulation_run_id=RUN,
                    account_id=a["account_id"],
                    beneficiary_account_hash=h(f"BEN{j}"),
                    beneficiary_bank=r.choice(BANKS),
                    beneficiary_name=nm(r),
                    # Background beneficiaries predate the 30-day transaction window.
                    # Fresh-beneficiary behavior is injected explicitly by scenarios.
                    added_at=dt(BASE - timedelta(days=r.randint(31, 300))),
                    added_channel="mobile",
                    status="active",
                    is_internal_bank=r.random() < 0.35,
                    beneficiary_risk_level=(
                        "High"
                        if risk
                        else r.choices(["Low", "Medium", "High"], [80, 18, 2])[0]
                    ),
                    mule_cluster_id=f"MULE_{j % 3}" if risk else "",
                )
            )
            j += 1
    return out


def g_account_change_events():
    r = rfor("changes")
    dev = {
        c["customer_id"]: d["device_id"]
        for c, d in zip(read("customers"), read("devices"))
    }
    cust = {c["customer_id"]: c for c in read("customers")}
    out = []
    j = 1
    for a in read("accounts"):
        risk = cust[a["customer_id"]]["is_mule_candidate_seed"] == "true"
        if risk or r.random() < 0.18:
            t = BASE - timedelta(days=r.randint(0, 20), minutes=r.randint(5, 200))
            out.append(
                dict(
                    change_event_id=f"{RUN}_CHG_{j:06d}",
                    simulation_run_id=RUN,
                    account_id=a["account_id"],
                    customer_id=a["customer_id"],
                    changed_at=dt(t),
                    change_type=r.choice(
                        ["phone", "password", "trusted_device", "transfer_limit"]
                    ),
                    channel="mobile",
                    device_id=dev[a["customer_id"]],
                    verification_method="sms_otp",
                    change_result="success",
                    old_value_hash=h(f"O{j}"),
                    new_value_hash=h(f"N{j}"),
                    is_sensitive_change=True,
                )
            )
            j += 1
    return out


def g_transactions():
    r = rfor("tx")
    cust = {c["customer_id"]: c for c in read("customers")}
    ses = {}
    ben = {}
    for x in read("login_sessions"):
        ses.setdefault(x["account_id"], []).append(x)
    for x in read("beneficiaries"):
        ben.setdefault(x["account_id"], []).append(x)
    accs = read("accounts")
    internal = [a["account_id"] for a in accs]
    out = []
    j = 1
    for a in accs:
        bal = float(a["average_balance"]) + 50000000
        n = max(3, int(r.gauss(CFG["avg_transactions_per_account"], 3)))
        c = cust[a["customer_id"]]
        sess_sorted = sorted(ses[a["account_id"]], key=lambda x: x["login_at"])
        ben_sorted = sorted(ben[a["account_id"]], key=lambda x: x["added_at"])
        scheduled = []
        for _ in range(n):
            chosen_session = r.choice(sess_sorted)
            login_at = datetime.fromisoformat(chosen_session["login_at"])
            session_end_at = datetime.fromisoformat(chosen_session["session_end_at"])
            available_seconds = max(
                1, int((session_end_at - login_at).total_seconds()) - 1
            )
            transaction_at = login_at + timedelta(
                seconds=r.randint(1, available_seconds)
            )
            scheduled.append((transaction_at, chosen_session))
        scheduled.sort(key=lambda item: item[0])
        for k, (t, s) in enumerate(scheduled):
            fraud = c["is_mule_candidate_seed"] == "true" and k >= n - 2
            tt = dt(t)
            elig_b = [x for x in ben_sorted if x["added_at"] <= tt]
            if not elig_b:
                raise RuntimeError(
                    f"no eligible beneficiary for {a['account_id']} at {tt}"
                )
            b = r.choice(elig_b)
            amt = (
                r.randint(20000, 3000000)
                if not fraud
                else r.randint(25000000, 90000000)
            )
            direct = "DEBIT" if r.random() < 0.82 else "CREDIT"
            before = bal
            bal = max(0, bal - amt) if direct == "DEBIT" else bal + amt
            out.append(
                dict(
                    transaction_id=f"{RUN}_TXN_{j:08d}",
                    simulation_run_id=RUN,
                    account_id=a["account_id"],
                    customer_id=a["customer_id"],
                    session_id=s["session_id"],
                    device_id=s["device_id"],
                    beneficiary_id=b["beneficiary_id"] if direct == "DEBIT" else "",
                    transaction_at=tt,
                    amount=amt,
                    currency="VND",
                    direction=direct,
                    transaction_type="transfer",
                    channel=r.choice(["mobile", "web", "api"]),
                    counterparty_account_hash=b["beneficiary_account_hash"],
                    counterparty_bank=b["beneficiary_bank"],
                    counterparty_internal_account_id=(
                        r.choice(internal)
                        if b["is_internal_bank"] == "true" and r.random() < 0.5
                        else ""
                    ),
                    merchant_id="",
                    merchant_category_code="",
                    ip_address=s["ip_address"],
                    province=s["province"],
                    country="VN",
                    vpn_flag=fraud,
                    proxy_flag=False,
                    status="success",
                    failure_reason="",
                    balance_before=round(before, 2),
                    balance_after=round(bal, 2),
                    created_at=dt(BASE),
                )
            )
            j += 1
    return out


def g_transaction_features():
    out = []
    by = {}
    for x in read("transactions"):
        by.setdefault(x["account_id"], []).append(x)
    for xs in by.values():
        xs.sort(key=lambda x: x["transaction_at"])
        amounts = [float(x["amount"]) for x in xs]
        med = sorted(amounts)[len(amounts) // 2]
        for i, x in enumerate(xs):
            fraud = float(x["amount"]) > 20000000
            out.append(
                dict(
                    transaction_id=x["transaction_id"],
                    feature_version="v1",
                    computed_at=x["transaction_at"],
                    is_new_device=fraud,
                    is_new_beneficiary=fraud,
                    is_after_sensitive_change=fraud,
                    txn_count_10m=4 if fraud else 1,
                    txn_count_1h=min(i + 1, 8),
                    txn_amount_sum_24h=sum(amounts[max(0, i - 10) : i + 1]),
                    amount_to_median_ratio=round(float(x["amount"]) / max(med, 1), 4),
                    failed_auth_count_30m=3 if fraud else 0,
                    time_since_beneficiary_added_minutes=8 if fraud else 5000,
                    time_since_sensitive_change_minutes=10 if fraud else "",
                    features={"fraud_seed": fraud},
                )
            )
    return out


def g_auth_events():
    r = rfor("auth")
    out = []
    j = 1
    for x in read("transactions"):
        if r.random() < 0.35:
            risk = float(x["amount"]) > 20000000
            out.append(
                dict(
                    auth_event_id=f"{RUN}_AUT_{j:08d}",
                    simulation_run_id=RUN,
                    transaction_id=x["transaction_id"],
                    session_id="",
                    change_event_id="",
                    account_id=x["account_id"],
                    customer_id=x["customer_id"],
                    auth_at=x["transaction_at"],
                    auth_method="sms_otp",
                    auth_result="failed" if risk and r.random() < 0.4 else "success",
                    failed_attempt_count=3 if risk else 0,
                    auth_risk_score=85 if risk else 10,
                )
            )
            j += 1
    return out


def g_sales_points():
    return [
        dict(
            sales_point_id=f"{RUN}_SP_{i:03d}",
            simulation_run_id=RUN,
            sales_point_name=f"Điểm bán {p}",
            sales_point_address=f"{10 + i} Đường Trung Tâm, {p}",
            province=p,
            region="North" if p in ["Hà Nội", "Hải Phòng"] else "South/Central",
            opened_at="2022-01-01",
            monthly_application_baseline=60,
            status="active",
            created_at=dt(BASE),
        )
        for i, (p, _, _) in enumerate(PROV, 1)
    ]


def g_sales_agents():
    r = rfor("agents")
    out = []
    j = 1
    for sp in read("sales_points"):
        for _ in range(5):
            out.append(
                dict(
                    sales_agent_id=f"{RUN}_AG_{j:04d}",
                    simulation_run_id=RUN,
                    sales_point_id=sp["sales_point_id"],
                    sales_agent_name=nm(r),
                    join_date="2023-01-01",
                    role="sales",
                    monthly_application_baseline=20,
                    status="active",
                    created_at=dt(BASE),
                )
            )
            j += 1
    return out


def g_loan_applications():
    r = rfor("apps")
    cs = read("customers")
    dev = read("devices")
    sps = read("sales_points")
    ags = read("sales_agents")
    by = {}
    for a in ags:
        by.setdefault(a["sales_point_id"], []).append(a)
    out = []
    j = 1
    for i, c in enumerate(cs):
        if r.random() > CFG["loan_application_rate"]:
            continue
        sp = r.choice(sps)
        ag = r.choice(by[sp["sales_point_id"]])
        fraud = c["is_synthetic_identity_seed"] == "true"
        at = BASE - timedelta(days=r.randint(5, 120))
        approved = not fraud or r.random() < 0.55
        status = (
            "disbursed"
            if approved and r.random() < 0.75
            else ("approved" if approved else "rejected")
        )
        out.append(
            dict(
                application_id=f"{RUN}_APP_{j:06d}",
                simulation_run_id=RUN,
                customer_id=c["customer_id"],
                application_at=dt(at),
                loan_amount=r.choice([20000000, 30000000, 50000000, 80000000]),
                loan_term_months=r.choice([6, 12, 18, 24]),
                loan_product="cash_loan",
                loan_purpose="consumption",
                application_channel=r.choice(
                    ["branch", "pos", "online", "partner", "call_center"]
                ),
                sales_point_id=sp["sales_point_id"],
                sales_agent_id=ag["sales_agent_id"],
                application_status=status,
                credit_underwriting_result="pass" if approved else "fail",
                decision_at=dt(at + timedelta(hours=12)),
                device_id=dev[i]["device_id"],
                ip_address=f"172.16.{i % 255}.{i * 7 % 254 + 1}",
                is_vpn=fraud,
                is_proxy=False,
                is_emulator=fraud,
                created_at=dt(BASE),
            )
        )
        j += 1
    return out


def g_applicant_declared_profiles():
    r = rfor("dp")
    cs = {c["customer_id"]: c for c in read("customers")}
    out = []
    for i, a in enumerate(read("loan_applications"), 1):
        c = cs[a["customer_id"]]
        f = c["is_synthetic_identity_seed"] == "true"
        out.append(
            dict(
                declared_profile_id=f"{RUN}_DPR_{i:06d}",
                simulation_run_id=RUN,
                application_id=a["application_id"],
                customer_id=a["customer_id"],
                declared_full_name=c["full_name"] if not f else nm(r),
                declared_id_number_hash=c["id_number_hash"],
                declared_dob=c["dob"],
                declared_phone_hash=c["phone_hash"] if not f else h(f"FAKE{i}"),
                declared_email_hash=c["email_hash"],
                declared_permanent_address=f"12 Đường A, {c['province']}",
                declared_current_address=f"34 Đường B, {c['province']}",
                declared_marital_status="married",
                declared_dependents=1,
                address_cluster_id=f"APPADDR_{i % 90}",
                profile_similarity_cluster_id=f"SYN_{i % 4}" if f else "",
                address_quality_score=35 if f else 90,
                created_at=a["created_at"],
            )
        )
    return out


def g_employment_income_profiles():
    cs = {c["customer_id"]: c for c in read("customers")}
    out = []
    for i, a in enumerate(read("loan_applications"), 1):
        c = cs[a["customer_id"]]
        f = c["is_synthetic_identity_seed"] == "true"
        out.append(
            dict(
                employment_id=f"{RUN}_EMP_{i:06d}",
                simulation_run_id=RUN,
                application_id=a["application_id"],
                occupation_group=c["occupation_group"],
                employer_name=f"Công ty {i % 120}",
                employer_phone_hash=h(f"EMP{i % 10 if f else i}"),
                employer_phone_cluster_id=f"EPH_{i % 10 if f else i}",
                employer_phone_verification_status="suspicious" if f else "verified",
                is_employer_phone_reused=f,
                employer_address="KCN A",
                employment_start_date="2022-01-01",
                months_at_employer=55,
                declared_monthly_income=50000000 if f else 18000000,
                income_document_type="payslip",
                employer_cluster_id=f"EMPCL_{i % 8 if f else i}",
                created_at=a["created_at"],
            )
        )
    return out


def g_reference_contacts():
    r = rfor("refs")
    cs = {c["customer_id"]: c for c in read("customers")}
    out = []
    j = 1
    for a in read("loan_applications"):
        f = cs[a["customer_id"]]["is_synthetic_identity_seed"] == "true"
        for order in [1, 2]:
            out.append(
                dict(
                    reference_id=f"{RUN}_REF_{j:07d}",
                    simulation_run_id=RUN,
                    application_id=a["application_id"],
                    reference_name=nm(r),
                    relationship="friend",
                    reference_phone_hash=h(f"REF{j % 8 if f else j}"),
                    phone_reuse_count=8 if f else 1,
                    reference_quality_score=35 if f else 90,
                    reference_order=order,
                    verification_status="suspicious" if f else "verified",
                    created_at=a["created_at"],
                )
            )
            j += 1
    return out


def g_application_documents():
    cs = {c["customer_id"]: c for c in read("customers")}
    out = []
    j = 1
    for a in read("loan_applications"):
        f = cs[a["customer_id"]]["is_synthetic_identity_seed"] == "true"
        for typ in ["id_card_front", "id_card_back", "selfie", "payslip"]:
            out.append(
                dict(
                    document_id=f"{RUN}_DOC_{j:07d}",
                    simulation_run_id=RUN,
                    application_id=a["application_id"],
                    document_type=typ,
                    document_hash=h(f"DOC{j % 6 if f else j}"),
                    submitted_at=a["application_at"],
                    ocr_quality_score=90,
                    tamper_score=85
                    if f and typ in ["id_card_front", "payslip"]
                    else 10,
                    duplicate_document_hash_count=5 if f else 1,
                    id_front_back_match_flag=not f,
                    id_expired_flag=False,
                    face_match_score=0.5 if f else 0.95,
                    liveness_result=(
                        "fail"
                        if f and typ == "selfie"
                        else ("pass" if typ == "selfie" else "not_applicable")
                    ),
                    document_result="manual_review" if f else "accepted",
                    created_at=a["created_at"],
                )
            )
            j += 1
    return out


def g_credit_bureau_snapshots():
    cs = {c["customer_id"]: c for c in read("customers")}
    out = []
    for i, a in enumerate(read("loan_applications"), 1):
        f = cs[a["customer_id"]]["is_synthetic_identity_seed"] == "true"
        out.append(
            dict(
                bureau_snapshot_id=f"{RUN}_CIC_{i:06d}",
                simulation_run_id=RUN,
                application_id=a["application_id"],
                bureau_score=450 if f else 700,
                active_loan_count=4 if f else 1,
                dpd_max_12m=60 if f else 0,
                recent_inquiry_count=6 if f else 1,
                thin_file_flag=f,
                bureau_match_result="partial_match" if f else "full_match",
                snapshot_at=a["application_at"],
                created_at=a["created_at"],
            )
        )
    return out


def g_disbursement_accounts():
    cs = {c["customer_id"]: c for c in read("customers")}
    acc = {}
    for x in read("accounts"):
        acc.setdefault(x["customer_id"], x["account_id"])
    out = []
    for i, a in enumerate(
        [
            x
            for x in read("loan_applications")
            if x["application_status"] == "disbursed"
        ],
        1,
    ):
        c = cs[a["customer_id"]]
        f = c["is_synthetic_identity_seed"] == "true"
        t = datetime.fromisoformat(a["decision_at"]) + timedelta(hours=5)
        out.append(
            dict(
                disbursement_id=f"{RUN}_DIS_{i:06d}",
                simulation_run_id=RUN,
                application_id=a["application_id"],
                receiving_account_hash=h(f"DISB{i % 3 if f else i}"),
                receiving_account_name=c["full_name"] if not f else "Third Party",
                receiving_bank="VCB",
                same_as_applicant=not f,
                account_reuse_count=5 if f else 1,
                linked_account_id=acc.get(a["customer_id"], "") if not f else "",
                disbursement_status="completed",
                disbursed_at=dt(t),
                disbursed_amount=a["loan_amount"],
                created_at=a["created_at"],
            )
        )
    return out


def g_loan_repayment_outcomes():
    apps = {a["application_id"]: a for a in read("loan_applications")}
    cs = {c["customer_id"]: c for c in read("customers")}
    out = []
    for i, d in enumerate(read("disbursement_accounts"), 1):
        a = apps[d["application_id"]]
        f = cs[a["customer_id"]]["is_synthetic_identity_seed"] == "true"
        dis = datetime.fromisoformat(d["disbursed_at"])
        dpd = 95 if f else 0
        due = float(a["loan_amount"]) / int(a["loan_term_months"])
        paid = 0 if f else due
        out.append(
            dict(
                loan_outcome_id=f"{RUN}_OUT_{i:06d}",
                simulation_run_id=RUN,
                application_id=a["application_id"],
                disbursed_at=d["disbursed_at"],
                first_due_date=ds(dis.date() + timedelta(days=30)),
                first_payment_status="missed" if f else "paid_on_time",
                first_payment_days_past_due=dpd,
                contact_status_after_disbursement="lost_contact"
                if f
                else "contactable",
                dpd_30_flag=f,
                dpd_60_flag=f,
                dpd_90_flag=f,
                installments_due=1,
                installments_paid_on_time=0 if f else 1,
                total_amount_due=due,
                total_amount_paid=paid,
                outstanding_balance=float(a["loan_amount"]) - paid,
                early_default_flag=f,
                writeoff_amount=float(a["loan_amount"]) * 0.7 if f else 0,
                loan_performance_status="default" if f else "performing",
                credit_performance_label="default" if f else "good",
                fraud_outcome_label="confirmed_fraud" if f else "legitimate",
                outcome_observed_at=dt(dis + timedelta(days=100)),
                created_at=d["created_at"],
            )
        )
    return out


RULES = [
    ("R_TXN_ATO_001", "ATO", "transaction", "ATO", "device", "Critical", 90, "HOLD"),
    (
        "R_TXN_VEL_001",
        "Velocity",
        "transaction",
        "VELOCITY",
        "velocity",
        "High",
        70,
        "CHALLENGE",
    ),
    (
        "R_TXN_MULE_001",
        "Mule",
        "transaction",
        "MULE",
        "network",
        "Critical",
        90,
        "HOLD",
    ),
    (
        "R_TXN_GEO_001",
        "Impossible travel",
        "transaction",
        "IMPOSSIBLE_TRAVEL",
        "anomaly",
        "High",
        80,
        "CHALLENGE",
    ),
    (
        "R_LOAN_SYN_001",
        "Synthetic identity",
        "loan",
        "SYNTHETIC_IDENTITY",
        "identity",
        "Critical",
        95,
        "DECLINE",
    ),
    (
        "R_LOAN_DOC_001",
        "Document fraud",
        "loan",
        "DOCUMENT_FRAUD",
        "document",
        "High",
        80,
        "MANUAL_REVIEW",
    ),
    (
        "R_LOAN_CIC_001",
        "Loan stacking",
        "loan",
        "LOAN_STACKING",
        "velocity",
        "High",
        75,
        "MANUAL_REVIEW",
    ),
    (
        "R_LOAN_DIS_001",
        "Shared disbursement",
        "loan",
        "SHARED_DISBURSEMENT",
        "network",
        "Critical",
        90,
        "HOLD",
    ),
]


def g_rules():
    return [
        dict(
            rule_id=f"RULE_{i:03d}",
            rule_code=x[0],
            rule_name=x[1],
            owner_domain=x[2],
            scenario_code=x[3],
            rule_type=x[4],
            description=x[1],
            severity=x[5],
            base_score=x[6],
            decision_flag=x[7],
            status="active",
            created_by="generator",
            created_at=dt(BASE),
        )
        for i, x in enumerate(RULES, 1)
    ]


def g_decision_outcomes():
    out = []
    j = 1
    for x in read("transactions"):
        risk = float(x["amount"]) > 20000000
        out.append(
            dict(
                decision_outcome_id=f"{RUN}_DEC_{j:08d}",
                simulation_run_id=RUN,
                message_type="transaction",
                entity_type="transaction",
                entity_id=x["transaction_id"],
                transaction_id=x["transaction_id"],
                application_id="",
                decision_at=x["transaction_at"],
                decision_flag="HOLD" if risk else "ACCEPT",
                risk_score_100=92 if risk else 20,
                reason_codes=arr(["ATO_SEQUENCE", "HIGH_AMOUNT"] if risk else []),
                alert_recommended=risk,
                alert_type="ATO" if risk else "",
                triage_queue="TXN_HIGH" if risk else "",
                processing_latency_ms=25,
                created_at=x["created_at"],
            )
        )
        j += 1
    cs = {c["customer_id"]: c for c in read("customers")}
    for a in read("loan_applications"):
        risk = cs[a["customer_id"]]["is_synthetic_identity_seed"] == "true"
        out.append(
            dict(
                decision_outcome_id=f"{RUN}_DEC_{j:08d}",
                simulation_run_id=RUN,
                message_type="loan_application",
                entity_type="loan_application",
                entity_id=a["application_id"],
                transaction_id="",
                application_id=a["application_id"],
                decision_at=a["decision_at"],
                decision_flag="DECLINE" if risk else "ACCEPT",
                risk_score_100=95 if risk else 20,
                reason_codes=arr(["SYNTHETIC_IDENTITY", "DOC_TAMPER"] if risk else []),
                alert_recommended=risk,
                alert_type="LOAN_FRAUD" if risk else "",
                triage_queue="LOAN_HIGH" if risk else "",
                processing_latency_ms=80,
                created_at=a["created_at"],
            )
        )
        j += 1
    return out


def g_rule_hits():
    rules = read("rules")
    out = []
    j = 1
    for d in read("decision_outcomes"):
        pool = [
            x
            for x in rules
            if x["owner_domain"]
            == ("transaction" if d["message_type"] == "transaction" else "loan")
        ]
        for k, ru in enumerate(pool, 1):
            hit = d["alert_recommended"] == "true" and k <= 2
            out.append(
                dict(
                    rule_hit_id=f"{RUN}_RH_{j:09d}",
                    simulation_run_id=RUN,
                    decision_outcome_id=d["decision_outcome_id"],
                    rule_id=ru["rule_id"],
                    evaluated_at=d["decision_at"],
                    hit_flag=hit,
                    score_contribution=float(ru["base_score"]) / 2 if hit else 0,
                    evaluated_values={"entity_id": d["entity_id"]},
                    reason_code=ru["rule_code"] if hit else "",
                    execution_order=k,
                )
            )
            j += 1
    return out


def g_alerts():
    dec = [d for d in read("decision_outcomes") if d["alert_recommended"] == "true"]
    hits = {}
    rules = {r["rule_id"]: r for r in read("rules")}
    tx = {x["transaction_id"]: x for x in read("transactions")}
    apps = {a["application_id"]: a for a in read("loan_applications")}
    for hrow in read("rule_hits"):
        if hrow["hit_flag"] == "true":
            hits.setdefault(hrow["decision_outcome_id"], []).append(hrow)
    out = []
    for i, d in enumerate(dec, 1):
        ph = hits[d["decision_outcome_id"]][0]
        ru = rules[ph["rule_id"]]
        if d["message_type"] == "transaction":
            x = tx[d["transaction_id"]]
            cid = x["customer_id"]
            aid = x["account_id"]
            tid = x["transaction_id"]
            app = ""
            et = "transaction"
        else:
            x = apps[d["application_id"]]
            cid = x["customer_id"]
            aid = ""
            tid = ""
            app = x["application_id"]
            et = "loan_application"
        out.append(
            dict(
                alert_id=f"{RUN}_ALT_{i:06d}",
                simulation_run_id=RUN,
                scenario_code=ru["scenario_code"],
                primary_rule_id=ru["rule_id"],
                decision_outcome_id=d["decision_outcome_id"],
                entity_type=et,
                entity_id=d["entity_id"],
                customer_id=cid,
                account_id=aid,
                transaction_id=tid,
                application_id=app,
                triggered_at=d["decision_at"],
                final_risk_score_100=d["risk_score_100"],
                severity=ru["severity"],
                alert_status="open",
                alert_reason=d["alert_type"],
                score_explanation={"risk_score": d["risk_score_100"]},
                assigned_to="",
                closed_at="",
                updated_at=d["created_at"],
            )
        )
    return out


def g_cases():
    out = []
    for i, a in enumerate(read("alerts"), 1):
        loan = a["entity_type"] == "loan_application"
        conf = i % 4 != 0
        c = datetime.fromisoformat(a["triggered_at"]) + timedelta(minutes=10)
        res = c + timedelta(hours=12)
        out.append(
            dict(
                case_id=f"{RUN}_CASE_{i:06d}",
                simulation_run_id=RUN,
                case_type="loan_fraud" if loan else "transaction_fraud",
                primary_customer_id=a["customer_id"],
                primary_account_id=a["account_id"],
                primary_application_id=a["application_id"],
                primary_alert_id=a["alert_id"],
                created_at=dt(c),
                assigned_team="Loan Fraud Ops" if loan else "Transaction Fraud Ops",
                case_priority=a["severity"],
                case_status="confirmed_fraud" if conf else "false_positive",
                resolution_at=dt(res),
                resolution_reason="Evidence confirmed"
                if conf
                else "Customer verified genuine",
                analyst_id=f"ANL_{i % 5 + 1}",
                loss_amount=5000000 if conf else 0,
                prevented_loss_amount=10000000 if conf else 0,
            )
        )
    return out


def g_verification_results():
    al = {a["alert_id"]: a for a in read("alerts")}
    out = []
    for i, c in enumerate(read("cases"), 1):
        a = al[c["primary_alert_id"]]
        loan = c["case_type"] == "loan_fraud"
        conf = c["case_status"] == "confirmed_fraud"
        out.append(
            dict(
                verification_id=f"{RUN}_VER_{i:06d}",
                simulation_run_id=RUN,
                owner_domain="loan" if loan else "transaction",
                transaction_id=a["transaction_id"],
                application_id=a["application_id"],
                alert_id=a["alert_id"],
                case_id=c["case_id"],
                verified_at=c["resolution_at"],
                verification_label="CONFIRMED_FRAUD" if conf else "FALSE_POSITIVE",
                review_outcome=c["resolution_reason"],
                loss_amount=c["loss_amount"],
                prevented_loss_amount=c["prevented_loss_amount"],
            )
        )
    return out


def g_fraud_ground_truth():
    al = {a["alert_id"]: a for a in read("alerts")}
    out = []
    for i, v in enumerate(read("verification_results"), 1):
        a = al[v["alert_id"]]
        conf = v["verification_label"] == "CONFIRMED_FRAUD"
        out.append(
            dict(
                fraud_event_id=f"{RUN}_FGT_{i:06d}",
                simulation_run_id=RUN,
                owner_domain=v["owner_domain"],
                scenario_code=a["scenario_code"],
                primary_customer_id=a["customer_id"],
                primary_account_id=a["account_id"],
                primary_transaction_id=a["transaction_id"],
                primary_application_id=a["application_id"],
                start_at=a["triggered_at"],
                end_at=v["verified_at"],
                fraud_label="confirmed_fraud" if conf else "false_positive_seed",
                fraud_outcome=v["review_outcome"],
                injection_method="deterministic_rare_scenario_seed",
                expected_rule_codes=arr([a["scenario_code"]]),
                expected_decision_flag=(
                    "DECLINE"
                    if conf and v["owner_domain"] == "loan"
                    else ("HOLD" if conf else "ACCEPT")
                ),
                loss_amount=v["loss_amount"],
            )
        )
    return out
