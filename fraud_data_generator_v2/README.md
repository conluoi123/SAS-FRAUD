# Fraud Simulation CSV Generator

Bộ sinh dữ liệu cho 27 bảng trong schema `fraud_sim`.

## Chạy

```bash
python run_all_v2.py
python verify_data.py
```

CSV được tạo trong `output/`.

Để sinh bộ raw transaction đa bảng cho EDA → join → feature → model:

```powershell
python run_training_raw.py
```

Kết quả nằm trong `output_training_raw/merged/`: vẫn là các bảng raw riêng biệt,
không join sẵn và không chia train/validation/test. Mỗi lần chạy dùng nhiều seed độc lập;
`dataset_manifest.json` ghi lại seed, run và số dòng từng bảng.
Xem `RAW_TRANSACTION_DATASET.md` để biết grain, join key, label mapping và cột cần loại
khỏi feature nhằm tránh leakage.

## Import PostgreSQL

Chạy DDL schema trước, sau đó từ thư mục `sql/`:

```bash
psql -U postgres -d <database> -f import_csv.sql
```

## Quy mô mặc định

- 1.000 khách hàng
- Khoảng 1.250 tài khoản
- Khoảng 15.000 giao dịch
- Khoảng 350 hồ sơ vay
- Fraud hiếm nhưng có chủ đích để bao phủ ATO, mule, high-value/velocity, impossible travel, synthetic identity, document fraud, CIC velocity, shared disbursement, early default và false positive.

## Cấu trúc

- `generators/01_...py` đến `27_...py`: mỗi bảng một file Python riêng.
- `generators/engine.py`: hàm dùng chung và logic sinh dữ liệu.
- `run_all.py`: entry point V1 legacy, không dùng cho model dataset mới.
- `run_all_v2.py`: pipeline chính có scenario injection, feature rebuild và ground truth.
- `scenario_event_entities.csv`: bridge event-to-entity để gán nhãn mọi transaction
  primary/supporting mà không suy từ pattern ID; có `target_fraud`, `hard_negative`
  và `sample_weight` cân bằng theo event.
- `run_training_raw.py`: sinh nhiều run độc lập rồi ghép dọc từng bảng raw; không tạo
  data mart đã join.
- `verify_data.py`: kiểm tra đủ cột, PK, FK cốt lõi, run ID và một số business constraint.
- `sql/import_csv.sql`: import CSV theo đúng thứ tự khóa ngoại.
- `sql/truncate_all.sql`: xóa dữ liệu demo an toàn bằng CASCADE.
