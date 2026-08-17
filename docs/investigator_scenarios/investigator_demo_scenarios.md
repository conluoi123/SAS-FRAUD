# Investigator Demo Scenarios — Backlog

> Cập nhật: 17/08/2026
> Mục đích: Lưu các kịch bản demo cho giao diện dạng "Investigator" (Alert → Case →
> Disposition), tách biệt khỏi việc build rule detection trên SAS Fraud Decisioning.
> Chưa triển khai — tài liệu này là backlog cho tương lai, không phải spec đã chốt.

## Bối cảnh

Thái muốn có 1 giao diện thứ hai (ngoài Streamlit console gửi message test hiện tại)
để **nhận và xử lý Alert/Decline**, thiết kế theo kiểu SAS Visual Investigator — nghĩa
là không chỉ là 1 bảng alert phẳng, mà có khả năng **gộp nhiều alert liên quan thành 1
case, phân tích liên kết (link analysis), và đóng case với disposition** — để demo cho
khách hàng (ngân hàng) thấy chiều sâu sản phẩm.

Ghi chú: DB mô phỏng cũ của team (`database/schema/schema_mvp_phuong_quoc.sql`) đã lỗi
thời — Thái đã cập nhật bản mới, không dùng bản cũ này làm tham chiếu nữa. Khi có DB/
data model mới, cần đối chiếu lại 5 kịch bản dưới đây với cấu trúc bảng thật.

## Nguyên tắc chọn kịch bản

Mỗi kịch bản phải có **nhiều alert rời rạc, trông giống false positive riêng lẻ khi
nhìn từng cái** — chỉ khi investigator liên kết lại (theo device / IP / beneficiary /
counterparty / customer) mới lộ ra là 1 vụ gian lận thật. Đây là giá trị cốt lõi phân
biệt "Investigator" với 1 danh sách alert đơn thuần (alert đơn lẻ = 1 rule fire thì hệ
thống nào cũng có).

---

## Kịch bản A — Mule Device Ring (liên kết theo thiết bị)

**Câu chuyện:** 3 số thẻ debit khác nhau (không cùng chủ) đều phát sinh giao dịch CNP
trong vòng 20 phút, dùng chung 1 `device.identifier`. Riêng lẻ mỗi giao dịch chỉ trigger
rule "CNP + thiết bị mới" hoặc "risky MCC" — nhìn từng alert thì như 3 vụ không liên quan.

**Investigator thể hiện:** Analyst mở 1 alert, hệ thống gợi ý "3 alert khác cùng thiết bị
trong 24h" → gom thành 1 Case → xem link graph (1 device – 3 card) → nâng priority lên
Critical → confirm fraud cho cả 3, block device.

**Rule nền tảng liên quan:** Rule 1 (CNP new device — đã build), Rule "Device fan-out"
(xem `docs/rules/rule_05_device_fanout_DRAFT.md`, đang chờ xác nhận SAS có hỗ trợ profile
key theo device không).

**Vì sao đáng làm trước:** Effort thấp nhất — tái dùng rule đã build, chỉ cần thêm khả
năng gom nhiều alert theo field chung (device) ở tầng Investigator.

---

## Kịch bản B — Account Takeover Chain (liên kết theo thời gian/chuỗi sự kiện)

**Câu chuyện:** 1 khách hàng: đăng nhập từ quốc gia lạ → đổi mật khẩu → 40 phút sau giao
dịch CNP giá trị cao xác thực yếu. 3 sự kiện này bắn ra 2-3 alert riêng biệt theo thời gian.

**Investigator thể hiện:** Timeline view gộp login event + account change event +
transaction event của cùng customer trên 1 trục thời gian — investigator "đọc" ra câu
chuyện ATO trong vài giây thay vì tra log thủ công.

**Vì sao đáng làm:** Tính năng timeline kể chuyện rất trực quan, dễ trình bày trước
audience không kỹ thuật (ban lãnh đạo khách hàng).

**Phụ thuộc:** Cần message login/account-change riêng biệt gửi vào SAS (xem câu hỏi mở
ở `docs/rules/rule_06_login_impossible_travel_DRAFT.md` — cùng phụ thuộc dữ liệu).

---

## Kịch bản C — False Positive Rescue (thể hiện độ chính xác)

**Câu chuyện:** Khách hàng lớn tuổi đổi điện thoại mới, mua vé máy bay giá trị cao ngay
hôm sau → trigger "CNP + thiết bị mới + giá trị cao". Nhưng lịch sử 6 tháng gần đây khách
này có thói quen du lịch/mua sắm quốc tế tương tự.

**Investigator thể hiện:** Analyst xem "customer risk context" (lịch sử hành vi bình
thường) ngay trong case → đóng case với disposition `FALSE_POSITIVE` kèm lý do → dữ liệu
này feedback để tune ngưỡng rule sau này (Impact Analysis).

**Vì sao đáng làm:** Bank rất sợ hệ thống chặn nhầm khách VIP — chứng minh Investigator
giảm friction cho khách hàng thật, không chỉ "chặn cho chắc". Tốt để khép lại demo, xoá lo
ngại về false positive.

---

## Kịch bản D — Structuring / Mule Network qua Beneficiary chung

**Câu chuyện:** 5 tài khoản nguồn khác nhau, không liên quan gì nhau bề ngoài, đều chuyển
tiền số tiền hơi dưới ngưỡng kiểm soát (dùng rule Structuring) **về cùng 1 tài khoản thụ
hưởng** trong 2 giờ.

**Investigator thể hiện:** Link graph theo hướng ngược lại kịch bản A — không phải 1
device nhiều thẻ, mà **nhiều customer độc lập → 1 điểm hội tụ** (tài khoản mule nhận
tiền). Network analysis kinh điển cho AML/mule detection.

**Rule nền tảng liên quan:** Rule "Structuring / threshold-splitting"
(`docs/rules/rule_04_structuring_threshold_split.md`).

**Vì sao đáng làm:** Sát nhu cầu thật của compliance/AML team ở bank Việt Nam hiện nay
(quy định NHNN về tài khoản mule) — có thể là kịch bản "đắt giá" nhất để chốt deal.

---

## Kịch bản E — Repeat Offender (case history / entity memory)

**Câu chuyện:** Một customer/device từng có case đã đóng với disposition
`CONFIRMED_FRAUD` cách đây 2 tháng, giờ xuất hiện lại với 1 alert mới (khác rule, có thể
khác cả số thẻ nhưng cùng thiết bị/CCCD).

**Investigator thể hiện:** Hệ thống tự động cảnh báo "entity này từng dính case gian lận
đã xác nhận" ngay khi alert mới tạo — không cần analyst nhớ hay tra cứu thủ công.

**Vì sao đáng làm:** Cho thấy hệ thống "có trí nhớ", giá trị tích lũy theo thời gian —
luận điểm bán hàng dài hạn (càng dùng lâu càng thông minh). Yêu cầu kỹ thuật cao nhất
(cần lưu trữ case lịch sử + entity resolution) nên để sau cùng trong backlog.

---

## Thứ tự demo đề xuất (15-20 phút)

**A → D → C** — A cho thấy sức mạnh liên kết cơ bản (dễ hiểu), D nâng lên mức
network/AML (ấn tượng mạnh, đúng pain point compliance), C khép lại bằng câu chuyện
"không làm phiền khách hàng tốt" (xoa dịu lo ngại false positive). B và E để dành cho bản
demo mở rộng/sau này khi có nhiều thời gian hơn hoặc cần thuyết phục sâu hơn về giá trị
dài hạn.

## Trạng thái triển khai

Chưa triển khai bất kỳ phần nào của tài liệu này (giao diện Investigator, data model
case/alert, link analysis). Đây thuần là backlog nghiệp vụ. Việc triển khai thực tế đang
tạm gác lại để ưu tiên hoàn thiện các rule detection nền tảng trước (xem
`docs/SAS_FRAUD_RULES_CHAT_HANDOFF.md` và `docs/rules/`).
