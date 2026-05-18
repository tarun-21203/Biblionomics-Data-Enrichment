import json
import os
from decimal import Decimal
import csv
import io
import boto3
from botocore.exceptions import ClientError
import time

class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return int(o) if o % 1 == 0 else float(o)
        return super().default(o)

dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")

TABLE_NAME = os.environ["DYNAMODB_TABLE"]
INPUT_BUCKET = os.environ["INPUT_BUCKET"]


def lambda_handler(event, context):
    params = event.get("queryStringParameters") or {}
    request_id = params.get("id")
    filter_text = params.get("filter", "").strip().lower()
    status_filter = params.get("status", "").strip().lower()

    table = dynamodb.Table(TABLE_NAME)

    if request_id:
        return get_single(table, request_id)
    else:
        return get_all(table, filter_text, status_filter)

def get_payload(item):
    payload = {
        "requestId": item["requestId"],
        "identifier": item.get("identifier", ""),
        "status": item.get("status", ""),
        "totalIsbns": item.get("totalIsbns", 0),
        "processedIsbns": item.get("processedIsbns", 0),
        "enrichmentProgress": item.get("enrichmentProgress", 0),
        "createdAt": item.get("createdAt", ""),
        "updatedAt": item.get("updatedAt", ""),
        "notes": item.get("notes", []),
        "inputS3Key": item.get("inputS3Key", None),
        "outputS3Key": item.get("outputS3Key", None),
        "inputPresignedUrl": None,
        "inputPresignedUrlExpiry": None,
        "outputPresignedUrl": None,
        "outputPresignedUrlExpiry": None,
    }
    now_unix = int(time.time())
    if (item.get("inputPresignedUrlExpiry") or 0) > now_unix + 60:
        payload["inputPresignedUrl"] = item.get("inputPresignedUrl")
        payload["inputPresignedUrlExpiry"] = item.get("inputPresignedUrlExpiry")
    if (item.get("outputPresignedUrlExpiry") or 0) > now_unix + 60:
        payload["outputPresignedUrl"] = item.get("outputPresignedUrl")
        payload["outputPresignedUrlExpiry"] = item.get("outputPresignedUrlExpiry")
    return payload

def get_single(table, request_id):
    try:
        result = table.get_item(Key={"requestId": request_id})
    except ClientError as e:
        return _response(500, {"error": str(e)})

    item = result.get("Item")
    if not item:
        return _response(404, {"error": "Request not found"})

    return _response(200, get_payload(item))

def get_all(table, filter_text, status_filter):
    try:
        result = table.scan()
        items = result.get("Items", [])

        # Handle pagination
        while "LastEvaluatedKey" in result:
            result = table.scan(ExclusiveStartKey=result["LastEvaluatedKey"])
            items.extend(result.get("Items", []))
    except ClientError as e:
        return _response(500, {"error": str(e)})

    requests = []
    for item in items:
        if status_filter and item.get("status", "").lower() != status_filter:
            continue
        if filter_text:
            if (
                filter_text not in item.get("identifier", "").lower()
                and filter_text not in item.get("requestId", "").lower()
            ):
                continue
        requests.append(get_payload(item))
    requests.sort(key=lambda x: x.get("createdAt", ""), reverse=True)
    return _response(200, {"requests": requests})


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "OPTIONS,GET",
        },
        "body": json.dumps(body, cls=DecimalEncoder),
    }