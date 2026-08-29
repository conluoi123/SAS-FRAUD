# SKILLS.md — SAS-FRAUD Data Science Playbook

> Quy ước làm việc cho notebook, EDA, preprocessing, modeling và trực quan hóa trong repo SAS-FRAUD.
>
> File này là **project playbook**. Nó không thay thế data contract trong `fraud_data_generator_v2/RAW_TRANSACTION_DATASET.md` hay business scope trong `docs/business_domain.md`.

---

## 1. Phạm vi hiện tại

- Domain: Transaction Fraud.
- Grain ML: một transaction tại `transaction_at=T`.
- Label source: `scenario_event_entities.csv`.
- Population: background normal, confirmed fraud và hard-negative.
- Split: theo customer/account; không random theo row.
- Feature lịch sử: chỉ dùng dữ liệu có timestamp `< T`.

Các notebook không được tự thay đổi grain, label policy hoặc split policy mà không ghi rõ lý do trong phần đầu notebook.

---

## 2. Notebook Contract — bắt buộc

### 2.1. Table of Contents

Mọi notebook phải có **Table of Contents** ngay sau title và phần mô tả mục tiêu.

Mẫu tối thiểu:

```markdown
# 02 — Exploratory Data Analysis

> Mục tiêu: ...
> Input: ...
> Output: ...

## Table of Contents

1. [Mục tiêu và câu hỏi](#1-mục-tiêu-và-câu-hỏi)
2. [Chuẩn bị dữ liệu](#2-chuẩn-bị-dữ-liệu)
3. [Phân tích](#3-phân-tích)
4. [Kết luận](#4-kết-luận)
```

Quy tắc:

- TOC phải phản ánh đúng các section thực tế.
- Cập nhật TOC khi thêm, xóa hoặc đổi tên section.
- Không liệt kê từng cell nhỏ; chỉ liệt kê section có ý nghĩa.
- Notebook ngắn vẫn phải có TOC để các notebook đồng nhất.

### 2.2. Markdown trước mỗi code cell

Trong mọi notebook có code, **mỗi logical code cell phải có một Markdown cell ngay trước nó** để giải thích code sắp làm gì.

Markdown nên trả lời ngắn gọn:

- **Mục tiêu:** kiểm tra/tính toán gì?
- **Input:** dùng dataframe/bảng/cột nào?
- **Output hoặc check:** mong đợi bảng, metric, chart hay assertion nào?

Mẫu:

```markdown
### Kiểm tra tính duy nhất của khóa giao dịch

Đếm `transaction_id` trùng trong bảng transaction. Kết quả mong đợi là 0; nếu khác 0 thì dừng bước join feature.
```

Không cần lặp đủ ba nhãn `Mục tiêu/Input/Output` khi một đoạn văn ngắn đã diễn đạt rõ. Không đặt nhiều code cell liên tiếp mà không có Markdown giải thích ở giữa; nếu chúng cùng một mục đích, gộp code vào một logical cell.

Ngoại lệ duy nhất: notebook hoàn toàn Markdown như `00_business_rule.ipynb` không cần code cell giả.

### 2.3. Cấu trúc đầu notebook

Thứ tự chuẩn:

1. Title.
2. Mục tiêu, input và output của notebook.
3. Table of Contents.
4. Assumptions/data contract liên quan.
5. Environment/setup code cell, có Markdown mô tả trước.
6. Nội dung phân tích.
7. Kết luận và handoff sang notebook tiếp theo.

### 2.4. Ranh giới giữa các notebook

| Notebook | Trách nhiệm chính | Không nên làm |
|---|---|---|
| `00_business_rule` | Business scope, scenario, label policy, boundary | EDA sâu, preprocessing, model training |
| `01_data_quality` | Schema, type, missing, duplicate, FK, grain, timeline, leakage checks | Tối ưu model |
| `02_eda` | Business-question-driven EDA và insight | Fit preprocessing/model trên toàn data |
| `03_feature_engineering` | Point-in-time features và feature registry | Dùng future data/label metadata |
| `04_preprocessing_split` | Entity-safe split, imputer, encoder, scaler | Fit transform trước split |
| `05_modeling` | Baseline, model comparison, tuning | Chọn threshold chỉ bằng accuracy |
| `06_evaluation` | Threshold, scenario recall, hard-negative FPR, error analysis | Đưa test feedback ngược vào training |
| `07_sas_handoff` | Final feature mapping và serving contract | Thêm feature không có production source |

Tên notebook có thể thay đổi, nhưng boundary phải được giữ.

---

## 3. Quy chuẩn dùng `notebooks/src`

### 3.1. Mục đích

Logic dùng lại từ hai notebook trở lên phải chuyển vào `notebooks/src/`, đặc biệt:

- Design tokens và chart formatting.
- Hàm load/validate dữ liệu dùng chung.
- Feature transformation đã ổn định.
- Metric/report helper.

Notebook giữ narrative, business question, tham số phân tích và kết quả; không copy-paste một khối helper dài qua nhiều notebook.

### 3.2. Visualization bắt buộc dùng design system

Trước khi vẽ chart/dashboard, import và gọi `setup()` đúng một lần:

```python
from pathlib import Path
import sys

repo_root = Path.cwd()
src_dir = repo_root / "notebooks" / "src"
if not src_dir.exists():
    src_dir = repo_root / "src"
sys.path.insert(0, str(src_dir.resolve()))

from viz_utils import *
setup()
```

Sau đó:

- Dùng `PALETTE`/`COLORS_SEQ`; không tự tạo palette khác trong từng notebook.
- Dùng `section()` cho section header trực quan khi notebook có output code.
- Dùng `kpi_cards()` cho summary KPI.
- Dùng `bar_chart()`, `line_chart()`, `pareto_chart()` khi phù hợp.
- Với chart tùy chỉnh, dùng `clean_ax()`/`clean_spines()` và formatter trong `viz_utils.py`.
- Dùng `save_fig()` khi chart là artifact cần tái sử dụng.
- Không đặt màu đỏ/xanh tùy tiện: đỏ/danger cho fraud/risk/error, xanh/stable cho normal/pass, accent cho hard-negative/warning.

Nếu helper hiện tại chưa hỗ trợ chart cần thiết, mở rộng `notebooks/src/viz_utils.py` thay vì tạo style riêng trong notebook.

### 3.3. Dashboard/figure multi-panel

Dashboard hoặc figure tổng hợp phải:

- Có KPI summary ở đầu.
- Có title/subtitle nêu câu hỏi nghiệp vụ.
- Dùng cùng font, spacing, palette và number formatter.
- Không nhồi quá nhiều chart; mỗi panel phải trả lời một câu hỏi.
- Có insight ngắn ngay sau visual quan trọng.
- Phân biệt rõ fraud, hard-negative và background normal.

### 3.4. Quy tắc visual trong EDA

Mỗi visual phải đi theo luồng:

```text
Business question → Visual/check → Observation → So what?
```

Không vẽ chart chỉ vì có cột dữ liệu. Nếu table diễn đạt rõ hơn chart thì dùng table.

---

## 4. Data và label invariants

- Dùng `scenario_event_entities.csv` để gán nhãn; không suy label từ `_SCN_` hoặc ID pattern.
- `label_scope=fraud` → `target_fraud=1`.
- `label_scope=hard_negative` → `target_fraud=0`, `hard_negative=1`.
- Không có transaction bridge row → background negative theo data contract hiện tại.
- `context_only`, đặc biệt TXN-03 account-level, không được map thành transaction positive.
- Dùng `sample_weight` để một multi-row event không lấn át event một dòng.
- Sau mỗi join, assert grain và row count; không chấp nhận row multiplication âm thầm.

---

## 5. Data Quality standard

Mỗi check phải có:

1. Tên invariant.
2. Giá trị thực tế.
3. Expected threshold/condition.
4. Trạng thái PASS/WARN/FAIL.
5. Hành động xử lý nếu không PASS.

Nhóm check tối thiểu:

- Schema, dtype và required columns.
- PK uniqueness và FK coverage.
- Missing theo ý nghĩa: not-applicable, no-history, unknown.
- Join cardinality/grain.
- Timeline causality.
- Balance continuity khi liên quan.
- Label bridge integrity.
- Cross-run distribution stability.
- Constant/near-constant columns.
- Leakage/shortcut audit.

Output cần có một Data Quality Issues Log:

| Check | Table/column | Actual | Expected | Status | Action |
|---|---|---:|---:|---|---|

---

## 6. EDA standard

EDA phải so sánh ba population:

```text
confirmed fraud vs hard-negative vs background normal
```

Nhóm phân tích tối thiểu:

- Target và scenario distribution.
- Distribution theo 5 simulation run.
- Numeric/categorical/time distribution.
- Missing pattern theo population.
- Account/customer/device/beneficiary behavior.
- Sequence và network pattern.
- Generator shortcut và scenario template audit.

Mỗi section bắt đầu bằng business question và kết thúc bằng insight/hành động tiếp theo.

---

## 7. Feature engineering và preprocessing

- Mọi rolling/aggregate feature tại T chỉ dùng record có timestamp `< T`.
- Ghi công thức, window, entity key, missing policy và production source cho mỗi feature.
- Không one-hot raw ID/hash.
- Không dùng scenario, event, role, scope, operational decision hoặc ground-truth field làm feature.
- Không dùng `features.scenario_hint`.
- Split theo customer/account trước khi fit imputer, encoder, scaler hoặc feature selector.
- Chạy ablation với generator-provided risk score/new-device-like signals để đo shortcut dependence.

Feature registry tối thiểu:

| Feature | Công thức | Window | Entity | Missing | SAS source dự kiến |
|---|---|---|---|---|---|

---

## 8. Modeling và evaluation

- Baseline dễ giải thích trước: rule, Logistic Regression, Decision Tree.
- Sau đó mới so sánh tree ensemble/boosting nếu cần.
- Không dùng accuracy làm metric chính cho fraud.
- Báo cáo PR-AUC, precision, recall, F1, confusion matrix và ROC-AUC bổ trợ.
- Báo cáo recall theo từng TXN scenario.
- Báo cáo hard-negative FPR riêng.
- Báo cáo metric tại threshold vận hành: FPR hoặc alerts/1.000 transaction cố định.
- Tách entity an toàn; assert không giao customer/account giữa train/validation/test.
- Resampling/class weight chỉ áp dụng trên training partition.
- Test set không được dùng để chọn feature, model hoặc threshold.

---

## 9. Output và reproducibility

Mỗi notebook kết thúc bằng:

- Tóm tắt phát hiện chính.
- Assumption/limitation còn mở.
- Artifact được tạo và đường dẫn.
- Handoff rõ cho notebook kế tiếp.

Notebook phải chạy được từ trên xuống dưới trong kernel sạch. Tránh phụ thuộc vào biến được tạo thủ công từ lần chạy trước.

Code ổn định và dùng lại nên ở `notebooks/src`; notebook chỉ orchestration và narrative.

---

## 10. `viz_utils.py` quick reference

| Function | Công dụng |
|---|---|
| `setup()` | Áp dụng style chung; gọi một lần đầu notebook |
| `section(title, subtitle)` | Section header đồng bộ |
| `kpi_cards(cards)` | KPI cards HTML |
| `kpi_card_mpl(ax, ...)` | KPI card trong matplotlib figure |
| `bar_chart(...)` | Bar chart chuẩn |
| `line_chart(...)` | Time-series/multi-series line chart |
| `pareto_chart(...)` | Pareto 80/20 |
| `clean_ax(...)` | Chuẩn hóa custom axes |
| `clean_spines(ax)` | Chuẩn hóa border/ticks |
| `label_bars_v/h(ax)` | Gắn nhãn bar |
| `fmt_pct`, `fmt_currency`, `fmt_num` | Formatter chuẩn |
| `quick_profile(df)` | Profile dataframe nhanh |
| `save_fig(fig, name)` | Lưu figure vào thư mục chung |
| `export_dashboard_json(data)` | Export dữ liệu dashboard web |

---

## 11. Skill roadmap từ GitHub research

Các repo dưới đây chỉ là nguồn tham khảo kỹ thuật. Chưa clone code, chưa cài dependency và chưa đưa nguyên repo bên ngoài vào project.

| Skill nên tách sau | Nguồn tham khảo | Giá trị cho SAS-FRAUD |
|---|---|---|
| `fraud-notebook-authoring` | Jupytext, nbdime, nbval | Notebook text pairing, diff/merge rõ, execute/validate tự động |
| `fraud-data-contract` | Pandera | Schema/type/range/strict column checks có thể tái sử dụng |
| `fraud-project-structure` | Cookiecutter Data Science | Tách data/notebook/src/model/report có quy ước |
| `fraud-imbalanced-modeling` | imbalanced-learn | Resampling/pipeline/metrics cho target lệch lớp |
| `fraud-drift-monitoring` | Evidently | Cross-run drift, data quality và model monitoring report |

Nguồn:

- <https://github.com/drivendataorg/cookiecutter-data-science>
- <https://github.com/mwouts/jupytext>
- <https://github.com/jupyter/nbdime>
- <https://github.com/computationalmodelling/nbval>
- <https://github.com/unionai-oss/pandera>
- <https://github.com/scikit-learn-contrib/imbalanced-learn>
- <https://github.com/evidentlyai/evidently>

Ưu tiên tạo skill theo thứ tự:

1. `fraud-data-contract` cho `01_data_quality.ipynb`.
2. `fraud-notebook-authoring` để kiểm tra TOC, Markdown-before-code và clean execution.
3. `fraud-imbalanced-modeling` trước giai đoạn modeling.
4. `fraud-drift-monitoring` khi có model output hoặc dữ liệu production/reference.

Mỗi skill thực tế phải được đóng gói riêng bằng `SKILL.md`, có description rõ lúc nào kích hoạt, chỉ thêm script/reference khi thật sự tái sử dụng, và phải validate trước khi dùng.
