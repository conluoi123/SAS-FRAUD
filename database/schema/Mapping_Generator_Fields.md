# Mapping: Idealized Variable Catalog ↔ SAS Message Schema/Profile THẬT (org BANKING_FRAUD)

> Đích mapping = `Message_Schema.md` + `Profile.md` (trích trực tiếp từ `detection.sas`, Build Package 50106, đang chạy live trong org **BANKING_FRAUD**) — cả 2 file này cùng 3 file Excel tham khảo giờ nằm chung trong `sas_reference/` (cùng thư mục với file này), đây là **nguồn quyền lực nhất**, ưu tiên hơn 2 file Excel tham khảo (`Bảng mô tả các Schema hiện có.xlsx` / `Bảng profile hiện có.xlsx`, vốn là catalog khả năng chung của SAS, không phải cấu hình đang chạy) và hơn cả bộ 175-biến lý tưởng hoá trong `architecture_refactored_sas_message_schema.xlsx`.
>
> Dùng bảng này để: (1) biết chính xác field nào generator phải xuất ra để SFD nhận và chạy rule được thật, (2) biết profile nào đang active để rule velocity/behavior có dữ liệu dùng.

---

## 1. Message fields — generator PHẢI xuất đúng path này

| Package.Field (path thật) | Type | Bắt buộc | Idealized Variable tương ứng | Mức khớp | Ghi chú cho generator |
|---|---|---|---|---|---|
| `request.messageClassificationName` | varchar(80) | **Có** | — (không có trong idealized catalog) | MỚI | Phải set đúng tên node classification đã cấu hình cho org, nếu sai message không route đúng rule |
| `request.schemaName` | varchar(100) | **Có** | — | MỚI | Tên schema — bắt buộc để SFD parse đúng |
| `request.messageDtTm` | double (datetime) | Không | V041 txn_timestamp / V061 event_timestamp | CLOSE | 1 field thời gian dùng chung cho mọi loại message, không tách riêng theo auth/txn như idealized design |
| `request.messageIdentifier` | varchar(36) UUID | Không | V040 transaction_id | CLOSE | Dùng làm trx_id chung, không phải riêng cho transaction |
| `solution.activityType` | varchar(2) | **Có** | V044 txn_type | CLOSE | Enum 2 ký tự — cần xin danh sách giá trị hợp lệ đã cấu hình (không thấy trong file trích xuất) |
| `solution.channelType` | varchar(2) | **Có** | V046 channel | CLOSE | Enum 2 ký tự, cùng vấn đề — cần danh sách giá trị hợp lệ |
| `solution.customerType` | varchar(2) | **Có** | V003 customer_type | CLOSE | |
| `solution.authenticationType` | varchar(2) | **Có** | — | MỚI | Không có trong idealized catalog, generator cần thêm |
| `solution.originationType` | varchar(2) | **Có** | — | MỚI | Không có trong idealized catalog, generator cần thêm |
| `customer.identifier` | varchar(100) | Không | V001 customer_id | EXACT | |
| `device.identifier` | varchar(100) | Không | V020 device_id / V021 device_fingerprint | DERIVED | Schema thật gộp ID+fingerprint làm 1 field — generator nên dùng fingerprint làm giá trị của field này |
| `debitaccount.number` | varchar(100) | Không | V010 account_id | CLOSE | **Profile Key của SAS_DebitAccount** |
| `debitaccount.availableBalance` | double | Không | V012 available_balance | EXACT | |
| `debitcard.number` | varchar(80) | Không | — (idealized catalog không có khái niệm debit card riêng biệt account) | MỚI | **Profile Key của SAS_DebitCard** |
| `creditcard.number` | varchar(80) | Không | — | MỚI | **Profile Key của SAS_CreditCard** |
| `creditcard.cardholderCountryCode` | varchar(3) | Không | V031 ip_country (gần đúng, khác domain) | CLOSE | Đây là quốc gia đăng ký thẻ, không phải quốc gia IP hiện tại |
| `creditcard.delinquencyStatus` | varchar(3) | Không | — | MỚI | |
| `creditcard.openDt` | double (datetime) | Không | — | MỚI | Ngày mở thẻ — dùng được cho kịch bản "tài khoản/thẻ mới" |
| `cardfinancial.amount` | double | Không | V042 txn_amount | EXACT (khi giao dịch thẻ) | |
| `cardfinancial.cardPresentInd` | varchar(1) | Không | — | MỚI, **QUAN TRỌNG** | Đây chính là field `cardPresentInd` đã dùng trong rule CNP hiện có — nhớ quy ước: **`'1' = CNP`** trên môi trường này (xem `feedback_sas_fraud_rule_conventions`) |
| `cardfinancial.ecommerceAuthentication` | varchar(10) | Không | — | MỚI | vd. 3DS |
| `payment.amount` | double | Không | V042 txn_amount | EXACT (khi giao dịch payment không phải thẻ) | 2 field amount riêng (cardfinancial vs payment) tuỳ loại giao dịch |
| `authentication.decision` | varchar(25) | Không | V063 auth_result | CLOSE | |
| `authentication.level` | varchar(10) | Không | V064 auth_method | CLOSE | |
| `merchant.categoryCode` | varchar(4) | Không | V049 merchant_category | EXACT | MCC |
| `merchant.country` | varchar(3) | Không | — | MỚI | |
| `merchant.terminalCategory` | varchar(15) | Không | — | MỚI | POS/ATM/eCom |
| `applicant.identifier` | varchar(100) | Không | — | MỚI, PENDING dùng | Có tồn tại nhưng org hiện chưa có message loan để tận dụng |
| `application.identifier` | varchar(100) | Không | V100 application_id | CLOSE nhưng PENDING dùng | Field tồn tại sẵn trong schema chung, nhưng chưa có `MS_LOAN_APP` variable set đi kèm |

**PENDING hoàn toàn (có trong idealized catalog, KHÔNG có field thật tương ứng nào, kể cả gần đúng):**
V022 is_emulator, V023 is_rooted_device, V030 ip_address, V032 ip_city, V033/034 lat/lon, V035 is_vpn, V036 is_proxy, toàn bộ VS_BENEFICIARY (V080-084), toàn bộ VS_EMPLOYEE (V090-097), toàn bộ VS_LOAN_CORE/EMPLOYMENT/REFERENCE/AGENT/DOCUMENT/CIC/DISBURSEMENT/REPAYMENT (V100-175), V050 branch_id, V051 atm_id, V047 counterparty_account_id.

→ **Xác nhận lần 2 (độc lập với file Excel):** org `BANKING_FRAUD` hiện tại chỉ chạy được Card/Debit fraud. Toàn bộ LOAN-\* và các kịch bản TXN cần beneficiary/network-geo/device-risk-flag (TXN-05, 06, 07, và phần geo của TXN-01/08) **không có message field thật để bơm vào** — generator sinh ra các field này cũng không ai đọc, vì SFD schema hiện tại không parse chúng.

---

## 2. Profile fields — chỉ 3 profile đang active

| Profile (Profile Key) | Field thật | Idealized profile ý tưởng | Mức khớp |
|---|---|---|---|
| `SAS_CreditCard` (`creditcard.number`) | `atmTotalDailyAmt`, `totalSpend10Min[10]`, `totalSpend10MinDtTm[10]` | txn_count_10m, sum_amount_24h | DERIVED — có mảng rolling 10 giá trị + timestamp, phải tự COUNT/SUM trong rule, không có sẵn field đếm |
| | `atmWithdrawalDtTm[10]`, `dailyTotalAtmSpend[10]` | velocity ATM | DERIVED |
| | `currentCardPresentDtTm`/`previousCardPresentDtTm` | — | MỚI — dùng so sánh current vs previous card-present cho rule CNP-sequence |
| | `currentForeignDtTm`/`previousForeignDtTm`, `currentMerchantCountry`/`previousMerchantCountry` | geo mismatch ý tưởng trong TH1 Impossible Travel | DERIVED — so sánh 2 quốc gia merchant liên tiếp, KHÔNG phải toạ độ GPS thật như bản thiết kế idealized giả định |
| | `cvv2FailureDayCnt`, `expiryDtFailureDayCnt` | failed_login_count | DERIVED — đây là đếm lỗi nhập CVV2/expiry, không phải đếm lỗi login |
| | `travelDtTm` | — | Có field tên "travel" nhưng ý nghĩa suy luận, cần hỏi lại business thật sự track gì |
| `SAS_DebitAccount` (`debitaccount.number`) | `firstPaymentDtTm`, `overLimitDtTm` | dormancy/reactivation ý tưởng TH2 | DERIVED một phần — có mốc thanh toán đầu tiên nhưng KHÔNG có `last_financial_txn_time`/`avg_balance_90d` như thiết kế idealized đòi hỏi |
| `SAS_DebitCard` (`debitcard.number`) | `knownDeviceFingerprint[10]` | device_changed_flag | **EXACT nhất trong toàn bộ mapping** — check `device.identifier` hiện tại có nằm trong mảng 10 fingerprint đã biết không → suy ra thiết bị mới |
| | `testMessageDtTm[10]`, `testerMessageDtTm` | — | Có vẻ dùng nội bộ cho test/thăm dò gian lận, không phải feature nghiệp vụ |

**PENDING hoàn toàn:** không có profile nào theo `customer_id` hay `device_id` — nghĩa là các ý tưởng `failed_login_count_5m`, `unique_ip_count_1h`, `unique_device_count_1h` trong `Profile bên SAS` (TH3 Brute Force) **hiện không có chỗ lưu** trên SAS, vì chưa có Profile Set nào keyed theo customer/device/session.

---

## 3. Việc cần làm ngay để bắt đầu generator

1. **Generator chỉ nên nhắm 3 entity có Profile thật**: `creditcard.number`, `debitaccount.number`, `debitcard.number` — vì chỉ 3 cái này SFD mới thực sự tích luỹ hành vi được. Kịch bản nào không xoay quanh 1 trong 3 entity này thì chạy xong không có rule velocity/behavior nào dùng được.
2. **Kịch bản khả thi ngay** (map được ≥70% field bắt buộc): các biến thể của TXN-04 Velocity Burst (dùng `totalSpend10Min[10]`), phần lõi của CNP-rule đã có (`cardPresentInd`), device-new-check qua `knownDeviceFingerprint[10]` (một phần TXN-01/TXN-06/TXN-10), country-mismatch qua `currentMerchantCountry`/`previousMerchantCountry` (bản rút gọn của "impossible travel", không phải GPS).
3. **Kịch bản KHÔNG khả thi trên org hiện tại** (100% PENDING field): toàn bộ LOAN-\*, TXN-05 (New Beneficiary), TXN-07 (Money Mule — cần beneficiary), TXN-09 (Rogue Employee — cần VS_EMPLOYEE) — generator có thể vẫn sinh dữ liệu này cho mục đích thiết kế/demo nội bộ, nhưng **đừng gửi vào SFD thật**, vì schema không nhận.
4. **2 field bắt buộc cần xin thêm giá trị hợp lệ** trước khi code generator: `solution.activityType`, `solution.channelType`, `solution.customerType`, `solution.authenticationType`, `solution.originationType` đều là enum 2 ký tự nhưng file trích xuất không kèm value list — cần lấy từ SAS Environment Manager hoặc hỏi người quản trị org.
