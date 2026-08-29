from __future__ import annotations
import csv
from datetime import datetime, timedelta
from pathlib import Path

from generators.engine import BASE, M, OUT, RUN, arr, dt, write

ROOT = Path(__file__).resolve().parent
RULES = [
    (
        "R_TXN_GEO_001",
        "Impossible Travel",
        "transaction",
        "TXN-01",
        "anomaly",
        "High",
        80,
        "CHALLENGE",
    ),
    (
        "R_TXN_DORMANT_001",
        "Dormant Awakening",
        "transaction",
        "TXN-02",
        "anomaly",
        "Critical",
        90,
        "HOLD",
    ),
    (
        "R_TXN_AUTH_001",
        "Brute Force Authentication",
        "transaction",
        "TXN-03",
        "velocity",
        "High",
        85,
        "CHALLENGE",
    ),
    (
        "R_TXN_VEL_001",
        "Velocity Burst",
        "transaction",
        "TXN-04",
        "velocity",
        "High",
        80,
        "HOLD",
    ),
    (
        "R_TXN_SCAM_001",
        "Rapid New Beneficiary Transfer",
        "transaction",
        "TXN-05",
        "anomaly",
        "High",
        80,
        "CHALLENGE",
    ),
    (
        "R_TXN_ATO_001",
        "Account Takeover Chain",
        "transaction",
        "TXN-06",
        "identity",
        "Critical",
        95,
        "HOLD",
    ),
    (
        "R_TXN_MULE_001",
        "Money Mule Network",
        "transaction",
        "TXN-07",
        "network",
        "Critical",
        95,
        "HOLD",
    ),
    (
        "R_TXN_DEVICE_001",
        "Emulator Bot Farm",
        "transaction",
        "TXN-08",
        "device",
        "Critical",
        90,
        "HOLD",
    ),
    (
        "R_TXN_INTERNAL_001",
        "Internal Fund Diversion",
        "transaction",
        "TXN-09",
        "manual",
        "Critical",
        95,
        "HOLD",
    ),
    (
        "R_LOAN_INCOME_001",
        "Income Mismatch",
        "loan",
        "LOAN-01",
        "anomaly",
        "High",
        75,
        "MANUAL_REVIEW",
    ),
    (
        "R_LOAN_CIC_001",
        "Loan Stacking",
        "loan",
        "LOAN-02",
        "velocity",
        "High",
        80,
        "MANUAL_REVIEW",
    ),
    (
        "R_LOAN_EMP_001",
        "Ghost Employer",
        "loan",
        "LOAN-03",
        "network",
        "High",
        80,
        "MANUAL_REVIEW",
    ),
    (
        "R_LOAN_REF_001",
        "Reference Recycling",
        "loan",
        "LOAN-04",
        "network",
        "High",
        75,
        "MANUAL_REVIEW",
    ),
    (
        "R_LOAN_DOC_001",
        "Document Integrity Failure",
        "loan",
        "LOAN-05",
        "document",
        "Critical",
        90,
        "DECLINE",
    ),
    (
        "R_LOAN_SYN_001",
        "Synthetic Identity Farm",
        "loan",
        "LOAN-06",
        "identity",
        "Critical",
        95,
        "DECLINE",
    ),
    (
        "R_LOAN_AGENT_001",
        "Sales Agent Collusion",
        "loan",
        "LOAN-07",
        "network",
        "Critical",
        90,
        "MANUAL_REVIEW",
    ),
    (
        "R_LOAN_DIS_001",
        "Shared Disbursement Ring",
        "loan",
        "LOAN-08",
        "network",
        "Critical",
        90,
        "HOLD",
    ),
    (
        "R_LOAN_BUSTOUT_001",
        "First Party Bust-Out",
        "loan",
        "LOAN-09",
        "anomaly",
        "Critical",
        95,
        "ALERT_ONLY",
    ),
]


def load_manifest():
    with (OUT / "scenario_manifest.csv").open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def build():
    man = load_manifest()
    used_rule_codes = {
        code
        for event in man
        for code in event["expected_rule_codes"].split("|")
        if code
    }
    rule_rows = []
    for i, x in enumerate((x for x in RULES if x[0] in used_rule_codes), 1):
        code, name, domain, sc, typ, sev, score, flag = x
        rule_rows.append(
            dict(
                rule_id=f"RULE_V2_{i:03d}",
                rule_code=code,
                rule_name=name,
                owner_domain=domain,
                scenario_code=sc,
                rule_type=typ,
                description=name,
                severity=sev,
                base_score=score,
                decision_flag=flag,
                status="active",
                created_by="scenario_engine_v2",
                created_at=dt(BASE),
            )
        )
    write("rules", M["rules"], rule_rows)
    rulemap = {x["rule_code"]: x for x in rule_rows}
    dec = []
    hits = []
    alerts = []
    cases = []
    vers = []
    truth = []
    rh = 1
    for i, e in enumerate(man, 1):
        did = f"{RUN}_V2_DEC_{i:06d}"
        is_tx = e["domain"] == "transaction"
        has_txn = is_tx and e["primary_transaction_id"]
        entity = (
            e["primary_transaction_id"]
            if has_txn
            else (e["primary_account_id"] if is_tx else e["primary_application_id"])
        )
        etype = (
            "transaction" if has_txn else ("account" if is_tx else "loan_application")
        )
        rules = e["expected_rule_codes"].split("|") if e["expected_rule_codes"] else []
        is_fp = e["fraud_label"] == "false_positive_seed"
        score = min(100, 65 + 10 * len(rules))
        alert_id = f"{RUN}_V2_ALT_{i:06d}"
        case_id = f"{RUN}_V2_CASE_{i:06d}"
        ver_id = f"{RUN}_V2_VER_{i:06d}"
        dec.append(
            dict(
                decision_outcome_id=did,
                simulation_run_id=RUN,
                message_type="transaction" if is_tx else "loan_application",
                entity_type=etype,
                entity_id=entity,
                transaction_id=e["primary_transaction_id"] if is_tx else "",
                application_id=e["primary_application_id"] if not is_tx else "",
                decision_at=e["end_at"],
                decision_flag=e["expected_decision_flag"],
                risk_score_100=score,
                reason_codes=arr(rules),
                alert_recommended=True,
                alert_type=e["scenario_code"],
                triage_queue="TXN_SCENARIO" if is_tx else "LOAN_SCENARIO",
                processing_latency_ms=35 if is_tx else 90,
                created_at=dt(BASE),
            )
        )
        for order, rc in enumerate(rules, 1):
            if rc not in rulemap:
                continue
            ru = rulemap[rc]
            hits.append(
                dict(
                    rule_hit_id=f"{RUN}_V2_RH_{rh:07d}",
                    simulation_run_id=RUN,
                    decision_outcome_id=did,
                    rule_id=ru["rule_id"],
                    evaluated_at=e["end_at"],
                    hit_flag=True,
                    score_contribution=min(float(ru["base_score"]) / len(rules), 100),
                    evaluated_values={
                        "scenario_code": e["scenario_code"],
                        "event_id": e["event_id"],
                    },
                    reason_code=rc,
                    execution_order=order,
                )
            )
            rh += 1
        primary = rulemap[rules[0]] if rules and rules[0] in rulemap else rule_rows[0]
        customer = e["primary_customer_id"]
        account = e["primary_account_id"]
        app = e["primary_application_id"]
        txn = e["primary_transaction_id"]
        alerts.append(
            dict(
                alert_id=alert_id,
                simulation_run_id=RUN,
                scenario_code=e["scenario_code"],
                primary_rule_id=primary["rule_id"],
                decision_outcome_id=did,
                entity_type=etype,
                entity_id=entity,
                customer_id=customer,
                account_id=account if is_tx else "",
                transaction_id=txn if is_tx else "",
                application_id=app if not is_tx else "",
                triggered_at=e["end_at"],
                final_risk_score_100=score,
                severity=e["severity"],
                alert_status="false_positive" if is_fp else "closed",
                alert_reason=e["description"],
                score_explanation={"rules": rules, "scenario_event": e["event_id"]},
                assigned_to="scenario_analyst",
                closed_at=dt(datetime.fromisoformat(e["end_at"]) + timedelta(hours=6)),
                updated_at=dt(BASE),
            )
        )
        cases.append(
            dict(
                case_id=case_id,
                simulation_run_id=RUN,
                case_type="transaction_fraud" if is_tx else "loan_fraud",
                primary_customer_id=customer,
                primary_account_id=account if is_tx else "",
                primary_application_id=app if not is_tx else "",
                primary_alert_id=alert_id,
                created_at=e["end_at"],
                assigned_team="Transaction Fraud Ops" if is_tx else "Loan Fraud Ops",
                case_priority=e["severity"],
                case_status="false_positive" if is_fp else "confirmed_fraud",
                resolution_at=dt(
                    datetime.fromisoformat(e["end_at"]) + timedelta(hours=6)
                ),
                resolution_reason=e["description"],
                analyst_id="ANL_SCENARIO",
                loss_amount=0,
                prevented_loss_amount=0 if is_fp else 10000000,
            )
        )
        vers.append(
            dict(
                verification_id=ver_id,
                simulation_run_id=RUN,
                owner_domain=e["domain"],
                transaction_id=txn if is_tx else "",
                application_id=app if not is_tx else "",
                alert_id=alert_id,
                case_id=case_id,
                verified_at=dt(
                    datetime.fromisoformat(e["end_at"]) + timedelta(hours=6)
                ),
                verification_label="FALSE_POSITIVE" if is_fp else "CONFIRMED_FRAUD",
                review_outcome=e["description"],
                loss_amount=0,
                prevented_loss_amount=0 if is_fp else 10000000,
            )
        )
        truth.append(
            dict(
                fraud_event_id=f"{RUN}_V2_FGT_{i:06d}",
                simulation_run_id=RUN,
                owner_domain=e["domain"],
                scenario_code=e["scenario_code"],
                primary_customer_id=customer,
                primary_account_id=account,
                primary_transaction_id=txn,
                primary_application_id=app,
                start_at=e["start_at"],
                end_at=e["end_at"],
                fraud_label=e["fraud_label"],
                fraud_outcome=e["description"],
                injection_method="scenario_blueprint_v2",
                expected_rule_codes=arr(rules),
                expected_decision_flag=e["expected_decision_flag"],
                loss_amount=0,
            )
        )
    write("decision_outcomes", M["decision_outcomes"], dec)
    write("rule_hits", M["rule_hits"], hits)
    write("alerts", M["alerts"], alerts)
    write("cases", M["cases"], cases)
    write("verification_results", M["verification_results"], vers)
    write("fraud_ground_truth", M["fraud_ground_truth"], truth)
    print("[OPS] built", len(dec), "scenario decisions and", len(hits), "rule hits")


if __name__ == "__main__":
    build()
