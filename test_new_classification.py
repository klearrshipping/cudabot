import json
import sys

sys.path.insert(0, 'customs_api')

from modules.esad_processor.esad_modules.core.esad_product_classification import classify_product_commercial_vs_personal

# Load BOL and Invoice data
with open('customs_api/processed_orders/ORD-20251009-002/bills_of_lading/bill_of_lading_ORD-20251009-002_primary_extract.json') as f:
    bol_data = json.load(f)

with open('customs_api/processed_orders/ORD-20251009-002/invoices/invoice_ORD-20251009-002_invoice_1_extract.json') as f:
    invoice_data = json.load(f)

# Classify with verbose output
result = classify_product_commercial_vs_personal(invoice_data, bol_data, verbose=True)

