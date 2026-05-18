# API Test Commands

```bash
export API=https://ytvmzukual.execute-api.us-east-1.amazonaws.com/dev
export KEY=rzNQ6SfzWd318eDXhLtTta5a3eMP4SAi4K16h23S
```

---

## POST /jobs/begin

```bash
curl -s -X POST "$API/jobs/begin" \
  -H "x-api-key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "identifier": "Test Batch",
    "csvFile": "'$(echo -e "ISBN\n9781234567890\n9780987654321" | base64 -w 0)'"
  }' | jq
```

# Update DynamoDB record
aws dynamodb update-item \
  --table-name enrichment-requests-dev \
  --key '{"requestId": {"S": "4339ba7e-e53e-4f84-baa9-77dca28df0cc"}}' \
  --update-expression "SET outputS3Key = :oKey, #s = :status, processedIsbns = :p, enrichmentProgress = :prog" \
  --expression-attribute-names '{"#s": "status"}' \
  --expression-attribute-values '{
    ":oKey": {"S": "4339ba7e-e53e-4f84-baa9-77dca28df0cc_output.csv"},
    ":status": {"S": "completed"},
    ":p": {"N": "2"},
    ":prog": {"N": "100"}
  }'


---

## GET /jobs/status — all requests

```bash
curl -s "$API/jobs/status" \
  -H "x-api-key: $KEY" | jq
```

## GET /jobs/status — filter by text

```bash
curl -s "$API/jobs/status?filter=Test" \
  -H "x-api-key: $KEY" | jq
```

## GET /jobs/status — filter by status

```bash
curl -s "$API/jobs/status?status=pending" \
  -H "x-api-key: $KEY" | jq
```

## GET /jobs/status — single request

```bash
curl -s "$API/jobs/status?id=<requestId>" \
  -H "x-api-key: $KEY" | jq
```

---

## GET /jobs/generate-download

```bash
curl -s "$API/jobs/generate-download?id=ecde8013-bcd9-4a56-840b-b7c3d27e5b17" \
  -H "x-api-key: $KEY" | jq
```

---

## Test missing API key (expect 403)

```bash
curl -s "$API/jobs/status" | jq
```

### Redeploy frontend

```
cd ../frontend
npm run build
aws s3 sync dist/ s3://biblionomics-frontend-dev --delete
aws cloudfront create-invalidation --distribution-id E1SAZ5O39ZGBCO --paths '/*'
```