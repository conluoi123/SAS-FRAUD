# SAS Message Test Console

Streamlit console for sending both `Payment Fraud / GLOBAL` and
`Application Fraud / GLOBAL` messages to the same SAS Detection runtime.
Payment Fraud keeps its existing scenarios and payload. Application Fraud uses
a separate operational workspace for one-off requests and sequential CSV batches.

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
optional `SAS_ALERT_TRIAGE_URL` from `.env`.

## Application Fraud demo

1. Select **Application Fraud** and use **Nhập một hồ sơ** to inspect and send a
   single payload.
2. Select **Gửi hồ sơ từ CSV**, download the template, upload a completed file,
   review whole-file validation, confirm, then choose **Chạy batch**.
3. Batch requests are sent sequentially in CSV order. They are not retried after
   an HTTP response because a request may already have updated SAS profiles.
4. Request success, fired rule, and alert creation are displayed separately and
   come from the real SAS response.

The Streamlit frontend sends raw Application Fraud inputs only. SAS Profile and
Variable Rules own all 7/30-day calculations; profile history arrays are not UI
or CSV inputs.

For development on the internal SSH host, forward the Streamlit port:

```bash
ssh -N -L 8501:127.0.0.1:8501 <user>@10.1.175.108
```

Then open `http://localhost:8501`. Do not expose this test console publicly.
