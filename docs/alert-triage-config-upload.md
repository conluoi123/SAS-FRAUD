# Huong dan upload cau hinh SAS Alert Triage

Tai lieu nay mo ta quy trinh dong goi va import lai cau hinh SAS Alert Triage sau khi chinh sua cac file export. Quy trinh da duoc kiem thu tren moi truong lab `https://viya.sas.env`.

## 1. Pham vi

Quy trinh bao gom:

1. Luu ban backup.
2. Kiem tra cau truc candidate.
3. Dong goi candidate thanh ZIP.
4. Lay OAuth access token.
5. Upload ZIP vao Alert Triage.
6. Doc ket qua import.
7. Kiem tra giao dien va rollback khi can.

Import cau hinh khong phai la thao tac upload trong man hinh Administration. Endpoint REST duoc su dung la:

```text
POST https://viya.sas.env/alerts/config
```

## 2. Dieu kien truoc khi import

- Tai khoan SAS co capability `triage.alert.import_config`.
- May co PowerShell va `curl.exe`.
- Candidate nam trong thu muc rieng, khong sua truc tiep backup.
- Cac file JSON da duoc validate.
- Da co ban export goc de rollback.

Trong lan trien khai CNP, cac thu muc duoc su dung la:

```text
D:\Thuc tap\HPT\SAS-FRAUD\export
D:\Thuc tap\HPT\SAS-FRAUD\alerts-config-working-cnp
```

Thu muc `export` la backup goc. Thu muc `alerts-config-working-cnp` la candidate da chinh sua.

## 3. Cau truc ZIP bat buoc

Tai cap cao nhat cua ZIP phai co truc tiep cac thanh phan sau:

```text
alerts-config/
alerts-transaction-config/
capabilities/
identities/
config_definitions.gojson
```

Khong duoc de ZIP bi long them mot thu muc goc:

```text
alerts-config-working-cnp/
    alerts-config/
    alerts-transaction-config/
```

## 4. Dong goi candidate

Mo PowerShell va chuyen den repository:

```powershell
cd "D:\Thực tập\HPT\SAS-FRAUD"
```

Tao file ZIP:

```powershell
Compress-Archive -Path ".\alerts-config-working-cnp\*" -DestinationPath ".\cnp-alert-page-import.zip" -CompressionLevel Optimal -Force
```

Kiem tra file da ton tai:

```powershell
Test-Path ".\cnp-alert-page-import.zip"
```

Ket qua phai la:

```text
True
```

## 5. Lay OAuth access token

Khong su dung Basic Auth truc tiep voi endpoint `/alerts/config`. Cach do se tra ve `401 Full authentication is required`.

Khai bao username:

```powershell
$user = "viya-admin"
```

Nhap mat khau an trong terminal:

```powershell
$securePass = Read-Host "Nhap mat khau SAS Viya" -AsSecureString
```

Khi nhap, PowerShell khong hien ky tu mat khau. Nhap xong thi nhan Enter.

Chuyen mat khau thanh gia tri tam de gui den SAS Logon:

```powershell
$pass = [System.Net.NetworkCredential]::new("", $securePass).Password
```

Lay OAuth token. Nen dan nguyen lenh mot dong de tranh loi dau backtick, dau gach cheo hoac URL Markdown:

```powershell
$tokenResponse = curl.exe -k -sS -X POST "https://viya.sas.env/SASLogon/oauth/token" -u "sas.cli:" -H "Content-Type: application/x-www-form-urlencoded" --data-urlencode "grant_type=password" --data-urlencode "username=$user" --data-urlencode "password=$pass"
```

Doc response:

```powershell
$tokenObject = $tokenResponse | ConvertFrom-Json
$tokenObject | Select-Object token_type, expires_in, error, error_description
```

Ket qua thanh cong co dang:

```text
token_type expires_in error error_description
---------- ---------- ----- -----------------
bearer           3599
```

Luu access token vao bien ma khong in token ra terminal:

```powershell
$token = $tokenObject.access_token
```

Kiem tra bien token:

```powershell
if ([string]::IsNullOrWhiteSpace($token)) { "TOKEN_MISSING" } else { "TOKEN_READY" }
```

Chi tiep tuc khi ket qua la `TOKEN_READY`.

## 6. Upload cau hinh

Chay lenh sau tren mot dong:

```powershell
$importResponse = curl.exe -k -sS -X POST "https://viya.sas.env/alerts/config" -H "Authorization: Bearer $token" -H "Content-Type: application/zip" --data-binary "@cnp-alert-page-import.zip" -w "`nHTTP_STATUS=%{http_code}`n"
```

Khong in `$token` hoac `$tokenResponse` ra man hinh. `$importResponse` khong chua access token va co the dung de debug.

## 7. Phan tich ket qua

Tach JSON khoi dong HTTP status:

```powershell
$json = (($importResponse | Where-Object { $_ -notmatch "^HTTP_STATUS=" }) -join "`n")
$result = $json | ConvertFrom-Json
```

Xem tong quan:

```powershell
$result | Select-Object totalNumResourcesCreatedOrUpdated, configurationComplete, httpStatusCode
```

Import chi duoc xem la hoan thanh khi:

```text
configurationComplete : True
httpStatusCode         : 200
```

Kiem tra cac thanh phan khong thanh cong:

```powershell
$result.configurationResults | Where-Object status -ne "success" | Select-Object path, status, error
```

Lenh nay khong duoc tra ve muc `failure` hoac `skipped`.

Co the luu toan bo response de phan tich:

```powershell
($importResponse -join "`n") | Set-Content -LiteralPath ".\cnp-import-response.txt" -Encoding UTF8
```

## 8. Xu ly loi thuong gap

### 8.1 HTTP 401

Vi du:

```json
{
  "httpStatusCode": 401,
  "message": "Full authentication is required to access this resource"
}
```

Nguyen nhan thuong gap:

- Dang su dung Basic Auth truc tiep thay vi Bearer token.
- Token bi rong.
- Token da het han.

Khac phuc: lay token moi tu `/SASLogon/oauth/token`, sau do gui header:

```text
Authorization: Bearer <access-token>
```

### 8.2 HTTP 403

Token hop le nhung tai khoan khong co capability `triage.alert.import_config`. Can kiem tra role/group cua tai khoan voi quan tri vien SAS.

### 8.3 HTTP 400 va cac muc `skipped`

Khong retry ngay. Luu toan bo response va tim muc `failure` dau tien. Cac muc `skipped` chi la nhung file phia sau chua duoc xu ly, khong phai nguyen nhan goc.

Import co the thanh cong mot phan. Vi du trong lan import CNP dau tien:

- Page definitions: `success`.
- Enrichment fields/mappings: `success`.
- Component definitions: `success`.
- Transaction grid definitions: `failure`.
- Cac transaction config phia sau: `skipped`.

Nguyen nhan cua grid CNP la cau hinh moi thieu `transactionTypeIds`. Trong export cua moi truong, tat ca 13 grid co san deu co thuoc tinh nay. Grid moi duoc sua bang cach:

- Sao chep 36 `transactionTypeIds` tu `sfd_allTx_paymentfraud`.
- Dung `displayWidthVal: 0`.
- Dung `isResizable: false` de phu hop voi quy uoc cua cac grid hien tai.

Sau khi sua, dong goi lai ZIP va import lai toan bo candidate. Ket qua thanh cong thuc te:

```text
totalNumResourcesCreatedOrUpdated : 197
configurationComplete             : True
httpStatusCode                    : 200
```

## 9. Kiem tra sau import

1. Mo Alert Triage va nhan `Ctrl+F5`.
2. Mo alert co Entity Type `sfd_debitacc` va Triage Type `sfd_payment_fraud`.
3. Kiem tra pane `CNP Risk Signals`.
4. Kiem tra Transaction Viewer co cac tab theo thu tu:
   - CNP Review
   - All
   - Payment Transactions
   - Events
5. Kiem tra tab CNP Review co dung 10 cot.
6. Gui mot transaction moi voi Entity ID moi de kiem tra enrichment.

Alert cu co the hien layout moi nhung thieu enrichment moi. Vi vay can tao alert moi khi xac minh du lieu.

## 10. Rollback

Neu can quay lai cau hinh cu:

1. Dong goi noi dung thu muc `export` thanh ZIP, dam bao khong bi long thu muc.
2. Lay Bearer token con hieu luc hoac lay token moi.
3. POST ZIP backup vao cung endpoint `/alerts/config`.
4. Kiem tra `configurationComplete=True` va `httpStatusCode=200`.
5. Hard refresh Alert Triage va kiem tra lai alert page.

## 11. Don dep thong tin xac thuc

Sau khi import xong, xoa cac bien nhay cam khoi PowerShell:

```powershell
Remove-Variable token, tokenObject, tokenResponse, pass, securePass -ErrorAction SilentlyContinue
```

Khong ghi mat khau, access token hoac refresh token vao tai lieu, source code, commit hay anh chup man hinh.
