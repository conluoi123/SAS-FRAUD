# Rule 3 — CNP + Subscription/Recurring-billing Card Testing

> Trạng thái: **Prototype** — chưa deploy. Cần Thái xác nhận 2 điểm ở mục "Cần xác nhận
> trên SAS" trước khi build thật trên môi trường.

## Mô tả nghiệp vụ

Kẻ gian dò thẻ đánh cắp qua các dịch vụ subscription giá trị nhỏ (ví dụ đăng ký thử app,
gói cước nhỏ) thay vì e-commerce thông thường, vì các merchant subscription thường ít bị
soi kỹ hơn. Dấu hiệu: nhiều lần thử subscription **khác nhau** bị auth fail liên tiếp trên
cùng 1 thẻ trong thời gian ngắn, sau đó có 1 lần thành công — khác về logic với
`rule_by_sas_DC_invalid_MCCs` (chỉ check MCC + amount nhỏ, không quan tâm số subscription
khác nhau) và `Multiple_Test_Transactions` trong bộ Cards Issuing gốc (chỉ đếm số giao
dịch nhỏ, không phân biệt theo subscription).

## Field sử dụng

| Field | Nguồn | Trạng thái |
|---|---|---|
| `message.merchant.subscriptionIdentifier` | Sheet Merchant, Bảng mô tả Schema | **Cần xác nhận** — có thực sự được producer gửi lên không |
| `message.cardfinancial.ecommerceAuthentication` | Đã dùng ở Rule 1 | Đã xác nhận có |
| `message.cardfinancial.amount` | Đã dùng ở Rule 1 | Đã xác nhận có |
| `message.debitcard.number` | Profile key hiện tại | Đã xác nhận có |

## Variable Rule

```sas
/*
    Rule Type: Variable
    Rule Name: rule_var_track_subscription_attempts

    Mo ta:
    Ghi nhan 3 subscriptionIdentifier gan nhat bi tu choi/that bai xac thuc
    (ecommerceAuthentication in FAILED/ATTEMPTED) tren giao dich CNP the ghi no,
    theo kieu LRU giong pattern knownDeviceFingerprint cua Rule 1.

    Profile Variable:
    profile.sas_debitcard.recentSubscriptionId[1..3]      - String
    profile.sas_debitcard.recentSubscriptionDtTm[1..3]     - Timestamp
*/

if message.solution.originationType = 'DC'
and message.solution.activityType = 'CA'
then do;

    if message.cardfinancial.cardPresentInd = '1'
    and message.merchant.subscriptionIdentifier ^= ''
    and message.merchant.subscriptionIdentifier ^= 'N/A'
    and message.cardfinancial.ecommerceAuthentication in ('FAILED', 'ATTEMPTED')
    then do;

        if message.merchant.subscriptionIdentifier ^= profile.sas_debitcard.recentSubscriptionId[1]
        and message.merchant.subscriptionIdentifier ^= profile.sas_debitcard.recentSubscriptionId[2]
        and message.merchant.subscriptionIdentifier ^= profile.sas_debitcard.recentSubscriptionId[3]
        then do;
            profile.sas_debitcard.recentSubscriptionId[3] =
                profile.sas_debitcard.recentSubscriptionId[2];
            profile.sas_debitcard.recentSubscriptionDtTm[3] =
                profile.sas_debitcard.recentSubscriptionDtTm[2];

            profile.sas_debitcard.recentSubscriptionId[2] =
                profile.sas_debitcard.recentSubscriptionId[1];
            profile.sas_debitcard.recentSubscriptionDtTm[2] =
                profile.sas_debitcard.recentSubscriptionDtTm[1];

            profile.sas_debitcard.recentSubscriptionId[1] =
                message.merchant.subscriptionIdentifier;
            profile.sas_debitcard.recentSubscriptionDtTm[1] =
                message.request.messageDtTm;
        end;

    end;

end;
```

## Decision Rule

```sas
/*
    Rule Type: Decision
    Rule Name: rule_cnp_subscription_testing

    Mo ta:
    Canh bao khi the ghi no co 3 subscription khac nhau bi tu choi/that bai
    xac thuc trong vong 30 phut (dau hieu do the qua kenh subscription).
    Action ban dau la Alert, chua Decline cho den khi tune.
*/

if message.solution.originationType = 'DC'
and message.solution.activityType = 'CA'
then do;

    if profile.sas_debitcard.recentSubscriptionId[1] ^= ''
    and profile.sas_debitcard.recentSubscriptionId[2] ^= ''
    and profile.sas_debitcard.recentSubscriptionId[3] ^= ''
    and message.request.messageDtTm - profile.sas_debitcard.recentSubscriptionDtTm[3] < dhms(0,0,30,0)
    then do;
        detection.Alert();
    end;

end;
```

## Alert configuration

- Alert type: `Debit Account`
- Alert reason/code: `CNP_SUBSCRIPTION_TESTING`
- Diễn giải: `Multiple distinct subscription auth failures on debit card within 30 minutes`

## Cần xác nhận trên SAS (Thái check giúp)

1. `message.merchant.subscriptionIdentifier` có thực sự populate trong message thật hay
   chỉ tồn tại trong workbook mà chưa được producer gửi?
2. Ngoài `ecommerceAuthentication`, có field nào khác thể hiện rõ hơn "authorization bị từ
   chối" (ví dụ `authorizationDecisionReason`) mà nên dùng thay vì suy luận qua
   `ecommerceAuthentication in (FAILED, ATTEMPTED)`?
   **Cập nhật 17/08/2026:** Bảng mô tả Schema (bản mới) xác nhận
   `message.cardfinancial.authorizationDecisionReason` (String, Read & Write) — "Lý do
   quyết định của hệ thống cấp phép" — là ứng viên tốt hơn. Cần Thái xác nhận các giá trị
   enum thực tế của field này (ví dụ mã nào tương ứng "declined do CVV/expiry sai" so với
   "declined do rủi ro chung") trước khi thay thế điều kiện hiện tại.
3. ~~QUAN TRỌNG: xác nhận quy ước `cardPresentInd`~~ — **Đã xác nhận 17/08/2026:**
   `cardPresentInd = '1'` = CNP là đúng trên môi trường này (Thái xác nhận trực tiếp).
   Bảng mô tả Schema mô tả theo chuẩn chung, không khớp mapping thực tế — không cần sửa
   gì trong rule này.

## Test dự kiến (positive + negative)

- Positive: 3 message liên tiếp trong <30 phút, mỗi message có
  `subscriptionIdentifier` khác nhau + `ecommerceAuthentication = FAILED` → variable rule
  cập nhật đủ 3 slot → decision rule fire Alert ở message thứ 3 hoặc message tiếp theo.
- Negative: chỉ 2 subscription khác nhau (chưa đủ 3 slot) → không hit.
- Negative: 3 subscription khác nhau nhưng cách nhau >30 phút → không hit.
- Negative: cùng 1 subscriptionIdentifier lặp lại 3 lần (không phải 3 subscription khác
  nhau) → không hit vì mảng không dịch chuyển (điều kiện `^=` cả 3 slot chặn ghi trùng).
