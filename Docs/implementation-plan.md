# Plan: BIBLIOnomics Enrichment Frontend + APIs

## TL;DR
Build a React frontend with 3 pages (Dashboard, Submit, Enrichment detail) backed by 3 Lambda functions (API Gateway) and DynamoDB. Users upload CSV of ISBNs → backend processes → returns enriched 75-column data. No authentication (internal tool). Hosted on S3 + CloudFront.

---

## Architecture Overview

```
Frontend (React) → API Gateway → Lambda Functions → DynamoDB
                                      ↓
                                   S3 (CSV storage)
```

**Components:**
- **Frontend**: React SPA hosted on S3 + CloudFront
- **API Layer**: API Gateway (REST) — protected by API key (`x-api-key` header)
- **Compute**: 3 Individual Lambda functions (Python 3.11)
- **Database**: DynamoDB (single table)
- **Storage**: 2 S3 buckets (input CSV, output CSV) — private, CORS enabled for presigned URLs

---

## Phase 1: Database Design (DynamoDB)

**Table: `enrichment-requests-{env}`**

| Field | Type | Description |
|-------|------|-------------|
| `PK` | String | `{requestId}` (UUID) |
| `SK` | String | `{requestId}` (same as PK) |
| `requestId` | String | UUID |
| `identifier` | String | User-provided name; defaults to requestId if omitted |
| `status` | String | `pending` \| `completed` \| `failed` |
| `createdAt` | String | ISO timestamp |
| `updatedAt` | String | ISO timestamp |
| `inputS3Key` | String | S3 key in input bucket (`{requestId}_input.csv`) |
| `outputS3Key` | String | S3 key in output bucket (null if not completed) |
| `totalIsbns` | Number | Count of ISBNs in input CSV |
| `processedIsbns` | Number | Count of processed ISBNs |
| `enrichmentProgress` | Number | 0–100 |
| `inputPresignedUrl` | String | Cached presigned URL for input CSV |
| `inputPresignedUrlExpiry` | Number | Unix timestamp of expiry |
| `outputPresignedUrl` | String | Cached presigned URL for output CSV |
| `outputPresignedUrlExpiry` | Number | Unix timestamp of expiry |
| `notes` | List | Array of note objects (see below) |

**Notes Schema:**
```json
[
  {
    "timestamp": "2026-03-15T10:02:00Z",
    "type": "info | warning | error",
    "message": "Missing author_location for ISBN 9780785291909"
  }
]
```

**CSV Input Format:**
```
ISBN
9781234567890
9780987654321
```
First row must be header `ISBN` (case-insensitive). Subsequent rows contain one ISBN per row.

---

## Phase 2: API Design

All APIs require header: `x-api-key: <key>`. OPTIONS routes are exempt (CORS preflight).

### API 1: `POST /jobs/begin`
**Lambda file**: `lambdas/job_starter/job_starter.py`

**Request body:**
```json
{
  "identifier": "Q1 2026 Book List",
  "csvFile": "<base64 encoded CSV>"
}
```
- `identifier`: optional; defaults to requestId if blank
- `csvFile`: required; base64-encoded CSV with `ISBN` header

**Response 200:**
```json
{
  "requestId": "uuid-123",
  "status": "pending",
  "message": "Enrichment request submitted successfully"
}
```

**Response 400:** `{ "error": "csvFile is required" }` or `{ "error": "Invalid base64 CSV data" }` or `{ "error": "Could not parse CSV" }`

**Lambda Logic:**
1. Parse base64 CSV, validate, count ISBNs (skips header row)
2. Upload raw CSV bytes to input bucket: `{requestId}_input.csv`
3. Create DynamoDB record with status=`pending`, processedIsbns=0, enrichmentProgress=0
4. Return requestId


---

### API 2: `GET /jobs/status`
**Lambda file**: `lambdas/get_status/get_status.py`

**Query Parameters:**
- `id` (optional): get specific request by requestId
- `filter` (optional): case-insensitive partial match on `identifier` or `requestId`
- `status` (optional): exact match on status (`pending`, `completed`, `failed`)

**Without `id`** — returns list of all requests (sorted newest first):
```json
{
  "requests": [
    {
      "requestId": "uuid-123",
      "identifier": "Q1 2026 Book List",
      "status": "pending",
      "totalIsbns": 500,
      "processedIsbns": 234,
      "enrichmentProgress": 47,
      "createdAt": "2026-03-15T10:00:00Z",
      "updatedAt": "2026-03-15T10:05:00Z",
      "notes": [],
      "inputS3Key": "uuid-123_input.csv",
      "outputS3Key": null,
      "inputPresignedUrl": "https://...",        // only if valid for 60+ seconds
      "inputPresignedUrlExpiry": 1234567890      // only if valid for 60+ seconds
    }
  ]
}
```

**With `id`** — returns single item (same shape as above, plus output presigned URL if valid):

```json
{
  "requestId": "uuid-123",
  "identifier": "Q1 2026 Book List",
  "status": "completed",
  "totalIsbns": 500,
  "processedIsbns": 500,
  "enrichmentProgress": 100,
  "createdAt": "2026-03-15T10:00:00Z",
  "updatedAt": "2026-03-15T10:30:00Z",
  "notes": [...],
  "inputS3Key": "uuid-123_input.csv",
  "outputS3Key": "uuid-123_output.csv",
  "inputPresignedUrl": "https://...",         // only if expiry > now + 60s
  "inputPresignedUrlExpiry": 1234567890,
  "outputPresignedUrl": "https://...",        // only if expiry > now + 60s
  "outputPresignedUrlExpiry": 1234567890
}
```

**Response 404:** `{ "error": "Request not found" }`

---

### API 3: `GET /jobs/generate-download?id={requestId}`
**Lambda file**: `lambdas/generate_download/generate_download.py`

Always requires `id`. Called by frontend when presigned URLs are missing or expired.

**Response 200:**
```json
{
  "inputPresignedUrl": "https://s3.amazonaws.com/input-bucket/...",
  "inputPresignedUrlExpiry": 1234567890,
  "outputPresignedUrl": "https://s3.amazonaws.com/output-bucket/...",
  "outputPresignedUrlExpiry": 1234567890
}
```
- `outputPresignedUrl` / `outputPresignedUrlExpiry` are `null` if no `outputS3Key` on record
- Only regenerates a URL if the cached one has expired (with 60-second buffer); otherwise returns cached value
- Caches new URLs back to DynamoDB via `put_item`

**Response 400:** `{ "error": "id query parameter is required" }`
**Response 404:** `{ "error": "Request not found" }`

---

## Phase 3: Frontend Presigned URL Flow

### Enrichment Detail page (`/enrichment/:id`)

1. On mount: `GET /jobs/status?id={id}`
2. Check `inputPresignedUrl` — if absent or expiry ≤ now+60s → call `GET /jobs/generate-download?id={id}`, use `inputPresignedUrl` from response
3. If `status === 'completed'`: check `outputPresignedUrl` — if absent or expiry ≤ now+60s → call generate-download (reuse same call if already made), use `outputPresignedUrl` from response
4. Fetch CSV content via `inputPresignedUrl` to display inline table
5. While `status === 'pending'`: poll `GET /jobs/status?id={id}` every 5 seconds

---

## Phase 4: Frontend Pages

### Page 1: Dashboard (`/`)
- List all enrichment requests in a table/card format
- Columns: identifier, status badge, progress %, totalIsbns, createdAt
- Text search input (filters by identifier/requestId)
- Dropdown filter by status (All / Pending / Completed / Failed)
- "New Enrichment" button → `/submit`
- Click row → `/enrichment/{id}`
- Poll every 10 seconds (or manual refresh button)

**API calls:**
- On mount + filter change: `GET /jobs/status?filter={text}&status={status}`

---

### Page 2: Submit (`/submit`)
- Optional identifier text input
- CSV file picker (`accept=".csv"`)


- Submit button (disabled until file selected)
- On submit: encode file as base64, POST to `/jobs/begin`
- Success: show confirmation + "View Status" button → `/enrichment/{requestId}`
- Error: show error message inline

---

### Page 3: Enrichment Detail (`/enrichment/:id`)
- Header: identifier + status badge
- Progress bar (0–100%) while pending
- Progress text: `{processedIsbns} / {totalIsbns} ISBNs`
- Notes panel (warnings/errors/info with timestamps)
- Inline CSV table (fetched via input presigned URL)


- Download buttons:
  - "Download Input CSV" (always)
  - "Download Output CSV" (only if completed)
- Back button to Dashboard
- Poll every 5s while status=pending

---

## Phase 5: Infrastructure (AWS SAM)

**Template**: `backend/template.yaml`

| Resource | Name |
|---|---|
| S3 Input | `biblionomics-enrichment-input-{env}` |
| S3 Output | `biblionomics-enrichment-output-{env}` |
| DynamoDB | `enrichment-requests-{env}` |
| Lambda | `biblionomics-job-starter-{env}` → `job_starter.lambda_handler` |
| Lambda | `biblionomics-get-status-{env}` → `get_status.lambda_handler` |
| Lambda | `biblionomics-generate-download-{env}` → `generate_download.lambda_handler` |
| API GW | `biblionomics-api-{env}` — API key required, OPTIONS exempt |


**Deploy:**
```bash
sam build && sam deploy --guided
aws apigateway get-api-key --api-key <ApiKeyId> --include-value
```

---

## Project Structure

```
biblionomics-enrich/
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── Submit.tsx
│   │   │   └── EnrichmentDetail.tsx
│   │   ├── components/
│   │   │   ├── StatusBadge.tsx
│   │   │   └── Layout.tsx
│   │   ├── services/
│   │   │   └── api.ts
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── index.html
│   ├── package.json
│   └── vite.config.ts
├── backend/
│   ├── lambdas/
│   │   ├── job_starter/job_starter.py
│   │   ├── get_status/get_status.py
│   │   └── generate_download/generate_download.py
│   └── template.yaml
└── docs/

```

---

## Decisions

- **Auth**: API key in `x-api-key` header (internal tool, acceptable exposure)
- **Lambda architecture**: Individual files per endpoint, no framework
- **File upload**: Base64 in request body (~6MB limit, sufficient for ISBN CSVs)
- **Presigned URL TTL**: 30 minutes, cached in DynamoDB, checked with 60s buffer
- **Polling**: Dashboard 10s, Detail page 5s while pending
- **CSV display**: Detail page fetches via presigned URL, renders inline table
- **Out of scope**: Enrichment processing Lambda, multiple users, authentication