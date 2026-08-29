# Fraud Data Generator V2 — Hướng dẫn đầy đủ

## Trạng thái dữ liệu hiện tại (cập nhật 2026-08-28)

Đã chạy xong lần gần nhất, **PASSED** với 2 residual nhỏ đã biết (xem "Đã sửa gần đây" bên dưới):

```
customers 1000 | accounts 1268 | transactions 14382 | login_sessions 3228 | beneficiaries 2597
loan_applications 386 | disbursement_accounts 276 | scenario coverage 22 codes (20 kịch bản + FP-TXN + FP-LOAN)
fraud_ground_truth: 56 total = 44 confirmed_fraud + 12 false_positive_seed
verify_data.py: FAILED (2) — chỉ còn 78 transaction sau session_end_at + 146 transaction trước beneficiary added_at
  (giảm từ 7,235 và 677 trước khi sửa — xem changelog)
```

Không cần chạy lại ngay trừ khi bạn đổi `config.json` hoặc sửa code generator. Muốn kiểm tra nhanh trạng thái mà không sinh lại: `python verify_data.py`.

## Chạy lại từ đầu

Không có `.venv` riêng cho project này (chỉ dùng thư viện chuẩn: `csv`, `json`, `random`, `hashlib`, `datetime`), dùng thẳng Python hệ thống:

```bash
cd "D:\Thực tập\HPT\fraud_data_generator_v2"
python run_all_v2.py      # sinh toàn bộ dữ liệu (mất ~5-10s)
python verify_data.py     # kiểm tra tính hợp lệ, in ra ROW COUNTS + lỗi nếu có
```

`run_all_v2.py` chạy đúng thứ tự: sinh bảng nền (`engine.py`) → tiêm 20 kịch bản + hard-negative (`scenario_engine.py`) → chain lại số dư (`recompute_balances.py`) → tính lại feature (`rebuild_features.py`) → build decision/alert/case/ground-truth (`build_operations_v2.py`).

Muốn đổi seed/số lượng để sinh bộ dữ liệu khác: sửa `config.json` rồi chạy lại `run_all_v2.py` — toàn bộ `output/*.csv` sẽ bị ghi đè.

## Tác dụng từng file (đúng theo pipeline THẬT đang chạy)

### Entry point
| File | Vai trò |
|---|---|
| `run_all_v2.py` | **Entry point duy nhất nên dùng.** Điều phối toàn bộ pipeline theo đúng thứ tự ở trên. |
| `run_all.py` | **Legacy/cũ, đừng dùng.** Bản V1 trước khi có scenario injection — chỉ gọi `gen(t)` cho mọi bảng bằng logic yếu trong `engine.py` (không có 20 kịch bản, không có ground truth tin cậy). Giữ lại để tham khảo lịch sử, không phải pipeline hiện hành. |

### Logic sinh dữ liệu thật
| File | Vai trò |
|---|---|
| `generators/engine.py` | **Nơi chứa toàn bộ logic sinh dữ liệu nền** — mọi bảng (customers, accounts, transactions...) đều có 1 hàm `g_<tên_bảng>()` ở đây. Cũng chứa cấu hình chung (`M` = schema mọi bảng, `CFG`, `BASE`, các hàm tiện ích `dt/h/nm/read/write`). File `01_*.py`...`27_*.py` bên dưới CHỈ gọi vào đây. |
| `generators/01_simulation_runs.py` … `27_fraud_ground_truth.py` | **Không phải logic riêng** — mỗi file chỉ là 2 dòng gọi `gen('<tên_bảng>')` từ `engine.py`, dùng để **chạy debug 1 bảng đơn lẻ** khi cần (vd `python generators/08_transactions.py` chỉ sinh lại bảng transactions). Không được `run_all_v2.py` import — an toàn để bỏ qua khi đọc code. |
| `generators/recompute_balances.py` | **Mới thêm.** Hậu xử lý: sort transaction theo thời gian thực trong từng account, chain lại `balance_before`/`balance_after` cho nhất quán — chạy sau khi cả dữ liệu nền lẫn kịch bản đã tồn tại. |
| `scenario_engine.py` | Tiêm 20 kịch bản gian lận (TXN-01..10, LOAN-01..10) + `collect_background_hard_negatives()` (mới thêm — gán ground truth `false_positive_seed` cho các bản ghi mule/synthetic nền không thuộc kịch bản nào). Ghi ra `output/scenario_manifest.csv` — bảng truy vết event → entity chính → rule kỳ vọng. |
| `rebuild_features.py` | Tính lại `transaction_features` (velocity 10 phút/1 giờ/24 giờ, khoảng cách tới lần đổi thông tin nhạy cảm gần nhất...) bằng cửa sổ thời gian thực đúng nghĩa, chạy sau khi scenario đã tiêm xong. Đây là bản feature dùng thật; hàm `g_transaction_features` trong `engine.py` là bản cũ/yếu, không được gọi trong V2. |
| `build_operations_v2.py` | Đọc `scenario_manifest.csv`, build `rules`, `decision_outcomes`, `rule_hits`, `alerts`, `cases`, `verification_results`, `fraud_ground_truth` — **nguồn ground truth chính thức** của dữ liệu V2 (ghi đè hoàn toàn lên các bảng cùng tên do `engine.py` sinh nháp). |
| `verify_data.py` | Kiểm tra: header/PK/FK cơ bản, DPD logic, đủ 20 kịch bản, **+ mới thêm**: timeline causality (session/beneficiary), balance chain continuity, decision entity_type consistency, ground truth có false-positive không. |
| `config.json` | Tham số sinh dữ liệu: `customer_count`, `random_seed`, `scenario_counts` (số lượng mỗi kịch bản — cơ chế **duy nhất** quyết định số lượng fraud thật, không phải `*_rate`), `loan_fraud_rate` (chỉ quyết định số customer bị seed "synthetic identity" ở tầng nền), `clean_false_positive_count` (cap số lượng hard-negative lấy vào ground truth, mới được wire lại — trước đây tồn tại nhưng không nơi nào đọc). |

### Output
`output/*.csv` — 27 bảng theo schema `fraud_sim` (xem tên cột đầy đủ trong `M` dict ở đầu `engine.py`), cộng `scenario_manifest.csv` (metadata kiểm thử, không thuộc schema Postgres, không import vào DB).

### Import PostgreSQL (không bắt buộc cho luồng Data Science)
```bash
cd sql
psql -U postgres -d <database> -f import_csv.sql
```

## Đã sửa gần đây (2026-08-28, theo review timeline/balance/ground-truth)

- Timeline: transaction trước session login **7,291 → 0**; sau session kết thúc 7,235 → 78; trước beneficiary 677 → 146.
- Balance chain gãy: **12,148/13,315 → 0**.
- Ground truth: thêm 12 bản ghi `false_positive_seed` (trước đó 0).
- TXN-03: `entity_type` sửa từ `transaction` (sai) sang `account` (đúng).
- Chi tiết root cause + cách sửa: xem lịch sử review trong phiên làm việc, không lặp lại ở đây.
