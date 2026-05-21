# CLAUDE.md — Project Notes

## SAM Deploy: Fixing ResourceExistenceCheck / Changeset Failures

### Symptom
```
Waiter ChangeSetCreateComplete failed: ... Status: FAILED
Reason: The following hook(s)/validation failed: [AWS::EarlyValidation::ResourceExistenceCheck]
```
This means CloudFormation found a named resource in your template that already exists in AWS **outside** the stack (created manually or from a previous deploy that wasn't tracked).

---

### Step 1 — Find what's actually in the stack vs what's new

```bash
aws cloudformation list-stack-resources --stack-name sam-app \
  --query 'StackResourceSummaries[*].[LogicalResourceId,PhysicalResourceId,ResourceStatus]' \
  --output table
```

Compare against the template — any resource in the template **not** in that list is "new" and a candidate for conflict.

---

### Step 2 — Check which new resources already exist in AWS

```bash
# Lambdas
aws lambda get-function --function-name <name> 2>&1 | grep -E "FunctionName|ResourceNotFoundException"

# S3 buckets
aws s3api head-bucket --bucket <name> 2>&1

# IAM roles
aws iam get-role --role-name <name> 2>&1

# Step Functions
aws stepfunctions describe-state-machine --state-machine-arn arn:aws:states:us-east-1:<account>:stateMachine:<name> 2>&1

# CloudFront
aws cloudfront list-distributions --query "DistributionList.Items[?contains(Origins.Items[0].DomainName, '<keyword>')].[Id,DomainName]" --output table
```

---

### Step 3a — Stateless resources (lambdas, IAM roles): just delete and redeploy

```bash
aws lambda delete-function --function-name <name>
aws iam delete-role --role-name <name>
sam build && sam deploy
```

---

### Step 3b — Stateful resources (S3 buckets with data, CloudFront): import into the stack

CloudFormation resource import lets you adopt existing resources without recreating them.

#### Rules for import changesets:
1. Only add new resources — **cannot modify or add Outputs** in the same changeset
2. All imported resources **must have `DeletionPolicy: Retain`**
3. The template must use **fully processed JSON** (not SAM YAML with local CodeUri paths) — use the currently deployed template as the base
4. Parameters must match exactly what's already on the stack

#### Process:

**Get the currently deployed template (use this as your base — do NOT use template.yaml directly):**
```bash
aws cloudformation get-template --stack-name sam-app --template-stage Original \
  --query TemplateBody --output text > /tmp/current-template.yaml
```

**Or get fully processed JSON (safer — avoids SAM transform issues):**
```bash
aws cloudformation get-template --stack-name sam-app --template-stage Processed \
  > /tmp/processed-raw.json
# Then use Python to parse TemplateBody dict and add new resources
python3 -c "
import json
t = json.load(open('/tmp/processed-raw.json'))['TemplateBody']
t['Resources']['NewResource'] = { ... }
json.dump(t, open('/tmp/import-template.json', 'w'), indent=2)
"
```

**Create the import resources file:**
```json
[
  {
    "ResourceType": "AWS::S3::Bucket",
    "LogicalResourceId": "FrontendBucket",
    "ResourceIdentifier": { "BucketName": "actual-bucket-name" }
  },
  {
    "ResourceType": "AWS::CloudFront::Distribution",
    "LogicalResourceId": "FrontendDistribution",
    "ResourceIdentifier": { "Id": "DISTRIBUTION_ID" }
  },
  {
    "ResourceType": "AWS::CloudFront::OriginAccessControl",
    "LogicalResourceId": "FrontendOAC",
    "ResourceIdentifier": { "Id": "OAC_ID" }
  },
  {
    "ResourceType": "AWS::S3::BucketPolicy",
    "LogicalResourceId": "FrontendBucketPolicy",
    "ResourceIdentifier": { "Bucket": "actual-bucket-name" }
  }
]
```

**Run the import:**
```bash
aws cloudformation create-change-set \
  --stack-name sam-app \
  --change-set-name import-resources \
  --change-set-type IMPORT \
  --resources-to-import file://import-resources.json \
  --template-body file://import-template.json \
  --parameters ParameterKey=Env,UsePreviousValue=true ParameterKey=ApiKey,UsePreviousValue=true \
  --capabilities CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND

aws cloudformation wait change-set-create-complete \
  --stack-name sam-app --change-set-name import-resources

aws cloudformation execute-change-set \
  --stack-name sam-app --change-set-name import-resources

aws cloudformation wait stack-import-complete --stack-name sam-app
```

---

### Common import failure messages and fixes

| Error | Fix |
|-------|-----|
| `'CodeUri' is not a valid S3 Uri` | Use processed template (post-build), not local SAM YAML |
| `cannot modify or add [Outputs]` | Remove any new/changed Outputs from the import template |
| `resources must have DeletionPolicy` | Add `DeletionPolicy: Retain` to every resource being imported |
| `cannot modify resources not being imported` | Use the exact currently-deployed template as base — don't change existing resources |
| `BiblioShareToken usePreviousValue=true` not valid | Parameter wasn't in previous template; pass the value explicitly |

---

### After import: run normal sam deploy

Once resources are adopted into the stack, `sam deploy` works normally to add/update everything else.

```bash
PATH="$PWD/env/bin:$PATH" sam build && sam deploy
```

> **Note:** Use `PATH="$PWD/env/bin:$PATH"` prefix — the project has a venv at `backend/env/` with pip. System pip is not installed.

---

## Deploying Lambda Changes Without sam deploy

```bash
cd backend/lambdas/<function_name>
zip function.zip <handler>.py

# Update existing function
aws lambda update-function-code \
  --function-name <function-name> \
  --zip-file fileb://function.zip

# Create new function
aws lambda create-function \
  --function-name <name> \
  --runtime python3.12 \
  --role arn:aws:iam::163771015590:role/biblionomics-lambda-role-dev \
  --handler <file>.<handler> \
  --zip-file fileb://function.zip \
  --environment Variables="{KEY=value}"
```

---

## Adding API Gateway Routes Without sam deploy

```bash
API_ID=ytvmzukual

# 1. Create integration
INTEGRATION_ID=$(aws apigatewayv2 create-integration \
  --api-id $API_ID \
  --integration-type AWS_PROXY \
  --integration-uri <lambda-arn> \
  --payload-format-version 2.0 \
  --query 'IntegrationId' --output text)

# 2. Get authorizer ID
AUTHORIZER_ID=$(aws apigatewayv2 get-authorizers --api-id $API_ID \
  --query 'Items[0].AuthorizerId' --output text)

# 3. Create route
aws apigatewayv2 create-route \
  --api-id $API_ID \
  --route-key "POST /my-route" \
  --target "integrations/$INTEGRATION_ID" \
  --authorization-type CUSTOM \
  --authorizer-id $AUTHORIZER_ID

# 4. Grant invoke permission
aws lambda add-permission \
  --function-name <name> \
  --statement-id apigw-invoke \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:us-east-1:163771015590:$API_ID/*/*/my-route"
```

---

## Updating CloudFront (Frontend Deploy)

```bash
cd frontend
npm run build
aws s3 sync dist/ s3://biblionomics-frontend-dev --delete
aws cloudfront create-invalidation --distribution-id E1SAZ5O39ZGBCO --paths "/*"
```

---

## Key Resource IDs (dev environment)

| Resource | ID / Name |
|----------|-----------|
| Stack | `sam-app` |
| API Gateway | `ytvmzukual` |
| CloudFront Distribution | `E1SAZ5O39ZGBCO` |
| CloudFront OAC | `ERQYDF2BBU3BO` |
| Frontend S3 Bucket | `biblionomics-frontend-dev` |
| Input S3 Bucket | `biblionomics-enrichment-input-dev` |
| Output S3 Bucket | `biblionomics-enrichment-output-dev` |
| DynamoDB Table | `enrichment-requests-dev` |
| Lambda Role | `biblionomics-lambda-role-dev` |
| AWS Account | `163771015590` |
| Region | `us-east-1` |