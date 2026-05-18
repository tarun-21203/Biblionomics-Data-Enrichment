import json
import base64
import uuid
import csv
import io
import os
import time
import boto3

dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")

TABLE_NAME = os.environ["DYNAMODB_TABLE"]
INPUT_BUCKET = os.environ["INPUT_BUCKET"]


def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return _response(400, {"error": "Invalid JSON body"})

    identifier = body.get("identifier", "").strip()
    csv_b64 = body.get("csvFile", "")

    if not csv_b64:
        return _response(400, {"error": "csvFile is required"})

    # Decode CSV
    try:
        csv_bytes = base64.b64decode(csv_b64)
        csv_text = csv_bytes.decode("utf-8")
    except Exception:
        return _response(400, {"error": "Invalid base64 CSV data"})

    # Count ISBNs (non-empty rows, skip header if present)
    try:
        reader = csv.reader(io.StringIO(csv_text))
        rows = [r for r in reader if any(cell.strip() for cell in r)]
        rows = rows[1:]
        total_isbns = len(rows)
    except Exception:
        return _response(400, {"error": "Could not parse CSV"})

    request_id = str(uuid.uuid4())
    now = int(time.time())
    s3_key = f"{request_id}_input.csv"

    # Upload CSV to S3
    try:
        s3.put_object(
            Bucket=INPUT_BUCKET,
            Key=s3_key,
            Body=csv_bytes,
            ContentType="text/csv",
        )
    except Exception as e:
        return _response(500, {"error": f"Failed to upload CSV: {str(e)}"})

    # Create DynamoDB record
    table = dynamodb.Table(TABLE_NAME)
    item = {
        "requestId": request_id,
        "identifier": identifier or request_id,
        "status": "pending",
        "createdAt": now,
        "updatedAt": now,
        "inputS3Key": s3_key,
        "outputS3Key": None,
        "totalIsbns": total_isbns,
        "processedIsbns": 0,
        "inputPresignedUrl": None,
        "inputPresignedUrlExpiry": None,
        "outputPresignedUrl": None,
        "outputPresignedUrlExpiry": None,
        "notes": [],
    }

    try:
        table.put_item(Item=item)
    except Exception as e:
        return _response(500, {"error": f"Failed to create record: {str(e)}"})

    return _response(200, {
        "requestId": request_id,
        "status": "pending",
        "message": "Enrichment request submitted successfully",
    })


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }