# SAS-FRAUD

## Tổng quan

SAS-FRAUD là dự án mô phỏng/triển khai quy trình phân tích và phát hiện gian lận giao dịch, tập trung vào:

- Khám phá dữ liệu và kiểm tra chất lượng dữ liệu giao dịch.
- Xây dựng business rules cho fraud decisioning.
- Chuẩn bị nền tảng cho backend, frontend, database và notebook phân tích.
- Tạo môi trường Python 3.11 nhất quán để phát triển, thử nghiệm và demo.

## Cấu trúc thư mục

```text
SAS-FRAUD/
├── app/
│   ├── backend/          # API/backend service
│   └── frontend/         # UI/demo frontend
├── data/                 # Dữ liệu cục bộ, không commit dữ liệu thật
├── database/
│   ├── migrations/       # Migration scripts
│   ├── queries/          # SQL queries
│   ├── schema/           # Database schema
│   └── seed/             # Seed/sample data scripts
├── docs/                 # Tài liệu nghiệp vụ/kỹ thuật
├── notebooks/            # Notebook phân tích và thử nghiệm rule
├── .env.example          # Mẫu biến môi trường
├── .gitignore
├── README.md
└── requirements.txt
```

## Yêu cầu môi trường

- Python `3.11`
- Git
- Khuyến nghị dùng virtual environment để cô lập dependency.

Kiểm tra phiên bản Python:

```bash
python --version
```

Nếu máy có nhiều phiên bản Python, dùng:

```bash
py -3.11 --version
```

## Cài đặt

### 1. Clone hoặc mở repository

```bash
cd SAS-FRAUD
```

### 2. Tạo virtual environment

Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

### 3. Cài đặt dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Cấu hình biến môi trường

```bash
cp .env.example .env
```

Trên Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Cập nhật giá trị trong `.env` theo môi trường local/dev nếu cần.

## Chạy notebook

```bash
jupyter lab
```

Notebook hiện có:

- `notebooks/00_business_rule.ipynb`: thử nghiệm logic business rule.
- `notebooks/01_data_quality.ipynb`: kiểm tra chất lượng dữ liệu.

## Quy ước dữ liệu

- Không commit dữ liệu nhạy cảm, dữ liệu khách hàng thật hoặc file dump lớn.
- Đặt dữ liệu local trong `data/raw/`, `data/interim/`, `data/processed/` hoặc `data/external/`.
- Nếu cần dữ liệu mẫu để demo, dùng dữ liệu đã ẩn danh và ghi rõ nguồn trong `docs/`.

## Kiểm tra chất lượng code

Chạy test:

```bash
pytest
```

Format code:

```bash
black .
```

Lint code:

```bash
ruff check .
```

## Gợi ý workflow phát triển

1. Tạo branch riêng cho từng tính năng hoặc thử nghiệm.
2. Cập nhật notebook/rule theo yêu cầu nghiệp vụ.
3. Chuẩn hóa logic có thể tái sử dụng vào `app/backend/`.
4. Thêm migration/schema khi thay đổi database.
5. Chạy test/lint trước khi merge.

## Ghi chú bảo mật

Dự án liên quan đến fraud decisioning nên cần đặc biệt lưu ý:

- Không hard-code secret, connection string hoặc credential.
- Không đưa dữ liệu giao dịch thật lên repository.
- Log cần được masking nếu có thông tin định danh hoặc thông tin tài chính.
- Rule/model phục vụ quyết định gian lận cần có khả năng giải thích và audit.
