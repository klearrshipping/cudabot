#!/usr/bin/env python3
"""
CSV Data Client
Replaces Supabase functions with CSV file reads for reference data
"""

import os
import pandas as pd
from typing import Dict, List, Optional
import json

# Cache for CSV data to avoid repeated file reads
_csv_cache = {}

def _get_csv_path(filename: str) -> str:
    """Get the full path to a CSV file in the data folder"""
    current_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    return os.path.join(current_dir, 'data', filename)

def _load_csv_data(filename: str, use_cache: bool = True) -> pd.DataFrame:
    """Load CSV data with optional caching"""
    if use_cache and filename in _csv_cache:
        return _csv_cache[filename]
    
    csv_path = _get_csv_path(filename)
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found: {csv_path}")
    
    df = pd.read_csv(csv_path)
    
    if use_cache:
        _csv_cache[filename] = df
    
    return df

def fetch_package_types() -> List[Dict]:
    """Fetch package types from package_type.csv"""
    try:
        df = _load_csv_data('package_type.csv')
        return df.to_dict('records')
    except Exception as e:
        print(f"Error loading package types: {e}")
        return []

def fetch_locodes() -> List[Dict]:
    """Fetch locodes from locode.csv"""
    try:
        df = _load_csv_data('locode.csv')
        return df.to_dict('records')
    except Exception as e:
        print(f"Error loading locodes: {e}")
        return []

def fetch_package_type_by_code(code: str) -> List[Dict]:
    """Fetch package type by code from package_type.csv"""
    try:
        df = _load_csv_data('package_type.csv')
        result = df[df['code'] == code]
        return result.to_dict('records')
    except Exception as e:
        print(f"Error fetching package type by code {code}: {e}")
        return []

def fetch_locode_by_code(locode: str) -> List[Dict]:
    """Fetch locode by code from locode.csv"""
    try:
        df = _load_csv_data('locode.csv')
        result = df[df['locode'] == locode]
        return result.to_dict('records')
    except Exception as e:
        print(f"Error fetching locode by code {locode}: {e}")
        return []

def fetch_financial_transactions() -> List[Dict]:
    """Fetch financial transactions from financial_transaction_final.csv"""
    try:
        df = _load_csv_data('financial_transaction_final.csv')
        return df.to_dict('records')
    except Exception as e:
        print(f"Error loading financial transactions: {e}")
        return []

def fetch_countries() -> List[Dict]:
    """Fetch countries from country.csv"""
    try:
        df = _load_csv_data('country.csv')
        return df.to_dict('records')
    except Exception as e:
        print(f"Error loading countries: {e}")
        return []

def fetch_currencies() -> List[Dict]:
    """Fetch currencies from currency.csv"""
    try:
        df = _load_csv_data('currency.csv')
        return df.to_dict('records')
    except Exception as e:
        print(f"Error loading currencies: {e}")
        return []

def fetch_offices() -> List[Dict]:
    """Fetch offices from office.csv"""
    try:
        df = _load_csv_data('office.csv')
        return df.to_dict('records')
    except Exception as e:
        print(f"Error loading offices: {e}")
        return []

def fetch_warehouses() -> List[Dict]:
    """Fetch warehouses from warehouse.csv"""
    try:
        df = _load_csv_data('warehouse.csv')
        return df.to_dict('records')
    except Exception as e:
        print(f"Error loading warehouses: {e}")
        return []

def fetch_transport_modes() -> List[Dict]:
    """Fetch transport modes from transport_mode.csv"""
    try:
        df = _load_csv_data('transport_mode.csv')
        return df.to_dict('records')
    except Exception as e:
        print(f"Error loading transport modes: {e}")
        return []

def fetch_incoterms() -> List[Dict]:
    """Fetch incoterms from incoterm.csv"""
    try:
        df = _load_csv_data('incoterm.csv')
        return df.to_dict('records')
    except Exception as e:
        print(f"Error loading incoterms: {e}")
        return []

def clear_cache():
    """Clear the CSV data cache"""
    global _csv_cache
    _csv_cache.clear()
