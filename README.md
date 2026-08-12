# SAS-FRAUD


Tóm lại chuẩn quy trình từ **Harbor image -> runtime test** là như này.

**1. Deploy trong SDA**

Trong SDA:

```text
Deployments -> Quoc RFC Bank Asia -> Deploy
```

Chờ status xanh.

Sau đó vào Harbor:

```text
https://registry.sas.env
Project: fraud
Repository: quocrfcbankasia
```

Lấy image reference, ví dụ:

```text
registry.sas.env/fraud/quocrfcbankasia@sha256:2968db554128018572f1b3cdaf4778491304be179054ffdbba5b30c6cca546cb
```

**2. Kiểm tra deployment runtime hiện tại**

Trên SSH server:

```bash
kubectl get deploy -A | grep -i fraud
```

Kết quả của bạn:

```text
detection-runtime   sas-sda-detection-scr-banking-fraud
```

Xem container names và images:

```bash
kubectl get deploy -n detection-runtime sas-sda-detection-scr-banking-fraud \
-o jsonpath='{.spec.template.spec.containers[*].name}{"\n"}{.spec.template.spec.containers[*].image}{"\n"}'
```

Bạn sẽ thấy 2 container:

```text
sas-sda-scr sas-detection
registry.sas.env/fraud/bankingfraud:... cr.sas.com/.../sas-detection:...
```

Chỉ đổi container:

```text
sas-sda-scr
```

Không đổi:

```text
sas-detection
```

**3. Set image từ Harbor vào runtime**

Dùng image digest từ Harbor:

```bash
kubectl set image deployment/sas-sda-detection-scr-banking-fraud \
-n detection-runtime \
sas-sda-scr=registry.sas.env/fraud/quocrfcbankasia@sha256:2968db554128018572f1b3cdaf4778491304be179054ffdbba5b30c6cca546cb
```

Chờ rollout:

```bash
kubectl rollout status deployment/sas-sda-detection-scr-banking-fraud -n detection-runtime
```

Kiểm tra pod:

```bash
kubectl get pods -n detection-runtime
```

Cần thấy pod `2/2 Running`.

**4. Verify endpoint đang chạy package của mình**

```bash
curl -k 'https://banking-fraud.ingress-nginx.sas.env/detection/health'
```

Kỳ vọng:

```text
Valid deployment module [QuocRFCBankAsia]
```

Dù URL vẫn là `banking-fraud`, bên trong đã chạy package của bạn.

**5. Gửi message test**

Dùng endpoint này:

```text
https://banking-fraud.ingress-nginx.sas.env/detection/decision/execute
```

Không dùng:

```text
quocrfcbankasia.ingress-nginx.sas.env
```

vì host đó không tồn tại trong lab.

**Ghi nhớ ngắn**

```text
SDA Deploy -> Harbor có image
Harbor image chưa tự chạy
kubectl set image -> đưa image vào SCR runtime
health check -> xác nhận package
curl POST -> test rule/schema
```
