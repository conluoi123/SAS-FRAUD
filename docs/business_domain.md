# Business Domain Guide — Transaction Fraud Training Dataset

> Tài liệu này mô tả scope hiện tại của bộ dữ liệu phục vụ EDA, preprocessing và huấn luyện model Transaction Fraud.
>
> Snapshot hiện tại: generator `2.2.0-transaction-raw-multirun`, 5 simulation run, seed `20260828..20260832`, kiểm tra ngày 2026-08-29.

---

## 1. Scope hiện tại

### 1.1. Bài toán ML

| Thuộc tính | Định nghĩa |
|---|---|
| Domain | Transaction/Account Fraud |
| Bài toán | Binary classification: fraud hay legitimate |
| Grain | Một dòng là một transaction |
| Entity chính | `account_id`, liên kết với `customer_id` |
| Thời điểm scoring | `transaction_at = T` |
| Target | `target_fraud` thuộc `{0, 1}` |
| Hard-negative | `hard_negative=1`: legitimate nhưng có biểu hiện gần giống fraud |
| Label bridge | `scenario_event_entities.csv` |
| Phạm vi scenario | `TXN-01..TXN-10` cùng hard-negative tương ứng |

### 1.2. Loan domain đã ra khỏi scope training này

`enabled_domains=["transaction"]` và toàn bộ `LOAN-01..LOAN-10` có `scenario_counts=0`. Vì vậy các bảng Loan trong thư mục merged chỉ có header, không có dữ liệu:

- `loan_applications`
- `applicant_declared_profiles`
- `employment_income_profiles`
- `reference_contacts`
- `application_documents`
- `credit_bureau_snapshots`
- `disbursement_accounts`
- `loan_repayment_outcomes`
- `sales_agents`, `sales_points`

Không load, join hoặc kiểm tra missing các bảng này trong pipeline Transaction ML. Nếu Loan Fraud được khởi động lại sau này, cần một data contract và model riêng.

### 1.3. Raw dataset, chưa phải model-ready mart

Output hiện tại là các CSV chuẩn hóa riêng biệt:

```text
fraud_data_generator_v2/output_training_raw/merged/
```

Generator **không**:

- Join sẵn thành một bảng rộng.
- Chia train/validation/test.
- Fit imputer, encoder hoặc scaler.
- Chọn feature cuối cùng.

Các bước này thuộc notebook Data Science và phải thực hiện sau khi chốt grain, label và point-in-time rule.

---

## 2. Cách bộ dữ liệu được sinh

Entry point cho training dataset:

```powershell
python run_training_raw.py
```

Luồng thực tế:

```text
config_training_transaction.json
        │
        ├── run_001: RUN_TXN_TRAIN_001, seed 20260828
        ├── run_002: RUN_TXN_TRAIN_002, seed 20260829
        ├── run_003: RUN_TXN_TRAIN_003, seed 20260830
        ├── run_004: RUN_TXN_TRAIN_004, seed 20260831
        └── run_005: RUN_TXN_TRAIN_005, seed 20260832
                    │
                    ├── engine.py sinh population nền
                    ├── scenario_engine.py tiêm scenario + hard-negative
                    ├── recompute_balances.py nối balance chain
                    ├── rebuild_features.py tính transaction feature
                    ├── build_operations_v2.py tạo operations/ground truth
                    └── verify_data.py kiểm tra từng run
                              │
                              └── ghép dọc từng raw table vào merged/
```

Mỗi run có 1.500 customer và dùng seed độc lập. `run_training_raw.py` chỉ merge sau khi từng run vượt qua bước verify blocking; sau merge script tiếp tục kiểm tra primary key và liên kết transaction của label bridge.

### 2.1. Cấu hình scenario

Mỗi run yêu cầu 20 event cho từng `TXN-01..TXN-10`. Qua 5 run, mỗi fraud scenario có 100 event.

Hard-negative gồm hai nguồn:

- `HN-TXN-01..HN-TXN-10`: 15 event/scenario/run, tổng 75 event cho từng loại.
- `FP-TXN`: background risky-looking records được xác minh legitimate, tổng 150 transaction.

Scenario engine random hóa có kiểm soát thời điểm, số tiền và cường độ nhưng vẫn giữ điều kiện nghiệp vụ. Mục tiêu là giảm khả năng model học thuộc một template cố định.

---

## 3. Snapshot dữ liệu sau 5 simulator

### 3.1. Số dòng raw

| Nhóm | Bảng | Số dòng | Grain/vai trò |
|---|---|---:|---|
| Run | `simulation_runs` | 5 | Một simulation run |
| Shared | `customers` | 7.500 | Một customer |
| Shared | `accounts` | 9.425 | Một account |
| Shared | `devices` | 10.625 | Một device/fingerprint |
| Transaction | `login_sessions` | 26.861 | Một login session |
| Transaction | `beneficiaries` | 20.674 | Một beneficiary của account |
| Transaction | `account_change_events` | 2.588 | Một lần thay đổi account |
| Transaction | `transactions` | 112.565 | Một transaction |
| Transaction | `transaction_features` | 112.565 | Một bộ feature/transaction |
| Transaction | `auth_events` | 40.265 | Một authentication event |
| Label | `scenario_event_entities` | 4.097 | Bridge event–entity |
| Label | `scenario_manifest` | 1.900 | Một scripted event |
| Label | `fraud_ground_truth` | 1.900 | Ground truth cấp event |
| Operations | `rules` | 9 | Catalog transaction rule |
| Operations | `decision_outcomes` | 1.900 | Decision cấp event |
| Operations | `rule_hits` | 2.700 | Rule hit |
| Operations | `alerts` | 1.900 | Alert |
| Operations | `cases` | 1.900 | Investigation case |
| Operations | `verification_results` | 1.900 | Kết quả xác minh |

Các bảng operations và ground truth chỉ dùng để dựng/kiểm tra nhãn hoặc mô phỏng downstream workflow. Chúng không được dùng làm model input.

### 3.2. Population dùng cho transaction model

Toàn bộ 112.565 transaction raw đều có thể tham gia EDA sau khi áp dụng đúng label policy:

| Population | Số dòng | Tỷ lệ | Mapping |
|---|---:|---:|---|
| Background normal | 108.568 | 96,449% | Không có transaction bridge row |
| Confirmed fraud | 2.386 | 2,120% | `label_scope=fraud`, `target_fraud=1` |
| Hard-negative | 1.611 | 1,431% | `label_scope=hard_negative`, `target_fraud=0` |
| **Tổng** | **112.565** | **100%** | |

Fraud rate nhị phân là `2.386 / 112.565 = 2,1197%`.

**Đính chính về con số 43.116:** artifact merged và notebook `00_business_rule` hiện không lọc dataset xuống 43.116 dòng. Manifest xác nhận có 112.565 transaction và notebook xác nhận toàn bộ đều usable theo data contract hiện tại. Nếu một notebook sau tạo tập 43.116 dòng thì phải ghi rõ filter/sampling policy và coi đó là một derived dataset, không thay thế số lượng raw population.

### 3.3. Phân bố theo simulation run

| Run | Transaction | Fraud | Hard-negative | Fraud rate xấp xỉ |
|---|---:|---:|---:|---:|
| `RUN_TXN_TRAIN_001` | 22.066 | 472 | 313 | 2,1% |
| `RUN_TXN_TRAIN_002` | 22.797 | 479 | 327 | 2,1% |
| `RUN_TXN_TRAIN_003` | 22.710 | 472 | 322 | 2,1% |
| `RUN_TXN_TRAIN_004` | 22.431 | 487 | 314 | 2,2% |
| `RUN_TXN_TRAIN_005` | 22.561 | 476 | 335 | 2,1% |

Quy mô và fraud rate khá ổn định qua 5 seed. Tuy nhiên vẫn phải kiểm tra distribution drift của từng feature theo run, không chỉ so sánh target rate.

### 3.4. Fraud transaction theo scenario

| Scenario | Fraud transaction | Unique account | Unique event | Ghi chú về grain |
|---|---:|---:|---:|---|
| TXN-01 | 100 | 100 | 100 | Một transaction/event |
| TXN-02 | 100 | 100 | 100 | Một transaction/event |
| TXN-03 | 0 | — | 100 account event | `context_only`, không phải transaction positive |
| TXN-04 | 586 | 100 | 100 | Nhiều transaction trong velocity burst |
| TXN-05 | 100 | 100 | 100 | Một rapid transfer/event |
| TXN-06 | 100 | 100 | 100 | Transaction đích của ATO chain |
| TXN-07 | 900 | 300 | 100 | Nhiều account/transaction trong mule network |
| TXN-08 | 200 | 200 | 100 | Nhiều bot transaction/event |
| TXN-09 | 200 | 200 | 100 | Chuyển nội bộ và chuyển tiếp |
| TXN-10 | 100 | 100 | 100 | Transaction đích của SIM-swap chain |
| **Tổng transaction positive** | **2.386** | | | |

Ở transaction grain có 9 fraud scenario. TXN-03 vẫn tồn tại trong ground truth ở account/auth grain nhưng 100 bridge row của nó có `entity_type=account`, `label_scope=context_only` và tuyệt đối không được map thành transaction positive.

### 3.5. Hard-negative theo scenario

| Scenario | Hard-negative transaction |
|---|---:|
| FP-TXN | 150 |
| HN-TXN-01 | 75 |
| HN-TXN-02 | 75 |
| HN-TXN-03 | 75 |
| HN-TXN-04 | 444 |
| HN-TXN-05 | 75 |
| HN-TXN-06 | 75 |
| HN-TXN-07 | 417 |
| HN-TXN-08 | 75 |
| HN-TXN-09 | 75 |
| HN-TXN-10 | 75 |
| **Tổng** | **1.611** |

HN-TXN-04 và HN-TXN-07 có nhiều transaction/event, nên số dòng lớn hơn 75. Không để chúng hoặc các fraud multi-row scenario chi phối loss chỉ vì một event sinh nhiều transaction; dùng `sample_weight` từ bridge.

---

## 4. Business data model

```text
simulation_runs
      │
      └── customers 1──N accounts 1──N transactions 1──1 transaction_features
                    │          │
                    │          ├──N auth_events (transaction context)
                    │          ├──1 login_sessions N──1 devices
                    │          ├──0..1 beneficiaries
                    │          └──0..N scenario_event_entities (label bridge)
                    │
                    └──N account_change_events
```

### 4.1. Vai trò từng bảng

| Bảng | Ý nghĩa nghiệp vụ | Join từ transaction | Vai trò ML |
|---|---|---|---|
| `transactions` | Giao dịch tiền vào/ra tại T | Base grain | Current-event feature |
| `transaction_features` | Feature rolling đã tính | `transaction_id`, 1:1 | Velocity/time-since feature |
| `accounts` | Trạng thái, tuổi, loại, hạn mức, số dư nền | `account_id`, N:1 | Account behavior context |
| `customers` | Segment, KYC, risk nền, tỉnh | `customer_id`, N:1 | Customer context |
| `login_sessions` | Nơi, thời gian, thiết bị, VPN/proxy | `session_id`, N:1 | Session risk và location |
| `devices` | Trust, emulator/root, device risk | `device_id`, N:1 | Device risk |
| `beneficiaries` | Người nhận, bank, risk, mule cluster | `beneficiary_id`, N:0..1 | New-beneficiary/network risk |
| `auth_events` | Password/OTP/biometric và kết quả | Aggregate trước T | Failed-auth/security feature |
| `account_change_events` | Đổi phone/password/device/limit | Aggregate/latest trước T | ATO/SIM-swap sequence |
| `scenario_event_entities` | Event–entity label bridge | `entity_id=transaction_id` | Target/weight, không làm feature |
| `scenario_manifest` | Metadata scripted event | `event_id` | Audit scenario, không làm feature |

### 4.2. Join contract

Model-ready mart bắt đầu từ `transactions`:

```text
transactions
  LEFT JOIN transaction_features USING (transaction_id)       # 1:1
  LEFT JOIN accounts USING (account_id)                        # N:1
  LEFT JOIN customers USING (customer_id)                      # N:1
  LEFT JOIN login_sessions USING (session_id)                  # N:1
  LEFT JOIN devices USING (device_id)                          # N:1
  LEFT JOIN beneficiaries USING (beneficiary_id)               # N:0..1
  LEFT JOIN aggregated_auth_before_T                           # N:1 sau aggregate
  LEFT JOIN aggregated_account_changes_before_T                # N:1 sau aggregate
  LEFT JOIN transaction_label_bridge                           # 0..1 label row
```

Quy tắc bắt buộc:

- Assert số dòng vẫn là 112.565 sau các join 1:1/N:1.
- Không join trực tiếp `auth_events` hoặc `account_change_events` trước khi aggregate; sẽ nhân bản transaction.
- Với mọi rolling feature, chỉ dùng event có timestamp `< transaction_at`.
- `simulation_run_id` phải tham gia key/audit khi merge nhiều run để không vô tình đối chiếu nhầm entity giữa run.

---

## 5. Ý nghĩa nghiệp vụ của các scenario

| Code | Business pattern | Bảng/tín hiệu chính | Điều kiện phải được giữ sau random hóa |
|---|---|---|---|
| TXN-01 | Impossible travel | Session location/time | New location, khoảng cách lớn trong thời gian phi lý |
| TXN-02 | Dormant account awakening | Account, session, transaction | Account dormant hoạt động từ context bất thường |
| TXN-03 | Brute-force/credential stuffing | Auth, account/session | Nhiều auth fail rồi success; account-level context |
| TXN-04 | Velocity burst | Transaction, rolling feature | Nhiều transaction trong 10 phút/1 giờ |
| TXN-05 | Rapid transfer to new beneficiary | Beneficiary, transaction | Beneficiary vừa thêm rồi nhận tiền nhanh |
| TXN-06 | Full account takeover | Session, auth, change, beneficiary, transaction | Device/IP rủi ro → sensitive changes → transfer |
| TXN-07 | Money mule network | Account, beneficiary, transaction graph | Fan-in/fan-out/layering giữa nhiều account |
| TXN-08 | Emulator/proxy bot farm | Device, session, auth | Emulator/root/proxy và hoạt động hàng loạt |
| TXN-09 | Rogue employee | Branch/internal transaction | Chuyển nội bộ bất thường rồi chuyển tiếp |
| TXN-10 | SIM swap + takeover | Change event, device, beneficiary, transaction | Đổi phone/device/limit rồi rút phần lớn balance |

Random hóa amount/time/intensity không được làm mất các bất đẳng thức và thứ tự sự kiện tạo nên business rule của scenario.

---

## 6. Label contract

### 6.1. Gán nhãn đúng

Lọc bridge ở `entity_type=transaction`, sau đó join:

```text
transactions.transaction_id = scenario_event_entities.entity_id
```

| Nguồn | Điều kiện | `target_fraud` | `hard_negative` |
|---|---|---:|---:|
| Bridge | `label_scope=fraud` | 1 | 0 |
| Bridge | `label_scope=hard_negative` | 0 | 1 |
| Không có bridge row | Background transaction | 0 | 0 |
| Bridge account/context | `label_scope=context_only` | Không join vào transaction target | Không join |

Không suy nhãn từ `_SCN_`, `scenario_code`, rule hit hoặc tên ID.

### 6.2. Sample weight

Một scripted event có thể sinh một hoặc nhiều positive/hard-negative transaction. `scenario_event_entities.sample_weight` được đặt sao cho tổng trọng số của các transaction trong cùng một event bằng 1.

Khi fit model:

- Dùng `sample_weight` để TXN-07/TXN-04 không lấn át scenario một dòng.
- Background transaction không có bridge nhận weight mặc định 1, trừ khi sampling policy định nghĩa khác.
- Đánh giá cả metric có trọng số theo event và metric không trọng số theo transaction; hai góc nhìn trả lời hai câu hỏi khác nhau.

### 6.3. Account overlap

Notebook hiện thấy 12 account xuất hiện trong cả fraud và hard-negative. Đây có thể là hành vi hợp lệ theo thời gian, nhưng dẫn đến leakage nếu split theo row.

Split phải giữ toàn bộ transaction của cùng account ở một partition. Nếu split theo customer thì tự động giữ các account của cùng customer cùng partition.

---

## 7. Feature scope

### 7.1. Feature candidate

| Nhóm | Ví dụ | Nguồn |
|---|---|---|
| Current event | amount, direction, type, channel, balance trước/sau | `transactions` |
| Ratio | amount/balance, amount/single limit, amount/daily limit | Derived tại T |
| Time | hour, day-of-week, night/weekend | `transaction_at` |
| Account | status, age, dormant duration, account type | `accounts` |
| Customer | segment, KYC, base risk, province | `customers` |
| Session | new device/location, VPN/proxy, session risk | `login_sessions` |
| Device | trust, emulator/root, device risk | `devices` |
| Beneficiary | age, internal/external, risk level | `beneficiaries` và T |
| Velocity | count 10m/1h, amount sum 24h | `transaction_features` hoặc tính lại |
| Security sequence | failed auth, sensitive change count/time-since | Aggregate trước T |
| Network | counterparty reuse, fan-in/fan-out, mule-cluster size | Derived point-in-time |

### 7.2. Cột bị cấm làm model input

| Nhóm | Cột/bảng | Lý do |
|---|---|---|
| Raw ID | transaction/customer/account/session/device/beneficiary IDs | Học thuộc entity/run |
| Run metadata | `simulation_run_id`, random seed | Học khác biệt simulator |
| Generator trace | `_SCN_` hoặc pattern trong ID | Leakage trực tiếp |
| Label bridge | scenario/event/role/scope/target/hard-negative/sample-weight | Label metadata |
| Ground truth | `fraud_ground_truth`, `verification_results` | Outcome leakage |
| Operations | decisions, alerts, cases, rule hits, scores/reason codes | Được tạo sau khi biết scenario |
| JSON hint | `features.scenario_hint` | Tiết lộ scenario |
| Seed flag | synthetic-identity/mule-candidate seed | Điều khiển generator |
| Raw hash | Các `*_hash` | Chỉ nhất quán trong simulation, dễ học cluster giả |
| Constant | currency/country/status nếu chỉ có một giá trị | Không có sức phân biệt |

ID vẫn cần giữ bên ngoài feature matrix để group split, audit và error analysis.

### 7.3. Feature cần audit đặc biệt

- `amount_to_median_ratio`: phải xác nhận chỉ dùng lịch sử trước T; không dùng median toàn account có transaction tương lai.
- `txn_count_10m`, `txn_count_1h`, `txn_amount_sum_24h`: chốt rõ có bao gồm current transaction hay không và dùng cùng định nghĩa ở production.
- `is_new_device`, device/session/auth risk score: là feature nghiệp vụ hợp lệ nhưng có thể được generator tạo quá rõ theo scenario. Chạy ablation có/không có nhóm này.
- Network feature: mọi count/reuse/cluster phải point-in-time; full-dataset count sẽ gây look-ahead.

---

## 8. EDA cần làm

### 8.1. Kiểm tra data contract

- Đọc `dataset_manifest.json` và assert row count.
- Kiểm tra PK unique trong từng table và FK coverage.
- Kiểm tra `transactions` và `transaction_features` là 1:1.
- Kiểm tra bridge transaction link đều tồn tại; không có duplicate event–entity link.
- Kiểm tra grain sau từng join; phát hiện row multiplication ngay lập tức.
- Parse boolean, numeric, ISO datetime có timezone và JSON đúng kiểu.

### 8.2. Population và target

- Confirm 108.568 background, 2.386 fraud, 1.611 hard-negative.
- Phân tích riêng ba population thay vì chỉ fraud/normal.
- So sánh số event và số transaction theo scenario.
- Kiểm tra `sample_weight` cộng về 1 trong mỗi event.
- So sánh target/feature distribution theo 5 simulation run.

### 8.3. Shortcut audit

- Category chỉ xuất hiện ở fraud hoặc ở đúng một scenario.
- Amount/timestamp/intensity có spike cứng do template.
- ID/hash/run có khả năng nhận diện seed.
- Missing pattern khác hoàn hảo giữa fraud và normal.
- Rule đơn giản đạt gần 100% trên scenario nhưng không phản ánh production.
- Model performance giảm bao nhiêu khi bỏ risk score, new-device flag và seed-like feature.

### 8.4. Sequence và network

- Session → auth → account change → beneficiary → transaction.
- Time delta giữa từng bước và transaction T.
- Fan-in/fan-out và flow-through time trong mule network.
- Shared device/IP/beneficiary/counterparty giữa các account.
- Account/customer history chỉ dùng records trước T.

---

## 9. Preprocessing và split

### 9.1. Preprocessing

- Boolean string → boolean/0-1.
- Datetime → timezone-aware; tạo time feature theo timezone nghiệp vụ đã chốt.
- Amount skew → cân nhắc `log1p`, đồng thời giữ business ratios.
- Low-cardinality category → one-hot hoặc native categorical tùy model.
- High-cardinality ID/hash → không one-hot; chỉ dùng để tạo aggregate point-in-time rồi drop.
- Missing → phân biệt not-applicable, no-history và unknown; tạo indicator nếu có ý nghĩa.
- Imputer/encoder/scaler/feature selector chỉ fit trên train partition.

### 9.2. Entity-safe split

Không random row split.

Khuyến nghị:

1. Group theo `customer_id` nếu muốn chặn mọi account của cùng customer đi qua nhiều partition.
2. Hoặc group theo `account_id` nếu prediction contract chỉ yêu cầu account mới ở test.
3. Sau split, assert intersection entity giữa train/validation/test bằng 0.
4. Kiểm tra mỗi partition đều có đủ fraud scenario và hard-negative.
5. Giữ thông tin `simulation_run_id` để audit; có thể dùng một run làm seed-holdout robustness test, nhưng không đưa run ID vào model.

### 9.3. Imbalance và metric

- Fraud rate 2,12%: không dùng accuracy làm metric chính.
- Báo cáo PR-AUC, ROC-AUC bổ trợ, precision/recall/F1 tại threshold.
- Báo cáo recall tại FPR hoặc alerts-per-1.000-transactions cố định.
- Báo cáo hard-negative FPR riêng.
- Báo cáo recall theo từng scenario, không chỉ overall recall.
- Dùng sample weight/event-aware metric để scenario nhiều dòng không chi phối kết luận.

---

## 10. Business rule baseline

Notebook `00_business_rule.ipynb` định nghĩa 13 tín hiệu rule để:

1. Kiểm tra generator tạo đúng business pattern.
2. Làm baseline so sánh với ML.
3. Phát hiện synthetic shortcut.

Kết quả hiện tại:

| Metric | Giá trị |
|---|---:|
| Rule baseline recall | 0,7779 |
| Rule baseline precision | 0,0360 |

Recall khá nhưng precision rất thấp cho thấy một tập rule OR đơn giản tạo quá nhiều false positive. ML cần học interaction/combination và được đánh giá đặc biệt trên hard-negative, không chỉ cố vượt recall của rule.

Rule signal chính theo scenario:

| Scenario | Signal/rule kỳ vọng |
|---|---|
| TXN-01 | New location, new device, geo/time mismatch |
| TXN-02 | Dormant account, new device |
| TXN-03 | Failed-auth sequence; account-level only |
| TXN-04 | Velocity 10m/1h |
| TXN-05 | New beneficiary, short beneficiary age, amount/limit |
| TXN-06 | Sensitive changes, new device, VPN/proxy |
| TXN-07 | Network/fan-in/fan-out, một phần velocity |
| TXN-08 | Emulator/root, VPN/proxy, new device |
| TXN-09 | Branch/internal transfer pattern |
| TXN-10 | Sensitive changes, new device, amount/balance |

---

## 11. Giới hạn khi diễn giải kết quả model

- Đây là synthetic dataset; performance không đại diện trực tiếp cho ngân hàng thật.
- Có 5 seed nhưng vẫn cùng một generator và cùng họ logic scenario.
- Fraud/hard-negative được thiết kế có chủ đích, không phản ánh đầy đủ base rate và unknown fraud pattern production.
- TXN-03 không được học như transaction positive trong model hiện tại.
- Operational risk score và rule outcome là dữ liệu hậu nghiệm, không phải feature độc lập.
- Một số feature được generator set rõ theo scenario; model tốt có thể vẫn đang học simulator shortcut.
- Random hóa trong từng scenario giúp giảm template memorization nhưng không thay thế external/real-data validation.

Kết quả phù hợp để xây POC, kiểm tra pipeline, feature contract, rule/model integration và thresholding. Không nên dùng nó như bằng chứng duy nhất cho production readiness.

---

## 12. Lộ trình notebook hiện tại

### `00_business_rule.ipynb`

Đã chốt:

- Business target và transaction grain.
- Label bridge/policy.
- Population ba nhóm.
- Rule definition và rule baseline.
- Allow/deny feature list.
- Entity-safe split policy.

### `01_data_quality.ipynb`

Bước tiếp theo cần thực hiện:

- Schema/type/missing/duplicate/FK checks.
- Timeline và point-in-time checks.
- Join cardinality checks.
- Cross-run stability.
- Leakage/shortcut audit.
- Xuất data-quality report trước feature engineering.

### Các bước sau

```text
00 Business rule/label
  → 01 Data quality
  → EDA
  → point-in-time feature engineering
  → entity-safe split
  → preprocessing pipeline
  → baseline/model comparison
  → threshold + scenario/hard-negative error analysis
  → feature registry + SAS serving mapping
```

---

## 13. Source of truth

Ưu tiên theo thứ tự:

1. `fraud_data_generator_v2/output_training_raw/merged/dataset_manifest.json` — số run và row count thực tế.
2. `fraud_data_generator_v2/RAW_TRANSACTION_DATASET.md` — data contract, join, label và split rule.
3. `fraud_data_generator_v2/config_training_transaction.json` — training scope và scenario count.
4. `fraud_data_generator_v2/run_training_raw.py` — cách sinh/merge/verify 5 run.
5. `fraud_data_generator_v2/scenario_engine.py` — scenario, hard-negative và label bridge.
6. `fraud_data_generator_v2/rebuild_features.py` — feature hiện có và point-in-time audit target.
7. `notebooks/00_business_rule_executed.ipynb` — số liệu label/rule đã chạy.
8. `database/schema/Mapping_Generator_Fields.md` — khả năng phục vụ feature trên SAS live.

`fraud_scenarios.md` mô tả ý định nghiệp vụ; code, manifest, CSV và notebook executed mới là bằng chứng về dữ liệu thực sự đã sinh.
