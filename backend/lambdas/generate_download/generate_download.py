import json
import os
import time
from decimal import Decimal
import boto3
from botocore.exceptions import ClientError

class DecimalSupportedJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return int(o) if o % 1 == 0 else float(o)
        return super().default(o)

dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")

TABLE_NAME = os.environ["DYNAMODB_TABLE"]
INPUT_BUCKET = os.environ["INPUT_BUCKET"]
OUTPUT_BUCKET = os.environ["OUTPUT_BUCKET"]

PRESIGNED_URL_TTL_SECONDS = 1800  # 30 minutes


def lambda_handler(event, context):
    params = event.get("queryStringParameters") or {}
    request_id = params.get("id")

    if not request_id:
        return _response(400, {"error": "id query parameter is required"})

    table = dynamodb.Table(TABLE_NAME)

    try:
        result = table.get_item(Key={"requestId": request_id})
    except ClientError as e:
        return _response(500, {"error": str(e)})

    item = result.get("Item")
    if not item:
        return _response(404, {"error": "Request not found"})

    now_unix = int(time.time())
    expiry_unix = now_unix + PRESIGNED_URL_TTL_SECONDS
    if item.get("inputS3Key") and now_unix > (item.get("inputPresignedUrlExpiry") or 0) + 60:
        try:
            item["inputPresignedUrl"] = s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": INPUT_BUCKET, "Key": item.get("inputS3Key")},
                ExpiresIn=PRESIGNED_URL_TTL_SECONDS,
            )
            item["inputPresignedUrlExpiry"] = expiry_unix
        except ClientError as e:
            return _response(500, {"error": f"Failed to generate input URL: {str(e)}"})
    if item.get("outputS3Key") and now_unix > (item.get("outputPresignedUrlExpiry") or 0) + 60:
        try:
            item["outputPresignedUrl"] = s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": OUTPUT_BUCKET, "Key": item.get("outputS3Key")},
                ExpiresIn=PRESIGNED_URL_TTL_SECONDS,
            )
            item["outputPresignedUrlExpiry"] = expiry_unix  
        except ClientError as e:
            return _response(500, {"error": f"Failed to generate output URL: {str(e)}"})

    # Cache URLs in DynamoDB
    try:
        table.put_item(Item=item)
    except ClientError as e:
        return _response(500, {"error": f"Failed to update item with URLs: {str(e)}"})

    return _response(200, {
        "inputPresignedUrl": item.get("inputPresignedUrl"),
        "inputPresignedUrlExpiry": item.get("inputPresignedUrlExpiry"),
        "outputPresignedUrl": item.get("outputPresignedUrl"),
        "outputPresignedUrlExpiry": item.get("outputPresignedUrlExpiry"),
    })


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, cls=DecimalSupportedJSONEncoder),
    }