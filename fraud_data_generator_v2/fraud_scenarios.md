# Blueprint: 20 Kịch bản Gian lận cho Data Generator
### Phác thảo bởi: Góc nhìn Phân tích Rủi ro Ngân hàng

> Tài liệu này mô tả chi tiết 20 kịch bản gian lận (10 Transaction + 10 Loan),
> sắp xếp từ **Cơ bản** (1 rule đơn lẻ, dễ code) đến **Phức tạp** (chuỗi hành vi đa bảng, nhiều rule phối hợp).
> Mỗi kịch bản ghi rõ bối cảnh thực tế, luồng dữ liệu cần sinh, và rule kỳ vọng SAS sẽ kích hoạt.

---

# 🏦 MẢNG 1: TRANSACTION FRAUD (Gian lận Giao dịch)

## CƠ BẢN (Single-Rule / Dấu hiệu đơn lẻ)

---

### TXN-01: Impossible Travel (Di chuyển phi lý)
**Bối cảnh thực tế:** Khách hàng đăng nhập ở Hà Nội lúc 10:00, rồi 15 phút sau lại đăng nhập ở TP.HCM. Không ai có thể bay 1,700km trong 15 phút. Đây là dấu hiệu rõ ràng nhất cho thấy thông tin đăng nhập đã bị đánh cắp.

**Luồng dữ liệu cần sinh:**

| Thời gian | Bảng | Hành động |
|---|---|---|
| T+00 | `login_sessions` | Session 1: `province='Hà Nội'`, `latitude=21.03`, `longitude=105.85`, `login_result='success'` |
| T+15m | `login_sessions` | Session 2: `province='TP.HCM'`, `latitude=10.82`, `longitude=106.63`, `login_result='success'`, `is_new_location=True` |
| T+16m | `transactions` | Chuyển tiền từ Session 2, số tiền trung bình |

**Trường trigger:**
- Khoảng cách tọa độ Session 1 vs Session 2 > 500km
- Chênh lệch thời gian < 2 giờ
- `is_new_location = True`

**Rule kỳ vọng:** `R_TXN_GEO_001` — Impossible Travel Detection

---

### TXN-02: Dormant Account Awakening (Tài khoản "ngủ đông" bất ngờ hoạt động)
**Bối cảnh thực tế:** Tài khoản 2 năm không giao dịch. Chủ tài khoản thường là người già hoặc sinh viên đã quên. Hacker dò được thông tin đăng nhập qua các vụ rò rỉ dữ liệu (Data Breach) trên Dark Web.

**Luồng dữ liệu cần sinh:**

| Thời gian | Bảng | Hành động |
|---|---|---|
| (Sẵn có) | `accounts` | `status='dormant'`, `dormant_since` = 2 năm trước |
| T+00 | `login_sessions` | Đăng nhập từ `is_new_device=True`, IP lạ |
| T+05m | `transactions` | Chuyển tiền đi, số tiền lớn |

**Trường trigger:**
- `accounts.status = 'dormant'`
- `login_sessions.is_new_device = True`
- Khoảng cách thời gian từ `dormant_since` đến `transaction_at` quá lớn

**Rule kỳ vọng:** `R_TXN_DORMANT_001` — Dormant Account Reactivation Anomaly

---

### TXN-03: Brute Force Authentication (Dò mật khẩu)
**Bối cảnh thực tế:** Hacker dùng tool tự động thử hàng loạt mật khẩu phổ biến (123456, password, ngày sinh...) cho đến khi trúng. Thường xảy ra vào ban đêm khi chủ tài khoản đang ngủ.

**Luồng dữ liệu cần sinh:**

| Thời gian | Bảng | Hành động |
|---|---|---|
| T+00 (2:00 AM) | `auth_events` | `auth_result='failed'`, `failed_attempt_count=1` |
| T+10s | `auth_events` | `auth_result='failed'`, `failed_attempt_count=2` |
| T+20s | `auth_events` | `auth_result='failed'`, `failed_attempt_count=3` |
| T+30s | `auth_events` | `auth_result='success'`, `failed_attempt_count=3`, `auth_risk_score=95` |

**Trường trigger:**
- `failed_attempt_count >= 3`
- `auth_risk_score > 90`
- Thời gian giữa các lần thử rất ngắn (< 1 phút)
- Xảy ra lúc nửa đêm (Unusual hour)

**Rule kỳ vọng:** `R_TXN_AUTH_001` — Brute Force / Credential Stuffing

---

### TXN-04: Velocity Burst (Rút tiền cấp tốc)
**Bối cảnh thực tế:** Sau khi chiếm được tài khoản, hacker biết rằng thời gian là vàng. Chúng sẽ tạo ra nhiều giao dịch nhỏ liên tục (mỗi giao dịch dưới hạn mức cảnh báo) để rút sạch tiền trong vài phút trước khi hệ thống phát hiện.

**Luồng dữ liệu cần sinh:**

| Thời gian | Bảng | Hành động |
|---|---|---|
| T+00 | `transactions` | Chuyển 4,900,000 VND (ngay dưới ngưỡng 5 triệu) |
| T+01m | `transactions` | Chuyển 4,800,000 VND |
| T+02m | `transactions` | Chuyển 4,950,000 VND |
| T+03m | `transactions` | Chuyển 4,700,000 VND |
| T+04m | `transactions` | Chuyển 4,850,000 VND |

**Trường trigger:**
- `transaction_features.txn_count_10m >= 5`
- `txn_amount_sum_24h` tăng vọt so với bình thường
- Tất cả giao dịch đều ngay dưới một ngưỡng cố định (Structuring / Smurfing)

**Rule kỳ vọng:** `R_TXN_VEL_001` — High Frequency / Velocity Anomaly

---

### TXN-05: New Beneficiary Rapid Transfer (Thêm người nhận rồi chuyển ngay)
**Bối cảnh thực tế:** Khách hàng bị cuộc gọi lừa đảo (Giả danh công an / Giả danh ngân hàng). Kẻ lừa đảo hướng dẫn nạn nhân thêm số tài khoản lạ vào danh bạ rồi chuyển tiền ngay lập tức "để bảo vệ tài sản". Đặc trưng: Thiết bị sạch, IP quen, nhưng hành vi bất thường.

**Luồng dữ liệu cần sinh:**

| Thời gian | Bảng | Hành động |
|---|---|---|
| T+00 | `login_sessions` | Đăng nhập từ thiết bị quen (`is_new_device=False`), IP quen |
| T+01m | `beneficiaries` | Thêm tài khoản thụ hưởng mới, `is_internal_bank=False` |
| T+02m | `transactions` | Chuyển số tiền rất lớn (gần `single_txn_limit`) cho thụ hưởng mới |

**Trường trigger:**
- `transaction_features.is_new_beneficiary = True`
- `time_since_beneficiary_added_minutes < 5`
- `amount` gần sát `single_txn_limit`

**Rule kỳ vọng:** `R_TXN_SCAM_001` — Rapid Transfer to New Beneficiary

---

## PHỨC TẠP (Multi-Rule / Chuỗi hành vi)

---

### TXN-06: Full Account Takeover Chain (Chiếm đoạt tài khoản toàn diện)
**Bối cảnh thực tế:** Đây là kịch bản hoàn chỉnh nhất mà hacker chuyên nghiệp sử dụng. Chúng thực hiện một chuỗi hành động logic: Đăng nhập → Vô hiệu hóa bảo mật → Nâng hạn mức → Cài tài khoản mồi → Rút tiền → Xóa dấu vết. Mỗi bước đơn lẻ có thể không đủ để trigger alert, nhưng khi nối chuỗi lại thì rõ ràng là tấn công.

**Luồng dữ liệu cần sinh:**

| Thời gian | Bảng | Hành động | Ghi chú |
|---|---|---|---|
| T+00 | `login_sessions` | IP lạ, thiết bị mới, VPN bật | Entry point |
| T+02m | `auth_events` | `auth_method='sms_otp'`, `auth_result='success'` | Lừa được OTP |
| T+04m | `account_change_events` | `change_type='password'` | Khóa chủ TK thật |
| T+06m | `account_change_events` | `change_type='phone'` | Chuyển OTP sang máy hacker |
| T+08m | `account_change_events` | `change_type='transfer_limit'` | Nâng hạn mức lên max |
| T+10m | `beneficiaries` | Thêm TK thụ hưởng mới | Cài tài khoản mồi |
| T+12m | `transactions` | Chuyển 90% số dư | Rút tiền |
| T+13m | `beneficiaries` | `status='removed'` | Xóa dấu vết |

**Trường trigger (Tổ hợp):**
- `is_new_device + is_new_location + vpn_flag = True` (Session rủi ro cao)
- 3 `account_change_events` liên tiếp trong 10 phút (`is_sensitive_change = True`)
- `time_since_sensitive_change_minutes < 15`
- `time_since_beneficiary_added_minutes < 5`
- Beneficiary bị xóa ngay sau giao dịch

**Rules kỳ vọng (Chuỗi):** `R_TXN_ATO_001` + `R_TXN_VEL_001` + `R_TXN_SCAM_001`

---

### TXN-07: Money Mule Network (Đường dây rửa tiền có tổ chức)
**Bối cảnh thực tế:** Đường dây cờ bạc online hoặc lừa đảo đầu tư. Nạn nhân chuyển tiền vào các tài khoản "Chim mồi" (Mule) do sinh viên/công nhân mở thuê. Tiền vào Mule rồi được chia nhỏ chuyển tiếp đến các tài khoản khác để rửa sạch (Layering).

**Luồng dữ liệu cần sinh:**

| Giai đoạn | Bảng | Hành động |
|---|---|---|
| Chuẩn bị | `customers` | Tạo 3 Mule (`is_mule_candidate_seed=True`), mỗi người 1 `accounts` |
| Chuẩn bị | `beneficiaries` | Cả 3 Mule đăng ký lẫn nhau làm thụ hưởng, chung `mule_cluster_id='RING_01'` |
| Giai đoạn 1 | `transactions` | 5 nạn nhân khác nhau chuyển tiền lớn vào Mule A |
| Giai đoạn 2 | `transactions` | Mule A chia nhỏ, chuyển sang Mule B và Mule C |
| Giai đoạn 3 | `transactions` | Mule B, C rút tiền mặt (`transaction_type='cash_withdrawal'`) |

**Trường trigger (Tổ hợp):**
- `mule_cluster_id` không rỗng
- `beneficiary_risk_level = 'High'`
- Nhiều `customer_id` khác nhau chuyển tiền vào cùng 1 `account_id` (Fan-in pattern)
- Sau khi nhận tiền, tài khoản Mule lập tức chuyển đi hoặc rút (Fan-out pattern)
- `accounts.open_date` rất mới (TK mở chưa lâu)

**Rules kỳ vọng:** `R_TXN_MULE_001` + `R_TXN_VEL_001`

---

### TXN-08: Emulator + Proxy Bot Farm (Tấn công bằng Bot hàng loạt)
**Bối cảnh thực tế:** Hacker dùng phần mềm giả lập Android (Android Emulator) kết hợp Proxy xoay (Rotating Proxy) để thử đăng nhập hàng loạt tài khoản. Mỗi lần thử, Emulator giả dạng một "thiết bị" khác nhau, Proxy đổi IP khác nhau. Mục tiêu: Dò tìm các tài khoản có mật khẩu yếu.

**Luồng dữ liệu cần sinh:**

| Thời gian | Bảng | Hành động |
|---|---|---|
| T+00 → T+30m | `devices` | Tạo 10 thiết bị giả: tất cả `is_emulator=True`, `is_rooted_or_jailbroken=True`, `device_risk_score > 90` |
| T+00 → T+30m | `login_sessions` | 10 lần đăng nhập vào 10 tài khoản khác nhau, mỗi lần từ 1 device khác nhau, `proxy_flag=True` |
| (Subset) | `auth_events` | 8/10 lần `auth_result='failed'`, 2 lần `auth_result='success'` |
| Ngay sau | `transactions` | 2 tài khoản bị dò trúng: chuyển tiền đi ngay |

**Trường trigger:**
- `devices.is_emulator = True` + `is_rooted_or_jailbroken = True`
- `login_sessions.proxy_flag = True`
- Nhiều `account_id` khác nhau bị đăng nhập từ cùng 1 `device_fingerprint` (hoặc cùng subnet IP)
- `device_risk_score > 90`

**Rules kỳ vọng:** `R_TXN_AUTH_001` + `R_TXN_ATO_001` + Device Risk Rule

---

### TXN-09: Internal Collusion — Rogue Employee (Nhân viên nội gián rút tiền khách)
**Bối cảnh thực tế:** Nhân viên ngân hàng làm việc tại quầy (Branch) lợi dụng quyền truy cập nội bộ để chuyển tiền từ tài khoản của khách hàng vãng lai (không dùng Mobile Banking) sang tài khoản cá nhân. Khách hàng chỉ phát hiện khi nhận sổ phụ cuối tháng.

**Luồng dữ liệu cần sinh:**

| Thời gian | Bảng | Hành động |
|---|---|---|
| T+00 | `login_sessions` | `auth_method='internal_token'`, `device_type='internal_terminal'`, `province` khớp chi nhánh |
| T+02m | `transactions` | `channel='branch'`, `direction='DEBIT'`, chuyển sang `counterparty_internal_account_id` (TK nội bộ của nhân viên) |
| T+05m | `transactions` | TK nhận tiền lập tức chuyển ra ngoài (`direction='DEBIT'`, `channel='mobile'`, `is_internal_bank=False`) |

**Trường trigger:**
- `channel = 'branch'` + giao dịch vào TK nội bộ
- TK nhận là nhân viên ngân hàng (có thể check `counterparty_internal_account_id`)
- Sau khi nhận, tiền lập tức chuyển ra ngoài hệ thống
- Giao dịch xảy ra ngoài giờ làm việc hoặc cuối ngày

**Rules kỳ vọng:** `R_TXN_INTERNAL_001` — Internal Fund Diversion + `R_TXN_VEL_001`

---

### TXN-10: SIM Swap + Takeover (Chiếm SIM → Chiếm tài khoản)
**Bối cảnh thực tế:** Kẻ gian làm giả giấy tờ lên cửa hàng viễn thông xin cấp lại SIM điện thoại của nạn nhân. Khi SIM mới được kích hoạt, SIM cũ mất sóng. Kẻ gian dùng SIM mới nhận OTP và chiếm toàn bộ tài khoản ngân hàng. Đây là loại tấn công nguy hiểm nhất vì nạn nhân không biết cho đến khi thấy điện thoại mất sóng.

**Luồng dữ liệu cần sinh:**

| Thời gian | Bảng | Hành động |
|---|---|---|
| T-24h | `login_sessions` | Chủ TK thật: Đăng nhập bình thường từ thiết bị quen, IP quen |
| T+00 (SIM bị swap) | `account_change_events` | `change_type='phone'`, `verification_method='sms_otp'`, `channel='mobile'`, nhưng `device_id` là thiết bị MỚI |
| T+02m | `account_change_events` | `change_type='trusted_device'` — Đăng ký Smart OTP trên thiết bị mới |
| T+05m | `account_change_events` | `change_type='transfer_limit'` — Nâng hạn mức |
| T+08m | `beneficiaries` | Thêm TK thụ hưởng lạ |
| T+10m | `transactions` | Chuyển toàn bộ số dư. `amount ≈ balance_before` |
| T+11m | `beneficiaries` | `status='removed'` |

**Trường trigger (Tổ hợp):**
- `change_type='phone'` thực hiện từ `device_id` chưa từng thấy
- Ngay sau đổi SĐT: đổi `trusted_device` + nâng `transfer_limit` (3 sensitive changes liên tiếp)
- `time_since_sensitive_change_minutes < 15` tại thời điểm chuyển tiền
- `amount / balance_before > 0.8` (Rút gần hết)

**Rules kỳ vọng:** `R_TXN_ATO_001` + `R_TXN_SCAM_001` + `R_TXN_VEL_001`

---

# 🏦 MẢNG 2: LOAN FRAUD (Gian lận Khoản vay)

## CƠ BẢN (Single-Rule / Dấu hiệu đơn lẻ)

---

### LOAN-01: Income Inflation (Khai khống thu nhập)
**Bối cảnh thực tế:** Đây là loại gian lận phổ biến nhất ở Việt Nam. Khách hàng hoặc Sale Agent tự ý nâng số lương khai báo lên gấp 3-5 lần thực tế để đủ điều kiện vay số tiền mong muốn. Thường kèm theo Sao kê lương giả.

**Luồng dữ liệu cần sinh:**

| Bảng | Trường | Giá trị gian lận |
|---|---|---|
| `customers` | `income_band` | `'<5M'` (Sự thật ngân hàng nắm) |
| `employment_income_profiles` | `declared_monthly_income` | `65,000,000` (Khai vống x13 lần) |
| `employment_income_profiles` | `income_document_type` | `'payslip'` |
| `application_documents` | `tamper_score` | `85` (Sao kê lương bị chỉnh sửa) |

**Trường trigger:**
- Chênh lệch `income_band` vs `declared_monthly_income` quá lớn
- `tamper_score > 70`

**Rule kỳ vọng:** `R_LOAN_DOC_001` — Document Tampering / Income Mismatch

---

### LOAN-02: Loan Stacking (Vay chồng chéo)
**Bối cảnh thực tế:** Khách hàng đang ôm 5-6 khoản nợ ở nhiều tổ chức, đi vay thêm khoản mới để xoay vòng trả nợ cũ (kiểu Ponzi cá nhân). Sớm hay muộn cũng vỡ nợ.

**Luồng dữ liệu cần sinh:**

| Bảng | Trường | Giá trị gian lận |
|---|---|---|
| `credit_bureau_snapshots` | `active_loan_count` | `6` |
| `credit_bureau_snapshots` | `recent_inquiry_count` | `12` (Bị 12 tổ chức khác tra soát trong 3 tháng) |
| `credit_bureau_snapshots` | `dpd_max_12m` | `45` (Đã từng chậm trả 45 ngày) |
| `credit_bureau_snapshots` | `bureau_score` | `380` (Điểm CIC rất thấp) |

**Trường trigger:**
- `active_loan_count >= 5`
- `recent_inquiry_count >= 8`
- `dpd_max_12m > 30`

**Rule kỳ vọng:** `R_LOAN_CIC_001` — Loan Stacking / Over-indebtedness

---

### LOAN-03: Ghost Employer (Công ty ma)
**Bối cảnh thực tế:** Khách hàng khai tên công ty, nhưng khi gọi số điện thoại công ty để xác minh thì: (a) Số này là số di động cá nhân chứ không phải đường dây văn phòng, (b) Người nhấc máy nói vu vơ không biết gì, hoặc (c) Số này đã được dùng làm "SĐT công ty" cho 20 hồ sơ vay khác nhau.

**Luồng dữ liệu cần sinh:**

| Bảng | Trường | Giá trị gian lận |
|---|---|---|
| `employment_income_profiles` | `employer_phone_verification_status` | `'suspicious'` |
| `employment_income_profiles` | `is_employer_phone_reused` | `True` |
| `employment_income_profiles` | `employer_phone_cluster_id` | Chung mã với nhiều hồ sơ khác (VD: `'EPH_GHOST_01'`) |

**Trường trigger:**
- `employer_phone_verification_status IN ('suspicious', 'unreachable', 'mismatch')`
- `is_employer_phone_reused = True`
- `employer_phone_cluster_id` xuất hiện ở >= 5 hồ sơ khác nhau

**Rule kỳ vọng:** `R_LOAN_EMP_001` — Ghost Employer / Phone Reuse

---

### LOAN-04: Reference Recycling (Tái sử dụng người tham chiếu)
**Bối cảnh thực tế:** Đường dây làm hồ sơ giả chỉ có 2-3 số điện thoại "đóng vai" người tham chiếu cho hàng chục hồ sơ. Khi thẩm định viên gọi, có người nhấc máy xác nhận ngọt ngào, nhưng thực chất đó là "diễn viên" do đường dây thuê.

**Luồng dữ liệu cần sinh:**

| Bảng | Trường | Giá trị gian lận |
|---|---|---|
| `reference_contacts` | `reference_phone_hash` | Gán cùng 1 hash cho 8 hồ sơ khác nhau |
| `reference_contacts` | `phone_reuse_count` | `8` |
| `reference_contacts` | `reference_quality_score` | `25` |
| `reference_contacts` | `verification_status` | `'suspicious'` |

**Trường trigger:**
- `phone_reuse_count >= 5`
- `reference_quality_score < 40`

**Rule kỳ vọng:** `R_LOAN_REF_001` — Reference Phone Reuse / Collusion Ring

---

### LOAN-05: Expired / Mismatched ID Documents (Giấy tờ hết hạn hoặc không khớp)
**Bối cảnh thực tế:** Khách hàng nộp mặt trước CCCD của mình, nhưng mặt sau lại là CCCD của người khác (lấy nhầm hoặc cố tình ghép). Hoặc CCCD đã hết hạn sử dụng.

**Luồng dữ liệu cần sinh:**

| Bảng | Trường | Giá trị gian lận |
|---|---|---|
| `application_documents` (id_card_front) | `ocr_quality_score` | `90` (Ảnh rõ) |
| `application_documents` (id_card_back) | `id_front_back_match_flag` | `False` (Mặt trước và sau KHÔNG khớp) |
| `application_documents` (id_card_front) | `id_expired_flag` | `True` |
| `application_documents` (selfie) | `face_match_score` | `0.45` (Khuôn mặt selfie không khớp ảnh trên CCCD) |
| `application_documents` (selfie) | `liveness_result` | `'fail'` (Dùng ảnh in hoặc Deepfake) |

**Trường trigger:**
- `id_front_back_match_flag = False`
- `id_expired_flag = True`
- `face_match_score < 0.6`
- `liveness_result = 'fail'`

**Rule kỳ vọng:** `R_LOAN_DOC_001` — Document Integrity Failure

---

## PHỨC TẠP (Multi-Rule / Chuỗi hành vi)

---

### LOAN-06: Synthetic Identity Farm (Xưởng danh tính ma)
**Bối cảnh thực tế:** Tổ chức tội phạm tạo ra 5-10 danh tính nhân tạo (tên giả, số CCCD ăn cắp từ trẻ em/người già), tất cả đều khai cùng một "công ty ma", cùng khu vực, cùng mức lương. Chúng nộp hồ sơ đồng loạt trong thời gian ngắn để "xả" trước khi bị phát hiện.

**Luồng dữ liệu cần sinh:**

| Bảng | Trường | Đặc điểm |
|---|---|---|
| `customers` (x5) | `is_synthetic_identity_seed` | `True` |
| `loan_applications` (x5) | `application_at` | 5 hồ sơ nộp trong cùng 1 tuần |
| `loan_applications` (x5) | `is_emulator`, `is_vpn` | `True` (Nộp từ Emulator qua VPN) |
| `applicant_declared_profiles` (x5) | `profile_similarity_cluster_id` | Cùng mã `'SYN_FARM_01'` |
| `applicant_declared_profiles` (x5) | `address_quality_score` | `20 - 30` (Địa chỉ ma) |
| `applicant_declared_profiles` (x5) | `declared_phone_hash` | Khác với `customers.phone_hash` |
| `employment_income_profiles` (x5) | `employer_phone_cluster_id` | Chung mã `'EPH_GHOST_01'` |
| `credit_bureau_snapshots` (x5) | `bureau_match_result` | `'partial_match'` hoặc `'no_hit'` (CIC không nhận diện được) |

**Trường trigger (Tổ hợp):**
- `profile_similarity_cluster_id` xuất hiện >= 3 lần
- `address_quality_score < 40`
- `declared_phone_hash ≠ customers.phone_hash`
- `employer_phone_cluster_id` trùng nhau
- `bureau_match_result = 'partial_match'`
- `is_emulator = True`

**Rules kỳ vọng:** `R_LOAN_SYN_001` + `R_LOAN_EMP_001` + `R_LOAN_DOC_001`

---

### LOAN-07: Sales Agent Collusion (Nhân viên tín dụng câu kết)
**Bối cảnh thực tế:** 1 nhân viên Sale đẩy số lượng hồ sơ bất thường trong tháng, hầu hết khách hàng đều có chung đặc điểm: Giấy tờ mờ, SĐT công ty trùng, thu nhập khai giống nhau. Sale này hoặc là "xào" hồ sơ để đạt KPI, hoặc đang câu kết với đường dây làm giả.

**Luồng dữ liệu cần sinh:**

| Bảng | Trường | Đặc điểm |
|---|---|---|
| `loan_applications` (x10) | `sales_agent_id` | Cùng 1 Agent |
| `loan_applications` (x10) | Khoảng `application_at` | Dồn trong 1 tháng (bất thường so với `monthly_application_baseline`) |
| `application_documents` | `face_match_score` | Nhiều hồ sơ có score thấp (0.5 - 0.65) |
| `employment_income_profiles` | `employer_phone_hash` | 6/10 hồ sơ chung 1 SĐT công ty |
| `reference_contacts` | `reference_phone_hash` | 4/10 hồ sơ chung người tham chiếu |

**Trường trigger:**
- Số hồ sơ Agent nộp / tháng > 3x `monthly_application_baseline`
- Tỷ lệ `face_match_score < 0.7` trong hồ sơ của Agent > 30%
- `employer_phone_hash` hoặc `reference_phone_hash` bị trùng lặp bất thường

**Rules kỳ vọng:** `R_LOAN_AGENT_001` — Agent Anomaly + `R_LOAN_EMP_001` + `R_LOAN_REF_001`

---

### LOAN-08: Shared Disbursement Ring (Giải ngân gom về một mối)
**Bối cảnh thực tế:** 3 người lạ nộp hồ sơ độc lập, mọi thông tin đều sạch, hồ sơ được duyệt. Nhưng đến bước cuối cùng (Giải ngân), cả 3 đều yêu cầu chuyển tiền vào cùng 1 số tài khoản. Đây là dấu hiệu chắc chắn rằng cả 3 hồ sơ do 1 "ông trùm" điều khiển.

**Luồng dữ liệu cần sinh:**

| Bảng | Trường | Đặc điểm |
|---|---|---|
| `loan_applications` (x3) | `customer_id` | 3 khách hàng khác nhau |
| `loan_applications` (x3) | `application_status` | `'disbursed'` (Đã được duyệt) |
| `disbursement_accounts` (x3) | `receiving_account_hash` | **Cùng 1 mã hash** |
| `disbursement_accounts` (x3) | `same_as_applicant` | `False` |
| `disbursement_accounts` (x3) | `account_reuse_count` | `3` |
| `disbursement_accounts` (x3) | `receiving_account_name` | Khác tên người vay |

**Trường trigger (Tổ hợp):**
- `account_reuse_count >= 2`
- `same_as_applicant = False` (Tên người nhận ≠ Tên người vay)
- `receiving_account_hash` xuất hiện ở >= 2 hồ sơ khác nhau

**Rules kỳ vọng:** `R_LOAN_DIS_001` — Shared Disbursement / Third-party Account

---

### LOAN-09: First-Party Bust-Out (Vay chủ đích để bùng nợ)
**Bối cảnh thực tế:** Khách hàng "nuôi" profile tín dụng đẹp trong 2 năm (trả nợ đúng hạn, tăng hạn mức dần). Khi đã được tin tưởng, họ vay một cú lớn cuối cùng rồi biến mất. Đây là loại khó bắt nhất vì lúc duyệt hồ sơ mọi thứ đều hoàn hảo — chỉ phát hiện được ở giai đoạn hậu kiểm (Post-disbursement).

**Luồng dữ liệu cần sinh:**

| Giai đoạn | Bảng | Đặc điểm |
|---|---|---|
| Duyệt | `credit_bureau_snapshots` | `bureau_score = 780`, `dpd_max_12m = 0`, `thin_file_flag = False` (Hồ sơ cực đẹp) |
| Duyệt | `applicant_declared_profiles` | Thông tin khớp 100% với `customers` |
| Duyệt | `application_documents` | `tamper_score < 10`, `face_match_score = 0.98` (Giấy tờ sạch sẽ) |
| Duyệt | `loan_applications` | `application_status = 'disbursed'`, `loan_amount` = số tiền lớn nhất cho phép |
| Hậu kiểm | `loan_repayment_outcomes` | `first_payment_status = 'missed'` |
| Hậu kiểm | `loan_repayment_outcomes` | `dpd_30_flag = True`, `dpd_60_flag = True`, `dpd_90_flag = True` |
| Hậu kiểm | `loan_repayment_outcomes` | `contact_status_after_disbursement = 'lost_contact'` (Tắt máy, mất liên lạc) |
| Hậu kiểm | `loan_repayment_outcomes` | `early_default_flag = True`, `fraud_outcome_label = 'confirmed_fraud'` |

**Trường trigger:**
- `early_default_flag = True` + `contact_status = 'lost_contact'`
- `loan_amount` ở mức cao nhất trong lịch sử của khách hàng
- Trước đó từng vay nhiều khoản nhỏ và trả đúng hạn (Pattern: Escalating loan amounts)

**Rules kỳ vọng:** `R_LOAN_BUSTOUT_001` — First-Party Bust-Out (Post-disbursement ML model)

---

### LOAN-10: Full Fraud Ring — Tổng lực (Danh tính ma + Sale nội gián + Giấy tờ giả + Giải ngân gom)
**Bối cảnh thực tế:** Đường dây tổ chức bài bản nhất. Có người chuyên làm giấy tờ giả, có nhân viên Sale "nội gián" trong ngân hàng giúp đẩy hồ sơ qua vòng duyệt, có người chuyên mở tài khoản mồi nhận tiền giải ngân. Tất cả phối hợp nhịp nhàng.

**Luồng dữ liệu cần sinh:**

| Vai trò | Bảng | Đặc điểm |
|---|---|---|
| **Ông trùm** | `customers` (x5) | `is_synthetic_identity_seed=True`, cùng `address_cluster_id` |
| **Sale nội gián** | `loan_applications` (x5) | Cùng 1 `sales_agent_id`, nộp dồn trong 2 tuần |
| **Xưởng giấy tờ** | `application_documents` | `document_hash` trùng nhau (Dùng lại template), `tamper_score > 80` |
| **Xưởng giấy tờ** | `application_documents` (selfie) | `liveness_result='fail'`, `face_match_score < 0.5` |
| **Công ty ma** | `employment_income_profiles` (x5) | Cùng `employer_phone_cluster_id`, `is_employer_phone_reused=True` |
| **Diễn viên đóng vai** | `reference_contacts` (x5) | Cùng `reference_phone_hash`, `phone_reuse_count >= 5` |
| **Profile giả** | `applicant_declared_profiles` (x5) | Cùng `profile_similarity_cluster_id`, `address_quality_score < 30` |
| **TK mồi nhận tiền** | `disbursement_accounts` (x5) | Cùng `receiving_account_hash`, `same_as_applicant=False`, `account_reuse_count=5` |
| **Bùng nợ** | `loan_repayment_outcomes` (x5) | `first_payment_status='missed'`, `early_default_flag=True`, `contact_status='lost_contact'` |

**Trường trigger (Tất cả đồng thời):**
- `profile_similarity_cluster_id` trùng (Cluster danh tính)
- `employer_phone_cluster_id` trùng (Công ty ma)
- `reference_phone_hash` trùng (Diễn viên tham chiếu)
- `document_hash` trùng (Xưởng giấy tờ)
- `receiving_account_hash` trùng (TK mồi)
- `sales_agent_id` dồn bất thường (Sale nội gián)
- `address_quality_score < 30` + `is_emulator = True`

**Rules kỳ vọng (Toàn bộ hệ thống):** `R_LOAN_SYN_001` + `R_LOAN_DOC_001` + `R_LOAN_EMP_001` + `R_LOAN_REF_001` + `R_LOAN_DIS_001` + `R_LOAN_AGENT_001`

> [!IMPORTANT]
> Kịch bản LOAN-10 là "Boss cuối" của Generator. Nếu SAS bắt được kịch bản này trọn vẹn, 
> đó là bằng chứng sắc bén nhất cho sếp thấy hệ thống hoạt động end-to-end.

---

## 📊 Tổng hợp: Bảng ánh xạ Kịch bản → Rule → Bảng dữ liệu

| Mã | Kịch bản | Mức độ | Rules chính | Bảng dữ liệu chính |
|---|---|---|---|---|
| TXN-01 | Impossible Travel | Cơ bản | GEO | `login_sessions` |
| TXN-02 | Dormant Awakening | Cơ bản | DORMANT | `accounts`, `login_sessions` |
| TXN-03 | Brute Force | Cơ bản | AUTH | `auth_events` |
| TXN-04 | Velocity Burst | Cơ bản | VEL | `transactions`, `transaction_features` |
| TXN-05 | New Bene Rapid Transfer | Cơ bản | SCAM | `beneficiaries`, `transactions` |
| TXN-06 | Full ATO Chain | Phức tạp | ATO+VEL+SCAM | 6 bảng (session→change→bene→txn) |
| TXN-07 | Mule Network | Phức tạp | MULE+VEL | `beneficiaries`, `transactions` |
| TXN-08 | Bot Farm | Phức tạp | AUTH+ATO+DEV | `devices`, `login_sessions`, `auth_events` |
| TXN-09 | Rogue Employee | Phức tạp | INTERNAL+VEL | `transactions` (branch channel) |
| TXN-10 | SIM Swap + ATO | Phức tạp | ATO+SCAM+VEL | `account_change_events`, `transactions` |
| LOAN-01 | Income Inflation | Cơ bản | DOC | `employment_income_profiles`, `application_documents` |
| LOAN-02 | Loan Stacking | Cơ bản | CIC | `credit_bureau_snapshots` |
| LOAN-03 | Ghost Employer | Cơ bản | EMP | `employment_income_profiles` |
| LOAN-04 | Reference Recycling | Cơ bản | REF | `reference_contacts` |
| LOAN-05 | ID Mismatch | Cơ bản | DOC | `application_documents` |
| LOAN-06 | Synthetic Farm | Phức tạp | SYN+EMP+DOC | 4 bảng (profiles+employment+docs+CIC) |
| LOAN-07 | Agent Collusion | Phức tạp | AGENT+EMP+REF | `loan_applications`, `employment`, `reference` |
| LOAN-08 | Shared Disbursement | Phức tạp | DIS | `disbursement_accounts` |
| LOAN-09 | First-Party Bust-Out | Phức tạp | BUSTOUT (ML) | `loan_repayment_outcomes` |
| LOAN-10 | Full Fraud Ring | Phức tạp | TẤT CẢ | Toàn bộ bảng Loan |

---

## 🛠 Gợi ý tỷ lệ trộn khi viết Generator

```python
# Ví dụ config cho 1000 khách hàng
SCENARIO_MIX = {
    # === 85% Clean Data (Không có fraud) ===
    'LEGITIMATE':           0.85,
    
    # === 15% Fraud Seeds (Tổng cộng) ===
    # Transaction Fraud (8%)
    'TXN_01_IMPOSSIBLE':    0.01,
    'TXN_02_DORMANT':       0.01,
    'TXN_03_BRUTE_FORCE':   0.01,
    'TXN_04_VELOCITY':      0.01,
    'TXN_05_NEW_BENE':      0.01,
    'TXN_06_FULL_ATO':      0.01,
    'TXN_07_MULE_RING':     0.01,
    'TXN_08_BOT_FARM':      0.005,
    'TXN_09_ROGUE_EMP':     0.005,
    'TXN_10_SIM_SWAP':      0.005,
    
    # Loan Fraud (7%)
    'LOAN_01_INCOME':       0.01,
    'LOAN_02_STACKING':     0.01,
    'LOAN_03_GHOST_EMP':    0.01,
    'LOAN_04_REF_REUSE':    0.01,
    'LOAN_05_ID_MISMATCH':  0.005,
    'LOAN_06_SYN_FARM':     0.01,
    'LOAN_07_AGENT':        0.005,
    'LOAN_08_SHARED_DISB':  0.005,
    'LOAN_09_BUSTOUT':      0.005,
    'LOAN_10_FULL_RING':    0.005,
}
```
