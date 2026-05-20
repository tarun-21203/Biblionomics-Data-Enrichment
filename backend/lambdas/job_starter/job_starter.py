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
stepfunctions = boto3.client("stepfunctions")

TABLE_NAME = os.environ["DYNAMODB_TABLE"]
INPUT_BUCKET = os.environ["INPUT_BUCKET"]
STATE_MACHINE_ARN = os.environ.get("STATE_MACHINE_ARN")


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
        header = rows[0] if rows else []
        rows = rows[1:]
        # Assume ISBN is in the first column
        isbns_list = [r[0].strip() for r in rows if r and r[0].strip()]
        total_isbns = len(isbns_list)
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
        "status": "processing",
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

    # Start Step Functions execution
    try:
        stepfunctions.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            name=request_id,
            input=json.dumps({
                "jobId": request_id,
                "isbns": isbns_list
            })
        )
    except Exception as e:
        return _response(500, {"error": f"Failed to start Step Functions execution: {str(e)}"})

    return _response(200, {
        "requestId": request_id,
    "status": "processing",
    "message": "Enrichment request submitted and Step Functions started successfully",
    })


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }