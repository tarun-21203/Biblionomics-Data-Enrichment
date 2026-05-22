import json
import boto3
import os
import csv
import io
import re

s3 = boto3.client('s3')
OUTPUT_BUCKET = os.environ.get('OUTPUT_BUCKET')

def clean_csv_value(value):
    """Clean problematic characters from CSV values"""
    if not isinstance(value, str):
        return value
    
    # Replace problematic quote combinations that break CSV parsing
    value = value.replace('"', '""')  # Escape double quotes properly for CSV
    
    # Remove or replace other problematic characters
    value = re.sub(r'[\r\n\t]', ' ', value)  # Replace newlines and tabs with spaces
    value = re.sub(r'\s+', ' ', value)  # Collapse multiple spaces
    value = value.strip()  # Remove leading/trailing whitespace
    
    return value

# Define the correct field order (from enrich_one_book config.py)
CSV_FIELD_ORDER = [
    # Section A: Source Data (1-35)
    "id",
    "title",
    "primary_author",
    "isbn_13",
    "book_format",
    "cdn_creator",
    "short_description",
    "genre_tags",
    "cover_source",
    "isbn_10",
    "subtitle",
    "series_title",
    "publisher",
    "author_description",
    "awards",
    "bisac_primary_code",
    "bisac_secondary_code",
    "bisac_tertiary_code",
    "bisac_level_1",
    "bisac_level_2",
    "bisac_level_3",
    "bisac_level_4",
    "series_number",
    "volume_number",
    "table_of_contents",
    "all_authors",
    "secondary_author",
    "publication_date",
    "format",
    "long_description",
    "page_count",
    "target_audience",
    "list_price_cad",
    "list_price_usd",
    "reading_level",
    # Section B: Physical Dimensions (36-45)
    "book_height_in",
    "book_height_mm",
    "book_width_in",
    "book_width_mm",
    "spine_thickness_in",
    "spine_thickness_mm",
    "book_weight_lb",
    "book_weight_g",
    "cover_dimensions",
    "book_size_category",
    # Section C: Author Bio Extraction (46-52)
    "author_location_raw",
    "author_province",
    "author_region",
    "author_profession_raw",
    "author_institution",
    "author_bio_richness",
    "author_summary",
    # Section D: Connection Fields (53-60)
    "primary_industry",
    "gift_price_tier",
    "book_length_category",
    "publisher_region",
    "book_themes_bisac",
    "locations_mentioned",
    "time_period_mentioned",
    "corporate_appropriate",
    # Section E: External Sources (61-66)
    "google_books_rating",
    "google_books_rating_count",
    "google_books_available",
    "open_library_available",
    "amazon_ca_url",
    "goodreads_url",
    # Section F: Enrichment Metadata (67-74)
    "enrichment_status",
    "enrichment_date",
    "confidence_score",
    "data_richness",
    "data_sources",
    "fields_populated",
    "verification_status",
    "last_updated",
    # Section G: Extracted Extras (75)
    "extracted_extras",
]

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

    # Find all fields present in the results
    all_fields_in_data = set()
    for row in results:
        all_fields_in_data.update(row.keys())


    # Use ALL fields from our predefined order (this ensures consistent CSV structure)
    ordered_headers = CSV_FIELD_ORDER.copy()
    
    # Add any unexpected fields that aren't in our predefined order (as backup)
    for field in all_fields_in_data:
        if field not in ordered_headers:
            ordered_headers.append(field)
    
    # Clean the data to prevent CSV parsing issues
    cleaned_results = []
    for row in results:
        cleaned_row = {}
        for key, value in row.items():
            cleaned_row[key] = clean_csv_value(value)
        cleaned_results.append(cleaned_row)
    
    # Create CSV in memory with proper quote handling
    csv_buffer = io.StringIO()
    writer = csv.DictWriter(
        csv_buffer, 
        fieldnames=ordered_headers,
        quoting=csv.QUOTE_ALL,  # Quote all fields to handle embedded quotes
        escapechar='\\',        # Use backslash for escaping
        doublequote=True        # Double quotes within quoted fields
    )
    writer.writeheader()
    writer.writerows(cleaned_results)

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