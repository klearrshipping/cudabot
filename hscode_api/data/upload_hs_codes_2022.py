import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from supabase import create_client, Client
import csv
from config import SUPABASE_URL, SUPABASE_KEY

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Path to your CSV
csv_file = 'all_hs_codes.csv'

# Read CSV and convert to list of dicts
with open(csv_file, newline='', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    data = [row for row in reader]

# Print first record for debugging
if data:
    print("First record structure:", data[0])

# Convert empty strings to null for better database compatibility
def clean_record(record):
    return {k: (None if v == "" else v) for k, v in record.items()}

# Upload data with error handling
for i, record in enumerate(data):
    try:
        # Clean the record by converting empty strings to null
        cleaned_record = clean_record(record)

        # Rename CSV columns to match Supabase table if needed:
        # Example: 'HS Code' → 'hs_code', 'HS Description' → 'description'
        mapped_record = {
            'hs_code': cleaned_record.get('HS Code'),
            'heading': cleaned_record.get('Heading'),
            'heading_description': cleaned_record.get('Heading Description'),
            'subcategory': cleaned_record.get('Subcategory'),
            'description': cleaned_record.get('HS Description'),
            'source_file': cleaned_record.get('Source File'),
            # tariff_code → can leave None for now
            'tariff_code': None
        }

        # Upload
        response = supabase.table('hs_codes_2022').insert(mapped_record).execute()
        print(f"Successfully uploaded record {i+1}")
    except Exception as e:
        print(f"Error uploading record {i+1}:")
        print(f"Record data: {mapped_record}")
        print(f"Error: {str(e)}")
        break

print("Data upload complete.") 