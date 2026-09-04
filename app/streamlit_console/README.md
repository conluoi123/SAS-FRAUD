# SAS Message Test Console

Streamlit console for sending both `Payment Fraud / GLOBAL` and
`Application Fraud / GLOBAL` messages to the same SAS Detection runtime.
Payment Fraud keeps its existing scenarios and payload. Application Fraud uses
a separate form, payload builder, five deterministic scenarios, local 30-day
history features, response comparison, JSON download, and the shared Alert Log.

Application Fraud uses alert type `app_fraud_app` (Application Fraud
Application), entity type `sfd_application`, and alerting entity
`message.application.identifier`. It never sends `message.solution` or uses the
recycled `app_fraud_cust` alert type.

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

1. Select **Application Fraud** and **Scenario history**.
2. Start with **Scenario 01** and confirm no expected rule is shown.
3. Select one of scenarios 02–05. Its verification flags and synthetic history
   are reset automatically, and exactly one expected rule should be shown.
4. Inspect the payload, send it, and compare Expected Alert/Rules with the SAS
   response. Use the displayed Application ID to search Alert Triage.
5. Switch to **Session history** to derive counts only from successful HTTP
   submissions in the current Streamlit session. The clear button resets it.

The history, identity checks, income checks, and risk flags are synthetic POC
inputs. Streamlit computes the distinct-customer windows and sends them in
`message.appRisk`; it does not claim SAS Profile calculates those counts.

For development on the internal SSH host, forward the Streamlit port:

```bash
ssh -N -L 8501:127.0.0.1:8501 <user>@10.1.175.108
```

Then open `http://localhost:8501`. Do not expose this test console publicly.
