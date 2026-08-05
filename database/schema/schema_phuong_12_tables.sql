CREATE SCHEMA IF NOT EXISTS fraud_sim;

CREATE TABLE IF NOT EXISTS fraud_sim.sales_points (
    sales_point_id TEXT PRIMARY KEY,
    simulation_run_id TEXT REFERENCES fraud_sim.simulation_runs(simulation_run_id),
    sales_point_name TEXT NOT NULL,
    province TEXT NOT NULL,
    region TEXT NOT NULL,
    opened_at DATE NOT NULL,
    monthly_application_baseline NUMERIC(10, 2) NOT NULL CHECK (monthly_application_baseline >= 0),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'closed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fraud_sim.sales_agents (
    sales_agent_id TEXT PRIMARY KEY,
    simulation_run_id TEXT REFERENCES fraud_sim.simulation_runs(simulation_run_id),
    sales_point_id TEXT NOT NULL REFERENCES fraud_sim.sales_points(sales_point_id),
    sales_agent_name TEXT NOT NULL,
    join_date DATE NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('sales', 'team_lead', 'partner_staff', 'underwriter')),
    monthly_application_baseline NUMERIC(10, 2) NOT NULL CHECK (monthly_application_baseline >= 0),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'resigned', 'suspended')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fraud_sim.loan_applications (
    application_id TEXT PRIMARY KEY,
    simulation_run_id TEXT REFERENCES fraud_sim.simulation_runs(simulation_run_id),
    customer_id TEXT NOT NULL REFERENCES fraud_sim.customers(customer_id),
    application_at TIMESTAMPTZ(3) NOT NULL,
    loan_amount NUMERIC(18, 2) NOT NULL CHECK (loan_amount > 0),
    loan_term_months INTEGER NOT NULL CHECK (loan_term_months > 0),
    loan_product TEXT NOT NULL,
    loan_purpose TEXT NOT NULL,
    application_channel TEXT NOT NULL CHECK (application_channel IN ('branch', 'pos', 'online', 'partner', 'call_center')),
    message_type TEXT NOT NULL DEFAULT 'loan_application_submitted' CHECK (message_type IN ('loan_application_submitted', 'loan_application_status_changed', 'loan_disbursement_completed', 'loan_repayment_event')),
    sales_point_id TEXT NOT NULL REFERENCES fraud_sim.sales_points(sales_point_id),
    sales_agent_id TEXT NOT NULL REFERENCES fraud_sim.sales_agents(sales_agent_id),
    application_status TEXT NOT NULL CHECK (application_status IN ('submitted', 'in_review', 'approved', 'rejected', 'disbursed', 'cancelled')),
    underwriting_result TEXT CHECK (underwriting_result IN ('pass', 'fail', 'manual_review')),
    decision_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fraud_sim.application_digital_contexts (
    digital_context_id TEXT PRIMARY KEY,
    simulation_run_id TEXT REFERENCES fraud_sim.simulation_runs(simulation_run_id),
    application_id TEXT NOT NULL UNIQUE REFERENCES fraud_sim.loan_applications(application_id),
    device_id TEXT REFERENCES fraud_sim.devices(device_id),
    ip_address INET,
    user_agent TEXT,
    geo_lat NUMERIC(9, 6),
    geo_lon NUMERIC(9, 6),
    is_vpn BOOLEAN NOT NULL DEFAULT FALSE,
    is_proxy BOOLEAN NOT NULL DEFAULT FALSE,
    is_emulator BOOLEAN NOT NULL DEFAULT FALSE,
    submitted_at TIMESTAMPTZ(3) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fraud_sim.applicant_declared_profiles (
    declared_profile_id TEXT PRIMARY KEY,
    simulation_run_id TEXT REFERENCES fraud_sim.simulation_runs(simulation_run_id),
    application_id TEXT NOT NULL UNIQUE REFERENCES fraud_sim.loan_applications(application_id),
    customer_id TEXT NOT NULL REFERENCES fraud_sim.customers(customer_id),
    declared_full_name TEXT NOT NULL,
    declared_id_number_hash TEXT NOT NULL,
    declared_dob DATE NOT NULL,
    declared_phone_hash TEXT NOT NULL,
    declared_email_hash TEXT,
    declared_permanent_address TEXT NOT NULL,
    declared_current_address TEXT NOT NULL,
    declared_marital_status TEXT CHECK (declared_marital_status IN ('single', 'married', 'divorced', 'widowed', 'unknown')),
    declared_dependents INTEGER NOT NULL CHECK (declared_dependents >= 0),
    address_cluster_id TEXT NOT NULL,
    profile_similarity_cluster_id TEXT,
    address_quality_score NUMERIC(5, 2) CHECK (address_quality_score IS NULL OR address_quality_score BETWEEN 0 AND 100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fraud_sim.employment_income_profiles (
    employment_id TEXT PRIMARY KEY,
    simulation_run_id TEXT REFERENCES fraud_sim.simulation_runs(simulation_run_id),
    application_id TEXT NOT NULL UNIQUE REFERENCES fraud_sim.loan_applications(application_id),
    occupation_group TEXT NOT NULL,
    employer_name TEXT NOT NULL,
    employer_phone_hash TEXT,
    employer_phone_cluster_id TEXT,
    employer_phone_verification_status TEXT CHECK (employer_phone_verification_status IS NULL OR employer_phone_verification_status IN ('not_checked', 'verified', 'unreachable', 'mismatch', 'suspicious')),
    is_employer_phone_reused BOOLEAN NOT NULL DEFAULT FALSE,
    employer_address TEXT NOT NULL,
    employment_start_date DATE,
    months_at_employer INTEGER CHECK (months_at_employer IS NULL OR months_at_employer >= 0),
    declared_monthly_income NUMERIC(18, 2) NOT NULL CHECK (declared_monthly_income >= 0),
    income_document_type TEXT NOT NULL CHECK (income_document_type IN ('payslip', 'bank_statement', 'labor_contract', 'tax_record', 'self_declared', 'none')),
    employer_cluster_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fraud_sim.sales_point_performance_snapshots (
    sales_point_snapshot_id TEXT PRIMARY KEY,
    simulation_run_id TEXT REFERENCES fraud_sim.simulation_runs(simulation_run_id),
    sales_point_id TEXT NOT NULL REFERENCES fraud_sim.sales_points(sales_point_id),
    as_of_at TIMESTAMPTZ(3) NOT NULL,
    observation_window_days INTEGER NOT NULL CHECK (observation_window_days > 0),
    total_applications INTEGER NOT NULL DEFAULT 0 CHECK (total_applications >= 0),
    approved_applications INTEGER NOT NULL DEFAULT 0 CHECK (approved_applications >= 0),
    historical_bad_rate NUMERIC(8, 4) CHECK (historical_bad_rate IS NULL OR historical_bad_rate BETWEEN 0 AND 1),
    historical_fraud_rate NUMERIC(8, 4) CHECK (historical_fraud_rate IS NULL OR historical_fraud_rate BETWEEN 0 AND 1),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (sales_point_id, as_of_at, observation_window_days)
);

CREATE TABLE IF NOT EXISTS fraud_sim.sales_agent_performance_snapshots (
    sales_agent_snapshot_id TEXT PRIMARY KEY,
    simulation_run_id TEXT REFERENCES fraud_sim.simulation_runs(simulation_run_id),
    sales_agent_id TEXT NOT NULL REFERENCES fraud_sim.sales_agents(sales_agent_id),
    as_of_at TIMESTAMPTZ(3) NOT NULL,
    observation_window_days INTEGER NOT NULL CHECK (observation_window_days > 0),
    total_applications INTEGER NOT NULL DEFAULT 0 CHECK (total_applications >= 0),
    approved_applications INTEGER NOT NULL DEFAULT 0 CHECK (approved_applications >= 0),
    historical_approval_rate NUMERIC(8, 4) CHECK (historical_approval_rate IS NULL OR historical_approval_rate BETWEEN 0 AND 1),
    historical_bad_rate NUMERIC(8, 4) CHECK (historical_bad_rate IS NULL OR historical_bad_rate BETWEEN 0 AND 1),
    historical_fraud_rate NUMERIC(8, 4) CHECK (historical_fraud_rate IS NULL OR historical_fraud_rate BETWEEN 0 AND 1),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (sales_agent_id, as_of_at, observation_window_days)
);

CREATE TABLE IF NOT EXISTS fraud_sim.reference_contacts (
    reference_id TEXT PRIMARY KEY,
    simulation_run_id TEXT REFERENCES fraud_sim.simulation_runs(simulation_run_id),
    application_id TEXT NOT NULL REFERENCES fraud_sim.loan_applications(application_id),
    reference_name TEXT NOT NULL,
    relationship TEXT NOT NULL,
    reference_phone_hash TEXT NOT NULL,
    phone_reuse_count INTEGER NOT NULL DEFAULT 1 CHECK (phone_reuse_count >= 1),
    reference_quality_score NUMERIC(5, 2) CHECK (reference_quality_score IS NULL OR reference_quality_score BETWEEN 0 AND 100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fraud_sim.disbursement_accounts (
    disbursement_id TEXT PRIMARY KEY,
    simulation_run_id TEXT REFERENCES fraud_sim.simulation_runs(simulation_run_id),
    application_id TEXT NOT NULL UNIQUE REFERENCES fraud_sim.loan_applications(application_id),
    receiving_account_hash TEXT NOT NULL,
    receiving_account_name TEXT NOT NULL,
    receiving_bank TEXT NOT NULL,
    same_as_applicant BOOLEAN NOT NULL,
    account_reuse_count INTEGER NOT NULL DEFAULT 1 CHECK (account_reuse_count >= 1),
    linked_account_id TEXT REFERENCES fraud_sim.accounts(account_id),
    disbursement_status TEXT NOT NULL CHECK (disbursement_status IN ('pending', 'completed', 'failed', 'cancelled')),
    disbursed_at TIMESTAMPTZ,
    disbursed_amount NUMERIC(18, 2) CHECK (disbursed_amount IS NULL OR disbursed_amount >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fraud_sim.application_documents (
    document_id TEXT PRIMARY KEY,
    simulation_run_id TEXT REFERENCES fraud_sim.simulation_runs(simulation_run_id),
    application_id TEXT NOT NULL REFERENCES fraud_sim.loan_applications(application_id),
    document_type TEXT NOT NULL CHECK (document_type IN ('id_card_front', 'id_card_back', 'payslip', 'bank_statement', 'labor_contract', 'utility_bill', 'selfie', 'other')),
    document_hash TEXT NOT NULL,
    submitted_at TIMESTAMPTZ NOT NULL,
    ocr_quality_score NUMERIC(5, 2) CHECK (ocr_quality_score IS NULL OR ocr_quality_score BETWEEN 0 AND 100),
    tamper_score NUMERIC(5, 2) CHECK (tamper_score IS NULL OR tamper_score BETWEEN 0 AND 100),
    missing_field_count INTEGER NOT NULL DEFAULT 0 CHECK (missing_field_count >= 0),
    duplicate_document_hash_count INTEGER NOT NULL DEFAULT 1 CHECK (duplicate_document_hash_count >= 1),
    id_front_back_match_flag BOOLEAN,
    id_expired_flag BOOLEAN,
    face_match_score NUMERIC(6, 4) CHECK (face_match_score IS NULL OR face_match_score BETWEEN 0 AND 1),
    liveness_result TEXT CHECK (liveness_result IS NULL OR liveness_result IN ('pass', 'fail', 'not_applicable')),
    document_result TEXT NOT NULL CHECK (document_result IN ('accepted', 'rejected', 'manual_review')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fraud_sim.credit_bureau_snapshots (
    bureau_snapshot_id TEXT PRIMARY KEY,
    simulation_run_id TEXT REFERENCES fraud_sim.simulation_runs(simulation_run_id),
    application_id TEXT NOT NULL UNIQUE REFERENCES fraud_sim.loan_applications(application_id),
    bureau_score INTEGER CHECK (bureau_score IS NULL OR bureau_score BETWEEN 0 AND 1000),
    active_loan_count INTEGER NOT NULL DEFAULT 0 CHECK (active_loan_count >= 0),
    dpd_max_12m INTEGER NOT NULL DEFAULT 0 CHECK (dpd_max_12m >= 0),
    recent_inquiry_count INTEGER NOT NULL DEFAULT 0 CHECK (recent_inquiry_count >= 0),
    thin_file_flag BOOLEAN NOT NULL DEFAULT FALSE,
    bureau_match_result TEXT NOT NULL CHECK (bureau_match_result IN ('full_match', 'partial_match', 'no_hit')),
    snapshot_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fraud_sim.underwriting_decisions (
    decision_id TEXT PRIMARY KEY,
    simulation_run_id TEXT REFERENCES fraud_sim.simulation_runs(simulation_run_id),
    application_id TEXT NOT NULL REFERENCES fraud_sim.loan_applications(application_id),
    decision_at TIMESTAMPTZ NOT NULL,
    decision_type TEXT NOT NULL CHECK (decision_type IN ('auto_approve', 'auto_reject', 'manual_review', 'manual_approve', 'manual_reject')),
    scorecard_score NUMERIC(5, 2) CHECK (scorecard_score IS NULL OR scorecard_score BETWEEN 0 AND 100),
    fraud_rule_hit_count INTEGER NOT NULL DEFAULT 0 CHECK (fraud_rule_hit_count >= 0),
    manual_override_flag BOOLEAN NOT NULL DEFAULT FALSE,
    decision_reason_code TEXT,
    approved_amount NUMERIC(18, 2) CHECK (approved_amount IS NULL OR approved_amount >= 0),
    underwriter_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fraud_sim.loan_decision_outcomes (
    decision_outcome_id TEXT PRIMARY KEY,
    simulation_run_id TEXT REFERENCES fraud_sim.simulation_runs(simulation_run_id),
    application_id TEXT NOT NULL REFERENCES fraud_sim.loan_applications(application_id),
    message_id TEXT,
    decision_at TIMESTAMPTZ(3) NOT NULL,
    decision_flag TEXT NOT NULL CHECK (decision_flag IN ('ACCEPT', 'DECLINE', 'HOLD', 'CHALLENGE', 'ALERT_ONLY', 'MANUAL_REVIEW')),
    risk_score NUMERIC(8, 4) CHECK (risk_score IS NULL OR risk_score BETWEEN 0 AND 1),
    reason_codes TEXT[] NOT NULL DEFAULT '{}',
    alert_recommended BOOLEAN NOT NULL DEFAULT FALSE,
    alert_type TEXT,
    triage_queue TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fraud_sim.loan_repayment_outcomes (
    loan_id TEXT PRIMARY KEY,
    simulation_run_id TEXT REFERENCES fraud_sim.simulation_runs(simulation_run_id),
    application_id TEXT NOT NULL UNIQUE REFERENCES fraud_sim.loan_applications(application_id),
    disbursed_at TIMESTAMPTZ NOT NULL,
    first_due_date DATE NOT NULL,
    first_payment_status TEXT NOT NULL CHECK (first_payment_status IN ('paid', 'partial', 'missed', 'not_due')),
    dpd_30_flag BOOLEAN NOT NULL DEFAULT FALSE,
    dpd_60_flag BOOLEAN NOT NULL DEFAULT FALSE,
    dpd_90_flag BOOLEAN NOT NULL DEFAULT FALSE,
    contactable_after_disbursement BOOLEAN NOT NULL DEFAULT TRUE,
    early_default_flag BOOLEAN NOT NULL DEFAULT FALSE,
    writeoff_amount NUMERIC(18, 2) NOT NULL DEFAULT 0 CHECK (writeoff_amount >= 0),
    outcome_observed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fraud_sim.loan_fraud_ground_truth (
    loan_fraud_event_id TEXT PRIMARY KEY,
    simulation_run_id TEXT REFERENCES fraud_sim.simulation_runs(simulation_run_id),
    scenario_code TEXT NOT NULL,
    start_at TIMESTAMPTZ NOT NULL,
    end_at TIMESTAMPTZ NOT NULL,
    fraud_label TEXT NOT NULL CHECK (fraud_label IN ('suspected_fraud', 'confirmed_fraud', 'false_positive_seed')),
    fraud_outcome TEXT NOT NULL,
    injection_method TEXT NOT NULL,
    expected_decision_flag TEXT NOT NULL CHECK (expected_decision_flag IN ('ACCEPT', 'DECLINE', 'HOLD', 'CHALLENGE', 'ALERT_ONLY', 'MANUAL_REVIEW')),
    expected_alert_type TEXT,
    expected_queue TEXT,
    CHECK (end_at >= start_at)
);

CREATE TABLE IF NOT EXISTS fraud_sim.loan_rule_catalog (
    rule_code TEXT PRIMARY KEY,
    rule_name TEXT NOT NULL,
    scenario_code TEXT NOT NULL,
    message_type TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('Low', 'Medium', 'High', 'Critical')),
    default_decision_flag TEXT NOT NULL CHECK (default_decision_flag IN ('ACCEPT', 'DECLINE', 'HOLD', 'CHALLENGE', 'ALERT_ONLY', 'MANUAL_REVIEW')),
    reason_code TEXT NOT NULL UNIQUE,
    description TEXT,
    active_flag BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fraud_sim.loan_expected_rule_hits (
    loan_fraud_event_id TEXT NOT NULL REFERENCES fraud_sim.loan_fraud_ground_truth(loan_fraud_event_id),
    rule_code TEXT NOT NULL REFERENCES fraud_sim.loan_rule_catalog(rule_code),
    expected_reason_code TEXT NOT NULL,
    expected_hit BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (loan_fraud_event_id, rule_code)
);

CREATE TABLE IF NOT EXISTS fraud_sim.loan_message_inventory (
    message_type TEXT PRIMARY KEY,
    monetary_flag BOOLEAN NOT NULL,
    source_domain TEXT NOT NULL,
    sas_project TEXT NOT NULL,
    sas_message_schema TEXT NOT NULL,
    expected_integration_pattern TEXT NOT NULL CHECK (expected_integration_pattern IN ('REST_SYNC', 'REST_ASYNC', 'KAFKA_ASYNC', 'BATCH')),
    max_attribute_count INTEGER NOT NULL DEFAULT 30 CHECK (max_attribute_count BETWEEN 1 AND 30),
    description TEXT
);

CREATE TABLE IF NOT EXISTS fraud_sim.loan_message_variable_mappings (
    mapping_id TEXT PRIMARY KEY,
    message_type TEXT NOT NULL REFERENCES fraud_sim.loan_message_inventory(message_type),
    source_table TEXT NOT NULL,
    source_column TEXT NOT NULL,
    sas_variable_path TEXT NOT NULL,
    data_type TEXT NOT NULL,
    mandatory_level TEXT NOT NULL CHECK (mandatory_level IN ('mandatory', 'recommended', 'optional')),
    transform_rule TEXT,
    dq_rule TEXT,
    include_in_mvp BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (message_type, sas_variable_path)
);

CREATE TABLE IF NOT EXISTS fraud_sim.loan_profile_variable_catalog (
    profile_variable_id TEXT PRIMARY KEY,
    profile_set_name TEXT NOT NULL,
    entity_key_variable_path TEXT NOT NULL,
    profile_variable_name TEXT NOT NULL,
    window_definition TEXT NOT NULL,
    calculation_logic TEXT NOT NULL,
    used_by_rule_code TEXT REFERENCES fraud_sim.loan_rule_catalog(rule_code),
    leakage_safe_rule TEXT NOT NULL DEFAULT 'Use only events with event_time < current_message_time',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (profile_set_name, profile_variable_name, window_definition)
);

CREATE TABLE IF NOT EXISTS fraud_sim.loan_fraud_event_applications (
    loan_fraud_event_id TEXT NOT NULL REFERENCES fraud_sim.loan_fraud_ground_truth(loan_fraud_event_id),
    application_id TEXT NOT NULL REFERENCES fraud_sim.loan_applications(application_id),
    event_role TEXT NOT NULL DEFAULT 'related',
    PRIMARY KEY (loan_fraud_event_id, application_id)
);

CREATE TABLE IF NOT EXISTS fraud_sim.loan_fraud_event_customers (
    loan_fraud_event_id TEXT NOT NULL REFERENCES fraud_sim.loan_fraud_ground_truth(loan_fraud_event_id),
    customer_id TEXT NOT NULL REFERENCES fraud_sim.customers(customer_id),
    event_role TEXT NOT NULL DEFAULT 'related',
    PRIMARY KEY (loan_fraud_event_id, customer_id)
);

CREATE TABLE IF NOT EXISTS fraud_sim.loan_fraud_event_sales_agents (
    loan_fraud_event_id TEXT NOT NULL REFERENCES fraud_sim.loan_fraud_ground_truth(loan_fraud_event_id),
    sales_agent_id TEXT NOT NULL REFERENCES fraud_sim.sales_agents(sales_agent_id),
    event_role TEXT NOT NULL DEFAULT 'related',
    PRIMARY KEY (loan_fraud_event_id, sales_agent_id)
);

CREATE TABLE IF NOT EXISTS fraud_sim.loan_fraud_event_sales_points (
    loan_fraud_event_id TEXT NOT NULL REFERENCES fraud_sim.loan_fraud_ground_truth(loan_fraud_event_id),
    sales_point_id TEXT NOT NULL REFERENCES fraud_sim.sales_points(sales_point_id),
    event_role TEXT NOT NULL DEFAULT 'related',
    PRIMARY KEY (loan_fraud_event_id, sales_point_id)
);

CREATE INDEX IF NOT EXISTS idx_sales_agents_point ON fraud_sim.sales_agents(sales_point_id);
CREATE INDEX IF NOT EXISTS idx_loan_app_customer_time ON fraud_sim.loan_applications(customer_id, application_at);
CREATE INDEX IF NOT EXISTS idx_loan_app_sales_agent_time ON fraud_sim.loan_applications(sales_agent_id, application_at);
CREATE INDEX IF NOT EXISTS idx_loan_app_sales_point_time ON fraud_sim.loan_applications(sales_point_id, application_at);
CREATE INDEX IF NOT EXISTS idx_declared_id_hash ON fraud_sim.applicant_declared_profiles(declared_id_number_hash);
CREATE INDEX IF NOT EXISTS idx_declared_phone_hash ON fraud_sim.applicant_declared_profiles(declared_phone_hash);
CREATE INDEX IF NOT EXISTS idx_declared_address_cluster ON fraud_sim.applicant_declared_profiles(address_cluster_id);
CREATE INDEX IF NOT EXISTS idx_reference_phone_hash ON fraud_sim.reference_contacts(reference_phone_hash);
CREATE INDEX IF NOT EXISTS idx_digital_context_device_time ON fraud_sim.application_digital_contexts(device_id, submitted_at) WHERE device_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_digital_context_ip_time ON fraud_sim.application_digital_contexts(ip_address, submitted_at) WHERE ip_address IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_employer_phone_hash ON fraud_sim.employment_income_profiles(employer_phone_hash) WHERE employer_phone_hash IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_sales_agent_snapshots_time ON fraud_sim.sales_agent_performance_snapshots(sales_agent_id, as_of_at);
CREATE INDEX IF NOT EXISTS idx_sales_point_snapshots_time ON fraud_sim.sales_point_performance_snapshots(sales_point_id, as_of_at);
CREATE INDEX IF NOT EXISTS idx_disbursement_account_hash ON fraud_sim.disbursement_accounts(receiving_account_hash);
CREATE INDEX IF NOT EXISTS idx_documents_hash ON fraud_sim.application_documents(document_hash);
CREATE INDEX IF NOT EXISTS idx_loan_ground_truth_scenario ON fraud_sim.loan_fraud_ground_truth(scenario_code, start_at);
CREATE INDEX IF NOT EXISTS idx_loan_decision_outcomes_app_time ON fraud_sim.loan_decision_outcomes(application_id, decision_at);
CREATE INDEX IF NOT EXISTS idx_loan_profile_catalog_set ON fraud_sim.loan_profile_variable_catalog(profile_set_name, profile_variable_name);
