# AGENTS.md — Codex Operating Guide for SAS-FRAUD

> Handbook để AI/Codex làm việc chính xác, hiệu quả và nhất quán trong repository SAS-FRAUD.
>
> Đây là file chỉ dẫn ở repository root. Codex tự động nạp các quy tắc này cho toàn bộ repository, trừ khi một thư mục con có `AGENTS.md` với chỉ dẫn cụ thể hơn.

---

## 1. Mục tiêu làm việc

Tối ưu cho kết quả đúng, kiểm chứng được và có thể tiếp tục sử dụng, không tối ưu cho số lượng câu chữ hay số lượng thao tác.

Mỗi task cần xác định:

- Outcome người dùng thực sự cần.
- Scope file/hệ thống được phép tác động.
- Success criteria có thể kiểm tra.
- Nguồn bằng chứng đáng tin cậy.
- Artifact hoặc câu trả lời cuối cùng phải bàn giao.

Ưu tiên prompt/instruction gọn, nói mỗi quy tắc một lần. Không lặp hướng dẫn ở nhiều tài liệu nếu có thể dẫn tới một source of truth.

---

## 2. Thứ tự ưu tiên chỉ dẫn

Áp dụng theo thứ tự:

1. System/developer instructions của phiên làm việc.
2. Yêu cầu trực tiếp mới nhất của người dùng.
3. `AGENTS.md` gần file đang sửa nhất nếu sau này được tạo.
4. Data contract và project playbook trong repo.
5. Convention hiện có của code xung quanh.

Nếu chỉ dẫn mâu thuẫn, không âm thầm chọn. Nêu xung đột khi nó ảnh hưởng outcome hoặc cần quyền quyết định của người dùng.

---

## 3. Source of truth của repository

Đọc đúng nguồn theo task, không nạp toàn repo theo thói quen.

| Task | Nguồn ưu tiên |
|---|---|
| Business scope/EDA/model | `docs/business_domain.md` |
| Notebook convention | `docs/SKILLS.md` |
| Raw transaction contract | `fraud_data_generator_v2/RAW_TRANSACTION_DATASET.md` |
| Row counts/run metadata | `fraud_data_generator_v2/output_training_raw/merged/dataset_manifest.json` |
| Generator configuration | `fraud_data_generator_v2/config_training_transaction.json` |
| Generator pipeline | `run_training_raw.py`, `run_all_v2.py` |
| Scenario/label logic | `scenario_engine.py` |
| Existing transaction feature | `rebuild_features.py` |
| Schema/FK/type | `database/schema/` |
| SAS live mapping | `database/schema/Mapping_Generator_Fields.md` |
| App/backend behavior | Code và test gần component trong `app/` |

Code, manifest và output thực tế có ưu tiên cao hơn tài liệu mô tả cũ khi chúng không khớp. Khi phát hiện lệch, báo rõ và cập nhật tài liệu nếu task cho phép.

---

## 4. Working contract

### 4.1. Trước khi hành động

- Đọc yêu cầu và phân loại: giải thích, review, diagnose, sửa, xây mới hay research.
- Với task chỉ hỏi/diagnose, không tự ý sửa file.
- Với task yêu cầu thay đổi, kiểm tra file liên quan và trạng thái Git trước khi edit.
- Dùng `rg`/`rg --files` để tìm nhanh; chỉ đọc phần cần thiết.
- Không hỏi lại nếu có thể suy ra an toàn từ code, schema hoặc tài liệu hiện có.
- Hỏi khi lựa chọn còn thiếu sẽ làm thay đổi đáng kể outcome, dữ liệu hoặc kiến trúc.

### 4.2. Trong khi làm

- Bắt đầu bằng outcome, không kể dài dòng về quá trình.
- Giữ thay đổi nhỏ, đúng scope và dễ review.
- Tái sử dụng helper/module hiện có trước khi tạo abstraction mới.
- Bảo toàn thay đổi không liên quan của người dùng.
- Với task dài, cập nhật tiến độ ngắn gọn theo milestone.
- Khi có assumption quan trọng, ghi rõ assumption và bằng chứng.

### 4.3. Trước khi kết thúc

- Kiểm tra artifact tồn tại và nội dung đúng yêu cầu.
- Chạy verification tỷ lệ thuận với rủi ro.
- Xem diff/status để phát hiện thay đổi ngoài scope.
- Tóm tắt: outcome, file thay đổi, test/check đã chạy, giới hạn còn lại.
- Không tuyên bố “đã xong” nếu chưa kiểm chứng success criteria.

---

## 5. Quy tắc trả lời

- Trả lời trực tiếp câu hỏi trước.
- Mặc định ngắn gọn; mở rộng khi task phức tạp hoặc người dùng yêu cầu.
- Dùng tiếng Việt rõ ràng, giữ tên field/code bằng tiếng Anh.
- Không nhắc lại toàn bộ yêu cầu của người dùng.
- Không dùng quá nhiều heading/bullet cho câu hỏi đơn giản.
- Phân biệt fact, inference và recommendation.
- Khi dùng web, đặt citation ngay cạnh claim được hỗ trợ.
- Khi nhắc file local, dùng đường dẫn clickable và line phù hợp nếu hữu ích.
- Không che giấu blocker, warning, test chưa chạy hoặc dữ liệu chưa đủ.

Mẫu handoff cho task thay đổi:

```text
Đã hoàn thành <outcome> tại <file>.
Đã kiểm tra: <test/check>.
Lưu ý còn lại: <nếu có>.
```

---

## 6. Planning và task dài

Không lập plan cho câu hỏi hoặc edit đơn giản.

Dùng plan/ExecPlan khi task:

- Kéo dài qua nhiều component hoặc notebook.
- Có migration/refactor lớn.
- Có nhiều dependency hoặc acceptance criteria.
- Cần người dùng review hướng đi trước khi triển khai.

Plan phải là living document: cập nhật trạng thái, quyết định, phát hiện và kết quả kiểm chứng. Chia thay đổi lớn thành các stage coherent, reviewable; không tạo một diff khổng lồ nếu có thể hoàn thành theo lát cắt nhỏ.

---

## 7. Repository-specific data invariants

### 7.1. Scope ML hiện tại

- Domain: Transaction Fraud.
- Grain: một transaction tại `transaction_at=T`.
- Dataset: 5 simulation runs merged theo bảng raw.
- Loan tables ngoài scope training hiện tại.

### 7.2. Label

- Gán label qua `scenario_event_entities.csv`.
- `label_scope=fraud` → `target_fraud=1`.
- `label_scope=hard_negative` → `target_fraud=0`, `hard_negative=1`.
- Không có transaction bridge row → background negative theo contract hiện tại.
- `context_only`, đặc biệt TXN-03 account-level, không là transaction positive.
- Không suy label từ `_SCN_`, ID pattern, rule hit hoặc operational outcome.
- Dùng `sample_weight` để event nhiều transaction không chi phối loss.

### 7.3. Leakage và point-in-time

- Feature tại T chỉ dùng record có timestamp `< T`, trừ current-event field được định nghĩa rõ.
- Không dùng future transaction, full-history aggregate hoặc post-decision outcome.
- Không dùng ID, scenario/event metadata, ground truth, alert/case/verification, risk score hậu nghiệm hay `scenario_hint` làm feature.
- Split theo customer/account; assert intersection giữa train/validation/test bằng 0.
- Fit imputer, encoder, scaler, resampler và selector chỉ trên train.

### 7.4. Join

- Bắt đầu từ `transactions`.
- Assert row count sau từng join.
- Aggregate bảng 1:N như auth/change events trước khi join.
- Mang `simulation_run_id` trong key/audit để tránh join nhầm giữa run.

---

## 8. Notebook standard

Tuân thủ đầy đủ `docs/SKILLS.md`. Tối thiểu:

- Mỗi notebook có title, mục tiêu/input/output và Table of Contents.
- Mỗi logical code cell có Markdown giải thích ngay trước.
- Không trộn trách nhiệm business, data quality, EDA, feature engineering và modeling nếu đã có notebook riêng.
- Code dùng lại từ hai notebook trở lên đưa vào `notebooks/src/`.
- Chart/dashboard dùng design system trong `notebooks/src/viz_utils.py`.
- Mỗi EDA visual trả lời business question và có observation/“so what?”.
- EDA phải đủ sâu để kể câu chuyện dữ liệu, nhưng mỗi chart phải cung cấp bằng chứng mới.
- Notebook phải chạy từ trên xuống trong kernel sạch.

---

## 9. Coding và file changes

- Python target: 3.11.
- Tôn trọng formatter/linter/test hiện có trong repo.
- Dùng `apply_patch` cho edit thủ công có kiểm soát.
- Không sửa generated CSV/output để “chữa” logic; sửa generator hoặc preprocessing source.
- Không hard-code path tuyệt đối, token, password, connection string hoặc PII.
- Không commit data thật, local token, cache, executed notebook hoặc generated figure không cần thiết.
- Với thay đổi API/schema, cập nhật caller, docs và test liên quan trong cùng task.
- Không tạo helper mới nếu helper hiện có giải quyết được.
- Không đổi tên/move/delete file lớn khi chưa xác định caller và tác động.

---

## 10. Verification ladder

Chọn mức kiểm tra nhỏ nhất nhưng đủ bằng chứng:

| Thay đổi | Verification tối thiểu |
|---|---|
| Markdown/docs | Đọc lại section, kiểm tra link/path, `git diff` |
| Python helper | Import/compile + test trực tiếp function thay đổi |
| Generator | Chạy run phù hợp + `verify_data.py` + manifest/label checks |
| Notebook | Execute từ kernel sạch hoặc ít nhất parse + run relevant cells |
| Data join/feature | Row-count, PK/FK, point-in-time và leakage assertions |
| Model | Entity-safe split, baseline, scenario recall, hard-negative FPR |
| Backend/API | Targeted pytest + request/response contract |
| Schema/migration | Syntax/apply test trên môi trường an toàn + rollback consideration |

Không chạy test suite rộng hoặc tác động hệ thống ngoài khi targeted verification đã đủ, trừ khi thay đổi nằm ở shared/core behavior.

---

## 11. Safety và quyền hạn

- Không xóa/reset/overwrite dữ liệu hoặc Git state nếu người dùng chưa yêu cầu rõ.
- Kiểm tra target tuyệt đối trước thao tác recursive/move/delete.
- Không expose secret trong log, tool output hoặc câu trả lời.
- Không gọi API/DB production, publish, deploy hoặc gửi message nếu task chỉ yêu cầu review/diagnose.
- Nếu command quan trọng bị sandbox/network chặn, yêu cầu approval đúng scope; không lách quyền.
- Giữ thao tác external có thể review, retry có giới hạn và có stopping condition.

---

## 12. Skills và progressive disclosure

- Chỉ dùng skill khi task khớp trigger/description.
- `SKILL.md` giữ workflow cốt lõi ngắn; chi tiết theo mode để trong `references/`.
- Script dành cho thao tác lặp lại hoặc cần tính xác định.
- Không tạo skill cho lời khuyên generic hoặc task chỉ xuất hiện một lần.
- Tránh skill chồng lấn; ưu tiên cải thiện skill hiện có.
- Skill mới phải có trigger rõ, procedure có thể thực hiện và verification cụ thể.
- Validate skill trước khi đưa vào sử dụng.

Project playbook `docs/SKILLS.md` là quy ước chung. Các Codex skill thực tế phải được đóng gói riêng bằng `SKILL.md` với YAML frontmatter.

---

## 13. Definition of Done

Task chỉ hoàn thành khi:

- Outcome khớp yêu cầu mới nhất.
- Không có thay đổi ngoài scope chưa giải thích.
- File/code/data contract liên quan nhất quán.
- Verification phù hợp đã pass hoặc failure được báo rõ.
- Không tạo leakage, secret exposure hoặc destructive side effect.
- Người tiếp theo có thể hiểu artifact và bước tiếp theo mà không cần đọc lại toàn hội thoại.

---

## 14. Nguồn OpenAI/Codex đã tham khảo

### Repository chính thức

- [`openai/codex`](https://github.com/openai/codex): nguồn về `AGENTS.md`, instruction scope, repository workflow và targeted verification.
- [`openai/openai-cookbook`](https://github.com/openai/openai-cookbook): ExecPlan cho task dài và các workflow Codex có thể tái sử dụng.
- [`openai/plugins`](https://github.com/openai/plugins): nguồn hiện hành cho plugin/skill examples.
- [`openai/skills`](https://github.com/openai/skills): catalog cũ; repository tự ghi đã deprecated, chỉ dùng để tham khảo lịch sử và chuyển sang `openai/plugins` cho ví dụ mới.

### Nguyên tắc được tổng hợp

- `AGENTS.md` có scope theo directory tree; file sâu hơn ưu tiên trong scope của nó.
- Instruction nên cụ thể cho repo, không nhồi generic knowledge.
- Prompt lean, outcome-first, có success criteria và stopping condition.
- Task lớn dùng living plan; task nhỏ không cần process nặng.
- Verify targeted theo component trước khi chạy kiểm tra rộng.
- Skill phải chuyên biệt, ngắn và dùng progressive disclosure.
- Giữ context bounded: đọc đúng nguồn, không đưa artifact lớn không cần thiết vào context.

Các nguồn này cung cấp pattern; quy tắc nghiệp vụ SAS-FRAUD trong các mục trên vẫn lấy từ code và tài liệu nội bộ của repository.
