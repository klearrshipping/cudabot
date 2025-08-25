#!/usr/bin/env python3
"""
ESAD Primary Processing - Step 1 of the workflow (IMPROVED VERSION)
Uses eSAD.json prompts with LLM to process extracted JSON files and generate esad_fields.json
"""

import json
import os
import requests
import re
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path

# Add parent directory to path to import config
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Try to import config, fallback to environment variables
try:
    from config import OPENROUTER_API_KEY, OPENROUTER_URL, OPENROUTER_HEADERS, OPENROUTER_GENERAL_MODELS
except ImportError:
    OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
    OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
    OPENROUTER_HEADERS = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    # Fallback for models
    OPENROUTER_GENERAL_MODELS = {
        "mistral_small": "mistralai/mistral-small-3.2-24b-instruct",
        "gpt_5_nano": "openai/gpt-5-nano"
    }

# Import Supabase client for database operations
try:
    from config import SUPABASE_URL, SUPABASE_ANON_KEY
    from supabase import create_client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    print("⚠️ Supabase integration not available")

class ESADPrimaryProcessor:
    """
    ESAD Primary Processor - Step 1 of the workflow (IMPROVED VERSION)
    Uses eSAD.json prompts with LLM to process extracted JSON files and generate esad_fields.json
    """
    
    def __init__(self, model: str = "mistral_small"):
        self.model = model
        self.api_key = OPENROUTER_API_KEY
        self.supabase = None
        
        # Load eSAD structure with prompts
        self.esad_structure = self._load_esad_structure()
        
        if SUPABASE_AVAILABLE:
            try:
                self.supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
                print(f"✅ Connected to Supabase for ESAD processing")
            except Exception as e:
                print(f"⚠️ Failed to connect to Supabase: {e}")
                self.supabase = None
    
    def _load_esad_structure(self) -> Dict[str, Any]:
        """Load the eSAD structure from eSAD.json"""
        try:
            esad_file = Path(__file__).parent.parent / "secondary_processing" / "eSAD.json"
            with open(esad_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(f"✅ Loaded eSAD structure with {len(data.get('esad_mandatory_fields', {}).get('fields', []))} fields")
            return data
        except Exception as e:
            print(f"⚠️ Error loading eSAD structure: {e}")
            return {}
    
    def process_order(self, order_id: int, bol_extraction: Dict[str, Any], invoice_extraction: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an order using eSAD.json prompts with LLM to generate esad_fields.json
        
        Args:
            order_id: Order ID
            bol_extraction: Bill of lading extraction JSON
            invoice_extraction: Invoice extraction JSON
            
        Returns:
            dict: Processing results and populated ESAD fields
        """
        print(f"🔄 Starting ESAD primary processing for order {order_id}")
        
        try:
            # Step 1: Use eSAD.json prompts with LLM to process the extracted JSON files
            esad_fields = self._process_with_llm(bol_extraction, invoice_extraction, order_id)
            
            # Step 2: Generate esad_fields.json file
            json_file_path = self._generate_esad_fields_json(order_id, esad_fields)
            
            # Step 3: Optionally save to database if available
            fields_saved = 0
            if self.supabase:
                fields_saved = self._save_to_esad_fields_table(order_id, esad_fields)
            
            # Step 4: Return results
            result = {
                "order_id": order_id,
                "processing_status": "success",
                "fields_populated": len(esad_fields),
                "fields_saved_to_db": fields_saved,
                "esad_fields_json_path": str(json_file_path),
                "esad_fields": esad_fields,
                "processing_timestamp": datetime.now().isoformat(),
                "processor": "esad_primary_processor_llm_manifest_enhanced"
            }
            
            print(f"✅ ESAD primary processing completed for order {order_id}")
            print(f"   • Fields populated: {len(esad_fields)}")
            print(f"   • Fields saved to DB: {fields_saved}")
            print(f"   • ESAD fields JSON generated: {json_file_path}")
            
            return result
            
        except Exception as e:
            print(f"❌ Error in ESAD primary processing: {e}")
            return {
                "order_id": order_id,
                "processing_status": "failed",
                "error": str(e),
                "processing_timestamp": datetime.now().isoformat(),
                "processor": "esad_primary_processor_llm_manifest_enhanced"
            }
    
    def _process_with_llm(self, bol_extraction: Dict[str, Any], invoice_extraction: Dict[str, Any], order_id: int) -> Dict[str, Any]:
        """
        Use eSAD.json prompts with LLM to process the extracted JSON files
        
        Args:
            bol_extraction: Bill of lading extraction data
            invoice_extraction: Invoice extraction data
            
        Returns:
            dict: Populated ESAD fields based on LLM processing (ALL fields included)
        """
        esad_fields = {}
        
        # Get fields from eSAD.json
        fields = self.esad_structure.get('esad_mandatory_fields', {}).get('fields', [])
        
        print(f"🤖 Processing {len(fields)} ESAD fields using LLM...")
        
        for field_def in fields:
            field_name = field_def.get("field_name")
            extraction_prompt = field_def.get("extraction_prompt")
            box_field = field_def.get("box_field")
            
            if not field_name or not extraction_prompt:
                continue
            
            # Skip Regime Type - will be handled by esad_regime script automatically
            if field_name == "Regime Type":
                print(f"  ⏭️ {field_name}: Skipping LLM - will be handled by esad_regime script")
                esad_fields[field_name] = {
                    "value": None,  # Will be populated later
                    "box_field": box_field,
                    "extraction_prompt": extraction_prompt,
                    "source": "pending_regime_lookup"
                }
                continue
            
            # Skip Commercial reference number - will be populated with Order ID automatically
            if field_name == "Commercial reference number":
                print(f"  ⏭️ {field_name}: Skipping LLM - will be populated with Order ID")
                esad_fields[field_name] = {
                    "value": f"ORD-{datetime.now().strftime('%Y%m%d')}-{order_id:03d}",  # Generate Order ID format
                    "box_field": box_field,
                    "extraction_prompt": extraction_prompt,
                    "source": "order_id_generated"
                }
                continue
            
            # Skip automated fields - will be handled by specific scripts or default values
            if field_def.get("processing_method") == "automated_default_value":
                default_value = field_def.get("default_value", "N/A")
                print(f"  ⏭️ {field_name}: Skipping LLM - will be set to default value '{default_value}'")
                esad_fields[field_name] = {
                    "value": default_value,
                    "box_field": box_field,
                    "extraction_prompt": extraction_prompt,
                    "source": "default_value"
                }
                continue
            
            # Skip TRN fields - will be handled by esad_trn script automatically
            if field_name in ["Importer/Consignee TRN No.", "Declarant/Representative TRN No."]:
                print(f"  ⏭️ {field_name}: Skipping LLM - will be handled by esad_trn script")
                esad_fields[field_name] = {
                    "value": None,  # Will be populated later
                    "box_field": box_field,
                    "extraction_prompt": extraction_prompt,
                    "source": "pending_trn_lookup"
                }
                continue
            
            # Use LLM to process the extraction prompt
            field_value = self._extract_field_with_llm(
                field_name, 
                extraction_prompt, 
                bol_extraction, 
                invoice_extraction
            )
            
            # Always add the field, even if value is None (null)
            esad_fields[field_name] = {
                "value": field_value,
                "box_field": box_field,
                "extraction_prompt": extraction_prompt,
                "source": "llm_processing" if field_value is not None else "llm_processing_null"
            }
            
            if field_value is not None:
                print(f"  ✅ {field_name}: {field_value}")
            else:
                print(f"  ⚠️ {field_name}: null (data not available)")
        
        print(f"📊 Field processing complete: {len([f for f in esad_fields.values() if f['value'] is not None])} populated, {len([f for f in esad_fields.values() if f['value'] is None])} null")
        
        # Step 2: Check for manifest-related null fields and fetch data if needed
        print(f"🔍 Checking for manifest-related null fields...")
        manifest_fields_updated = self._fetch_manifest_data_if_needed(esad_fields, bol_extraction, order_id)
        
        if manifest_fields_updated:
            print(f"📊 After manifest data fetch: {len([f for f in esad_fields.values() if f['value'] is not None])} populated, {len([f for f in esad_fields.values() if f['value'] is None])} null")
        
        # Step 3: Handle Regime Type field automatically
        print(f"🔍 Processing Regime Type field...")
        regime_updated = self._fetch_regime_data_if_needed(esad_fields, bol_extraction, invoice_extraction, order_id)
        
        if regime_updated:
            print(f"📊 After regime data fetch: {len([f for f in esad_fields.values() if f['value'] is not None])} populated, {len([f for f in esad_fields.values() if f['value'] is None])} null")
        
        # Step 4: Handle TRN fields automatically (only if Jamaican entities)
        print(f"🔍 Processing TRN fields...")
        if self._is_trn_required(bol_extraction):
            print(f"  🇯🇲 Jamaican entity detected - TRN required")
            trn_updated = self._fetch_trn_data_if_needed(esad_fields, bol_extraction, invoice_extraction, order_id)
            
            if trn_updated:
                print(f"📊 After TRN data fetch: {len([f for f in esad_fields.values() if f['value'] is not None])} populated, {len([f for f in esad_fields.values() if f['value'] is None])} null")
        else:
            print(f"  🌍 Non-Jamaican entity detected - TRN not required")
            # Mark TRN fields as not required
            for field_name in ["Importer/Consignee TRN No.", "Declarant/Representative TRN No."]:
                if field_name in esad_fields:
                    esad_fields[field_name]["source"] = "not_required"
                    esad_fields[field_name]["value"] = None
                    print(f"  ⏭️ {field_name}: Marked as not required (non-Jamaican entity)")
        
        return esad_fields
    
    def _extract_field_with_llm(self, field_name: str, prompt: str, bol_data: Dict[str, Any], invoice_data: Dict[str, Any]) -> Any:
        """
        Extract a field value using LLM with the eSAD.json prompt and extracted data
        
        Args:
            field_name: Name of the ESAD field
            prompt: Extraction prompt from eSAD.json
            bol_data: Bill of lading extraction data
            invoice_data: Invoice extraction data
            
        Returns:
            Any: Extracted field value or None if not found
        """
        try:
            # Get field-specific instructions
            format_instructions = self._get_format_instructions(field_name)
            
            # Prepare the context for the LLM
            context = f"""
You are processing ESAD (Electronic Single Administrative Document) fields for customs declaration.

FIELD: {field_name}
PROMPT: {prompt}

CRITICAL INSTRUCTIONS:
{format_instructions}

- Return ONLY the extracted value, NO explanations, NO quotes, NO additional text
- If the information is not available, return exactly: null
- Do not include any reasoning or explanations in your response
- Do not include prefixes like "EXTRACTED VALUE:" or similar

AVAILABLE DATA:

BILL OF LADING DATA:
{json.dumps(bol_data, indent=2)}

INVOICE DATA:
{json.dumps(invoice_data, indent=2)}

RESPONSE FORMAT: Return only the clean value as specified above."""
            
            # Call the LLM
            response = self._call_llm(context)
            
            if response:
                # Clean and validate the response
                cleaned_value = self._clean_response(response, field_name)
                return cleaned_value
            else:
                return None
                
        except Exception as e:
            print(f"  ❌ Error calling LLM for {field_name}: {e}")
            return None
    
    def _get_format_instructions(self, field_name: str) -> str:
        """
        Get specific format instructions for each field type
        
        Args:
            field_name: Name of the ESAD field
            
        Returns:
            str: Specific formatting instructions for the field
        """
        format_rules = {
            # Address fields
            "Exporter/Consignor Address": "Return complete address as single line, no quotes",
            "Importer/Consignee Address": "Return complete address as single line, no quotes",
            
            # Name fields  
            "Exporter/Consignor Name/Company": "Return company/person name only, no quotes",
            "Importer/Consignee Name/Company": "Return company/person name only, no quotes",
            
            # Country fields
            "Country Last Consignment": "Return country name only (e.g., 'United States')",
            "Trading Country": "Return country name only (e.g., 'United States')",
            "Country of export": "Return country name only (e.g., 'United States')",
            "Country Origin Code": "Return 2-letter ISO country code only (e.g., 'US', 'JM')",
            
            # Numeric fields
            "Total packages": "Return number only (e.g., '2')",
            "No. of packages": "Return number only (e.g., '2')", 
            "Amount": "Return numeric value only (e.g., '1496.93')",
            "Invoice value": "Return numeric value only (e.g., '1399.0')",
            "Freight charges": "Return numeric value only (e.g., '211.71')",
            "Insurance charges": "Return numeric value only (e.g., '0' if not found)",
            "Gross Weight (kg)": "Return numeric value only (e.g., '78.93')",
            "Net Weight (kg)": "Return numeric value only or 'null' if not available",
            "Statistical Units": "Return numeric quantity only (e.g., '1')",
            
            # Currency fields
            "Currency code": "Return primary currency code only (e.g., 'USD')",
            
            # Transport fields
            "Mode of transport at the border": "Return mode only: 'SEA', 'AIR', 'ROAD', or 'RAIL'",
            "Identity and nationality of active means of transport at arrival": "Return 'VesselName/CountryCode' format (e.g., 'SEABOARD GEMINI/LR')",
            
            # Package fields
            "Kind of packages": "Return package code only (e.g., 'BX', 'CT', 'PK')",
            "Marks and numbers of packages": "Return container/package numbers separated by commas",
            
            # Reference fields
            "Commercial reference number": "Return reference number only",
            "Manifest": "Return manifest number only",
            "Transport document/Previous Document": "Return document numbers separated by commas",
            
            # Code fields
            "Office code": "Return office code only or infer from port (e.g., 'JMKCT')",
            "Commodity code": "Return HS code only or 'null' if not determinable",
            "Procedure": "Return procedure code only or 'null' if not determinable",
            "V.M.": "Return valuation method number only (e.g., '1')",
            
            # Description fields
            "Commercial description": "Return product description only, no quotes",
            
            # Location fields
            "Place of Loading/Unloading": "Return port/location name only",
            "Location of goods": "Return storage location/berth only",
            "Applicable place": "Return port/place name only",
            
            # Terms fields
            "Delivery terms": "Return INCOTERM only (e.g., 'CIF', 'FOB') or infer from freight terms",
            "Nature of Transaction": "Return transaction type only (e.g., 'sale', 'gift')",
            
            # Other fields
            "Principal": "Return responsible party name and address",
            "Regime Type": "Return regime code only or 'null' if not determinable",
            "Importer/Consignee TRN No.": "Return TRN number only or 'null' if not available",
            "Declarant/Representative TRN No.": "Return TRN number only or 'null' if not available"
        }
        
        return format_rules.get(field_name, "Return the extracted value only, no explanations")
    
    def _clean_response(self, response: str, field_name: str) -> Any:
        """
        Clean and validate the LLM response based on field type
        
        Args:
            response: Raw LLM response
            field_name: Name of the ESAD field
            
        Returns:
            Any: Cleaned field value or None
        """
        if not response or not response.strip():
            return None
            
        # Remove common unwanted prefixes and suffixes
        cleaned = response.strip()
        
        # Remove quotes if present
        if cleaned.startswith('"') and cleaned.endswith('"'):
            cleaned = cleaned[1:-1]
        if cleaned.startswith("'") and cleaned.endswith("'"):
            cleaned = cleaned[1:-1]
            
        # Remove common prefixes
        prefixes_to_remove = [
            "EXTRACTED VALUE:",
            "Extracted value:",
            "Value:",
            "Result:",
            "Answer:",
            "The extracted value is:",
            "Based on the provided data,",
            "From the provided data,"
        ]
        
        for prefix in prefixes_to_remove:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
                break
        
        # Handle null values
        if cleaned.lower() in ['null', 'none', 'n/a', 'not available', 'not found']:
            return None
            
        # Field-specific cleaning
        if field_name in ["Currency code"]:
            # Extract primary currency code
            currencies = re.findall(r'\b[A-Z]{3}\b', cleaned)
            if currencies:
                return currencies[0]  # Return first/primary currency
                
        elif field_name in ["Country Origin Code"]:
            # Extract 2-letter country code
            country_codes = re.findall(r'\b[A-Z]{2}\b', cleaned)
            if country_codes:
                return country_codes[0]
                
        elif field_name in ["Mode of transport at the border"]:
            # Standardize transport modes
            cleaned_upper = cleaned.upper()
            if any(word in cleaned_upper for word in ['SEA', 'SHIP', 'VESSEL', 'MARITIME']):
                return "SEA"
            elif any(word in cleaned_upper for word in ['AIR', 'FLIGHT', 'PLANE']):
                return "AIR"
            elif any(word in cleaned_upper for word in ['ROAD', 'TRUCK', 'VEHICLE']):
                return "ROAD"
            elif any(word in cleaned_upper for word in ['RAIL', 'TRAIN']):
                return "RAIL"
                
        elif field_name in ["Identity and nationality of active means of transport at arrival"]:
            # Extract vessel name and country code dynamically
            # Look for vessel name pattern and country/flag info
            vessel_pattern = r'([A-Z\s]+?)(?:/|\s+)([A-Z]{2,3})'
            match = re.search(vessel_pattern, cleaned.upper())
            if match:
                vessel_name = match.group(1).strip()
                country_code = match.group(2).strip()
                return f"{vessel_name}/{country_code}"
            
            # Alternative: look for country name and convert to code
            country_mappings = {
                'LIBERIA': 'LR', 'PANAMA': 'PA', 'MARSHALL ISLANDS': 'MH',
                'BAHAMAS': 'BS', 'MALTA': 'MT', 'CYPRUS': 'CY',
                'UNITED STATES': 'US', 'UNITED KINGDOM': 'GB',
                'SINGAPORE': 'SG', 'HONG KONG': 'HK', 'GREECE': 'GR',
                'NORWAY': 'NO', 'DENMARK': 'DK', 'NETHERLANDS': 'NL',
                'GERMANY': 'DE', 'ITALY': 'IT', 'FRANCE': 'FR',
                'JAPAN': 'JP', 'SOUTH KOREA': 'KR', 'CHINA': 'CN',
                'INDIA': 'IN', 'BRAZIL': 'BR', 'RUSSIA': 'RU',
                'TURKEY': 'TR', 'ISRAEL': 'IL', 'SAUDI ARABIA': 'SA'
            }
            
            # Extract vessel name (usually comes first)
            parts = cleaned.split()
            if len(parts) >= 2:
                # Try to find country name in the text
                for country, code in country_mappings.items():
                    if country in cleaned.upper():
                        # Extract vessel name (everything before country reference)
                        vessel_parts = []
                        for part in parts:
                            if part.upper() not in country.split():
                                vessel_parts.append(part)
                            else:
                                break
                        if vessel_parts:
                            vessel_name = ' '.join(vessel_parts[:3])  # Limit to reasonable vessel name length
                            return f"{vessel_name.upper()}/{code}"
                
        elif field_name in ["Kind of packages"]:
            # Extract package type codes
            if "BX" in cleaned.upper():
                return "BX"
            elif "BOX" in cleaned.upper():
                return "BX"
            elif "CARTON" in cleaned.upper() or "CTN" in cleaned.upper():
                return "CT"
                
        elif "Weight" in field_name or "Amount" in field_name or "value" in field_name or field_name in ["Total packages", "No. of packages", "Statistical Units"]:
            # Extract numeric values
            numbers = re.findall(r'\d+\.?\d*', cleaned)
            if numbers:
                try:
                    return str(float(numbers[0])) if '.' in numbers[0] else numbers[0]
                except ValueError:
                    pass
                    
        elif field_name == "V.M.":
            # Extract valuation method number
            if "method 1" in cleaned.lower() or cleaned.strip() == "1":
                return "1"
            numbers = re.findall(r'\d+', cleaned)
            if numbers:
                return numbers[0]
        
        # Remove excessive whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        return cleaned if cleaned else None
    
    def _fetch_manifest_data_if_needed(self, esad_fields: Dict[str, Any], bol_data: Dict[str, Any], order_id: int) -> bool:
        """
        Check if Office code or Manifest fields are null and fetch manifest data if needed
        
        Args:
            esad_fields: Current ESAD fields
            bol_data: Bill of lading data for BOL number extraction
            
        Returns:
            bool: True if manifest fields were updated, False otherwise
        """
        # Check if manifest-related fields are null
        office_code_null = esad_fields.get("Office code", {}).get("value") is None
        manifest_null = esad_fields.get("Manifest", {}).get("value") is None
        
        if not office_code_null and not manifest_null:
            print("  ✅ Office code and Manifest fields are already populated")
            return False
        
        print("  🔍 Office code or Manifest field is null - fetching manifest data...")
        
        # Extract BOL number from BOL data
        bol_number = self._extract_bol_number(bol_data)
        if not bol_number:
            print("  ❌ Could not extract BOL number for manifest lookup")
            return False
        
        print(f"  🎯 Using BOL number: {bol_number}")
        
        # Fetch manifest data using esad_manifest
        manifest_data = self._call_esad_manifest(bol_number)
        if not manifest_data:
            print("  ❌ Failed to fetch manifest data")
            return False
        
        # Update null fields with manifest data
        fields_updated = 0
        
        if office_code_null and manifest_data.office:
            esad_fields["Office code"]["value"] = manifest_data.office
            esad_fields["Office code"]["source"] = "manifest_lookup"
            print(f"  ✨ Updated Office code: {manifest_data.office}")
            fields_updated += 1
        
        if manifest_null and manifest_data.reference_id:
            esad_fields["Manifest"]["value"] = manifest_data.reference_id
            esad_fields["Manifest"]["source"] = "manifest_lookup"
            print(f"  ✨ Updated Manifest: {manifest_data.reference_id}")
            fields_updated += 1
        
        if fields_updated > 0:
            print(f"  ✅ Successfully updated {fields_updated} manifest-related fields")
            return True
        
        return False
    
    def _extract_bol_number(self, bol_data: Dict[str, Any]) -> Optional[str]:
        """Extract BOL number from BOL data"""
        # Try different possible field names for BOL
        bol_candidates = [
            bol_data.get("bill_of_lading", ""),
            bol_data.get("transport_document", ""),
            bol_data.get("bol", ""),
            bol_data.get("bl_number", ""),
            bol_data.get("document_number", "")
        ]
        
        # Return the first non-empty BOL number
        for bol in bol_candidates:
            if bol and str(bol).strip():
                return str(bol).strip()
        
        return None
    
    def _call_esad_manifest(self, bol_number: str) -> Optional[Dict[str, Any]]:
        """
        Call the esad_manifest script to fetch manifest data
        
        Args:
            bol_number: BOL number to look up
            
        Returns:
            dict: Manifest data or None if failed
        """
        try:
            # Import the manifest tracker
            import sys
            import os
            sys.path.append(os.path.join(os.path.dirname(__file__), "..", "secondary_processing"))
            
            from esad_manifest import ManifestTracker
            
            print(f"  🔄 Fetching manifest data for BOL: {bol_number}")
            
            # Initialize and run the manifest tracker
            tracker = ManifestTracker()
            result = tracker.track_bol(bol_number)
            
            if result.success and result.entries:
                # Get the most recent entry (first in the list)
                latest_entry = result.entries[0]
                
                manifest_data = {
                    "office": latest_entry.office,
                    "reference_id": latest_entry.reference_id,
                    "date": latest_entry.date,
                    "status": latest_entry.status
                }
                
                print(f"  📋 Manifest data extracted:")
                print(f"     Office: {manifest_data['office']}")
                print(f"     Reference ID: {manifest_data['reference_id']}")
                print(f"     Date: {manifest_data['date']}")
                print(f"     Status: {manifest_data['status']}")
                
                return manifest_data
            else:
                print(f"  ❌ Manifest lookup failed: {result.error_message}")
                return None
                
        except Exception as e:
            print(f"  ❌ Error calling esad_manifest: {e}")
            return None
    
    def _fetch_regime_data_if_needed(self, esad_fields: Dict[str, Any], bol_data: Dict[str, Any], invoice_data: Dict[str, Any], order_id: int) -> bool:
        """
        Check if Regime Type field needs to be populated and fetch regime data if needed
        
        Args:
            esad_fields: Current ESAD fields
            bol_data: Bill of lading data
            invoice_data: Invoice data
            
        Returns:
            bool: True if regime field was updated, False otherwise
        """
        # Check if Regime Type field needs processing
        regime_field = esad_fields.get("Regime Type", {})
        regime_source = regime_field.get("source")
        
        if regime_source != "pending_regime_lookup":
            print("  ✅ Regime Type field is already populated or not pending")
            return False
        
        print("  🔍 Regime Type field needs processing - fetching regime data...")
        
        # Fetch regime data using esad_regime
        regime_data = self._call_esad_regime(bol_data, invoice_data)
        if not regime_data:
            print("  ❌ Failed to fetch regime data")
            return False
        
        # Update Regime Type field with regime data
        if regime_data.regime_type:
            esad_fields["Regime Type"]["value"] = regime_data.regime_type
            esad_fields["Regime Type"]["source"] = "regime_lookup"
            print(f"  ✨ Updated Regime Type: {regime_data.regime_type}")
            return True
        
        return False
    
    def _call_esad_regime(self, bol_data: Dict[str, Any], invoice_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Call the esad_regime script to fetch regime data
        
        Args:
            bol_data: Bill of lading data
            invoice_data: Invoice data
            
        Returns:
            dict: Regime data or None if failed
        """
        try:
            # Import the regime processor
            import sys
            import os
            sys.path.append(os.path.join(os.path.dirname(__file__), "..", "secondary_processing"))
            
            from esad_regime import RegimeTypeProcessor
            
            print(f"  🔄 Fetching regime data...")
            
            # Initialize and run the regime processor
            regime_processor = RegimeTypeProcessor()
            # Combine BOL and invoice data into a single structure for regime analysis
            combined_data = {
                'form_fields': {
                    'shipper': bol_data.get('shipper', ''),
                    'shipper_address': bol_data.get('shipper_address', ''),
                    'consignee_name': bol_data.get('consignee_name', ''),
                    'consignee_address': bol_data.get('consignee_address', ''),
                    'port_of_destination': bol_data.get('port_of_destination', ''),
                    'port_of_loading': bol_data.get('port_of_loading', ''),
                    'weight': bol_data.get('weight', ''),
                    'measure': bol_data.get('measure', ''),
                    'commodity': bol_data.get('commodity', ''),
                    'bill_of_lading': bol_data.get('bill_of_lading', ''),
                    'vessel': bol_data.get('vessel', ''),
                    'charges': bol_data.get('charges', [])
                },
                'invoice_data': invoice_data,
                'tables': []  # Add empty tables if needed
            }
            regime_data = regime_processor.determine_regime_type(combined_data)
            
            if regime_data:
                print(f"  📋 Regime data extracted:")
                print(f"     Regime Type: {regime_data.regime_type or 'N/A'}")
                print(f"     Description: {regime_data.description or 'N/A'}")
                print(f"     Procedure Code: {regime_data.procedure_code or 'N/A'}")
                
                return regime_data
            else:
                print(f"  ❌ Regime lookup failed")
                return None
                
        except Exception as e:
            print(f"  ❌ Error calling esad_regime: {e}")
            return None
    
    def _fetch_trn_data_if_needed(self, esad_fields: Dict[str, Any], bol_data: Dict[str, Any], invoice_data: Dict[str, Any], order_id: int) -> bool:
        """
        Check if TRN fields need to be populated and fetch TRN data if needed
        
        Args:
            esad_fields: Current ESAD fields
            bol_data: Bill of lading data
            invoice_data: Invoice data
            order_id: Order ID
            
        Returns:
            bool: True if TRN fields were updated, False otherwise
        """
        # Check if TRN fields need processing
        trn_fields_to_process = []
        
        for field_name, field_data in esad_fields.items():
            if field_data.get("source") == "pending_trn_lookup":
                trn_fields_to_process.append(field_name)
        
        if not trn_fields_to_process:
            print("  ✅ All TRN fields are already populated or not pending")
            return False
        
        print(f"  🔍 TRN fields need processing: {', '.join(trn_fields_to_process)}")
        
        # Fetch TRN data using esad_trn
        trn_data = self._call_esad_trn(bol_data, invoice_data)
        if not trn_data:
            print("  ❌ Failed to fetch TRN data")
            return False
        
        # Update TRN fields with lookup results
        fields_updated = 0
        
        for field_name in trn_fields_to_process:
            if field_name == "Importer/Consignee TRN No." and trn_data.get("importer") and trn_data["importer"].success:
                esad_fields[field_name]["value"] = trn_data["importer"].trn_number
                esad_fields[field_name]["source"] = "trn_lookup"
                print(f"  ✨ Updated {field_name}: {trn_data['importer'].trn_number}")
                fields_updated += 1
            elif field_name == "Declarant/Representative TRN No." and trn_data.get("exporter") and trn_data["exporter"].success:
                esad_fields[field_name]["value"] = trn_data["exporter"].trn_number
                esad_fields[field_name]["source"] = "trn_lookup"
                print(f"  ✨ Updated {field_name}: {trn_data['exporter'].trn_number}")
                fields_updated += 1
        
        if fields_updated > 0:
            print(f"  ✅ Successfully updated {fields_updated} TRN fields")
            return True
        
        return False
    
    def _call_esad_trn(self, bol_data: Dict[str, Any], invoice_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Call the esad_trn script to fetch TRN data
        
        Args:
            bol_data: Bill of lading data
            invoice_data: Invoice data
            
        Returns:
            dict: TRN data or None if failed
        """
        try:
            # Import the TRN lookup processor
            import sys
            import os
            sys.path.append(os.path.join(os.path.dirname(__file__), "..", "secondary_processing"))
            
            from esad_trn import TRNLookupProcessor
            
            print(f"  🔄 Fetching TRN data...")
            
            # Initialize and run the TRN lookup processor
            trn_processor = TRNLookupProcessor()
            trn_data = trn_processor.lookup_trn_from_documents(bol_data, invoice_data)
            
            if trn_data:
                print(f"  📋 TRN data extracted:")
                if trn_data.get("exporter") and trn_data["exporter"].success:
                    print(f"     Exporter TRN: {trn_data['exporter'].trn_number or 'N/A'}")
                if trn_data.get("importer") and trn_data["importer"].success:
                    print(f"     Importer TRN: {trn_data['importer'].trn_number or 'N/A'}")
                
                return trn_data
            else:
                print(f"  ❌ TRN lookup failed")
                return None
                
        except Exception as e:
            print(f"  ❌ Error calling esad_trn: {e}")
            return None
    
    def _is_trn_required(self, bol_data: Dict[str, Any]) -> bool:
        """
        Determine if TRN fields are required based on entity locations in BOL
        
        Args:
            bol_data: Bill of lading data
            
        Returns:
            bool: True if TRN is required (Jamaican entity), False otherwise
        """
        try:
            # Jamaican location indicators
            jamaica_indicators = [
                "JAMAICA", "JM", "JAM", "KINGSTON", "MONTEGO BAY", "PORT ROYAL",
                "OCHO RIOS", "NEGRIL", "FALMOUTH", "LUCEA", "BLACK RIVER"
            ]
            
            # Check address fields in BOL for Jamaican locations
            address_fields_to_check = [
                "shipper_address", "consignee_address", "notify_party_address",
                "port_of_destination", "port_of_loading", "place_of_delivery",
                "shipper", "consignee_name", "notify_party"
            ]
            
            # Convert all data to string and check for Jamaican indicators
            bol_text = " ".join([
                str(bol_data.get(field, "")) for field in address_fields_to_check
            ]).upper()
            
            # Check if any Jamaican indicator is present
            for indicator in jamaica_indicators:
                if indicator in bol_text:
                    print(f"    🇯🇲 Jamaican location detected: {indicator}")
                    return True
            
            print(f"    🌍 No Jamaican location detected - TRN not required")
            return False
            
        except Exception as e:
            print(f"    ⚠️ Error checking TRN requirement: {e}")
            # Default to requiring TRN if we can't determine
            return True
    
    def _call_llm(self, prompt: str) -> Optional[str]:
        """
        Call the OpenRouter LLM API with improved settings for cleaner responses
        
        Args:
            prompt: The prompt to send to the LLM
            
        Returns:
            str: LLM response or None if failed
        """
        try:
            # Get the model identifier
            model_id = OPENROUTER_GENERAL_MODELS.get(self.model)
            if not model_id:
                print(f"❌ Model {self.model} not found in OPENROUTER_GENERAL_MODELS")
                return None
            
            payload = {
                "model": model_id,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": 200,  # Reduced for cleaner responses
                "temperature": 0.0,  # Set to 0 for more deterministic responses
                "top_p": 0.1,        # More focused responses
                "frequency_penalty": 0.2,  # Reduce repetition
                "presence_penalty": 0.1    # Encourage conciseness
            }
            
            response = requests.post(
                OPENROUTER_URL,
                headers=OPENROUTER_HEADERS,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                return content.strip()
            else:
                print(f"❌ LLM API error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Error calling LLM: {e}")
            return None
    
    def _generate_esad_fields_json(self, order_id: int, esad_fields: Dict[str, Any]) -> Path:
        """
        Generate esad_fields.json file with the LLM processing results and manifest lookup data
        
        Args:
            order_id: Order ID
            esad_fields: Populated ESAD fields (including manifest lookup results)
            
        Returns:
            Path: Path to the generated JSON file
        """
        try:
            # Create output directory if it doesn't exist
            output_dir = Path(__file__).parent.parent / "processed_data" / "esad_fields"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"esad_fields_order_{order_id}_{timestamp}_manifest_enhanced.json"
            file_path = output_dir / filename
            
            # Count different source types
            manifest_lookup_count = len([f for f in esad_fields.values() if f.get("source") == "manifest_lookup"])
            regime_lookup_count = len([f for f in esad_fields.values() if f.get("source") == "regime_lookup"])
            trn_lookup_count = len([f for f in esad_fields.values() if f.get("source") == "trn_lookup"])
            trn_not_required_count = len([f for f in esad_fields.values() if f.get("source") == "not_required"])
            default_value_count = len([f for f in esad_fields.values() if f.get("source") == "default_value"])
            order_id_generated_count = len([f for f in esad_fields.values() if f.get("source") == "order_id_generated"])
            null_count = len([f for f in esad_fields.values() if f.get("value") is None])
            
            # Prepare the JSON structure
            esad_data = {
                "order_id": order_id,
                "processing_timestamp": datetime.now().isoformat(),
                "processor": "esad_primary_processor_llm_manifest_enhanced",
                "model_used": self.model,
                "fields_count": len(esad_fields),
                "lookup_summary": {
                    "total_fields": len(esad_fields),
                    "llm_populated": len([f for f in esad_fields.values() if f.get("source") == "llm_processing"]),
                    "manifest_lookup_populated": manifest_lookup_count,
                    "regime_lookup_populated": regime_lookup_count,
                    "trn_lookup_populated": trn_lookup_count,
                    "trn_not_required": trn_not_required_count,
                    "default_value_populated": default_value_count,
                    "order_id_generated": order_id_generated_count,
                    "remaining_null": null_count,
                    "total_lookup_rate": f"{((manifest_lookup_count + regime_lookup_count + trn_lookup_count + default_value_count + order_id_generated_count) / len(esad_fields) * 100):.1f}%"
                },
                "esad_fields": esad_fields
            }
            
            # Write to file
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(esad_data, f, indent=2, ensure_ascii=False)
            
            print(f"💾 Generated enhanced ESAD fields JSON: {file_path}")
            print(f"   📊 Lookup summary: {manifest_lookup_count} manifest fields, {regime_lookup_count} regime fields, {trn_lookup_count} TRN fields, {trn_not_required_count} TRN not required, {default_value_count} default values, {order_id_generated_count} order ID generated, {null_count} remaining null")
            return file_path
            
        except Exception as e:
            print(f"❌ Error generating ESAD fields JSON: {e}")
            return Path("error.json")
    
    def _save_to_esad_fields_table(self, order_id: int, esad_fields: Dict[str, Any]) -> int:
        """
        Save populated ESAD fields to the esad_fields table (ALL fields included)
        
        Args:
            order_id: Order ID
            esad_fields: Populated ESAD fields (including null values)
            
        Returns:
            int: Number of fields saved
        """
        if not self.supabase:
            print("⚠️ Supabase not available - skipping database save")
            return 0
        
        try:
            print(f"💾 Saving ESAD fields to esad_fields table for order {order_id}")
            
            # Prepare the record for the wide-column esad_fields table
            esad_record = {
                "order_id": order_id,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            fields_saved = 0
            null_fields = 0
            
            # Map ESAD field names to database column names
            for field_name, field_data in esad_fields.items():
                column_name = self._map_field_to_column(field_name)
                field_value = field_data.get("value")
                
                if column_name:
                    # Always save the field, even if value is None
                    esad_record[column_name] = field_value
                    fields_saved += 1
                    
                    if field_value is not None:
                        print(f"  ✅ Mapped: {field_name} -> {column_name} = {field_value}")
                    else:
                        print(f"  ⚠️ Mapped: {field_name} -> {column_name} = null")
                        null_fields += 1
                else:
                    print(f"  ❌ No column mapping found for: {field_name}")
            
            # Save the complete record to the esad_fields table
            if fields_saved > 0:
                try:
                    result = self.supabase.table("esad_fields").insert(esad_record).execute()
                    if result.data:
                        print(f"  💾 Saved {fields_saved} fields to esad_fields table ({null_fields} with null values)")
                        return fields_saved
                    else:
                        print(f"  ❌ Failed to save record to esad_fields table")
                        return 0
                        
                except Exception as e:
                    print(f"  ❌ Error saving to esad_fields table: {e}")
                    return 0
            
            return fields_saved
            
        except Exception as e:
            print(f"❌ Error saving to esad_fields table: {e}")
            return 0
    
    def _map_field_to_column(self, field_name: str) -> str:
        """
        Map ESAD field names to database column names
        
        Args:
            field_name: ESAD field name from eSAD.json
            
        Returns:
            str: Database column name or None if no mapping found
        """
        # Mapping from ESAD field names to database column names
        field_mapping = {
            # Box A fields
            "Office code": "office_code",
            "Manifest": "manifest",
            
            # Box 1-2 fields
            "Regime Type": "regime_type",
            "Exporter/Consignor Name/Company": "exporter_consignor_name_company",
            "Exporter/Consignor Address": "exporter_consignor_address",
            
            # Box 6-8 fields
            "Total packages": "total_packages",
            "Commercial reference number": "commercial_reference_number",
            "Importer/Consignee TRN No.": "importer_consignee_trn_no",
            "Importer/Consignee Name/Company": "importer_consignee_name_company",
            "Importer/Consignee Address": "importer_consignee_address",
            
            # Box 10-15 fields
            "Country Last Consignment": "country_last_consignment",
            "Trading Country": "trading_country",
            "Declarant/Representative TRN No.": "declarant_representative_trn_no",
            "Country of export": "country_of_export",
            "Country Origin Code": "country_origin_code",
            
            # Box 18 field
            "Identity and nationality of active means of transport at arrival": "transport_identity_nationality",
            
            # Box 20 fields
            "Delivery terms": "delivery_terms",
            "Applicable place": "applicable_place",
            
            # Box 22 fields
            "Currency code": "currency_code",
            "Amount": "amount",
            
            # Box val_note fields
            "Invoice value": "invoice_value",
            "Freight charges": "freight_charges",
            "Insurance charges": "insurance_charges",
            
            # Box 24-25 fields
            "Nature of Transaction": "nature_of_transaction",
            "Mode of transport at the border": "mode_transport_border",
            
            # Box 27, 30, 31 fields
            "Place of Loading/Unloading": "place_loading_unloading",
            "Location of goods": "location_of_goods",
            "Marks and numbers of packages": "marks_numbers_of_packages",
            "No. of packages": "number_of_packages",
            "Kind of packages": "kind_of_packages",
            "Commercial description": "commercial_description",
            
            # Box 33-38 fields
            "Commodity code": "commodity_code",
            "Gross Weight (kg)": "gross_weight_kg",
            "Procedure": "procedure",
            "Net Weight (kg)": "net_weight_kg",
            
            # Box 40-43 fields
            "Transport document/Previous Document": "transport_document",
            "Statistical Units": "statistical_units",
            "V.M.": "valuation_method",
            
            # Box 49-50 fields
            "Identification of warehouse": "identification_of_warehouse",
            "Principal": "principal"
        }
        
        return field_mapping.get(field_name)


def main():
    """Test the improved ESAD primary processor with LLM"""
    
    # Example extracted data for testing - replace with actual document data
    bol_extraction = {
        "manifest/registration_#": "JMALB 2025 32",
        "shipper": "EXAMPLE COMPANY",
        "shipper_address": "123 MAIN STREET, CITY, STATE 12345. COUNTRY NAME",
        "consignee_name": "EXAMPLE CONSIGNEE",
        "consignee_address": "456 DESTINATION ROAD, KINGSTON 19, JAMAICA",
        "port_of_loading": "ORIGIN PORT, ORIGIN COUNTRY",
        "port_of_destination": "KINGSTON, JAMAICA",
        "vessel": "EXAMPLE VESSEL / VOYAGE123",
        "vessel_flag": "EXAMPLE COUNTRY",
        "weight": "100.50 KGM",
        "package_type": "BX",
        "commodity": "3 CTNS STC: EXAMPLE PRODUCT DESCRIPTION",
        "bill_of_lading": "BL123456",
        "charges": [
            {"charge_type": "FREIGHT", "currency": "USD", "collect_amount": "250.00"},
            {"charge_type": "HANDLING", "currency": "JMD", "local_collect_amount": "1500.00"}
        ]
    }
    
    invoice_extraction = {
        "supplier": {"name": "Example Supplier Inc."},
        "buyer": {"name": "Example Buyer"},
        "items": [{"description": "Example Product Description", "quantity": 2.0}],
        "totals": {"total_amount": 1200.00},
        "currency": "USD"
    }
    
    # Initialize improved processor
    processor = ESADPrimaryProcessor(model="mistral_small")
    
    # Process
    print("Testing improved ESAD primary processor with LLM...")
    print("Note: Using example data - replace with actual document extractions")
    result = processor.process_order(1, bol_extraction, invoice_extraction)
    
    print(f"\nProcessing Result:")
    print(f"Status: {result.get('processing_status')}")
    print(f"Fields populated: {result.get('fields_populated')}")
    print(f"Fields saved to DB: {result.get('fields_saved_to_db')}")
    print(f"ESAD fields JSON: {result.get('esad_fields_json_path')}")


if __name__ == "__main__":
    main() 