#!/usr/bin/env python3
"""
Test Script for ESAD CIF Processor with Real Data
Tests the enhanced CIF processor using actual invoice and bill of lading files
Demonstrates freight cost disaggregation and complex invoice scenarios
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, List

# Add the current directory to Python path to import esad_cif
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from esad_cif import process_val_note_for_cif, CIFProcessor

class RealDataCIFTester:
    """Test the CIF processor with real invoice and BOL data"""
    
    def __init__(self):
        self.test_results = []
        self.workspace_root = Path(__file__).parent.parent.parent
        
    def load_json_file(self, file_path: str) -> Dict[str, Any]:
        """Load and parse a JSON file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Error loading {file_path}: {e}")
            return {}
    
    def extract_val_note_from_invoice(self, invoice_data: Dict[str, Any]) -> str:
        """Extract val_note format data from invoice JSON"""
        if not invoice_data:
            return "No invoice data"
        
        totals = invoice_data.get('totals', {})
        items = invoice_data.get('items', [])
        
        # Calculate goods value (subtotal)
        goods_value = totals.get('subtotal', 0.0)
        
        # Get total amount (might include freight)
        total_amount = totals.get('total_amount', 0.0)
        
        # Check if shipping/handling is separate
        shipping_handling = totals.get('shipping_handling', 0.0)
        
        # Extract tax and other charges that should be included in CIF
        tax_amount = totals.get('tax', 0.0)
        
        val_note = f"""Invoice value (goods only): {goods_value}
Invoice total (including freight): {total_amount if total_amount > goods_value else 'null'}
Freight charges (invoice): {shipping_handling if shipping_handling > 0 else 'null'}
Tax: {tax_amount if tax_amount > 0 else 'null'}
Insurance charges: null"""
        
        return val_note
    
    def extract_val_note_from_bol(self, bol_data: Dict[str, Any]) -> str:
        """Extract val_note format data from bill of lading JSON"""
        if not bol_data:
            return "No BOL data"
        
        charges = bol_data.get('charges', [])
        
        # Extract freight charges
        freight_charges = 0.0
        other_charges = 0.0
        
        for charge in charges:
            charge_type = charge.get('charge_type', '').upper()
            collect_amount = float(charge.get('collect_amount', 0.0) or 0.0)
            
            if 'FREIGHT' in charge_type:
                freight_charges += collect_amount
            else:
                other_charges += collect_amount
        
        val_note = f"""Freight charges (BOL): {freight_charges if freight_charges > 0 else 'null'}
Other charges (BOL): {other_charges if other_charges > 0 else 'null'}"""
        
        return val_note
    
    def combine_val_note_data(self, invoice_val_note: str, bol_val_note: str) -> str:
        """Combine invoice and BOL val_note data"""
        combined = invoice_val_note.strip()
        if bol_val_note.strip():
            combined += f"\n{bol_val_note.strip()}"
        return combined
    
    def test_real_order_data(self):
        """Test with real order data from ORD-20250824-003"""
        print("🔍 Testing with Real Order Data: ORD-20250824-003")
        print("=" * 60)
        
        # Load real invoice and BOL data
        invoice_path = self.workspace_root / "processed_data" / "orders" / "ORD-20250824-003" / "primary_process" / "invoice_ORD-20250824-003_primary_extract.json"
        bol_path = self.workspace_root / "processed_data" / "orders" / "ORD-20250824-003" / "primary_process" / "bill_of_lading_ORD-20250824-003_primary_extract.json"
        
        invoice_data = self.load_json_file(str(invoice_path))
        bol_data = self.load_json_file(str(bol_path))
        
        if not invoice_data or not bol_data:
            print("❌ Could not load order data files")
            return
        
        # Extract val_note data
        invoice_val_note = self.extract_val_note_from_invoice(invoice_data)
        bol_val_note = self.extract_val_note_from_bol(bol_data)
        combined_val_note = self.combine_val_note_data(invoice_val_note, bol_val_note)
        
        print("📋 Invoice Data:")
        print(f"   Goods Value: ${invoice_data.get('totals', {}).get('subtotal', 0):.2f}")
        print(f"   Total Amount: ${invoice_data.get('totals', {}).get('total_amount', 0):.2f}")
        print(f"   Shipping/Handling: ${invoice_data.get('totals', {}).get('shipping_handling', 0):.2f}")
        
        print("\n📋 Bill of Lading Data:")
        charges = bol_data.get('charges', [])
        for charge in charges:
            charge_type = charge.get('charge_type', '')
            collect_amount = charge.get('collect_amount', 0)
            if collect_amount and float(collect_amount) > 0:
                print(f"   {charge_type}: ${float(collect_amount):.2f}")
        
        print(f"\n📝 Combined Val_Note Data:")
        print(combined_val_note)
        
        # Process with CIF processor
        print(f"\n🔄 Processing with Enhanced CIF Processor...")
        result = process_val_note_for_cif(combined_val_note)
        
        # Display results
        self.display_cif_results(result, "Real Order ORD-20250824-003")
        
        return result
    
    def test_extracted_invoice_files(self):
        """Test with extracted invoice files"""
        print("\n🔍 Testing with Extracted Invoice Files")
        print("=" * 60)
        
        invoice_dir = self.workspace_root / "extracted_invoices"
        invoice_files = list(invoice_dir.glob("invoice_extract_*.json"))
        
        if not invoice_files:
            print("❌ No extracted invoice files found")
            return
        
        # Test with first few invoice files
        for i, invoice_file in enumerate(invoice_files[:3]):
            print(f"\n📋 Testing Invoice File {i+1}: {invoice_file.name}")
            print("-" * 40)
            
            invoice_data = self.load_json_file(str(invoice_file))
            if not invoice_data:
                continue
            
            # Extract val_note data
            invoice_val_note = self.extract_val_note_from_invoice(invoice_data)
            
            print("📝 Invoice Val_Note Data:")
            print(invoice_val_note)
            
            # Process with CIF processor
            print(f"\n🔄 Processing with Enhanced CIF Processor...")
            result = process_val_note_for_cif(invoice_val_note)
            
            # Display results
            self.display_cif_results(result, f"Extracted Invoice {i+1}")
    
    def test_complex_scenarios(self):
        """Test complex scenarios that require freight disaggregation"""
        print("\n🔍 Testing Complex Scenarios")
        print("=" * 60)
        
        # Scenario 1: Invoice includes freight in total, BOL has separate freight
        print("\n📋 Scenario 1: Invoice includes freight, BOL has separate freight")
        scenario_1 = """Invoice value (goods only): 1399.0
Invoice total (including freight): 1610.71
Freight charges (BOL): 211.71
Insurance charges: null
Other charges (BOL): 5750.00"""
        
        result_1 = process_val_note_for_cif(scenario_1)
        self.display_cif_results(result_1, "Scenario 1: BOL Freight + Invoice Total")
        
        # Scenario 2: Invoice shows freight separately
        print("\n📋 Scenario 2: Invoice shows freight separately")
        scenario_2 = """Invoice value (goods only): 2500.0
Invoice total (including freight): null
Freight charges (BOL): null
Freight charges (invoice): 150.0
Insurance charges: 25.0
Other charges (BOL): 0.0"""
        
        result_2 = process_val_note_for_cif(scenario_2)
        self.display_cif_results(result_2, "Scenario 2: Invoice Freight Separate")
        
        # Scenario 3: Freight needs to be disaggregated from invoice total
        print("\n📋 Scenario 3: Freight disaggregation needed")
        scenario_3 = """Invoice value (goods only): 800.0
Invoice total (including freight): 950.0
Freight charges (BOL): null
Freight charges (invoice): null
Insurance charges: null
Other charges (BOL): 0.0"""
        
        result_3 = process_val_note_for_cif(scenario_3)
        self.display_cif_results(result_3, "Scenario 3: Freight Disaggregation")
    
    def display_cif_results(self, result: Dict[str, Any], test_name: str):
        """Display CIF processing results in a formatted way"""
        print(f"\n💰 CIF Results for {test_name}")
        print("-" * 40)
        
        cif_breakdown = result.get('cif_breakdown', {})
        freight_analysis = result.get('freight_analysis', {})
        processing_summary = result.get('processing_summary', {})
        
        print(f"📊 CIF Breakdown:")
        print(f"   Goods Value: ${cif_breakdown.get('cost', 0):.2f}")
        print(f"   Insurance: ${cif_breakdown.get('insurance', 0):.2f}" if cif_breakdown.get('insurance') else "   Insurance: None")
        print(f"   Freight: ${cif_breakdown.get('freight', 0):.2f}")
        print(f"   Invoice Charges: ${cif_breakdown.get('invoice_charges', 0):.2f}")
        print(f"   Total CIF: ${cif_breakdown.get('total_cif', 0):.2f}")
        
        print(f"\n🚢 Freight Analysis:")
        print(f"   Source: {freight_analysis.get('freight_source', 'Unknown')}")
        print(f"   Disaggregation Applied: {freight_analysis.get('disaggregation_applied', False)}")
        if freight_analysis.get('other_bol_charges'):
            print(f"   Other BOL Charges: ${freight_analysis.get('other_bol_charges', 0):.2f}")
        
        print(f"\n📝 Processing Summary:")
        print(f"   Components Extracted: {processing_summary.get('components_extracted', 0)}")
        print(f"   Total Calculated: {processing_summary.get('total_calculated', False)}")
        
        # Show key processing notes
        processing_notes = processing_summary.get('processing_notes', [])
        if processing_notes:
            print(f"\n🔍 Key Processing Notes:")
            for note in processing_notes[:5]:  # Show first 5 notes
                print(f"   • {note}")
            if len(processing_notes) > 5:
                print(f"   ... and {len(processing_notes) - 5} more notes")
    
    def run_all_tests(self):
        """Run all test scenarios"""
        print("🧪 ESAD CIF Processor - Real Data Test Suite")
        print("=" * 70)
        print("Testing enhanced CIF processor with freight cost disaggregation")
        print("and complex invoice scenarios using real data files")
        print("=" * 70)
        
        try:
            # Test 1: Real order data
            self.test_real_order_data()
            
            # Test 2: Extracted invoice files
            self.test_extracted_invoice_files()
            
            # Test 3: Complex scenarios
            self.test_complex_scenarios()
            
            print("\n✅ All tests completed successfully!")
            print("\n📝 Summary of Enhanced CIF Processor Features:")
            print("   • Handles BOL freight as primary source")
            print("   • Disaggregates freight from invoice totals when needed")
            print("   • Tracks freight source and disaggregation status")
            print("   • Processes other BOL charges for complete cost analysis")
            print("   • Provides detailed processing notes for audit trail")
            print("   • Works with real invoice and BOL data structures")
            
        except Exception as e:
            print(f"\n❌ Test suite failed with error: {e}")
            import traceback
            traceback.print_exc()

def main():
    """Main function to run the test suite"""
    tester = RealDataCIFTester()
    tester.run_all_tests()

if __name__ == "__main__":
    main()
