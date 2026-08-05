# Schema Phuong V2 Change Summary

## Muc tieu sua

Ban v2 sua schema Phuong theo feedback SAS Fraud: tach raw database layer khoi message/profile/decision/UAT layer, dong thoi khac phuc data leakage va channel risk.

## Da sua trong schema

- Data leakage: xoa `normal_bad_rate`, `normal_approval_rate`, `agent_risk_level`, `sales_point_risk_level` khoi bang tinh `sales_agents` va `sales_points`.
- Leakage-safe baseline: them `sales_agent_performance_snapshots` va `sales_point_performance_snapshots`, bat buoc dung theo nguyen tac `as_of_at < application_at`.
- Channel risk: them `application_digital_contexts` de luu `device_id`, `ip_address`, `user_agent`, geo, VPN/proxy/emulator cho online channel.
- Fake employer/company: them `employer_phone_hash`, `employer_phone_cluster_id`, `employer_phone_verification_status`, `is_employer_phone_reused`.
- Timestamp granularity: chuan hoa `application_at` va digital timestamp thanh `TIMESTAMPTZ(3)`.
- SAS decision output: them `loan_decision_outcomes` de luu `decision_flag`, `risk_score`, `reason_codes`, `alert_recommended`.
- UAT/back-test: thay `expected_detection_rules` text tu do bang `expected_decision_flag`, `expected_alert_type`, `expected_queue` va bang `loan_expected_rule_hits`.
- Rule catalog: them `loan_rule_catalog` de co `rule_code` va `reason_code` on dinh.
- SAS message contract: them `loan_message_inventory` va `loan_message_variable_mappings`.
- SAS profile catalog: them `loan_profile_variable_catalog` de mo ta profile set/key/window/calculation logic.

## Khong phai dap bo schema cu

Schema SQL van la raw synthetic source. SAS khong doc nguyen tat ca bang; backend/notebook se lay du lieu tu PostgreSQL de tao message JSON theo contract, toi da 30 attributes/message.

## Thu tu chay khuyen nghi

1. Drop schema cu neu chua co data: `DROP SCHEMA IF EXISTS fraud_sim CASCADE;`
2. Chay schema Quoc truoc vi tao `customers`, `accounts`, `devices`, `simulation_runs`.
3. Chay `schema_phuong_12_tables.sql` ban v2.
4. Insert message inventory/profile catalog/rule catalog seed data.
5. Moi bat dau gen synthetic data.
