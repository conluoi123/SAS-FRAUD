# Rule 2 — CNP + Merchant/MCC Rủi Ro Cao

> Trạng thái: **Prototype** — Advanced List `risky_mcc_list` đã tạo xong trên SAS (version
> 1.0), đã nạp đủ 6 mã MCC. Chỉ còn cập nhật lại decision rule để dùng list này thay vì
> hardcode, xem bản "production" trong mục Decision Rule bên dưới.

## Mô tả nghiệp vụ

Cảnh báo giao dịch CNP thẻ ghi nợ khi merchant thuộc nhóm MCC rủi ro cao (cờ bạc, tiền
điện tử, cầm đồ...) và số tiền vượt ngưỡng kiểm soát. Khác Rule 1 (dựa vào thiết bị +
auth), rule này thuần túy so khớp tĩnh (watchlist), **không cần lưu lịch sử/trạng thái**
— nên **không cần Variable Rule**, chỉ cần List + Decision Rule.

## Field sử dụng

| Field | Trạng thái |
|---|---|
| `message.merchant.categoryCode` | Đã xác nhận có (Merchant sheet, Bảng mô tả Schema) |
| `message.cardfinancial.amount` | Đã xác nhận có (dùng ở Rule 1) |
| `message.cardfinancial.cardPresentInd` | `'1'` = CNP — đã xác nhận đúng trên môi trường này |

## List Setup (thay vì hardcode MCC trong code)

**Đã tạo xong trên SAS (17/08/2026):**

- **List Name (internal)**: `risky_mcc_list`
- **Label**: `Risky MCC List`
- **Description**: `List of high risk MCCs (gambling, crypto, pawn shop, ...)`
- **Column/Type**: `MCC / String`
- **Key Column**: `MCC`
- **Version**: `1.0`
- **Giá trị đã nạp** (business cần rà soát lại, đây vẫn là danh sách minh hoạ ban đầu):
  `7995`, `6051`, `5944`, `5732`, `5816`, `5967`

Trong rule, gọi bằng `lists.risky_mcc_list.contains(message.merchant.categoryCode)` thay
vì liệt kê từng mã bằng `or`.

Còn thiếu: xác nhận list đã **Deploy** chưa (nếu lúc tạo không tick "Deploy list on
creation") — vào list `risky_mcc_list`, tab **Properties**/nút deploy để kiểm tra, vì rule
sẽ không đọc được list nếu chưa deploy.

## Decision Rule

Không có Variable Rule cho rule này (không có state để lưu).

**Bản prototype (hardcode, đang dùng để test nhanh):**

```sas
/*
    Rule Type: Decision
    Rule Name: rule_cnp_risky_mcc

    Mo ta:
    Canh bao giao dich CNP the ghi no khi merchant thuoc nhom MCC rui ro cao
    va so tien giao dich vuot nguong kiem soat. Action ban dau la Alert-only.
*/

if message.solution.originationType = 'DC'
and message.solution.activityType = 'CA'
then do;

    if message.cardfinancial.cardPresentInd = '1'
    and message.cardfinancial.amount > 300
    and (
        message.merchant.categoryCode = '7995'
        or message.merchant.categoryCode = '6051'
        or message.merchant.categoryCode = '5944'
        or message.merchant.categoryCode = '5732'
        or message.merchant.categoryCode = '5816'
        or message.merchant.categoryCode = '5967'
    )
    then do;
        detection.Alert();
    end;

end;
```

**Bản production (sau khi dựng xong `risky_mcc_list` ở trên):**

```sas
/*
    Rule Type: Decision
    Rule Name: rule_cnp_risky_mcc

    Mo ta:
    Ban production - dung Advanced List thay vi hardcode MCC, de business
    tu cap nhat danh sach ma khong can sua code.
*/

if message.solution.originationType = 'DC'
and message.solution.activityType = 'CA'
then do;

    if message.cardfinancial.cardPresentInd = '1'
    and message.cardfinancial.amount > 300
    and lists.risky_mcc_list.contains(message.merchant.categoryCode)
    then do;
        detection.Alert();
    end;

end;
```

## Alert configuration

- Alert type: `Debit Account`
- Alert reason/code: `CNP_RISKY_MCC`
- Diễn giải: `CNP transaction on a high-risk MCC above the control amount`

## Cần xác nhận trên SAS (Thái check giúp)

1. Danh sách 6 MCC hiện tại (`7995`, `6051`, `5944`, `5732`, `5816`, `5967`) chỉ là ví dụ
   minh hoạ — business/risk owner cần rà soát và chốt danh sách MCC rủi ro thật trước khi
   nạp vào `risky_mcc_list`.
2. Ngưỡng `amount > 300` là giá trị khởi đầu, cần tune bằng Impact Analysis sau khi có dữ
   liệu test/production.

## Test dự kiến (positive + negative)

- Positive: CNP, amount = 400, categoryCode = `7995` → Alert.
- Negative: CNP, amount = 400, categoryCode = `5411` (không nằm trong list) → không hit.
- Negative: CNP, amount = 250 (dưới ngưỡng), categoryCode = `7995` → không hit.
- Negative: card-present (`cardPresentInd ^= '1'`), categoryCode = `7995`, amount = 400 →
  không hit (rule chỉ áp cho CNP).

## Hướng dẫn setup từ đầu

Rule này chỉ cần 2 bước (không cần Variable Rule vì không có state/lịch sử):

### Bước 1 — Tạo Advanced List ✅ Đã xong (17/08/2026)

List `risky_mcc_list` đã tạo, đã nạp đủ 6 mã MCC. Chỉ còn kiểm tra list đã **Deploy** chưa
trước khi rule ở Bước 2 có thể đọc được.

### Bước 2 — Tạo Decision Rule

Vào `OPERATE -> Rules`, project `SAS Debit Card Fraud`:

- `Rule type`: `Decision`
- `Name`: `rule_cnp_risky_mcc`
- `Message schema`: `Payment Fraud`
- `Message classification`: `GLOBAL`

Alert config:

- `Alert type`: `Debit Account`
- `Alert reason`: `CNP_RISKY_MCC`

Paste bản production (dùng `lists.risky_mcc_list.contains(...)`) nếu List đã dựng xong ở
Bước 1; nếu chưa, tạm dùng bản hardcode để test trước. Compile, Save, Deploy, ghi lại
package version.

### Bước 3 — Test

Gửi các case ở mục "Test dự kiến" qua Streamlit console (scenario "Rule 2 — CNP +
merchant/MCC rủi ro cao"), đối chiếu `packageVersion`, `rulefired`, `sas.alerted[]` như quy
trình chung.
