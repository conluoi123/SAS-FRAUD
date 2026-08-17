# SAS Fraud Rules - Context Handoff

> Cap nhat: 17/08/2026  
> Muc dich: Ban giao boi canh cho mot chat/agent khac de tiep tuc viet, deploy va test rule SAS Fraud ma khong phai tim hieu lai tu dau.

## 1. Muc tieu hien tai

Xay dung khoang 20-30 rule gian lan giao dich tren SAS Fraud Decisioning, sau do sinh message/data de test tung rule qua mot ung dung Streamlit noi bo.

Rule dau tien da lam va test end-to-end:

- Scenario: **CNP + thiet bi moi + xac thuc yeu**.
- Project: `SAS Debit Card Fraud`.
- Message schema: `Payment Fraud`.
- Message classification: `GLOBAL`.
- Variable rule: cap nhat danh sach thiet bi quen thuoc.
- Decision rule: decline va alert giao dich CNP gia tri cao tu thiet bi moi khi xac thuc yeu/that bai.
- Ket qua: decision rule da fire, tra ve `Decline`, tao alert va alert da xuat hien trong Alert Triage.

## 2. Tai lieu nguon da cung cap

Hai workbook nay la nguon tham chieu chinh cho field va profile:

1. `C:/Users/ADMIN/Downloads/Bang mo ta cac Schema hien co.xlsx`
2. `C:/Users/ADMIN/Downloads/Bang profile hien co.xlsx`

Ten file thuc te co dau tieng Viet:

- `Bang mo ta cac Schema hien co.xlsx` tuong ung voi file `Bảng mô tả các Schema hiện có.xlsx`.
- `Bang profile hien co.xlsx` tuong ung voi file `Bảng profile hiện có.xlsx`.

Neu chat moi co quyen truy cap may, nen doc lai hai file de doi chieu ten field truoc khi viet rule moi.

## 3. Schema va field quan trong da xac nhan

Nhung schema nghiep vu chinh tren he thong:

- Transaction/financial: `Card Financial`, `Payment`, `Credit Card`, `Card EMV`, cac Debit Variables, `Credit Account`, `Check`, `Chargeback`.
- Context/channel: `Digital`, `Channel`, `Merchant`, `Batch`, `Device`.
- Identity/authentication: `Authentication`, `Identification`, `Customer`, `Location`.
- Solution: cac bien dau vao/dau ra quan trong cho SAS Fraud.

Field da dung trong rule CNP:

| Muc dich | SAS path | Kieu/ghi chu |
| --- | --- | --- |
| Phan loai debit card | `message.solution.originationType` | Dang dung gia tri `'DC'` |
| Phan loai authorization | `message.solution.activityType` | Dang dung gia tri `'CA'` |
| Nhan dien CNP | `message.cardfinancial.cardPresentInd` | Trong moi truong nay, mau rule SAS xac nhan CNP la `'1'` |
| So tien | `message.cardfinancial.amount` | Numeric |
| Ket qua e-commerce auth | `message.cardfinancial.ecommerceAuthentication` | Vi du `SUCCESS`, `FAILED` |
| Ma thiet bi | `message.device.identifier` | Scalar String; day la field dung de so sanh thiet bi hien tai |
| Fingerprint thiet bi | `message.device.fingerprint` | `String[10]`; hien chi gui tham chieu, khong dung trong logic rule hien tai |
| Quyet dinh xac thuc | `message.authentication.decision` | Vi du `ACCEPT`, `DENY` |
| Muc xac thuc | `message.authentication.level` | Vi du `HIGH`, `LOW` |
| Ket qua xac thuc | `message.authentication.result` | Array, vi du `["SUCCESS"]` |
| Khoa profile debit card | `message.debitcard.number` | Phai giu nguyen khi seed va test cung mot profile |
| Entity alert debit account | `message.debitaccount.number` | Alert type hien dung la Debit Account |
| MCC | `message.merchant.categoryCode` | Se dung cho rule CNP + risky merchant/MCC |

### Quy uoc dac biet ve CNP

Khong tu dong doi `cardPresentInd = '1'` thanh `'0'`. Du ve mat dat ten co the gay nham lan, sample rule co san tren chinh moi truong SAS nay ghi ro:

```sas
message.cardfinancial.cardPresentInd = '1'
```

la CNP/online. Tat ca test end-to-end hien tai cung dang dung quy uoc nay.

### `authentication` va `auth`

Rule hien tai doc:

```sas
message.authentication.decision
message.authentication.level
```

Frontend da duoc sua de gui object `message.authentication`. Khong nen chi gui `message.auth`, vi variable rule tung khong cap nhat profile do sai path. Response SAS co the tra them cac field khac, nhung request test can khop dung path ma rule doc.

## 4. Profile hien tai

Profile set dang dung:

- Profile variable set: `SAS_DebitCard`.
- Rule syntax: `profile.sas_debitcard.<variable>`.
- Profile key: `debitcard.number` / `message.debitcard.number`.

Mot so bien san co da thay trong response:

- `currentMessageDtTm`
- `lastMessageDtTm`
- `testerMessageDtTm`
- `testMessageDtTm[]`
- `detailChangeDtTm`

Bien them cho scenario thiet bi moi:

- Name: `knownDeviceFingerprint`.
- Data type: String.
- Is Array: Yes.
- Logic hien tai chi dung 3 phan tu `[1]`, `[2]`, `[3]`.

### Luu y dat ten

`knownDeviceFingerprint` la ten da tao truoc, nhung hien no **khong luu fingerprint**. No dang luu:

```sas
message.device.identifier
```

Tuc la danh sach ma dinh danh thiet bi quen thuoc. Ten hop ly hon ve lau dai la `knownDeviceIdentifier`, nhung doi ten luc nay se can tao/migrate profile variable va sua ca hai rule. Trong giai doan hien tai co the giu ten cu, nhung comment phai noi ro y nghia.

## 5. Variable rule toi uu

Muc dich: chi hoc thiet bi sau mot giao dich CNP co xac thuc manh va thanh cong, dong thoi duy tri 3 thiet bi gan nhat theo kieu LRU.

Rule de xuat:

```sas
/*
    Rule Type: Variable
    Rule Name: rule_var_update_known_device_fingerprint

    Mo ta:
    Cap nhat 3 ma dinh danh thiet bi CNP quen thuoc gan nhat cua the ghi no
    sau giao dich CNP co xac thuc manh va thanh cong.

    Profile Variable:
    profile.sas_debitcard.knownDeviceFingerprint[1..3]
    (Ten bien la fingerprint nhung gia tri luu la message.device.identifier.)
*/

if message.solution.originationType = 'DC'
and message.solution.activityType = 'CA'
then do;

    if message.cardfinancial.cardPresentInd = '1'
    and message.device.identifier ^= ''
    and message.device.identifier ^= 'UNKNOWN'
    and message.device.identifier ^= 'N/A'
    and message.authentication.decision = 'ACCEPT'
    and message.authentication.level = 'HIGH'
    and message.cardfinancial.ecommerceAuthentication = 'SUCCESS'
    then do;

        if message.device.identifier = profile.sas_debitcard.knownDeviceFingerprint[1]
        then do;
            profile.sas_debitcard.knownDeviceFingerprint[1] =
                message.device.identifier;
        end;

        else if message.device.identifier = profile.sas_debitcard.knownDeviceFingerprint[2]
        then do;
            profile.sas_debitcard.knownDeviceFingerprint[2] =
                profile.sas_debitcard.knownDeviceFingerprint[1];

            profile.sas_debitcard.knownDeviceFingerprint[1] =
                message.device.identifier;
        end;

        else if message.device.identifier = profile.sas_debitcard.knownDeviceFingerprint[3]
        then do;
            profile.sas_debitcard.knownDeviceFingerprint[3] =
                profile.sas_debitcard.knownDeviceFingerprint[2];

            profile.sas_debitcard.knownDeviceFingerprint[2] =
                profile.sas_debitcard.knownDeviceFingerprint[1];

            profile.sas_debitcard.knownDeviceFingerprint[1] =
                message.device.identifier;
        end;

        else do;
            profile.sas_debitcard.knownDeviceFingerprint[3] =
                profile.sas_debitcard.knownDeviceFingerprint[2];

            profile.sas_debitcard.knownDeviceFingerprint[2] =
                profile.sas_debitcard.knownDeviceFingerprint[1];

            profile.sas_debitcard.knownDeviceFingerprint[1] =
                message.device.identifier;
        end;

    end;

end;
```

### Vi sao khong hoc moi giao dich `ACCEPT`

Neu chi can `authentication.decision = 'ACCEPT'`, ke gian co the lam profile hoc mot thiet bi khong dang tin cay. Dieu kien `HIGH` va `ecommerceAuthentication = 'SUCCESS'` lam giam nguy co profile poisoning.

### Mang rong co cap nhat duoc khong

Co. Khi profile ban dau rong, cac slot `[1..3]` doc ra rong. Nhanh `else do` van chay:

1. `[3]` nhan gia tri rong cua `[2]`.
2. `[2]` nhan gia tri rong cua `[1]`.
3. `[1]` nhan `message.device.identifier`.

Sau ba message seed khac nhau, mang ky vong la:

```text
[1] = DEV-KNOWN-003
[2] = DEV-KNOWN-002
[3] = DEV-KNOWN-001
```

## 6. Decision rule hien tai

```sas
/*
    Rule Type: Decision
    Rule Name: rule_cnp_new_device_weak_auth

    Project: SAS Debit Card Fraud
    Message Schema: Payment Fraud
    Message Classification: GLOBAL
    Organization: SAS Banking Fraud

    Mo ta:
    Tu choi va canh bao giao dich CNP the ghi no co gia tri cao,
    phat sinh tu thiet bi moi va co xac thuc yeu/khong thanh cong.
*/

if message.solution.originationType = 'DC'
and message.solution.activityType = 'CA'
then do;

    if message.cardfinancial.cardPresentInd = '1'
    and message.cardfinancial.amount > 500
    and message.device.identifier ^= ''
    and message.device.identifier ^= 'UNKNOWN'
    and message.device.identifier ^= 'N/A'
    and message.device.identifier ^= profile.sas_debitcard.knownDeviceFingerprint[1]
    and message.device.identifier ^= profile.sas_debitcard.knownDeviceFingerprint[2]
    and message.device.identifier ^= profile.sas_debitcard.knownDeviceFingerprint[3]
    and (
        message.authentication.decision ^= 'ACCEPT'
        or message.authentication.level = 'LOW'
        or message.cardfinancial.ecommerceAuthentication ^= 'SUCCESS'
    )
    then do;

        detection.Decline();
        detection.Alert();

    end;

end;
```

Alert configuration:

- Alert type: `Debit Account`.
- Alert reason/code concept: `CNP_NEW_DEVICE_WEAK_AUTH`.
- Dien giai: `CNP transaction from new device with weak authentication`.

### Ghi chu ve logic weak auth

Nhom dieu kien dang dung `OR`, nghia la chi can mot trong ba dau hieu xau la du:

- Decision khac `ACCEPT`.
- Level la `LOW`.
- E-commerce authentication khac `SUCCESS`.

Day la logic manh tay. Neu false positive cao, co the chuyen sang score/risk tier hoac yeu cau hai dau hieu cung luc. Chua nen doi truoc khi co ket qua test/Impact Analysis.

## 7. Thu tu rule va priority

Variable rule phai chay truoc decision rule trong cung message neu muon profile update co anh huong den logic sau do. Tuy nhien, voi message weak-auth thi variable rule khong hoc thiet bi do, nen decision rule van nhan no la thiet bi moi.

Khuyen nghi:

- Variable rule: priority `Main`, dat truoc decision rule trong ordering neu UI cho phep.
- Decision rule: priority `Main` trong giai doan test.
- Chua can dung priority cao hon neu khong co rule conflict/short-circuit.

Can luu y semantics thu tu cap nhat profile co the phu thuoc runtime SAS. Ket qua can xac nhan bang response `rulefired` va `profiles` thay vi chi dua vao vi tri tren UI.

## 8. Cach seed profile

Khong nhap truc tiep ba gia tri vao phan `Known device profile seed` tren FE. Cac o nay hien chi la gia tri ky vong de FE danh gia readiness, khong tu ghi vao SAS profile.

De seed mot thiet bi:

1. Dung message `Payment Fraud / GLOBAL`.
2. Giu nguyen `debitcard.number`, vi day la profile key.
3. Dat `cardPresentInd = '1'`.
4. Dat `authentication.decision = 'ACCEPT'`.
5. Dat `authentication.level = 'HIGH'`.
6. Dat `authentication.result = ['SUCCESS']`.
7. Dat `cardfinancial.ecommerceAuthentication = 'SUCCESS'`.
8. Dat `device.identifier` thanh thiet bi can seed.
9. Gui message va kiem tra `profiles.SAS_DebitCard.knownDeviceFingerprint` trong response.

Ba thiet bi seed da dung:

```text
DEV-KNOWN-001
DEV-KNOWN-002
DEV-KNOWN-003
```

Chi can doi `device.identifier` cho tung lan seed. `device.fingerprint` khong tham gia logic hien tai, co the giu mot gia tri hop le de payload dung schema.

Phai tao `transactionIdentifier`/message identifier moi cho moi lan gui neu runtime co deduplication.

## 9. Cach test decision rule

Sau khi seed xong, gui message cung `debitcard.number` voi cac gia tri chinh:

```json
{
  "message": {
    "solution": {
      "originationType": "DC",
      "activityType": "CA"
    },
    "request": {
      "schemaName": "Payment Fraud",
      "messageClassificationName": "GLOBAL"
    },
    "cardfinancial": {
      "amount": 750,
      "cardPresentInd": "1",
      "ecommerceAuthentication": "FAILED"
    },
    "authentication": {
      "decision": "DENY",
      "level": "LOW",
      "result": ["FAILURE"]
    },
    "device": {
      "identifier": "DEV-NEW-9001"
    },
    "debitcard": {
      "number": "DC-41127322"
    },
    "debitaccount": {
      "number": "DA-CUST-41127322"
    }
  }
}
```

Ket qua trigger ky vong:

- HTTP thanh cong.
- Runtime dung package moi.
- Decision rule co `firedFlg = true`.
- `alertFlg = true`.
- Decision `outcomeName = Decline`.
- `sas.alerted` co entity debit account.
- Alert xuat hien trong Alert Triage.

Test am tinh can co:

- Known device + weak auth: khong hit vi device da co trong profile.
- New device + strong auth: khong hit.
- New device + weak auth nhung amount `<= 500`: khong hit.
- Card-present/non-CNP: khong hit.
- Sai `originationType` hoac `activityType`: khong hit.

## 10. Dau hieu response da xac nhan thanh cong

Trong mot lan test thanh cong da quan sat:

- Variable rule reference: `50060.x`.
- Decision rule reference: `50061.x`.
- Decision rule `firedFlg = true`.
- `alertFlg = true`.
- `outcomeName = Decline`.
- Alert entity: `DA-CUST-41127322`.
- Alert entity type: `sfd_debitacc`.
- Alert da xuat hien trong Alert Triage.

Version rule/package co the thay doi moi lan edit/deploy, khong hard-code cac ID tren vao logic nghiep vu.

## 11. Deployment va package version

Deploy rule tren SAS Detection Definition khong dam bao endpoint runtime dang chay package moi ngay lap tuc. Da tung gap:

```text
Runtime package mismatch: expected 50026, got 50021.
```

Response moi hon da quan sat package `50032`; package nay cung se thay doi sau deploy tiep theo.

Luon doc:

```text
message.sas.system.packageVersion
```

va so sanh voi package/deployment mong doi. Neu mismatch thi ket qua test chua phan anh code vua deploy.

Man hinh Deployment History:

- Dau check xanh: deployment thanh cong.
- Dau X do: deployment that bai.
- Image registry digest nhu `registry.sas.env/fraud/bankingfraud@sha256:...` chi la image artifact/digest, khong phai package version nghiep vu de nhap vao FE.

## 12. Message classification

Endpoint da tung tra HTTP 400 khi gui `Southeast`:

```text
Message Classification provided does not match valid choices.
ValidMessageClassification: GLOBAL
```

Vi vay payload test hien tai phai dung:

```json
"messageClassificationName": "GLOBAL"
```

Classification dung de chon nhanh rule tree/nhom rule duoc ap dung cho message. Cac node `Greater China`, `Southeast`, `Central` co tren UI khong dong nghia runtime endpoint hien tai chap nhan tat ca cac gia tri do.

## 13. Streamlit test console

Vi tri:

```text
D:/Thuc tap/HPT/SAS-FRAUD/app/streamlit_console
```

File chinh:

- `app.py`: giao dien, preset, readiness, response viewer va package check.
- `payloads.py`: tao request `Payment Fraud`.
- `sas_client.py`: goi endpoint SAS.
- `sas_response.py`: parse response.
- `tests/test_streamlit_console.py`: test payload/response logic.

Hang so rule hien tai:

```python
CNP_RULE_NAME = "rule_cnp_new_device_weak_auth"
CNP_RULE_REASON = "CNP_NEW_DEVICE_WEAK_AUTH"
```

Preset hien co:

- `Trigger: new device + weak auth`
- `No trigger: known device`
- `No trigger: strong auth`
- `Custom`

Frontend hien gui:

- `message.authentication`, khong gui `message.auth`.
- `message.device.identifier` de rule so sanh.
- `message.device.fingerprint[]` chi de payload/schema day du, khong tham gia logic.
- `Payment Fraud` va `GLOBAL`.
- `debitcard.number` de resolve `SAS_DebitCard` profile.

FE co truong `Expected package version` va canh bao neu response runtime tra package khac.

Chay local:

```powershell
cd D:\Thực tập\HPT\SAS-FRAUD
python -m pip install -r requirements.txt
streamlit run app/streamlit_console/app.py --server.address 127.0.0.1 --server.port 8501
```

Kiem tra da chay:

```powershell
python -m py_compile app\streamlit_console\app.py app\streamlit_console\payloads.py tests\test_streamlit_console.py
python -m pytest tests\test_streamlit_console.py
```

Ket qua gan nhat: `3 passed`.

### Huong mo rong FE

Moi rule mot tab la hop ly khi chi co vai rule, nhung 20-30 rule se lam UI rat dai va kho bao tri. Kien truc nen chuyen dan sang:

- Mot registry/config cho tung scenario: rule name, reason, schema, classification, default payload, conditions va expected action.
- Nhom tab theo family (`CNP`, `ATO`, `Transfer`, `Merchant`, `Check`, ...).
- Dung selector cho scenario trong tung family thay vi 30 tab cap cao nhat.
- Tai su dung mot response viewer va runtime settings chung.

Khong can refactor ngay khi dang xac minh rule dau tien, nhung nen lam truoc khi so rule vuot 5-7.

## 14. Loi da gap va cach hieu

### `mismatched input 'ne' expecting {THEN, ';'}`

SAS rule editor khong chap nhan toan tu `ne` trong cu phap da dung. Dung:

```sas
^=
```

de bieu dien khac nhau.

### `There is a type mismatch. The assigned value must be of the type VARCHAR.`

Nguyen nhan la gan mot array (`message.device.fingerprint`) vao mot slot String/VARCHAR. Neu can lay fingerprint thi phai lay mot phan tu nhu `[1]`; tuy nhien thiet ke hien tai da chuyen sang scalar:

```sas
message.device.identifier
```

### Profile khong cap nhat

Checklist:

- Request co `message.authentication` dung path khong.
- Auth co `ACCEPT`, `HIGH`, `SUCCESS` khong.
- `ecommerceAuthentication = 'SUCCESS'` khong.
- `cardPresentInd = '1'` khong.
- `device.identifier` co rong/dirty khong.
- `debitcard.number` co dung profile key va giong message truoc khong.
- Variable rule co trong Production Rules khong.
- Response package co phai deployment moi khong.
- Trong `rulefired`, variable rule co dung reference/version mong doi khong.

### Rule deploy nhung khong co trong response

Thuong la endpoint van dang chay package cu. Kiem tra `message.sas.system.packageVersion`, khong chi nhin danh sach Production Rules tren UI.

### Alert khong len Alert Triage

Can phan biet:

- Rule khong fire: `firedFlg = false`.
- Rule fire nhung khong alert: `alertFlg = false` hoac `sas.alerted` rong.
- Alert da tao nhung triage cham/loc sai entity/time range.

Rule CNP hien tai da duoc xac nhan tao alert thanh cong, nen neu tai dien thi uu tien kiem tra package, rule version va filter tren triage.

## 15. Danh sach 10 nhom rui ro ban dau

Danh sach lam roadmap, khong phai tat ca deu da implement:

1. Card Not Present Fraud.
2. Lost/Stolen Card Usage.
3. Account Takeover.
4. Unauthorized Wire/Transfer Fraud.
5. Bust-Out Fraud.
6. Merchant Collusion.
7. Refund/Chargeback Abuse.
8. Check Fraud.
9. Synthetic Identity Fraud.
10. Cross-Border / Impossible Travel Fraud.

Bon rule con cu the trong nhom CNP:

1. CNP + thiet bi moi + xac thuc yeu. **Da implement va test thanh cong.**
2. CNP + merchant/MCC rui ro cao. **Rule tiep theo.**
3. CNP + quoc gia/IP bat thuong.
4. CNP + velocity qua nhieu merchant.

## 16. Rule tiep theo: CNP + risky merchant/MCC

Huong ban dau:

- Project: `SAS Debit Card Fraud`.
- Schema: `Payment Fraud`.
- Classification: `GLOBAL`.
- Rule type: `Decision`.
- Priority: `Main`.
- Action ban dau: `Alert`, chua `Decline` cho den khi tune.
- Amount threshold ban dau: `> 300`.
- MCC candidate: `7995`, `6051`, `5944`, `5732`, `5816`, `5967`.

Prototype hard-code:

```sas
/*
    Rule Type: Decision
    Rule Name: rule_cnp_risky_mcc

    Mo ta:
    Canh bao giao dich CNP the ghi no khi merchant thuoc nhom MCC rui ro cao
    va so tien giao dich vuot nguong kiem soat.
*/

if message.solution.originationType = 'DC'
and message.solution.activityType = 'CA'
then do;

    if message.cardfinancial.cardPresentInd = '1'
    and message.cardfinancial.amount > 300
    and (
        message.merchant.categoryCode = '7995'
        or message.merchant.categoryCode = '6051'
        or message.merchant.categoryCode = '5944'
        or message.merchant.categoryCode = '5732'
        or message.merchant.categoryCode = '5816'
        or message.merchant.categoryCode = '5967'
    )
    then do;
        detection.Alert();
    end;

end;
```

Huong production tot hon la tao Advanced List `Risky_MCC_List` de business co the sua MCC ma khong sua code rule. Truoc khi viet syntax Advanced List, can xem mot sample rule/list co san tren chinh moi truong SAS de dung dung API/cu phap cua version dang chay.

## 17. Nguyen tac lam cac rule sau

Voi moi scenario, nen lam theo thu tu:

1. Chot nghiep vu va action: alert, decline, review hay score.
2. Map tung condition vao field co that trong workbook schema.
3. Xac dinh condition nao can history/profile/advanced list.
4. Chi tao Variable rule khi can state lich su; Decision rule khong bat buoc luc nao cung co Variable rule kem theo.
5. Viet comment ngan gon bang tieng Viet theo format sample SAS.
6. Compile/save rule.
7. Cau hinh Alert Type/Reason neu co `detection.Alert()`.
8. Deploy va ghi lai package version.
9. Tao positive test va it nhat 3 negative tests.
10. Kiem tra response `rulefired`, decision, alert, profile va Alert Triage.
11. Sau khi dung logic moi tune threshold bang Impact Analysis/data test.

## 18. Nhung dieu chua duoc khang dinh 100%

- `device.identifier` co on dinh lau dai theo thiet bi hay thay doi theo session/phuong thuc thu thap hay khong: can xac minh hop dong du lieu tu nguon upstream.
- Danh sach MCC rui ro cao va threshold `300/500` moi la gia tri khoi dau, can business/risk owner phe duyet va tune.
- Dung card-level profile cho thiet bi la du cho MVP, nhung thuc te mot khach hang co the co nhieu the. Customer-level device profile co the phu hop hon neu schema/profile key ho tro.
- IP khong phai luc nao cung co trong CNP. CNP qua web/mobile co the co IP; mail order/telephone order hoac kenh trung gian co the khong co. Rule IP phai xu ly missing/null va khong dong nhat IP voi device identity.
- Thu tu variable/decision va thoi diem profile update can tiep tuc xac nhan tren runtime khi co nhieu rule phu thuoc cung mot profile.

## 19. Cau lenh khoi dong cho chat moi

Co the gui file nay kem yeu cau:

> Hay doc toan bo `SAS_FRAUD_RULES_CHAT_HANDOFF.md`. Tiep tuc tu trang thai hien tai, khong thay doi quy uoc CNP `cardPresentInd = '1'`, dung `message.authentication` va `message.device.identifier`. Truoc mat hay huong dan va implement rule `CNP + merchant/MCC rui ro cao`, sau do cap nhat Streamlit test console theo kien truc co the mo rong cho 20-30 rule.

