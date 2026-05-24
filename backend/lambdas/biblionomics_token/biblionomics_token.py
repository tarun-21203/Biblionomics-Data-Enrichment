import json
import os
import time
import boto3

lambda_client = boto3.client("lambda")

ENRICH_FUNCTION_NAME = os.environ["ENRICH_FUNCTION_NAME"]


def lambda_handler(event, context):
    method = event.get("requestContext", {}).get("http", {}).get("method", "")
    path = event.get("requestContext", {}).get("http", {}).get("path", "")

    if method == "GET":
        try:
            config = lambda_client.get_function_configuration(FunctionName=ENRICH_FUNCTION_NAME)
            env = config.get("Environment", {}).get("Variables", {})
        except Exception as e:
            return _response(500, {"error": f"Failed to get config: {str(e)}"})

        if path.endswith("/google-api-key"):
            return _response(200, {"key": env.get("GOOGLE_BOOKS_API_KEY", "")})
        return _response(200, {"biblionomicsApiKey": env.get("BIBLIOSHARE_TOKEN", "")})

    if method == "POST":
        try:
            body = json.loads(event.get("body", "{}"))
        except json.JSONDecodeError:
            return _response(400, {"error": "Invalid JSON body"})

        biblionomics_api_key = body.get("biblionomicsApiKey", "").strip()
        google_api_key = body.get("googleApiKey", "").strip()

        if not biblionomics_api_key and not google_api_key:
            return _response(400, {"error": "biblionomicsApiKey or googleApiKey is required"})

        try:
            config = lambda_client.get_function_configuration(FunctionName=ENRICH_FUNCTION_NAME)
            env_vars = config.get("Environment", {}).get("Variables", {})
            if biblionomics_api_key:
                env_vars["BIBLIOSHARE_TOKEN"] = biblionomics_api_key
            if google_api_key:
                env_vars["GOOGLE_BOOKS_API_KEY"] = google_api_key
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
            return _response(500, {"error": f"Failed to update config: {str(e)}"})
        return _response(200, {"message": "Config updated successfully"})

    return _response(405, {"error": "Method not allowed"})


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }