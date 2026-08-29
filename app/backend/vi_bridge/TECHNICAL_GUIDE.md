# Huong dan ky thuat `vi_bridge`

Thu muc `app/backend/vi_bridge/` la package Python dung de ket noi luong
Alert Triage sang SAS Visual Investigator (VI).

Trang thai hien tai: package nay moi xu ly phan sau khi da co message mark.
No chua doc truc tiep tu Kafka. Script test thu cong se doc message mau trong
`sample_data/transaction_topic_mark_sample.json`, sau do goi cac API that cua
SAS VI.

## Muc tieu cua package

`vi_bridge` nhan mot message tu topic `transaction-topic-mark` cua Alert
Triage, kiem tra mark do co can dieu tra hay khong, tim hoac tao Known Object
trong Visual Investigator, tao payload alerting event, roi gui alert sang VI.

Luong xu ly tong quat:

1. Doc cau hinh ket noi VI tu `.env`.
2. Lay OAuth access token tu SAS Logon.
3. Doc `markProperties` trong message.
4. Kiem tra `rootMarkName` co nam trong nhom can escalate hay khong.
5. Map `transactionTypeId` sang entity type trong VI.
6. Lay `alertData.actionableEntityID` lam business key cua Known Object.
7. Goi `svi-datahub` de tim Known Object da ton tai.
8. Neu chua co thi tao Known Object moi.
9. Build payload `alertingEvent`.
10. Goi `svi-alert` de tao alert trong Visual Investigator.

## Cau truc file

```text
app/backend/vi_bridge/
  __init__.py
  auth.py
  builder.py
  config.py
  mapping.py
  README.md
  run_manual_test.py
  vi_client.py
  sample_data/
    transaction_topic_mark_sample.json
```

Thu muc `__pycache__/` neu co la bytecode Python tu sinh khi chay chuong trinh,
khong phai source code chinh.

## `__init__.py`

File nay khai bao y nghia cua package `vi_bridge`.

No mo ta ro package hien tai dang lam cac viec:

- Resolve hoac create Known Object trong Visual Investigator bang API
  `svi-datahub`.
- Map transaction type cua Alert Triage sang VI entity type.
- Build payload `alertingEvent`.
- POST payload sang VI Alerts API `svi-alert`.

File nay cung ghi chu rang Kafka consumer chua duoc implement. Khi co ket noi
Kafka that, co the them `consumer.py` va de consumer goi lai ham
`run_bridge_for_mark()` trong `run_manual_test.py` cho tung message doc duoc.

## `config.py`

File nay phu trach load cau hinh ket noi Visual Investigator tu environment
variables.

Class chinh:

```python
ViConfig
```

`ViConfig` gom cac truong:

- `base_url`: URL goc cua SAS Viya/VI, lay tu `VI_BASE_URL`.
- `tls_verify`: co verify TLS certificate hay khong, lay tu `VI_TLS_VERIFY`.
- `username`: user dang nhap VI, lay tu `VI_USERNAME`.
- `password`: password dang nhap VI, lay tu `VI_PASSWORD`.
- `domain_id`: domain trong VI, mac dinh `svidomain`.
- `alert_origin_code`: ma nguon alert, mac dinh `AT`.
- `request_timeout_seconds`: timeout cho request HTTP, mac dinh `30`.

Ham chinh:

```python
load_vi_config() -> ViConfig
```

Ham nay:

- Goi `load_dotenv()` de nap bien moi truong tu file `.env`.
- Kiem tra cac bien bat buoc:
  - `VI_BASE_URL`
  - `VI_USERNAME`
  - `VI_PASSWORD`
- Neu thieu bien bat buoc, ham raise `KeyError` voi thong bao ro rang.
- Loai dau `/` cuoi `VI_BASE_URL` bang `.rstrip("/")` de ghep endpoint on dinh.

Ham phu:

```python
_get_bool(name: str, default: str = "false") -> bool
```

Ham nay chuyen environment variable dang chuoi sang boolean. Chi gia tri
`"true"` sau khi trim va lower moi duoc xem la `True`.

## `auth.py`

File nay phu trach lay OAuth token de goi cac REST API cua SAS Viya /
Visual Investigator.

Ham chinh:

```python
get_oauth_token(config: ViConfig) -> str
```

Ham nay goi endpoint:

```text
POST {VI_BASE_URL}/SASLogon/oauth/token
```

Thong tin request:

- Basic auth client:
  - username: `sas.cli`
  - password: chuoi rong
- Header:
  - `Content-Type: application/x-www-form-urlencoded`
- Form data:
  - `grant_type=password`
  - `username=config.username`
  - `password=config.password`

Sau khi request thanh cong, ham doc JSON response va tra ve `access_token`.
Neu response khong co `access_token`, ham raise `RuntimeError`.

Token nay duoc dung lam Bearer token khi goi `svi-datahub` va `svi-alert`.

## `mapping.py`

File nay la noi quan ly mapping giua transaction type cua Alert Triage va
entity type cua Visual Investigator.

Dataclass chinh:

```python
EntityTypeMapping
```

Dataclass nay co 3 truong:

- `vi_entity_type`: ten entity type/object type trong VI.
- `vi_source_field`: field trong VI dung de luu business key tu Alert Triage.
- `vi_alert_type_code`: alert type code da ton tai trong reference data cua VI.

Bang mapping hien tai:

```python
TRANSACTION_TYPE_TO_ENTITY = {
    "DCCA": EntityTypeMapping(
        vi_entity_type="CNP_Debit_Account_Quoc",
        vi_source_field="source_account_id",
        vi_alert_type_code="CNP",
    ),
}
```

Y nghia:

- Khi `markProperties.transactionTypeId` la `DCCA`, bridge se tao alert cho VI
  entity type `CNP_Debit_Account_Quoc`.
- Business key cua object se duoc luu vao field `source_account_id`.
- Alert type code gui sang VI la `CNP`.

Danh sach mark can escalate:

```python
ESCALATE_ROOT_MARKS = {"confirm_invalid", "marked_for_review"}
```

Neu `rootMarkName` khong nam trong set nay, bridge se bo qua message va khong
tao alert.

Ham chinh:

```python
resolve_entity_mapping(transaction_type_id: str) -> EntityTypeMapping
```

Tra ve mapping ung voi `transactionTypeId`. Neu chua co mapping, ham raise
`ValueError` va yeu cau can VI admin xac nhan entity type/page truoc khi them
mapping moi.

```python
should_escalate(root_mark_name: str) -> bool
```

Tra ve `True` neu mark can day sang VI de dieu tra.

## `builder.py`

File nay build payload JSON theo format ma VI Alerts API can.

Ham chinh:

```python
build_alerting_event(
    mark_message: dict[str, Any],
    vi_object_id: str,
    entity_mapping: EntityTypeMapping,
    config: ViConfig,
) -> dict[str, Any]
```

Input:

- `mark_message`: message mark tu Alert Triage/Kafka.
- `vi_object_id`: id noi bo cua Known Object trong VI.
- `entity_mapping`: mapping da resolve tu `mapping.py`.
- `config`: cau hinh VI.

Ham lay `markProperties` tu message va tao payload dang:

```json
{
  "jsonLayout": "nested",
  "alertingEvents": [
    {
      "alertingEventId": "...",
      "actionableEntityType": "...",
      "actionableEntityId": "...",
      "alertOriginCode": "...",
      "alertTypeCode": "...",
      "domainId": "...",
      "alertTriggerText": "...",
      "scenarioFiredEvents": [...],
      "enrichment": {...}
    }
  ]
}
```

Diem quan trong:

- `alertingEventId` dung `markProperties.id`.
- `scenarioFiredEventId` cung dung `markProperties.id`.
- Cach nay giup idempotency: neu cung mot Kafka message bi deliver lai, bridge
  khong nen tao alert duplicate bang random id moi.

Phan `enrichment` hien tai chi gom cac field that su co trong
`transaction-topic-mark`:

- `sourceAlertId`
- `sourceTransactionId`
- `markConfigId`
- `reasonCodeId`
- `reasonCodeLabel`
- `memoText`

Ghi chu quan trong: message hien tai khong co cac field giau hon nhu
`transactionAmount`, `merchantName`, `authenticationDecision`. Neu analyst can
cac field do, phien ban sau phai query them transaction detail tu database cua
Alert Triage bang `markProperties.transactionId`.

## `vi_client.py`

File nay chua cac ham goi HTTP sang hai nhom API cua SAS Visual Investigator:

- `svi-datahub`: tim/tao Known Object.
- `svi-alert`: tao alerting event.

Hang so content type/accept:

- `FILTER_CONTENT_TYPE`
- `FILTER_ACCEPT`
- `FILTER_ACCEPT_ITEM`
- `CREATE_CONTENT_TYPE`
- `ALERTING_EVENT_CONTENT_TYPE`
- `ALERTING_EVENT_ACCEPT`

Cac gia tri nay la media type ma SAS VI API yeu cau.

Ham phu:

```python
_headers(token, content_type=None, accept=None, accept_item=None)
```

Tao HTTP headers gom:

- `Authorization: Bearer <token>`
- `Content-Type` neu co
- `Accept` neu co
- `Accept-Item` neu co

### `find_document_by_field(...)`

```python
find_document_by_field(
    config: ViConfig,
    token: str,
    entity_type: str,
    field_name: str,
    field_value: str,
) -> dict[str, Any] | None
```

Cong dung:

- Tim document/Known Object trong VI theo field.
- Vi du tim object type `CNP_Debit_Account_Quoc` co
  `source_account_id == "NKQ-23120347"`.

Endpoint:

```text
POST {VI_BASE_URL}/svi-datahub/documents/{entity_type}
```

Body:

```json
{
  "filter": "eq(source_account_id,'NKQ-23120347')",
  "limit": 1
}
```

Neu tim thay, ham tra ve item dau tien. Neu khong co item nao, tra ve `None`.

### `create_document(...)`

```python
create_document(
    config: ViConfig,
    token: str,
    entity_type: str,
    field_values: dict[str, Any],
) -> dict[str, Any]
```

Cong dung:

- Tao Known Object moi trong VI.

Endpoint:

```text
POST {VI_BASE_URL}/svi-datahub/documents
```

Body:

```json
{
  "objectTypeName": "CNP_Debit_Account_Quoc",
  "fieldValues": {
    "source_account_id": "NKQ-23120347",
    "source_system": "Alert Triage"
  }
}
```

Ham tra ve JSON response cua VI.

### `resolve_or_create_known_object(...)`

```python
resolve_or_create_known_object(
    config: ViConfig,
    token: str,
    entity_type: str,
    source_field: str,
    source_value: str,
    extra_fields_if_created: dict[str, Any] | None = None,
) -> str
```

Cong dung:

- Tim Known Object theo `source_field == source_value`.
- Neu da co, tra ve `existing["id"]`.
- Neu chua co, tao object moi va tra ve `created["id"]`.

Day la ham trung tam cho logic "Known Object da ton tai hay chua".

### `post_alerting_event(...)`

```python
post_alerting_event(
    config: ViConfig,
    token: str,
    alerting_event_payload: dict[str, Any],
) -> dict[str, Any]
```

Cong dung:

- Gui payload alerting event sang VI Alerts API.

Endpoint:

```text
POST {VI_BASE_URL}/svi-alert/alertingEvents
```

Neu status code la `200` hoac `201`, ham xem la thanh cong va tra ve:

```python
{
    "status_code": response.status_code,
    "body": ...
}
```

Neu status code khac, ham goi `response.raise_for_status()`.

### `_safe_json(...)`

```python
_safe_json(response: requests.Response) -> Any
```

Cong dung:

- Thu parse response thanh JSON.
- Neu response khong phai JSON, tra ve plain text.

## `run_manual_test.py`

File nay la script test thu cong end-to-end, khong can Kafka.

File message mau:

```python
SAMPLE_MESSAGE_PATH = Path(__file__).parent / "sample_data" / "transaction_topic_mark_sample.json"
```

Ham chinh:

```python
run_bridge_for_mark(mark_message: dict) -> dict
```

Luong xu ly trong ham:

1. Goi `load_vi_config()` de load `.env`.
2. Goi `get_oauth_token(config)` de lay token.
3. Lay `mark_props = mark_message["markProperties"]`.
4. Goi `should_escalate(mark_props["rootMarkName"])`.
5. Neu mark khong can investigate, tra ve:

   ```python
   {
       "skipped": True,
       "reason": "..."
   }
   ```

6. Goi `resolve_entity_mapping(mark_props["transactionTypeId"])`.
7. Lay `source_value = mark_message["alertData"]["actionableEntityID"]`.
8. Goi `vi_client.resolve_or_create_known_object(...)`.
9. Goi `build_alerting_event(...)`.
10. In payload ra terminal.
11. Goi `vi_client.post_alerting_event(...)`.
12. Tra ve ket qua tu VI.

Khi chay file bang `python -m`, block sau se doc JSON mau va goi pipeline:

```python
if __name__ == "__main__":
    with open(SAMPLE_MESSAGE_PATH, encoding="utf-8") as f:
        sample_message = json.load(f)

    outcome = run_bridge_for_mark(sample_message)
    print("--- Result ---")
    print(json.dumps(outcome, indent=2, default=str))
```

## `sample_data/transaction_topic_mark_sample.json`

Day la message mau dai dien cho mot message doc tu topic
`transaction-topic-mark`.

Cau truc chinh:

```json
{
  "markProperties": {...},
  "alertData": {...},
  "messageVariables": {...}
}
```

### `markProperties`

Chua thong tin mark cua Alert Triage:

- `id`: GUID cua mark, duoc dung lam `alertingEventId`.
- `transactionId`: id giao dich nguon.
- `alertId`: id alert nguon trong Alert Triage.
- `transactionTypeId`: loai giao dich, hien tai la `DCCA`.
- `markConfigId`: cau hinh mark.
- `rootMarkName`: loai mark goc, vi du `confirm_invalid`.
- `transactionMarkLabel`: label hien thi, vi du `Suspected Fraud`.
- `reasonCodeId`: ma reason code.
- `reasonCodeLabel`: label reason code.
- `CreationTimeStamp`, `CreatedBy`, `ModifiedTimeStamp`, `ModifiedBy`:
  metadata audit.

### `alertData`

Chua business key cua object can dieu tra:

```json
{
  "actionableEntityID": "NKQ-23120347"
}
```

Gia tri nay duoc dung de tim hoac tao Known Object trong VI.

### `messageVariables`

Chua metadata bo sung cua message SAS, vi du schema, organization va timestamp.
Hien tai bridge chua dung cac field nay de build alert.

## `README.md`

README la ban tom tat ngan cua package:

- File nao lam gi.
- Phan nao da hoat dong.
- Phan nao con thieu.
- Cach chay script test.
- Cac gap da biet.

File `TECHNICAL_GUIDE.md` nay mo ta chi tiet hon README de phuc vu viec doc
code va ban giao ky thuat.

## Dieu kien truoc khi chay test

Can co Python va dependencies trong `requirements.txt`, dac biet:

- `python-dotenv`
- `requests`

Neu chua cai dependencies:

```powershell
pip install -r requirements.txt
```

Can tao file `.env` o thu muc root project. Co the copy tu `.env.example`:

```powershell
Copy-Item .env.example .env
```

Sau do dien cac bien lien quan VI:

```env
VI_BASE_URL=https://viya.sas.env
VI_TLS_VERIFY=false
VI_USERNAME=<your-vi-username>
VI_PASSWORD=<your-vi-password>
VI_DOMAIN_ID=svidomain
VI_ALERT_ORIGIN_CODE=AT
VI_REQUEST_TIMEOUT_SECONDS=30
```

Luu y:

- `VI_USERNAME` va `VI_PASSWORD` la bat buoc.
- `VI_BASE_URL` la bat buoc.
- Neu moi truong dung certificate noi bo chua trust tren may local, co the can
  de `VI_TLS_VERIFY=false` nhu `.env.example`.
- Script test se goi API that cua VI, nen co the tao Known Object/Alert that
  trong moi truong VI.

## Cach chay test thu cong

Dung PowerShell tai root project:

```powershell
cd "D:\Thực tập\HPT\SAS-FRAUD"
python -m app.backend.vi_bridge.run_manual_test
```

Neu dang dung virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
python -m app.backend.vi_bridge.run_manual_test
```

Output mong doi:

1. Terminal in ra payload:

   ```text
   --- Payload about to be sent to VI ---
   {
     "jsonLayout": "nested",
     "alertingEvents": [...]
   }
   ```

2. Terminal in ra ket qua:

   ```text
   --- Result ---
   {
     "status_code": 201,
     "body": ...
   }
   ```

Status code `200` hoac `201` deu duoc code xem la thanh cong.

## Cach test tung phan bang Python interactive

Co the mo Python tu root project:

```powershell
python
```

Load cau hinh:

```python
from app.backend.vi_bridge.config import load_vi_config

config = load_vi_config()
config.base_url
```

Lay token:

```python
from app.backend.vi_bridge.auth import get_oauth_token

token = get_oauth_token(config)
token[:20]
```

Test mapping:

```python
from app.backend.vi_bridge.mapping import resolve_entity_mapping, should_escalate

should_escalate("confirm_invalid")
resolve_entity_mapping("DCCA")
```

Build payload tu sample:

```python
import json
from pathlib import Path

from app.backend.vi_bridge.builder import build_alerting_event
from app.backend.vi_bridge.mapping import resolve_entity_mapping

path = Path("app/backend/vi_bridge/sample_data/transaction_topic_mark_sample.json")
message = json.loads(path.read_text(encoding="utf-8"))

mapping = resolve_entity_mapping(message["markProperties"]["transactionTypeId"])
payload = build_alerting_event(
    mark_message=message,
    vi_object_id="example-vi-object-id",
    entity_mapping=mapping,
    config=config,
)
payload
```

## Loi thuong gap

### Thieu bien moi truong

Thong bao co dang:

```text
Missing required environment variable(s): VI_USERNAME, VI_PASSWORD
```

Cach xu ly:

- Kiem tra da tao `.env` chua.
- Kiem tra `.env` co `VI_BASE_URL`, `VI_USERNAME`, `VI_PASSWORD` chua.
- Chay command tu root project de `python-dotenv` load dung file `.env`.

### Login that bai hoac HTTP 401

Nguyen nhan co the:

- Sai `VI_USERNAME` hoac `VI_PASSWORD`.
- User khong co quyen goi API.
- Endpoint `VI_BASE_URL` sai.

Cach xu ly:

- Kiem tra lai credential.
- Kiem tra co dang truy cap dung VI environment khong.
- Hoi VI admin neu user thieu quyen.

### Loi TLS certificate

Neu gap loi certificate verification, trong moi truong test local co the dat:

```env
VI_TLS_VERIFY=false
```

Neu moi truong production yeu cau verify TLS, nen cau hinh CA bundle dung cach
thay vi tat verify.

### `svi-datahub` tra ve 404

Trong `vi_client.py` co ghi chu rang base path `svi-datahub` chua duoc verify
live trong lan chay dau. Neu endpoint:

```text
{VI_BASE_URL}/svi-datahub/...
```

tra ve 404, can hoi VI admin duong dan gateway dung cho Datahub API.

### Khong co mapping cho `transactionTypeId`

Thong bao co dang:

```text
No VI entity type mapping configured for transactionTypeId='...'
```

Cach xu ly:

- Xac nhan voi VI admin entity type tuong ung da duoc tao trong VI.
- Xac nhan alert type code da co trong VI reference data.
- Sau do moi them row vao `TRANSACTION_TYPE_TO_ENTITY` trong `mapping.py`.

### Mark bi skip

Neu `rootMarkName` khong thuoc:

```python
{"confirm_invalid", "marked_for_review"}
```

bridge se khong gui alert sang VI. Day la hanh vi co chu y, vi khong phai moi
mark deu can dieu tra.

## Gioi han hien tai

1. Chua co Kafka consumer.
   - Bridge chua tu doc `transaction-topic-mark`.
   - Hien tai chi test bang JSON mau.

2. Chua enrich day du thong tin giao dich.
   - Message mau khong co amount, merchant, authentication decision.
   - Neu can, phai query them tu bang transaction cua Alert Triage.

3. Mapping moi phai duoc xac nhan voi VI admin.
   - Code chi tao entity instance/document.
   - Code khong tao entity type, page, alert type reference data trong VI.

4. Script test goi moi truong VI that.
   - Can can than vi co the tao du lieu that trong Visual Investigator.

## Khi nao can them `consumer.py`

Chi nen them Kafka consumer khi da co thong tin ket noi Kafka that:

- bootstrap server dung cho Kafka wire protocol
- security protocol
- SASL/SSL config neu co
- topic name
- consumer group id

Khi do `consumer.py` co the doc tung message tu topic
`transaction-topic-mark`, parse JSON, roi goi:

```python
from app.backend.vi_bridge.run_manual_test import run_bridge_for_mark

run_bridge_for_mark(message)
```

Nen tach logic core ra khoi `run_manual_test.py` trong tuong lai neu consumer
duoc implement chinh thuc, vi ten `run_manual_test.py` hien tai chi phu hop cho
test thu cong.
