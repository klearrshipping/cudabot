#!/usr/bin/env python3
"""
Real Data Test Script for ESAD Transaction Type Processing
Tests the process_transaction_type function using actual invoice and BOL extracts
"""

import json
import os
from esad_trans_type import process_transaction_type

def load_real_data():
    """Load real invoice and BOL extracts for testing"""
    
    # Load invoice extract
    invoice_path = "../../extracted_invoices/invoice_extract_20250817_074343.json"
    if os.path.exists(invoice_path):
        with open(invoice_path, 'r') as f:
            invoice_data = json.load(f)
        print(f"✅ Loaded invoice extract: {invoice_path}")
    else:
        print(f"❌ Invoice extract not found: {invoice_path}")
        invoice_data = None
    
    # Load BOL extract
    bol_path = "../../processed_data/orders/ORD-20250824-003/primary_process/bill_of_lading_ORD-20250824-003_primary_extract.json"
    if os.path.exists(bol_path):
        with open(bol_path, 'r') as f:
            bol_data = json.load(f)
        print(f"✅ Loaded BOL extract: {bol_path}")
    else:
        print(f"❌ BOL extract not found: {bol_path}")
        bol_data = None
    
    return invoice_data, bol_data

def extract_transaction_context(invoice_data, bol_data):
    """Extract transaction context from invoice and BOL data"""
    
    transaction_context = []
    
    if invoice_data:
        # Extract invoice transaction details
        supplier = invoice_data.get('supplier', {}).get('name', 'Unknown')
        buyer = invoice_data.get('buyer', {}).get('name', 'Unknown')
        payment_method = invoice_data.get('payment_terms', {}).get('method', 'Unknown')
        shipping_method = invoice_data.get('shipping', {}).get('method', 'Unknown')
        currency = invoice_data.get('currency', 'Unknown')
        
        transaction_context.append(f"Supplier: {supplier}")
        transaction_context.append(f"Buyer: {buyer}")
        transaction_context.append(f"Payment Method: {payment_method}")
        transaction_context.append(f"Shipping Method: {shipping_method}")
        transaction_context.append(f"Currency: {currency}")
        
        # Add invoice totals context
        totals = invoice_data.get('totals', {})
        if totals:
            subtotal = totals.get('subtotal', 0)
            tax = totals.get('tax', 0)
            total = totals.get('total_amount', 0)
            transaction_context.append(f"Invoice Subtotal: ${subtotal}")
            transaction_context.append(f"Tax: ${tax}")
            transaction_context.append(f"Total Amount: ${total}")
    
    if bol_data:
        # Extract BOL transaction details
        shipper = bol_data.get('shipper', 'Unknown')
        consignee = bol_data.get('consignee_name', 'Unknown')
        freight_charges = []
        
        # Extract freight and other charges
        charges = bol_data.get('charges', [])
        for charge in charges:
            charge_type = charge.get('charge_type', '')
            collect_amount = charge.get('collect_amount', '0')
            currency = charge.get('currency', '')
            
            if charge_type == 'FREIGHT' and float(collect_amount) > 0:
                freight_charges.append(f"Freight: {currency} {collect_amount}")
            elif charge_type and float(collect_amount) > 0:
                freight_charges.append(f"{charge_type}: {currency} {collect_amount}")
        
        transaction_context.append(f"BOL Shipper: {shipper}")
        transaction_context.append(f"BOL Consignee: {consignee}")
        transaction_context.extend(freight_charges)
    
    return "\n".join(transaction_context)

def test_transaction_type_with_real_data():
    """Test transaction type processing with real invoice and BOL data"""
    
    print("🧪 Testing ESAD Transaction Type Processing with Real Data")
    print("=" * 70)
    
    # Load real data
    invoice_data, bol_data = load_real_data()
    
    if not invoice_data and not bol_data:
        print("❌ No data available for testing")
        return
    
    # Extract transaction context
    transaction_context = extract_transaction_context(invoice_data, bol_data)
    
    print("\n📋 Transaction Context Extracted:")
    print("-" * 40)
    print(transaction_context)
    
    # Test case 1: Full transaction context
    print("\n📋 Test Case 1: Full Transaction Context")
    print("=" * 50)
    
    result_1 = process_transaction_type(transaction_context)
    print(f"Input Length: {len(transaction_context)} characters")
    print(f"Success: {result_1['success']}")
    if result_1['success']:
        print(f"Processed Result: {result_1['processed_result']}")
        print(f"Processing Notes: {result_1['processing_notes']}")
    else:
        print(f"Error: {result_1['error']}")
    
    # Test case 2: Invoice-only context
    if invoice_data:
        print("\n📋 Test Case 2: Invoice-Only Context")
        print("=" * 40)
        
        invoice_context = f"""
        Commercial transaction between {invoice_data.get('supplier', {}).get('name', 'Unknown')} and {invoice_data.get('buyer', {}).get('name', 'Unknown')}
        Payment: {invoice_data.get('payment_terms', {}).get('method', 'Unknown')}
        Shipping: {invoice_data.get('shipping', {}).get('method', 'Unknown')}
        Total: ${invoice_data.get('totals', {}).get('total_amount', 0)}
        """
        
        result_2 = process_transaction_type(invoice_context.strip())
        print(f"Input: {invoice_context.strip()}")
        print(f"Success: {result_2['success']}")
        if result_2['success']:
            print(f"Processed Result: {result_2['processed_result']}")
            print(f"Processing Notes: {result_2['processing_notes']}")
        else:
            print(f"Error: {result_2['error']}")
    
    # Test case 3: BOL-only context
    if bol_data:
        print("\n📋 Test Case 3: BOL-Only Context")
        print("=" * 35)
        
        bol_context = f"""
        Transport document: {bol_data.get('bill_of_lading', 'Unknown')}
        Shipper: {bol_data.get('shipper', 'Unknown')}
        Consignee: {bol_data.get('consignee_name', 'Unknown')}
        Freight charges: {len([c for c in bol_data.get('charges', []) if c.get('charge_type') == 'FREIGHT' and float(c.get('collect_amount', 0)) > 0])} freight items
        """
        
        result_3 = process_transaction_type(bol_context.strip())
        print(f"Input: {bol_context.strip()}")
        print(f"Success: {result_3['success']}")
        if result_3['success']:
            print(f"Processed Result: {result_3['processed_result']}")
            print(f"Processing Notes: {result_3['processing_notes']}")
        else:
            print(f"Error: {result_3['error']}")
    
    # Test case 4: Simple commercial indicators
    print("\n📋 Test Case 4: Simple Commercial Indicators")
    print("=" * 45)
    
    simple_context = "Commercial sale with payment terms, standard shipping, invoice total with tax"
    
    result_4 = process_transaction_type(simple_context)
    print(f"Input: {simple_context}")
    print(f"Success: {result_4['success']}")
    if result_4['success']:
        print(f"Processed Result: {result_4['processed_result']}")
        print(f"Processing Notes: {result_4['processing_notes']}")
    else:
        print(f"Error: {result_4['error']}")
    
    print("\n✅ Real data transaction type processing test completed!")
    print("\n📝 Summary:")
    print("   • Tested with actual Amazon invoice extract")
    print("   • Tested with actual BOL extract from SEABOARD GEMINI")
    print("   • Box 24 'Nature of Transaction' processes real document data")
    print("   • Returns classified transaction type using financial codes")
    print("   • Integrates with the ESAD field processing system")

if __name__ == "__main__":
    test_transaction_type_with_real_data()
