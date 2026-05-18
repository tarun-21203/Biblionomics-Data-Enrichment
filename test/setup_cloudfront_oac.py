#!/usr/bin/env python3
"""
Attaches OAC to the CloudFront distribution and adds the bucket policy.
Run once after initial deployment.
"""
import json
import boto3

DIST_ID = "E1SAZ5O39ZGBCO"
OAC_ID = "ERQYDF2BBU3BO"
BUCKET = "biblionomics-frontend-dev"
ORIGIN_ID = "s3-origin"

cf = boto3.client("cloudfront")
s3 = boto3.client("s3")
sts = boto3.client("sts")

account_id = sts.get_caller_identity()["Account"]

# 1. Update CloudFront distribution to use OAC
print("Fetching distribution config...")
resp = cf.get_distribution_config(Id=DIST_ID)
etag = resp["ETag"]
config = resp["DistributionConfig"]

for origin in config["Origins"]["Items"]:
    if origin["Id"] == ORIGIN_ID:
        origin["OriginAccessControlId"] = OAC_ID
        origin["S3OriginConfig"] = {"OriginAccessIdentity": ""}
        break

print("Updating distribution with OAC...")
cf.update_distribution(Id=DIST_ID, IfMatch=etag, DistributionConfig=config)

# 2. Add bucket policy
print("Adding bucket policy...")
policy = {
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": {"Service": "cloudfront.amazonaws.com"},
        "Action": "s3:GetObject",
        "Resource": f"arn:aws:s3:::{BUCKET}/*",
        "Condition": {
            "StringEquals": {
                "AWS:SourceArn": f"arn:aws:cloudfront::{account_id}:distribution/{DIST_ID}"
            }
        }
    }]
}
s3.put_bucket_policy(Bucket=BUCKET, Policy=json.dumps(policy))

print("Done. Wait ~5 minutes for CloudFront to deploy, then invalidate cache:")
print(f"  aws cloudfront create-invalidation --distribution-id {DIST_ID} --paths '/*'")