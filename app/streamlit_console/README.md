# Loan Application Portal

Customer-demo-ready simulated bank front office for loan origination and
Application Fraud screening. The default workspace is the Vietnamese teller
flow; the legacy Payment Fraud scenario console remains available as a secondary
technical workspace.

Application Fraud uses alert type `app_fraud_app` (Application Fraud
Application), entity type `sfd_application`, and alerting entity
`message.application.identifier`. Its discriminator is `originationType=AP` and
`activityType=SB`; channel codes come from `application_config.py`.

## Run

From the repository root:

```bash
python -m pip install -r requirements.txt
streamlit run app/streamlit_console/app.py --server.address 127.0.0.1 --server.port 8501
```

The app reads `SAS_DECISION_URL`, `SAS_REQUEST_TIMEOUT_SECONDS`,
`SAS_TLS_VERIFY`, `SAS_CA_BUNDLE`, and `SAS_EXPECTED_PACKAGE_VERSION` from
`.env`. Demo labels can be configured with `BANK_DISPLAY_NAME`,
`BANK_DEMO_USER`, and `BANK_DEMO_BRANCH`.

## Application Fraud demo

1. Open **Hồ sơ mới**, complete the bank application form, optionally inspect or
   edit **Message JSON**, then run fraud screening.
2. Select **Xử lý hồ sơ hàng loạt**, download the template, upload a completed file,
   review whole-file validation, confirm, then choose **Chạy batch**.
3. Batch requests are sent sequentially in CSV order. They are not retried after
   an HTTP response because a request may already have updated SAS profiles.
4. Request success, fired rule, and alert creation are displayed separately and
   come from the real SAS response.

Every Application Fraud request actually submitted from Single Application,
the final Guided Demo step, or a valid Batch row is written to the local
`.application_history.json` feed. **Hồ sơ đã xử lý** shows both alert and
no-alert results; **Nhật ký cảnh báo** remains a separate alert-only feed.
Transaction identifiers provide the primary deduplication key so Streamlit
reruns do not duplicate history records. Guided Demo seed requests and invalid,
unsent CSV rows are excluded.

The form and JSON editor share one canonical effective payload. A validated JSON
edit is the exact object sent to SAS; later form edits patch only known paths and
preserve JSON-only additions. SAS Profile and Variable Rules continue to own all
7/30-day calculations.

The current POC traceability path ends at the Detection Runtime response. The
runtime returns the fraud decision, fired rule, reason, alert flag, and the
alerted entity in `message.sas.alerted[].outcomeEntity` with its type in
`outcomeEntityType`. The portal presents every returned entity as the factual
search/correlation key a user can use in SAS Alert Triage.

Correlation beyond the returned alerted entity would require source-event
integrations outside the current Streamlit scope. The portal consistently uses
the SAS-returned alerted entity as the Alert Triage search value and never
relabels another application or message identifier as that value.

For development on the internal SSH host, forward the Streamlit port:

```bash
ssh -N -L 8501:127.0.0.1:8501 <user>@10.1.175.108
```

Then open `http://localhost:8501`. Do not expose this test console publicly.
