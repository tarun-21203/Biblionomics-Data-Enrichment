import json
import boto3
import os
import csv
import io

s3 = boto3.client('s3')
OUTPUT_BUCKET = os.environ.get('OUTPUT_BUCKET')

def lambda_handler(event, context):
    """
    Expects event payload format from Step Functions Map State:
    {
        "jobId": "12345",
        "enrichmentResults": [
            { "isbn_13": "...", "title": "...", ... },
            { ... }
        ]
    }
    """
    job_id = event.get('jobId')
    results = event.get('enrichmentResults', [])
    
    if not job_id or not results:
        raise ValueError("Missing jobId or enrichmentResults")
    
    # Extract all possible CSV headers from the results
    headers = set()
    for row in results:
        headers.update(row.keys())
    headers = list(headers)
    
    # Create CSV in memory
    csv_buffer = io.StringIO()
    writer = csv.DictWriter(csv_buffer, fieldnames=headers)
    writer.writeheader()
    writer.writerows(results)
    
    # Upload to S3 Output Bucket
    output_key = f"jobs/{job_id}/results.csv"
    
    s3.put_object(
        Bucket=OUTPUT_BUCKET,
        Key=output_key,
        Body=csv_buffer.getvalue(),
        ContentType='text/csv'
    )
    
    return {
        "jobId": job_id,
        "outputKey": output_key,
        "status": "UPLOADED"
    }