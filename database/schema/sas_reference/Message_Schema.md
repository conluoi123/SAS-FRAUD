# SAS Fraud Decisioning — Message Schema (Organization: BANKING_FRAUD)

> Nguồn: `detection.sas` (generated code, Build Package ID 50106, tạo bởi service `sas-detection-definition`, ngày 2026-08-22) — lấy trực tiếp từ tổ chức phát hiện gian lận **BANKING_FRAUD** qua SAS Information Catalog (folder `BANKING_FRAUD`, file `detection.sas`).
> Mỗi package `message_xxx` tương ứng với một **VariableSet** (nhóm trường) trong Message Schema. Cột **Bắt buộc** và **Chế độ truy cập** lấy từ cấu hình mapper gốc (`0/1` = optional/required, `ro/rw/na` = read-only / read-write / not-applicable).
> ⚠️ File cấu hình gốc không có mô tả nghiệp vụ (trường `description` rỗng) — cột **Chức năng** dưới đây là suy luận hợp lý từ tên trường, không phải văn bản chính thức của SAS.

## Cấu trúc tổng thể

```
message (root)
├─ applicant           (message_applicant)
├─ application          (message_application)
├─ authentication        (message_authentication)
├─ cardfinancial         (message_cardfinancial)
├─ creditcard            (message_creditcard)
├─ customer              (message_customer)
├─ debitaccount          (message_debitaccount)
├─ debitcard             (message_debitcard)
├─ device                (message_device)
├─ merchant              (message_merchant)
├─ payment               (message_payment)
├─ request               (message_request)
├─ sas                   (message_sas)
│   ├─ modelfired[1]     (message_sas_modelfired)   -- mảng 1 phần tử
│   └─ system            (message_sas_system)
└─ solution              (message_solution)
```

---

## 1. `applicant` — Người nộp hồ sơ / đăng ký

| Field | Type | Bắt buộc | Truy cập | Chức năng |
|---|---|---|---|---|
| identifier | varchar(100) | Không | ro | Mã định danh của applicant (người/đối tượng đang nộp hồ sơ mở tài khoản, thẻ...) |

## 2. `application` — Hồ sơ đăng ký / mở sản phẩm

| Field | Type | Bắt buộc | Truy cập | Chức năng |
|---|---|---|---|---|
| identifier | varchar(100) | Không | ro | Mã định danh của hồ sơ đăng ký (application) |

## 3. `authentication` — Thông tin xác thực giao dịch

| Field | Type | Bắt buộc | Truy cập | Chức năng |
|---|---|---|---|---|
| decision | varchar(25) | Không | ro | Kết quả quyết định xác thực (vd. approved/declined/challenge) |
| level | varchar(10) | Không | ro | Mức độ / cấp xác thực đã áp dụng (vd. OTP, biometric, 3DS...) |

## 4. `cardfinancial` — Thông tin tài chính của giao dịch thẻ

| Field | Type | Bắt buộc | Truy cập | Chức năng |
|---|---|---|---|---|
| amount | double | Không | ro | Số tiền giao dịch thẻ |
| cardPresentInd | varchar(1) | Không | ro | Cờ cho biết thẻ có hiện diện vật lý tại điểm giao dịch hay không (card-present) |
| ecommerceAuthentication | varchar(10) | Không | ro | Loại xác thực thương mại điện tử áp dụng cho giao dịch (vd. 3DS...) |

## 5. `creditcard` — Thông tin thẻ tín dụng

| Field | Type | Bắt buộc | Truy cập | Chức năng |
|---|---|---|---|---|
| cardholderCountryCode | varchar(3) | Không | ro | Mã quốc gia của chủ thẻ |
| delinquencyStatus | varchar(3) | Không | ro | Trạng thái nợ quá hạn của thẻ |
| number | varchar(80) | Không | ro | Số thẻ tín dụng — **là khóa Profile (Profile Key)** cho `profile.SAS_CreditCard` |
| openDt | double (datetime21.2) | Không | ro | Ngày/giờ mở thẻ |

## 6. `customer` — Thông tin khách hàng

| Field | Type | Bắt buộc | Truy cập | Chức năng |
|---|---|---|---|---|
| identifier | varchar(100) | Không | ro | Mã định danh khách hàng |

## 7. `debitaccount` — Tài khoản thanh toán / ghi nợ

| Field | Type | Bắt buộc | Truy cập | Chức năng |
|---|---|---|---|---|
| availableBalance | double | Không | ro | Số dư khả dụng của tài khoản tại thời điểm giao dịch |
| number | varchar(100) | Không | ro | Số tài khoản — **là khóa Profile (Profile Key)** cho `profile.SAS_DebitAccount` |

## 8. `debitcard` — Thẻ ghi nợ

| Field | Type | Bắt buộc | Truy cập | Chức năng |
|---|---|---|---|---|
| number | varchar(80) | Không | ro | Số thẻ ghi nợ — **là khóa Profile (Profile Key)** cho `profile.SAS_DebitCard` |

## 9. `device` — Thiết bị thực hiện giao dịch

| Field | Type | Bắt buộc | Truy cập | Chức năng |
|---|---|---|---|---|
| identifier | varchar(100) | Không | ro | Mã định danh/vân tay thiết bị (device fingerprint hoặc device ID) |

## 10. `merchant` — Đơn vị chấp nhận thanh toán

| Field | Type | Bắt buộc | Truy cập | Chức năng |
|---|---|---|---|---|
| categoryCode | varchar(4) | Không | ro | Mã ngành hàng của merchant (MCC — Merchant Category Code) |
| country | varchar(3) | Không | ro | Mã quốc gia của merchant |
| terminalCategory | varchar(15) | Không | ro | Loại/danh mục thiết bị đầu cuối (POS, ATM, e-commerce...) |

## 11. `payment` — Thông tin thanh toán chung

| Field | Type | Bắt buộc | Truy cập | Chức năng |
|---|---|---|---|---|
| amount | double | Không | ro | Số tiền thanh toán |

## 12. `request` — Metadata điều khiển của message (request envelope)

| Field | Type | Bắt buộc | Truy cập | Mặc định | Chức năng |
|---|---|---|---|---|---|
| clientAmount | double | Không | ro | 0 | Số tiền do client gửi lên |
| clientDecision | int | Không | ro | — | Quyết định do client đưa ra trước khi gọi detection |
| command | varchar(8) | Không | ro | — | Lệnh xử lý (vd. Execute, Error...) cho message hiện tại |
| decisioningInd | int | Không | ro | 1 | Cờ bật/tắt việc chạy decisioning cho message này |
| logLevel | int | Không | na | 0 | Mức độ log áp dụng khi xử lý message |
| messageClassificationName | varchar(80) | **Có** | ro | — | Tên phân loại message — quyết định luồng rule/model nào sẽ chạy |
| messageDtTm | double (datetime21.2) | Không | ro | — | Ngày/giờ tạo message |
| messageIdentifier | varchar(36) | Không | ro | — | Mã định danh duy nhất (UUID) của message |
| messageVisibility | varchar(100) | Không | ro | — | Phạm vi hiển thị của message |
| restResponse | int | Không | rw | 0 | Kết quả trả về qua REST — có thể được ghi lại trong lúc xử lý |
| restResponseFlg | int (binary) | Không | ro | — | Cờ nhị phân cho biết có cần trả response qua REST hay không |
| schemaName | varchar(100) | **Có** | ro | — | Tên schema của message (định danh loại message đang gửi vào) |

## 13. `sas.modelfired[1]` — Kết quả model đã chạy (mảng 1 phần tử)

| Field | Type | Chức năng |
|---|---|---|
| elapsed | int | Thời gian (ms) model chạy xong |
| referenceIdentifier | varchar(36) | Mã tham chiếu của lượt chạy model |
| returnDesc | varchar(4) | Mã mô tả kết quả trả về |
| returnDetails | varchar(100) | Chi tiết kết quả trả về (thường dùng khi lỗi) |
| returnType | int | Loại kết quả trả về (mã trạng thái) |
| score | int | Điểm số (score) do model gian lận sinh ra |
| scoreExplanation | varchar(100) | Diễn giải cho điểm số chính |
| supplementalScores | int[10] | Mảng điểm số phụ (tối đa 10 điểm bổ sung từ model) |
| supplementalScoreExplanations | varchar(100)[10] | Diễn giải tương ứng cho từng điểm số phụ |

## 14. `sas.system` — Metadata hệ thống của message

| Field | Type | Truy cập | Chức năng |
|---|---|---|---|
| messageClassificationNode | varchar(36) | na | Node phân loại message trong cấu hình detection |
| messageDtTmUtc | double (datetime21.2) | ro | Ngày/giờ message (UTC) |
| messageIdentifier | varchar(36) | na | Mã định danh message (bản sao ở cấp system) |
| organizationIdentifier | varchar(36) | na | Mã tổ chức (organization ID) — vd. ID của BANKING_FRAUD |
| organizationName | varchar(16) | na | Tên tổ chức (vd. `BANKING_FRAUD`) |
| packageVersion | int | na | Phiên bản gói cấu hình detection (Build Package ID) |
| processInd | varchar(1) | na | Cờ cho biết message có được xử lý hay không |
| returnDesc | varchar(4) | na | Mã mô tả kết quả xử lý |
| returnDetails | varchar(100) | na | Chi tiết kết quả xử lý |
| returnType | int | na | Loại kết quả xử lý |
| schemaVersion | varchar(12) | na | Phiên bản của Message Schema đang sử dụng |
| transactionDtTmUtc | double (datetime21.2) | ro | Ngày/giờ giao dịch gốc (UTC) |
| transactionIdentifier | varchar(36) | na | Mã định danh giao dịch |

## 15. `solution` — Phân loại nghiệp vụ của giao dịch

| Field | Type | Bắt buộc | Truy cập | Chức năng |
|---|---|---|---|---|
| activityType | varchar(2) | **Có** | ro | Loại hoạt động nghiệp vụ (vd. giao dịch rút tiền, chuyển khoản...) |
| authenticationType | varchar(2) | **Có** | ro | Loại xác thực áp dụng ở mức giải pháp |
| channelType | varchar(2) | **Có** | ro | Kênh giao dịch (vd. ATM, Mobile, Internet Banking, POS...) |
| customerType | varchar(2) | **Có** | ro | Loại khách hàng (cá nhân/doanh nghiệp...) |
| originationType | varchar(2) | **Có** | ro | Nguồn gốc phát sinh giao dịch |

---

### Ghi chú
- Các trường có ghi "**là khóa Profile**" chính là field được dùng làm **Profile Key** để cập nhật Profile tương ứng — xem `Profile.md`.
- `ro` = read-only (chỉ đọc từ message đầu vào), `rw` = read-write (có thể bị ghi lại trong lúc xử lý), `na` = không map trực tiếp / dùng nội bộ.
- Toàn bộ danh sách trên được trích xuất trực tiếp từ code DS2 generated (`package "message_xxx" / inline; declare ...`), không phải diễn giải lại từ tài liệu — đảm bảo khớp 100% với cấu hình đang chạy trong tổ chức `BANKING_FRAUD`.
