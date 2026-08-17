# SAS Message Test Console

Minimal Streamlit console for sending `Payment Fraud / GLOBAL` messages to the
SAS Detection runtime and inspecting decisions, fired rules, alerts, timings,
profiles, and the unmodified response body.

## Run

From the repository root:

```bash
python -m pip install -r requirements.txt
streamlit run app/streamlit_console/app.py --server.address 127.0.0.1 --server.port 8501
```

The app reads `SAS_DECISION_URL`, `SAS_REQUEST_TIMEOUT_SECONDS`,
`SAS_TLS_VERIFY`, and `SAS_CA_BUNDLE` from `.env`.

For development on the internal SSH host, forward the Streamlit port:

```bash
ssh -N -L 8501:127.0.0.1:8501 <user>@10.1.175.108
```

Then open `http://localhost:8501`. Do not expose this test console publicly.
