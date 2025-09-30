#!/usr/bin/env python3
"""
eSAD Regime Type Processor
Determines appropriate regime type using contextual analysis and LLM reasoning
Enhanced with improved error handling, logging, and data validation
"""

# Standard library imports
import json
import re
import time
import logging
import traceback
import os
import sys
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# Third-party imports
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Add parent directory to path to import config
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))

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
        'X-Title': 'eSAD Regime Processor'
    }

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('esad_regime_processor.log')
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class RegimeTypeResult:
    """Result of regime type determination"""
    regime_type: str
    procedure_code: int
    description: str
    confidence: str
    reasoning: str
    import_export_direction: str
    commercial_determination: str
    contextual_factors: Dict[str, Any]
    processing_time: float = 0.0
    model: str = ""

def extract_ports_from_bol(bol_data: Dict[str, Any]) -> Dict[str, str]:
    """Extract port information from BOL/AWB data using LLM"""
    
    # Safely serialize BOL data to avoid circular references
    def safe_json_dumps(obj, max_depth=3, current_depth=0):
        """Safely serialize JSON with depth limit to avoid circular references"""
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
    
    prompt = f"""
Extract port information from this Bill of Lading/Airway Bill data:

{json.dumps(safe_bol_data, indent=2)}

Look for these field variations:

PORT OF DEPARTURE (ORIGIN):
- Port of Departure
- Port of Loading (POL)
- Port of Shipment
- Port of Origin
- Place of Receipt
- Place of Origin
- Airport of Departure (for AWB)
- Place of Loading
- Port where goods are taken in charge
- Export Port

PORT OF DESTINATION (ARRIVAL):
- Port of Destination
- Port of Discharge (POD)
- Place of Delivery
- Final Destination
- Destination Port
- Airport of Destination (for AWB)
- Place of Discharge
- Port of Arrival
- Port where goods are delivered
- Import Port

Return only a JSON object with:
{{
  "port_of_departure": "extracted departure port",
  "port_of_destination": "extracted destination port"
}}
"""
    
    payload = {
        "model": "openai/gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 500
    }
    
    response = requests.post(OPENROUTER_URL, headers=OPENROUTER_HEADERS, json=payload, timeout=30)
    response_data = response.json()
    content = response_data['choices'][0]['message']['content']
    
    json_match = re.search(r'\{.*\}', content, re.DOTALL)
    result = json.loads(json_match.group())
    
    # Print captured fields
    print("🔍 Captured Port Fields:")
    print(f"  Port of Departure: {result.get('port_of_departure', 'Not found')}")
    print(f"  Port of Destination: {result.get('port_of_destination', 'Not found')}")
    
    return result

def determine_trade_lane(port_of_departure: str, port_of_destination: str) -> str:
    """Determine if transaction is Import or Export based on port locations"""
    
    # Define Jamaica-related terms (case insensitive)
    jamaica_terms = [
        'jamaica', 'kingston', 'montego bay', 'port royal', 
        'falmouth', 'savanna-la-mar', 'port antonio', 'ocho rios',
        'negril', 'mandeville', 'spanish town', 'may pen',
        'nmia', 'norman manley', 'sangster', 'mbj',
        'norman manley international', 'kingston airport'
    ]
    
    # Check if ports contain Jamaica-related terms
    departure_is_jamaica = any(term in port_of_departure.lower() for term in jamaica_terms)
    destination_is_jamaica = any(term in port_of_destination.lower() for term in jamaica_terms)
    
    # Determine trade lane
    if destination_is_jamaica and not departure_is_jamaica:
        trade_lane = "Import"
    elif departure_is_jamaica and not destination_is_jamaica:
        trade_lane = "Export"
    else:
        trade_lane = "Unknown"
    
    # Print trade lane determination
    print(f"🚢 Trade Lane Determination:")
    print(f"  Port of Departure: {port_of_departure} {'(Jamaica)' if departure_is_jamaica else '(Non-Jamaica)'}")
    print(f"  Port of Destination: {port_of_destination} {'(Jamaica)' if destination_is_jamaica else '(Non-Jamaica)'}")
    print(f"  Trade Lane: {trade_lane}")
    
    return trade_lane

def classify_product_commercial_vs_personal(invoice_data: Dict[str, Any], bol_data: Dict[str, Any]) -> Dict[str, Any]:
    """Classify if products are commercial or personal using LLM analysis"""
    
    # Extract product information
    products = []
    
    # From invoice items
    if 'items' in invoice_data and invoice_data['items']:
        for item in invoice_data['items']:
            products.append({
                'description': item.get('description', ''),
                'quantity': item.get('quantity', 0),
                'unit_price': item.get('unit_price', 0),
                'total_price': item.get('total_price', 0),
                'source': 'invoice'
            })
    
    # From BOL cargo details
    if 'cargo' in bol_data:
        cargo = bol_data['cargo']
        if isinstance(cargo, list):
            for item in cargo:
                products.append({
                    'description': item.get('nature_and_quantity_of_goods', ''),
                    'quantity': item.get('no_of_pieces', 0),
                    'unit_price': 0,
                    'total_price': 0,
                    'source': 'bol'
                })
        elif isinstance(cargo, dict):
            products.append({
                'description': cargo.get('commodity_description', ''),
                'quantity': cargo.get('package_count_and_description', 0),
                'unit_price': 0,
                'total_price': 0,
                'source': 'bol'
            })
    
    if not products:
        return {
            'classification': 'Unknown',
            'confidence': 'low',
            'reasoning': 'No product information found',
            'products_analyzed': 0
        }
    
    # Build comprehensive prompt with safe JSON serialization
    def safe_json_dumps(obj, max_depth=3, current_depth=0):
        """Safely serialize JSON with depth limit to avoid circular references"""
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
    
    # Safely serialize data
    safe_invoice_data = safe_json_dumps(invoice_data)
    safe_bol_data = safe_json_dumps(bol_data)
    
    prompt = f"""
Analyze the following products to determine if they are COMMERCIAL or PERSONAL:

PRODUCTS TO ANALYZE:
{json.dumps(products, indent=2)}

ADDITIONAL CONTEXT:
- Invoice Data: {json.dumps(safe_invoice_data, indent=2)}
- BOL Data: {json.dumps(safe_bol_data, indent=2)}

CLASSIFICATION CRITERIA:

COMMERCIAL INDICATORS:
1. BUSINESS USE ITEMS:
   - Office equipment (computers, printers, furniture)
   - Industrial machinery and tools
   - Commercial vehicles (trucks, vans, delivery vehicles)
   - Professional equipment (medical, dental, construction)
   - Manufacturing supplies and raw materials
   - Wholesale quantities (bulk orders)
   - Business software and systems

2. HIGH-VALUE ITEMS:
   - Items over $5,000 USD
   - Luxury goods in commercial quantities
   - Professional-grade equipment
   - Industrial/commercial vehicles

3. COMMERCIAL QUANTITIES:
   - Bulk orders (multiple units of same item)
   - Wholesale quantities
   - Items clearly for resale
   - Professional/industrial quantities

4. BUSINESS ENTITIES:
   - Shipped to/from business addresses
   - Company names in shipping info
   - Commercial invoice formats
   - Business registration numbers

5. COMMERCIAL KEYWORDS:
   - "commercial", "industrial", "professional", "business"
   - "wholesale", "retail", "distribution", "manufacturing"
   - "equipment", "machinery", "systems", "tools"
   - Brand names with commercial models

PERSONAL INDICATORS:
1. HOUSEHOLD ITEMS:
   - Personal electronics (phones, laptops for personal use)
   - Clothing and personal accessories
   - Home appliances and furniture
   - Personal vehicles (cars, motorcycles for personal use)
   - Personal care items
   - Hobby and recreational items

2. PERSONAL QUANTITIES:
   - Single units or small quantities
   - Personal use quantities
   - Individual/household consumption

3. PERSONAL ADDRESSES:
   - Residential addresses
   - Individual names (not company names)
   - Personal shipping information

4. PERSONAL KEYWORDS:
   - "personal", "household", "individual", "private"
   - "home", "family", "personal use"
   - Consumer brand names

GREY ZONE PRODUCTS (Could be Commercial OR Personal):
- Inverters (1kw-15kw range - common in both homes and small businesses)
- Generators (portable to industrial - depends on size and context)
- Solar panels and equipment (residential vs commercial installations)
- Computers and electronics (personal vs business use)
- Tools and equipment (hobby vs professional use)
- Vehicles (personal vs commercial depending on type and use)
- Furniture (home vs office use)

IMPORTANT: Always identify grey zone products first, then apply contextual analysis.
If a product could reasonably be used for both personal and commercial purposes, it is a grey zone product.

GREY ZONE DECISION LOGIC:
When a product falls into the grey zone, determine classification based on CONSIGNEE TYPE + QUANTITY:

1. CONSIGNEE ANALYSIS:
   - Individual Name (John Smith, Mary Johnson) = PERSONAL CONSIGNEE
   - Company Name (ABC Ltd, XYZ Corp, Business Name) = COMMERCIAL CONSIGNEE
   - Business Address (office, warehouse, commercial building) = COMMERCIAL CONSIGNEE
   - Residential Address (home, apartment, house) = PERSONAL CONSIGNEE

2. CONTEXTUAL QUANTITY ANALYSIS:
   Analyze the quantity in context of the product type and consignee to determine if it suggests personal or commercial use:

   PERSONAL USE INDICATORS:
   - Quantity suggests individual/household consumption
   - Reasonable for personal use (e.g., 1 inverter for home, 2 laptops for family)
   - Not excessive for personal needs
   - Typical consumer quantities

   COMMERCIAL USE INDICATORS:
   - Quantity suggests business operations or resale
   - Excessive for personal consumption (e.g., 10 inverters, 50 laptops)
   - Bulk quantities indicating wholesale/distribution
   - Professional/industrial quantities

3. GREY ZONE DECISION LOGIC:
   For grey zone products, analyze the combination of:
   - CONSIGNEE TYPE (Individual vs Business Entity)
   - PRODUCT TYPE (Nature and typical use)
   - QUANTITY CONTEXT (Reasonable for personal vs commercial use)

   DECISION FRAMEWORK:
   1. Identify consignee type (Individual name vs Company name)
   2. Assess if quantity is reasonable for personal consumption of that product type
   3. Consider the nature of the product and its typical use patterns
   4. Make contextual determination based on all factors

   EXAMPLES OF CONTEXTUAL ANALYSIS:
   - Individual + 1 inverter = Personal (reasonable for home use)
   - Individual + 5 inverters = Commercial (excessive for personal use)
   - Individual + 10 Snickers = Personal (reasonable personal consumption)
   - Individual + 100 Snickers = Commercial (excessive for personal consumption)
   - Business + 1 inverter = Commercial (business entity)
   - Business + 10 inverters = Commercial (business entity + bulk quantity)

   CRITICAL: Individual names (like "Rafer Johnson", "John Smith", "Mary Johnson") should be treated as PERSONAL CONSIGNEES regardless of invoice type or supplier context.
   The consignee's individual name takes precedence over other contextual factors for grey zone products.

   IMPORTANT: Use contextual reasoning rather than rigid quantity thresholds.
   Consider what would be reasonable for personal vs commercial use based on the specific product and consignee.

4. BUSINESS ENTITY INDICATORS:
   - Company suffixes: Ltd, LLC, Inc, Corp, Co, Enterprise, etc.
   - Business registration numbers
   - Commercial addresses
   - Professional titles in names

5. PERSONAL ENTITY INDICATORS:
   - Individual names without company suffixes
   - Residential addresses
   - Personal titles (Mr., Mrs., Ms., Dr.)

MIXED INDICATORS:
- Combination of commercial and personal items
- Unclear business vs personal use
- Ambiguous quantities or values

Return ONLY a JSON object with:
{{
  "classification": "Commercial" | "Personal" | "Mixed" | "Unknown",
  "confidence": "high" | "medium" | "low",
  "reasoning": "Detailed explanation of classification decision including grey zone analysis",
  "products_analyzed": number_of_products,
  "commercial_indicators": ["list of commercial indicators found"],
  "personal_indicators": ["list of personal indicators found"],
  "grey_zone_products": ["list of products that could be either commercial or personal"],
  "consignee_analysis": "Analysis of consignee type (individual vs business entity)",
  "quantity_analysis": "Contextual analysis of quantities and their implications for classification",
  "contextual_reasoning": "Detailed explanation of how consignee type, product type, and quantity context were evaluated"
}}
"""
    
    payload = {
        "model": "openai/gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 1000
    }
    
    try:
        response = requests.post(OPENROUTER_URL, headers=OPENROUTER_HEADERS, json=payload, timeout=30)
        response_data = response.json()
        content = response_data['choices'][0]['message']['content']
        
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        result = json.loads(json_match.group())
        
        # Print classification results
        print(f"🏢 Product Classification:")
        print(f"  Classification: {result.get('classification', 'Unknown')}")
        print(f"  Confidence: {result.get('confidence', 'Unknown')}")
        print(f"  Products Analyzed: {result.get('products_analyzed', 0)}")
        print(f"  Grey Zone Products: {result.get('grey_zone_products', [])}")
        print(f"  Consignee Analysis: {result.get('consignee_analysis', 'No analysis provided')}")
        print(f"  Quantity Analysis: {result.get('quantity_analysis', 'No analysis provided')}")
        print(f"  Contextual Reasoning: {result.get('contextual_reasoning', 'No reasoning provided')}")
        print(f"  Final Reasoning: {result.get('reasoning', 'No reasoning provided')}")
        
        return result
        
    except Exception as e:
        print(f"❌ Error in product classification: {e}")
        return {
            'classification': 'Unknown',
            'confidence': 'low',
            'reasoning': f'Classification failed: {str(e)}',
            'products_analyzed': len(products)
        }

def is_motor_vehicle(description: str) -> bool:
    """Use LLM to determine if a product description represents a motor vehicle"""
    if not description or description.lower() in ['not specified', 'none', '']:
        return False
    
    prompt = f"""
Determine if the following product description represents a motor vehicle:

PRODUCT DESCRIPTION: "{description}"

MOTOR VEHICLE CRITERIA:
- Cars, trucks, SUVs, vans, motorcycles, scooters, ATVs
- Boats, yachts, watercraft
- Aircraft, helicopters, drones (if motorized)
- Construction vehicles, heavy machinery with engines
- Recreational vehicles (RVs), campers, trailers with engines
- Electric vehicles (Tesla, electric cars, electric motorcycles)
- Hybrid vehicles
- Any vehicle with an engine or motor for transportation

NOT MOTOR VEHICLES:
- Vehicle parts, accessories, or components
- Vehicle maintenance items (oil, filters, tires)
- Vehicle electronics (stereos, GPS, cameras)
- Vehicle tools or equipment
- Bicycles (unless electric motorized)
- Non-motorized trailers or carts

Return ONLY a JSON object with:
{{
  "is_motor_vehicle": true or false,
  "confidence": "high" | "medium" | "low",
  "reasoning": "Brief explanation of why this is or isn't a motor vehicle"
}}
"""
    
    payload = {
        "model": "openai/gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 200
    }
    
    try:
        response = requests.post(OPENROUTER_URL, headers=OPENROUTER_HEADERS, json=payload, timeout=15)
        response_data = response.json()
        content = response_data['choices'][0]['message']['content']
        
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        result = json.loads(json_match.group())
        
        return result.get('is_motor_vehicle', False)
        
    except Exception as e:
        print(f"❌ Error in motor vehicle detection: {e}")
        return False

def extract_invoice_value(invoice_data: Dict[str, Any]) -> Dict[str, Any]:
    """Use LLM to extract and convert invoice total value to USD"""
    
    # Safely serialize invoice data to avoid circular references
    def safe_json_dumps(obj, max_depth=3, current_depth=0):
        """Safely serialize JSON with depth limit to avoid circular references"""
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
    
    safe_invoice_data = safe_json_dumps(invoice_data)
    
    prompt = f"""
Extract the total invoice value and convert to USD from this invoice data:

INVOICE DATA:
{json.dumps(safe_invoice_data, indent=2)}

EXTRACTION REQUIREMENTS:
1. Find the total invoice amount (look for total_amount, grand_total, invoice_total, etc.)
2. Identify the currency (USD, JMD, EUR, GBP, CAD, etc.)
3. Convert to USD if needed (use approximate rates: JMD=0.0065, EUR=1.1, GBP=1.25, CAD=0.75)
4. Return the value in USD

Return ONLY a JSON object with:
{{
  "total_value_usd": number,
  "original_currency": "currency_code",
  "original_amount": number,
  "confidence": "high" | "medium" | "low",
  "reasoning": "Brief explanation of value extraction and conversion"
}}
"""
    
    payload = {
        "model": "openai/gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 300
    }
    
    try:
        response = requests.post(OPENROUTER_URL, headers=OPENROUTER_HEADERS, json=payload, timeout=15)
        response_data = response.json()
        content = response_data['choices'][0]['message']['content']
        
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        result = json.loads(json_match.group())
        
        return {
            'total_value_usd': result.get('total_value_usd', 0),
            'original_currency': result.get('original_currency', 'USD'),
            'original_amount': result.get('original_amount', 0),
            'confidence': result.get('confidence', 'low'),
            'reasoning': result.get('reasoning', 'Value extraction failed')
        }
        
    except Exception as e:
        print(f"❌ Error in value extraction: {e}")
        return {
            'total_value_usd': 0,
            'original_currency': 'USD',
            'original_amount': 0,
            'confidence': 'low',
            'reasoning': f'Value extraction failed: {str(e)}'
        }

class RegimeTypeProcessor:
    """Processor for determining eSAD regime type using contextual analysis"""
    
    def __init__(self):
        """Initialize with regime types data"""
        self.home_country = "Jamaica"

    def determine_regime_type(self, extracted_data: Dict[str, Any]) -> RegimeTypeResult:
        """
        Main function to determine regime type using LLM-powered analysis
        """
        print("🔍 Determining regime type using LLM-powered analysis...")
        
        start_time = time.time()
        
        try:
            # Extract data components
            invoice_data = extracted_data.get('invoice_data', {})
            bol_data = extracted_data.get('bol_data', {})
            
            # STAGE 1: Extract ports and determine trade lane
            print("📦 STAGE 1: Extracting ports and determining trade lane...")
            ports = extract_ports_from_bol(bol_data)
            trade_lane = determine_trade_lane(
                ports['port_of_departure'], 
                ports['port_of_destination']
            )
            
            # STAGE 2: Classify products (commercial vs personal)
            print("🏢 STAGE 2: Classifying products...")
            product_classification = classify_product_commercial_vs_personal(invoice_data, bol_data)
            
            # STAGE 3: Determine regime type with caveats
            print("📋 STAGE 3: Determining regime type...")
            regime_result = self._determine_regime_type_with_caveats(
                trade_lane, 
                product_classification.get('classification', 'Unknown'), 
                extracted_data
            )
            
            # Create RegimeTypeResult
            processing_time = time.time() - start_time
            
            result = RegimeTypeResult(
                regime_type=regime_result.get('regime_type', 'Unknown'),
                procedure_code=regime_result.get('procedure_code', 0),
                description=regime_result.get('type_of_declaration', 'Unknown'),
                confidence=regime_result.get('confidence', 'low'),
                reasoning=regime_result.get('reasoning', 'No reasoning provided'),
                import_export_direction=trade_lane,
                commercial_determination=product_classification.get('classification', 'Unknown'),
                contextual_factors={
                    'ports': ports,
                    'product_classification': product_classification,
                    'regime_result': regime_result,
                    'caveat_applied': regime_result.get('caveat_applied', None)
                },
                processing_time=processing_time,
                model="openai/gpt-4o-mini"
            )
            
            print(f"✅ Regime type determination completed in {processing_time:.2f}s")
            return result
            
        except Exception as e:
            print(f"❌ Error in regime type determination: {e}")
            traceback.print_exc()
            
            # Return fallback result
            return RegimeTypeResult(
                regime_type="Unknown",
                procedure_code=0,
                description="Unknown",
                confidence="low",
                reasoning=f"Error in processing: {str(e)}",
                import_export_direction="Unknown",
                commercial_determination="Unknown",
                contextual_factors={},
                processing_time=time.time() - start_time,
                model="error"
            )

    def _determine_regime_type_with_caveats(self, trade_lane: str, product_classification: str, extracted_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Determine regime type by matching trade lane and product classification against RegimeType.json with import caveats"""
        
        # Load regime types from data folder
        try:
            regime_file_path = Path("C:/Users/rafer/OneDrive/Desktop/projects/cuda/customs_api/data/RegimeType.json")
            with open(regime_file_path, 'r', encoding='utf-8') as file:
                regime_types = json.load(file)
        except FileNotFoundError:
            print(f"❌ Error: RegimeType.json not found at {regime_file_path}")
            return {
                'regime_type': 'Unknown',
                'procedure_code': 0,
                'type_of_declaration': 'Unknown',
                'confidence': 'low',
                'reasoning': 'RegimeType.json file not found'
            }
        
        # Apply import caveats for commercial classification
        final_classification = product_classification
        caveat_applied = None
        
        if trade_lane == "Import" and extracted_data:
            invoice_data = extracted_data.get('invoice_data', {})
            total_value = 0
            value_source = "unknown"
            
            # Check if CIF result is available (preferred method)
            if 'cif_result' in extracted_data and extracted_data['cif_result'] and extracted_data['cif_result'].get('success'):
                cif_result = extracted_data['cif_result']
                # Use the actual CIF value (Cost + Insurance + Freight) which is the total value for customs
                total_value = cif_result.get('val_note_cif', 0)
                if total_value > 0:
                    value_source = "CIF"
                else:
                    # Fallback to Cost + Freight if CIF not available
                    total_value = cif_result.get('val_note_cost_and_freight', 0)
                    if total_value > 0:
                        value_source = "Cost_and_Freight"
                    else:
                        # Fallback to invoice total if neither CIF nor Cost+Freight available
                        total_value = cif_result.get('val_note_invoice_total_including_freight', 0)
                        value_source = "invoice_total"
            
            # If no CIF result available, extract from invoice using LLM
            if total_value == 0 and invoice_data:
                value_info = extract_invoice_value(invoice_data)
                total_value = value_info['total_value_usd']
                value_source = "LLM_extraction"
            
            if total_value >= 5000:
                final_classification = "Commercial"
                if value_source == "CIF":
                    caveat_applied = f"Value >= $5000 USD (${total_value:,.2f} from CIF calculation)"
                elif value_source == "Cost_and_Freight":
                    caveat_applied = f"Value >= $5000 USD (${total_value:,.2f} from Cost + Freight calculation)"
                elif value_source == "invoice_total":
                    caveat_applied = f"Value >= $5000 USD (${total_value:,.2f} from invoice total)"
                else:
                    caveat_applied = f"Value >= $5000 USD (${total_value:,.2f} from {value_info['original_currency']} {value_info['original_amount']:,.2f})"
            
            # Caveat 2: Check if product is a motor vehicle using LLM
            if 'items' in invoice_data and invoice_data['items']:
                for item in invoice_data['items']:
                    description = item.get('description', '')
                    if is_motor_vehicle(description):
                        final_classification = "Commercial"
                        caveat_applied = f"Motor vehicle detected: {description}"
                        break
        
        # Build LLM prompt for regime type determination
        prompt = f"""
Determine the appropriate regime type based on the following criteria:

TRADE LANE: {trade_lane}
ORIGINAL PRODUCT CLASSIFICATION: {product_classification}
FINAL PRODUCT CLASSIFICATION: {final_classification}
CAVEAT APPLIED: {caveat_applied if caveat_applied else 'None'}

IMPORT CAVEATS (for Import trade lane only):
1. Any product with value >= $5000 USD is automatically Commercial
2. Any motor vehicle is automatically Commercial
3. These caveats override the original product classification

AVAILABLE REGIME TYPES:
{json.dumps(regime_types, indent=2)}

MATCHING CRITERIA:
1. Match the trade lane (Import/Export) with the entry_type field
2. Match the FINAL product classification (Commercial/Personal) with the description field
3. Consider the details field for additional context
4. Return the most appropriate regime type

Return ONLY a JSON object with:
{{
  "regime_type": "selected regime type name",
  "procedure_code": selected_procedure_code,
  "type_of_declaration": "selected type of declaration",
  "confidence": "high" | "medium" | "low",
  "reasoning": "Detailed explanation of why this regime type was selected",
  "matched_criteria": "Which fields matched (entry_type, description, details)",
  "caveat_applied": "{caveat_applied if caveat_applied else 'None'}"
}}
"""
        
        payload = {
            "model": "openai/gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 800
        }
        
        try:
            response = requests.post(OPENROUTER_URL, headers=OPENROUTER_HEADERS, json=payload, timeout=30)
            response_data = response.json()
            content = response_data['choices'][0]['message']['content']
            
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            result = json.loads(json_match.group())
            
            # Print regime type determination results
            print(f"📋 Regime Type Determination:")
            print(f"  Original Classification: {product_classification}")
            print(f"  Final Classification: {final_classification}")
            print(f"  Caveat Applied: {caveat_applied if caveat_applied else 'None'}")
            print(f"  Regime Type: {result.get('regime_type', 'Unknown')}")
            print(f"  Procedure Code: {result.get('procedure_code', 0)}")
            print(f"  Type of Declaration: {result.get('type_of_declaration', 'Unknown')}")
            print(f"  Confidence: {result.get('confidence', 'Unknown')}")
            print(f"  Matched Criteria: {result.get('matched_criteria', 'No criteria provided')}")
            print(f"  Reasoning: {result.get('reasoning', 'No reasoning provided')}")
            
            return result
            
        except Exception as e:
            print(f"❌ Error in regime type determination: {e}")
            return {
                'regime_type': 'Unknown',
                'procedure_code': 0,
                'type_of_declaration': 'Unknown',
                'confidence': 'low',
                'reasoning': f'Regime type determination failed: {str(e)}',
                'caveat_applied': caveat_applied
            }


def main():
    """Test the regime type processor"""
    processor = RegimeTypeProcessor()
    
    test_data = {
        'form_fields': {
            'shipper': 'Test Company Ltd',
            'consignee_name': 'John Doe',
            'bill_of_lading': 'TEST123',
            'weight': '100kg'
        },
        'bol_data': {
            'port_of_discharge': 'Kingston, Jamaica',
            'port_of_loading': 'Miami, USA'
        },
        'existing_fields': {
            '8_importer_consignee_address': 'Kingston, Jamaica',
            '2_exporter_consignor_address': 'Miami, USA'
        },
        'invoice_data': {
            'items': [
                {
                    'description': 'Test equipment',
                    'quantity': 1,
                    'unit_price': 1000,
                    'total_price': 1000
                }
            ]
        },
        'tables': [
            {
                'rows': [
                    ['Total', '1000', 'USD']
                ]
            }
        ],
        'metadata': {
            'document_type': 'Commercial Invoice'
        }
    }
    
    result = processor.determine_regime_type(test_data)
    print(f"\n🎉 Final Result:")
    print(f"   Regime Type: {result.regime_type}")
    print(f"   Description: {result.description}")
    print(f"   Direction: {result.import_export_direction}")
    print(f"   Commercial: {result.commercial_determination}")
    print(f"   Confidence: {result.confidence}")


if __name__ == "__main__":
    main()
