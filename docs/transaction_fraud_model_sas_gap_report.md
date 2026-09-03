# Model `transaction_fraud` (LOGISTIC_CORE_V1) — Đánh giá & Gap Analysis đưa lên SAS

> Tổng hợp từ phiên làm việc dùng `sas-execution-mcp` để đọc trực tiếp `detection.sas` của org `BANKING_FRAUD` (Detection organization ID `35402c0a-8201-46f0-85ab-db94d520fcd8`) và đối chiếu với model train local tại `models/transaction_fraud/`. Bổ sung cho [`sas_model_scoring_architecture.md`](./sas_model_scoring_architecture.md) (kiến trúc chung Model+Rule) — tài liệu này tập trung vào **tình trạng thật của org `BANKING_FRAUD`** và **khoảng cách cụ thể** để đưa model local lên.

---

## 1. Hiện trạng model/score đang chạy thật trên SAS (org `BANKING_FRAUD`)

**Model Repository** (`list_registered_models`):

| Model | Loại | Version | Ghi chú |
|---|---|---|---|
| `DebitCard_Fraud_GBM` | Gradient Boosting, 18 features | 3.0 | Đang được rule gọi live |
| `DebitCard_Fraud_LogReg` | Logistic Regression | 2.1 | Được đánh dấu **champion** trong description, nhưng KHÔNG phải model rule đang gọi |
| `Python_DecisionTree_Fraud` | Decision Tree max_depth=5, gini, class_weight=balanced | 2.0 | — |

**MAS modules đã publish**: `debitcard_fraud_gbm`, `debitcard_fraud_gbm_8de7104aa42f`, `debitcard_fraud_logreg`, `python_decisiontree_fraud`, decision flow `"Debit Card Fraud GBM Decision1_0"`, `"Debit Card Fraud Decision1_0"`.

**Rule đang gọi model thật** (`detection.sas`, rule `50078.2 – "CC Fraud ML Score and 30min Velocity"`):
```
if (detection.score('DC_Fraud_GBM_MAS') > 85) then alert
else if (detection.score('DC_Fraud_GBM_MAS') > 60 AND profile.SAS_CreditCard.txnCount30Min > 3) then alert
else if (profile.SAS_CreditCard.txnCount30Min > 8) then alert
```
- Tên alias `'DC_Fraud_GBM_MAS'` không khớp 100% ký tự với MAS module id nào — khả năng cao là alias đăng ký qua `detection.defineModels(json)` (wrapper method có trong code, nhưng **không tìm thấy call site JSON** trong `detection.sas` này — cấu hình alias nằm ở nơi khác, chưa verify được).
- **Phát hiện quan trọng**: model champion (LogReg) và model đang chạy live (GBM) là **2 model khác nhau** — cần làm rõ đây là chủ đích hay lệch đồng bộ Model Manager ↔ Decisioning.

**Data train của `DebitCard_Fraud_GBM`** (`get_castable_columns` trên CAS table `Public.BALANCED_FRAUD`, 60 rows, 31 cột): `Time, V1...V28, Amount, Class` — **chính xác là bộ Kaggle "Credit Card Fraud Detection" (ULB) public demo**, các cột `V1-V28` là PCA-anonymized, hoàn toàn không phải feature nghiệp vụ thật của ngân hàng. → Model GBM đang chạy live thực chất là **demo/PoC**, score của nó không mang ý nghĩa fraud thật cho giao dịch của tổ chức.

## 2. Message Schema / Profile Store hiện tại — rất tối giản

Từ comment header của `detection.sas` (org dùng 3 Message Schema: Card Fraud, Payment Fraud, Application Fraud, ghép từ ~30 Component Message dùng chung, trong đó có 1 component chuẩn tên **"Core" v17.3.0** — cung cấp field khung chung cho mọi message, nhưng **không có field nào của Core đang thực sự map** trong DS2 hiện hành).

Field thật trong từng component (rất ít, ví dụ):

| Component | Field có sẵn |
|---|---|
| `customer` | chỉ `identifier` |
| `debitaccount` | `availableBalance`, `number` |
| `device` | chỉ `identifier` |
| `cardfinancial` | `amount`, `cardPresentInd`, `ecommerceAuthentication` |
| `solution` | `activityType`, `authenticationType`, `channelType`, `customerType`, `originationType` (đều varchar(2), mã hoá) |
| `sas.system` | `messageDtTmUtc`, `transactionDtTmUtc` (timestamp thật, dùng được để derive giờ/thứ) |

**Không tồn tại component "Beneficiary"** trong danh sách 30 component đang dùng.

**Profile Store**: xác nhận qua code `detection.setMehMode('redis')` (trong constructor `CustomContext()`, comment ghi rõ "chỉ gọi được từ DS2 batch, không phải SCR/MAS") → **Profile Store chạy trên Redis**, và **có sẵn 1 chế độ chạy DS2 batch riêng** để replay dữ liệu lịch sử qua đúng logic cập nhật Profile (cơ chế backfill chuẩn — chưa xác nhận có batch destination/job nào đã cấu hình sẵn cho việc này, `list_publishing_destinations`/`list_jobs` không thấy tên rõ ràng).

Profile hiện có, đều rất sơ khai:
- `profile_SAS_CreditCard`: có `txnCount30Min` (velocity 30 phút, chỉ credit card)
- `profile_SAS_DebitAccount`: chỉ có 2 field datetime (`firstPaymentDtTm`, `overLimitDtTm`) — **không có bất kỳ velocity counter/sum nào**
- `profile_SAS_DebitCard`: có `knownDeviceFingerprint[10]` (LRU device fingerprint) — nhưng chỉ gắn với debit card, không phải account/transfer

**Phát hiện thêm**: method `UpdateValues(message)` của **cả 3 profile trên đều rỗng hoàn toàn** (không có dòng code nào bên trong, kể cả `profile_SAS_CreditCard` — nơi `txnCount30Min` đang chạy live). → Logic tăng/giảm counter thật sự **không nằm trong file DS2 sinh ra này** — nhiều khả năng SAS Detection quản lý phần đếm/cộng dồn qua một tầng khai báo riêng trong Profile Manager (khai báo "đếm field X trong cửa sổ Y, khoá theo Z, retention N ngày" trên UI, nền tảng tự sinh cơ chế tăng/hết hạn trong Redis) — `UpdateValues()` chỉ là hook mở rộng cho logic tuỳ biến thêm, hiện chưa ai dùng. Ý nghĩa: build Tier 3/4 nhiều khả năng là **cấu hình Profile Manager UI** (giống cách `txnCount30Min` đã được set up), không phải viết tay DS2 — nhưng cần admin SAS xác nhận lại vì chưa thấy được giao diện Profile Manager thật.

## 3. Model local `transaction_fraud` (LOGISTIC_CORE_V1) — tổng quan

Nguồn: `models/transaction_fraud/final/` (đã lock, có `final_model_manifest.json`, `sas_input_schema.csv`, `sas_feature_mapping.csv`, `scoring_utils.py`).

- **34 raw feature** → 50 processed feature (sau OHE), pipeline sklearn (`CalibratedFraudPipeline`: base pipeline + Platt calibrator).
- Output chuẩn: `fraud_probability` → `model_risk_score` (0–100) → `risk_band` (LOW/MEDIUM/HIGH/CRITICAL) → `decision` (APPROVE/REVIEW_CONTEXT/CHALLENGE_OR_ALERT/HOLD_AND_ALERT).
- **Hard rule bổ trợ** (kết hợp với score, giống pattern rule+model của SAS): `is_new_device AND is_new_beneficiary AND (is_high_balance_drain OR is_high_limit_usage)`.
- Test metrics (`RUN_TXN_TRAIN_005`, 22,134 rows / 477 fraud): PR-AUC 0.9967, ROC-AUC 0.99995, alert rate ~30/1000, precision ~49%, recall ~99.7%.
- Nguồn data train: `fraud_data_generator_v2/output_training_raw/merged/` — bộ bảng chuẩn hoá đầy đủ (`customers`, `accounts`, `transactions`, `devices`, `beneficiaries`, `auth_events`, `login_sessions`, `rules`/`rule_hits`, `fraud_ground_truth`, `scenario_manifest` — 10 kịch bản TXN-01..10), ID nhất quán xuyên suốt các bảng.

### Đánh giá chất lượng / độ phù hợp mục đích

✅ **Đúng/tốt hơn thiết kế mẫu của SAS**: output là xác suất calibrated + risk band + action mapping tường minh, kết hợp hard rule — đúng và chi tiết hơn cách rule `50078.2` hiện dùng (chỉ so sánh ngưỡng thô 85/60, không calibrate, không band).

⚠️ **Rủi ro cần lưu ý trước khi tin tưởng số liệu**:
1. **`log_amount` chiếm 51.7% tổng importance**; **12/34 feature = 0.0 importance** (`hour_sin/cos`, `dow_sin/cos`, `is_night`, `is_weekend`, `device_age_minutes`, `kyc_level`, `amount_to_limit_ratio`, `velocity_intensity`, `is_high_balance_drain`, `account_type`). Kết hợp PR-AUC ~1.0 trên **mọi** thuật toán/tier kể cả bản NO_SHORTCUT (`champion_candidates.csv`) → dấu hiệu rõ bộ data giả lập **dễ tách lớp hơn thực tế nhiều** (chính `training_manifest.json` tự flag rủi ro "shortcut/generalization audit").
2. **Test set không có fraud sample nào ở channel `api`/`web`** (0 fraud_rows — `stability_metrics.csv`), trong khi channel `atm` lại có tỷ lệ fraud bất thường 72% (40/55) — phân phối lệch xa thực tế, chỉ dùng được cho mục đích test nội bộ.
3. → **Kết luận**: kiến trúc/cách dùng đúng mục đích SAS model score, nhưng **con số hiệu năng hiện tại phản ánh tính dễ tách của data giả lập, chưa chứng minh được năng lực trên giao dịch thật** — cần nói rõ giới hạn này khi trình bày, và kỳ vọng performance giảm khi có real traffic.

## 4. Gap Analysis — 34 feature vs field/Profile thật đang có

| Tier | Feature | Trạng thái |
|---|---|---|
| **0 — Sẵn sàng, không cần đổi gì** | `hour_sin/cos`, `dow_sin/cos`, `is_night`, `is_weekend` | ✅ derive trực tiếp từ `message.sas.system.messageDtTmUtc` |
| **1 — Dễ: chỉ cần Enrichment mapping** | `log_amount`, `amount_to_pre_txn_balance_ratio`, `channel` | 🟡 field gốc đã có (`cardfinancial.amount`/`payment.amount`, `debitaccount.availableBalance`, `solution.channelType`), cần map lại đúng công thức/category |
| **2 — Trung bình: thêm field mới, nguồn tĩnh/master** | `account_type`, `customer_segment`, `kyc_level`, `base_risk_level`, `single_txn_limit`, `daily_transfer_limit` → kéo theo `amount_to_limit_ratio`, `is_high_limit_usage`, `is_high_balance_drain` | ❌ chưa có field, cần thêm vào `message_customer`/`message_debitaccount` + Enrichment lookup từ reference/master table |
| **3 — Khó: cần Profile mới (streaming, theo account)** | `prior_txn_count_{10m,1h,24h}`, `prior_txn_amount_sum_{10m,1h,24h}`, `avg_amount_per_recent_txn`, `velocity_intensity`, `time_since_previous_txn_minutes_log1p`, `is_first_transaction`, `amount_to_historical_median_ratio` (+`is_extreme_median_spike`, khó nhất vì median rolling không cộng dồn đơn giản) | ❌ `profile_SAS_DebitAccount` hiện chỉ có 2 field datetime, không có counter/sum nào |
| **4 — Khó nhất: mở rộng/tạo mới Component Message + Profile** | `is_new_device`, `device_age_minutes`, `prior_device_txn_count` (đúng entity account, không phải chỉ debit card); `is_external_transfer`, `is_new_beneficiary`, `prior_beneficiary_txn_count` | ❌ cơ chế "known device" hiện chỉ có ở `profile_SAS_DebitCard` (không lưu timestamp); **Component "Beneficiary" chưa tồn tại**, phải tạo mới hoàn toàn |

**Tóm gọn**: 6/34 dùng ngay, 3/34 cần map lại, **~24/34 (~70%) cần xây mới** — bao gồm 1 domain concept hoàn toàn chưa có (Beneficiary).

## 5. Cơ chế nạp dữ liệu — phân biệt rõ 3 loại, tránh nhầm

| Loại dữ liệu | Nạp bằng gì | Ghi chú |
|---|---|---|
| **Reference/master tĩnh** (Tier 2: customer_segment, kyc_level, account_type, limit...) | CAS table qua **Import** (`upload_data`/`upload_file`) → **promote vào In-Memory** (`promote_table_to_memory`) → gắn làm nguồn Enrichment lookup (join theo customer/account id), y hệt cơ chế `sfd_mer_name_enrch` đã làm cho merchant | Không cộng dồn theo thời gian — refresh định kỳ là đủ |
| **Backfill Profile Store** (Tier 3/4: velocity, device, beneficiary) | **Không phải load thẳng vào Redis** — phải **replay dữ liệu lịch sử qua chế độ DS2 batch** (sắp theo thời gian tăng dần) để cộng dồn đúng logic, y hệt real-time. Input replay thường vẫn cần nằm ở CAS table trước khi batch job đọc | Cần verify thêm cơ chế batch job/destination cụ thể với admin SAS — org này chưa thấy destination "batch" nào đặt tên rõ |
| **Data test/trial (option 3 đã hỏi trước đó)** | CAS table tạm, chỉ để chạy thử/so sánh score qua `score_data`/`query_data` | Không phải production |

**Về nguồn data cho cả 2 loại đầu (reference + backfill)**: dùng **chính bộ `fraud_data_generator_v2/output_training_raw/merged/`** (`customers.csv`/`accounts.csv` cho reference, `transactions.csv`+`devices.csv`+`beneficiaries.csv` cho backfill) — **đúng và là lựa chọn duy nhất khả thi** trong môi trường lab hiện tại (org `BANKING_FRAUD` không nối core banking thật — bằng chứng: model GBM live cũng train trên bộ Kaggle demo public). Khuyến nghị "cần data thật" chỉ áp dụng về sau khi lên production thật.

---

## Việc cần làm tiếp theo (đề xuất, chưa thực hiện)

1. Rà lại `sas_feature_mapping.csv` × Tier 1 (log_amount, channel, balance ratio) → thử nghiệm thêm Enrichment mapping trên UI, xem cơ chế hoạt động thật.
2. Hỏi admin SAS xác nhận: có batch destination/job nào dùng để replay/backfill Redis Profile Store chưa, hay phải tự dựng qua `submit_batch_job`.
3. Chuẩn bị bảng reference mẫu từ `customers.csv`/`accounts.csv` (map đúng field cần: segment/kyc/risk/type/limit) để nạp CAS khi đến Tier 2.
4. Song song, bổ sung test case cho channel `api`/`web` (hiện chưa có fraud sample) trước khi coi model đã sẵn sàng đánh giá đầy đủ.
