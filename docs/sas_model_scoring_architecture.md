# Kiến trúc Model + Rule trong SAS Fraud Decisioning — tri thức tổng hợp

> Đóng gói lại toàn bộ kiến thức đã thống nhất qua các buổi làm việc (bao gồm câu trả lời trực tiếp từ team SAS và tài liệu NotebookLM), phục vụ tham khảo về sau khi build model/tích hợp thật. Đi kèm với [`database/schema/Mapping_Generator_Fields.md`](../database/schema/Mapping_Generator_Fields.md) (mapping field-level) và [`fraud_data_generator_v2/README_V2.md`](../fraud_data_generator_v2/README_V2.md) (pipeline sinh dữ liệu).

---

## 1. Bức tranh tổng: 3 sản phẩm SAS ghép thành 1 pipeline

```
SAS Data Explorer          SAS Model Manager           SAS Intelligent Decisioning
(nạp dữ liệu vào CAS)  →   (train/version/publish   →  (ghép Model + Rule vào 1 Decision flow,
                            model, theo dõi drift)       chấm điểm real-time)
```

- **Data Explorer**: chỉ có 1 việc — đưa dữ liệu lịch sử (CSV/DB) vào CAS để Model Studio train được. **Không tham gia** vào luồng chấm điểm real-time (message JSON đi thẳng qua REST/Kafka vào SFD, không qua Data Explorer).
- **Model Manager**: quản lý vòng đời model (register → compare → champion/challenger → publish → monitor drift/bias → retrain). **Không phải nơi chấm điểm** — chỉ là kho quản lý.
- **Intelligent Decisioning**: nơi model thật sự "sống" — 1 **Decision** là 1 flow duy nhất gộp chung Rule Set, Model, Branch, Record Contacts node... Model không thay thế rule, mà là 1 node **cùng cấp** với rule trong flow.

## 2. Model nằm ở đâu trong Decision flow, và cách ghép với Rule

Vị trí chuẩn (đã xác nhận qua ví dụ SAS thật + tài liệu):

```
[Input Payload] → [Custom Code Node: tính biến phái sinh] → [Model Node: ra risk_score]
                                                                       │
                                                                       ▼
                                                          [Rule Sets Node / Branch]
                                                     đọc risk_score + logic nghiệp vụ
                                                                       │
                                        ┌──────────────────────────────┼──────────────────────┐
                                        ▼                              ▼                        ▼
                                    Approve                        Decline                  Challenge/Alert → SVI/Alert Triage
```

**3 cách ghép Model + Rule** (không phải 1 hoặc kia — tuỳ thiết kế, có thể dùng cả 3 ở các chỗ khác nhau trong cùng flow):

1. **Rule chạy TRƯỚC, làm bộ lọc nhanh (short-circuit)**: blacklist/whitelist/VIP check rẻ, chạy trước, match thì quyết luôn, bỏ qua model.
2. **Rule chạy SAU, tinh chỉnh trong nhánh "Review" của model**: model luôn chạy trước ra risk_score → Branch rẽ Allow/Review/Decline → trong nhánh Review (vùng mập mờ), Rule Set chạy tiếp để quyết escalate thật hay auto-clear.
3. **Rule chạy SONG SONG với model, gộp bằng OR**: cả 2 cùng đọc 1 message, ra 2 tín hiệu độc lập, Branch cuối gộp `IF risk_score≥X OR rule_fired THEN Decline`. Rule đóng vai "lưới an toàn" bắt pattern mới mà model (có độ trễ học) chưa kịp học, và cho reason code tường minh dễ giải trình hơn "AI nói vậy".

**Model KHÔNG train riêng theo từng scenario/kịch bản fraud.** Ranh giới tách model đúng là theo **domain/entity/message-type khác nhau thật sự** (vd Card/Account fraud model riêng, Loan fraud model riêng — vì khác entity, khác Message Schema, khác nhãn), không phải theo 20 kịch bản tiêm lỗi (TXN-01..10, LOAN-01..10) — các kịch bản đó chỉ là cách tạo đa dạng ví dụ training cho **1 model chung** của cùng domain. Bằng chứng: môi trường SAS thật chỉ có 1 model (`DebitCard_Fraud_LogReg`/GBM) sinh 1 `fraud_score` duy nhất, không phải 10+ model riêng.

## 3. Derived/Calculated Features — 2 cách xử lý chính thức

| Cách | Khi nào dùng | Cơ chế |
|---|---|---|
| **1. Pre-calculated (batch)** | Đã có sẵn/tính trước dữ liệu (Data Explorer/Studio/script ngoài) | Tính sẵn thành 1 cột trong CAS table (vd `AVG_AMOUNT_THIS_MONTH`) → chỉ cần **Variable Mapping** đơn giản nối cột ↔ tên input model, không cần code |
| **2. In-flight (real-time)** | Chỉ có dữ liệu thô (mảng/Data Grid lịch sử giao dịch) truyền vào lúc chấm điểm | Thêm **Custom Code Node (Python/DS2)** ngay trước Model Node, code nhận input_grid, tự tính (vd trung bình), gán ra biến output, map biến đó vào Model Node |

Quy tắc chọn: field tính từ 1 mảng/lặp (cần vòng lặp/aggregate) → **bắt buộc Custom Code Node**, không dùng được Branch/expression đơn giản.

## 4. Xử lý field bị thiếu khi chấm điểm — 4 cách chính thức (xác nhận từ team SAS)

| Cách | Cơ chế | Dùng khi nào |
|---|---|---|
| **1. Flag mandatory + reject** | Field bắt buộc → SAS tự reject message thiếu, có thể thêm orchestration lưu/store-forward message bị reject | Field sống còn cho quyết định (vd amount, entity key) |
| **2. Rule logic gộp field** | Variable rule gộp nhiều field khác nguồn thành 1 field nhất quán (vd `txn_amount = cardfinancial.amount ?? payment.amount`) | Field có nhiều nguồn khác nhau tuỳ loại message |
| **3. Build multiple models theo LOẠI DỮ LIỆU STREAMING** | Tách model theo message type có hình dạng dữ liệu khác nhau (vd model Transaction riêng, model Auth riêng) — không phải theo scenario | Message type khác nhau cấu trúc hẳn (có field tài chính vs không có) |
| **4. Imputation logic** | Tính giá trị mặc định từ **phân phối dữ liệu training** (median/mode...), áp y hệt production | Field đôi lúc trống ngẫu nhiên trong CÙNG loại message |

**Lưu ý phân biệt quan trọng**: field **hoàn toàn không tồn tại** trong schema thật (PENDING_SCHEMA, vd geo/beneficiary chưa có trên SAS hiện tại) khác với field **có tồn tại nhưng đôi lúc trống**. Cách 4 chỉ dùng cho loại sau; loại trước phải dùng Mục 5 (Data Query Node) hoặc chờ mở rộng schema.

## 5. Lấy dữ liệu real-time mà KHÔNG cần lưu bảng SAS trước

SAS Intelligent Decisioning là kiến trúc microservices mở — 4 cơ chế, không bắt buộc tạo bảng CAS trước:

1. **REST API Payload trực tiếp**: publish Decision → tự thành REST endpoint, app gửi JSON, SAS xử lý thẳng trong RAM, trả kết quả trong vài ms, không ghi đĩa.
2. **Data Grid (JSON) trong payload**: gửi cả danh sách giao dịch thô dạng Data Grid trong payload, Custom Code Node parse + tính toán ngay trong luồng.
3. **Data Query Node (SQL) — quan trọng nhất cho tình huống hiện tại**: Decision flow tự query trực tiếp sang CSDL ngoài (Postgres/Oracle/MySQL...) ngay lúc chấm điểm, chỉ cần truyền key (vd `customer_id`). **Đây là đường để dùng CSDL `fraud_sim` (Postgres) tự thiết kế mà KHÔNG cần chờ SAS admin mở rộng Message Schema chính thức** — các field LOAN-\*/Beneficiary hiện PENDING_SCHEMA có thể lấy qua đường này.
4. **Custom Code Node gọi REST API ngoài**: tự dựng 1 service/API riêng, Custom Code Node (DS2/Python) gọi HTTP GET/POST lấy dữ liệu về xử lý ngay.

### Lưu ý vận hành khi dùng Data Query Node (từ NotebookLM, đã đối chiếu)
- **Đánh Index** trên field khoá (customer_id/account_id) ở CSDL ngoài — bắt buộc để trả kết quả trong vài ms, không làm chậm luồng real-time. (Postgres `fraud_sim` đã có PK trên các cột này nên tự động có index, nhưng còn treo vấn đề reachability — xem Mục 7.)
- **Default value khi query rỗng** (customer mới, chưa có dữ liệu): gán sẵn giá trị mặc định trong Decision (vd `feature_A = 0`) để model không lỗi vì Null — đây chính là bản chuẩn hoá của "Cách 4 — Imputation" ở Mục 4, áp riêng cho trường hợp Data Query Node trả về 0 dòng.
- **Rủi ro cần cân nhắc**: gọi CSDL ngoài trong luồng synchronous real-time = thêm 1 bước mạng mỗi lần chấm điểm → ảnh hưởng latency/SLA. Cần hỏi rõ latency trung bình + cấu hình timeout/fallback riêng cho bước này trước khi coi đây là giải pháp production.

## 6. CAS là gì trong toàn bộ câu chuyện

CAS (Cloud Analytic Services) — engine tính toán của Viya, **chỉ dùng cho dữ liệu training/batch** (Data Explorer import CSV vào CAS table → Model Studio train). Không liên quan gì đến Message Schema (tầng real-time). Không cần tên cột CAS trùng tuyệt đối với tên field message thật, nhưng **bắt buộc phải có 1 bảng ánh xạ rõ ràng** giữa 2 bên (chính là việc `Mapping_Generator_Fields.md` đang làm) — vì lúc nhúng model đã train vào Decision, bước "Map Object Variables to Decision Variables" cần bảng đối chiếu này để nối đúng.

## 7. SVI (Visual Investigator) khác Alert Triage — đừng lẫn

- **Alert Triage**: giao diện dạng queue/grid đơn giản (Domain → Triage Type → Queue → Disposition), không có network graph.
- **SAS Visual Investigator (SVI)**: sản phẩm khác, có Network Diagram/sơ đồ mạng lưới điều tra — cần cho kịch bản ring/mule (TXN-07, TXN-09). Cần license riêng, không tự nhiên có trong Alert Triage. Dự án `vi_bridge` đang bridge Alert Triage → VI thật qua Kafka, đúng là để nối 2 hệ thống này.

## 8. Local Postgres `fraud_sim` — rủi ro khi dùng làm nguồn cho Data Query Node

- Postgres hiện chạy local trên laptop, lắng nghe `0.0.0.0:5432` (không tự chặn ở tầng Postgres).
- Nhưng SAS Viya server có gọi vào được không phụ thuộc **network giữa 2 bên** (VPN/firewall công ty), không kiểm tra được từ phía Claude (chỉ test được 1 chiều máy này → Viya, không test được chiều ngược lại).
- Dùng laptop cá nhân làm nguồn dữ liệu sống cho 1 POC nghiêm túc **rủi ro cao**: laptop tắt/ngủ → mất kết nối, IP đổi theo DHCP → phải sửa config liên tục.
- **Khuyến nghị**: hỏi IT/SAS admin về reachability, và cân nhắc đẩy `fraud_sim` lên 1 VM/server cố định trong cùng mạng với Viya thay vì giữ trên laptop.

## 9. Thiết kế dữ liệu cho việc train/chấm điểm — 3 lỗ hổng cần né khi build notebook

Rút ra từ việc review `fraud_data_generator_v2` (đã sửa timeline/balance/ground-truth, nhưng feature set thì CHƯA sửa, tự làm ở notebook):

1. **Feature set không khớp SAS thật (train/serving skew)**: `transaction_features.csv` tính từ toàn bộ quan hệ Postgres (`is_new_beneficiary`, `failed_auth_count_30m`...) — SAS live hiện KHÔNG có profile nào theo dõi mấy cái này (chỉ có 3 profile card/account, field rất hẹp). Train model bằng toàn bộ cột này thì model học phụ thuộc vào thứ không tồn tại lúc chấm điểm thật. → Lọc feature list theo đúng bảng mapping trước khi train.
2. **Leakage**: cột `features` (JSON) có `scenario_hint` để lộ thẳng kịch bản gian lận nào tạo ra dòng đó — không được đưa vào input model. `is_new_device` copy thẳng từ cờ mà `scenario_engine.py` tự set khi dựng kịch bản (không phải quan sát độc lập) — dùng thẳng gần như dùng nhãn.
3. **Look-ahead bias**: `amount_to_median_ratio` trong `rebuild_features.py` tính median từ **toàn bộ lịch sử account kể cả giao dịch tương lai** so với thời điểm đang chấm — cần tính lại kiểu cửa sổ trượt (chỉ dùng dữ liệu tính đến thời điểm t).

## 10. Demo offline (notebook) vs demo live (SAS thật) — khi nào tự thêm field được

| | Được tự thêm field không có trong SAS live? | Điều kiện |
|---|---|---|
| **Demo offline trong notebook** (train/eval, ROC, precision-recall) | **Được, thoải mái** | Miễn tính đúng logic causal (né lỗi Mục 9), không dùng field leakage, và **ghi chú rõ** feature nào "SAS live có sẵn" vs "giả định mở rộng cho mục đích trình bày" |
| **Demo end-to-end thật** (bắn message vào SAS live, xem Alert Triage nhận) | **Không**, trừ khi dùng 1 trong 3 cách ở Mục 5 (Data Query Node / Custom Code gọi API / xin SAS admin mở schema chính thức) | Field phải parse được bởi Message Schema thật, hoặc lấy qua Data Query Node lúc runtime |

## 11. Điểm tiếp tục sau khi hoàn tất luồng Data Science

Chưa cần quyết định mở rộng SAS Profile trong giai đoạn thử nghiệm feature. Trước hết, train và đánh giá model để chốt danh sách feature cuối cùng. Sau đó mới đối chiếu từng feature với SAS live và chọn phương án serving.

### 11.1. Thông tin phải bàn giao từ Data Science

Với mỗi feature được chọn, cần lưu đủ:

- Tên feature và datatype.
- Công thức tính chính xác.
- Cửa sổ thời gian (10 phút, 24 giờ, 30/90 ngày, 3 tháng...).
- Entity key: customer, account, debit card hay credit card.
- Nguồn dữ liệu thô và các điều kiện lọc transaction.
- Quy tắc xử lý missing, khách hàng mới và không đủ lịch sử.
- Feature importance/SHAP và mức đóng góp vào model.
- SLA/latency mong muốn khi scoring.

Feature registry tối thiểu nên có dạng:

| Feature | Công thức | Window | Entity key | Có trong SAS? | Nguồn production dự kiến | Default/missing |
|---|---|---|---|---|---|---|
| `txn_amount` | Số tiền giao dịch hiện tại | Current | Transaction | Có | Message | Reject nếu thiếu |
| `avg_txn_amount_90d` | `AVG(amount)` với `transaction_at < T` | 90 ngày | Account | Chưa | Profile/feature table/DB | Training median + history flag |
| `amount_vs_avg_ratio` | `txn_amount / avg_txn_amount_90d` | 90 ngày | Account | Chưa | Derived trong Decision | Missing flag |
| `txn_count_10m` | Số giao dịch trong `[T-10m, T)` | 10 phút | Card/account | Suy ra được | SAS Profile | `0` |
| `is_new_device` | Thiết bị hiện tại không thuộc danh sách known | Lịch sử | Debit card | Suy ra được | SAS Profile | Unknown flag |

### 11.2. Các phương án serving feature

| Phương án | Cách hoạt động | Ưu điểm | Nhược điểm |
|---|---|---|---|
| **SAS Profile** | SAS lưu và cập nhật lịch sử hành vi theo card/account | Nhanh, nằm trong SAS, phù hợp real-time, ít phụ thuộc bên ngoài | Cần SAS admin cấu hình; khó thay đổi; profile hiện tại còn hạn chế |
| **Data Query Node aggregate trực tiếp** | Mỗi lần scoring, query DB và chạy `AVG`/`SUM`/`COUNT` | Linh hoạt, dễ làm POC, không cần sửa Profile/Message Schema | Tăng latency; phụ thuộc DB/network; aggregate mỗi request có thể chậm |
| **Precomputed Feature Table/Feature Service** | Batch/streaming tính sẵn, SAS chỉ lookup giá trị mới nhất | Lookup nhanh; quản lý công thức tập trung; phù hợp production | Cần thêm pipeline/service; có độ trễ; phải quản lý version và độ tươi |
| **Data Grid + Custom Code Node** | Payload mang lịch sử; Python/DS2 tính feature trong Decision | Tự chứa trong request; linh hoạt; không query DB | Payload lớn; code phức tạp; tăng latency; không phù hợp lịch sử dài |
| **Custom Code gọi API ngoài** | Decision gọi feature API/service để lấy hoặc tính feature | Tách logic khỏi SAS; tái sử dụng; xử lý được logic phức tạp | Thêm dependency mạng; phải vận hành API, auth, timeout và fallback |
| **Chỉ dùng field trong message** | Model chỉ nhận field hiện có trong request | Đơn giản, latency thấp, dễ vận hành | Feature nghèo; khó phát hiện bất thường theo lịch sử |

### 11.3. Thứ tự ưu tiên sau khi chốt feature

1. Giữ các feature có sẵn trong Message Schema.
2. Dùng SAS Profile cho feature velocity/real-time quan trọng, ổn định và cần latency thấp.
3. Dùng Precomputed Feature Table cho aggregate lịch sử dài như 30/90 ngày.
4. Dùng Data Query Node aggregate trực tiếp trong giai đoạn POC/xác nhận feature.
5. Chỉ dùng Data Grid cho demo hoặc lịch sử rất ngắn.
6. Feature ít quan trọng nhưng khó cung cấp ổn định trong production thì loại khỏi model production.

### 11.4. Kiểm tra bắt buộc trước khi tích hợp SAS

- Training và serving phải dùng cùng công thức, window, timezone và default.
- Feature tại thời điểm `T` chỉ được dùng dữ liệu có thời gian `< T`.
- Không dùng `scenario_hint`, risk score, decision, alert, verification hoặc label làm input model.
- Kiểm tra mapping theo ba tầng: raw source → Decision variable; history/profile → derived feature; Decision variable → Model input.
- Feature không có nguồn production tin cậy phải được thay thế hoặc loại bỏ trước khi publish model.

---

*Tài liệu này tổng hợp tri thức đã thống nhất, không phải hướng dẫn thao tác từng bước — xem `Mapping_Generator_Fields.md` cho mapping field cụ thể, `README_V2.md` cho cách chạy generator.*
