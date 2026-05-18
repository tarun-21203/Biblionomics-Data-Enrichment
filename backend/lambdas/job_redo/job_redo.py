import json
import os
import time

import boto3

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["DYNAMODB_TABLE"])

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

    if item.get("status") == "pending":
        return resp(400, {"error": "Request is already in pending state"})

    table.update_item(
        Key={"requestId": request_id},
        UpdateExpression="SET #s = :s, processedIsbns = :z, updatedAt = :t",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":s": "pending", ":z": 0, ":t": int(time.time())},
    )

    return resp(200, {"requestId": request_id, "status": "pending", "message": "Job reset to pending"})