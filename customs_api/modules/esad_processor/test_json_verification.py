#!/usr/bin/env python3
"""
Test script to verify complete JSON output with all fields
"""

import json
import sys
import os

# Add the current directory to path
sys.path.append(os.path.dirname(__file__))

from esad_modules.core.esad_regime import RegimeTypeProcessor

def test_json_verification():
    """Test complete JSON output with real order data"""
    
    # Load real BOL data
    bol_file = "C:/Users/rafer/OneDrive/Desktop/projects/cuda/customs_api/processed_orders/ORD-20251005-001/bills_of_lading/bill_of_lading_ORD-20251005-001_primary_extract.json"
    with open(bol_file, 'r', encoding='utf-8') as f:
        bol_data = json.load(f)
    
    # Load real invoice data
    invoice_file = "C:/Users/rafer/OneDrive/Desktop/projects/cuda/customs_api/processed_orders/ORD-20251005-001/invoices/invoice_ORD-20251005-001_invoice_1_extract.json"
    with open(invoice_file, 'r', encoding='utf-8') as f:
        invoice_data = json.load(f)
    
    # Create test data structure
    test_data = {
        'invoice_data': invoice_data,
        'bol_data': bol_data,
        'form_fields': {
            'shipper': bol_data.get('shipper', {}).get('name', ''),
            'consignee_name': bol_data.get('consignee', {}).get('name', ''),
            'bill_of_lading': bol_data.get('bill_of_lading', ''),
            'weight': bol_data.get('cargo', {}).get('gross_weight', '')
        },
        'existing_fields': {
            '8_importer_consignee_address': f"{bol_data.get('consignee', {}).get('address_line_1', '')}, {bol_data.get('consignee', {}).get('city', '')}",
            '2_exporter_consignor_address': f"{bol_data.get('shipper', {}).get('address_line_1', '')}, {bol_data.get('shipper', {}).get('country', '')}"
        }
    }
    
    # Initialize processor and run test
    processor = RegimeTypeProcessor()
    result = processor.determine_regime_type(test_data)
    
    # Output as JSON
    print(json.dumps(result.to_json(), indent=2))
    
    # Output formatted summary as JSON
    print(json.dumps(result.get_summary_json(), indent=2))

if __name__ == "__main__":
    test_json_verification()
