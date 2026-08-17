# Rule 7 — Chargeback Abuse (Excessive Chargebacks per Card)

> Trạng thái: **Prototype** — vừa nhận field list schema `Chargeback` từ Thái (17/08/2026),
> đã thoát trạng thái BLOCKED. Vẫn còn 1 điểm cần xác nhận trước khi deploy (routing của
> message Chargeback) — xem mục "Cần xác nhận trên SAS".

## Field schema Chargeback (do Thái cung cấp)

| Field | Kiểu | Độ dài | Quyền | Mô tả |
|---|---|---|---|---|
| `message.chargeback.merchantCurrency` | String | 3 | Read-only | Mã tiền tệ merchant trên giao dịch gốc |
| `message.chargeback.miscellaneousData` | String | 100 | Read-only | Dữ liệu bổ sung |
| `message.chargeback.amount` | Number | — | Read-only | Số tiền giao dịch gốc |
| `message.chargeback.purchaseDtTm` | Timestamp | — | Read-only | Thời điểm giao dịch gốc |
| `message.chargeback.referenceNumber` | String | 30 | Read-only | Số tham chiếu giao dịch gốc |
| `message.chargeback.identifier` | String | 100 | Read-only | Payment ID giao dịch gốc |
| `message.chargeback.paymentMethod` | String | 1 | Read-only | Phương thức thanh toán giao dịch gốc |

Nhận xét quan trọng: schema này **không có field đếm/lý do chargeback** (không có reason
code, không có status) — mỗi message Chargeback đại diện cho **1 sự kiện chargeback đơn
lẻ**, tham chiếu ngược về giao dịch gốc. Muốn phát hiện "lạm dụng chargeback" phải tự đếm
tần suất qua nhiều message Chargeback bằng variable rule (profile), không có sẵn field
đếm nào trong chính schema.

## Mô tả nghiệp vụ

Vì schema không có field mô tả mức độ nghiêm trọng/lý do, rule khả thi nhất với dữ liệu
hiện có là theo **tần suất**: 1 thẻ có nhiều chargeback trong 1 khung thời gian là dấu
hiệu bất thường (dùng thẻ gian lận rồi chủ thẻ dispute hàng loạt, hoặc merchant collusion
tạo chargeback giả, hoặc khách hàng lạm dụng chargeback — "friendly fraud" lặp lại).

## Cần xác nhận trên SAS (Thái check giúp)

1. Message Chargeback dùng `originationType`/`activityType` giá trị gì để phân biệt với
   message giao dịch thường (DC/CA)? Draft dưới đây tạm dùng `activityType = 'CB'` —
   **giá trị giả định, cần Thái xác nhận đúng convention thật.**
2. Message Chargeback có kèm `message.debitcard.number` (số thẻ bị dispute) không, để
   dùng chung profile key `SAS_DebitCard` như các rule khác? Giả định là có, vì chargeback
   luôn gắn với 1 thẻ cụ thể.

## Variable Rule (draft — chờ xác nhận routing ở trên)

```sas
/*
    Rule Type: Variable
    Rule Name: rule_var_track_chargeback_events

    Mo ta:
    Ghi nhan 3 thoi diem chargeback gan nhat tren the ghi no, theo kieu mang
    dich chuyen (giong pattern ATM_withdrawalDtTm cua bo Cards Issuing goc).

    GIA DINH: message Chargeback dung activityType = 'CB' -- CAN XAC NHAN.

    Profile Variable:
    profile.sas_debitcard.chargebackDtTm[1..3]   - Timestamp
    profile.sas_debitcard.chargebackAmount[1..3] - Number
*/

if message.solution.originationType = 'DC'
and message.solution.activityType = 'CB'
then do;

    profile.sas_debitcard.chargebackDtTm[3] = profile.sas_debitcard.chargebackDtTm[2];
    profile.sas_debitcard.chargebackAmount[3] = profile.sas_debitcard.chargebackAmount[2];

    profile.sas_debitcard.chargebackDtTm[2] = profile.sas_debitcard.chargebackDtTm[1];
    profile.sas_debitcard.chargebackAmount[2] = profile.sas_debitcard.chargebackAmount[1];

    profile.sas_debitcard.chargebackDtTm[1] = message.request.messageDtTm;
    profile.sas_debitcard.chargebackAmount[1] = message.chargeback.amount;

end;
```

## Decision Rule (draft — chờ xác nhận routing ở trên)

```sas
/*
    Rule Type: Decision
    Rule Name: rule_chargeback_abuse_frequency

    Mo ta:
    Canh bao khi the ghi no co >=3 chargeback (tinh ca chargeback hien tai)
    trong vong 90 ngay -- dau hieu lam dung chargeback / merchant collusion /
    gian lan hang loat. Action ban dau la Alert, chua Decline (chargeback la
    su kien da xay ra, khong the "tu choi" giao dich qua khu -- Alert de mo
    case dieu tra, khong phai chan giao dich).
*/

if message.solution.originationType = 'DC'
and message.solution.activityType = 'CB'
then do;

    if profile.sas_debitcard.chargebackDtTm[3] ^= 0
    and message.request.messageDtTm - profile.sas_debitcard.chargebackDtTm[3] < dhms(90,0,0,0)
    then do;
        detection.Alert();
    end;

end;
```

## Alert configuration

- Alert type: `Debit Account`
- Alert reason/code: `CHARGEBACK_ABUSE_FREQUENCY`
- Diễn giải: `3 or more chargebacks on the same debit card within 90 days`

## Vì sao Alert-only, không Decline

Khác các rule trước (chặn giao dịch đang diễn ra), message Chargeback phản ánh 1 sự kiện
**đã xảy ra trong quá khứ** (tranh chấp giao dịch cũ) — không có "giao dịch hiện tại" để
Decline. Rule này chỉ nên mở Alert để đội vận hành mở case điều tra thẻ/khách hàng, không
áp `detection.Decline()`.

## Test dự kiến (positive + negative)

- Positive: gửi 3 message Chargeback liên tiếp cho cùng `debitcard.number`, cách nhau vài
  ngày nhưng tổng trong 90 ngày → message thứ 3 fire Alert.
- Negative: 2 chargeback trong 90 ngày (chưa đủ 3) → không hit.
- Negative: 3 chargeback nhưng khoảng cách giữa cái đầu và cái thứ 3 vượt 90 ngày → không
  hit (mảng đã dịch chuyển, `chargebackDtTm[3]` là cái cũ nhất trong 3 cái gần nhất).
- Negative: sai `activityType` (không phải giá trị chargeback thật một khi được xác nhận)
  → không hit.

## Việc cần làm sau khi xác nhận routing

1. Xác nhận `activityType` thật cho message Chargeback (thay `'CB'` placeholder).
2. Xác nhận `debitcard.number` có mặt trong message Chargeback.
3. Cập nhật `app/streamlit_console/scenarios.py` — đổi status từ draft sang chính thức
   sau khi test thành công trên môi trường thật.
