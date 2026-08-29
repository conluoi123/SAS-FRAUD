from generators.engine import CFG, M, gen, write
from generators.recompute_balances import recompute
from scenario_engine import inject_all
from rebuild_features import rebuild
from build_operations_v2 import build

# Generate raw/master tables first. Operation tables are rebuilt from scenario manifest.
enabled_domains = set(CFG.get("enabled_domains", ["transaction", "loan"]))
shared_tables = [
    "simulation_runs",
    "customers",
    "accounts",
    "devices",
    "login_sessions",
    "beneficiaries",
    "account_change_events",
    "transactions",
    "transaction_features",
    "auth_events",
]
loan_tables = [
    "sales_points",
    "sales_agents",
    "loan_applications",
    "applicant_declared_profiles",
    "employment_income_profiles",
    "reference_contacts",
    "application_documents",
    "credit_bureau_snapshots",
    "disbursement_accounts",
    "loan_repayment_outcomes",
]
for t in shared_tables:
    gen(t)
    print("[BASE]", t)
for t in loan_tables:
    if "loan" in enabled_domains:
        gen(t)
    else:
        write(t, M[t], [])
    print("[BASE]", t)
inject_all()
recompute()
rebuild()
build()
print("[DONE] V2 scenario-enriched dataset generated")
