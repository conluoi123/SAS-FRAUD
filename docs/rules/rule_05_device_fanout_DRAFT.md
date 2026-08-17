# Rule 5 — Device Fan-out across Multiple Cards (Mule Device Cluster) — DRAFT / BLOCKED

> Trạng thái: **Draft, chưa thể build** — phụ thuộc 1 xác nhận kiến trúc quan trọng từ
> Thái trước khi viết rule thật. Nội dung dưới đây là pseudocode để chuẩn bị sẵn, không
> phải rule sẵn sàng deploy.

## Mô tả nghiệp vụ

Toàn bộ profile trong 2 file Excel gốc + Rule 1-4 đều key theo **customer/card/account**.
Rule này cần key theo **device** — 1 thiết bị dùng để giao dịch trên nhiều số thẻ khác
nhau trong thời gian ngắn là dấu hiệu thiết bị gian lận dùng nhiều thẻ đánh cắp (mule
device). Đây là kịch bản nền tảng cho Investigator Kịch bản A (Mule Device Ring).

## Vì sao bị chặn (blocker chính)

Profile hiện tại (`SAS_DebitCard`) có profile key = `message.debitcard.number`. Rule này
cần một **Profile Variable Set mới**, ví dụ `SAS_Device`, với profile key =
`message.device.identifier` — lưu 1 mảng các số thẻ đã thấy trên thiết bị đó. Đây là thay
đổi kiến trúc (tạo Profile Variable Set mới trên SAS Detection Definition), không thể làm
chỉ bằng cách sửa rule text.

## Cần xác nhận trên SAS (Thái check giúp) — quan trọng nhất

1. Môi trường SAS Detection Definition có cho phép tạo Profile Variable Set với profile
   key = `message.device.identifier` không? (khác hẳn key theo card/account đang dùng ở
   tất cả rule khác)
2. Nếu có, giới hạn kích thước mảng String trong 1 profile variable là bao nhiêu (đủ lưu
   bao nhiêu số thẻ)?

## Pseudocode (chưa phải rule thật)

```sas
/*
    DRAFT - Variable Rule (pseudocode, chua xac nhan profile key kha thi)
    Rule Name (de xuat): rule_var_track_cards_per_device

    Neu SAS ho tro profile key = message.device.identifier:
    profile.sas_device.recentCardNumber[1..5]  - String, cac so the da thay tren thiet bi nay
    profile.sas_device.recentCardDtTm[1..5]     - Timestamp
*/

-- Tuong tu pattern rule_var_track_recent_amounts (Rule 4) nhung ghi
-- message.debitcard.number vao mang thay vi ghi amount, voi profile key
-- la device thay vi card.
```

```sas
/*
    DRAFT - Decision Rule (pseudocode)
    Rule Name (de xuat): rule_device_fanout_multi_card

    Neu trong 24h, thiet bi hien tai da xuat hien voi >= 3 so the KHAC NHAU
    (dem distinct trong mang recentCardNumber), va so the hien tai la 1 trong
    so do hoac la the moi thu 4 -> Decline + Alert.
*/
```

## Việc cần làm sau khi được xác nhận

1. Xác nhận Profile Variable Set mới `SAS_Device` được tạo trên môi trường.
2. Viết lại variable/decision rule thật (thay pseudocode) theo đúng cú pháp đã dùng ở Rule
   1/3/4.
3. Cập nhật `app/streamlit_console/scenarios.py` để bỏ đánh dấu `draft-blocked`.
