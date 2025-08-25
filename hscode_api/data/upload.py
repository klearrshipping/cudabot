from supabase import create_client, Client
import json
from config import SUPABASE_URL, SUPABASE_KEY

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Load JSON
with open('tariff_code.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Print first record for debugging
if data:
    print("First record structure:", json.dumps(data[0], indent=2))

# Convert empty strings to null for better database compatibility
def clean_record(record):
    return {k: (None if v == "" else v) for k, v in record.items()}

# Upload data with error handling
for i, record in enumerate(data):
    try:
        # Clean the record by converting empty strings to null
        cleaned_record = clean_record(record)
        response = supabase.table('tariff_codes').insert(cleaned_record).execute()
        print(f"Successfully uploaded record {i+1}")
    except Exception as e:
        print(f"Error uploading record {i+1}:")
        print(f"Record data: {json.dumps(cleaned_record, indent=2)}")
        print(f"Error: {str(e)}")
        break

print("Data upload complete.")
