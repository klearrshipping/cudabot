#!/usr/bin/env python3
"""
eSAD Regime Type Processor
Determines appropriate regime type using contextual analysis and LLM reasoning
"""

import json
import re
import requests
import time
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# Add parent directory to path to import config
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import OPENROUTER_API_KEY, OPENROUTER_URL, OPENROUTER_HEADERS

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

class RegimeTypeProcessor:
    """Processor for determining eSAD regime type using contextual analysis"""
    
    def __init__(self):
        """Initialize with regime types data"""
        self.home_country = "Jamaica"
        self.jamaican_locations = [
            'kingston', 'spanish town', 'portmore', 'may pen', 'old harbour',
            'mandeville', 'santa cruz', 'savanna-la-mar', 'negril', 'lucea',
            'montego bay', 'falmouth', 'ocho rios', 'port antonio', 'morant bay',
            'port maria', 'annotto bay', 'st. ann\'s bay', 'brown\'s town',
            'alexandria', 'linstead', 'bog walk'
        ]
        
        self.commercial_keywords = [
            'ltd', 'limited', 'corp', 'corporation', 'inc', 'incorporated',
            'company', 'co', 'distributors', 'distributor', 'trading',
            'imports', 'exports', 'wholesale', 'retail', 'enterprise',
            'enterprises', 'group', 'holdings', 'supplies', 'suppliers',
            'services', 'solutions', 'systems', 'international', 'global'
        ]
        
        # Load regime types from the provided data
        self.regime_types = [
            {
                "id": 1, "regime_type": "IM4", "type_of_declaration": "IM", "procedure_code": 4,
                "details": "Goods for Commercial Use (Resale), Motor Vehicles and Goods with a CIF value greater than US $5,000",
                "description": "Commercial Import", "entry_type": "Import"
            },
            {
                "id": 2, "regime_type": "IM7", "type_of_declaration": "IM", "procedure_code": 7,
                "details": "Goods to be stored in a Bonded Warehouse",
                "description": "Entry for Warehousing", "entry_type": "Import"
            },
            {
                "id": 3, "regime_type": "IM5", "type_of_declaration": "IM", "procedure_code": 5,
                "details": "Goods that will be Imported Temporarily",
                "description": "Temporary Import", "entry_type": "Import"
            },
            {
                "id": 4, "regime_type": "IMS4", "type_of_declaration": "IMS", "procedure_code": 4,
                "details": "Goods for personal use that have a CIF value less than US $5,000.00",
                "description": "Simplified Declaration for Import", "entry_type": "Import"
            },
            {
                "id": 5, "regime_type": "IM8", "type_of_declaration": "IM", "procedure_code": 8,
                "details": "Goods being transhipped through Jamaica (Transshipment)",
                "description": "Customs Transit/Transshipment", "entry_type": "Import"
            },
            {
                "id": 6, "regime_type": "IM9", "type_of_declaration": "IM", "procedure_code": 9,
                "details": "Goods to be stored in a Free Zone",
                "description": "Free Zone Entry", "entry_type": "Import"
            },
            {
                "id": 7, "regime_type": "IMD4", "type_of_declaration": "IMD", "procedure_code": 4,
                "details": "Goods for Immediate Delivery",
                "description": "Immediate Delivery – Import for Home Use", "entry_type": "Import"
            },
            {
                "id": 8, "regime_type": "IM6", "type_of_declaration": "IM", "procedure_code": 6,
                "details": "Goods that are being Re-Imported",
                "description": "Re-Importation", "entry_type": "Import"
            },
            {
                "id": 22, "regime_type": "EX1", "type_of_declaration": "EX", "procedure_code": 1,
                "details": "Goods for Export (Permanent)",
                "description": "Permanent Export", "entry_type": "Export"
            },
            {
                "id": 23, "regime_type": "EX8", "type_of_declaration": "EX", "procedure_code": 8,
                "details": "Goods in Transit for Export",
                "description": "Transit to Export", "entry_type": "Export"
            },
            {
                "id": 24, "regime_type": "EX2", "type_of_declaration": "EX", "procedure_code": 2,
                "details": "Goods that will be Temporarily Exported",
                "description": "Temporary Export", "entry_type": "Export"
            },
            {
                "id": 25, "regime_type": "EX3", "type_of_declaration": "EX", "procedure_code": 3,
                "details": "Goods for Re-Exportation",
                "description": "Re-Exportation", "entry_type": "Export"
            }
        ]
    
    def determine_regime_type(self, extracted_data: Dict[str, Any]) -> RegimeTypeResult:
        """
        Main function to determine regime type using contextual analysis
        """
        print("🔍 Determining regime type...")
        
        # Step 1: Determine import/export direction
        direction_info = self._determine_import_export(extracted_data)
        
        # Step 2: Analyze commercial vs personal
        commercial_info = self._analyze_commercial_nature(extracted_data, direction_info)
        
        # Step 3: Extract contextual factors
        context = self._extract_contextual_factors(extracted_data)
        
        # Step 4: Filter regime types based on direction
        relevant_regimes = self._filter_regime_types_by_direction(direction_info['direction'])
        
        # Step 5: Use LLM to select appropriate regime type
        llm_result = self._call_llm_for_regime_selection(
            extracted_data, direction_info, commercial_info, context, relevant_regimes
        )
        
        return llm_result
    
    def _determine_import_export(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Determine if this is import or export based on consignee location"""
        
        form_fields = data.get('form_fields', {})
        
        # Get consignee address and related fields
        consignee_address = form_fields.get('consignee_address', '')
        consignee_name = form_fields.get('consignee_name', '')
        port_of_destination = form_fields.get('port_of_destination', '')
        
        # Combine all address-related fields for analysis
        address_text = f"{consignee_address} {consignee_name} {port_of_destination}".lower()
        
        print(f"📍 Analyzing address: {address_text}")
        
        # Check for Jamaican indicators
        is_jamaica = False
        jamaica_indicators = []
        
        # Check for explicit Jamaica mentions
        if 'jamaica' in address_text or 'ja' in address_text:
            is_jamaica = True
            jamaica_indicators.append('Country name found')
        
        # Check for Jamaican locations
        for location in self.jamaican_locations:
            if location in address_text:
                is_jamaica = True
                jamaica_indicators.append(f'Jamaican location: {location}')
        
        # Check for Jamaican postal patterns (Kingston 11, etc.)
        jamaica_postal_pattern = r'kingston\s+\d+'
        if re.search(jamaica_postal_pattern, address_text):
            is_jamaica = True
            jamaica_indicators.append('Jamaican postal code pattern')
        
        direction = "Import" if is_jamaica else "Export"
        
        result = {
            'direction': direction,
            'consignee_in_jamaica': is_jamaica,
            'jamaica_indicators': jamaica_indicators,
            'analyzed_text': address_text,
            'home_country_entity': consignee_name if is_jamaica else form_fields.get('shipper', ''),
            'foreign_entity': form_fields.get('shipper', '') if is_jamaica else consignee_name
        }
        
        print(f"📦 Direction: {direction}")
        print(f"🏠 Home country entity: {result['home_country_entity']}")
        
        return result
    
    def _analyze_commercial_nature(self, data: Dict[str, Any], direction_info: Dict) -> Dict[str, Any]:
        """Analyze whether this is commercial or personal shipment using comprehensive framework"""
        
        print("🏢 Analyzing commercial nature using comprehensive framework...")
        
        # Use the new comprehensive product classification
        product_classification = self._classify_product_commercial_vs_household(data)
        
        # Get the overall classification
        overall_class = product_classification['overall_classification']
        
        # Determine if this is commercial based on the new framework
        is_commercial = overall_class['classification'] in ['Commercial', 'Mixed']
        
        # Legacy analysis for backward compatibility
        form_fields = data.get('form_fields', {})
        entity_name = direction_info['home_country_entity'].lower()
        
        # Check for commercial keywords in entity name (legacy method)
        commercial_keywords_found = []
        for keyword in self.commercial_keywords:
            if keyword in entity_name:
                commercial_keywords_found.append(keyword)
        
        has_commercial_keywords = len(commercial_keywords_found) > 0
        
        # Containerization analysis
        is_containerized = bool(form_fields.get('container', '') or form_fields.get(':_container_no', ''))
        
        # Enhanced commercial analysis combining both approaches
        commercial_analysis = {
            'entity_name': direction_info['home_country_entity'],
            'commercial_keywords_found': commercial_keywords_found,
            'has_commercial_keywords': has_commercial_keywords,
            'is_containerized': is_containerized,
            
            # New comprehensive framework results
            'product_classification': product_classification,
            'overall_classification': overall_class['classification'],
            'classification_confidence': overall_class['confidence'],
            'commercial_percentage': overall_class.get('commercial_percentage', 0),
            'household_percentage': overall_class.get('household_percentage', 0),
            
            # Combined commercial determination
            'is_commercial_by_framework': is_commercial,
            'is_commercial_by_legacy': has_commercial_keywords or is_containerized,
            'final_commercial_determination': is_commercial or has_commercial_keywords or is_containerized,
            
            # Detailed breakdown
            'products_analyzed': product_classification['products'],
            'commercial_count': product_classification['commercial_count'],
            'household_count': product_classification['household_count']
        }
        
        print(f"🏢 Enhanced Commercial Analysis:")
        print(f"   Entity: {commercial_analysis['entity_name']}")
        print(f"   Legacy commercial indicators: {commercial_keywords_found}")
        print(f"   Containerized: {is_containerized}")
        print(f"   Framework classification: {overall_class['classification']} ({overall_class['confidence']})")
        print(f"   Commercial products: {product_classification['commercial_count']}")
        print(f"   Household products: {product_classification['household_count']}")
        print(f"   Final determination: {'Commercial' if commercial_analysis['final_commercial_determination'] else 'Household'}")
        
        return commercial_analysis
    
    def _extract_package_info(self, tables: List) -> Dict[str, Any]:
        """Extract package quantity and type information from tables"""
        
        package_info = {
            'quantity': '',
            'type': '',
            'description': ''
        }
        
        for table in tables:
            headers = table.get('headers', [])
            rows = table.get('rows', [])
            
            # Look for package column
            for header_row in headers:
                for i, header in enumerate(header_row):
                    if 'package' in str(header).lower():
                        for row in rows:
                            if len(row) > i and row[i]:
                                package_text = str(row[i])
                                package_info['description'] = package_text
                                
                                # Extract quantity and type
                                match = re.search(r'(\d+)\s+(\w+)', package_text)
                                if match:
                                    package_info['quantity'] = match.group(1)
                                    package_info['type'] = match.group(2)
                                break
        
        return package_info
    
    def _extract_contextual_factors(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract all contextual factors for LLM analysis"""
        
        form_fields = data.get('form_fields', {})
        tables = data.get('tables', [])
        
        # Extract value information
        invoice_value = ''
        currency = ''
        
        for table in tables:
            rows = table.get('rows', [])
            for row in rows:
                if 'total' in str(row).lower():
                    for cell in row:
                        if cell and str(cell).replace(',', '').replace('.', '').isdigit():
                            amount = str(cell).replace(',', '')
                            if float(amount) > 0:
                                invoice_value = amount
                
                # Look for currency
                for cell in row:
                    if cell in ['USD', 'JMD', 'EUR', 'GBP', 'CAD']:
                        currency = cell
        
        context = {
            'invoice_value': invoice_value,
            'currency': currency,
            'vessel_info': form_fields.get('vessel/voyage', ''),
            'bill_of_lading': form_fields.get('bill_of_lading', ''),
            'port_of_origin': form_fields.get('port_of_origin', ''),
            'port_of_destination': form_fields.get('port_of_destination', ''),
            'document_type': data.get('metadata', {}).get('document_type', ''),
            'containers': [
                form_fields.get('container', ''),
                form_fields.get(':_container_no', '')
            ]
        }
        
        return context
    
    def _filter_regime_types_by_direction(self, direction: str) -> List[Dict]:
        """Filter regime types based on import/export direction"""
        
        entry_type = "Import" if direction == "Import" else "Export"
        
        filtered_regimes = [
            regime for regime in self.regime_types 
            if regime['entry_type'] == entry_type
        ]
        
        print(f"📋 Found {len(filtered_regimes)} relevant regime types for {direction}")
        
        return filtered_regimes
    
    def process_with_primary_backup(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process regime type determination with primary/backup models"""
        
        print("🚀 Starting regime type determination with primary/backup models...")
        
        # Step 1: Determine import/export direction
        direction_info = self._determine_import_export(extracted_data)
        
        # Step 2: Analyze commercial vs personal
        commercial_info = self._analyze_commercial_nature(extracted_data, direction_info)
        
        # Step 3: Extract contextual factors
        context = self._extract_contextual_factors(extracted_data)
        
        # Step 4: Filter regime types based on direction
        relevant_regimes = self._filter_regime_types_by_direction(direction_info['direction'])
        
        # Step 5: Build the prompt once
        prompt = self._build_regime_selection_prompt(
            extracted_data, direction_info, commercial_info, context, relevant_regimes
        )
        
        # Define primary and backup models
        primary_model = "mistralai/mistral-small-3.1-24b-instruct:free"
        backup_model = "openai/gpt-4o-mini:free"
        
        print(f"🤖 Primary model: {primary_model}")
        print(f"🔄 Backup model: {backup_model}")
        
        try:
            result = self._call_openrouter_model(primary_model, prompt, backup_model, 
                                               direction_info, commercial_info, context)
            
            # Create result data
            result_data = {
                'timestamp': datetime.now().isoformat(),
                'source_document': 'extracted_data',
                'primary_model': primary_model,
                'backup_model': backup_model,
                'result': {
                    'regime_type': result.regime_type,
                    'procedure_code': result.procedure_code,
                    'description': result.description,
                    'confidence': result.confidence,
                    'reasoning': result.reasoning,
                    'import_export_direction': result.import_export_direction,
                    'commercial_determination': result.commercial_determination,
                    'processing_time': result.processing_time,
                    'model_used': result.model
                }
            }
            
            # Save results to JSON file
            self._save_regime_results(result_data)
            
            return result_data
            
        except Exception as e:
            print(f"❌ Both models failed: {e}")
            error_data = {
                'timestamp': datetime.now().isoformat(),
                'source_document': 'extracted_data',
                'error': str(e)
            }
            
            # Save error results to JSON file
            self._save_regime_results(error_data)
            
            return error_data
    
    def _call_llm_for_regime_selection(self, data: Dict, direction_info: Dict, commercial_info: Dict, 
                                     context: Dict, relevant_regimes: List[Dict]) -> RegimeTypeResult:
        """Call LLM to select the most appropriate regime type (single model version)"""
        
        prompt = self._build_regime_selection_prompt(
            data, direction_info, commercial_info, context, relevant_regimes
        )
        
        try:
            start_time = time.time()
            
            payload = {
                "model": "mistralai/mistral-small-3.1-24b-instruct:free",
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.1,
                "max_tokens": 1000
            }
            
            response = requests.post(
                OPENROUTER_URL,
                headers=OPENROUTER_HEADERS,
                json=payload,
                timeout=60
            )
            
            processing_time = time.time() - start_time
            
            if response.status_code == 200:
                response_data = response.json()
                content = response_data['choices'][0]['message']['content']
                
                # Parse LLM response
                result = self._parse_regime_selection_response(
                    content, direction_info, commercial_info, context
                )
                
                print(f"🤖 LLM selected regime: {result.regime_type} - {result.description}")
                print(f"⚡ Processing time: {processing_time:.2f}s")
                
                return result
            
            else:
                # Fallback logic
                return self._fallback_regime_selection(direction_info, commercial_info, context)
        
        except Exception as e:
            print(f"❌ LLM call failed: {e}")
            return self._fallback_regime_selection(direction_info, commercial_info, context)
    
    def _build_regime_selection_prompt(self, data: Dict, direction_info: Dict, commercial_info: Dict, 
                                     context: Dict, relevant_regimes: List[Dict]) -> str:
        """Build comprehensive prompt for regime type selection"""
        
        prompt = f"""
TASK: Select the most appropriate eSAD regime type for customs declaration.

SHIPMENT ANALYSIS:
================

DIRECTION: {direction_info['direction']}
- Home country entity: {direction_info['home_country_entity']}
- Foreign entity: {direction_info['foreign_entity']}
- Consignee in Jamaica: {direction_info['consignee_in_jamaica']}

COMMERCIAL ANALYSIS:
===================
- Entity name: {commercial_info['entity_name']}
- Commercial keywords found: {commercial_info['commercial_keywords_found']}
- Has commercial indicators: {commercial_info['has_commercial_keywords']}
- Weight: {commercial_info['weight']}
- Package info: {commercial_info['package_info']}
- Commercial description: {commercial_info['commercial_description']}
- Containerized: {commercial_info['is_containerized']}

CONTEXTUAL FACTORS:
==================
- Invoice value: {context['invoice_value']} {context['currency']}
- Document type: {context['document_type']}
- Bill of lading: {context['bill_of_lading']}
- Port of origin: {context['port_of_origin']}
- Port of destination: {context['port_of_destination']}
- Containers: {context['containers']}

AVAILABLE REGIME TYPES:
======================
"""
        
        for regime in relevant_regimes:
            prompt += f"""
{regime['regime_type']} - {regime['description']}
Details: {regime['details']}
"""
        
        prompt += """

SELECTION CRITERIA:
==================
1. Commercial vs Personal Analysis (PRIMARY FACTOR):
   - Look at entity name keywords (Ltd, Corp, Distributors, etc.)
   - Consider quantity and weight in context of product type
   - 321 boxes of footwear (6149 KGS) = clearly commercial
   - 1-2 personal items = personal use
   - IMPORTANT: If item is deemed commercial, it remains commercial regardless of value

2. Value Thresholds (SECONDARY FACTOR):
   - >US$5,000 = IM4 (Commercial Import) - Standard commercial declaration
   - <US$5,000 = IMS4 (Simplified Declaration) - For personal use items only
   - <US$5,000 + Commercial indicators = IM4 (Commercial Import) - Commercial items always use commercial declaration

3. Special Circumstances (ONLY if explicitly documented):
   - Bonded warehouse storage = IM7
   - Temporary import = IM5
   - Re-importation = IM6
   - Transit/transshipment = IM8
   - Free zone storage = IM9
   - Immediate delivery = IMD4 (ONLY for urgent commercial deliveries)

4. Decision Priority Order:
   a) First: Determine if item is commercial or personal
   b) Second: Apply value thresholds based on commercial/personal classification
   c) Third: Apply special circumstances (if documented)
   d) Default: IM4 for commercial items, IMS4 for personal items

INSTRUCTIONS:
============
1. ALWAYS start with commercial vs personal analysis
2. If commercial indicators present (containerized, business entity, high quantity), use commercial declaration
3. Value thresholds only determine the TYPE of commercial declaration (IM4 vs IMD4)
4. Personal items below $5,000 can use IMS4
5. Commercial items below $5,000 still use IM4 (not IMS4)
6. Select the single most appropriate regime type

OUTPUT FORMAT:
==============
{
  "regime_type": "IM4",
  "confidence": "high",
  "reasoning": "Item is commercial (containerized shipment, business transaction) regardless of value $1,496.93. Commercial items always require commercial declaration (IM4), not simplified declaration (IMS4)."
}
"""
        
        return prompt
    
    def _parse_regime_selection_response(self, content: str, direction_info: Dict, 
                                       commercial_info: Dict, context: Dict) -> RegimeTypeResult:
        """Parse LLM response and create result object"""
        
        print(f"🔍 Parsing LLM response...")
        print(f"📝 Raw LLM content: {content[:200]}...")
        
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                print(f"📋 Extracted JSON: {json_str}")
                
                response_data = json.loads(json_str)
                print(f"✅ Parsed response data: {response_data}")
                
                selected_regime_type = response_data.get('regime_type', 'IM4')
                confidence = response_data.get('confidence', 'medium')
                reasoning = response_data.get('reasoning', 'LLM selection')
                
                print(f"🎯 LLM selected regime: {selected_regime_type}")
                print(f"💭 LLM reasoning: {reasoning}")
                
                # Validate the selected regime type
                if selected_regime_type not in [r['regime_type'] for r in self.regime_types]:
                    print(f"⚠️ Invalid regime type selected by LLM: {selected_regime_type}")
                    print(f"🔄 Falling back to fallback logic...")
                    return self._fallback_regime_selection(direction_info, commercial_info, context)
                
                # Find the full regime details
                regime_details = None
                for regime in self.regime_types:
                    if regime['regime_type'] == selected_regime_type:
                        regime_details = regime
                        break
                
                if not regime_details:
                    # Fallback to IM4 if not found
                    print(f"⚠️ Regime details not found for {selected_regime_type}, using IM4")
                    regime_details = next(r for r in self.regime_types if r['regime_type'] == 'IM4')
                
                print(f"✅ Using regime: {regime_details['regime_type']} - {regime_details['description']}")
                
                return RegimeTypeResult(
                    regime_type=regime_details['regime_type'],
                    procedure_code=regime_details['procedure_code'],
                    description=regime_details['description'],
                    confidence=confidence,
                    reasoning=reasoning,
                    import_export_direction=direction_info['direction'],
                    commercial_determination='Commercial' if commercial_info['has_commercial_keywords'] else 'Personal',
                    contextual_factors=context
                )
            else:
                print(f"⚠️ No JSON found in LLM response")
                print(f"🔄 Falling back to fallback logic...")
            
        except Exception as e:
            print(f"❌ Error parsing LLM response: {e}")
            print(f"🔄 Falling back to fallback logic...")
        
        # Fallback if parsing fails
        return self._fallback_regime_selection(direction_info, commercial_info, context)
    
    def _fallback_regime_selection(self, direction_info: Dict, commercial_info: Dict, context: Dict) -> RegimeTypeResult:
        """Fallback logic if LLM fails - now using comprehensive product classification"""
        
        print("🔄 Using enhanced fallback logic with comprehensive product classification...")
        
        # Enhanced fallback logic with comprehensive commercial analysis
        if direction_info['direction'] == 'Import':
            try:
                value = float(context['invoice_value'].replace(',', '')) if context['invoice_value'] else 0
                print(f"💰 Invoice value: ${value}")
                print(f"📊 Value threshold: $5,000")
                
                # Use the new comprehensive classification
                framework_classification = commercial_info.get('overall_classification', 'Commercial')
                classification_confidence = commercial_info.get('classification_confidence', 'Medium')
                commercial_percentage = commercial_info.get('commercial_percentage', 0)
                household_percentage = commercial_info.get('household_percentage', 0)
                
                print(f"🏢 Framework classification: {framework_classification} ({classification_confidence})")
                print(f"📊 Commercial: {commercial_percentage:.1f}%, Household: {household_percentage:.1f}%")
                
                # Determine if item is commercial based on comprehensive framework
                is_commercial = framework_classification in ['Commercial', 'Mixed']
                
                if is_commercial:
                    # Commercial items always use commercial declaration regardless of value
                    if value > 5000:
                        regime_type = 'IM4'  # Standard Commercial Import
                        reasoning = f"Commercial item (framework classification: {framework_classification}) with high value (${value}) above $5,000 threshold - Standard Commercial Import (IM4)"
                    else:
                        regime_type = 'IM4'  # Commercial Import (low value but still commercial)
                        reasoning = f"Commercial item (framework classification: {framework_classification}) with low value (${value}) below $5,000 threshold - Commercial Import (IM4) required for commercial items"
                else:
                    # Household items follow value thresholds
                    if value > 5000:
                        regime_type = 'IM4'  # Personal items above threshold need commercial declaration
                        reasoning = f"Household item (framework classification: {framework_classification}) with high value (${value}) above $5,000 threshold - Commercial declaration (IM4) required"
                    else:
                        regime_type = 'IMS4'  # Personal items below threshold can use simplified
                        reasoning = f"Household item (framework classification: {framework_classification}) with low value (${value}) below $5,000 threshold - Simplified Declaration (IMS4) appropriate"
                        
            except (ValueError, AttributeError):
                # If value parsing fails, use framework classification
                framework_classification = commercial_info.get('overall_classification', 'Commercial')
                if framework_classification in ['Commercial', 'Mixed']:
                    regime_type = 'IM4'  # Default to commercial
                    reasoning = f"Value parsing failed, defaulting to commercial import based on framework classification: {framework_classification}"
                else:
                    regime_type = 'IMS4'  # Default to simplified
                    reasoning = f"Value parsing failed, defaulting to simplified declaration based on framework classification: {framework_classification}"
        else:
            regime_type = 'EX1'  # Permanent export
            reasoning = "Export direction detected"
        
        # Find regime details
        regime_details = next(r for r in self.regime_types if r['regime_type'] == regime_type)
        
        print(f"🎯 Enhanced fallback selected: {regime_type} - {reasoning}")
        
        return RegimeTypeResult(
            regime_type=regime_details['regime_type'],
            procedure_code=regime_details['procedure_code'],
            description=regime_details['description'],
            confidence='medium',
            reasoning=reasoning,
            import_export_direction=direction_info['direction'],
            commercial_determination='Commercial' if commercial_info.get('final_commercial_determination', False) else 'Personal',
            contextual_factors=context
        )
    
    def _call_openrouter_model(self, primary_model: str, prompt: str, backup_model: str, 
                              direction_info: Dict, commercial_info: Dict, context: Dict) -> RegimeTypeResult:
        """Call OpenRouter API with primary/backup model fallback"""
        
        # Try primary model first
        try:
            start_time = time.time()
            
            payload = {
                "model": primary_model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.1,
                "max_tokens": 1000
            }
            
            response = requests.post(
                OPENROUTER_URL,
                headers=OPENROUTER_HEADERS,
                json=payload,
                timeout=60
            )
            
            processing_time = time.time() - start_time
            
            if response.status_code == 200:
                response_data = response.json()
                content = response_data['choices'][0]['message']['content']
                
                # Parse LLM response
                result = self._parse_regime_selection_response(
                    content, direction_info, commercial_info, context
                )
                result.processing_time = processing_time
                result.model = primary_model
                
                print(f"✅ Primary model ({primary_model}) succeeded: {result.regime_type}")
                return result
            
            else:
                print(f"❌ Primary model failed with HTTP {response.status_code}")
                raise Exception(f"HTTP {response.status_code}")
        
        except Exception as e:
            print(f"⚠️ Primary model failed: {e}")
            print(f"🔄 Trying backup model: {backup_model}")
            
            # Try backup model
            try:
                start_time = time.time()
                
                payload = {
                    "model": backup_model,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.1,
                    "max_tokens": 1000
                }
                
                response = requests.post(
                    OPENROUTER_URL,
                    headers=OPENROUTER_HEADERS,
                    json=payload,
                    timeout=60
                )
                
                processing_time = time.time() - start_time
                
                if response.status_code == 200:
                    response_data = response.json()
                    content = response_data['choices'][0]['message']['content']
                    
                    # Parse LLM response
                    result = self._parse_regime_selection_response(
                        content, direction_info, commercial_info, context
                    )
                    result.processing_time = processing_time
                    result.model = backup_model
                    
                    print(f"✅ Backup model ({backup_model}) succeeded: {result.regime_type}")
                    return result
                
                else:
                    print(f"❌ Backup model failed with HTTP {response.status_code}")
                    raise Exception(f"Both models failed")
            
            except Exception as backup_error:
                print(f"❌ Backup model failed: {backup_error}")
                raise Exception(f"Both models failed: {e}, {backup_error}")
    
    def _save_regime_results(self, result_data: Dict[str, Any]) -> None:
        """Save regime results to JSON file"""
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Create output directory if it doesn't exist
        output_dir = Path("regime_results")
        output_dir.mkdir(exist_ok=True)
        
        output_file = output_dir / f"regime_{timestamp}.json"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Regime results saved to: {output_file}")
    
    def _classify_product_commercial_vs_household(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Comprehensive product classification using the commercial vs household framework
        """
        print("🔍 Analyzing product classification: Commercial vs Household...")
        
        form_fields = data.get('form_fields', {})
        tables = data.get('tables', [])
        
        # Extract product information from tables
        products = []
        for table in tables:
            headers = table.get('headers', [])
            rows = table.get('rows', [])
            
            # Look for product-related columns
            for header_row in headers:
                for i, header in enumerate(header_row):
                    header_lower = str(header).lower()
                    if any(keyword in header_lower for keyword in ['description', 'item', 'product', 'goods']):
                        # Found product description column
                        for row in rows:
                            if len(row) > i and row[i]:
                                product_info = self._analyze_single_product(
                                    row, header_row, i, form_fields
                                )
                                if product_info:
                                    products.append(product_info)
                                break
        
        # If no products found in tables, create from form fields
        if not products:
            commodity = form_fields.get('commodity', '')
            if commodity:
                products.append(self._analyze_single_product_from_commodity(
                    commodity, form_fields
                ))
        
        # Overall classification
        overall_classification = self._determine_overall_classification(products)
        
        result = {
            'products': products,
            'overall_classification': overall_classification,
            'total_products': len(products),
            'commercial_count': len([p for p in products if p['classification'] == 'Commercial']),
            'household_count': len([p for p in products if p['classification'] == 'Household'])
        }
        
        print(f"📊 Product Classification Results:")
        print(f"  Total products: {result['total_products']}")
        print(f"  Commercial: {result['commercial_count']}")
        print(f"  Household: {result['household_count']}")
        print(f"  Overall: {overall_classification['classification']} ({overall_classification['confidence']})")
        
        return result
    
    def _analyze_single_product(self, row: List, headers: List, product_col: int, form_fields: Dict) -> Dict[str, Any]:
        """Analyze a single product line item"""
        
        product_desc = str(row[product_col]) if len(row) > product_col else ""
        
        # Extract quantity, price, and other details
        quantity = 1
        unit_price = 0
        total_price = 0
        
        for i, header in enumerate(headers):
            header_lower = str(header).lower()
            if len(row) > i and row[i]:
                if 'quantity' in header_lower or 'qty' in header_lower:
                    try:
                        quantity = float(str(row[i]).replace(',', ''))
                    except:
                        quantity = 1
                elif 'unit' in header_lower and 'price' in header_lower:
                    try:
                        unit_price = float(str(row[i]).replace(',', '').replace('$', ''))
                    except:
                        unit_price = 0
                elif 'total' in header_lower and 'price' in header_lower:
                    try:
                        total_price = float(str(row[i]).replace(',', '').replace('$', ''))
                    except:
                        total_price = 0
        
        return self._classify_product_details(
            product_desc, quantity, unit_price, total_price, form_fields
        )
    
    def _analyze_single_product_from_commodity(self, commodity: str, form_fields: Dict) -> Dict[str, Any]:
        """Analyze product from commodity field when table data isn't available"""
        
        # Extract quantity from commodity field (e.g., "2 CTNS STC: SOLAR GENERATOR")
        quantity = 1
        if 'CTNS' in commodity or 'CTN' in commodity:
            try:
                qty_match = re.search(r'(\d+)\s+CTNS?', commodity)
                if qty_match:
                    quantity = int(qty_match.group(1))
            except:
                quantity = 1
        
        return self._classify_product_details(
            commodity, quantity, 0, 0, form_fields
        )
    
    def _classify_product_details(self, description: str, quantity: float, unit_price: float, 
                                total_price: float, form_fields: Dict) -> Dict[str, Any]:
        """Apply the classification framework to product details"""
        
        # 1. QUANTITY ANALYSIS (Primary Indicator)
        quantity_classification = self._analyze_quantity(description, quantity)
        
        # 2. PRODUCT NATURE (Primary Indicator)
        product_nature = self._analyze_product_nature(description)
        
        # 3. PRICING STRUCTURE (Secondary Indicator)
        pricing_analysis = self._analyze_pricing(unit_price, total_price, quantity)
        
        # 4. CONSIGNEE INFORMATION (Secondary Indicator)
        consignee_analysis = self._analyze_consignee(form_fields)
        
        # 5. PACKAGING & SHIPPING DETAILS (Supporting Indicator)
        shipping_analysis = self._analyze_shipping_details(form_fields)
        
        # 6. PRODUCT DESCRIPTIONS (Supporting Indicator)
        description_analysis = self._analyze_product_description(description)
        
        # Make final classification
        classification_result = self._make_classification_decision(
            quantity_classification, product_nature, pricing_analysis,
            consignee_analysis, shipping_analysis, description_analysis
        )
        
        return {
            'description': description,
            'quantity': quantity,
            'unit_price': unit_price,
            'total_price': total_price,
            'classification': classification_result['classification'],
            'confidence': classification_result['confidence'],
            'primary_factors': classification_result['primary_factors'],
            'supporting_factors': classification_result['supporting_factors'],
            'notes': classification_result['notes'],
            'analysis_breakdown': {
                'quantity': quantity_classification,
                'product_nature': product_nature,
                'pricing': pricing_analysis,
                'consignee': consignee_analysis,
                'shipping': shipping_analysis,
                'description': description_analysis
            }
        }
    
    def _analyze_quantity(self, description: str, quantity: float) -> Dict[str, Any]:
        """Analyze quantity for commercial vs household indicators"""
        
        # Define reasonable household quantities for different product types
        household_limits = {
            'electronics': 2,      # TVs, computers, phones
            'appliances': 3,       # Kitchen appliances, etc.
            'clothing': 20,        # Articles of clothing
            'food': 50,            # Food items
            'tools': 5,            # Hand tools, power tools
            'furniture': 3,        # Chairs, tables, etc.
            'generators': 2,       # Power generators
            'default': 10          # General default
        }
        
        # Determine product category
        product_category = 'default'
        desc_lower = description.lower()
        
        if any(word in desc_lower for word in ['generator', 'solar', 'battery', 'power']):
            product_category = 'generators'
        elif any(word in desc_lower for word in ['tv', 'computer', 'phone', 'laptop', 'tablet']):
            product_category = 'electronics'
        elif any(word in desc_lower for word in ['refrigerator', 'stove', 'washer', 'dryer', 'microwave']):
            product_category = 'appliances'
        elif any(word in desc_lower for word in ['shirt', 'pants', 'dress', 'shoes', 'jacket']):
            product_category = 'clothing'
        elif any(word in desc_lower for word in ['food', 'beverage', 'snack', 'drink']):
            product_category = 'food'
        elif any(word in desc_lower for word in ['tool', 'drill', 'saw', 'hammer', 'wrench']):
            product_category = 'tools'
        elif any(word in desc_lower for word in ['chair', 'table', 'bed', 'sofa', 'desk']):
            product_category = 'furniture'
        
        household_limit = household_limits.get(product_category, household_limits['default'])
        
        if quantity > household_limit:
            return {
                'indicator': 'Commercial',
                'reasoning': f'Quantity ({quantity}) exceeds typical household needs for {product_category}',
                'household_limit': household_limit,
                'weight': 'Primary'
            }
        else:
            return {
                'indicator': 'Household',
                'reasoning': f'Quantity ({quantity}) is reasonable for household use',
                'household_limit': household_limit,
                'weight': 'Primary'
            }
    
    def _analyze_product_nature(self, description: str) -> Dict[str, Any]:
        """Analyze if product is inherently commercial or household"""
        
        desc_lower = description.lower()
        
        # Inherently commercial indicators
        commercial_indicators = [
            'industrial', 'commercial', 'restaurant', 'professional', 'wholesale',
            'bulk', 'raw material', 'manufacturing', 'business', 'enterprise',
            'pos system', 'cash register', 'commercial kitchen', 'warehouse',
            'forklift', 'pallet', 'industrial grade', 'heavy machinery'
        ]
        
        # Inherently household indicators
        household_indicators = [
            'personal', 'home use', 'household', 'consumer', 'retail',
            'personal care', 'home décor', 'family', 'residential',
            'portable', 'compact', 'home size', 'consumer grade'
        ]
        
        commercial_score = sum(1 for indicator in commercial_indicators if indicator in desc_lower)
        household_score = sum(1 for indicator in household_indicators if indicator in desc_lower)
        
        if commercial_score > household_score:
            return {
                'indicator': 'Commercial',
                'reasoning': f'Product description contains {commercial_score} commercial indicators',
                'weight': 'Primary'
            }
        elif household_score > commercial_score:
            return {
                'indicator': 'Household',
                'reasoning': f'Product description contains {household_score} household indicators',
                'weight': 'Primary'
            }
        else:
            return {
                'indicator': 'Dual-Use',
                'reasoning': 'Product can serve both commercial and household purposes',
                'weight': 'Primary'
            }
    
    def _analyze_pricing(self, unit_price: float, total_price: float, quantity: float) -> Dict[str, Any]:
        """Analyze pricing structure for commercial vs household indicators"""
        
        if unit_price == 0 or total_price == 0:
            return {
                'indicator': 'Insufficient Data',
                'reasoning': 'Pricing information not available',
                'weight': 'Secondary'
            }
        
        # Calculate effective unit price
        effective_unit_price = total_price / quantity if quantity > 0 else unit_price
        
        # Wholesale vs retail pricing indicators
        # This is a simplified analysis - in practice, you'd need industry-specific benchmarks
        
        if effective_unit_price < 10:  # Very low unit price suggests wholesale
            return {
                'indicator': 'Commercial',
                'reasoning': f'Low unit price (${effective_unit_price:.2f}) suggests wholesale/commercial pricing',
                'weight': 'Secondary'
            }
        elif effective_unit_price > 1000:  # High unit price suggests retail
            return {
                'indicator': 'Household',
                'reasoning': f'High unit price (${effective_unit_price:.2f}) suggests retail/consumer pricing',
                'weight': 'Secondary'
            }
        else:
            return {
                'indicator': 'Unclear',
                'reasoning': f'Unit price (${effective_unit_price:.2f}) doesn\'t clearly indicate pricing structure',
                'weight': 'Secondary'
            }
    
    def _analyze_consignee(self, form_fields: Dict) -> Dict[str, Any]:
        """Analyze consignee information for commercial vs household indicators"""
        
        consignee_name = form_fields.get('consignee_name', '').lower()
        consignee_address = form_fields.get('consignee_address', '').lower()
        
        # Commercial indicators
        commercial_indicators = [
            'ltd', 'limited', 'corp', 'corporation', 'inc', 'incorporated',
            'company', 'co', 'distributors', 'distributor', 'trading',
            'imports', 'exports', 'wholesale', 'retail', 'enterprise',
            'enterprises', 'group', 'holdings', 'supplies', 'suppliers',
            'services', 'solutions', 'systems', 'international', 'global',
            'restaurant', 'hotel', 'office', 'warehouse', 'factory'
        ]
        
        # Check for commercial indicators
        commercial_found = []
        for indicator in commercial_indicators:
            if indicator in consignee_name or indicator in consignee_address:
                commercial_found.append(indicator)
        
        if commercial_found:
            return {
                'indicator': 'Commercial',
                'reasoning': f'Consignee shows commercial indicators: {commercial_found}',
                'weight': 'Secondary'
            }
        else:
            return {
                'indicator': 'Household',
                'reasoning': 'Consignee appears to be individual/residential',
                'weight': 'Secondary'
            }
    
    def _analyze_shipping_details(self, form_fields: Dict) -> Dict[str, Any]:
        """Analyze shipping details for commercial vs household indicators"""
        
        container = form_fields.get('container', '')
        weight = form_fields.get('weight', '')
        package_type = form_fields.get('package_type', '')
        
        # Commercial shipping indicators
        commercial_indicators = []
        
        if container:
            commercial_indicators.append('Containerized shipment')
        
        if weight and 'KGM' in weight:
            try:
                weight_value = float(weight.replace(' KGM', ''))
                if weight_value > 100:  # Heavy shipments often commercial
                    commercial_indicators.append(f'Heavy shipment ({weight_value} KGM)')
            except:
                pass
        
        if package_type in ['PAL', 'CRT', 'BOX']:
            commercial_indicators.append(f'Commercial packaging ({package_type})')
        
        if commercial_indicators:
            return {
                'indicator': 'Commercial',
                'reasoning': f'Shipping details suggest commercial: {", ".join(commercial_indicators)}',
                'weight': 'Supporting'
            }
        else:
            return {
                'indicator': 'Household',
                'reasoning': 'Shipping details suggest household/consumer shipment',
                'weight': 'Supporting'
            }
    
    def _analyze_product_description(self, description: str) -> Dict[str, Any]:
        """Analyze product description for commercial vs household indicators"""
        
        desc_lower = description.lower()
        
        # Look for specific product characteristics
        indicators = []
        
        # Size/scale indicators
        if any(word in desc_lower for word in ['portable', 'compact', 'mini', 'small']):
            indicators.append('Portable/compact design')
        
        if any(word in desc_lower for word in ['industrial', 'heavy duty', 'commercial grade']):
            indicators.append('Industrial/commercial specifications')
        
        if any(word in desc_lower for word in ['home', 'household', 'personal', 'family']):
            indicators.append('Home/personal use specified')
        
        if any(word in desc_lower for word in ['professional', 'business', 'enterprise']):
            indicators.append('Professional/business use specified')
        
        if indicators:
            # Determine overall direction
            household_count = sum(1 for ind in indicators if 'home' in ind.lower() or 'personal' in ind.lower())
            commercial_count = sum(1 for ind in indicators if 'industrial' in ind.lower() or 'professional' in ind.lower())
            
            if household_count > commercial_count:
                return {
                    'indicator': 'Household',
                    'reasoning': f'Product description emphasizes household use: {", ".join(indicators)}',
                    'weight': 'Supporting'
                }
            elif commercial_count > household_count:
                return {
                    'indicator': 'Commercial',
                    'reasoning': f'Product description emphasizes commercial use: {", ".join(indicators)}',
                    'weight': 'Supporting'
                }
        
        return {
            'indicator': 'Neutral',
            'reasoning': 'Product description doesn\'t clearly indicate use case',
            'weight': 'Supporting'
        }
    
    def _make_classification_decision(self, quantity_analysis: Dict, product_nature: Dict, 
                                    pricing_analysis: Dict, consignee_analysis: Dict,
                                    shipping_analysis: Dict, description_analysis: Dict) -> Dict[str, Any]:
        """Make final classification decision based on all analyses"""
        
        # Score the analyses
        scores = {'Commercial': 0, 'Household': 0}
        factors = {'Commercial': [], 'Household': []}
        
        # Primary factors (weight = 3)
        for analysis in [quantity_analysis, product_nature]:
            if analysis['weight'] == 'Primary':
                # Handle Dual-Use by splitting the score
                if analysis['indicator'] == 'Dual-Use':
                    scores['Commercial'] += 1.5
                    scores['Household'] += 1.5
                    factors['Commercial'].append(f"{analysis['reasoning']} (Primary - Dual-Use)")
                    factors['Household'].append(f"{analysis['reasoning']} (Primary - Dual-Use)")
                else:
                    scores[analysis['indicator']] += 3
                    factors[analysis['indicator']].append(f"{analysis['reasoning']} (Primary)")
        
        # Secondary factors (weight = 2)
        for analysis in [pricing_analysis, consignee_analysis]:
            if analysis['indicator'] in ['Commercial', 'Household']:
                scores[analysis['indicator']] += 2
                factors[analysis['indicator']].append(f"{analysis['reasoning']} (Secondary)")
            elif analysis['indicator'] == 'Dual-Use':
                scores['Commercial'] += 1
                scores['Household'] += 1
                factors['Commercial'].append(f"{analysis['reasoning']} (Secondary - Dual-Use)")
                factors['Household'].append(f"{analysis['reasoning']} (Secondary - Dual-Use)")
        
        # Supporting factors (weight = 1)
        for analysis in [shipping_analysis, description_analysis]:
            if analysis['indicator'] in ['Commercial', 'Household']:
                scores[analysis['indicator']] += 1
                factors[analysis['indicator']].append(f"{analysis['reasoning']} (Supporting)")
            elif analysis['indicator'] == 'Dual-Use':
                scores['Commercial'] += 0.5
                scores['Household'] += 0.5
                factors['Commercial'].append(f"{analysis['reasoning']} (Supporting - Dual-Use)")
                factors['Household'].append(f"{analysis['reasoning']} (Supporting - Dual-Use)")
        
        # Make decision
        if scores['Commercial'] > scores['Household']:
            classification = 'Commercial'
            confidence = 'High' if scores['Commercial'] - scores['Household'] >= 3 else 'Medium'
        elif scores['Household'] > scores['Commercial']:
            classification = 'Household'
            confidence = 'High' if scores['Household'] - scores['Commercial'] >= 3 else 'Medium'
        else:
            # Tie - default to Commercial as per framework
            classification = 'Commercial'
            confidence = 'Low'
            factors['Commercial'].append('Default classification due to tie (uncertainty)')
        
        return {
            'classification': classification,
            'confidence': confidence,
            'primary_factors': factors[classification],
            'supporting_factors': factors.get('Household' if classification == 'Commercial' else 'Commercial', []),
            'notes': f'Commercial score: {scores["Commercial"]}, Household score: {scores["Household"]}',
            'scores': scores
        }
    
    def _determine_overall_classification(self, products: List[Dict]) -> Dict[str, Any]:
        """Determine overall classification for the entire shipment"""
        
        if not products:
            return {
                'classification': 'Commercial',
                'confidence': 'Low',
                'reasoning': 'No product information available - defaulting to Commercial'
            }
        
        # Count classifications
        commercial_count = len([p for p in products if p['classification'] == 'Commercial'])
        household_count = len([p for p in products if p['classification'] == 'Household'])
        total_count = len(products)
        
        # Determine overall classification
        if commercial_count > household_count:
            classification = 'Commercial'
            confidence = 'High' if commercial_count / total_count >= 0.8 else 'Medium'
        elif household_count > commercial_count:
            classification = 'Household'
            confidence = 'High' if household_count / total_count >= 0.8 else 'Medium'
        else:
            # Mixed shipment
            classification = 'Mixed'
            confidence = 'Medium'
        
        return {
            'classification': classification,
            'confidence': confidence,
            'reasoning': f'{commercial_count} commercial, {household_count} household products',
            'commercial_percentage': (commercial_count / total_count) * 100 if total_count > 0 else 0,
            'household_percentage': (household_count / total_count) * 100 if total_count > 0 else 0
        }


def main():
    """Test the regime type processor with real data"""
    print("=== eSAD REGIME TYPE PROCESSOR TEST ===\n")
    
    # Load the most recent extracted data file
    extracted_data_dir = Path("extracted_data")
    if extracted_data_dir.exists():
        json_files = list(extracted_data_dir.glob("*.json"))
        if json_files:
            # Get the most recent file
            latest_file = max(json_files, key=lambda x: x.stat().st_mtime)
            print(f"📄 Loading data from: {latest_file}")
            
            with open(latest_file, 'r', encoding='utf-8') as f:
                test_data = json.load(f)
        else:
            print("❌ No JSON files found in extracted_data directory")
            return
    else:
        print("❌ extracted_data directory not found")
        return
    
    # Initialize processor
    processor = RegimeTypeProcessor()
    
    # Process with primary/backup models
    result_data = processor.process_with_primary_backup(test_data)
    
    # Display results
    if 'error' in result_data:
        print(f"\n❌ REGIME TYPE DETERMINATION FAILED:")
        print(f"   Error: {result_data['error']}")
    else:
        result = result_data['result']
        print(f"\n🎯 REGIME TYPE DETERMINATION RESULTS:")
        print(f"   Selected Regime: {result['regime_type']}")
        print(f"   Procedure Code: {result['procedure_code']}")
        print(f"   Description: {result['description']}")
        print(f"   Direction: {result['import_export_direction']}")
        print(f"   Commercial: {result['commercial_determination']}")
        print(f"   Confidence: {result['confidence']}")
        print(f"   Model Used: {result['model_used']}")
        print(f"   Processing Time: {result['processing_time']:.2f}s")
        print(f"   Reasoning: {result['reasoning']}")
    
    print(f"\n✅ Regime type determination completed!")

if __name__ == "__main__":
    main() 