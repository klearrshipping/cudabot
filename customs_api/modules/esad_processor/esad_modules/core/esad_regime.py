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

# Import product classification module
try:
    from .esad_product_classification import classify_product_commercial_vs_personal
except ImportError:
    from esad_product_classification import classify_product_commercial_vs_personal

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
    
    def to_json(self) -> Dict[str, Any]:
        """Convert RegimeTypeResult to JSON-serializable dictionary"""
        return {
            "regime_type": self.regime_type,
            "procedure_code": self.procedure_code,
            "description": self.description,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "import_export_direction": self.import_export_direction,
            "commercial_determination": self.commercial_determination,
            "contextual_factors": self.contextual_factors,
            "processing_time": self.processing_time,
            "model": self.model,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_summary_json(self) -> Dict[str, Any]:
        """Get formatted summary as JSON data"""
        port_data = self.contextual_factors.get('port_data', {})
        trade_lane = self.contextual_factors.get('trade_lane_result', {})
        product_class = self.contextual_factors.get('product_classification', {})
        regime_result = self.contextual_factors.get('regime_result', {})
        
        return {
            "key_results_summary": {
                "regime_type": self.regime_type,
                "procedure_code": self.procedure_code,
                "description": self.description,
                "direction": self.import_export_direction,
                "classification": self.commercial_determination,
                "confidence": self.confidence,
                "processing_time_seconds": round(self.processing_time, 2)
            },
            "port_country_information": {
                "last_port_of_departure": {
                    "port_name": port_data.get('last_port_of_departure', {}).get('port_name', 'Unknown'),
                    "country": port_data.get('last_port_of_departure', {}).get('country', 'Unknown')
                },
                "jamaica_port_of_entry": {
                    "port_name": port_data.get('jamaica_port_of_entry', {}).get('port_name', 'Unknown')
                },
                "country_of_origin": port_data.get('country_of_origin', 'Unknown'),
                "country_of_export": port_data.get('country_of_export', 'Unknown'),
                "country_of_last_departure": port_data.get('country_of_last_departure', 'Unknown')
            },
            "trade_lane_analysis": {
                "direction": trade_lane.get('trade_lane', 'Unknown'),
                "departure_is_jamaica": trade_lane.get('analysis', {}).get('last_port_of_departure', {}).get('is_jamaica', 'Unknown'),
                "destination_is_jamaica": trade_lane.get('analysis', {}).get('jamaica_port_of_entry', {}).get('is_jamaica', 'Unknown')
            },
            "product_classification": {
                "classification": product_class.get('classification', 'Unknown'),
                "confidence": product_class.get('confidence', 'Unknown'),
                "products_analyzed": product_class.get('products_analyzed', 'Unknown'),
                "grey_zone_products": product_class.get('grey_zone_products', []),
                "personal_indicators": product_class.get('personal_indicators', []),
                "commercial_indicators": product_class.get('commercial_indicators', [])
            },
            "regime_determination": {
                "original_classification": regime_result.get('original_classification', 'Unknown'),
                "final_classification": regime_result.get('final_classification', 'Unknown'),
                "caveat_applied": regime_result.get('caveat_applied', 'None'),
                "matched_criteria": regime_result.get('matched_criteria', 'Unknown')
            }
        }

def extract_ports_from_bol(bol_data: Dict[str, Any], invoice_data: Dict[str, Any] = None) -> Dict[str, Any]:
    """Extract comprehensive port and country information from BOL/AWB and invoice data using LLM"""
    
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
    safe_invoice_data = safe_json_dumps(invoice_data) if invoice_data else {}
    
    prompt = f"""
You are analyzing a Bill of Lading (BOL) or Airway Bill (AWB) and Commercial Invoice for goods being imported into Jamaica. 

Extract and identify the following information:

1. LAST PORT OF DEPARTURE (Immediate Origin)
   - This is the port from which goods were shipped DIRECTLY to Jamaica
   - If the shipment involved transshipment, identify the LAST intermediate port before Jamaica
   - Look for: "Airport of Departure", "Port of Loading", "Transshipment Port"

2. JAMAICA PORT OF ENTRY (Destination)
   - This is the port where goods physically arrived in Jamaica
   - Look for: "Port of Discharge (POD)", "Airport of Destination", "Port of Entry"
   - Common Jamaica ports: Kingston, Montego Bay (seaports); Norman Manley International, Sangster International (airports)

3. COUNTRY OF EXPORT (Shipper's Country)
   - This is the country where the SHIPPER/EXPORTING COMPANY is located
   - Look for: Shipper's address, company location in "Shipper's Name and Address" field
   - This represents the country of the exporting business entity

4. COUNTRY OF LAST DEPARTURE
   - This is the country where the Last Port of Departure is located
   - This is where the vessel/aircraft physically departed from before arriving in Jamaica
   - May differ from Country of Export if goods were transshipped

5. COUNTRY OF ORIGIN
   - This is the country where the goods were manufactured, produced, or grown
   - Look for: "Country of Origin", "C/T/O", "Made in", "Product of", "Origin"
   - This information is typically found in the COMMERCIAL INVOICE, not the BOL
   - Check invoice fields like: country_of_origin, invoice_details.country_of_origin, etc.

BOL/AWB DATA:
{json.dumps(safe_bol_data, indent=2)}

COMMERCIAL INVOICE DATA:
{json.dumps(safe_invoice_data, indent=2)}

Return your response in the following JSON format:
{{
  "last_port_of_departure": {{
    "port_name": "",
    "country": "",
    "port_code": ""
  }},
  "jamaica_port_of_entry": {{
    "port_name": "",
    "port_code": ""
  }},
  "country_of_export": "",
  "country_of_last_departure": "",
  "country_of_origin": ""
}}

If any information is not found in the document, use "Not specified" as the value.
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
        
        # Add extraction metadata
        result['extraction_metadata'] = {
            'status': 'success',
            'message': 'Port and country information successfully extracted',
            'data_sources': {
                'bol_data': True,
                'invoice_data': invoice_data is not None
            }
        }
        
        return result
        
    except Exception as e:
        # Return fallback structure with error metadata
        return {
            "last_port_of_departure": {
                "port_name": "Not specified",
                "country": "Not specified",
                "port_code": "Not specified"
            },
            "jamaica_port_of_entry": {
                "port_name": "Not specified",
                "port_code": "Not specified"
            },
            "country_of_export": "Not specified",
            "country_of_last_departure": "Not specified",
            "country_of_origin": "Not specified",
            "extraction_metadata": {
                "status": "error",
                "message": f"Port extraction failed: {str(e)}",
                "data_sources": {
                    "bol_data": True,
                    "invoice_data": invoice_data is not None
                }
            }
        }

def determine_trade_lane(port_data: Dict[str, Any]) -> str:
    """Determine if transaction is Import or Export based on port and country information"""
    
    # Extract port information from the new structure
    last_port = port_data.get('last_port_of_departure', {})
    jamaica_port = port_data.get('jamaica_port_of_entry', {})
    country_of_export = port_data.get('country_of_export', '')
    country_of_last_departure = port_data.get('country_of_last_departure', '')
    
    # Get port names and countries
    departure_port_name = last_port.get('port_name', '')
    departure_country = last_port.get('country', '')
    destination_port_name = jamaica_port.get('port_name', '')
    
    # Define Jamaica-related terms (case insensitive)
    jamaica_terms = [
        'jamaica', 'kingston', 'montego bay', 'port royal', 
        'falmouth', 'savanna-la-mar', 'port antonio', 'ocho rios',
        'negril', 'mandeville', 'spanish town', 'may pen',
        'nmia', 'norman manley', 'sangster', 'mbj',
        'norman manley international', 'kingston airport'
    ]
    
    # Check if departure location is Jamaica-related
    departure_is_jamaica = (
        any(term in departure_port_name.lower() for term in jamaica_terms) or
        any(term in departure_country.lower() for term in jamaica_terms) or
        'jamaica' in departure_country.lower()
    )
    
    # Check if destination is Jamaica-related
    destination_is_jamaica = (
        any(term in destination_port_name.lower() for term in jamaica_terms) or
        'jamaica' in destination_port_name.lower()
    )
    
    # Determine trade lane
    if destination_is_jamaica and not departure_is_jamaica:
        trade_lane = "Import"
    elif departure_is_jamaica and not destination_is_jamaica:
        trade_lane = "Export"
    else:
        trade_lane = "Unknown"
    
    # Return trade lane determination with metadata
    trade_lane_result = {
        "trade_lane": trade_lane,
        "analysis": {
            "last_port_of_departure": {
                "port_name": departure_port_name,
                "country": departure_country,
                "is_jamaica": departure_is_jamaica
            },
            "jamaica_port_of_entry": {
                "port_name": destination_port_name,
                "is_jamaica": destination_is_jamaica
            },
            "country_of_export": country_of_export,
            "country_of_last_departure": country_of_last_departure
        },
        "determination_metadata": {
            "status": "success",
            "message": f"Trade lane determined as {trade_lane}",
            "jamaica_terms_checked": len(jamaica_terms)
        }
    }
    
    return trade_lane_result

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
        
        start_time = time.time()
        
        try:
            # Extract data components
            invoice_data = extracted_data.get('invoice_data', {})
            bol_data = extracted_data.get('bol_data', {})
            
            # STAGE 1: Extract ports and determine trade lane
            port_data = extract_ports_from_bol(bol_data, invoice_data)
            trade_lane_result = determine_trade_lane(port_data)
            trade_lane = trade_lane_result.get('trade_lane', 'Unknown')
            
            # STAGE 2: Classify products (commercial vs personal)
            product_classification = classify_product_commercial_vs_personal(invoice_data, bol_data)
            
            # STAGE 3: Determine regime type with caveats
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
                    'port_data': port_data,
                    'trade_lane_result': trade_lane_result,
                    'product_classification': product_classification,
                    'regime_result': regime_result,
                    'caveat_applied': regime_result.get('caveat_applied', None),
                    'processing_metadata': {
                        'stages_completed': 3,
                        'stage_1': 'Port extraction and trade lane determination',
                        'stage_2': 'Product classification',
                        'stage_3': 'Regime type determination',
                        'total_processing_time': processing_time,
                        'model_used': 'openai/gpt-4o-mini'
                    }
                },
                processing_time=processing_time,
                model="openai/gpt-4o-mini"
            )
            
            return result
            
        except Exception as e:
            # Return fallback result
            return RegimeTypeResult(
                regime_type="Unknown",
                procedure_code=0,
                description="Unknown",
                confidence="low",
                reasoning=f"Error in processing: {str(e)}",
                import_export_direction="Unknown",
                commercial_determination="Unknown",
                contextual_factors={
                    'error': {
                        'status': 'error',
                        'message': f"Regime type determination failed: {str(e)}",
                        'error_type': type(e).__name__
                    }
                },
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
            
            # Add additional metadata to regime result
            result['original_classification'] = product_classification
            result['final_classification'] = final_classification
            result['caveat_applied'] = caveat_applied if caveat_applied else 'None'
            result['determination_metadata'] = {
                'status': 'success',
                'message': 'Regime type successfully determined',
                'original_classification': product_classification,
                'final_classification': final_classification,
                'caveat_applied': caveat_applied if caveat_applied else 'None'
            }
            
            return result
            
        except Exception as e:
            return {
                'regime_type': 'Unknown',
                'procedure_code': 0,
                'type_of_declaration': 'Unknown',
                'confidence': 'low',
                'reasoning': f'Regime type determination failed: {str(e)}',
                'original_classification': product_classification,
                'final_classification': final_classification,
                'caveat_applied': caveat_applied if caveat_applied else 'None',
                'determination_metadata': {
                    'status': 'error',
                    'message': f'Regime type determination failed: {str(e)}',
                    'error_type': type(e).__name__,
                    'original_classification': product_classification,
                    'final_classification': final_classification,
                    'caveat_applied': caveat_applied if caveat_applied else 'None'
                }
            }


def main():
    """Test the regime type processor with JSON output"""
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
            'port_of_loading': 'Miami, USA',
            'shipper': {
                'name': 'Test Shipper Inc',
                'address': '123 Business St, Miami, FL, USA'
            },
            'consignee': {
                'name': 'Test Consignee Ltd',
                'address': '456 Main St, Kingston, Jamaica'
            }
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
    
    # Output as JSON
    print(json.dumps(result.to_json(), indent=2))
    
    # Output formatted summary as JSON
    print(json.dumps(result.get_summary_json(), indent=2))


if __name__ == "__main__":
    main()
