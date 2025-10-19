#!/usr/bin/env python3
"""
esad_warehouse.py
────────────────
Matches office codes with warehouse information from warehouse.csv.

Usage:
    python -m modules.esad_warehouse <esad_json_path>

This script:
1. Takes the office_code_processed value from eSAD results
2. Fetches warehouse data from warehouse.csv
3. Matches the office code with the office_id column
4. Returns the corresponding warehouse code(s)
"""

import sys
import json
import csv
from typing import List, Dict, Optional, Any
from pathlib import Path

# Cache for warehouse data to avoid repeated file reads
_warehouse_data_cache = None

def get_warehouse_data() -> List[Dict]:
    """Get warehouse data with caching to avoid repeated file reads."""
    global _warehouse_data_cache
    if _warehouse_data_cache is None:
        csv_path = Path(__file__).parent.parent.parent / "data" / "warehouse.csv"
        warehouses = []
        
        # Try different encodings to handle potential encoding issues
        encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
        
        for encoding in encodings:
            try:
                with open(csv_path, 'r', encoding=encoding) as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        warehouses.append({
                            'code': row['code'],
                            'warehouse': row['warehouse'],
                            'office_id': row['office_id']
                        })
                print(f"✅ Successfully loaded warehouse data using {encoding} encoding")
                break
            except UnicodeDecodeError:
                continue
            except Exception as e:
                print(f"❌ Error reading warehouse data with {encoding}: {e}")
                continue
        
        if not warehouses:
            raise RuntimeError("Failed to load warehouse data with any encoding")
        
        _warehouse_data_cache = warehouses
    
    return _warehouse_data_cache

def get_office_code_from_json(json_path: str) -> Optional[str]:
    """Extract office_code_processed from eSAD results JSON."""
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Try to get office_code_processed from different possible locations
        extracted_fields = data.get('result', {}).get('extracted_fields', {})
        office_code = extracted_fields.get('office_code_processed')
        
        if not office_code:
            # Try alternative field names
            office_code = extracted_fields.get('office_code')
        
        return office_code
        
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        print(f"❌ Error extracting office code: {e}")
        return None

def find_warehouses_by_office_id(office_id: str, warehouses: List[Dict]) -> List[Dict]:
    """Find all warehouses that match the given office_id."""
    if not office_id:
        return []
    
    matching_warehouses = []
    office_id_clean = office_id.strip().upper()
    
    for warehouse in warehouses:
        warehouse_office_id = warehouse['office_id'].strip().upper()
        if warehouse_office_id == office_id_clean:
            matching_warehouses.append(warehouse)
    
    return matching_warehouses

def select_warehouse_interactive(warehouses: List[Dict]) -> Optional[Dict]:
    """Interactive warehouse selection when multiple options are available."""
    print(f"\n🔍 Multiple warehouses found. Please select one for Box Field 30:")
    print("=" * 60)
    
    # Display all available warehouses with numbers
    for i, warehouse in enumerate(warehouses, 1):
        print(f"  {i}. {warehouse['code']} - {warehouse['warehouse']}")
        print(f"     Office ID: {warehouse['office_id']}")
        print()
    
    # Get user selection
    while True:
        try:
            selection = input("Enter the number of your choice (or 'q' to quit): ").strip()
            
            if selection.lower() == 'q':
                print("❌ Selection cancelled by user")
                return None
            
            choice = int(selection)
            if 1 <= choice <= len(warehouses):
                selected_warehouse = warehouses[choice - 1]
                print(f"✅ Selected: {selected_warehouse['code']} - {selected_warehouse['warehouse']}")
                return selected_warehouse
            else:
                print(f"❌ Invalid choice. Please enter a number between 1 and {len(warehouses)}")
                
        except ValueError:
            print("❌ Invalid input. Please enter a number or 'q' to quit")
        except (KeyboardInterrupt, EOFError):
            print("\n❌ Selection interrupted or no input available")
            return None

def process_warehouse_lookup(office_code: str, warehouses: List[Dict], auto_mode: bool = False) -> Dict[str, any]:
    """Process warehouse lookup and return results for box field 30."""
    if not office_code:
        return {
            'success': False,
            'error': 'No office code provided',
            'warehouses': [],
            'office_code': None,
            'box_30_value': None
        }
    
    print(f"🏢 Looking up warehouses for office code: {office_code}")
    
    # Find matching warehouses
    matching_warehouses = find_warehouses_by_office_id(office_code, warehouses)
    
    if matching_warehouses:
        print(f"✅ Found {len(matching_warehouses)} warehouse(s) for office {office_code}")
        
        if len(matching_warehouses) == 1:
            # Only one warehouse - use it directly
            selected_warehouse = matching_warehouses[0]
            print(f"📦 Single warehouse found: {selected_warehouse['code']} - {selected_warehouse['warehouse']}")
        else:
            # Multiple warehouses - let user choose or auto-select
            if auto_mode:
                # Auto mode: select first warehouse
                selected_warehouse = matching_warehouses[0]
                print(f"🤖 Auto mode: Selected first warehouse: {selected_warehouse['code']} - {selected_warehouse['warehouse']}")
            else:
                # Interactive mode: let user choose
                selected_warehouse = select_warehouse_interactive(matching_warehouses)
                if not selected_warehouse:
                    # User cancelled or invalid selection
                    return {
                        'success': False,
                        'error': 'No warehouse selected by user',
                        'office_code': office_code,
                        'warehouses': matching_warehouses,
                        'warehouse_codes': [w['code'] for w in matching_warehouses],
                        'count': len(matching_warehouses),
                        'box_30_value': None
                    }
        
        return {
            'success': True,
            'office_code': office_code,
            'warehouses': matching_warehouses,
            'warehouse_codes': [w['code'] for w in matching_warehouses],
            'count': len(matching_warehouses),
            'box_30_value': selected_warehouse['code'],
            'selected_warehouse': selected_warehouse
        }
    else:
        print(f"❌ No warehouses found for office code: {office_code}")
        return {
            'success': False,
            'error': f'No warehouses found for office code: {office_code}',
            'office_code': office_code,
            'warehouses': [],
            'warehouse_codes': [],
            'count': 0,
            'box_30_value': None
        }

class WarehouseProcessor:
    """Processor class for eSAD warehouse lookup (Box 30)."""
    
    def __init__(self, config: Dict = None):
        """Initialize the WarehouseProcessor."""
        self.config = config or {}
    
    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process input data to determine warehouse code.
        
        Box 49 (Warehouse) is ONLY completed when a Customs Procedure Code (CPC) 
        for warehousing or Free Zone is entered in Box 37. 
        In all other circumstances, it should be left blank.
        
        Args:
            input_data: Dictionary containing invoice_data, bol_data, fields, and existing_fields
            
        Returns:
            Dictionary with processing results
        """
        try:
            # Check if Box 37 has a warehousing/Free Zone CPC code
            existing_fields = input_data.get('existing_fields', {})
            cpc_code = existing_fields.get('37_customs_procedure_code') or existing_fields.get('customs_procedure_code')
            
            # List of CPC codes that require warehouse information
            # These are codes related to warehousing, bonded warehouses, and Free Zones
            warehousing_cpc_codes = [
                '71',  # Placing goods under customs warehousing procedure
                '76',  # Entry for a free zone
                '77',  # Placing goods under the free zone procedure
                # Add more warehousing-related CPC codes as needed
            ]
            
            # Check if CPC requires warehouse info
            requires_warehouse = False
            if cpc_code:
                # Check if the CPC code starts with any warehousing codes
                cpc_str = str(cpc_code)
                requires_warehouse = any(cpc_str.startswith(code) for code in warehousing_cpc_codes)
            
            # If no warehousing CPC, return success with null warehouse (leave blank)
            if not requires_warehouse:
                return {
                    'success': True,
                    'warehouse_code': None,
                    'message': 'Box 49 left blank - no warehousing/Free Zone CPC in Box 37',
                    'requires_warehouse': False
                }
            
            # If warehousing CPC is present, proceed with warehouse lookup
            office_code = self._extract_office_code(input_data)
            
            if not office_code:
                return {
                    'success': False,
                    'error': 'Warehousing CPC present but no office code found',
                    'warehouse_code': None,
                    'requires_warehouse': True
                }
            
            # Get warehouse data
            warehouses = get_warehouse_data()
            if not warehouses:
                return {
                    'success': False,
                    'error': 'No warehouse data found',
                    'warehouse_code': None
                }
            
            # Process warehouse lookup (use auto mode for non-interactive processing)
            results = process_warehouse_lookup(office_code, warehouses, auto_mode=True)
            
            if results['success']:
                return {
                    'success': True,
                    'warehouse_code': results['box_30_value'],
                    'office_code': results['office_code'],
                    'warehouse_name': results['selected_warehouse']['warehouse'],
                    'warehouses_found': results['count'],
                    'requires_warehouse': True
                }
            else:
                return {
                    'success': False,
                    'error': results['error'],
                    'office_code': office_code,
                    'warehouse_code': None,
                    'requires_warehouse': True
                }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'warehouse_code': None
            }
    
    def _extract_office_code(self, input_data: Dict[str, Any]) -> str:
        """Extract office code from input data."""
        # Try to get from existing fields first
        existing_fields = input_data.get('existing_fields', {})
        
        # Look for office code in various field keys
        office_keys = [
            'office_code',
            'office_code_processed',
            '30_office_code',
            'manifest_office_code',
            'office_id'
        ]
        
        for key in office_keys:
            if key in existing_fields and existing_fields[key]:
                return str(existing_fields[key])
        
        # Try to extract from invoice data
        invoice_data = input_data.get('invoice_data', {})
        if invoice_data:
            # Check for office-related fields
            for field in ['office_code', 'office_id', 'manifest_office']:
                if field in invoice_data and invoice_data[field]:
                    return str(invoice_data[field])
        
        # Try to extract from BOL data
        bol_data = input_data.get('bol_data', {})
        if bol_data:
            # Check for office-related fields
            for field in ['office_code', 'office_id', 'manifest_office']:
                if field in bol_data and bol_data[field]:
                    return str(bol_data[field])
        
        return ""

def main():
    """Main function with improved error handling."""
    if len(sys.argv) < 2:
        print("Usage: python -m modules.esad_warehouse <esad_json_path> [--auto]")
        print("  --auto: Automatically select first warehouse when multiple options exist")
        sys.exit(1)
    
    json_path = sys.argv[1]
    auto_mode = "--auto" in sys.argv
    
    try:
        # Get office code from eSAD results
        office_code = get_office_code_from_json(json_path)
        if not office_code:
            print("❌ No office code found in eSAD results")
            sys.exit(1)
        
        print(f"📋 Extracted office code: {office_code}")
        print(f"🔧 Mode: {'🤖 Auto' if auto_mode else '👤 Interactive'}")
        
        # Get warehouse data
        warehouses = get_warehouse_data()
        print(f"📊 Loaded {len(warehouses)} warehouses from database")
        
        # Process warehouse lookup
        results = process_warehouse_lookup(office_code, warehouses, auto_mode)
        
        # Display results
        print(f"\n🏢 Warehouse Lookup Results for Box Field 30:")
        print("=" * 60)
        print(f"Office Code: {results['office_code']}")
        print(f"Status: {'✅ Success' if results['success'] else '❌ Failed'}")
        print(f"Warehouses Found: {results['count']}")
        
        if results['success']:
            print(f"\n📦 Box Field 30 - Location of Goods:")
            print(f"   Selected Warehouse Code: {results['box_30_value']}")
            print(f"   Warehouse Name: {results['selected_warehouse']['warehouse']}")
            print(f"   Office ID: {results['selected_warehouse']['office_id']}")
            
            if results['count'] > 1:
                print(f"\n📋 All Available Warehouses:")
                for i, warehouse in enumerate(results['warehouses'], 1):
                    print(f"  {i}. Code: {warehouse['code']}")
                    print(f"     Name: {warehouse['warehouse']}")
                    print(f"     Office ID: {warehouse['office_id']}")
                    print()
        else:
            print(f"Error: {results['error']}")
        
        # Save results to JSON file
        output_filename = f"warehouse_lookup_{Path(json_path).stem}.json"
        with open(output_filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Results saved to: {output_filename}")
        
        # Return appropriate exit code
        sys.exit(0 if results['success'] else 1)
        
    except FileNotFoundError:
        print(f"Error: File '{json_path}' not found.")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in file '{json_path}'.")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
