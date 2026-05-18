#!/bin/bash
set -e

ENV=${1:-dev}
BUCKET="biblionomics-frontend-${ENV}"

echo "Building frontend..."
npm run build

echo "Syncing to s3://${BUCKET}..."
aws s3 sync dist/ "s3://${BUCKET}" --delete

echo "Fetching CloudFront distribution ID..."
DIST_ID=$(aws cloudformation describe-stacks --stack-name sam-app \
  --query "Stacks[0].Outputs[?OutputKey=='FrontendDistributionId'].OutputValue" \
  --output text)

echo "Invalidating CloudFront cache (${DIST_ID})..."
aws cloudfront create-invalidation --distribution-id "$DIST_ID" --paths "/*"

echo "Done. Site live at:"
aws cloudformation describe-stacks --stack-name sam-app \
  --query "Stacks[0].Outputs[?OutputKey=='FrontendUrl'].OutputValue" \
  --output text