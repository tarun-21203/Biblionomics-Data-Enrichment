# Biblionomics Book Data Enrichment

Biblionomics Data Enrichment is a cloud-native book metadata enrichment pipeline. Given a CSV file containing a list of ISBN-13 numbers, the system queries multiple bibliographic data sources, applies natural language processing to extract structured author metadata, and produces an enriched CSV containing up to 75 fields per book — covering everything from BISAC classifications and pricing to author location, profession, and institutional affiliations.

The system is built on AWS serverless infrastructure. Every operation is handled by short-lived Lambda functions, and retrieving information on ISBNs in parallel is orchestrated through Step Functions. A React-based frontend provides a user interface for uploading ISBN lists, monitoring job progress, and downloading enriched results.

# Deployment

The backend is deployed using AWS SAM, which uses CloudFormation under the hood. All AWS resource definitions are in `backend/template.yaml`.

## Prerequisites

- AWS CLI configured with credentials for the target account (`us-east-1`)
- AWS SAM CLI installed
- A **Google Books API key** — enable the Books API in Google Cloud Console and generate an API key
- A **BiblioShare (Biblionomics) API token** — obtained from BiblioShare/BNC

## samconfig.toml

Create `backend/samconfig.toml` containing deployment configuration and API keys:

```toml
version = 0.1

[default.deploy.parameters]
stack_name = "sam-app"
resolve_s3 = true
s3_prefix = "sam-app"
confirm_changeset = true
capabilities = "CAPABILITY_NAMED_IAM"
parameter_overrides = "Env=\"dev\" ApiKey=\"<your-api-key>\" BiblioShareToken=\"<your-biblioshare-token>\" GoogleBooksApiKey=\"<your-google-books-api-key>\""
image_repositories = []

[default.global.parameters]
region = "us-east-1"
```

| Parameter | Description |
|---|---|
| `Env` | Deployment environment — use `dev` for development |
| `ApiKey` | The `x-api-key` secret that the frontend and API clients must send with every request |
| `BiblioShareToken` | BiblioShare ONIX API token used by `enrich_one_book` to query bibliographic data |
| `GoogleBooksApiKey` | Google Books API key used by `enrich_one_book` for secondary enrichment and reader ratings |

## Build and Deploy

Run from the `backend/` directory:

```bash
cd backend
python3 -m venv env
source env/bin/activate
sam build && sam deploy
```

SAM will package all Lambda functions, upload them to S3, and create or update the `sam-app` CloudFormation stack. On first deployment this provisions all resources (API Gateway, Lambda functions, Step Functions, DynamoDB table, S3 buckets, CloudFront distribution, IAM roles). Subsequent deploys update only changed resources.

## Frontend Build and Deploy

After the backend stack is up, build and deploy the React frontend:

```bash
cd frontend
npm install
npm run build
aws s3 sync dist/ s3://biblionomics-frontend-<ENV> --delete
aws cloudfront create-invalidation --distribution-id <distribution_id> --paths "/*"
```

- `biblionomics-frontend-<ENV>` — replace `<ENV>` with the value set for `Env` in `samconfig.toml` (e.g. `dev` or `prod`)
- `<distribution_id>` — the CloudFront distribution ID output by SAM after deploy. Retrieve it with:

```bash
aws cloudformation describe-stacks --stack-name sam-app \
  --query "Stacks[0].Outputs[?OutputKey=='FrontendDistributionId'].OutputValue" \
  --output text
```

Example invalidation command:

```bash
aws cloudfront create-invalidation --distribution-id E1SAZ5O39ZGBCO --paths "/*"
```