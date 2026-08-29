# Raw transaction dataset contract

## Grain and joins

Start from `transactions.csv` (one row per transaction), then join only what the
experiment needs:

| Table | Join key | Cardinality from transaction |
|---|---|---|
| `customers.csv` | `customer_id` | many-to-one |
| `accounts.csv` | `account_id` | many-to-one |
| `login_sessions.csv` | `session_id` | many-to-one |
| `devices.csv` | `device_id` | many-to-one |
| `beneficiaries.csv` | `beneficiary_id` | many-to-zero/one |
| `transaction_features.csv` | `transaction_id` | one-to-one |
| `auth_events.csv` | aggregate by account/session before `transaction_at` | many-to-one |
| `account_change_events.csv` | latest event before `transaction_at` | many-to-one |
| `scenario_event_entities.csv` | `entity_id = transaction_id` | label bridge |

The generator does not create a joined mart and does not split the data.

## Label mapping

- `target_fraud = 1`: transaction belongs to a confirmed fraud event.
- `target_fraud = 0, hard_negative = 1`: legitimate near-miss that resembles fraud.
- No bridge row: ordinary background transaction; map to `target_fraud = 0` after checking
  that the experiment intentionally includes background data.
- Use `sample_weight` when training so each scripted event contributes total weight 1.
- `label_scope = context_only` is context, not a positive transaction label.

## Split and leakage rules

- Split by `customer_id` or `account_id`, never random row split.
- Keep all five simulation runs represented when auditing stability across seeds.
- Never use IDs, `scenario_code`, `event_id`, `entity_role`, `label_scope`, operational
  outcomes, or fraud-ground-truth columns as model features.
- Time-window features must use records strictly earlier than `transaction_at`.
- Fit encoders, imputers, scalers, and feature selection on train only.

## Reproducible generation

```powershell
python run_training_raw.py
```

The merged raw tables and `dataset_manifest.json` are written to
`output_training_raw/merged/`.
