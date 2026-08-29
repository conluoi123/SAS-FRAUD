from __future__ import annotations
import csv
import json
import os
from pathlib import Path
from datetime import datetime, timedelta, date
from generators.engine import (
    ROOT,
    OUT,
    RUN,
    BASE,
    M,
    h,
    dt,
    ds,
    rfor,
    read,
    write,
    PROV,
)

CONFIG_PATH = Path(os.environ.get("FRAUD_CONFIG", ROOT / "config.json"))
if not CONFIG_PATH.is_absolute():
    CONFIG_PATH = ROOT / CONFIG_PATH
CFG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
COUNTS = CFG["scenario_counts"]
MANIFEST_COLS = [
    "event_id",
    "scenario_code",
    "domain",
    "primary_customer_id",
    "primary_account_id",
    "primary_transaction_id",
    "primary_application_id",
    "start_at",
    "end_at",
    "expected_rule_codes",
    "expected_decision_flag",
    "severity",
    "fraud_label",
    "description",
]
ENTITY_COLS = [
    "event_id",
    "scenario_code",
    "entity_type",
    "entity_id",
    "entity_role",
    "label_scope",
    "target_fraud",
    "hard_negative",
    "sample_weight",
    "valid_from",
    "valid_to",
]


class Store:
    def __init__(self):
        self.d = {t: read(t) for t in M if (OUT / f"{t}.csv").exists()}

    def rows(self, t):
        return self.d.setdefault(t, [])

    def save(self, t):
        write(t, M[t], self.d[t])

    def save_all(self):
        for t in self.d:
            if t in M:
                self.save(t)


def boolv(x):
    return str(x).lower() == "true"


def next_id(rows, col, prefix, width=7):
    return f"{RUN}_{prefix}_{len(rows) + 1:0{width}d}"


def by(rows, key):
    return {x[key]: x for x in rows}


def group(rows, key):
    d = {}
    for x in rows:
        d.setdefault(x[key], []).append(x)
    return d


def coherent_personas(s: Store):
    r = rfor("persona_v2")
    personas = {
        "student": {
            "ages": (18, 25),
            "income": ["<5M", "<5M", "5-10M"],
            "segment": ["student"],
            "occ": ["student"],
        },
        "worker": {
            "ages": (20, 50),
            "income": ["5-10M", "10-20M"],
            "segment": ["mass", "payroll"],
            "occ": ["factory", "driver", "sales"],
        },
        "professional": {
            "ages": (24, 55),
            "income": ["10-20M", "20-40M"],
            "segment": ["payroll", "mass"],
            "occ": ["office", "teacher", "healthcare", "engineer"],
        },
        "affluent": {
            "ages": (30, 65),
            "income": ["20-40M", ">40M"],
            "segment": ["affluent"],
            "occ": ["finance", "self_employed", "engineer"],
        },
        "sme": {
            "ages": (25, 65),
            "income": ["20-40M", ">40M"],
            "segment": ["sme"],
            "occ": ["self_employed"],
        },
    }
    today = date(2026, 8, 6)
    for c in s.rows("customers"):
        if c["customer_type"] == "sme":
            p = personas["sme"]
        else:
            age = today.year - date.fromisoformat(c["dob"]).year
            if age <= 24:
                p = personas["student"] if r.random() < 0.45 else personas["worker"]
            elif age <= 35:
                p = r.choice(
                    [
                        personas["worker"],
                        personas["professional"],
                        personas["professional"],
                    ]
                )
            elif age <= 55:
                p = r.choice(
                    [
                        personas["worker"],
                        personas["professional"],
                        personas["professional"],
                        personas["affluent"],
                    ]
                )
            else:
                p = r.choice([personas["professional"], personas["affluent"]])
        c["occupation_group"] = r.choice(p["occ"])
        c["income_band"] = r.choice(p["income"])
        c["customer_segment"] = r.choice(p["segment"])
        # Prevent impossible clean combinations. Fraud scenarios may override later.
        if c["occupation_group"] == "student" and c["income_band"] not in (
            "<5M",
            "5-10M",
        ):
            c["income_band"] = "5-10M"
    s.save("customers")


def append_manifest(
    man,
    event_id,
    code,
    domain,
    cust="",
    acc="",
    txn="",
    app="",
    start=None,
    end=None,
    rules=None,
    decision="HOLD",
    severity="High",
    label="confirmed_fraud",
    desc="",
):
    event_id = event_id if event_id.startswith(f"{RUN}_") else f"{RUN}_{event_id}"
    man.append(
        dict(
            event_id=event_id,
            scenario_code=code,
            domain=domain,
            primary_customer_id=cust,
            primary_account_id=acc,
            primary_transaction_id=txn,
            primary_application_id=app,
            start_at=dt(start or BASE),
            end_at=dt(end or (start or BASE) + timedelta(minutes=15)),
            expected_rule_codes="|".join(rules or []),
            expected_decision_flag=decision,
            severity=severity,
            fraud_label=label,
            description=desc,
        )
    )


def append_entity(
    entities,
    event_id,
    scenario_code,
    entity_type,
    entity_id,
    entity_role,
    label_scope,
    start,
    end,
):
    """Write an explicit event-to-entity label mapping for model datasets."""
    event_id = event_id if event_id.startswith(f"{RUN}_") else f"{RUN}_{event_id}"
    entities.append(
        dict(
            event_id=event_id,
            scenario_code=scenario_code,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_role=entity_role,
            label_scope=label_scope,
            target_fraud=1 if label_scope == "fraud" else 0,
            hard_negative=1 if label_scope == "hard_negative" else 0,
            sample_weight="",
            valid_from=dt(start),
            valid_to=dt(end),
        )
    )


def add_device(s, tag, emulator=False, rooted=False, risk=85):
    rows = s.rows("devices")
    did = f"{RUN}_SCN_DEV_{tag}"
    if any(x["device_id"] == did for x in rows):
        return did
    rows.append(
        dict(
            device_id=did,
            simulation_run_id=RUN,
            device_fingerprint=h(did),
            device_type="mobile",
            os="Android Emulator" if emulator else "Android 14",
            first_seen_at=dt(BASE),
            trust_status="suspicious",
            is_emulator=emulator,
            is_rooted_or_jailbroken=rooted,
            device_risk_score=risk,
            account_login_count=1,
            created_at=dt(BASE),
        )
    )
    return did


def add_session(
    s,
    tag,
    a,
    device,
    t,
    province="Hà Nội",
    lat=21.0285,
    lon=105.8542,
    newdev=True,
    newloc=True,
    vpn=False,
    proxy=False,
    risk=85,
    result="success",
):
    rows = s.rows("login_sessions")
    sid = f"{RUN}_SCN_SES_{tag}"
    rows.append(
        dict(
            session_id=sid,
            simulation_run_id=RUN,
            account_id=a["account_id"],
            customer_id=a["customer_id"],
            device_id=device,
            login_at=dt(t),
            ip_address=f"203.0.113.{(len(rows) % 240) + 1}",
            province=province,
            country="VN",
            latitude=lat,
            longitude=lon,
            geo_source="gps",
            vpn_flag=vpn,
            proxy_flag=proxy,
            login_result=result,
            failure_reason="" if result == "success" else "invalid_credentials",
            auth_method="password",
            is_new_device=newdev,
            is_new_location=newloc,
            session_risk_score=risk,
            session_end_at=dt(t + timedelta(minutes=45)),
        )
    )
    return sid


def add_bene(s, tag, a, t, risk="High", cluster="", status="active", internal=False):
    rows = s.rows("beneficiaries")
    bid = f"{RUN}_SCN_BEN_{tag}"
    rows.append(
        dict(
            beneficiary_id=bid,
            simulation_run_id=RUN,
            account_id=a["account_id"],
            beneficiary_account_hash=h(bid),
            beneficiary_bank="OTHER" if not internal else "VCB",
            beneficiary_name=f"Scenario Beneficiary {tag}",
            added_at=dt(t),
            added_channel="mobile",
            status=status,
            is_internal_bank=internal,
            beneficiary_risk_level=risk,
            mule_cluster_id=cluster,
        )
    )
    return bid


def add_change(s, tag, a, device, t, typ):
    rows = s.rows("account_change_events")
    cid = f"{RUN}_SCN_CHG_{tag}"
    rows.append(
        dict(
            change_event_id=cid,
            simulation_run_id=RUN,
            account_id=a["account_id"],
            customer_id=a["customer_id"],
            changed_at=dt(t),
            change_type=typ,
            channel="mobile",
            device_id=device,
            verification_method="sms_otp",
            change_result="success",
            old_value_hash=h(cid + "old"),
            new_value_hash=h(cid + "new"),
            is_sensitive_change=True,
        )
    )
    return cid


def add_txn(
    s,
    tag,
    a,
    sid,
    dev,
    bid,
    t,
    amount,
    typ="transfer",
    channel="mobile",
    direction="DEBIT",
    internal_acc="",
    status="success",
):
    rows = s.rows("transactions")
    tid = f"{RUN}_SCN_TXN_{tag}"
    before = max(float(a["average_balance"]), amount * 1.05)
    after = before - amount if direction == "DEBIT" else before + amount
    rows.append(
        dict(
            transaction_id=tid,
            simulation_run_id=RUN,
            account_id=a["account_id"],
            customer_id=a["customer_id"],
            session_id=sid,
            device_id=dev,
            beneficiary_id=bid if direction == "DEBIT" and bid else "",
            transaction_at=dt(t),
            amount=round(amount, 2),
            currency="VND",
            direction=direction,
            transaction_type=typ,
            channel=channel,
            counterparty_account_hash=h("CP" + tag),
            counterparty_bank="OTHER",
            counterparty_internal_account_id=internal_acc,
            merchant_id="",
            merchant_category_code="",
            ip_address="203.0.113.200",
            province="Hà Nội",
            country="VN",
            vpn_flag=False,
            proxy_flag=False,
            status=status,
            failure_reason="",
            balance_before=round(before, 2),
            balance_after=round(max(after, 0), 2),
            created_at=dt(BASE),
        )
    )
    return tid


def add_auth(
    s,
    tag,
    a,
    t,
    transaction="",
    session="",
    change="",
    result="failed",
    attempts=3,
    risk=95,
    method="password",
):
    rows = s.rows("auth_events")
    aid = f"{RUN}_SCN_AUT_{tag}"
    rows.append(
        dict(
            auth_event_id=aid,
            simulation_run_id=RUN,
            transaction_id=transaction,
            session_id=session,
            change_event_id=change,
            account_id=a["account_id"],
            customer_id=a["customer_id"],
            auth_at=dt(t),
            auth_method=method,
            auth_result=result,
            failed_attempt_count=attempts,
            auth_risk_score=risk,
        )
    )
    return aid


def choose_accounts(s, n, exclude=set()):
    return [a for a in s.rows("accounts") if a["account_id"] not in exclude][:n]


def inject_transaction(s, man, entities):
    r = rfor("txn_scenarios_v2")
    accounts = s.rows("accounts")
    used = set()

    def take():
        for a in accounts:
            if a["account_id"] not in used and a["status"] != "closed":
                used.add(a["account_id"])
                return a
        raise RuntimeError("not enough accounts")

    # TXN-01 Impossible Travel
    for i in range(COUNTS["TXN-01"]):
        a = take()
        t = BASE + timedelta(days=1, hours=i)
        origin, destination = r.choice(
            [
                (PROV[0], PROV[1]),
                (PROV[0], PROV[4]),
                (PROV[3], PROV[1]),
                (PROV[1], PROV[0]),
                (PROV[2], PROV[0]),
            ]
        )
        travel_minutes = r.randint(8, 75)
        amount = r.randint(500_000, 12_000_000)
        d = add_device(s, f"T01_{i}", risk=90)
        add_session(
            s, f"T01A_{i}", a, d, t, origin[0], origin[1], origin[2], False, False
        )
        sid = add_session(
            s,
            f"T01B_{i}",
            a,
            d,
            t + timedelta(minutes=travel_minutes),
            destination[0],
            destination[1],
            destination[2],
            False,
            True,
            risk=96,
        )
        b = add_bene(s, f"T01_{i}", a, t)
        tx_time = t + timedelta(minutes=travel_minutes + 1)
        tx = add_txn(s, f"T01_{i}", a, sid, d, b, tx_time, amount)
        append_manifest(
            man,
            f"EV_TXN01_{i}",
            "TXN-01",
            "transaction",
            a["customer_id"],
            a["account_id"],
            tx,
            "",
            t,
            tx_time,
            ["R_TXN_GEO_001"],
            "CHALLENGE",
            "High",
            desc="Impossible travel between distant provinces in under 75 minutes",
        )
        append_entity(
            entities,
            f"EV_TXN01_{i}",
            "TXN-01",
            "transaction",
            tx,
            "primary",
            "fraud",
            t,
            tx_time,
        )
    # TXN-02 dormant
    for i in range(COUNTS["TXN-02"]):
        a = take()
        a["status"] = "dormant"
        a["dormant_since"] = dt(BASE - timedelta(days=r.randint(365, 1200)))
        d = add_device(s, f"T02_{i}", risk=90)
        t = BASE + timedelta(days=2, hours=i)
        sid = add_session(s, f"T02_{i}", a, d, t, newdev=True, newloc=True, risk=94)
        b = add_bene(s, f"T02_{i}", a, t)
        transfer_delay = r.randint(2, 30)
        tx = add_txn(
            s,
            f"T02_{i}",
            a,
            sid,
            d,
            b,
            t + timedelta(minutes=transfer_delay),
            min(float(a["single_txn_limit"]) * r.uniform(0.6, 0.95), 45000000),
        )
        append_manifest(
            man,
            f"EV_TXN02_{i}",
            "TXN-02",
            "transaction",
            a["customer_id"],
            a["account_id"],
            tx,
            "",
            t,
            t + timedelta(minutes=transfer_delay),
            ["R_TXN_DORMANT_001"],
            "HOLD",
            "Critical",
            desc="Dormant account awakening from new device",
        )
        append_entity(
            entities,
            f"EV_TXN02_{i}",
            "TXN-02",
            "transaction",
            tx,
            "primary",
            "fraud",
            t,
            t + timedelta(minutes=transfer_delay),
        )
    # TXN-03 brute force; auth events tied to session to respect exact-one context
    for i in range(COUNTS["TXN-03"]):
        a = take()
        t = BASE + timedelta(days=3, hours=23, minutes=i)
        d = add_device(s, f"T03_{i}", risk=92)
        sid = add_session(s, f"T03_{i}", a, d, t, newdev=True, newloc=True, risk=95)
        failed_attempts = r.randint(3, 7)
        attempt_gap_seconds = r.randint(5, 20)
        for k in range(failed_attempts + 1):
            add_auth(
                s,
                f"T03_{i}_{k}",
                a,
                t + timedelta(seconds=attempt_gap_seconds * k),
                session=sid,
                result="success" if k == failed_attempts else "failed",
                attempts=max(k, 1),
                risk=95 if k == failed_attempts else min(94, 78 + k * 3),
            )
        append_manifest(
            man,
            f"EV_TXN03_{i}",
            "TXN-03",
            "transaction",
            a["customer_id"],
            a["account_id"],
            "",
            "",
            t,
            t + timedelta(seconds=attempt_gap_seconds * failed_attempts),
            ["R_TXN_AUTH_001"],
            "CHALLENGE",
            "High",
            desc="Credential stuffing followed by success",
        )
        append_entity(
            entities,
            f"EV_TXN03_{i}",
            "TXN-03",
            "account",
            a["account_id"],
            "primary",
            "context_only",
            t,
            t + timedelta(seconds=attempt_gap_seconds * failed_attempts),
        )
    # TXN-04 velocity burst
    for i in range(COUNTS["TXN-04"]):
        a = take()
        t = BASE + timedelta(days=4, hours=i)
        d = add_device(s, f"T04_{i}", risk=70)
        sid = add_session(s, f"T04_{i}", a, d, t, newdev=False, newloc=False, risk=50)
        b = add_bene(s, f"T04_{i}", a, t - timedelta(days=30))
        tids = []
        burst_size = r.randint(4, 8)
        spacing_seconds = r.randint(35, 110)
        for k in range(burst_size):
            amt = r.randint(4_300_000, 4_990_000)
            tids.append(
                add_txn(
                    s,
                    f"T04_{i}_{k}",
                    a,
                    sid,
                    d,
                    b,
                    t + timedelta(seconds=spacing_seconds * k),
                    amt,
                )
            )
        burst_end = t + timedelta(seconds=spacing_seconds * (burst_size - 1))
        append_manifest(
            man,
            f"EV_TXN04_{i}",
            "TXN-04",
            "transaction",
            a["customer_id"],
            a["account_id"],
            tids[-1],
            "",
            t,
            burst_end,
            ["R_TXN_VEL_001"],
            "HOLD",
            "High",
            desc="Four to eight structured transfers in under 10 minutes",
        )
        for k, tid in enumerate(tids):
            append_entity(
                entities,
                f"EV_TXN04_{i}",
                "TXN-04",
                "transaction",
                tid,
                "primary" if k == len(tids) - 1 else "supporting_velocity",
                "fraud",
                t,
                burst_end,
            )
    # TXN-05 new beneficiary rapid transfer
    for i in range(COUNTS["TXN-05"]):
        a = take()
        t = BASE + timedelta(days=5, hours=i)
        d = add_device(s, f"T05_{i}", risk=10)
        sid = add_session(s, f"T05_{i}", a, d, t, newdev=False, newloc=False, risk=15)
        beneficiary_delay = r.randint(1, 20)
        transfer_delay = beneficiary_delay + r.randint(1, 10)
        b = add_bene(s, f"T05_{i}", a, t + timedelta(minutes=beneficiary_delay))
        tx = add_txn(
            s,
            f"T05_{i}",
            a,
            sid,
            d,
            b,
            t + timedelta(minutes=transfer_delay),
            float(a["single_txn_limit"]) * r.uniform(0.75, 0.98),
        )
        append_manifest(
            man,
            f"EV_TXN05_{i}",
            "TXN-05",
            "transaction",
            a["customer_id"],
            a["account_id"],
            tx,
            "",
            t,
            t + timedelta(minutes=transfer_delay),
            ["R_TXN_SCAM_001"],
            "CHALLENGE",
            "High",
            desc="Known device but rapid large transfer to new beneficiary",
        )
        append_entity(
            entities,
            f"EV_TXN05_{i}",
            "TXN-05",
            "transaction",
            tx,
            "primary",
            "fraud",
            t,
            t + timedelta(minutes=transfer_delay),
        )
    # TXN-06 full ATO
    for i in range(COUNTS["TXN-06"]):
        a = take()
        t = BASE + timedelta(days=6, hours=i)
        d = add_device(s, f"T06_{i}", risk=98)
        sid = add_session(
            s, f"T06_{i}", a, d, t, newdev=True, newloc=True, vpn=True, risk=99
        )
        add_auth(
            s,
            f"T06_{i}",
            a,
            t + timedelta(minutes=2),
            session=sid,
            result="success",
            attempts=1,
            risk=90,
            method="sms_otp",
        )
        for k, typ in enumerate(["password", "phone", "transfer_limit"]):
            add_change(s, f"T06_{i}_{k}", a, d, t + timedelta(minutes=4 + 2 * k), typ)
        b = add_bene(s, f"T06_{i}", a, t + timedelta(minutes=10))
        tx = add_txn(
            s,
            f"T06_{i}",
            a,
            sid,
            d,
            b,
            t + timedelta(minutes=12),
            float(a["average_balance"]) * r.uniform(0.65, 0.95),
        )
        [
            x.update(status="removed")
            for x in s.rows("beneficiaries")
            if x["beneficiary_id"] == b
        ]
        append_manifest(
            man,
            f"EV_TXN06_{i}",
            "TXN-06",
            "transaction",
            a["customer_id"],
            a["account_id"],
            tx,
            "",
            t,
            t + timedelta(minutes=13),
            ["R_TXN_ATO_001", "R_TXN_VEL_001", "R_TXN_SCAM_001"],
            "HOLD",
            "Critical",
            desc="Full account takeover chain",
        )
        append_entity(
            entities,
            f"EV_TXN06_{i}",
            "TXN-06",
            "transaction",
            tx,
            "primary",
            "fraud",
            t,
            t + timedelta(minutes=13),
        )
    # TXN-07 mule ring one ring, 3 mules + 5 victims
    for ring in range(COUNTS["TXN-07"]):
        mules = [take() for _ in range(3)]
        victims = [take() for _ in range(5)]
        t = BASE + timedelta(days=7)
        cluster = f"RING_{ring + 1:02d}"
        for a in mules:
            cust = next(
                c for c in s.rows("customers") if c["customer_id"] == a["customer_id"]
            )
            cust["is_mule_candidate_seed"] = "true"
            a["open_date"] = ds((BASE - timedelta(days=20)).date())
        primary = ""
        ring_tids = []
        # victim credits into mule A modeled as credit transactions on mule A from different counterparties
        ma = mules[0]
        d = add_device(s, f"T07_MA_{ring}", risk=75)
        sid = add_session(
            s, f"T07_MA_{ring}", ma, d, t, newdev=False, newloc=False, risk=60
        )
        for k, v in enumerate(victims):
            primary = add_txn(
                s,
                f"T07_IN_{ring}_{k}",
                ma,
                sid,
                d,
                "",
                t + timedelta(minutes=k),
                r.randint(4_500_000, 9_500_000),
                direction="CREDIT",
            )
            ring_tids.append((primary, "mule_inflow"))
        for k, target in enumerate(mules[1:]):
            b = add_bene(
                s,
                f"T07_{ring}_{k}",
                ma,
                t + timedelta(minutes=6),
                cluster=cluster,
                internal=True,
            )
            layering_tx = add_txn(
                s,
                f"T07_OUT_{ring}_{k}",
                ma,
                sid,
                d,
                b,
                t + timedelta(minutes=8 + k),
                r.randint(12_000_000, 19_000_000),
                internal_acc=target["account_id"],
            )
            ring_tids.append((layering_tx, "layering"))
            td = add_device(s, f"T07_T{ring}_{k}", risk=70)
            ts = add_session(
                s,
                f"T07_T{ring}_{k}",
                target,
                td,
                t + timedelta(minutes=10),
                newdev=False,
                newloc=False,
                risk=60,
            )
            cashout_tx = add_txn(
                s,
                f"T07_CASH_{ring}_{k}",
                target,
                ts,
                td,
                "",
                t + timedelta(minutes=12 + k),
                r.randint(8_000_000, 15_000_000),
                typ="cash_withdrawal",
                channel="atm",
            )
            ring_tids.append((cashout_tx, "cash_out"))
        append_manifest(
            man,
            f"EV_TXN07_{ring}",
            "TXN-07",
            "transaction",
            ma["customer_id"],
            ma["account_id"],
            primary,
            "",
            t,
            t + timedelta(minutes=15),
            ["R_TXN_MULE_001", "R_TXN_VEL_001"],
            "HOLD",
            "Critical",
            desc="Fan-in, layering, and cash-out mule ring",
        )
        for tid, role in ring_tids:
            append_entity(
                entities,
                f"EV_TXN07_{ring}",
                "TXN-07",
                "transaction",
                tid,
                "primary" if tid == primary else role,
                "fraud",
                t,
                t + timedelta(minutes=15),
            )
    # TXN-08 bot farm
    for farm in range(COUNTS["TXN-08"]):
        targets = [take() for _ in range(10)]
        t = BASE + timedelta(days=8)
        successful = ""
        successful_tids = []
        for k, a in enumerate(targets):
            d = add_device(s, f"T08_{farm}_{k}", True, True, 95 + k % 4)
            sid = add_session(
                s,
                f"T08_{farm}_{k}",
                a,
                d,
                t + timedelta(minutes=3 * k),
                newdev=True,
                newloc=True,
                proxy=True,
                risk=98,
                result="success" if k >= 8 else "failed",
            )
            add_auth(
                s,
                f"T08_{farm}_{k}",
                a,
                t + timedelta(minutes=3 * k),
                session=sid,
                result="success" if k >= 8 else "failed",
                attempts=3,
                risk=98,
            )
            if k >= 8:
                b = add_bene(s, f"T08_{farm}_{k}", a, t + timedelta(minutes=3 * k))
                successful = add_txn(
                    s,
                    f"T08_{farm}_{k}",
                    a,
                    sid,
                    d,
                    b,
                    t + timedelta(minutes=3 * k + 1),
                    r.randint(5_000_000, 20_000_000),
                )
                successful_tids.append(successful)
        append_manifest(
            man,
            f"EV_TXN08_{farm}",
            "TXN-08",
            "transaction",
            targets[-1]["customer_id"],
            targets[-1]["account_id"],
            successful,
            "",
            t,
            t + timedelta(minutes=31),
            ["R_TXN_AUTH_001", "R_TXN_ATO_001", "R_TXN_DEVICE_001"],
            "HOLD",
            "Critical",
            desc="Emulator and rotating proxy bot farm",
        )
        for tid in successful_tids:
            append_entity(
                entities,
                f"EV_TXN08_{farm}",
                "TXN-08",
                "transaction",
                tid,
                "primary" if tid == successful else "compromised_account_transfer",
                "fraud",
                t,
                t + timedelta(minutes=31),
            )
    # TXN-09 rogue employee
    for i in range(COUNTS["TXN-09"]):
        victim = take()
        receiver = take()
        t = BASE + timedelta(days=9, hours=19 + i)
        d = add_device(s, f"T09_INT_{i}", risk=55)
        # change device type
        for x in s.rows("devices"):
            if x["device_id"] == d:
                x["device_type"] = "internal_terminal"
                x["os"] = "Internal Branch OS"
        sid = add_session(
            s, f"T09_{i}", victim, d, t, newdev=False, newloc=False, risk=65
        )
        b = add_bene(s, f"T09_{i}", victim, t, internal=True)
        diverted_amount = r.randint(12_000_000, 30_000_000)
        tx = add_txn(
            s,
            f"T09_{i}",
            victim,
            sid,
            d,
            b,
            t + timedelta(minutes=2),
            diverted_amount,
            channel="branch",
            internal_acc=receiver["account_id"],
        )
        rd = add_device(s, f"T09_R_{i}", risk=40)
        rs = add_session(
            s,
            f"T09_R_{i}",
            receiver,
            rd,
            t + timedelta(minutes=3),
            newdev=False,
            newloc=False,
            risk=45,
        )
        rb = add_bene(s, f"T09_R_{i}", receiver, t)
        receiver_tx = add_txn(
            s,
            f"T09_R_{i}",
            receiver,
            rs,
            rd,
            rb,
            t + timedelta(minutes=5),
            diverted_amount * r.uniform(0.82, 0.97),
        )
        append_manifest(
            man,
            f"EV_TXN09_{i}",
            "TXN-09",
            "transaction",
            victim["customer_id"],
            victim["account_id"],
            tx,
            "",
            t,
            t + timedelta(minutes=5),
            ["R_TXN_INTERNAL_001", "R_TXN_VEL_001"],
            "HOLD",
            "Critical",
            desc="Branch internal fund diversion and rapid external transfer",
        )
        append_entity(
            entities,
            f"EV_TXN09_{i}",
            "TXN-09",
            "transaction",
            tx,
            "primary",
            "fraud",
            t,
            t + timedelta(minutes=5),
        )
        append_entity(
            entities,
            f"EV_TXN09_{i}",
            "TXN-09",
            "transaction",
            receiver_tx,
            "rapid_external_transfer",
            "fraud",
            t,
            t + timedelta(minutes=5),
        )
    # TXN-10 SIM swap
    for i in range(COUNTS["TXN-10"]):
        a = take()
        t = BASE + timedelta(days=10, hours=i)
        oldd = add_device(s, f"T10_OLD_{i}", risk=5)
        add_session(
            s,
            f"T10_OLD_{i}",
            a,
            oldd,
            t - timedelta(hours=24),
            newdev=False,
            newloc=False,
            risk=5,
        )
        d = add_device(s, f"T10_NEW_{i}", risk=97)
        for k, typ in enumerate(["phone", "trusted_device", "transfer_limit"]):
            add_change(s, f"T10_{i}_{k}", a, d, t + timedelta(minutes=k * 3), typ)
        sid = add_session(
            s,
            f"T10_{i}",
            a,
            d,
            t + timedelta(minutes=1),
            newdev=True,
            newloc=True,
            risk=98,
        )
        b = add_bene(s, f"T10_{i}", a, t + timedelta(minutes=8))
        tx = add_txn(
            s,
            f"T10_{i}",
            a,
            sid,
            d,
            b,
            t + timedelta(minutes=10),
            float(a["average_balance"]) * r.uniform(0.65, 0.98),
        )
        [
            x.update(status="removed")
            for x in s.rows("beneficiaries")
            if x["beneficiary_id"] == b
        ]
        append_manifest(
            man,
            f"EV_TXN10_{i}",
            "TXN-10",
            "transaction",
            a["customer_id"],
            a["account_id"],
            tx,
            "",
            t,
            t + timedelta(minutes=11),
            ["R_TXN_ATO_001", "R_TXN_SCAM_001", "R_TXN_VEL_001"],
            "HOLD",
            "Critical",
            desc="SIM swap followed by trusted device and limit change",
        )
        append_entity(
            entities,
            f"EV_TXN10_{i}",
            "TXN-10",
            "transaction",
            tx,
            "primary",
            "fraud",
            t,
            t + timedelta(minutes=11),
        )
    for tname in [
        "customers",
        "accounts",
        "devices",
        "login_sessions",
        "beneficiaries",
        "account_change_events",
        "transactions",
        "auth_events",
    ]:
        s.save(tname)


def ensure_loan_bundle(s, cust, tag, t, agent=None, force_disbursed=True):
    sps = s.rows("sales_points")
    agents = s.rows("sales_agents")
    devs = group(s.rows("devices"), "simulation_run_id")[RUN]
    sp = (
        sps[0]
        if agent is None
        else next(x for x in sps if x["sales_point_id"] == agent["sales_point_id"])
    )
    ag = agent or agents[0]
    did = next(
        (
            x["device_id"]
            for x in devs
            if x["device_id"].endswith(cust["customer_id"][-6:])
        ),
        devs[0]["device_id"],
    )
    appid = f"{RUN}_SCN_APP_{tag}"
    amount = 120000000 if force_disbursed else 60000000
    s.rows("loan_applications").append(
        dict(
            application_id=appid,
            simulation_run_id=RUN,
            customer_id=cust["customer_id"],
            application_at=dt(t),
            loan_amount=amount,
            loan_term_months=24,
            loan_product="cash_loan",
            loan_purpose="business",
            application_channel="online",
            sales_point_id=sp["sales_point_id"],
            sales_agent_id=ag["sales_agent_id"],
            application_status="disbursed" if force_disbursed else "in_review",
            credit_underwriting_result="pass" if force_disbursed else "manual_review",
            decision_at=dt(t + timedelta(hours=4)),
            device_id=did,
            ip_address="198.51.100.10",
            is_vpn=False,
            is_proxy=False,
            is_emulator=False,
            created_at=dt(BASE),
        )
    )
    s.rows("applicant_declared_profiles").append(
        dict(
            declared_profile_id=f"{RUN}_SCN_DPR_{tag}",
            simulation_run_id=RUN,
            application_id=appid,
            customer_id=cust["customer_id"],
            declared_full_name=cust["full_name"],
            declared_id_number_hash=cust["id_number_hash"],
            declared_dob=cust["dob"],
            declared_phone_hash=cust["phone_hash"],
            declared_email_hash=cust["email_hash"],
            declared_permanent_address=f"12 Main, {cust['province']}",
            declared_current_address=f"12 Main, {cust['province']}",
            declared_marital_status="married",
            declared_dependents=1,
            address_cluster_id=cust["address_cluster_id"],
            profile_similarity_cluster_id="",
            address_quality_score=90,
            created_at=dt(BASE),
        )
    )
    s.rows("employment_income_profiles").append(
        dict(
            employment_id=f"{RUN}_SCN_EMP_{tag}",
            simulation_run_id=RUN,
            application_id=appid,
            occupation_group=cust["occupation_group"],
            employer_name="Công ty Hợp Lệ",
            employer_phone_hash=h("EMP" + tag),
            employer_phone_cluster_id=f"EPH_{tag}",
            employer_phone_verification_status="verified",
            is_employer_phone_reused=False,
            employer_address="1 Business Street",
            employment_start_date="2021-01-01",
            months_at_employer=67,
            declared_monthly_income=25000000,
            income_document_type="payslip",
            employer_cluster_id=f"EMP_{tag}",
            created_at=dt(BASE),
        )
    )
    for order in (1, 2):
        s.rows("reference_contacts").append(
            dict(
                reference_id=f"{RUN}_SCN_REF_{tag}_{order}",
                simulation_run_id=RUN,
                application_id=appid,
                reference_name=f"Reference {tag}-{order}",
                relationship="friend" if order == 1 else "colleague",
                reference_phone_hash=h(f"REF{tag}{order}"),
                phone_reuse_count=1,
                reference_quality_score=90,
                reference_order=order,
                verification_status="verified",
                created_at=dt(BASE),
            )
        )
    for typ in ["id_card_front", "id_card_back", "selfie", "payslip"]:
        s.rows("application_documents").append(
            dict(
                document_id=f"{RUN}_SCN_DOC_{tag}_{typ}",
                simulation_run_id=RUN,
                application_id=appid,
                document_type=typ,
                document_hash=h(f"DOC{tag}{typ}"),
                submitted_at=dt(t),
                ocr_quality_score=95,
                tamper_score=5,
                duplicate_document_hash_count=1,
                id_front_back_match_flag=True,
                id_expired_flag=False,
                face_match_score=0.98,
                liveness_result="pass" if typ == "selfie" else "not_applicable",
                document_result="accepted",
                created_at=dt(BASE),
            )
        )
    s.rows("credit_bureau_snapshots").append(
        dict(
            bureau_snapshot_id=f"{RUN}_SCN_CIC_{tag}",
            simulation_run_id=RUN,
            application_id=appid,
            bureau_score=720,
            active_loan_count=1,
            dpd_max_12m=0,
            recent_inquiry_count=1,
            thin_file_flag=False,
            bureau_match_result="full_match",
            snapshot_at=dt(t),
            created_at=dt(BASE),
        )
    )
    if force_disbursed:
        disbt = t + timedelta(hours=8)
        s.rows("disbursement_accounts").append(
            dict(
                disbursement_id=f"{RUN}_SCN_DIS_{tag}",
                simulation_run_id=RUN,
                application_id=appid,
                receiving_account_hash=h("DIS" + tag),
                receiving_account_name=cust["full_name"],
                receiving_bank="VCB",
                same_as_applicant=True,
                account_reuse_count=1,
                linked_account_id="",
                disbursement_status="completed",
                disbursed_at=dt(disbt),
                disbursed_amount=amount,
                created_at=dt(BASE),
            )
        )
        s.rows("loan_repayment_outcomes").append(
            dict(
                loan_outcome_id=f"{RUN}_SCN_OUT_{tag}",
                simulation_run_id=RUN,
                application_id=appid,
                disbursed_at=dt(disbt),
                first_due_date=ds(disbt.date() + timedelta(days=30)),
                first_payment_status="paid_on_time",
                first_payment_days_past_due=0,
                contact_status_after_disbursement="contactable",
                dpd_30_flag=False,
                dpd_60_flag=False,
                dpd_90_flag=False,
                installments_due=1,
                installments_paid_on_time=1,
                total_amount_due=amount / 24,
                total_amount_paid=amount / 24,
                outstanding_balance=amount - amount / 24,
                early_default_flag=False,
                writeoff_amount=0,
                loan_performance_status="performing",
                credit_performance_label="good",
                fraud_outcome_label="legitimate",
                outcome_observed_at=dt(disbt + timedelta(days=35)),
                created_at=dt(BASE),
            )
        )
    return appid


def inject_transaction_hard_negatives(s, man, entities):
    """Near-miss legitimate journeys for every TXN fraud family.

    These rows deliberately share risky categories and partial signals with fraud, while a
    cooling period, successful recovery, known business pattern, or verified channel makes
    the final outcome legitimate. This prevents models from learning generator shortcuts.
    """
    configured = CFG.get("transaction_hard_negative_counts", 0)
    r = rfor("txn_hard_negatives_v2")
    occupied = {
        x["account_id"]
        for x in s.rows("transactions")
        if "_SCN_" in x["transaction_id"]
    }
    pool = [
        a
        for a in s.rows("accounts")
        if a["status"] != "closed" and a["account_id"] not in occupied
    ]
    cursor = 0

    def count(code):
        if isinstance(configured, dict):
            return int(configured.get(code, 0))
        return int(configured)

    def take():
        nonlocal cursor
        if cursor >= len(pool):
            raise RuntimeError("not enough accounts for transaction hard negatives")
        a = pool[cursor]
        cursor += 1
        return a

    def record(code, i, a, tids, start, end, rules, desc):
        event_id = f"EV_HN{code.replace('-', '')}_{i:04d}"
        append_manifest(
            man,
            event_id,
            code,
            "transaction",
            a["customer_id"],
            a["account_id"],
            tids[-1],
            "",
            start,
            end,
            rules,
            "ACCEPT",
            "Medium",
            label="false_positive_seed",
            desc=desc,
        )
        for pos, tid in enumerate(tids):
            append_entity(
                entities,
                event_id,
                code,
                "transaction",
                tid,
                "primary" if pos == len(tids) - 1 else "supporting_legitimate",
                "hard_negative",
                start,
                end,
            )

    # HN-TXN-01: distant logins are many hours apart, so travel is plausible.
    for i in range(count("HN-TXN-01")):
        a = take()
        t = BASE + timedelta(days=31, hours=i % 20)
        d1, d2 = (
            add_device(s, f"HN01A_{i}", risk=18),
            add_device(s, f"HN01B_{i}", risk=22),
        )
        add_session(
            s,
            f"HN01A_{i}",
            a,
            d1,
            t,
            province="Hà Nội",
            newdev=False,
            newloc=False,
            risk=18,
        )
        t2 = t + timedelta(hours=r.randint(6, 12))
        sid = add_session(
            s,
            f"HN01B_{i}",
            a,
            d2,
            t2,
            province="TP.HCM",
            newdev=False,
            newloc=True,
            risk=35,
        )
        bid = add_bene(s, f"HN01_{i}", a, t2 - timedelta(days=30), risk="Low")
        tid = add_txn(
            s,
            f"HN01_{i}",
            a,
            sid,
            d2,
            bid,
            t2 + timedelta(minutes=5),
            r.randint(300_000, 4_000_000),
        )
        record(
            "HN-TXN-01",
            i,
            a,
            [tid],
            t,
            t2 + timedelta(minutes=6),
            ["R_TXN_GEO_001"],
            "Plausible inter-city travel followed by a normal transfer",
        )

    # HN-TXN-02: dormant account reactivated and verified at a branch.
    for i in range(count("HN-TXN-02")):
        a = take()
        a["dormant_since"] = ds((BASE - timedelta(days=r.randint(100, 220))).date())
        t = BASE + timedelta(days=32, hours=i % 18)
        dev = add_device(s, f"HN02_{i}", risk=12)
        next(x for x in s.rows("devices") if x["device_id"] == dev).update(
            device_type="internal_terminal",
            os="Internal Branch OS",
            trust_status="trusted",
        )
        sid = add_session(
            s, f"HN02_{i}", a, dev, t, newdev=False, newloc=False, risk=20
        )
        bid = add_bene(
            s, f"HN02_{i}", a, t - timedelta(days=60), risk="Low", internal=True
        )
        tid = add_txn(
            s,
            f"HN02_{i}",
            a,
            sid,
            dev,
            bid,
            t + timedelta(minutes=8),
            r.randint(200_000, 2_000_000),
            channel="branch",
        )
        record(
            "HN-TXN-02",
            i,
            a,
            [tid],
            t,
            t + timedelta(minutes=10),
            ["R_TXN_DORMANT_001"],
            "Verified branch reactivation of a dormant account",
        )

    # HN-TXN-03: failed password attempts followed by biometric recovery.
    for i in range(count("HN-TXN-03")):
        a = take()
        t = BASE + timedelta(days=33, hours=i % 18)
        dev = add_device(s, f"HN03_{i}", risk=28)
        sid = add_session(
            s, f"HN03_{i}", a, dev, t, newdev=False, newloc=False, risk=32
        )
        for k in range(r.randint(3, 5)):
            add_auth(
                s,
                f"HN03F_{i}_{k}",
                a,
                t + timedelta(minutes=k),
                session=sid,
                attempts=k + 1,
                risk=65,
            )
        add_auth(
            s,
            f"HN03S_{i}",
            a,
            t + timedelta(minutes=7),
            session=sid,
            result="success",
            attempts=0,
            risk=18,
            method="biometric",
        )
        bid = add_bene(s, f"HN03_{i}", a, t - timedelta(days=90), risk="Low")
        tid = add_txn(
            s,
            f"HN03_{i}",
            a,
            sid,
            dev,
            bid,
            t + timedelta(minutes=10),
            r.randint(80_000, 800_000),
            typ="bill_payment",
        )
        record(
            "HN-TXN-03",
            i,
            a,
            [tid],
            t,
            t + timedelta(minutes=11),
            ["R_TXN_AUTH_001"],
            "Password failures resolved by biometric recovery",
        )

    # HN-TXN-04: legitimate batch payments create velocity without fraud.
    for i in range(count("HN-TXN-04")):
        a = take()
        t = BASE + timedelta(days=34, hours=i % 16)
        dev = add_device(s, f"HN04_{i}", risk=15)
        sid = add_session(
            s, f"HN04_{i}", a, dev, t, newdev=False, newloc=False, risk=20
        )
        bid = add_bene(s, f"HN04_{i}", a, t - timedelta(days=120), risk="Low")
        tids = [
            add_txn(
                s,
                f"HN04_{i}_{k}",
                a,
                sid,
                dev,
                bid,
                t + timedelta(minutes=2 * k + 1),
                r.randint(50_000, 500_000),
                typ="bill_payment",
                channel="api",
            )
            for k in range(r.randint(4, 8))
        ]
        record(
            "HN-TXN-04",
            i,
            a,
            tids,
            t,
            t + timedelta(minutes=20),
            ["R_TXN_VEL_001"],
            "Known recurring batch of low-value bill payments",
        )

    # HN-TXN-05: new beneficiary, but cooling period and low value are respected.
    for i in range(count("HN-TXN-05")):
        a = take()
        added = BASE + timedelta(days=35, hours=i % 18)
        t = added + timedelta(hours=r.randint(24, 72))
        dev = add_device(s, f"HN05_{i}", risk=20)
        bid = add_bene(s, f"HN05_{i}", a, added, risk="Low")
        sid = add_session(
            s, f"HN05_{i}", a, dev, t, newdev=False, newloc=False, risk=20
        )
        tid = add_txn(
            s,
            f"HN05_{i}",
            a,
            sid,
            dev,
            bid,
            t + timedelta(minutes=3),
            r.randint(100_000, 1_500_000),
        )
        record(
            "HN-TXN-05",
            i,
            a,
            [tid],
            added,
            t + timedelta(minutes=4),
            ["R_TXN_SCAM_001"],
            "New beneficiary used after a safe cooling period",
        )

    # HN-TXN-06: sensitive change is followed by cooling and a small transfer.
    for i in range(count("HN-TXN-06")):
        a = take()
        changed = BASE + timedelta(days=36, hours=i % 18)
        dev = add_device(s, f"HN06_{i}", risk=25)
        change = add_change(
            s, f"HN06_{i}", a, dev, changed, r.choice(["phone", "email", "password"])
        )
        add_auth(
            s,
            f"HN06_{i}",
            a,
            changed,
            change=change,
            result="success",
            attempts=0,
            risk=15,
            method="biometric",
        )
        t = changed + timedelta(hours=r.randint(48, 96))
        sid = add_session(
            s, f"HN06_{i}", a, dev, t, newdev=False, newloc=False, risk=18
        )
        bid = add_bene(s, f"HN06_{i}", a, changed - timedelta(days=180), risk="Low")
        tid = add_txn(
            s,
            f"HN06_{i}",
            a,
            sid,
            dev,
            bid,
            t + timedelta(minutes=4),
            r.randint(100_000, 1_000_000),
        )
        record(
            "HN-TXN-06",
            i,
            a,
            [tid],
            changed,
            t + timedelta(minutes=5),
            ["R_TXN_ATO_001"],
            "Verified profile change with cooling period",
        )

    # HN-TXN-07: legitimate merchant fan-in followed by an ATM withdrawal.
    for i in range(count("HN-TXN-07")):
        a = take()
        t = BASE + timedelta(days=37, hours=i % 18)
        dev = add_device(s, f"HN07_{i}", risk=18)
        next(x for x in s.rows("devices") if x["device_id"] == dev).update(
            device_type="atm", os="ATM OS", trust_status="trusted"
        )
        sid = add_session(
            s, f"HN07_{i}", a, dev, t, newdev=False, newloc=False, risk=24
        )
        tids = [
            add_txn(
                s,
                f"HN07IN_{i}_{k}",
                a,
                sid,
                dev,
                "",
                t + timedelta(minutes=2 * k + 1),
                r.randint(200_000, 1_200_000),
                typ="merchant_settlement",
                channel="api",
                direction="CREDIT",
            )
            for k in range(r.randint(3, 6))
        ]
        tids.append(
            add_txn(
                s,
                f"HN07OUT_{i}",
                a,
                sid,
                dev,
                "",
                t + timedelta(minutes=15),
                r.randint(300_000, 2_000_000),
                typ="cash_withdrawal",
                channel="atm",
            )
        )
        record(
            "HN-TXN-07",
            i,
            a,
            tids,
            t,
            t + timedelta(minutes=16),
            ["R_TXN_MULE_001"],
            "Registered merchant settlements followed by normal ATM cash use",
        )

    # HN-TXN-08: emulator/proxy QA session with a low-value approved payment.
    for i in range(count("HN-TXN-08")):
        a = take()
        t = BASE + timedelta(days=38, hours=i % 18)
        dev = add_device(s, f"HN08_{i}", emulator=True, risk=72)
        sid = add_session(
            s, f"HN08_{i}", a, dev, t, newdev=True, newloc=False, proxy=True, risk=68
        )
        bid = add_bene(s, f"HN08_{i}", a, t - timedelta(days=120), risk="Low")
        tid = add_txn(
            s,
            f"HN08_{i}",
            a,
            sid,
            dev,
            bid,
            t + timedelta(minutes=5),
            r.randint(10_000, 100_000),
            typ="bill_payment",
        )
        record(
            "HN-TXN-08",
            i,
            a,
            [tid],
            t,
            t + timedelta(minutes=6),
            ["R_TXN_DEVICE_001"],
            "Approved low-value QA payment from registered test emulator",
        )

    # HN-TXN-09: legitimate internal-terminal transaction at a branch.
    for i in range(count("HN-TXN-09")):
        a = take()
        t = BASE + timedelta(days=39, hours=i % 18)
        dev = add_device(s, f"HN09_{i}", risk=10)
        next(x for x in s.rows("devices") if x["device_id"] == dev).update(
            device_type="internal_terminal",
            os="Internal Branch OS",
            trust_status="trusted",
        )
        sid = add_session(
            s, f"HN09_{i}", a, dev, t, newdev=False, newloc=False, risk=12
        )
        bid = add_bene(
            s, f"HN09_{i}", a, t - timedelta(days=365), risk="Low", internal=True
        )
        tid = add_txn(
            s,
            f"HN09_{i}",
            a,
            sid,
            dev,
            bid,
            t + timedelta(minutes=6),
            r.randint(500_000, 5_000_000),
            channel="branch",
        )
        record(
            "HN-TXN-09",
            i,
            a,
            [tid],
            t,
            t + timedelta(minutes=7),
            ["R_TXN_INTERNAL_001"],
            "Customer-present verified branch transfer",
        )

    # HN-TXN-10: device/phone maintenance followed by a delayed normal payment.
    for i in range(count("HN-TXN-10")):
        a = take()
        changed = BASE + timedelta(days=40, hours=i % 18)
        dev = add_device(s, f"HN10_{i}", risk=28)
        add_change(s, f"HN10_{i}", a, dev, changed, "phone")
        t = changed + timedelta(hours=r.randint(24, 72))
        sid = add_session(s, f"HN10_{i}", a, dev, t, newdev=True, newloc=False, risk=30)
        bid = add_bene(s, f"HN10_{i}", a, changed - timedelta(days=200), risk="Low")
        tid = add_txn(
            s,
            f"HN10_{i}",
            a,
            sid,
            dev,
            bid,
            t + timedelta(minutes=5),
            r.randint(80_000, 800_000),
            typ="bill_payment",
        )
        record(
            "HN-TXN-10",
            i,
            a,
            [tid],
            changed,
            t + timedelta(minutes=6),
            ["R_TXN_ATO_001"],
            "Verified device maintenance with cooling period",
        )

    for tname in [
        "accounts",
        "devices",
        "login_sessions",
        "beneficiaries",
        "account_change_events",
        "transactions",
        "auth_events",
    ]:
        s.save(tname)
    print(
        f"[SCENARIO] +{sum(count(f'HN-TXN-{i:02d}') for i in range(1, 11))} scenario-specific transaction hard negatives"
    )


def inject_loan(s, man):
    customers = s.rows("customers")
    used = set()

    def take():
        for c in customers:
            if c["customer_id"] not in used and c["customer_type"] == "individual":
                used.add(c["customer_id"])
                return c
        raise RuntimeError("not enough customers")

    def bundle(code, i, c=None, agent=None):
        c = c or take()
        return c, ensure_loan_bundle(
            s, c, f"{code.replace('-', '')}_{i}", BASE + timedelta(days=20 + i), agent
        )

    # 01 income inflation
    for i in range(COUNTS["LOAN-01"]):
        c, app = bundle("L01", i)
        c["income_band"] = "<5M"
        emp = next(
            x
            for x in s.rows("employment_income_profiles")
            if x["application_id"] == app
        )
        emp["declared_monthly_income"] = 65000000
        emp["income_document_type"] = "payslip"
        doc = next(
            x
            for x in s.rows("application_documents")
            if x["application_id"] == app and x["document_type"] == "payslip"
        )
        doc["tamper_score"] = 85
        doc["document_result"] = "manual_review"
        append_manifest(
            man,
            f"EV_LOAN01_{i}",
            "LOAN-01",
            "loan",
            c["customer_id"],
            "",
            "",
            app,
            BASE + timedelta(days=20 + i),
            BASE + timedelta(days=20 + i, hours=4),
            ["R_LOAN_DOC_001", "R_LOAN_INCOME_001"],
            "MANUAL_REVIEW",
            "High",
            desc="Declared income inconsistent with known band",
        )
    # 02 stacking
    for i in range(COUNTS["LOAN-02"]):
        c, app = bundle("L02", i)
        cic = next(
            x for x in s.rows("credit_bureau_snapshots") if x["application_id"] == app
        )
        cic.update(
            active_loan_count=6,
            recent_inquiry_count=12,
            dpd_max_12m=45,
            bureau_score=380,
        )
        append_manifest(
            man,
            f"EV_LOAN02_{i}",
            "LOAN-02",
            "loan",
            c["customer_id"],
            "",
            "",
            app,
            BASE + timedelta(days=23 + i),
            BASE + timedelta(days=23 + i, hours=4),
            ["R_LOAN_CIC_001"],
            "MANUAL_REVIEW",
            "High",
            desc="High active loans and inquiry velocity",
        )
    # 03 ghost employer shared cluster
    ghost = "EPH_GHOST_01"
    gphone = h("GHOST_EMP_PHONE")
    for i in range(COUNTS["LOAN-03"]):
        c, app = bundle("L03", i)
        emp = next(
            x
            for x in s.rows("employment_income_profiles")
            if x["application_id"] == app
        )
        emp.update(
            employer_name="Công ty Ma 01",
            employer_phone_hash=gphone,
            employer_phone_cluster_id=ghost,
            employer_phone_verification_status="suspicious",
            is_employer_phone_reused=True,
            employer_cluster_id="EMP_GHOST_01",
        )
        append_manifest(
            man,
            f"EV_LOAN03_{i}",
            "LOAN-03",
            "loan",
            c["customer_id"],
            "",
            "",
            app,
            BASE + timedelta(days=26 + i),
            BASE + timedelta(days=26 + i, hours=4),
            ["R_LOAN_EMP_001"],
            "MANUAL_REVIEW",
            "High",
            desc="Ghost employer phone reused across applications",
        )
    # 04 reference recycling
    refhash = h("ACTOR_REFERENCE_PHONE")
    for i in range(COUNTS["LOAN-04"]):
        c, app = bundle("L04", i)
        refs = [x for x in s.rows("reference_contacts") if x["application_id"] == app]
        refs[0].update(
            reference_phone_hash=refhash,
            phone_reuse_count=COUNTS["LOAN-04"] + 5,
            reference_quality_score=25,
            verification_status="suspicious",
        )
        append_manifest(
            man,
            f"EV_LOAN04_{i}",
            "LOAN-04",
            "loan",
            c["customer_id"],
            "",
            "",
            app,
            BASE + timedelta(days=29 + i),
            BASE + timedelta(days=29 + i, hours=4),
            ["R_LOAN_REF_001"],
            "MANUAL_REVIEW",
            "High",
            desc="Reference actor phone recycled",
        )
    # 05 document integrity
    for i in range(COUNTS["LOAN-05"]):
        c, app = bundle("L05", i)
        docs = [
            x for x in s.rows("application_documents") if x["application_id"] == app
        ]
        for d in docs:
            if d["document_type"] == "id_card_front":
                d["id_expired_flag"] = True
            if d["document_type"] == "id_card_back":
                d["id_front_back_match_flag"] = False
            if d["document_type"] == "selfie":
                d.update(
                    face_match_score=0.45,
                    liveness_result="fail",
                    document_result="rejected",
                )
        append_manifest(
            man,
            f"EV_LOAN05_{i}",
            "LOAN-05",
            "loan",
            c["customer_id"],
            "",
            "",
            app,
            BASE + timedelta(days=32 + i),
            BASE + timedelta(days=32 + i, hours=4),
            ["R_LOAN_DOC_001"],
            "DECLINE",
            "Critical",
            desc="Expired and mismatched identity documents",
        )
    # 06 synthetic farm (5 identities)
    for farm in range(COUNTS["LOAN-06"]):
        apps = []
        cs = []
        t = BASE + timedelta(days=36)
        for k in range(5):
            c = take()
            c["is_synthetic_identity_seed"] = "true"
            app = ensure_loan_bundle(s, c, f"L06_{farm}_{k}", t + timedelta(days=k))
            apps.append(app)
            cs.append(c)
            la = next(
                x for x in s.rows("loan_applications") if x["application_id"] == app
            )
            la.update(is_emulator=True, is_vpn=True)
            p = next(
                x
                for x in s.rows("applicant_declared_profiles")
                if x["application_id"] == app
            )
            p.update(
                profile_similarity_cluster_id=f"SYN_FARM_{farm + 1:02d}",
                address_quality_score=25,
                declared_phone_hash=h(f"FAKEPHONE{farm}{k}"),
            )
            e = next(
                x
                for x in s.rows("employment_income_profiles")
                if x["application_id"] == app
            )
            e.update(
                employer_phone_cluster_id="EPH_GHOST_FARM",
                employer_phone_hash=h("FARM_EMP"),
                is_employer_phone_reused=True,
                employer_phone_verification_status="suspicious",
            )
            cic = next(
                x
                for x in s.rows("credit_bureau_snapshots")
                if x["application_id"] == app
            )
            cic.update(bureau_match_result="partial_match", thin_file_flag=True)
        append_manifest(
            man,
            f"EV_LOAN06_{farm}",
            "LOAN-06",
            "loan",
            cs[0]["customer_id"],
            "",
            "",
            apps[0],
            t,
            t + timedelta(days=5),
            ["R_LOAN_SYN_001", "R_LOAN_EMP_001", "R_LOAN_DOC_001"],
            "DECLINE",
            "Critical",
            desc="Synthetic identity farm cluster",
        )
    # 07 agent collusion, 10 apps same agent
    for farm in range(COUNTS["LOAN-07"]):
        agent = s.rows("sales_agents")[1]
        agent["monthly_application_baseline"] = 3
        apps = []
        cs = []
        shared_emp = h("AGENT_SHARED_EMP")
        shared_ref = h("AGENT_SHARED_REF")
        t = BASE + timedelta(days=43)
        for k in range(10):
            c = take()
            app = ensure_loan_bundle(
                s, c, f"L07_{farm}_{k}", t + timedelta(hours=12 * k), agent
            )
            apps.append(app)
            cs.append(c)
            selfie = next(
                x
                for x in s.rows("application_documents")
                if x["application_id"] == app and x["document_type"] == "selfie"
            )
            selfie["face_match_score"] = 0.55 if k < 5 else 0.9
            emp = next(
                x
                for x in s.rows("employment_income_profiles")
                if x["application_id"] == app
            )
            if k < 6:
                emp.update(
                    employer_phone_hash=shared_emp,
                    employer_phone_cluster_id="AGENT_EMP_RING",
                    is_employer_phone_reused=True,
                )
            ref = next(
                x
                for x in s.rows("reference_contacts")
                if x["application_id"] == app and x["reference_order"] == 1
            )
            if k < 4:
                ref.update(
                    reference_phone_hash=shared_ref,
                    phone_reuse_count=4,
                    verification_status="suspicious",
                )
        append_manifest(
            man,
            f"EV_LOAN07_{farm}",
            "LOAN-07",
            "loan",
            cs[0]["customer_id"],
            "",
            "",
            apps[0],
            t,
            t + timedelta(days=5),
            ["R_LOAN_AGENT_001", "R_LOAN_EMP_001", "R_LOAN_REF_001"],
            "MANUAL_REVIEW",
            "Critical",
            desc="Sales agent application spike with shared evidence",
        )
    # 08 shared disbursement ring
    for ring in range(COUNTS["LOAN-08"]):
        apps = []
        cs = []
        shared = h(f"SHARED_DISB_RING_{ring}")
        for k in range(3):
            c, app = bundle("L08", ring * 3 + k)
            apps.append(app)
            cs.append(c)
            d = next(
                x for x in s.rows("disbursement_accounts") if x["application_id"] == app
            )
            d.update(
                receiving_account_hash=shared,
                same_as_applicant=False,
                account_reuse_count=3,
                receiving_account_name="Ring Controller",
            )
        append_manifest(
            man,
            f"EV_LOAN08_{ring}",
            "LOAN-08",
            "loan",
            cs[0]["customer_id"],
            "",
            "",
            apps[0],
            BASE + timedelta(days=50),
            BASE + timedelta(days=51),
            ["R_LOAN_DIS_001"],
            "HOLD",
            "Critical",
            desc="Three unrelated borrowers share one disbursement account",
        )
    # 09 bust-out clean upfront, bad post-disbursement
    for i in range(COUNTS["LOAN-09"]):
        c, app = bundle("L09", i)
        la = next(x for x in s.rows("loan_applications") if x["application_id"] == app)
        la["loan_amount"] = 300000000
        cic = next(
            x for x in s.rows("credit_bureau_snapshots") if x["application_id"] == app
        )
        cic.update(
            bureau_score=780,
            dpd_max_12m=0,
            thin_file_flag=False,
            active_loan_count=0,
            recent_inquiry_count=0,
        )
        out = next(
            x for x in s.rows("loan_repayment_outcomes") if x["application_id"] == app
        )
        out.update(
            first_payment_status="missed",
            first_payment_days_past_due=95,
            contact_status_after_disbursement="lost_contact",
            dpd_30_flag=True,
            dpd_60_flag=True,
            dpd_90_flag=True,
            installments_paid_on_time=0,
            total_amount_paid=0,
            early_default_flag=True,
            loan_performance_status="default",
            credit_performance_label="default",
            fraud_outcome_label="confirmed_fraud",
        )
        append_manifest(
            man,
            f"EV_LOAN09_{i}",
            "LOAN-09",
            "loan",
            c["customer_id"],
            "",
            "",
            app,
            BASE + timedelta(days=53 + i),
            BASE + timedelta(days=153 + i),
            ["R_LOAN_BUSTOUT_001"],
            "ALERT_ONLY",
            "Critical",
            desc="Clean underwriting profile followed by immediate bust-out",
        )
    # 10 full ring 5 apps
    for ring in range(COUNTS["LOAN-10"]):
        agent = s.rows("sales_agents")[2]
        shared_doc = h("FULL_RING_DOC_TEMPLATE")
        shared_ref = h("FULL_RING_REF")
        shared_disb = h("FULL_RING_DISB")
        apps = []
        cs = []
        t = BASE + timedelta(days=56)
        for k in range(5):
            c = take()
            c.update(
                is_synthetic_identity_seed="true", address_cluster_id="FULL_RING_ADDR"
            )
            app = ensure_loan_bundle(
                s, c, f"L10_{ring}_{k}", t + timedelta(days=k), agent
            )
            apps.append(app)
            cs.append(c)
            la = next(
                x for x in s.rows("loan_applications") if x["application_id"] == app
            )
            la.update(is_emulator=True, is_vpn=True)
            p = next(
                x
                for x in s.rows("applicant_declared_profiles")
                if x["application_id"] == app
            )
            p.update(
                profile_similarity_cluster_id="FULL_RING_PROFILE",
                address_quality_score=20,
            )
            e = next(
                x
                for x in s.rows("employment_income_profiles")
                if x["application_id"] == app
            )
            e.update(
                employer_phone_cluster_id="FULL_RING_EMP",
                employer_phone_hash=h("FULL_RING_EMP"),
                is_employer_phone_reused=True,
                employer_phone_verification_status="suspicious",
            )
            ref = next(
                x
                for x in s.rows("reference_contacts")
                if x["application_id"] == app and x["reference_order"] == 1
            )
            ref.update(
                reference_phone_hash=shared_ref,
                phone_reuse_count=5,
                reference_quality_score=20,
                verification_status="suspicious",
            )
            for d in [
                x for x in s.rows("application_documents") if x["application_id"] == app
            ]:
                if d["document_type"] in ("payslip", "id_card_front"):
                    d.update(
                        document_hash=shared_doc,
                        tamper_score=90,
                        duplicate_document_hash_count=5,
                        document_result="manual_review",
                    )
                if d["document_type"] == "selfie":
                    d.update(face_match_score=0.4, liveness_result="fail")
            dis = next(
                x for x in s.rows("disbursement_accounts") if x["application_id"] == app
            )
            dis.update(
                receiving_account_hash=shared_disb,
                same_as_applicant=False,
                account_reuse_count=5,
                receiving_account_name="Full Ring Controller",
            )
            out = next(
                x
                for x in s.rows("loan_repayment_outcomes")
                if x["application_id"] == app
            )
            out.update(
                first_payment_status="missed",
                first_payment_days_past_due=95,
                contact_status_after_disbursement="lost_contact",
                dpd_30_flag=True,
                dpd_60_flag=True,
                dpd_90_flag=True,
                installments_paid_on_time=0,
                total_amount_paid=0,
                early_default_flag=True,
                loan_performance_status="default",
                credit_performance_label="default",
                fraud_outcome_label="confirmed_fraud",
            )
        append_manifest(
            man,
            f"EV_LOAN10_{ring}",
            "LOAN-10",
            "loan",
            cs[0]["customer_id"],
            "",
            "",
            apps[0],
            t,
            t + timedelta(days=100),
            [
                "R_LOAN_SYN_001",
                "R_LOAN_DOC_001",
                "R_LOAN_EMP_001",
                "R_LOAN_REF_001",
                "R_LOAN_DIS_001",
                "R_LOAN_AGENT_001",
            ],
            "DECLINE",
            "Critical",
            desc="Full organized fraud ring",
        )
    for tname in [
        "customers",
        "sales_agents",
        "loan_applications",
        "applicant_declared_profiles",
        "employment_income_profiles",
        "reference_contacts",
        "application_documents",
        "credit_bureau_snapshots",
        "disbursement_accounts",
        "loan_repayment_outcomes",
    ]:
        s.save(tname)


def collect_background_hard_negatives(s, man, entities):
    """Background mule/synthetic-seeded rows carry elevated-risk signals (engine.py) but are
    never scripted into a scenario, so they'd otherwise be unlabeled anomalies indistinguishable
    from clean data. Surface them explicitly as legitimate/false-positive-prone ground truth
    instead: they make a realistic hard-negative set (looks risky, isn't actually fraud), which
    also covers the previously-unused `clean_false_positive_count` config intent.
    Scenario-injected rows use the `_SCN_` id infix, so background rows are the ones without it.
    """
    cap = CFG.get("clean_false_positive_count")
    sessions = by(s.rows("login_sessions"), "session_id")
    beneficiaries = by(s.rows("beneficiaries"), "beneficiary_id")

    def valid_transaction_candidate(x):
        event_time = datetime.fromisoformat(x["transaction_at"])
        session = sessions.get(x["session_id"])
        beneficiary = beneficiaries.get(x["beneficiary_id"])
        if session and not (
            datetime.fromisoformat(session["login_at"])
            <= event_time
            <= datetime.fromisoformat(session["session_end_at"])
        ):
            return False
        if beneficiary and event_time < datetime.fromisoformat(beneficiary["added_at"]):
            return False
        return True

    tx_candidates = [
        x
        for x in s.rows("transactions")
        if "_SCN_" not in x["transaction_id"]
        and boolv(x["vpn_flag"])
        and valid_transaction_candidate(x)
    ]
    enabled_domains = set(CFG.get("enabled_domains", ["transaction", "loan"]))
    app_candidates = (
        [
            x
            for x in s.rows("loan_applications")
            if "_SCN_" not in x["application_id"]
            and boolv(x["is_vpn"])
            and boolv(x["is_emulator"])
        ]
        if "loan" in enabled_domains
        else []
    )
    r = rfor("background_hard_negatives")
    if cap:
        tx_candidates = r.sample(tx_candidates, min(cap, len(tx_candidates)))
        app_candidates = r.sample(app_candidates, min(cap, len(app_candidates)))
    for i, x in enumerate(tx_candidates, 1):
        t = datetime.fromisoformat(x["transaction_at"])
        append_manifest(
            man,
            f"EV_FPTXN_{i:04d}",
            "FP-TXN",
            "transaction",
            x["customer_id"],
            x["account_id"],
            x["transaction_id"],
            "",
            t,
            t + timedelta(minutes=5),
            ["R_TXN_VEL_001"],
            "HOLD",
            "High",
            label="false_positive_seed",
            desc="Background mule-seeded transaction investigated and confirmed legitimate",
        )
        append_entity(
            entities,
            f"EV_FPTXN_{i:04d}",
            "FP-TXN",
            "transaction",
            x["transaction_id"],
            "primary",
            "hard_negative",
            t,
            t + timedelta(minutes=5),
        )
    for i, x in enumerate(app_candidates, 1):
        t = datetime.fromisoformat(x["application_at"])
        append_manifest(
            man,
            f"EV_FPLOAN_{i:04d}",
            "FP-LOAN",
            "loan",
            x["customer_id"],
            "",
            "",
            x["application_id"],
            t,
            t + timedelta(hours=4),
            ["R_LOAN_SYN_001"],
            "MANUAL_REVIEW",
            "High",
            label="false_positive_seed",
            desc="Background synthetic-flagged application investigated and confirmed legitimate",
        )
    print(
        f"[SCENARIO] +{len(tx_candidates)} FP-TXN / +{len(app_candidates)} FP-LOAN hard-negative ground truth records"
    )


def inject_all():
    s = Store()
    coherent_personas(s)
    man = []
    entities = []
    enabled_domains = set(CFG.get("enabled_domains", ["transaction", "loan"]))
    if "transaction" in enabled_domains:
        inject_transaction(s, man, entities)
        inject_transaction_hard_negatives(s, man, entities)
    if "loan" in enabled_domains:
        inject_loan(s, man)
    collect_background_hard_negatives(s, man, entities)
    # Every labeled event contributes total weight 1, even burst/network scenarios with
    # many mapped transaction rows. Context-only links are intentionally left unweighted.
    event_sizes = {}
    for link in entities:
        if link["entity_type"] == "transaction" and link["label_scope"] in {
            "fraud",
            "hard_negative",
        }:
            event_sizes[link["event_id"]] = event_sizes.get(link["event_id"], 0) + 1
    for link in entities:
        size = event_sizes.get(link["event_id"])
        if size and link["entity_type"] == "transaction":
            link["sample_weight"] = round(1 / size, 8)
    with (OUT / "scenario_manifest.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_COLS)
        w.writeheader()
        w.writerows(man)
    with (OUT / "scenario_event_entities.csv").open(
        "w", encoding="utf-8", newline=""
    ) as f:
        w = csv.DictWriter(f, fieldnames=ENTITY_COLS)
        w.writeheader()
        w.writerows(entities)
    fraud_codes = {
        x["scenario_code"] for x in man if x["fraud_label"] == "confirmed_fraud"
    }
    print(
        f"[SCENARIO] injected {len(man)} scenario events across {len(fraud_codes)} fraud scenario codes"
    )
    print(f"[SCENARIO] wrote {len(entities)} explicit event-to-entity label mappings")
    return man


if __name__ == "__main__":
    inject_all()
