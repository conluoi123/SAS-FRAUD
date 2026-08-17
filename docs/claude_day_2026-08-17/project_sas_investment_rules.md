---
name: project-sas-investment-rules
description: "Advisory/roadmap for extending SAS Fraud rule coverage from Payments + Cards Issuing to a new \"Investment\" product line"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2f858c46-0db0-4970-af80-aa92e8b19e92
  modified: 2026-08-17T13:42:24.986Z
---

Thái asked for a senior BA/rule-design roadmap on extending the existing SAS Fraud rule library (Payments + Cards Issuing, see the source workbooks below) to cover a new "Investment"/brokerage product line — this is presale/solution-design work, distinct from the hands-on rule-building in [[project_sas_fraud_rules]].

**Source workbooks reviewed** (all in `C:\Users\ADMIN\Downloads\`): `Bảng profile hiện có.xlsx`, `Bảng mô tả các Schema hiện có.xlsx`, `Rule Templates SDA - Payments_v3.xlsx` (~26 rules, CK/BP/PT/FP/PP activity types), `Rule Templates SDA - Cards Issuing_v8.xlsx` (~30 rules, CC/DC + CA/CT activity types).

**Key finding:** the generic schemas (`Auth`, `Device`, `Digital`, `Location`, `Channel`, `Phone`) are entity-agnostic and port to Investment with zero schema work. Most Payments-side behavioral rules (dormant account, new-device/browser/OS, IP-country change, failed logins, z-score unusual-amount, high velocity, beneficiary watchlist/mule accounts) port 1:1 by swapping the account/entity key — these are the quick-win rule set.

**Scope not yet decided by Thái** (he dismissed the clarifying question, so this is still open): whether "Invest" means (a) fund-flow only (deposit/withdraw between payment account and investment account — cheap, ~80% reuse), (b) full trading lifecycle (order/execution/position — needs new Order/Instrument/Position schemas and a real-time order data feed that may not exist yet), or (c) phased rollout of both.

**Why:** likely feeding into a solution proposal / scope-of-work for a bank client, given Thái's role as Presale/Solution Consultant.

**How to apply:** if this resumes, re-ask the scope question before drafting new schema/rule-template Excel files — the effort estimate differs by an order of magnitude between (a) and (b), largely gated on whether the client's core trading/CTCK system can emit real-time Order/Execution/Position messages (unconfirmed). Deliverable format should mirror the existing rule-template workbooks' columns exactly (SFD Rule Name, Description, Rule, Variable Rule Name, Profile key, Decision Rule Code, Variable Rule Code) so it slots into the same documentation set.
