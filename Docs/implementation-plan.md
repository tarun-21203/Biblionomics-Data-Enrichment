# Plan: BIBLIOnomics Enrichment Frontend + APIs

## TL;DR
Build a React frontend with 3 pages (Dashboard, Submit, Enrichment detail) backed by 3 Lambda functions (API Gateway) and DynamoDB. Users upload CSV of ISBNs → backend processes → returns enriched 75-column data. No authentication (single-user demo). Hosted on S3 + CloudFront.

---

## Architecture Overview

```
Frontend (React) → API Gateway → Lambda Functions → DynamoDB
                                      ↓
                                   S3 (CSV storage)
```

**Components:**
- **Frontend**: React SPA hosted on S3 + CloudFront
- **API Layer**: API Gateway (REST)
- **Compute**: 3 Individual Lambda functions (Python)
- **Database**: DynamoDB (single table design)
- **Storage**: 2 S3 buckets (input CSV, output CSV)

---

## Phase 1: Database Design (DynamoDB)

**Table: `enrichment-requests`**

| Field | Type | Description |
|-------|------|-------------|
| `PK` | String | `REQUEST#{requestId}` |
| `SK` | String | `REQUEST#{requestId}` (same as PK for simple key) |
| `requestId` | String | UUID |
| `identifier` | String | User-provided name for request |
| `status` | String | `pending` \| `completed` \| `failed` |
| `createdAt` | String | ISO timestamp |
| `updatedAt` | String | ISO timestamp |
| `inputS3Key` | String | S3 key in input bucket |
| `outputS3Key` | String | S3 key in output bucket (null if pending) |
| `totalIsbns` | Number | Count of ISBNs in input |
| `processedIsbns` | Number | Count of processed ISBNs |
| `enrichmentProgress` | Number | Enrichment progress 0-100% (shown during pending) |
| `inputPresignedUrl` | String | Cached presigned URL for input |
| `inputPresignedUrlExpiry` | Number | Unix timestamp of expiry |
| `outputPresignedUrl` | String | Cached presigned URL for output |
| `outputPresignedUrlExpiry` | Number | Unix timestamp of expiry |
| `notes` | List | Array of note objects with processing details (see below) |

**Notes Schema:**
```json
[
  {
    "timestamp": "2026-03-15T10:02:00Z",
    "type": "info" | "warning" | "error",
    "message": "Missing author_location for ISBN 9780785291909"
  }
]
```

**Access Patterns:**
- Get all requests: Scan table (acceptable for demo scale)
- Get specific request: `PK = REQUEST#{requestId}`

---

## Phase 2: API Design

### API 1: `POST /jobs/begin`
**Lambda**: `JobStarter`

**Request:**
```json
{
  "identifier": "Q1 2026 Book List",
  "csvFile": "<base64 encoded CSV>"
}
```

**Response:**
```json
{
  "requestId": "uuid-123",
  "status": "pending",
  "message": "Enrichment request submitted successfully"
}
```

**Lambda Logic:**
1. Parse CSV (base64), count ISBNs
2. Upload CSV to input bucket: `{requestId}.csv`
3. Create DynamoDB record with status=pending, enrichmentProgress=0
4. (Future: Trigger enrichment Lambda - out of scope)
5. Return requestId

---

### API 2: `GET /jobs/status`
**Lambda**: `GetStatus`

**Query Parameters:**
- `id` (optional): Get specific request by requestId
- `filter` (optional): Fuzzy search by identifier or requestId (case-insensitive, partial match)

**Without params** — returns all requests for user

**With `filter` param** — returns requests where identifier OR requestId contains the filter string

**Response:**
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
      "createdAt": "2026-03-15T10:00:00Z"
    }
  ]
}
```

---

### API 3: `GET /jobs/status?id={requestId}`
**Lambda**: `GetStatus` (same as above, handles both cases)

**Response:**
```json
{
  "requestId": "uuid-123",
  "identifier": "Q1 2026 Book List",
  "status": "pending",
  "totalIsbns": 500,
  "processedIsbns": 234,
  "enrichmentProgress": 47,
  "createdAt": "2026-03-15T10:00:00Z",
  "updatedAt": "2026-03-15T10:05:00Z",
  "inputPresignedUrl": "https://...",
  "outputPresignedUrl": "https://...",
  "isbns": ["9780785291909", "9781234567890", ...],
  "notes": [
    {"timestamp": "2026-03-15T10:02:00Z", "type": "warning", "message": "Missing author_location for ISBN 9780785291909"},
    {"timestamp": "2026-03-15T10:03:00Z", "type": "info", "message": "Fallback to Google Books for ISBN 9781234567890"}
  ]
}
```

**Lambda Logic:**
1. If `id` provided: Get specific item by `PK = REQUEST#{id}`, fetch ISBNs from S3
2. If no `id`: Scan DynamoDB table for all requests
   - If `filter` provided: Filter results where `identifier` or `requestId` contains filter string (case-insensitive)
3. Return cached presigned URLs if still valid (for display purposes)

---

### API 4: `GET /jobs/generate-download?id={requestId}`
**Lambda**: `GenerateDownload`

**Note**: Always requires `id` parameter. Called when user clicks download on Enrichment page.

**Response:**
```json
{
  "inputUrl": "https://s3.amazonaws.com/input-bucket/...",
  "inputExpiresAt": "2026-03-15T10:30:00Z",
  "outputUrl": "https://s3.amazonaws.com/output-bucket/...",
  "outputExpiresAt": "2026-03-15T10:30:00Z"
}
```

Note: `outputUrl` and `outputExpiresAt` are null if status is pending.

**Lambda Logic:**
1. Fetch request from DynamoDB
2. Generate new presigned URLs (30 min expiry) for both input and output (if exists)
3. Update DynamoDB with new cached URLs and expiry timestamps
4. Return URLs

**Frontend Usage:**
- User clicks "Download" → calls this API → browser downloads from presigned URL
- Page also fetches CSV content via presigned URL to display in-page table

---

## Phase 3: Frontend Pages

### Page 1: Dashboard (`/`)

**Features:**
- List all enrichment requests in card/row format
- Each card shows: identifier, status badge, enrichment progress %, date
- Text filter input (filters by identifier)
- Dropdown filter by status (All / Pending / Completed)
- "New Enrichment" button → navigates to `/submit`
- Clicking any request → navigates to `/enrichment/{id}`

**API Calls:**
- On mount: `GET /jobs/status`
- On filter change: `GET /jobs/status?filter={searchText}`
- Poll every 10 seconds for updates (or use manual refresh button)

**UI Components:**
- SearchInput, StatusFilter (dropdown), RequestCard, NewRequestButton

---

### Page 2: Submit Enrichment (`/submit`)

**Features:**
- Text input for identifier (optional)
- File picker for CSV (accept=".csv")
- Submit button (disabled until file selected)
- Success state: shows "Uploaded successfully!" + "Check Status" button
- "Check Status" navigates to `/enrichment/{requestId}`

**API Calls:**
- On submit: `POST /jobs/begin`

**UI Components:**
- IdentifierInput, FilePicker, SubmitButton, SuccessMessage

---

### Page 3: Enrichment Detail (`/enrichment/:id`)

**Features:**
- Header with identifier and status badge
- Enrichment progress bar (0-100%) shown during pending state
- Progress info (processedIsbns / totalIsbns)
- **Notes section**: Display processing notes (warnings, errors, info) with timestamps
- CSV content displayed in-page as table (fetched via presigned URL)
- Download buttons:
  - "Download Input CSV" (always available)
  - "Download Output CSV" (only if completed)
- Back button to Dashboard

**API Calls:**
- On mount: `GET /jobs/status?id={id}`
- Poll every 5 seconds while status=pending
- On download click: `GET /jobs/generate-download?id={id}` → then fetch CSV from presigned URL

**UI Components:**
- StatusBadge, EnrichmentProgressBar, NotesPanel, DownloadButton, CsvTable, BackButton

---

## Phase 4: Infrastructure (AWS)

**Resources to create:**
1. **S3 Bucket (Input)**: `biblionomics-enrichment-input-{env}`
   - Folder structure: `{requestId}.csv`
   - Private (no public access)
   - CORS configured for presigned URL downloads

2. **S3 Bucket (Output)**: `biblionomics-enrichment-output-{env}`
   - Folder structure: `{requestId}.csv`
   - Private (no public access)
   - CORS configured for presigned URL downloads

3. **DynamoDB Table**: `enrichment-requests`
   - Partition key: `PK` (String)
   - Sort key: `SK` (String)

4. **Lambda Functions** (Python 3.11):
   - `JobStarter` — handles `/jobs/begin`
   - `GetStatus` — handles `/jobs/status` and `/jobs/status?id=`
   - `GenerateDownload` — handles `/jobs/generate-download?id=`

5. **API Gateway** (REST):
   - Routes mapped to Lambdas
   - CORS enabled

6. **S3 + CloudFront** for frontend hosting

**Deployment**: Use AWS SAM or CloudFormation template

---

## Steps

### Backend (can run in parallel)
1. Create DynamoDB table with schema above
2. Create two S3 buckets (input and output) with proper CORS config
3. Implement `JobStarter` Lambda
   - Parse base64 CSV
   - Upload to S3 input bucket
   - Create DynamoDB record
4. Implement `GetStatus` Lambda (handles both list and single request modes)
5. Implement `GenerateDownload` Lambda — generates presigned URLs and updates DynamoDB
6. Create API Gateway and connect routes (`/jobs/begin`, `/jobs/status`, `/jobs/generate-download`)
7. Create SAM/CloudFormation template

### Frontend (*depends on API definitions from backend*)
8. Initialize React project (Vite + React)
9. Set up routing (react-router-dom): `/`, `/submit`, `/enrichment/:id`
10. Create shared components: StatusBadge, ProgressBar, Layout
11. Implement Dashboard page with filtering
12. Implement Submit page with file upload
13. Implement Enrichment detail page with polling + inline CSV display
14. Add API service layer (axios/fetch wrapper)
15. Build and deploy to S3 + CloudFront

### Integration & Testing
16. Test full flow: upload CSV → view in dashboard → view details → download
17. Verify CSV content displays inline on Enrichment page
18. Manual verification with sample CSVs

---

## Relevant Files

*Project structure to create:*

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
│   │   │   ├── ProgressBar.tsx
│   │   │   ├── RequestCard.tsx
│   │   │   └── Layout.tsx
│   │   ├── services/
│   │   │   └── api.ts
│   │   ├── App.tsx
│   │   └── main.tsx
│   └── package.json
├── backend/
│   ├── lambdas/
│   │   ├── job_starter/
│   │   │   └── handler.py
│   │   ├── get_status/
│   │   │   └── handler.py
│   │   └── generate_download/
│   │       └── handler.py
│   └── template.yaml (SAM)
└── docs/
    └── (existing)
```

---

## Verification

1. **Unit tests**: Lambda handlers with mocked DynamoDB/S3
2. **Manual test**: Upload a sample CSV (10 ISBNs), verify it appears in dashboard
3. **Manual test**: Simulate completed status (manually update DynamoDB), verify download works
4. **Manual test**: Verify CSV content displays inline on Enrichment page
5. **Browser test**: Filter by status and text, verify correct filtering
6. **CORS test**: Frontend successfully calls all APIs from CloudFront domain

---

## Decisions

- **Auth**: Skipped for demo (single-user, no authentication)
- **Lambda architecture**: Individual functions per endpoint (no framework)
- **File upload**: Direct base64 in request body (simple, ~6MB limit)
- **Presigned URL TTL**: 30 minutes, cached in DynamoDB
- **Polling interval**: Dashboard 10s, Detail page 5s (while pending)
- **CSV display**: Enrichment page fetches CSV via presigned URL and renders inline
- **Out of scope**: Enrichment processing Lambda (updates status/progress, writes output CSV, calls BiblioShare/Google/OpenLibrary APIs)
- **Out of scope**: Multiple users, user management

---

## Further Considerations

1. **Progress simulation**: Since actual enrichment is out of scope, should we (A) leave status always "pending", (B) add a mock endpoint to update progress, or (C) auto-complete after X seconds? *Recommend B for demo purposes.*