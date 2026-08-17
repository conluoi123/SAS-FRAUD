# Rule 6 — Login-to-Transaction Impossible Travel (Cross-Channel) — DRAFT / BLOCKED

> Trạng thái: **Draft, chưa thể build** — phụ thuộc xác nhận về luồng message login/session
> vào SAS. Nội dung dưới đây là pseudocode để chuẩn bị sẵn.

## Mô tả nghiệp vụ

`rule_by_sas_CC_High_velocity_transactions_in_different_countries` (bộ Cards Issuing gốc)
chỉ so sánh 2 giao dịch thẻ Card Present với nhau. Rule này khác: so sánh **vị trí đăng
nhập/phiên (session)** với **vị trí giao dịch thẻ vật lý (POS)** — kết hợp 2 họ schema
(Digital/Auth session ↔ Merchant/Location giao dịch) chưa rule nào trong 2 file gốc làm.
Đây là nền tảng cho Investigator Kịch bản B (Account Takeover Chain).

## Vì sao bị chặn (blocker chính)

Cần xác nhận hệ thống có gửi **message riêng cho sự kiện login/session** (không kèm giao
dịch thẻ) vào SAS hay không, và message đó có populate `digital.ipCountryCode` hay không.
Nếu hệ thống hiện tại chỉ gửi message khi có giao dịch tài chính thật sự, rule này không
thể chạy như thiết kế — cần phương án khác (ví dụ dùng field vị trí có sẵn trong chính
message giao dịch, nếu có).

## Cần xác nhận trên SAS (Thái check giúp)

1. Hệ thống có gửi message riêng cho login/session (không phải giao dịch tài chính) vào
   SAS không? Nếu có, dùng `activityType`/`messageClassificationName` nào để phân biệt?
2. (Đã xác nhận một phần 17/08/2026) Bảng mô tả Schema bản mới ghi rõ `ipCountryCode`
   "Dùng trực tiếp cho Rule 3 để so khớp với quốc gia thường dùng của khách hàng" — tức
   đây là field đang thực sự được dùng trên môi trường, không chỉ lý thuyết. Câu hỏi 1 ở
   trên vẫn còn mở: field này có mặt trong MỌI message giao dịch hay chỉ trong message
   online/CNP (Digital schema có thể không tồn tại cho giao dịch card-present tại POS vật
   lý — cần xác nhận).
3. Nếu không có message login riêng: có field nào trong chính message giao dịch phản ánh
   được "vị trí phiên đăng nhập gần nhất" để dùng thay thế không? Ứng viên:
   `message.customer.addressCountry` (Customer schema, bản mới) — "quốc gia cư trú của
   khách hàng" — có thể dùng làm baseline "quốc gia thường trú" để so sánh, thay vì phải
   track lịch sử session, nếu chỉ cần phát hiện lệch quốc gia đơn giản (không cần đúng
   nghĩa "impossible travel" giữa 2 sự kiện gần nhau theo thời gian).

## Pseudocode (chưa phải rule thật)

```sas
/*
    DRAFT - Variable Rule (pseudocode)
    Rule Name (de xuat): rule_var_track_session_country

    profile.sas_debitcard.lastSessionCountry    - String
    profile.sas_debitcard.lastSessionDtTm       - Timestamp

    Cap nhat khi nhan duoc message login/session (activityType/schema
    rieng, chua xac dinh ten), luu message.digital.ipCountryCode.
*/
```

```sas
/*
    DRAFT - Decision Rule (pseudocode)
    Rule Name (de xuat): rule_login_impossible_travel

    Neu giao dich the hien tai la Card Present (POS vat ly) tai mot quoc gia
    KHAC voi lastSessionCountry, va message.request.messageDtTm -
    profile.sas_debitcard.lastSessionDtTm < dhms(0,2,0,0) (trong 2 gio)
    -> Decline + Alert.
*/
```

## Việc cần làm sau khi được xác nhận

1. Xác nhận nguồn dữ liệu login/session (câu hỏi 1-3 ở trên).
2. Viết lại variable/decision rule thật theo đúng cú pháp Rule 1/3/4.
3. Cập nhật `app/streamlit_console/scenarios.py` để bỏ đánh dấu `draft-blocked`.
