import csv
import io
import json
import os
import time

import boto3

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["DYNAMODB_TABLE"])
s3 = boto3.client("s3")
stepfunctions = boto3.client("stepfunctions")

INPUT_BUCKET = os.environ["INPUT_BUCKET"]
STATE_MACHINE_ARN = os.environ["STATE_MACHINE_ARN"]

HEADERS = {"Content-Type": "application/json"}


def resp(status, body):
    return {"statusCode": status, "headers": HEADERS, "body": json.dumps(body)}


def lambda_handler(event, context):
    body = json.loads(event.get("body") or "{}")
    request_id = body.get("requestId")

    if not request_id:
        return resp(400, {"error": "requestId is required"})

    try:
        result = table.get_item(Key={"requestId": request_id})
    except Exception as e:
        return resp(500, {"error": str(e)})

    item = result.get("Item")
    if not item:
        return resp(404, {"error": "Request not found"})

    if item.get("status") == "processing":
        return resp(400, {"error": "Job is already processing"})

    # Read ISBNs from original input CSV in S3
    input_key = item.get("inputS3Key")
    if not input_key:
        return resp(400, {"error": "No input CSV found for this job"})

    try:
        s3_obj = s3.get_object(Bucket=INPUT_BUCKET, Key=input_key)
        csv_text = s3_obj["Body"].read().decode("utf-8")
        reader = csv.reader(io.StringIO(csv_text))
        rows = [r for r in reader if any(cell.strip() for cell in r)]
        isbns_list = [r[0].strip() for r in rows[1:] if r and r[0].strip()]
    except Exception as e:
        return resp(500, {"error": f"Failed to read input CSV: {str(e)}"})

    if not isbns_list:
        return resp(400, {"error": "No ISBNs found in input CSV"})

    # Reset DynamoDB record
    table.update_item(
        Key={"requestId": request_id},
        UpdateExpression="SET #s = :s, processedIsbns = :z, updatedAt = :t, outputS3Key = :n, outputPresignedUrl = :n, outputPresignedUrlExpiry = :n, inputPresignedUrl = :n, inputPresignedUrlExpiry = :n",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":s": "processing",
            ":z": 0,
            ":t": int(time.time()),
            ":n": None,
        },
    )

    # Re-trigger Step Functions
    try:
        stepfunctions.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            name=f"{request_id}-redo-{int(time.time())}",
            input=json.dumps({"jobId": request_id, "isbns": isbns_list}),
        )
    except Exception as e:
        return resp(500, {"error": f"Failed to start Step Functions execution: {str(e)}"})

    return resp(200, {"requestId": request_id, "status": "processing", "message": "Job restarted successfully"})