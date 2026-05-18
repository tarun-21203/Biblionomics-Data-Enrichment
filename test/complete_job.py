#!/usr/bin/env python3
"""
Usage:
    python complete_job.py <request-id> --output-csv <path/to/file.csv>

Uploads the CSV to the output S3 bucket and marks the DynamoDB enrichment
request as completed.
"""
import argparse
import os
import time
import boto3
from botocore.exceptions import ClientError

ENV = os.environ.get("ENV", "dev")
TABLE_NAME = f"enrichment-requests-{ENV}"
OUTPUT_BUCKET = f"biblionomics-enrichment-output-{ENV}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("request_id", help="The enrichment request ID")
    parser.add_argument("--output-csv", required=True, help="Path to the output CSV file")
    args = parser.parse_args()

    request_id = args.request_id
    csv_path = args.output_csv
    s3_key = f"{request_id}_output.csv"

    if not os.path.exists(csv_path):
        print(f"Error: file not found: {csv_path}")
        exit(1)

    s3 = boto3.client("s3")
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(TABLE_NAME)

    # Upload CSV to output bucket
    print(f"Uploading {csv_path} → s3://{OUTPUT_BUCKET}/{s3_key}")
    try:
        s3.upload_file(csv_path, OUTPUT_BUCKET, s3_key, ExtraArgs={"ContentType": "text/csv"})
    except ClientError as e:
        print(f"S3 upload failed: {e}")
        exit(1)

    # Update DynamoDB record
    print(f"Updating DynamoDB record {request_id} → completed")
    try:
        table.update_item(
            Key={"requestId": request_id},
            UpdateExpression="SET #s = :s, outputS3Key = :k, updatedAt = :t, processedIsbns = totalIsbns",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":s": "completed",
                ":k": s3_key,
                ":t": int(time.time()),
            },
        )
    except ClientError as e:
        print(f"DynamoDB update failed: {e}")
        exit(1)

    print("Done.")


if __name__ == "__main__":
    main()