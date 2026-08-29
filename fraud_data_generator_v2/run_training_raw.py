"""Generate and merge multiple independent raw transaction simulation runs.

The output remains normalized CSV tables. No feature mart, train/validation/test split,
or pre-joined `all` dataset is produced.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
TEMPLATE = ROOT / "config_training_transaction.json"
OUTPUT_ROOT = ROOT / "output_training_raw"
MERGED = OUTPUT_ROOT / "merged"
CONFIGS = OUTPUT_ROOT / "_configs"
CATALOG_TABLES = {"rules.csv"}
PRIMARY_KEYS = {
    "simulation_runs.csv": "simulation_run_id",
    "customers.csv": "customer_id",
    "accounts.csv": "account_id",
    "devices.csv": "device_id",
    "login_sessions.csv": "session_id",
    "beneficiaries.csv": "beneficiary_id",
    "account_change_events.csv": "change_event_id",
    "transactions.csv": "transaction_id",
    "transaction_features.csv": "transaction_id",
    "auth_events.csv": "auth_event_id",
    "scenario_manifest.csv": "event_id",
}


def run_command(script: str, config_path: Path) -> None:
    env = os.environ.copy()
    env["FRAUD_CONFIG"] = str(config_path.resolve())
    subprocess.run([sys.executable, str(ROOT / script)], cwd=ROOT, env=env, check=True)


def generate_runs(template: dict, run_count: int) -> list[dict]:
    CONFIGS.mkdir(parents=True, exist_ok=True)
    runs = []
    base_seed = int(template["random_seed"])
    for index in range(1, run_count + 1):
        run_id = f"RUN_TXN_TRAIN_{index:03d}"
        relative_output = f"output_training_raw/runs/run_{index:03d}"
        config = dict(template)
        config.update(
            simulation_run_id=run_id,
            random_seed=base_seed + index - 1,
            output_dir=relative_output,
        )
        config_path = CONFIGS / f"run_{index:03d}.json"
        config_path.write_text(
            json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\n[TRAINING] generating {run_id} seed={config['random_seed']}")
        run_command("run_all_v2.py", config_path)
        run_command("verify_data.py", config_path)
        runs.append(
            {
                "simulation_run_id": run_id,
                "random_seed": config["random_seed"],
                "output_dir": relative_output,
                "absolute_output": ROOT / relative_output,
            }
        )
    return runs


def merge_csvs(runs: list[dict]) -> dict[str, int]:
    MERGED.mkdir(parents=True, exist_ok=True)
    first_dir = runs[0]["absolute_output"]
    names = sorted(path.name for path in first_dir.glob("*.csv"))
    row_counts = {}
    for name in names:
        sources = [run["absolute_output"] / name for run in runs]
        if name in CATALOG_TABLES:
            sources = sources[:1]
        header = None
        count = 0
        with (MERGED / name).open("w", encoding="utf-8", newline="") as target:
            writer = None
            for source in sources:
                with source.open(encoding="utf-8", newline="") as handle:
                    reader = csv.DictReader(handle)
                    if header is None:
                        header = reader.fieldnames
                        writer = csv.DictWriter(target, fieldnames=header)
                        writer.writeheader()
                    elif reader.fieldnames != header:
                        raise RuntimeError(f"header mismatch while merging {name}")
                    for row in reader:
                        writer.writerow(row)
                        count += 1
        row_counts[name] = count
    return row_counts


def verify_merged(row_counts: dict[str, int]) -> None:
    for name, key in PRIMARY_KEYS.items():
        path = MERGED / name
        seen = set()
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                value = row[key]
                if not value or value in seen:
                    raise RuntimeError(f"{name}: empty or duplicate {key}: {value}")
                seen.add(value)
    transaction_ids = set()
    with (MERGED / "transactions.csv").open(encoding="utf-8", newline="") as handle:
        transaction_ids = {row["transaction_id"] for row in csv.DictReader(handle)}
    with (MERGED / "scenario_event_entities.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        missing = [
            row["entity_id"]
            for row in csv.DictReader(handle)
            if row["entity_type"] == "transaction"
            and row["entity_id"] not in transaction_ids
        ]
    if missing:
        raise RuntimeError(
            f"scenario_event_entities.csv: {len(missing)} missing transactions"
        )
    if row_counts.get("transactions.csv", 0) == 0:
        raise RuntimeError("merged transactions.csv is empty")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, help="override training_run_count")
    parser.add_argument(
        "--merge-only", action="store_true", help="reuse existing run folders"
    )
    args = parser.parse_args()
    template = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    run_count = args.runs or int(template.get("training_run_count", 5))
    if run_count < 2:
        raise SystemExit("Use at least 2 runs so seed-specific patterns can be audited")
    if args.merge_only:
        base_seed = int(template["random_seed"])
        runs = [
            {
                "simulation_run_id": f"RUN_TXN_TRAIN_{index:03d}",
                "random_seed": base_seed + index - 1,
                "output_dir": f"output_training_raw/runs/run_{index:03d}",
                "absolute_output": ROOT / f"output_training_raw/runs/run_{index:03d}",
            }
            for index in range(1, run_count + 1)
        ]
    else:
        runs = generate_runs(template, run_count)
    row_counts = merge_csvs(runs)
    verify_merged(row_counts)
    manifest = {
        "dataset_type": "raw_normalized_transaction_tables",
        "joined_dataset_created": False,
        "split_created": False,
        "run_count": run_count,
        "runs": [
            {k: v for k, v in run.items() if k != "absolute_output"} for run in runs
        ],
        "row_counts": row_counts,
        "label_bridge": "scenario_event_entities.csv",
        "split_recommendation": "split by customer_id or account_id after your own joins",
    }
    (MERGED / "dataset_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n[DONE] raw multi-table training dataset: {MERGED.relative_to(ROOT)}")
    print(
        f"[DONE] {row_counts['transactions.csv']} transactions across {run_count} independent seeds"
    )


if __name__ == "__main__":
    main()
