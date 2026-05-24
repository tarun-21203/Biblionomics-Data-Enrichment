import json
import os
import time
import boto3

lambda_client = boto3.client("lambda")

ENRICH_FUNCTION_NAME = os.environ["ENRICH_FUNCTION_NAME"]


def lambda_handler(event, context):
    method = event.get("requestContext", {}).get("http", {}).get("method", "")

    if method == "GET":
        try:
            config = lambda_client.get_function_configuration(FunctionName=ENRICH_FUNCTION_NAME)
            key = config.get("Environment", {}).get("Variables", {}).get("GOOGLE_BOOKS_API_KEY", "")
        except Exception as e:
            return _response(500, {"error": f"Failed to get key: {str(e)}"})
        return _response(200, {"key": key})

    if method == "POST":
        try:
            body = json.loads(event.get("body", "{}"))
        except json.JSONDecodeError:
            return _response(400, {"error": "Invalid JSON body"})

        key = body.get("key", "").strip()
        if not key:
            return _response(400, {"error": "key is required"})

        try:
            config = lambda_client.get_function_configuration(FunctionName=ENRICH_FUNCTION_NAME)
            env_vars = config.get("Environment", {}).get("Variables", {})
            env_vars["GOOGLE_BOOKS_API_KEY"] = key
            for attempt in range(5):
                try:
                    lambda_client.update_function_configuration(
                        FunctionName=ENRICH_FUNCTION_NAME,
                        Environment={"Variables": env_vars},
                    )
                    break
                except lambda_client.exceptions.ResourceConflictException:
                    if attempt == 4:
                        raise
                    time.sleep(3 * (attempt + 1))
        except Exception as e:
            return _response(500, {"error": f"Failed to update key: {str(e)}"})
        return _response(200, {"message": "Google API key updated successfully"})

    return _response(405, {"error": "Method not allowed"})


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }