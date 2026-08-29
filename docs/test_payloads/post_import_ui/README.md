# Post-import Alert Page UI test

Run the payloads in numeric order. Each request uses a unique transaction ID.

Before the numbered UI sequence, use `00_noon_replay_control.json` when the same Rule 1 payload that worked earlier unexpectedly stops firing. This control preserves the earlier payload and changes only the request identifiers, timestamps, and the two synthetic debit numbers.

For this lab test, `message.debitcard.number` and `message.debitaccount.number` use the same synthetic identifier, matching the payload pattern that was verified successfully earlier.

| File | Entity | Expected result | Purpose |
|---|---|---|---|
| `01_baseline_same_entity.json` | `NKQ-23120347-A` | Profile update, no alert | Seed `knownDeviceFingerprint` using strong authentication and amount below the alert threshold. |
| `02_cnp_750_create_alert.json` | `NKQ-23120347-A` | Decline + Alert | Create the primary alert used to validate CNP Risk Signals. |
| `03_cnp_1200_high_queue.json` | `NKQ-23120347_v2` | Decline + Alert | Validate CNP fields and high-value routing independently. |
| `04_risky_mcc_rule2.json` | `NKQ-23120347_v3` | Rule 2 result | Regression-check the risky-MCC rule without modifying the primary CNP alert. |

After request 1, verify that `knownDeviceFingerprint[1]` contains `DEV-SEED-UI-2108-A`. Then send request 2 and find the alert by Entity ID `NKQ-23120347-A`. Validate the CNP Risk Signals pane before sending requests 3 and 4.

Expected values on the primary CNP alert:

```text
Transaction Amount:         750
Transaction Amount USD:     750
Card Present Indicator:     1
Device Identifier:          DEV-CNP750-UI-2108-A
Authentication Decision:    DENY
Authentication Level:       LOW
E-commerce Authentication:  FAILED
Merchant Name:              ECOM DIGITAL STORE
Merchant Category Code:     5411
```

`Decision Outcome` is populated only if the alerting event contains `message.sas.decision.outcome` after decision execution.
