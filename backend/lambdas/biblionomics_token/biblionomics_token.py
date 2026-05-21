import json
import os
import boto3

lambda_client = boto3.client("lambda")

ENRICH_FUNCTION_NAME = os.environ["ENRICH_FUNCTION_NAME"]


def lambda_handler(event, context):
    method = event.get("requestContext", {}).get("http", {}).get("method", "")

    if method == "GET":
        try:
            config = lambda_client.get_function_configuration(FunctionName=ENRICH_FUNCTION_NAME)
            token = config.get("Environment", {}).get("Variables", {}).get("BIBLIOSHARE_TOKEN", "")
        except Exception as e:
            return _response(500, {"error": f"Failed to get token: {str(e)}"})
        return _response(200, {"token": token})

    if method == "POST":
        try:
            body = json.loads(event.get("body", "{}"))
        except json.JSONDecodeError:
            return _response(400, {"error": "Invalid JSON body"})

        token = body.get("token", "").strip()
        if not token:
            return _response(400, {"error": "token is required"})

        try:
            config = lambda_client.get_function_configuration(FunctionName=ENRICH_FUNCTION_NAME)
            env_vars = config.get("Environment", {}).get("Variables", {})
            env_vars["BIBLIOSHARE_TOKEN"] = token
            lambda_client.update_function_configuration(
                FunctionName=ENRICH_FUNCTION_NAME,
                Environment={"Variables": env_vars},
            )
        except Exception as e:
            return _response(500, {"error": f"Failed to update token: {str(e)}"})
        return _response(200, {"message": "Token updated successfully"})

    return _response(405, {"error": "Method not allowed"})


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }