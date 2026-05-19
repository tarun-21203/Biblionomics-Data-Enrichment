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
    
    if not job_id:
        raise ValueError("Missing jobId")
        
    try:
        table.update_item(
            Key={'requestId': job_id},
            UpdateExpression="SET #status = :status, updatedAt = :updatedAt",
            ExpressionAttributeNames={
                '#status': 'status'
            },
            ExpressionAttributeValues={
                ':status': 'COMPLETED',
                ':updatedAt': datetime.utcnow().isoformat()
            }
        )
    except Exception as e:
        print(f"Error updating DynamoDB: {e}")
        raise e

    return {
        "jobId": job_id,
        "jobStatus": "COMPLETED"
    }