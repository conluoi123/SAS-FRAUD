---
name: feedback-sas-fraud-rule-conventions
description: "Non-obvious SAS Fraud Decisioning conventions and gotchas established while building the debit-card fraud rules, that would otherwise cause silent bugs"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 2f858c46-0db0-4970-af80-aa92e8b19e92
  modified: 2026-08-17T13:42:03.800Z
---

Several conventions in the SAS Fraud Decisioning environment (see [[project_sas_fraud_rules]]) are counter-intuitive or undocumented on the surface. Do not "fix" or second-guess these without re-confirming on the live environment — they were each discovered the hard way during rule 1's build/test cycle.

- **`message.cardfinancial.cardPresentInd = '1'` means CNP (card-not-present / online), not card-present.** This reads backwards from the field name, but the sample rule shipped on this specific SAS environment defines it this way, and every end-to-end test currently relies on it. Never silently "correct" it to `'0'` for CNP logic.
  **Why:** confirmed against the environment's own sample rule; getting this backwards makes every CNP rule fire on the wrong transactions with no error.
  **How to apply:** when writing any new CNP-family rule, use `cardPresentInd = '1'` for CNP, and call this out explicitly in the rule's comment since the name invites the opposite reading.

- **Use `message.authentication`, never `message.auth`,** and read fields as `message.authentication.decision` / `.level` / `.result`. The frontend previously sent `message.auth` and the variable rule silently failed to update the profile because the path didn't match.
  **Why:** silent path mismatch, no compile/runtime error — just a profile that never updates.
  **How to apply:** always match the exact path the rule reads; don't assume a shorter/aliased path works.

- **`message.device.identifier` is the scalar device ID used in rule logic; `message.device.fingerprint` is an array `String[10]` and is NOT used in current logic** (send a valid value for schema completeness only, never assign it directly to a VARCHAR/String slot — causes `type mismatch` errors).
  **Why:** discovered via a "type mismatch... must be of type VARCHAR" runtime error when an array was assigned into a scalar profile slot.

- **The profile variable `knownDeviceFingerprint` is misnamed** — it actually stores `message.device.identifier` values (a known-device-ID list), not fingerprints. Renaming requires migrating the profile variable and both rules that reference it, so it's being left as-is for now with a clarifying comment. Don't rename it opportunistically mid-task; treat a rename as a deliberate, coordinated migration.

- **SAS rule syntax uses `^=` for "not equal", not `ne`.** `ne` throws `mismatched input 'ne' expecting {THEN, ';'}`.

- **`messageClassificationName` must be `GLOBAL`** for the current test endpoint — other values visible in the UI tree (e.g. `Southeast`, `Greater China`, `Central`) return HTTP 400 `ValidMessageClassification: GLOBAL`. The UI showing more options does not mean the runtime endpoint accepts them all.

- **Never trust the Production Rules list or a deployment's green checkmark alone to confirm what's live.** Always read `message.sas.system.packageVersion` from the actual response and compare against the expected/deployed package — package mismatches after deploy have happened before (e.g. "Runtime package mismatch: expected 50026, got 50021"). A Docker image registry digest (`registry.sas.env/fraud/bankingfraud@sha256:...`) is an artifact reference only, not the business-facing package version.

- **Don't manually seed profile values through the Streamlit FE's "Known device profile seed" fields** — those are FE-side readiness/expectation display only and don't write to SAS. To actually seed a known device, send a real qualifying CNP message (strong+successful auth) through the normal message flow so the variable rule updates the profile for real.

- **Variable rules only learn a device after a CNP transaction with *both* `authentication.level = 'HIGH'` AND `ecommerceAuthentication = 'SUCCESS'`** (not just `decision = 'ACCEPT'` alone) — this is a deliberate anti-poisoning design choice, not an oversight. Don't loosen this condition without discussing the fraud-risk tradeoff first.

**How to apply broadly:** before writing a new rule or debugging why one doesn't fire/update, check this list first — most "it's not working" cases in this project so far have traced back to one of these.
