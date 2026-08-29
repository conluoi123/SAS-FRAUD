# SAS Fraud Decisioning — Profile (Organization: BANKING_FRAUD)

> Nguồn: `detection.sas` (generated code, Build Package ID 50106, tạo bởi service `sas-detection-definition`, ngày 2026-08-22), tổ chức phát hiện gian lận **BANKING_FRAUD**.
> Profile lưu trạng thái/hành vi tích lũy (rolling behavior) của một **entity** (số thẻ tín dụng, số tài khoản, số thẻ ghi nợ) theo thời gian, được cập nhật mỗi khi có message mới khớp Profile Key. Đây là dữ liệu SAS dùng để tính các rule/model dựa trên hành vi lịch sử (vd. "giao dịch ATM bất thường so với lịch sử").
> ⚠️ Cấu hình gốc không có mô tả nghiệp vụ cho từng field — cột **Chức năng** là suy luận từ tên trường (naming convention), không phải văn bản chính thức.

## Cấu trúc tổng thể

```
profile (root)
├─ SAS_CreditCard    (profile_SAS_CreditCard)   — khóa: message.creditcard.number   — retention: 730 (ngày)
├─ SAS_DebitAccount  (profile_SAS_DebitAccount) — khóa: message.debitaccount.number — retention: 730 (ngày)
└─ SAS_DebitCard     (profile_SAS_DebitCard)    — khóa: message.debitcard.number    — retention: 730 (ngày)
```

Mỗi Profile được khai báo qua `addProfileKey(profileId, '<message field làm khóa>', <số ngày lưu giữ>)`. Cả 3 profile đều dùng retention = **730 ngày (~2 năm)**.

---

## 1. `SAS_CreditCard` — Hồ sơ hành vi thẻ tín dụng

**Profile Key:** `message.creditcard.number` (số thẻ tín dụng)

### Trường vô hướng (scalar)

| Field | Type | Chức năng (suy luận) |
|---|---|---|
| atmOverlimitAmt | double | Số tiền vượt hạn mức khi rút ATM |
| atmSpendDtTm | double (datetime) | Thời điểm giao dịch chi tiêu tại ATM gần nhất |
| atmTotalDailyAmt | double | Tổng số tiền đã rút/chi tại ATM trong ngày |
| balanceEnquiryDtTm | double (datetime) | Thời điểm tra cứu số dư gần nhất |
| cashbackDayCnt | int | Số ngày (đếm) liên quan đến giao dịch cashback |
| currentCardPresentDtTm | double (datetime) | Thời điểm giao dịch "thẻ hiện diện" (card-present) gần nhất — bản ghi hiện tại |
| currentForeignDtTm | double (datetime) | Thời điểm giao dịch nước ngoài gần nhất — bản ghi hiện tại |
| currentMerchantCountry | varchar(3) | Mã quốc gia merchant của giao dịch hiện tại |
| currentMessageDtTm | double (datetime) | Thời điểm nhận message hiện tại |
| cvv2FailureDayCnt | int | Số lần nhập sai CVV2 tính theo ngày |
| cvv2FailureDtTm | double (datetime) | Thời điểm lần nhập sai CVV2 gần nhất |
| detailChangeDtTm | double (datetime) | Thời điểm thay đổi thông tin chi tiết thẻ/tài khoản gần nhất |
| expiryDtFailureDayCnt | int | Số lần nhập sai ngày hết hạn thẻ tính theo ngày |
| expiryDtFailureDtTm | double (datetime) | Thời điểm lần nhập sai ngày hết hạn gần nhất |
| firstWithdrawalDtTm | double (datetime) | Thời điểm rút tiền đầu tiên (mốc để tính "giao dịch đầu tiên") |
| lastMessageDtTm | double (datetime) | Thời điểm message trước đó (trước bản ghi hiện tại) |
| lateNightWithdrawalDtTm | double (datetime) | Thời điểm rút tiền vào khung giờ khuya gần nhất |
| lowvalueMessageDayCnt | int | Số message giá trị thấp tính theo ngày |
| lowvalueMessageDtTm | double (datetime) | Thời điểm message giá trị thấp gần nhất |
| passwordResetDtTm | double (datetime) | Thời điểm đặt lại mật khẩu/PIN gần nhất |
| previousCardPresentDtTm | double (datetime) | Thời điểm giao dịch "thẻ hiện diện" trước đó |
| previousForeignDtTm | double (datetime) | Thời điểm giao dịch nước ngoài trước đó |
| previousMerchantCountry | varchar(3) | Mã quốc gia merchant của giao dịch trước đó |
| testerMessageDtTm | double (datetime) | Thời điểm message thử nghiệm ("tester"/thăm dò gian lận) gần nhất |
| travelDtTm | double (datetime) | Thời điểm ghi nhận hành vi "đi du lịch" (đổi vị trí địa lý bất thường) |

### Trường mảng (array, 10 phần tử — rolling window)

| Field | Type | Chức năng (suy luận) |
|---|---|---|
| totalSpend10MinDtTm | double(datetime)[10] | Dấu thời gian của các giao dịch trong cửa sổ trượt "tổng chi tiêu 10 phút" |
| atmWithdrawalDtTm | double(datetime)[10] | Dấu thời gian của 10 lần rút ATM gần nhất |
| totalSpend10Min | double[10] | Tổng số tiền chi tiêu theo từng mốc trong cửa sổ trượt 10 phút |
| dailyTotalAtmSpend | double[10] | Tổng chi tiêu ATM theo ngày (lưu vết 10 giá trị gần nhất) |
| testMessageDtTm | double(datetime)[10] | Dấu thời gian của 10 message thử nghiệm gần nhất |

---

## 2. `SAS_DebitAccount` — Hồ sơ hành vi tài khoản ghi nợ

**Profile Key:** `message.debitaccount.number` (số tài khoản)

| Field | Type | Chức năng (suy luận) |
|---|---|---|
| firstPaymentDtTm | double (datetime) | Thời điểm thanh toán đầu tiên trên tài khoản (mốc tài khoản mới hoạt động) |
| overLimitDtTm | double (datetime) | Thời điểm gần nhất tài khoản vượt hạn mức |

---

## 3. `SAS_DebitCard` — Hồ sơ hành vi thẻ ghi nợ

**Profile Key:** `message.debitcard.number` (số thẻ ghi nợ)

### Trường vô hướng (scalar)

| Field | Type | Chức năng (suy luận) |
|---|---|---|
| currentMessageDtTm | double (datetime) | Thời điểm nhận message hiện tại |
| detailChangeDtTm | double (datetime) | Thời điểm thay đổi thông tin chi tiết thẻ gần nhất |
| lastMessageDtTm | double (datetime) | Thời điểm message trước đó |
| testerMessageDtTm | double (datetime) | Thời điểm message thử nghiệm gần nhất |

### Trường mảng (array, 10 phần tử)

| Field | Type | Chức năng (suy luận) |
|---|---|---|
| testMessageDtTm | double(datetime)[10] | Dấu thời gian của 10 message thử nghiệm gần nhất |
| knownDeviceFingerprint | varchar(40)[10] | Danh sách (tối đa 10) vân tay thiết bị (device fingerprint) đã biết từng dùng với thẻ này — dùng để phát hiện thiết bị lạ |

---

### Ghi chú
- Mỗi Profile được cập nhật thông qua method `UpdateValues(message)` — nhận toàn bộ `message` hiện tại để tính lại/ghi đè các trường hành vi ở trên.
- Các trường dạng `*DtTm` gần như đều lưu **dấu thời gian của lần xảy ra sự kiện gần nhất** (dùng để tính khoảng cách thời gian giữa các giao dịch — velocity/recency rule).
- Các trường dạng `*DayCnt` là **bộ đếm theo ngày**, thường dùng cho rule dạng "quá N lần trong ngày".
- Trường mảng 10 phần tử dùng cho các rule cần nhìn lại **lịch sử N sự kiện gần nhất** (rolling window), không chỉ giá trị tức thời.
