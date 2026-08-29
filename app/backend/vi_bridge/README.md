# vi_bridge — Alert Triage → Visual Investigator bridge

Status: **Phần B only** (everything except reading from Kafka). See the
chat log dated 2026-08-24/25 for the full investigation that led here.

## What works today

- `config.py` — loads VI connection settings from `.env`.
- `auth.py` — gets an OAuth token from `/SASLogon/oauth/token` (verified
  flow, matches `docs/visual-investigator-alert-integration-runbook.md`
  section 7).
- `mapping.py` — the one lookup table deciding which VI entity type a
  `transactionTypeId` maps to. Only `DCCA` → `CNP_Debit_Account_Quoc` is
  filled in (the case that was manually tested end-to-end).
- `vi_client.py` — calls the two real SAS REST APIs:
  - `svi-datahub` (find/create the "Known Object") — endpoints and body
    shapes confirmed from the official OpenAPI spec
    (`svi-datahub-v11/specifications/openapi.yml`), not guessed.
  - `svi-alert` (`POST /svi-alert/alertingEvents`) — already verified
    working (HTTP 201) via the manual PowerShell runbook.
- `builder.py` — turns a `transaction-topic-mark` message into the JSON
  payload VI expects.
- `run_manual_test.py` — runs the whole chain above against the **real**
  sample mark message in `sample_data/`, standing in for "a message just
  read from Kafka". No Kafka connection required.

## What's missing (Phần A — blocked)

Actually reading `transaction-topic-mark` from Kafka. Blocked on getting
the real Kafka bootstrap server address (or Kubernetes access to deploy
the consumer inside the cluster) from the SAS admin/mentor — `kafka.sas.env`
only exposes the web UI (port 443), not the Kafka wire protocol
(9092/9093/9094/29092/9096 all tested closed from the intern's VPN'd
machine).

## Before the first real run, verify

1. **`svi-datahub` base path** (`vi_client.py` top comment): assumed to be
   `{VI_BASE_URL}/svi-datahub/...`, following the same pattern as the
   already-working `/svi-alert/...`. Not yet tested live — if the first
   call 404s, ask a VI admin for the correct path.
2. **`.env`**: copy from `.env.example` and fill in `VI_USERNAME` /
   `VI_PASSWORD`.

## Known gap: enrichment fields

The real `transaction-topic-mark` message does not carry
`transactionAmount`, `merchantName`, `authenticationDecision`, etc. — only
what `builder.py` puts under `enrichment` today. If analysts need the
richer fields seen in the original manual demo
(`cnp-vi-alerting-event.json`), a future version must look up the full
transaction by `markProperties.transactionId` (likely in the Alert
Triage `alerts_transaction.DCCA` Postgres table) before calling
`build_alerting_event`.

## Run it

```powershell
cd "SAS-FRAUD"
python -m app.backend.vi_bridge.run_manual_test
```
