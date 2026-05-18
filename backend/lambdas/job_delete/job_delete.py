import json
import os

import boto3

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["DYNAMODB_TABLE"])
s3 = boto3.client("s3")

HEADERS = {"Content-Type": "application/json"}


def resp(status, body):
    return {"statusCode": status, "headers": HEADERS, "body": json.dumps(body)}


def lambda_handler(event, context):
    params = event.get("queryStringParameters") or {}
    request_id = params.get("id")

    if not request_id:
        return resp(400, {"error": "id query parameter is required"})

    try:
        result = table.get_item(Key={"requestId": request_id})
    except Exception as e:
        return resp(500, {"error": str(e)})

    item = result.get("Item")
    if not item:
        return resp(404, {"error": "Request not found"})

    input_bucket = os.environ["INPUT_BUCKET"]
    output_bucket = os.environ["OUTPUT_BUCKET"]

    if item.get("inputS3Key"):
        try:
            s3.delete_object(Bucket=input_bucket, Key=item["inputS3Key"])
        except Exception:
            pass

    if item.get("outputS3Key"):
        try:
            s3.delete_object(Bucket=output_bucket, Key=item["outputS3Key"])
        except Exception:
            pass

    table.delete_item(Key={"requestId": request_id})

    return resp(200, {"message": "Request deleted successfully"})