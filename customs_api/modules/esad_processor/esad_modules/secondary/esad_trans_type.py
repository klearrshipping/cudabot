#!/usr/bin/env python3
"""
ESAD Transaction Type Classification Script
Fetches financial transaction data from CSV files and transaction details from invoices
"""

import sys
import os
import json
import requests
from typing import List, Dict, Any

def get_csv_financial_transactions():
    """Fetch financial transaction data from CSV file"""
    try:
        import sys
        import os
        # Add the customs_api directory to the path
        current_dir = os.path.dirname(os.path.abspath(__file__))
        customs_api_dir = os.path.join(current_dir, '..', '..', '..', '..')
        sys.path.insert(0, customs_api_dir)
        from modules.core.csv_data_client import fetch_financial_transactions
        
        transactions = fetch_financial_transactions()
        
        print(f"✅ Successfully loaded {len(transactions)} records from financial_transaction_final.csv")
        return transactions
        
    except Exception as e:
        print(f"❌ Error loading data from CSV: {e}")
        return None

def get_invoice_transaction_details():
    """Fetch transaction details from invoices in CSV files"""
    try:
        # For now, return empty data since we're not storing invoices in CSV
        # This function can be updated later if needed
        print("ℹ️ Invoice data not available in CSV format - returning empty data")
        return []
        
    except Exception as e:
        print(f"❌ Error loading invoice data: {e}")
        return None

def format_transaction_data_for_prompt(transactions: List[Dict]) -> str:
    """Format the transaction data into a structured prompt for Kimi Free"""
    
    # Group transactions by transaction_code for better organization
    transaction_groups = {}
    for trans in transactions:
        code = trans['transaction_code']
        if code not in transaction_groups:
            transaction_groups[code] = {
                'description': trans['transaction_description'],
                'details': []
            }
        transaction_groups[code]['details'].append({
            'detail_code': trans['detail_code'],
            'detail_description': trans['detail_description']
        })
    
    # Build the classification system text
    classification_text = "OFFICIAL FINANCIAL TRANSACTION CLASSIFICATION SYSTEM:\n\n"
    
    for code, group in sorted(transaction_groups.items()):
        classification_text += f"Transaction Code {code}: {group['description']}\n"
        for detail in group['details']:
            classification_text += f"  - Detail Code {detail['detail_code']}: {detail['detail_description']}\n"
        classification_text += "\n"
    
    return classification_text

def send_to_kimi_free(prompt: str, transaction_details: str, invoice_info: Dict = None) -> Dict[str, Any]:
    """Send classification request to Kimi Free via OpenRouter"""
    
    try:
        from config import OPENROUTER_URL, OPENROUTER_HEADERS, OPENROUTER_GENERAL_MODELS
    except ImportError:
        print("❌ config.py not found or missing OpenRouter configuration")
        return {
            "success": False,
            "error": "OpenRouter configuration not found",
            "transaction_details": transaction_details
        }
    
    # Use Mistral Small model from OpenRouter general models for best performance
    model = OPENROUTER_GENERAL_MODELS.get("gpt_5", "openai/gpt-5")
    
    # Add invoice context if available
    invoice_context = ""
    if invoice_info:
        invoice_context = f"\nInvoice Number: {invoice_info.get('invoice_number', 'N/A')}\nInvoice Description: {invoice_info.get('description', 'N/A')}\n"
    
    # Construct the full prompt
    full_prompt = f"""{prompt}

You are a financial transaction classification expert. Your task is to analyze transaction details from invoices and return the most appropriate transaction_code and detail_code pair from the official classification system above.

Please analyze the following transaction details from an invoice and return the most appropriate transaction_code and detail_code pair from the official classification system above.{invoice_context}

Transaction Details: {transaction_details}

Please respond with only the transaction_code and detail_code in the format:
transaction_code: [number]
detail_code: [number]

If you cannot determine the appropriate codes, respond with:
transaction_code: 9
detail_code: 9
(which represents "Other" for both categories)"""

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": full_prompt
            }
        ],
        "max_tokens": 100,
        "temperature": 0.1
    }
    
    try:
        print(f"📤 Sending request to Mistral Small via OpenRouter...")
        response = requests.post(OPENROUTER_URL, headers=OPENROUTER_HEADERS, json=payload, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        
        # Extract the response content
        if 'choices' in result and len(result['choices']) > 0:
            content = result['choices'][0]['message']['content']
            print(f"📥 Response: {content}")
        else:
            content = "No response content found"
            print(f"⚠️  Unexpected response format: {result}")
        
        return {
            "success": True,
            "response": result,
            "content": content,
            "transaction_details": transaction_details,
            "invoice_info": invoice_info
        }
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error calling OpenRouter API: {e}")
        return {
            "success": False,
            "error": str(e),
            "transaction_details": transaction_details,
            "invoice_info": invoice_info
        }

def process_transaction_type(raw_transaction_data: str) -> Dict[str, Any]:
    """
    Process raw transaction type data and return classified transaction information
    
    Args:
        raw_transaction_data (str): Raw transaction type data extracted from documents
        
    Returns:
        Dict containing processed transaction type information
    """
    try:
        # Get the financial transaction classification data
        transactions = get_csv_financial_transactions()
        
        if not transactions:
            return {
                "success": False,
                "error": "Failed to load financial transaction data",
                "raw_input": raw_transaction_data,
                "processed_result": None
            }
        
        # Format the classification system for the prompt
        classification_system = format_transaction_data_for_prompt(transactions)
        
        # Send to Kimi Free for classification
        result = send_to_kimi_free(classification_system, raw_transaction_data)
        
        if result["success"]:
            return {
                "success": True,
                "raw_input": raw_transaction_data,
                "processed_result": result["content"],
                "classification_system": classification_system,
                "processing_notes": ["Transaction type successfully classified using financial codes"]
            }
        else:
            return {
                "success": False,
                "error": result.get("error", "Unknown error"),
                "raw_input": raw_transaction_data,
                "processed_result": None,
                "processing_notes": ["Failed to classify transaction type"]
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "raw_input": raw_transaction_data,
            "processed_result": None,
            "processing_notes": [f"Exception during processing: {str(e)}"]
        }

class TransactionTypeProcessor:
    """Processor class for eSAD transaction type classification (Box 24)."""
    
    def __init__(self, config: Dict = None):
        """Initialize the TransactionTypeProcessor."""
        self.config = config or {}
    
    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process input data to determine transaction type.
        
        Args:
            input_data: Dictionary containing invoice_data, bol_data, fields, and existing_fields
            
        Returns:
            Dictionary with processing results
        """
        try:
            # Extract transaction details from various sources
            transaction_details = self._extract_transaction_details(input_data)
            
            if not transaction_details:
                return {
                    'success': False,
                    'error': 'No transaction details found',
                    'transaction_code': None,
                    'detail_code': None
                }
            
            # Process transaction type classification
            result = process_transaction_type(transaction_details)
            
            if result['success']:
                # Parse the response to extract codes
                transaction_code, detail_code = self._parse_transaction_codes(result['processed_result'])
                
                return {
                    'success': True,
                    'transaction_code': transaction_code,
                    'detail_code': detail_code,
                    'transaction_details': transaction_details,
                    'raw_response': result['processed_result']
                }
            else:
                return {
                    'success': False,
                    'error': result['error'],
                    'transaction_code': None,
                    'detail_code': None
                }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'transaction_code': None,
                'detail_code': None
            }
    
    def _extract_transaction_details(self, input_data: Dict[str, Any]) -> str:
        """Extract transaction details from input data."""
        # Try to get from existing fields first
        existing_fields = input_data.get('existing_fields', {})
        
        # Look for transaction details in various field keys
        transaction_keys = [
            'transaction_details',
            '24_transaction_details',
            'transaction_type',
            'financial_transaction',
            'transaction_description'
        ]
        
        for key in transaction_keys:
            if key in existing_fields and existing_fields[key]:
                return str(existing_fields[key])
        
        # Try to extract from invoice data
        invoice_data = input_data.get('invoice_data', {})
        if invoice_data:
            # Check for transaction-related fields
            for field in ['transaction_details', 'transaction_type', 'description']:
                if field in invoice_data and invoice_data[field]:
                    return str(invoice_data[field])
        
        # Try to extract from BOL data
        bol_data = input_data.get('bol_data', {})
        if bol_data:
            # Check for transaction-related fields
            for field in ['transaction_details', 'transaction_type', 'description']:
                if field in bol_data and bol_data[field]:
                    return str(bol_data[field])
        
        return ""
    
    def _parse_transaction_codes(self, response: str) -> tuple:
        """Parse transaction codes from LLM response."""
        try:
            import re
            
            # Look for transaction_code: X and detail_code: Y patterns
            transaction_match = re.search(r'transaction_code:\s*(\d+)', response)
            detail_match = re.search(r'detail_code:\s*(\d+)', response)
            
            transaction_code = transaction_match.group(1) if transaction_match else None
            detail_code = detail_match.group(1) if detail_match else None
            
            return transaction_code, detail_code
            
        except Exception:
            return None, None

def main():
    """Main function to fetch data and send classification requests"""
    
    print("🚀 Starting ESAD Transaction Type Classification...")
    
    # Fetch financial transaction classification data from CSV
    transactions = get_csv_financial_transactions()
    
    if not transactions:
        print("❌ Failed to load transaction data from CSV")
        print("💡 Make sure the financial_transaction_final table exists and has data")
        return
    
    # Fetch transaction details from invoices
    invoices = get_invoice_transaction_details()
    
    if not invoices:
        print("❌ Failed to load invoice data")
        print("💡 Make sure the invoices table exists and has transaction_details column")
        return
    
    # Format the classification system for the prompt
    classification_system = format_transaction_data_for_prompt(transactions)
    
    print("📋 Classification system prepared:")
    print(classification_system)
    
    print(f"\n🧪 Processing {len(invoices)} invoice transaction details...")
    
    results = []
    for i, invoice in enumerate(invoices, 1):
        transaction_details = invoice.get('transaction_details', '')
        invoice_number = invoice.get('invoice_number', f'Invoice_{i}')
        description = invoice.get('description', 'No description')
        
        if not transaction_details:
            print(f"⚠️  Invoice {i}: No transaction details found, skipping...")
            continue
            
        print(f"\n📝 Invoice {i}: {invoice_number}")
        print(f"   Description: {description}")
        print(f"   Transaction Details: {transaction_details[:100]}...")
        
        # Send to Kimi Free
        result = send_to_kimi_free(classification_system, transaction_details, {
            'invoice_number': invoice_number,
            'description': description
        })
        results.append(result)
        
        if result["success"]:
            print(f"✅ Response received for invoice {i}")
        else:
            print(f"❌ Failed to get response for invoice {i}")
    
    # Save results to file
    output_file = "invoice_classification_results.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n💾 Results saved to {output_file}")
    print("✅ Classification script completed!")

if __name__ == "__main__":
    main() 