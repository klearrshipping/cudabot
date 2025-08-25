#!/usr/bin/env python3
"""
esad_weight.py
───────────────
Validates and populates weight fields from eSAD results.

Usage:
    python -m modules.esad_weight <esad_json_path>

This script:
1. Extracts net_weight and gross_weight from eSAD results
2. Validates weight values and ensures both fields are populated
3. Uses gross weight as fallback for net weight when needed
4. Returns standardized weight data with validation status
5. Handles various weight formats and edge cases
"""

import sys
import json
import re
from typing import Optional, Dict, Union
from decimal import Decimal, InvalidOperation

def get_weight_data_from_json(json_path: str) -> Dict[str, str]:
    """Extract net_weight and gross_weight from eSAD results JSON."""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    extracted_fields = data['result']['extracted_fields']
    
    return {
        'net_weight': extracted_fields.get('net_weight', ''),
        'gross_weight': extracted_fields.get('gross_weight', '')
    }

def clean_weight_value(weight_str: str) -> Optional[str]:
    """Clean and validate weight value."""
    if not weight_str or weight_str.lower() in ['not specified', 'none', '', 'null']:
        return None
    
    # Remove common non-numeric characters except decimal points
    cleaned = re.sub(r'[^\d.,]', '', weight_str)
    
    # Handle different decimal separators
    cleaned = cleaned.replace(',', '.')
    
    # Remove multiple decimal points (keep only the first)
    parts = cleaned.split('.')
    if len(parts) > 2:
        cleaned = parts[0] + '.' + ''.join(parts[1:])
    
    # Validate that it's a valid number
    try:
        float(cleaned)
        return cleaned
    except ValueError:
        return None

def parse_weight_to_decimal(weight_str: str) -> Optional[Decimal]:
    """Parse weight string to Decimal for precise calculations."""
    if not weight_str:
        return None
    
    cleaned = clean_weight_value(weight_str)
    if not cleaned:
        return None
    
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None

def validate_weight_relationship(net_weight: Optional[Decimal], gross_weight: Optional[Decimal]) -> Dict[str, Union[bool, str]]:
    """Validate the relationship between net and gross weight."""
    if not net_weight or not gross_weight:
        return {
            'is_valid': False,
            'reason': 'Missing weight values'
        }
    
    # Net weight should be less than or equal to gross weight
    if net_weight > gross_weight:
        return {
            'is_valid': False,
            'reason': f'Net weight ({net_weight}) cannot be greater than gross weight ({gross_weight})'
        }
    
    # Check if weights are reasonable (not too close to zero or too large)
    if net_weight <= 0 or gross_weight <= 0:
        return {
            'is_valid': False,
            'reason': 'Weight values must be positive'
        }
    
    if gross_weight > 1000000:  # 1 million kg limit
        return {
            'is_valid': False,
            'reason': f'Gross weight ({gross_weight}) seems unreasonably large'
        }
    
    return {
        'is_valid': True,
        'reason': 'Valid weight relationship'
    }

def determine_final_weights(net_weight: Optional[Decimal], gross_weight: Optional[Decimal]) -> Dict[str, Union[str, bool, str]]:
    """Determine final weight values with fallback logic."""
    results = {
        'original_net_weight': str(net_weight) if net_weight else None,
        'original_gross_weight': str(gross_weight) if gross_weight else None,
        'final_net_weight': None,
        'final_gross_weight': None,
        'net_weight_source': None,
        'gross_weight_source': None,
        'validation_status': None,
        'notes': []
    }
    
    # Set final gross weight
    if gross_weight:
        results['final_gross_weight'] = str(gross_weight)
        results['gross_weight_source'] = 'original'
    else:
        results['notes'].append('No gross weight available')
    
    # Set final net weight with fallback logic
    if net_weight:
        results['final_net_weight'] = str(net_weight)
        results['net_weight_source'] = 'original'
    elif gross_weight:
        # Use gross weight as fallback for net weight
        results['final_net_weight'] = str(gross_weight)
        results['net_weight_source'] = 'fallback_from_gross'
        results['notes'].append('Net weight populated using gross weight as fallback')
    else:
        results['notes'].append('No net weight available and no gross weight fallback')
    
    # Validate final weights
    final_net = parse_weight_to_decimal(results['final_net_weight']) if results['final_net_weight'] else None
    final_gross = parse_weight_to_decimal(results['final_gross_weight']) if results['final_gross_weight'] else None
    
    validation = validate_weight_relationship(final_net, final_gross)
    results['validation_status'] = validation['is_valid']
    results['validation_reason'] = validation['reason']
    
    return results

def process_weight_data(net_weight: str, gross_weight: str) -> Dict[str, Union[str, bool, str]]:
    """Process weight data and apply fallback logic."""
    print(f"\n⚖️ Processing weight data:")
    print(f"   Original Net Weight: '{net_weight}'")
    print(f"   Original Gross Weight: '{gross_weight}'")
    
    # Parse weights
    net_decimal = parse_weight_to_decimal(net_weight)
    gross_decimal = parse_weight_to_decimal(gross_weight)
    
    print(f"   Parsed Net Weight: {net_decimal}")
    print(f"   Parsed Gross Weight: {gross_decimal}")
    
    # Determine final weights with fallback logic
    results = determine_final_weights(net_decimal, gross_decimal)
    
    return results

def main():
    """Main function with comprehensive weight processing."""
    if len(sys.argv) < 2:
        print("Usage: python -m modules.esad_weight <esad_json_path>")
        sys.exit(1)
    
    json_path = sys.argv[1]
    
    try:
        # Get weight data from eSAD results
        weight_data = get_weight_data_from_json(json_path)
        print(f"📋 Extracted weight data:")
        print(f"   Net Weight: {weight_data['net_weight']}")
        print(f"   Gross Weight: {weight_data['gross_weight']}")
        
        # Process weight data
        results = process_weight_data(
            weight_data['net_weight'], 
            weight_data['gross_weight']
        )
        
        # Display results
        print(f"\n🏆 Weight Processing Results:")
        print("=" * 60)
        print(f"   Original Net Weight: {results['original_net_weight'] if results['original_net_weight'] else 'None'}")
        print(f"   Original Gross Weight: {results['original_gross_weight'] if results['original_gross_weight'] else 'None'}")
        print(f"   Final Net Weight: {results['final_net_weight'] if results['final_net_weight'] else 'None'}")
        print(f"   Final Gross Weight: {results['final_gross_weight'] if results['final_gross_weight'] else 'None'}")
        print(f"   Net Weight Source: {results['net_weight_source']}")
        print(f"   Gross Weight Source: {results['gross_weight_source']}")
        print(f"   Validation Status: {'✅ VALID' if results['validation_status'] else '❌ INVALID'}")
        print(f"   Validation Reason: {results['validation_reason']}")
        
        if results['notes']:
            print(f"\n📝 Processing Notes:")
            for note in results['notes']:
                print(f"   • {note}")
        
        # Summary
        if results['final_net_weight'] and results['final_gross_weight']:
            if results['validation_status']:
                print(f"\n✅ Successfully processed weights:")
                print(f"   Net Weight: {results['final_net_weight']} kg")
                print(f"   Gross Weight: {results['final_gross_weight']} kg")
                if results['net_weight_source'] == 'fallback_from_gross':
                    print(f"   ⚠️ Note: Net weight was populated using gross weight as fallback")
            else:
                print(f"\n⚠️ Weights processed but validation failed: {results['validation_reason']}")
        else:
            print(f"\n❌ Failed to populate both weight fields")
        
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