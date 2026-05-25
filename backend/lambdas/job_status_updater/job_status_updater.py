import boto3
import os
from datetime import datetime

dynamodb = boto3.resource('dynamodb')
DYNAMODB_TABLE = os.environ.get('DYNAMODB_TABLE')
table = dynamodb.Table(DYNAMODB_TABLE)

def lambda_handler(event, context):
    """
    Expects event from the Results Aggregator:
    {
        "aggregationResult": {
            "jobId": "12345",
            "outputKey": "jobs/12345/results.csv",
            "status": "UPLOADED"
        }
    }
    """
    aggregation_result = event.get('aggregationResult', {})
    job_id = aggregation_result.get('jobId') or event.get('jobId')
    output_key = aggregation_result.get('outputKey')
    status = event.get('status', 'completed')

    if not job_id:
        raise ValueError("Missing jobId")

    # Prepare update expression
    update_expression = "SET #status = :status, updatedAt = :updatedAt"
    expression_attribute_names = {'#status': 'status'}
    expression_attribute_values = {
        ':status': status,
        ':updatedAt': datetime.utcnow().isoformat()
    }

    # Add outputS3Key if provided
    if output_key:
        update_expression += ", outputS3Key = :outputKey"
        expression_attribute_values[':outputKey'] = output_key

    # Set processedIsbns to totalIsbns
    update_expression += ", processedIsbns = totalIsbns"

    try:
        table.update_item(
            Key={'requestId': job_id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values
        )
    except Exception as e:
        print(f"Error updating DynamoDB: {e}")
        raise e

    return {
        "jobId": job_id,
        "jobStatus": "COMPLETED"
    }