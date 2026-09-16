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
`SAS_TLS_VERIFY`, `SAS_CA_BUNDLE`, `SAS_EXPECTED_PACKAGE_VERSION`, and the
optional `SAS_ALERT_TRIAGE_URL` from `.env`. Demo labels can be configured with
`BANK_DISPLAY_NAME`, `BANK_DEMO_USER`, and `BANK_DEMO_BRANCH`.

## Application Fraud demo

1. Open **Hồ sơ mới**, complete the bank application form, optionally inspect or
   edit **Message JSON**, then run fraud screening.
2. Select **Xử lý hồ sơ hàng loạt**, download the template, upload a completed file,
   review whole-file validation, confirm, then choose **Chạy batch**.
3. Batch requests are sent sequentially in CSV order. They are not retried after
   an HTTP response because a request may already have updated SAS profiles.
4. Request success, fired rule, and alert creation are displayed separately and
   come from the real SAS response.

The form and JSON editor share one canonical effective payload. A validated JSON
edit is the exact object sent to SAS; later form edits patch only known paths and
preserve JSON-only additions. SAS Profile and Variable Rules continue to own all
7/30-day calculations.

The current repository captures prove that the Detection runtime returns fired
rules, reasons and alerted entities, but they do not contain an Alert Triage
`alertId`, and no verified authenticated lookup client exists in this console.
The data model therefore supports explicit `alertId`/`alertIdentifier` response
fields but keeps the value null and displays an honest unavailable message when
SAS does not return one. It never substitutes Application ID, Transaction ID,
Message ID or decision reference.

For development on the internal SSH host, forward the Streamlit port:

```bash
ssh -N -L 8501:127.0.0.1:8501 <user>@10.1.175.108
```

Then open `http://localhost:8501`. Do not expose this test console publicly.
