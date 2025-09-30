#!/usr/bin/env python3
"""
eSAD Data Loader Test Script
============================

This script loads the extracted data from ORD-20250927-001 based on
the workflow data that was already extracted.

Usage:
    python test_esad_workflow.py

The script will:
1. Load BOL and invoice data from JSON files
2. Display the loaded data
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional, Tuple


class ESADDataLoader:
    """Simple class to load extracted eSAD data"""
    
    def __init__(self, order_number: str = "ORD-20250927-001"):
        self.order_number = order_number
        # Get the script directory and go up one level to find customs_api
        script_dir = Path(__file__).parent
        project_root = script_dir.parent
        self.base_dir = project_root / "customs_api" / "processed_orders" / order_number
        self.bol_data = None
        self.invoice_data = None
        
    def load_extracted_data(self) -> Tuple[bool, str]:
        """Load BOL and invoice data from JSON files"""
        print("=" * 60)
        print("🔍 LOADING EXTRACTED DATA")
        print("=" * 60)
        
        # Load BOL data
        bol_file = self.base_dir / "bills_of_lading" / f"bill_of_lading_{self.order_number}_primary_extract.json"
        if not bol_file.exists():
            return False, f"BOL file not found: {bol_file}"
            
        try:
            with open(bol_file, 'r', encoding='utf-8') as f:
                self.bol_data = json.load(f)
            print(f"✅ Loaded BOL data from: {bol_file.name}")
        except Exception as e:
            return False, f"Error loading BOL data: {e}"
        
        # Load invoice data
        invoice_file = self.base_dir / "invoices" / f"invoice_{self.order_number}_invoice_1_extract.json"
        if not invoice_file.exists():
            return False, f"Invoice file not found: {invoice_file}"
            
        try:
            with open(invoice_file, 'r', encoding='utf-8') as f:
                self.invoice_data = json.load(f)
            print(f"✅ Loaded invoice data from: {invoice_file.name}")
        except Exception as e:
            return False, f"Error loading invoice data: {e}"
        
        return True, "Data loaded successfully"
    
    def display_loaded_data(self):
        """Display the loaded BOL and invoice data"""
        print("\n" + "=" * 60)
        print("📋 LOADED DATA SUMMARY")
        print("=" * 60)
        
        if self.bol_data:
            print("\n📦 BOL DATA:")
            print(f"   Document Type: {self.bol_data.get('document_type', 'N/A')}")
            print(f"   BOL Number: {self.bol_data.get('bill_of_lading', 'N/A')}")
            print(f"   Shipper: {self.bol_data.get('shipper', {}).get('name', 'N/A')}")
            print(f"   Consignee: {self.bol_data.get('consignee', {}).get('name', 'N/A')}")
            print(f"   Flight: {self.bol_data.get('carrier_use_only', {}).get('flight_number', 'N/A')}")
            print(f"   Weight: {self.bol_data.get('weights_measures', {}).get('gross_weight_kg', 'N/A')} kg")
            print(f"   Commodity: {self.bol_data.get('commodity_details', {}).get('description', 'N/A')}")
            
            # Additional BOL details
            print(f"\n   📍 Airport of Departure: {self.bol_data.get('airport_of_departure', {}).get('name', 'N/A')} ({self.bol_data.get('airport_of_departure', {}).get('code', 'N/A')})")
            print(f"   📍 Airport of Destination: {self.bol_data.get('routing_and_destination', {}).get('airport_of_destination', 'N/A')}")
            print(f"   📅 Flight Date: {self.bol_data.get('dates_found', {}).get('flight_date_original', 'N/A')}")
            print(f"   📅 Executed On: {self.bol_data.get('dates_found', {}).get('executed_on_original', 'N/A')}")
            print(f"   🏷️  Tracking Number: {self.bol_data.get('tracking_number', 'N/A')}")
            print(f"   💰 Declared Value: {self.bol_data.get('declared_values', {}).get('declared_value_for_customs', 'N/A')}")
            print(f"   📦 Pieces: {self.bol_data.get('weights_measures', {}).get('pieces', 'N/A')}")
            print(f"   ⚖️  Chargeable Weight: {self.bol_data.get('weights_measures', {}).get('chargeable_weight_kg', 'N/A')} kg")
            print(f"   💵 Freight Charges: ${self.bol_data.get('freight_and_charges', {}).get('total_freight_prepaid', 'N/A')}")
            print(f"   📋 ASYCUDA Ref: {self.bol_data.get('references_and_numbers', {}).get('asycuda_ref', 'N/A')}")
            print(f"   📋 AJAS Ref: {self.bol_data.get('references_and_numbers', {}).get('ajas_reference', 'N/A')}")
        
        if self.invoice_data:
            print("\n📄 INVOICE DATA:")
            print(f"   Supplier: {self.invoice_data.get('supplier', {}).get('name', 'N/A')}")
            print(f"   Invoice Number: {self.invoice_data.get('invoice_details', {}).get('invoice_number', 'N/A')}")
            print(f"   Date: {self.invoice_data.get('invoice_details', {}).get('date', 'N/A')}")
            print(f"   Total Amount: ${self.invoice_data.get('totals', {}).get('total_amount', 'N/A')}")
            print(f"   Currency: {self.invoice_data.get('currency', 'N/A')}")
            
            # Additional invoice details
            supplier_contact = self.invoice_data.get('supplier', {}).get('contact', {})
            print(f"   📞 Supplier Phone: {supplier_contact.get('telephone_main_header', 'N/A')}")
            print(f"   📞 Supplier Fax: {supplier_contact.get('fax_main_header', 'N/A')}")
            print(f"   👤 Contact Person: {supplier_contact.get('contact_person_name', 'N/A')}")
            print(f"   📱 Contact Tel: {supplier_contact.get('contact_person_tel', 'N/A')}")
            
            buyer_contact = self.invoice_data.get('buyer', {}).get('contact', {})
            print(f"   👤 Buyer Contact: {buyer_contact.get('contact_person_name', 'N/A')}")
            print(f"   📞 Buyer Tel: {buyer_contact.get('tel', 'N/A')}")
            
            invoice_details = self.invoice_data.get('invoice_details', {})
            print(f"   📋 Document Title: {invoice_details.get('document_title', 'N/A')}")
            print(f"   🌍 Country of Origin: {invoice_details.get('country_of_origin', 'N/A')}")
            print(f"   🏷️  HS Code: {invoice_details.get('hs_code', 'N/A')}")
            print(f"   📦 Incoterms: {invoice_details.get('incoterms', 'N/A')}")
            
            items = self.invoice_data.get('items', [])
            if items:
                item = items[0]
                print(f"\n   📦 PRODUCT DETAILS:")
                print(f"      Product: {item.get('description', 'N/A')}")
                print(f"      Quantity: {item.get('quantity', 'N/A')}")
                print(f"      Unit Price: ${item.get('unit_price', 'N/A')}")
                print(f"      Total Price: ${item.get('total_price', 'N/A')}")
            
            totals = self.invoice_data.get('totals', {})
            print(f"\n   💰 FINANCIAL SUMMARY:")
            print(f"      Subtotal: ${totals.get('subtotal', 'N/A')}")
            print(f"      Total Amount: ${totals.get('total_amount', 'N/A')}")
            print(f"      Currency Symbol: {totals.get('currency_symbol_present', 'N/A')}")
            
            shipping = self.invoice_data.get('shipping', {})
            print(f"\n   🚚 SHIPPING INFO:")
            print(f"      Method: {shipping.get('method', 'N/A')}")
            
            metadata = self.invoice_data.get('_metadata', {})
            print(f"\n   📊 EXTRACTION METADATA:")
            print(f"      Confidence: {self.invoice_data.get('extraction_confidence', 'N/A')}")
            print(f"      Timestamp: {metadata.get('extraction_timestamp', 'N/A')}")
            print(f"      Processor: {metadata.get('processor', 'N/A')}")
            print(f"      Model: {metadata.get('model', 'N/A')}")
            print(f"      Method: {metadata.get('processing_method', 'N/A')}")
    
    def run_data_loader(self):
        """Run the data loading process"""
        print("🚀 eSAD DATA LOADER")
        print("=" * 60)
        print(f"📋 Order: {self.order_number}")
        print(f"📂 Base Directory: {self.base_dir}")
        print("=" * 60)
        
        # Load extracted data
        success, message = self.load_extracted_data()
        if not success:
            print(f"❌ Failed to load data: {message}")
            return False
        
        # Display loaded data
        self.display_loaded_data()
        
        print("\n✅ Data loading completed!")
        return True


def main():
    """Main function to run the data loader"""
    print("🔧 eSAD Data Loader Test Script")
    print("=" * 60)
    
    # Initialize and run loader
    loader = ESADDataLoader()
    success = loader.run_data_loader()
    
    if success:
        print("\n🎉 Data loading completed successfully!")
        return 0
    else:
        print("\n❌ Data loading failed!")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
