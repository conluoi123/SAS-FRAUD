# Runbook dua rule/alert vao SAS Visual Investigator

Tai lieu nay ghi lai quy trinh da kiem thu tren moi truong lab
`https://viya.sas.env`. Muc tieu la tai su dung quy trinh cho cac rule sau:

```text
Decision rule
  -> Alert Triage alert
  -> Visual Investigator data object
  -> VI alerting event
  -> VI active alert
  -> Claim / Assign
  -> Investigate
  -> Disposition
```

## 1. Pham vi va gioi han hien tai

Quy trinh trong tai lieu la mot ban tich hop thu cong qua REST API:

1. Rule tao alert trong Alert Triage.
2. Nguoi thuc hien xac dinh entity va du lieu can chuyen.
3. Data object duoc tao hoac tim trong Visual Investigator.
4. Mot file alerting event JSON duoc tao va POST vao VI.

Quy trinh nay chung minh mapping va API bridge hoat dong. No chua phai luong tu
dong Alert Triage day alert sang VI. De tu dong hoa can co service, job hoac flow
doc alert/event nguon, map du lieu va goi API VI.

## 2. Vi du da kiem thu

Rule CNP duoc dung lam vi du:

```text
Rule name: rule_cnp_new_device_weak_auth
Rule reason: CNP_NEW_DEVICE_WEAK_AUTH
Dieu kien: CNP + thiet bi moi + xac thuc yeu + amount > 500
Alert Triage alert ID: 539642637588672
Alert Triage entity ID: NKQ-23120347
Customer ID: CUST-41127322
```

Mapping VI da kiem thu:

```text
VI domain ID: svidomain
VI strategy: Default Alert Strategy
VI queue: queue_default (Default Alert Queue)
VI entity label: CNP Debit Account Quoc
VI entity metadata name: CNP_Debit_Account_Quoc
VI object ID: fb52c1d8-74e5-41ca-9095-5c2c0cbacaa3
VI alert type code: CNP
VI alert ID: 4deee30a-7d40-48c7-b937-b774e16855ff
```

## 3. Khai niem can phan biet

### 3.1 Alert Triage entity va VI data object

Entity trong Alert Triage va data object trong VI khong tu dong la cung mot doi
tuong. Can map ro:

```text
Alert Triage entity ID -> VI source_account_id
VI metadata name       -> actionableEntityType
VI internal object ID  -> actionableEntityId
```

`actionableEntityId` la ID noi bo cua object VI, khong mac dinh bang account ID
nghiep vu. Co the lay ID nay tu URL cua object VI:

```text
/document/<actionableEntityType>/<actionableEntityId>
```

### 3.2 Alerting event va alert

- Alerting event la su kien dau vao gui vao VI Alert Service.
- Alert la ban ghi duoc VI tao/ghop va dua vao strategy/queue.
- Mot alert co the duoc lien ket voi nhieu alerting event theo chinh sach gop.

### 3.3 Claim, Assign va Disposition

- Claim/Check out: nguoi dung nhan va khoa alert de xu ly.
- Assign: cap nhat nguoi/nhom phu trach.
- Disposition: ghi ket luan va thuc hien hanh dong ket thuc/chuyen trang thai.

## 4. Cau hinh mot lan trong VI Administrator

### 4.1 Xac minh domain va queue

Vao:

```text
Manage Investigate and Search
-> Alerts
-> Domains
```

Moi truong lab da co:

```text
Domain: Visual Investigator Domain
domainId: svidomain
Assignment: Enabled
Default Alert Score: 0
Strategy: Default Alert Strategy
Queue: Default Alert Queue
Queue ID: queue_default
```

Queue mac dinh khong can routing rule. Alert khong khop queue rieng se vao queue
mac dinh.

### 4.2 Them Alert Type

Vao:

```text
Data Objects -> Reference Data -> AlertTypes
```

Them mot reference value cho rule/scenario. Vi du:

```text
Reference Value: CNP New Device Weak Authentication
Code: CNP
```

Code phai nam trong gioi han length cua field. Moi payload phai dung chinh xac
gia tri Code tai `alertTypeCode`.

### 4.3 Tao internal data object

Tao internal entity cho doi tuong dieu tra neu chua co. Vi du:

```text
Label: CNP Debit Account Quoc
Metadata name: CNP_Debit_Account_Quoc
```

Bo field toi thieu de demo:

```text
source_account_id
customer_id
account_type
account_status
source_system
```

Co the bat `Index for search` cho cac field can tim. Mot so field he thong hoac
ID duoc SAS tu dong dat Required; khong can co gang sua checkbox Required.

### 4.4 Cau hinh Views va Page

Trong data object:

1. Cau hinh label/table/search fields trong tab `Views`.
2. Tao page trong `Pages and Toolbar`.
3. Gan page cho cac context `Create`, `Edit` va `View`.
4. Luu data object va page.

Page chi quyet dinh giao dien object VI. No khong tu tao alert va khong tu map
Alert Triage sang VI.

### 4.5 Tao hoac tim VI object

Tao object tu control `New Object` tren Home page, hoac tim object da co bang
Search. Vi du object:

```text
source_account_id: NKQ-23120347
customer_id: CUST-41127322
account_type: Debit Account
account_status: Active
source_system: Alert Triage
```

Mo object va ghi lai:

```text
actionableEntityType = metadata name cua data object
actionableEntityId   = UUID cuoi URL object
```

## 5. Checklist thong tin cho moi rule

Truoc khi tao payload, dien bang sau:

| Gia tri | Vi du CNP | Nguon |
| --- | --- | --- |
| Rule name | `rule_cnp_new_device_weak_auth` | Decision rule |
| Rule reason | `CNP_NEW_DEVICE_WEAK_AUTH` | Decision output/tester |
| Source alert ID | `539642637588672` | Alert Triage |
| Source entity ID | `NKQ-23120347` | Alert Triage |
| VI alert type code | `CNP` | VI Reference Data |
| VI domain ID | `svidomain` | VI domain API/admin |
| VI entity type | `CNP_Debit_Account_Quoc` | VI metadata name |
| VI object ID | `fb52c1d8-...` | VI object URL |
| Queue ID | de trong hoac `queue_default` | VI domain/queue |

Khong lay transaction amount lam risk score neu rule khong tinh risk score.
Trong truong hop do, bo field `score`; VI se dung default score cua domain.

## 6. Tao alerting event JSON

Mo PowerShell:

```powershell
Set-Location -LiteralPath "D:\Thực tập\HPT\SAS-FRAUD"
```

Tao ID moi cho tung lan gui:

```powershell
$alertingEventId = [guid]::NewGuid().ToString()
$scenarioEventId = [guid]::NewGuid().ToString()
```

Mau PowerShell cho CNP:

```powershell
$payload = @{
    jsonLayout = "nested"
    alertingEvents = @(
        @{
            alertingEventId      = $alertingEventId
            actionableEntityType = "CNP_Debit_Account_Quoc"
            actionableEntityId   = "fb52c1d8-74e5-41ca-9095-5c2c0cbacaa3"
            alertOriginCode      = "AT"
            alertTypeCode        = "CNP"
            domainId             = "svidomain"
            alertTriggerText     = "CNP + new device + weak authentication + amount > 500"

            scenarioFiredEvents  = @(
                @{
                    scenarioFiredEventId = $scenarioEventId
                    scenarioId           = "rule_cnp_new_device_weak_auth"
                    scenarioName         = "CNP New Device Weak Authentication"
                    scenarioOriginCode   = "AT"
                    displayFlag          = $true
                    displayTypeCode      = "TEXT"
                    ruleId               = "rule_cnp_new_device_weak_auth"
                }
            )

            enrichment = @{
                sourceAlertId           = "539642637588672"
                sourceEntityId          = "NKQ-23120347"
                customerId              = "CUST-41127322"
                ruleName                = "rule_cnp_new_device_weak_auth"
                ruleReason              = "CNP_NEW_DEVICE_WEAK_AUTH"
                transactionAmount       = 750
                transactionCurrency     = "USD"
                authenticationDecision  = "DENY"
                authenticationLevel     = "LOW"
                ecommerceAuthentication = "FAILED"
                merchantName            = "ECOM DIGITAL STORE"
                merchantCategoryCode    = "5411"
            }
        }
    )
}

$path = Join-Path $PWD "cnp-vi-alerting-event.json"
$payload | ConvertTo-Json -Depth 10 |
    Set-Content -LiteralPath $path -Encoding UTF8

Write-Host "File: $path"
Write-Host "Alerting Event ID: $alertingEventId"
```

Kiem tra JSON:

```powershell
Get-Content -LiteralPath $path -Raw | ConvertFrom-Json |
    Select-Object jsonLayout, @{Name="EventID";Expression={$_.alertingEvents[0].alertingEventId}}
```

## 7. Lay OAuth token

Nhap username/password trong terminal. Mat khau khong hien ky tu khi nhap:

```powershell
$user = Read-Host "SAS username"
$securePass = Read-Host "SAS password" -AsSecureString
$pass = [System.Net.NetworkCredential]::new("", $securePass).Password
```

Lay token:

```powershell
$tokenResponse = curl.exe -k -sS -X POST `
  "https://viya.sas.env/SASLogon/oauth/token" `
  -u "sas.cli:" `
  -H "Content-Type: application/x-www-form-urlencoded" `
  --data-urlencode "grant_type=password" `
  --data-urlencode "username=$user" `
  --data-urlencode "password=$pass"

$tokenObject = $tokenResponse | ConvertFrom-Json
$token = $tokenObject.access_token
$tokenObject | Select-Object token_type, expires_in, error, error_description
```

Thanh cong khi co `token_type=bearer` va `expires_in` khoang 3599.

Neu can luu token tam thoi:

```powershell
$token | Set-Content -LiteralPath ".\sas-token.txt" -Encoding ASCII
```

Khong commit file token. Token co thoi han va phai lay lai khi het han.

## 8. POST alerting event vao VI

Endpoint dung tren moi truong lab:

```text
POST https://viya.sas.env/svi-alert/alertingEvents
```

Lenh gui:

```powershell
$token = (Get-Content -LiteralPath ".\sas-token.txt" -Raw).Trim()

$importResponse = curl.exe -k -sS -X POST `
  "https://viya.sas.env/svi-alert/alertingEvents" `
  -H "Authorization: Bearer $token" `
  -H "Content-Type: application/vnd.sas.investigation.triage.alerting.data.nested+json" `
  -H "Accept: application/vnd.sas.collection+json" `
  -H "Expect:" `
  --data-binary "@cnp-vi-alerting-event.json" `
  -w "`nHTTP_STATUS=%{http_code}`n"

$importResponse
```

Moi truong da tra ve `HTTP_STATUS=201`, nghia la alerting event duoc tao thanh
cong. Khong gui lai cung `alertingEventId` sau khi da nhan ma 2xx.

## 9. Xac minh ket qua

### 9.1 Kiem tra qua API
 
```powershell
curl.exe -k -sS `
  "https://viya.sas.env/svi-alert/alertingEvents/$alertingEventId" `
  -H "Authorization: Bearer $token" `
  -H "Accept: application/vnd.sas.investigation.triage.alerting.event.nested+json"
```

### 9.2 Kiem tra tren VI end-user

Vao:

```text
Visual Investigator -> Alerts
Strategy: Default Alert Strategy
View: All active alerts
```

Ket qua CNP da kiem thu:

```text
Score: 0
Actionable Entity Type: CNP_Debit_Account_Quoc
Actionable Entity Label: NKQ-23120347
Queue: Default Alert Queue
Scenario: CNP New Device Weak Authentication
Status: Active
```

`Score=0` la dung khi payload khong truyen score va default domain score bang 0.

## 10. Claim va doc Alert History

Chon dong alert va bam `Claim`. Claim tuong ung voi check out alert.

Alert History da kiem thu co thu tu:

```text
The alert was created.
A new alerting event was linked to the alert.
The alert was checked in by the system for a user.
The alert was checked out.
The alert assignment was updated.
```

Y nghia:

- Created: VI tao alert.
- Event linked: alerting event duoc gan vao alert.
- Checked in: alert san sang trong queue.
- Checked out: nguoi dung Claim alert.
- Assignment updated: nguoi/nhom phu trach duoc cap nhat.

Sau Claim, kiem tra `Alert Details`, `Alert Activity`, `Scoring History`,
`Alert History` va `Workspace`.

## 11. Enrichment va giao dien dieu tra

Payload co object `enrichment`, nhung viec luu du lieu khong dong nghia tat ca
field se tu dong hien tren page. De analyst thay amount, device, authentication
va merchant, can:

1. Xac minh enrichment da nam trong alerting event API response.
2. Tao/kiem tra enrichment field metadata trong VI Alerts configuration.
3. Dua cac field can thiet vao page/control phu hop.
4. Gui alerting event moi de kiem tra end-to-end.

Bo field CNP de xuat:

```text
sourceAlertId
sourceEntityId
customerId
ruleName
ruleReason
transactionAmount
transactionCurrency
authenticationDecision
authenticationLevel
ecommerceAuthentication
merchantName
merchantCategoryCode
```

Khong sua data object chi de thay the enrichment. Data object mo ta doi tuong
dieu tra; enrichment mo ta ngu canh cua alerting event.

## 12. Disposition va dong alert

`Productive` trong Alert Details de trong khi chua co disposition. De hoan tat
demo:

1. Vao VI Administrator.
2. Vao `Alerts -> Domains`.
3. Chon `Default Alert Strategy -> Default Alert Queue`.
4. Gan disposition phu hop cho queue.
5. Quay lai end-user, Claim alert va chon Disposition.

Bo ket luan toi thieu co the gom:

```text
Productive / Fraud
Unproductive / Genuine
Indeterminate / Needs Review
```

Ten va hanh dong thuc te phai theo disposition duoc cau hinh trong moi truong,
khong tu suy dien tu ten nghiep vu.

## 13. Loi thuong gap

### 13.1 `401 Full authentication is required`

Nguyen nhan: dung Basic Auth, token rong hoac token het han.

Khac phuc: lay Bearer token moi tu `/SASLogon/oauth/token`.

### 13.2 `405 POST is not supported` tai `/alertingEvents/nested`

Moi truong lab khong nhan POST tai:

```text
/svi-alert/alertingEvents/nested
```

Endpoint dung la:

```text
/svi-alert/alertingEvents
```

Tu `nested` duoc the hien trong `Content-Type` va `jsonLayout`, khong nam trong
URL POST. Loi 405 khong tao alert, vi vay co the sua endpoint va gui lai cung
event ID.

### 13.3 `400 Bad Request`

Kiem tra:

- `domainId` co ton tai.
- `alertTypeCode` co trong `AlertTypes` reference data.
- `actionableEntityType` dung metadata name, khong phai label.
- `actionableEntityId` la VI internal object ID.
- JSON co `jsonLayout=nested` va mang `alertingEvents`.

Khong retry bang Event ID moi cho den khi hieu nguyen nhan.

### 13.4 `415 Unsupported Media Type`

Kiem tra header:

```text
Content-Type: application/vnd.sas.investigation.triage.alerting.data.nested+json
```

### 13.5 Alert vao Default Alert Queue

Day khong phai loi neu chua co routing rule rieng. Tao queue/routing rieng chi
khi nghiep vu can tach workload CNP.

### 13.6 UI VI bi lech hoac mat toolbar

Thu theo thu tu:

1. `Ctrl+0` de reset zoom.
2. `Ctrl+F5` de hard refresh.
3. Mo lai URL `/SASVisualInvestigator/index.html#/alerts`.
4. Chon lai strategy/view va alert row.

Khong gui lai JSON chi vi UI bi loi hien thi.

## 14. Quy trinh lap lai cho rule moi

1. Test rule va xac nhan Alert Triage tao alert.
2. Ghi source alert ID, entity ID, rule name va reason.
3. Chon VI data object phu hop; chi tao object type moi neu model nghiep vu moi.
4. Tao/tim object VI va lay internal object ID tu URL.
5. Them `AlertTypes` code ngan, duy nhat.
6. Copy payload template va thay toan bo gia tri rule/entity.
7. Tao hai GUID moi.
8. Lay token moi.
9. POST vao `/svi-alert/alertingEvents`.
10. Chi gui mot lan; chap nhan `200` hoac `201` la thanh cong.
11. Kiem tra alert, queue, scenario va entity tren VI.
12. Claim, dieu tra, ghi evidence/comment neu co.
13. Apply disposition.
14. Kiem tra Alert History va trang thai cuoi.

## 15. Tieu chi hoan thanh full demo

- [ ] Rule fire dung tren bo test duong tinh.
- [ ] Alert hien trong Alert Triage.
- [ ] Entity va page Alert Triage hien dung.
- [ ] VI data object ton tai va tim duoc.
- [ ] Alert type code ton tai trong VI Reference Data.
- [ ] POST alerting event tra ve HTTP 2xx.
- [ ] VI tao Active Alert.
- [ ] Entity, scenario va queue dung.
- [ ] Claim/assignment duoc ghi trong Alert History.
- [ ] Enrichment quan trong hien cho analyst.
- [ ] Analyst ghi nhan dieu tra/evidence.
- [ ] Disposition duoc ap dung.
- [ ] Alert History va trang thai cuoi dung.
- [ ] Token va file nhay cam duoc don dep.

## 16. Don dep thong tin xac thuc

Sau khi test:

```powershell
Remove-Item -LiteralPath ".\sas-token.txt" -ErrorAction SilentlyContinue
Remove-Variable token, tokenObject, tokenResponse, pass, securePass -ErrorAction SilentlyContinue
```

Khong commit password, access token, cookie hoac response co thong tin nhay cam.
Payload demo chi duoc dung du lieu gia lap.
