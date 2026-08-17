# Rule 4 — Structuring / Threshold-Splitting (Smurfing)

> Trạng thái: **Prototype** — ngưỡng `500` trong code là giá trị placeholder minh hoạ,
> **chưa phải ngưỡng kiểm soát thật**. Cần Thái xác nhận giá trị thật trước khi tune.

## Mô tả nghiệp vụ

Khác với `rule_by_sas_High_Velocity` (chỉ đếm số lượng giao dịch) và `High_Total_Spend`/
`Unusual_amount` (so với trung bình lịch sử), rule này so **từng giao dịch với một ngưỡng
kiểm soát cố định (constant)** — phát hiện hành vi cố tình chia nhỏ giao dịch để né ngưỡng
review/limit. Ví dụ: 3 giao dịch 490 thay vì 1 giao dịch 1500, nếu ngưỡng review là 500.

## Field sử dụng

| Field | Trạng thái |
|---|---|
| `message.cardfinancial.amount` | Đã xác nhận có (dùng ở Rule 1) |
| `message.debitcard.number` | Profile key, đã xác nhận |
| Ngưỡng kiểm soát (constant, ví dụ `500`) | **Chưa xác nhận** — giá trị thật do business/risk owner quy định |

## Variable Rule

```sas
/*
    Rule Type: Variable
    Rule Name: rule_var_track_recent_amounts

    Mo ta:
    Luu 5 gia tri giao dich gan nhat (bao gom giao dich hien tai) va thoi diem,
    theo kieu mang dich chuyen (giong Previous_Payments_Tracker trong bo Payments goc),
    ap dung cho the ghi no thay vi tai khoan thanh toan.

    Profile Variable:
    profile.sas_debitcard.recentAmount[1..5]       - Number
    profile.sas_debitcard.recentAmountDtTm[1..5]    - Timestamp
*/

declare int i;
declare int j;

if message.solution.originationType = 'DC'
and message.solution.activityType = 'CA'
then do;

    do i = 5 to 2 by -1;
        j = i - 1;
        profile.sas_debitcard.recentAmount[i] = profile.sas_debitcard.recentAmount[j];
        profile.sas_debitcard.recentAmountDtTm[i] = profile.sas_debitcard.recentAmountDtTm[j];
    end;

    profile.sas_debitcard.recentAmount[1] = message.cardfinancial.amount;
    profile.sas_debitcard.recentAmountDtTm[1] = message.request.messageDtTm;

end;
```

## Decision Rule

```sas
/*
    Rule Type: Decision
    Rule Name: rule_cnp_structuring_threshold_split

    Mo ta:
    Canh bao khi >=2 trong so 5 giao dich gan nhat (tinh ca giao dich hien tai)
    deu nam trong khoang [80%, 100%) cua nguong kiem soat, xay ra trong 1 gio,
    va tong cac giao dich do vuot nguong -- dau hieu chia nho giao dich de ne
    kiem soat (structuring).

    LUU Y: THRESHOLD = 500 la gia tri placeholder minh hoa, CAN thay bang
    nguong kiem soat that cua the ghi no truoc khi dua vao production.
*/

declare double threshold;
declare double lower_bound;
declare double window_total;
declare int count_near_threshold;
declare int i;

if message.solution.originationType = 'DC'
and message.solution.activityType = 'CA'
then do;

    threshold = 500;
    lower_bound = threshold * 0.8;
    window_total = 0;
    count_near_threshold = 0;

    do i = 1 to 5;

        if message.request.messageDtTm - profile.sas_debitcard.recentAmountDtTm[i] < hms(1,0,0)
        then do;

            window_total = window_total + profile.sas_debitcard.recentAmount[i];

            if profile.sas_debitcard.recentAmount[i] >= lower_bound
            and profile.sas_debitcard.recentAmount[i] < threshold
            then count_near_threshold = count_near_threshold + 1;

        end;

    end;

    if count_near_threshold >= 2
    and window_total > threshold
    then do;
        detection.Alert();
    end;

end;
```

## Alert configuration

- Alert type: `Debit Account`
- Alert reason/code: `CNP_STRUCTURING_THRESHOLD_SPLIT`
- Diễn giải: `Multiple transactions clustered just under the control threshold within 1 hour`

## Cần xác nhận trên SAS (Thái check giúp)

1. Ngưỡng kiểm soát thật cho debit card là bao nhiêu? (per-transaction review/limit — có
   field nào trong `debitaccount`/`debitcard` chứa sẵn giá trị này, hay đây là số cố định
   business quy định ngoài hệ thống và phải hardcode trong rule?)
2. Nếu có field limit trong profile/message (ví dụ `debitaccount.singleTxnLimit`), nên
   dùng field đó thay vì constant `500` — cần xác nhận tên field chính xác.
   **Cập nhật 17/08/2026:** Bảng mô tả Schema (bản mới) có 2 ứng viên:
   - `message.channel.limit` (Number) + `message.channel.limitSubtype` (ví dụ
     `'PER_TXN_LIMIT'`, `'DAILY_ECOM_LIMIT'`) — có vẻ khớp nhất với ý "ngưỡng kiểm soát 1
     giao dịch", vì có phân loại theo per-transaction rõ ràng.
   - `message.debitaccount.spendLimit` (Number) — mô tả là "hạn mức chi tiêu cấp TÀI
     KHOẢN", có thể là hạn mức tổng chứ không phải per-transaction.
   Cần Thái xác nhận field nào đúng là ngưỡng "per-transaction control threshold" trước
   khi thay `THRESHOLD = 500` bằng field thật.
3. ~~QUAN TRỌNG: xác nhận quy ước `cardPresentInd`~~ — **Đã xác nhận 17/08/2026:**
   `cardPresentInd = '1'` = CNP là đúng trên môi trường này. Rule 4 hiện không dùng field
   này trong decision logic nên không bị ảnh hưởng, nhưng nếu sau này thêm điều kiện CNP
   vào rule này thì dùng `= '1'`.

## Test dự kiến (positive + negative)

- Positive: gửi 3 message liên tiếp trong 1 giờ, amount lần lượt 480, 470, 490 (đều trong
  [400, 500)) → decision rule fire ở message thứ 2 hoặc 3 (khi tổng vượt 500 và đã có ≥2
  giao dịch trong khoảng near-threshold).
- Negative: chỉ 1 giao dịch near-threshold (chưa đủ 2) → không hit.
- Negative: các giao dịch near-threshold nhưng cách nhau >1 giờ → không hit.
- Negative: 1 giao dịch duy nhất giá trị 1500 (không chia nhỏ) → không hit (đúng ý đồ, vì
  đây không phải hành vi structuring — rule khác như `Unusual_amount`/`High_Value_Payment`
  đã xử lý trường hợp giao dịch đơn giá trị lớn).
