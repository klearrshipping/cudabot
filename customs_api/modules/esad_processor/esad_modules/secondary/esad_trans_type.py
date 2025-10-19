#!/usr/bin/env python3
"""
ESAD Transaction Type Classification Script
Extracts transaction type from BOL/Invoice and matches to financial_transaction_final.csv
"""

import sys
import os
import json
import re
import csv
import requests
from typing import List, Dict, Any, Optional
from pathlib import Path

# Add the customs_api directory to the path
current_dir = os.path.dirname(os.path.abspath(__file__))
customs_api_dir = os.path.join(current_dir, '..', '..', '..', '..')
sys.path.insert(0, customs_api_dir)

# Import OpenRouter configuration
try:
    from config import OPENROUTER_API_KEY, OPENROUTER_URL, OPENROUTER_HEADERS
except ImportError:
    # Fallback configuration if config import fails
    OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY', '')
    OPENROUTER_URL = os.getenv('OPENROUTER_URL', 'https://openrouter.ai/api/v1/chat/completions')
    OPENROUTER_HEADERS = {
        'Authorization': f'Bearer {OPENROUTER_API_KEY}',
        'Content-Type': 'application/json',
        'HTTP-Referer': 'http://localhost:3000',
        'X-Title': 'eSAD Transaction Type Classifier'
    }

# Cache for transaction data
_transaction_data_cache = None

def get_csv_financial_transactions() -> List[Dict]:
    """Fetch financial transaction data from CSV file with caching"""
    global _transaction_data_cache
    
    if _transaction_data_cache is not None:
        return _transaction_data_cache
    
    try:
        csv_path = Path(__file__).parent.parent.parent.parent.parent / "data" / "financial_transaction_final.csv"
        transactions = []
        
        encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
        
        for encoding in encodings:
            try:
                with open(csv_path, 'r', encoding=encoding) as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        transactions.append({
                            'transaction_code': row['transaction_code'].strip(),
                            'transaction_description': row['transaction_description'].strip(),
                            'detail_code': row['detail_code'].strip(),
                            'detail_description': row['detail_description'].strip()
                        })
                break
            except UnicodeDecodeError:
                continue
            except Exception as e:
                continue
        
        if not transactions:
            raise RuntimeError("Failed to load transaction data with any encoding")
        
        _transaction_data_cache = transactions
        return transactions
        
    except Exception as e:
        print(f"❌ Error loading data from CSV: {e}")
        return []

def extract_transaction_type(bol_data: Dict[str, Any], invoice_data: Dict[str, Any], verbose: bool = False) -> Dict[str, Any]:
    """Extract transaction type from BOL and Invoice using LLM
    
    Args:
        bol_data: Bill of Lading data
        invoice_data: Invoice data
        verbose: If True, print extraction results to console (default: False)
    
    Returns:
        Dictionary containing transaction codes and matched transaction type
    """
    
    # Safely serialize data
    def safe_json_dumps(obj, max_depth=3, current_depth=0):
        if current_depth >= max_depth:
            return "[Max depth reached]"
        
        if isinstance(obj, dict):
            result = {}
            for key, value in obj.items():
                try:
                    result[key] = safe_json_dumps(value, max_depth, current_depth + 1)
                except:
                    result[key] = str(value)[:100] + "..." if len(str(value)) > 100 else str(value)
            return result
        elif isinstance(obj, list):
            result = []
            for item in obj:
                try:
                    result.append(safe_json_dumps(item, max_depth, current_depth + 1))
                except:
                    result.append(str(item)[:100] + "..." if len(str(item)) > 100 else str(item))
            return result
        else:
            return obj
    
    safe_bol_data = safe_json_dumps(bol_data)
    safe_invoice_data = safe_json_dumps(invoice_data)
    
    # Load transaction types
    transactions = get_csv_financial_transactions()
    
    if not transactions:
        return {
            'success': False,
            'error': 'Failed to load transaction data',
            'transaction_code': None,
            'detail_code': None
        }
    
    # Format transaction options for prompt
    transaction_options = format_transaction_data_for_prompt(transactions)
    
    prompt = f"""
You are analyzing a Bill of Lading (BOL) and Commercial Invoice to determine the financial transaction type.

AVAILABLE TRANSACTION TYPES:
{transaction_options}

Analyze the documents to determine the most appropriate transaction type based on:
- Payment terms
- Transaction description
- Nature of the transaction (sale, return, repair, etc.)
- Purpose of the shipment
- Compensation details

BOL DATA:
{json.dumps(safe_bol_data, indent=2)}

INVOICE DATA:
{json.dumps(safe_invoice_data, indent=2)}

INSTRUCTIONS:
- Most commercial imports are Transaction Code 1, Detail Code 1 (Outright purchase or sale)
- Returns use Transaction Code 2
- Repairs use Transaction Code 6
- Free transfers/aid use Transaction Code 3
- If uncertain, default to Transaction Code 1, Detail Code 1

Return your response in the following JSON format:
{{
  "transaction_code": "code number",
  "detail_code": "detail number",
  "transaction_description": "description",
  "reasoning": "brief explanation"
}}
"""
    
    payload = {
        "model": "openai/gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 300
    }
    
    try:
        if verbose:
            print("\n🔍 Extracting transaction type from BOL/Invoice...")
        
        response = requests.post(OPENROUTER_URL, headers=OPENROUTER_HEADERS, json=payload, timeout=30)
        response_data = response.json()
        content = response_data['choices'][0]['message']['content']
        
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        result = json.loads(json_match.group())
        
        transaction_code = result.get('transaction_code')
        detail_code = result.get('detail_code')
        
        # Find matching transaction from CSV
        matched_transaction = None
        for trans in transactions:
            if trans['transaction_code'] == str(transaction_code) and trans['detail_code'] == str(detail_code):
                matched_transaction = trans
                break
        
        if verbose:
            print(f"\n💼 TRANSACTION TYPE EXTRACTION:")
            print("=" * 60)
            print(f"Transaction Code: {transaction_code}")
            print(f"Detail Code: {detail_code}")
            if matched_transaction:
                print(f"Transaction: {matched_transaction['transaction_description']}")
                print(f"Detail: {matched_transaction['detail_description']}")
            print(f"Reasoning: {result.get('reasoning', 'N/A')}")
            print("=" * 60)
        
        return {
            'success': True,
            'transaction_code': transaction_code,
            'detail_code': detail_code,
            'transaction_description': matched_transaction['transaction_description'] if matched_transaction else result.get('transaction_description'),
            'detail_description': matched_transaction['detail_description'] if matched_transaction else None,
            'reasoning': result.get('reasoning'),
            'extraction_metadata': {
                'status': 'success',
                'message': 'Transaction type extracted successfully',
                'matched': matched_transaction is not None
            }
        }
        
    except Exception as e:
        if verbose:
            print(f"\n❌ Transaction extraction failed: {e}")
        
        return {
            'success': False,
            'error': f"Transaction extraction failed: {str(e)}",
            'transaction_code': None,
            'detail_code': None,
            'extraction_metadata': {
                'status': 'error',
                'message': str(e)
            }
        }

def format_transaction_data_for_prompt(transactions: List[Dict]) -> str:
    """Format the transaction data into a structured prompt"""
    
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

class TransactionTypeProcessor:
    """Processor class for eSAD transaction type classification (Box 24)."""
    
    def __init__(self, config: Dict = None):
        """Initialize the TransactionTypeProcessor."""
        self.config = config or {}
    
    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process input data to determine transaction type from BOL and Invoice.
        
        Args:
            input_data: Dictionary containing bol_data and invoice_data
            
        Returns:
            Dictionary with processing results including transaction codes
        """
        try:
            bol_data = input_data.get('bol_data', {})
            invoice_data = input_data.get('invoice_data', {})
            
            if not bol_data and not invoice_data:
                return {
                    'success': False,
                    'error': 'No BOL or Invoice data found',
                    'transaction_code': None,
                    'detail_code': None,
                    'transaction_type': None
                }
            
            # Extract transaction type using LLM
            result = extract_transaction_type(bol_data, invoice_data, verbose=False)
            
            if result['success']:
                return {
                    'success': True,
                    'transaction_code': result['transaction_code'],
                    'detail_code': result['detail_code'],
                    'transaction_type': f"{result['transaction_code']}.{result['detail_code']}",
                    'transaction_description': result.get('transaction_description'),
                    'detail_description': result.get('detail_description'),
                    'reasoning': result.get('reasoning')
                }
            else:
                return {
                    'success': False,
                    'error': result.get('error', 'Unknown error'),
                    'transaction_code': None,
                    'detail_code': None,
                    'transaction_type': None
                }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'transaction_code': None,
                'detail_code': None,
                'transaction_type': None
            }

def main():
    """Test the transaction type extraction with real BOL and Invoice data"""
    import json
    import argparse
    
    parser = argparse.ArgumentParser(description='Test Transaction Type Processor')
    parser.add_argument('order_id', help='Order ID to process (e.g., ORD-20251009-003)')
    args = parser.parse_args()
    
    print("🧪 Testing Transaction Type Processor")
    print("=" * 80)
    
    # Load test data
    try:
        base_path = Path(__file__).parent.parent.parent.parent
        order_id = args.order_id
        bol_path = base_path / "processed_orders" / order_id / "bills_of_lading" / f"bill_of_lading_{order_id}_primary_extract.json"
        invoice_path = base_path / "processed_orders" / order_id / "invoices" / f"invoice_{order_id}_invoice_1_extract.json"
        
        with open(bol_path, 'r', encoding='utf-8') as f:
            bol_data = json.load(f)
        
        with open(invoice_path, 'r', encoding='utf-8') as f:
            invoice_data = json.load(f)
        
        print(f"\n📁 Loaded test data:")
        print(f"   - Order ID: {order_id}")
        print(f"   - BOL: {bol_path.name}")
        print(f"   - Invoice: {invoice_path.name}")
        
        # Extract transaction type
        result = extract_transaction_type(bol_data, invoice_data, verbose=True)
        
        print("\n📊 Final Result:")
        print(json.dumps(result, indent=2))
        
    except FileNotFoundError as e:
        print(f"\n❌ Test data files not found: {e}")
        print("💡 Make sure processed orders exist in the correct location")
        print(f"💡 Usage: python esad_trans_type.py ORDER_ID")
    except Exception as e:
        print(f"\n❌ Error during test: {e}")


if __name__ == "__main__":
    main() 