---
name: project-sas-fraud-rules
description: Current state and roadmap of the SAS Fraud Decisioning rule-building project (20-30 rules + Streamlit test console)
metadata: 
  node_type: memory
  type: project
  originSessionId: 2f858c46-0db0-4970-af80-aa92e8b19e92
  modified: 2026-08-17T13:41:44.507Z
---

Building ~20-30 SAS Fraud Decisioning rules for `SAS Debit Card Fraud` project, tested end-to-end via an internal Streamlit console before eventually extending to other rule families (ATO, Transfer, Merchant, Check).

Full canonical handoff doc (source of truth, more detailed than this memory): [D:/Thực tập/HPT/SAS-FRAUD/docs/SAS_FRAUD_RULES_CHAT_HANDOFF.md](D:/Thực tập/HPT/SAS-FRAUD/docs/SAS_FRAUD_RULES_CHAT_HANDOFF.md) — last updated 2026-08-17. Re-read this file at the start of any session touching this project, since it is updated more often than this memory.

**Status as of 2026-08-17:**
- Rule 1 "CNP + thiết bị mới + xác thực yếu" (`rule_cnp_new_device_weak_auth` + variable rule `rule_var_update_known_device_fingerprint`) — implemented, deployed, tested end-to-end successfully (fires, declines, creates alert visible in Alert Triage).
- Rule 2 "CNP + merchant/MCC rủi ro cao" (`rule_cnp_risky_mcc`) — next up, prototype hard-coded in the handoff doc (candidate MCCs: 7995, 6051, 5944, 5732, 5816, 5967; amount threshold >300; action starts as Alert-only, not Decline, until tuned). Production version should move the MCC list into a SAS Advanced List (`Risky_MCC_List`) instead of hardcoding, but check a sample list rule already on the environment first for correct syntax.
- Remaining backlog: CNP + quốc gia/IP bất thường; CNP + velocity across merchants; then broader risk groups (Lost/Stolen Card, ATO, Wire/Transfer fraud, Bust-Out, Merchant Collusion, Refund/Chargeback abuse, Check Fraud, Synthetic Identity, Cross-Border/Impossible Travel).
- Streamlit console at `D:/Thực tập/HPT/SAS-FRAUD/app/streamlit_console` currently has one-tab-per-rule UI; flagged to refactor into a registry/config-driven design (per-scenario config: rule name, reason, schema, classification, default payload, expected action) grouped by rule family, before rule count exceeds 5-7.

**Why:** BA/rule-design work for a presale/solution engagement (bank fraud detection), incrementally proving out rules on a live SAS Fraud Decisioning environment before scaling up the rule count.

**How to apply:** When asked to write/test a new SAS fraud rule in this project, follow the 11-step process in section 17 of the handoff doc (confirm business action → map fields to the two schema/profile workbooks → decide if a Variable rule is needed → write bilingual VN comments → compile → configure Alert Type/Reason → deploy → record package version → write 1 positive + ≥3 negative tests → verify via `rulefired`/decision/alert/profile response fields and Alert Triage → tune thresholds via Impact Analysis only after logic is confirmed). See [[feedback-sas-fraud-rule-conventions]] for hard-won gotchas that aren't obvious from the code.

Reference workbooks used for field/profile lookup (also referenced in [[project_sas_investment_rules]] if that work continues): `Bảng mô tả các Schema hiện có.xlsx` and `Bảng profile hiện có.xlsx`, both in `C:\Users\ADMIN\Downloads\`.
