CREATE SCHEMA IF NOT EXISTS fraud_sim;

-- ============================================================
-- MVP SAS FRAUD SIMULATION SCHEMA
-- Shared by Phuong and Quoc
--
-- Design goal:
-- - Keep only tables the team can explain, generate, and demo now.
-- - Support both transaction fraud and loan application fraud.
-- - Defer advanced SAS mappings, rule versioning, graph, and audit logs.
-- ============================================================

-- ============================================================
-- 1. SHARED FOUNDATION - USED BY BOTH PHUONG AND QUOC
-- ============================================================

CREATE TABLE IF NOT EXISTS fraud_sim.simulation_runs (
    simulation_run_id TEXT PRIMARY KEY,
    run_name TEXT NOT NULL,
    dataset_version TEXT NOT NULL,
    random_seed BIGINT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ,
    run_status TEXT NOT NULL CHECK (run_status IN ('RUNNING', 'COMPLETED', 'FAILED')),
    configuration JSONB,
    created_by TEXT NOT NULL DEFAULT 'simulator',
    -- [P0] Đảm bảo completed_at luôn >= started_at
    CHECK (completed_at IS NULL OR completed_at >= started_at),
    -- [P0] Nếu RUNNING thì completed_at phải NULL; COMPLETED/FAILED thì completed_at NOT NULL
    CHECK (
        (run_status = 'RUNNING' AND completed_at IS NULL)
        OR run_status IN ('COMPLETED', 'FAILED')
    )
);

CREATE TABLE IF NOT EXISTS fraud_sim.customers (
    customer_id TEXT PRIMARY KEY,
    simulation_run_id TEXT NOT NULL REFERENCES fraud_sim.simulation_runs(simulation_run_id),
    customer_type TEXT NOT NULL CHECK (customer_type IN ('individual', 'sme', 'corporate')),
    full_name TEXT NOT NULL,
    gender TEXT CHECK (gender IN ('M', 'F', 'U')),
    dob DATE NOT NULL,
    id_number_hash TEXT NOT NULL,
    phone_hash TEXT NOT NULL,
    email_hash TEXT NOT NULL,
    province TEXT NOT NULL,
    address_cluster_id TEXT NOT NULL,
    phone_cluster_id TEXT NOT NULL,
    occupation_group TEXT NOT NULL,
    income_band TEXT NOT NULL,
    customer_segment TEXT NOT NULL CHECK (customer_segment IN ('student', 'mass', 'payroll', 'affluent', 'sme')),
    onboarding_channel TEXT NOT NULL CHECK (onboarding_channel IN ('branch', 'ekyc', 'partner', 'loan_application')),
    onboarding_date DATE NOT NULL,
    kyc_level TEXT NOT NULL CHECK (kyc_level IN ('basic', 'standard', 'biometric_verified', 'enhanced')),
    base_risk_level TEXT NOT NULL CHECK (base_risk_level IN ('Low', 'Medium', 'High')),
    customer_status TEXT NOT NULL DEFAULT 'active' CHECK (customer_status IN ('active', 'inactive', 'blocked', 'closed')),
    is_synthetic_identity_seed BOOLEAN NOT NULL DEFAULT FALSE,
    is_mule_candidate_seed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fraud_sim.accounts (
    account_id TEXT PRIMARY KEY,
    simulation_run_id TEXT NOT NULL REFERENCES fraud_sim.simulation_runs(simulation_run_id),
    customer_id TEXT NOT NULL REFERENCES fraud_sim.customers(customer_id),
    account_no_hash TEXT NOT NULL UNIQUE,
    account_type TEXT NOT NULL CHECK (account_type IN ('CASA', 'payroll', 'savings', 'business', 'loan_disbursement')),
    account_currency TEXT NOT NULL DEFAULT 'VND',
    open_date DATE NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active', 'dormant', 'frozen', 'closed')),
    branch_code TEXT,
    account_opening_channel TEXT CHECK (account_opening_channel IN ('branch', 'ekyc', 'partner', 'migration', 'loan_disbursement')),
    home_province TEXT NOT NULL,
    daily_transfer_limit NUMERIC(18, 2) NOT NULL CHECK (daily_transfer_limit >= 0),
    single_txn_limit NUMERIC(18, 2) NOT NULL CHECK (single_txn_limit >= 0),
    average_balance NUMERIC(18, 2) NOT NULL CHECK (average_balance >= 0),
    dormant_since TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (account_id, customer_id)
);

CREATE TABLE IF NOT EXISTS fraud_sim.devices (
    device_id TEXT PRIMARY KEY,
    simulation_run_id TEXT NOT NULL REFERENCES fraud_sim.simulation_runs(simulation_run_id),
    device_fingerprint TEXT NOT NULL UNIQUE,
    device_type TEXT NOT NULL CHECK (device_type IN ('mobile', 'desktop', 'tablet', 'atm', 'pos', 'internal_terminal')),
    os TEXT NOT NULL,
    first_seen_at TIMESTAMPTZ NOT NULL,
    trust_status TEXT NOT NULL CHECK (trust_status IN ('trusted', 'new', 'suspicious', 'blocked')),
    is_emulator BOOLEAN NOT NULL DEFAULT FALSE,
    is_rooted_or_jailbroken BOOLEAN NOT NULL DEFAULT FALSE,
    device_risk_score NUMERIC(5, 2) NOT NULL DEFAULT 0 CHECK (device_risk_score BETWEEN 0 AND 100),
    account_login_count INTEGER NOT NULL DEFAULT 0 CHECK (account_login_count >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 2. QUOC MVP - TRANSACTION / ACCOUNT FRAUD DOMAIN
-- Owns: login, beneficiary, account-change, auth, transaction flow.
-- Main demo flow:
-- new device -> sensitive change -> new beneficiary -> transfer -> alert
-- ============================================================

CREATE TABLE IF NOT EXISTS fraud_sim.login_sessions (
    session_id TEXT PRIMARY KEY,
    simulation_run_id TEXT NOT NULL REFERENCES fraud_sim.simulation_runs(simulation_run_id),
    account_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    device_id TEXT NOT NULL REFERENCES fraud_sim.devices(device_id),
    login_at TIMESTAMPTZ NOT NULL,
    ip_address TEXT NOT NULL,
    province TEXT NOT NULL,
    country TEXT NOT NULL DEFAULT 'VN',
    -- [P1] Tọa độ địa lý để hỗ trợ impossible travel detection
    latitude NUMERIC(9, 6) CHECK (latitude IS NULL OR latitude BETWEEN -90 AND 90),
    longitude NUMERIC(9, 6) CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180),
    geo_source TEXT CHECK (geo_source IS NULL OR geo_source IN ('ip', 'gps', 'cell', 'manual', 'unknown')),
    vpn_flag BOOLEAN NOT NULL DEFAULT FALSE,
    proxy_flag BOOLEAN NOT NULL DEFAULT FALSE,
    login_result TEXT NOT NULL CHECK (login_result IN ('success', 'failed', 'locked')),
    failure_reason TEXT,
    auth_method TEXT NOT NULL,
    is_new_device BOOLEAN NOT NULL,
    is_new_location BOOLEAN NOT NULL,
    session_risk_score NUMERIC(5, 2) NOT NULL DEFAULT 0 CHECK (session_risk_score BETWEEN 0 AND 100),
    session_end_at TIMESTAMPTZ,
    FOREIGN KEY (account_id, customer_id) REFERENCES fraud_sim.accounts(account_id, customer_id),
    CHECK (session_end_at IS NULL OR session_end_at >= login_at)
);

CREATE TABLE IF NOT EXISTS fraud_sim.beneficiaries (
    beneficiary_id TEXT PRIMARY KEY,
    simulation_run_id TEXT NOT NULL REFERENCES fraud_sim.simulation_runs(simulation_run_id),
    account_id TEXT NOT NULL REFERENCES fraud_sim.accounts(account_id),
    beneficiary_account_hash TEXT NOT NULL,
    beneficiary_bank TEXT NOT NULL,
    beneficiary_name TEXT NOT NULL,
    added_at TIMESTAMPTZ NOT NULL,
    added_channel TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'removed', 'blocked')),
    is_internal_bank BOOLEAN NOT NULL,
    beneficiary_risk_level TEXT NOT NULL CHECK (beneficiary_risk_level IN ('Low', 'Medium', 'High')),
    mule_cluster_id TEXT,
    UNIQUE (account_id, beneficiary_account_hash, beneficiary_bank)
);

CREATE TABLE IF NOT EXISTS fraud_sim.account_change_events (
    change_event_id TEXT PRIMARY KEY,
    simulation_run_id TEXT NOT NULL REFERENCES fraud_sim.simulation_runs(simulation_run_id),
    account_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    changed_at TIMESTAMPTZ NOT NULL,
    change_type TEXT NOT NULL CHECK (change_type IN ('phone', 'email', 'password', 'trusted_device', 'transfer_limit', 'address')),
    channel TEXT NOT NULL,
    device_id TEXT REFERENCES fraud_sim.devices(device_id),
    verification_method TEXT NOT NULL,
    change_result TEXT NOT NULL CHECK (change_result IN ('success', 'failed', 'reversed')),
    old_value_hash TEXT,
    new_value_hash TEXT,
    is_sensitive_change BOOLEAN NOT NULL DEFAULT TRUE,
    FOREIGN KEY (account_id, customer_id) REFERENCES fraud_sim.accounts(account_id, customer_id)
);

CREATE TABLE IF NOT EXISTS fraud_sim.transactions (
    transaction_id TEXT PRIMARY KEY,
    simulation_run_id TEXT NOT NULL REFERENCES fraud_sim.simulation_runs(simulation_run_id),
    account_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    session_id TEXT REFERENCES fraud_sim.login_sessions(session_id),
    device_id TEXT REFERENCES fraud_sim.devices(device_id),
    -- [P0] Tham chiếu beneficiary_id đơn (giữ tương thích ngược)
    beneficiary_id TEXT,
    transaction_at TIMESTAMPTZ NOT NULL,
    amount NUMERIC(18, 2) NOT NULL CHECK (amount > 0),
    currency TEXT NOT NULL DEFAULT 'VND',
    direction TEXT NOT NULL CHECK (direction IN ('DEBIT', 'CREDIT')),
    transaction_type TEXT NOT NULL CHECK (transaction_type IN ('transfer', 'bill_payment', 'cash_withdrawal', 'card_payment', 'loan_disbursement', 'loan_repayment')),
    channel TEXT NOT NULL CHECK (channel IN ('mobile', 'web', 'atm', 'branch', 'pos', 'api', 'internal')),
    counterparty_account_hash TEXT,
    counterparty_bank TEXT,
    -- [P1] Tham chiếu nội bộ nếu đối tác cùng ngân hàng (phát hiện U-turn, layering)
    counterparty_internal_account_id TEXT REFERENCES fraud_sim.accounts(account_id),
    merchant_id TEXT,
    merchant_category_code TEXT,
    ip_address TEXT,
    province TEXT,
    country TEXT NOT NULL DEFAULT 'VN',
    vpn_flag BOOLEAN NOT NULL DEFAULT FALSE,
    proxy_flag BOOLEAN NOT NULL DEFAULT FALSE,
    status TEXT NOT NULL CHECK (status IN ('success', 'failed', 'blocked', 'reversed')),
    failure_reason TEXT,
    balance_before NUMERIC(18, 2),
    balance_after NUMERIC(18, 2),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id, customer_id) REFERENCES fraud_sim.accounts(account_id, customer_id),
    -- [P0] Đảm bảo beneficiary thuộc đúng tài khoản chuyển
    FOREIGN KEY (beneficiary_id, account_id) REFERENCES fraud_sim.beneficiaries(beneficiary_id, account_id)
);

CREATE TABLE IF NOT EXISTS fraud_sim.transaction_features (
    transaction_id TEXT PRIMARY KEY REFERENCES fraud_sim.transactions(transaction_id),
    feature_version TEXT NOT NULL,
    computed_at TIMESTAMPTZ NOT NULL,
    is_new_device BOOLEAN NOT NULL,
    is_new_beneficiary BOOLEAN NOT NULL,
    is_after_sensitive_change BOOLEAN NOT NULL,
    txn_count_10m INTEGER NOT NULL DEFAULT 0 CHECK (txn_count_10m >= 0),
    txn_count_1h INTEGER NOT NULL DEFAULT 0 CHECK (txn_count_1h >= 0),
    txn_amount_sum_24h NUMERIC(18, 2) NOT NULL DEFAULT 0 CHECK (txn_amount_sum_24h >= 0),
    amount_to_median_ratio NUMERIC(12, 4),
    failed_auth_count_30m INTEGER NOT NULL DEFAULT 0 CHECK (failed_auth_count_30m >= 0),
    time_since_beneficiary_added_minutes INTEGER,
    time_since_sensitive_change_minutes INTEGER,
    features JSONB
);

CREATE TABLE IF NOT EXISTS fraud_sim.auth_events (
    auth_event_id TEXT PRIMARY KEY,
    simulation_run_id TEXT NOT NULL REFERENCES fraud_sim.simulation_runs(simulation_run_id),
    transaction_id TEXT REFERENCES fraud_sim.transactions(transaction_id),
    session_id TEXT REFERENCES fraud_sim.login_sessions(session_id),
    change_event_id TEXT REFERENCES fraud_sim.account_change_events(change_event_id),
    account_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    auth_at TIMESTAMPTZ NOT NULL,
    auth_method TEXT NOT NULL CHECK (auth_method IN ('password', 'sms_otp', 'soft_otp', 'biometric', 'passkey', 'token')),
    auth_result TEXT NOT NULL CHECK (auth_result IN ('success', 'failed', 'timeout', 'abandoned')),
    failed_attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (failed_attempt_count >= 0),
    auth_risk_score NUMERIC(5, 2) NOT NULL DEFAULT 0 CHECK (auth_risk_score BETWEEN 0 AND 100),
    FOREIGN KEY (account_id, customer_id) REFERENCES fraud_sim.accounts(account_id, customer_id),
    -- [P1] Mỗi auth_event phải gắn đúng 1 ngữ cảnh (login | transaction | account_change)
    CHECK (
        (transaction_id IS NOT NULL)::integer +
        (session_id IS NOT NULL)::integer +
        (change_event_id IS NOT NULL)::integer = 1
    )
);

-- ============================================================
-- 3. PHUONG MVP - LOAN APPLICATION FRAUD DOMAIN
-- Owns: sales channel, application, declared profile, income, documents,
-- CIC snapshot, and disbursement account.
-- Main demo flow:
-- suspicious applicant -> fake document/income/CIC -> loan decision -> alert
-- ============================================================

CREATE TABLE IF NOT EXISTS fraud_sim.sales_points (
    sales_point_id TEXT PRIMARY KEY,
    simulation_run_id TEXT NOT NULL REFERENCES fraud_sim.simulation_runs(simulation_run_id),
    sales_point_name TEXT NOT NULL,
    sales_point_address TEXT NOT NULL,
    province TEXT NOT NULL,
    region TEXT NOT NULL,
    opened_at DATE NOT NULL,
    monthly_application_baseline NUMERIC(10, 2) NOT NULL CHECK (monthly_application_baseline >= 0),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'closed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fraud_sim.sales_agents (
    sales_agent_id TEXT PRIMARY KEY,
    simulation_run_id TEXT NOT NULL REFERENCES fraud_sim.simulation_runs(simulation_run_id),
    sales_point_id TEXT NOT NULL REFERENCES fraud_sim.sales_points(sales_point_id),
    sales_agent_name TEXT NOT NULL,
    join_date DATE NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('sales', 'team_lead', 'partner_staff', 'underwriter')),
    monthly_application_baseline NUMERIC(10, 2) NOT NULL CHECK (monthly_application_baseline >= 0),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'resigned', 'suspended')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- [P0] Hỗ trợ composite FK từ loan_applications: đảm bảo agent thuộc đúng sales_point
    UNIQUE (sales_agent_id, sales_point_id)
);

CREATE TABLE IF NOT EXISTS fraud_sim.loan_applications (
    application_id TEXT PRIMARY KEY,
    simulation_run_id TEXT NOT NULL REFERENCES fraud_sim.simulation_runs(simulation_run_id),
    customer_id TEXT NOT NULL REFERENCES fraud_sim.customers(customer_id),
    application_at TIMESTAMPTZ NOT NULL,
    loan_amount NUMERIC(18, 2) NOT NULL CHECK (loan_amount > 0),
    loan_term_months INTEGER NOT NULL CHECK (loan_term_months > 0),
    loan_product TEXT NOT NULL,
    loan_purpose TEXT NOT NULL,
    application_channel TEXT NOT NULL CHECK (application_channel IN ('branch', 'pos', 'online', 'partner', 'call_center')),
    sales_point_id TEXT NOT NULL REFERENCES fraud_sim.sales_points(sales_point_id),
    sales_agent_id TEXT NOT NULL,
    application_status TEXT NOT NULL CHECK (application_status IN ('submitted', 'in_review', 'approved', 'rejected', 'disbursed', 'cancelled')),
    credit_underwriting_result TEXT CHECK (credit_underwriting_result IN ('pass', 'fail', 'manual_review')),
    decision_at TIMESTAMPTZ,
    device_id TEXT REFERENCES fraud_sim.devices(device_id),
    ip_address INET,
    is_vpn BOOLEAN NOT NULL DEFAULT FALSE,
    is_proxy BOOLEAN NOT NULL DEFAULT FALSE,
    is_emulator BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- [P0] Đảm bảo sales_agent_id thuộc đúng sales_point_id
    FOREIGN KEY (sales_agent_id, sales_point_id) REFERENCES fraud_sim.sales_agents(sales_agent_id, sales_point_id),
    -- [P1] Hỗ trợ composite FK từ applicant_declared_profiles
    UNIQUE (application_id, customer_id)
);

CREATE TABLE IF NOT EXISTS fraud_sim.applicant_declared_profiles (
    declared_profile_id TEXT PRIMARY KEY,
    simulation_run_id TEXT NOT NULL REFERENCES fraud_sim.simulation_runs(simulation_run_id),
    application_id TEXT NOT NULL UNIQUE,
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
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- [P0] Đảm bảo application_id + customer_id nhất quán với loan_applications
    FOREIGN KEY (application_id, customer_id) REFERENCES fraud_sim.loan_applications(application_id, customer_id)
);

CREATE TABLE IF NOT EXISTS fraud_sim.employment_income_profiles (
    employment_id TEXT PRIMARY KEY,
    simulation_run_id TEXT NOT NULL REFERENCES fraud_sim.simulation_runs(simulation_run_id),
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

CREATE TABLE IF NOT EXISTS fraud_sim.reference_contacts (
    reference_id TEXT PRIMARY KEY,
    simulation_run_id TEXT NOT NULL REFERENCES fraud_sim.simulation_runs(simulation_run_id),
    application_id TEXT NOT NULL REFERENCES fraud_sim.loan_applications(application_id),
    reference_name TEXT NOT NULL,
    -- [P1] Chuẩn hoá quan hệ để tránh giá trị tự do
    relationship TEXT NOT NULL CHECK (relationship IN ('spouse', 'parent', 'sibling', 'relative', 'friend', 'colleague', 'manager', 'other')),
    reference_phone_hash TEXT NOT NULL,
    phone_reuse_count INTEGER NOT NULL DEFAULT 1 CHECK (phone_reuse_count >= 1),
    reference_quality_score NUMERIC(5, 2) CHECK (reference_quality_score IS NULL OR reference_quality_score BETWEEN 0 AND 100),
    -- [P1] Thứ tự người tham chiếu (1 hoặc 2) để giới hạn tối đa 2 người/hồ sơ
    reference_order SMALLINT CHECK (reference_order IN (1, 2)),
    -- [P1] Trạng thái xác minh người tham chiếu
    verification_status TEXT CHECK (verification_status IS NULL OR verification_status IN ('not_checked', 'verified', 'unreachable', 'mismatch', 'suspicious')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- [P1] Mỗi hồ sơ chỉ có 1 người tham chiếu thứ nhất và 1 người thứ hai
    UNIQUE (application_id, reference_order),
    -- [P1] Không cho nhập trùng SĐT trên cùng hồ sơ
    UNIQUE (application_id, reference_phone_hash)
);

CREATE TABLE IF NOT EXISTS fraud_sim.application_documents (
    document_id TEXT PRIMARY KEY,
    simulation_run_id TEXT NOT NULL REFERENCES fraud_sim.simulation_runs(simulation_run_id),
    application_id TEXT NOT NULL REFERENCES fraud_sim.loan_applications(application_id),
    document_type TEXT NOT NULL CHECK (document_type IN ('id_card_front', 'id_card_back', 'payslip', 'bank_statement', 'labor_contract', 'utility_bill', 'selfie', 'other')),
    document_hash TEXT NOT NULL,
    submitted_at TIMESTAMPTZ NOT NULL,
    ocr_quality_score NUMERIC(5, 2) CHECK (ocr_quality_score IS NULL OR ocr_quality_score BETWEEN 0 AND 100),
    tamper_score NUMERIC(5, 2) CHECK (tamper_score IS NULL OR tamper_score BETWEEN 0 AND 100),
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
    simulation_run_id TEXT NOT NULL REFERENCES fraud_sim.simulation_runs(simulation_run_id),
    application_id TEXT NOT NULL REFERENCES fraud_sim.loan_applications(application_id),
    bureau_score INTEGER CHECK (bureau_score IS NULL OR bureau_score BETWEEN 0 AND 1000),
    active_loan_count INTEGER NOT NULL DEFAULT 0 CHECK (active_loan_count >= 0),
    dpd_max_12m INTEGER NOT NULL DEFAULT 0 CHECK (dpd_max_12m >= 0),
    recent_inquiry_count INTEGER NOT NULL DEFAULT 0 CHECK (recent_inquiry_count >= 0),
    thin_file_flag BOOLEAN NOT NULL DEFAULT FALSE,
    bureau_match_result TEXT NOT NULL CHECK (bureau_match_result IN ('full_match', 'partial_match', 'no_hit')),
    snapshot_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (application_id, snapshot_at)
);

CREATE TABLE IF NOT EXISTS fraud_sim.disbursement_accounts (
    disbursement_id TEXT PRIMARY KEY,
    simulation_run_id TEXT NOT NULL REFERENCES fraud_sim.simulation_runs(simulation_run_id),
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

CREATE TABLE IF NOT EXISTS fraud_sim.loan_repayment_outcomes (
    -- [P1] Đổi tên PK thành loan_outcome_id cho rõ nghĩa
    loan_outcome_id TEXT PRIMARY KEY,
    simulation_run_id TEXT NOT NULL REFERENCES fraud_sim.simulation_runs(simulation_run_id),
    application_id TEXT NOT NULL UNIQUE REFERENCES fraud_sim.loan_applications(application_id),
    disbursed_at TIMESTAMPTZ NOT NULL,
    first_due_date DATE NOT NULL,
    -- [P1] Phân biệt paid_on_time vs paid_late thay vì chỉ 'paid'
    first_payment_status TEXT NOT NULL CHECK (first_payment_status IN ('paid_on_time', 'paid_late', 'partial', 'missed', 'not_due')),
    -- [P1] Số ngày quá hạn thanh toán đầu tiên
    first_payment_days_past_due INTEGER CHECK (first_payment_days_past_due IS NULL OR first_payment_days_past_due >= 0),
    -- [P1] Thay boolean contactable bằng enum chi tiết hơn
    contact_status_after_disbursement TEXT CHECK (contact_status_after_disbursement IS NULL OR contact_status_after_disbursement IN ('not_checked', 'contactable', 'temporarily_unreachable', 'lost_contact', 'refused', 'invalid_contact')),
    dpd_30_flag BOOLEAN NOT NULL DEFAULT FALSE,
    dpd_60_flag BOOLEAN NOT NULL DEFAULT FALSE,
    dpd_90_flag BOOLEAN NOT NULL DEFAULT FALSE,
    -- [P1] Số kỳ đến hạn và số kỳ đã trả đúng hạn
    installments_due INTEGER CHECK (installments_due IS NULL OR installments_due >= 0),
    installments_paid_on_time INTEGER CHECK (installments_paid_on_time IS NULL OR installments_paid_on_time >= 0),
    total_amount_due NUMERIC(18, 2) CHECK (total_amount_due IS NULL OR total_amount_due >= 0),
    total_amount_paid NUMERIC(18, 2) CHECK (total_amount_paid IS NULL OR total_amount_paid >= 0),
    outstanding_balance NUMERIC(18, 2) CHECK (outstanding_balance IS NULL OR outstanding_balance >= 0),
    early_default_flag BOOLEAN NOT NULL DEFAULT FALSE,
    writeoff_amount NUMERIC(18, 2) NOT NULL DEFAULT 0 CHECK (writeoff_amount >= 0),
    -- [P1] Trạng thái hiệu suất khoản vay
    loan_performance_status TEXT CHECK (loan_performance_status IS NULL OR loan_performance_status IN ('performing', 'early_delinquency', 'delinquent', 'default', 'paid_off', 'not_matured')),
    -- [P1] Nhãn phân biệt gian lận vs nợ xấu tín dụng (dùng cho training ML)
    credit_performance_label TEXT CHECK (credit_performance_label IS NULL OR credit_performance_label IN ('good', 'delinquent', 'default', 'not_matured')),
    fraud_outcome_label TEXT CHECK (fraud_outcome_label IS NULL OR fraud_outcome_label IN ('legitimate', 'suspected_fraud', 'confirmed_fraud', 'unknown')),
    outcome_observed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- [P1] Logic nhất quán DPD: nếu dpd_90 thì dpd_60 và dpd_30 phải true
    CHECK (
        (NOT dpd_60_flag OR dpd_30_flag)
        AND (NOT dpd_90_flag OR dpd_60_flag)
    ),
    -- [P1] installments_paid_on_time không thể vượt installments_due
    CHECK (installments_paid_on_time IS NULL OR installments_due IS NULL OR installments_paid_on_time <= installments_due)
);

-- ============================================================
-- 4. COMMON MVP FRAUD OPERATION - USED BY BOTH PHUONG AND QUOC
-- Owns: simplified rules, rule_hits, SAS-like decision output, alerts, cases,
-- and ground truth labels for evaluation.
-- ============================================================

CREATE TABLE IF NOT EXISTS fraud_sim.rules (
    rule_id TEXT PRIMARY KEY,
    rule_code TEXT NOT NULL UNIQUE,
    rule_name TEXT NOT NULL,
    owner_domain TEXT NOT NULL CHECK (owner_domain IN ('shared', 'transaction', 'loan')),
    scenario_code TEXT NOT NULL,
    rule_type TEXT NOT NULL CHECK (rule_type IN ('velocity', 'anomaly', 'identity', 'device', 'document', 'network', 'manual')),
    description TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('Low', 'Medium', 'High', 'Critical')),
    base_score NUMERIC(5, 2) NOT NULL CHECK (base_score BETWEEN 0 AND 100),
    decision_flag TEXT NOT NULL CHECK (decision_flag IN ('ACCEPT', 'DECLINE', 'HOLD', 'CHALLENGE', 'ALERT_ONLY', 'MANUAL_REVIEW')),
    status TEXT NOT NULL CHECK (status IN ('draft', 'active', 'inactive', 'retired')),
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- [P0] Bảng rule_hits: theo dõi chi tiết kết quả đánh giá từng rule trên từng entity
-- Cần thiết để giải thích tại sao một quyết định được đưa ra (audit trail cho SAS)
CREATE TABLE IF NOT EXISTS fraud_sim.rule_hits (
    rule_hit_id TEXT PRIMARY KEY,
    simulation_run_id TEXT NOT NULL REFERENCES fraud_sim.simulation_runs(simulation_run_id),
    decision_outcome_id TEXT NOT NULL REFERENCES fraud_sim.decision_outcomes(decision_outcome_id),
    rule_id TEXT NOT NULL REFERENCES fraud_sim.rules(rule_id),
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    hit_flag BOOLEAN NOT NULL,
    score_contribution NUMERIC(5, 2) NOT NULL DEFAULT 0,
    evaluated_values JSONB,
    reason_code TEXT,
    execution_order INTEGER CHECK (execution_order IS NULL OR execution_order >= 1)
);

CREATE TABLE IF NOT EXISTS fraud_sim.decision_outcomes (
    decision_outcome_id TEXT PRIMARY KEY,
    simulation_run_id TEXT NOT NULL REFERENCES fraud_sim.simulation_runs(simulation_run_id),
    message_type TEXT NOT NULL CHECK (message_type IN ('transaction', 'loan_application')),
    entity_type TEXT NOT NULL CHECK (entity_type IN ('transaction', 'loan_application')),
    entity_id TEXT NOT NULL,
    transaction_id TEXT REFERENCES fraud_sim.transactions(transaction_id),
    application_id TEXT REFERENCES fraud_sim.loan_applications(application_id),
    decision_at TIMESTAMPTZ NOT NULL,
    decision_flag TEXT NOT NULL CHECK (decision_flag IN ('ACCEPT', 'DECLINE', 'HOLD', 'CHALLENGE', 'ALERT_ONLY', 'MANUAL_REVIEW')),
    risk_score_100 NUMERIC(5, 2) CHECK (risk_score_100 IS NULL OR risk_score_100 BETWEEN 0 AND 100),
    reason_codes TEXT[] NOT NULL DEFAULT '{}',
    alert_recommended BOOLEAN NOT NULL DEFAULT FALSE,
    alert_type TEXT,
    triage_queue TEXT,
    processing_latency_ms INTEGER CHECK (processing_latency_ms IS NULL OR processing_latency_ms >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (
        (message_type = 'transaction' AND transaction_id IS NOT NULL AND application_id IS NULL) OR
        (message_type = 'loan_application' AND application_id IS NOT NULL AND transaction_id IS NULL)
    )
);

CREATE TABLE IF NOT EXISTS fraud_sim.alerts (
    alert_id TEXT PRIMARY KEY,
    simulation_run_id TEXT NOT NULL REFERENCES fraud_sim.simulation_runs(simulation_run_id),
    scenario_code TEXT NOT NULL,
    primary_rule_id TEXT REFERENCES fraud_sim.rules(rule_id),
    decision_outcome_id TEXT REFERENCES fraud_sim.decision_outcomes(decision_outcome_id),
    entity_type TEXT NOT NULL CHECK (entity_type IN (
        'customer',
        'account',
        'transaction',
        'session',
        'device',
        'beneficiary',
        'change_event',
        'loan_application',
        'sales_agent',
        'sales_point',
        'application_document',
        'disbursement_account'
    )),
    entity_id TEXT NOT NULL,
    customer_id TEXT REFERENCES fraud_sim.customers(customer_id),
    account_id TEXT REFERENCES fraud_sim.accounts(account_id),
    transaction_id TEXT REFERENCES fraud_sim.transactions(transaction_id),
    application_id TEXT REFERENCES fraud_sim.loan_applications(application_id),
    triggered_at TIMESTAMPTZ NOT NULL,
    final_risk_score_100 NUMERIC(5, 2) NOT NULL CHECK (final_risk_score_100 BETWEEN 0 AND 100),
    severity TEXT NOT NULL CHECK (severity IN ('Low', 'Medium', 'High', 'Critical')),
    alert_status TEXT NOT NULL CHECK (alert_status IN ('new', 'open', 'assigned', 'suppressed', 'closed')),
    alert_reason TEXT,
    score_explanation JSONB,
    assigned_to TEXT,
    closed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fraud_sim.cases (
    case_id TEXT PRIMARY KEY,
    simulation_run_id TEXT NOT NULL REFERENCES fraud_sim.simulation_runs(simulation_run_id),
    case_type TEXT NOT NULL CHECK (case_type IN ('transaction_fraud', 'loan_fraud', 'mixed')),
    primary_customer_id TEXT REFERENCES fraud_sim.customers(customer_id),
    primary_account_id TEXT REFERENCES fraud_sim.accounts(account_id),
    primary_application_id TEXT REFERENCES fraud_sim.loan_applications(application_id),
    primary_alert_id TEXT REFERENCES fraud_sim.alerts(alert_id),
    created_at TIMESTAMPTZ NOT NULL,
    assigned_team TEXT NOT NULL,
    case_priority TEXT NOT NULL CHECK (case_priority IN ('Low', 'Medium', 'High', 'Critical')),
    case_status TEXT NOT NULL CHECK (case_status IN ('new', 'investigating', 'confirmed_fraud', 'false_positive', 'closed')),
    resolution_at TIMESTAMPTZ,
    resolution_reason TEXT,
    analyst_id TEXT,
    loss_amount NUMERIC(18, 2) NOT NULL DEFAULT 0 CHECK (loss_amount >= 0),
    prevented_loss_amount NUMERIC(18, 2) NOT NULL DEFAULT 0 CHECK (prevented_loss_amount >= 0)
);

CREATE TABLE IF NOT EXISTS fraud_sim.verification_results (
    verification_id TEXT PRIMARY KEY,
    simulation_run_id TEXT NOT NULL REFERENCES fraud_sim.simulation_runs(simulation_run_id),
    owner_domain TEXT NOT NULL CHECK (owner_domain IN ('transaction', 'loan')),
    transaction_id TEXT REFERENCES fraud_sim.transactions(transaction_id),
    application_id TEXT REFERENCES fraud_sim.loan_applications(application_id),
    alert_id TEXT REFERENCES fraud_sim.alerts(alert_id),
    case_id TEXT REFERENCES fraud_sim.cases(case_id),
    verified_at TIMESTAMPTZ NOT NULL,
    verification_label TEXT NOT NULL CHECK (verification_label IN ('CONFIRMED_FRAUD', 'GENUINE', 'FALSE_POSITIVE', 'INCONCLUSIVE', 'CUSTOMER_UNREACHABLE', 'TEST_EVENT')),
    review_outcome TEXT NOT NULL,
    loss_amount NUMERIC(18, 2) NOT NULL DEFAULT 0 CHECK (loss_amount >= 0),
    prevented_loss_amount NUMERIC(18, 2) NOT NULL DEFAULT 0 CHECK (prevented_loss_amount >= 0),
    CHECK (
        (owner_domain = 'transaction' AND transaction_id IS NOT NULL AND application_id IS NULL) OR
        (owner_domain = 'loan' AND application_id IS NOT NULL AND transaction_id IS NULL)
    )
);

CREATE TABLE IF NOT EXISTS fraud_sim.fraud_ground_truth (
    fraud_event_id TEXT PRIMARY KEY,
    simulation_run_id TEXT NOT NULL REFERENCES fraud_sim.simulation_runs(simulation_run_id),
    owner_domain TEXT NOT NULL CHECK (owner_domain IN ('transaction', 'loan', 'mixed')),
    scenario_code TEXT NOT NULL,
    primary_customer_id TEXT REFERENCES fraud_sim.customers(customer_id),
    primary_account_id TEXT REFERENCES fraud_sim.accounts(account_id),
    primary_transaction_id TEXT REFERENCES fraud_sim.transactions(transaction_id),
    primary_application_id TEXT REFERENCES fraud_sim.loan_applications(application_id),
    start_at TIMESTAMPTZ NOT NULL,
    end_at TIMESTAMPTZ NOT NULL,
    fraud_label TEXT NOT NULL CHECK (fraud_label IN ('attempted_fraud', 'suspected_fraud', 'confirmed_fraud', 'false_positive_seed')),
    fraud_outcome TEXT NOT NULL,
    injection_method TEXT NOT NULL,
    expected_rule_codes TEXT[] NOT NULL DEFAULT '{}',
    expected_decision_flag TEXT CHECK (expected_decision_flag IS NULL OR expected_decision_flag IN ('ACCEPT', 'DECLINE', 'HOLD', 'CHALLENGE', 'ALERT_ONLY', 'MANUAL_REVIEW')),
    loss_amount NUMERIC(18, 2) NOT NULL DEFAULT 0 CHECK (loss_amount >= 0),
    CHECK (end_at >= start_at)
);

-- ============================================================
-- 5. MVP INDEXES - SIMPLE QUERY SUPPORT FOR DEMO AND GENERATOR
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_customers_run ON fraud_sim.customers(simulation_run_id);
CREATE INDEX IF NOT EXISTS idx_customers_id_hash ON fraud_sim.customers(id_number_hash);
CREATE INDEX IF NOT EXISTS idx_customers_phone_hash ON fraud_sim.customers(phone_hash);
CREATE INDEX IF NOT EXISTS idx_accounts_run_customer ON fraud_sim.accounts(simulation_run_id, customer_id);
CREATE INDEX IF NOT EXISTS idx_devices_run_fingerprint ON fraud_sim.devices(simulation_run_id, device_fingerprint);

CREATE INDEX IF NOT EXISTS idx_login_account_time ON fraud_sim.login_sessions(account_id, login_at);
CREATE INDEX IF NOT EXISTS idx_transactions_account_time ON fraud_sim.transactions(account_id, transaction_at);
CREATE INDEX IF NOT EXISTS idx_transactions_customer_time ON fraud_sim.transactions(customer_id, transaction_at);
CREATE INDEX IF NOT EXISTS idx_transactions_beneficiary_time ON fraud_sim.transactions(beneficiary_id, transaction_at) WHERE beneficiary_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_auth_account_time ON fraud_sim.auth_events(account_id, auth_at);
CREATE INDEX IF NOT EXISTS idx_change_account_time ON fraud_sim.account_change_events(account_id, changed_at);

CREATE INDEX IF NOT EXISTS idx_loan_app_customer_time ON fraud_sim.loan_applications(customer_id, application_at);
CREATE INDEX IF NOT EXISTS idx_loan_app_sales_agent_time ON fraud_sim.loan_applications(sales_agent_id, application_at);
CREATE INDEX IF NOT EXISTS idx_declared_id_hash ON fraud_sim.applicant_declared_profiles(declared_id_number_hash);
CREATE INDEX IF NOT EXISTS idx_declared_phone_hash ON fraud_sim.applicant_declared_profiles(declared_phone_hash);
CREATE INDEX IF NOT EXISTS idx_reference_phone_hash ON fraud_sim.reference_contacts(reference_phone_hash);
CREATE INDEX IF NOT EXISTS idx_reference_employer_phone_hash ON fraud_sim.employment_income_profiles(employer_phone_hash) WHERE employer_phone_hash IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_documents_hash ON fraud_sim.application_documents(document_hash);
CREATE INDEX IF NOT EXISTS idx_cic_application_time ON fraud_sim.credit_bureau_snapshots(application_id, snapshot_at);
CREATE INDEX IF NOT EXISTS idx_disbursement_account_hash ON fraud_sim.disbursement_accounts(receiving_account_hash);
CREATE INDEX IF NOT EXISTS idx_repayment_application ON fraud_sim.loan_repayment_outcomes(application_id);

CREATE INDEX IF NOT EXISTS idx_decision_entity_time ON fraud_sim.decision_outcomes(entity_type, entity_id, decision_at);
-- [P0] Index hỗ trợ tra cứu rule_hits theo decision_outcome và trạng thái kích hoạt
CREATE INDEX IF NOT EXISTS idx_rule_hits_outcome ON fraud_sim.rule_hits(decision_outcome_id, hit_flag);
CREATE INDEX IF NOT EXISTS idx_rule_hits_rule ON fraud_sim.rule_hits(rule_id, hit_flag);
CREATE INDEX IF NOT EXISTS idx_alerts_status_priority ON fraud_sim.alerts(alert_status, severity, triggered_at);
CREATE INDEX IF NOT EXISTS idx_alerts_entity_time ON fraud_sim.alerts(entity_type, entity_id, triggered_at);
CREATE INDEX IF NOT EXISTS idx_cases_status_team ON fraud_sim.cases(case_status, assigned_team, created_at);
CREATE INDEX IF NOT EXISTS idx_verification_domain_time ON fraud_sim.verification_results(owner_domain, verified_at);
CREATE INDEX IF NOT EXISTS idx_ground_truth_scenario ON fraud_sim.fraud_ground_truth(owner_domain, scenario_code, start_at);
