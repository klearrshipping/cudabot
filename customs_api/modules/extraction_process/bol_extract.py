#!/usr/bin/env python3
"""
bol_extract.py
─────────────────────────
Bill of Lading and Arrival Notice extractor using Claude Sonnet 4 via OpenRouter
Now includes database integration for storing extractions
"""

from dotenv import load_dotenv
load_dotenv()

import os, pathlib, json
from pathlib import Path
from datetime import datetime
import re
from typing import Dict, List, Any
import base64
import requests

# Import configuration
import sys
sys.path.append(str(Path(__file__).parent.parent))
from config import OPENROUTER_API_KEY, OPENROUTER_URL, OPENROUTER_HEADERS, OPENROUTER_EXTRACTION_MODELS

# Import enhanced database client
try:
    from modules.core.supabase_client import (
        create_or_get_order, create_document_record, save_bol_extraction,
        check_database_schema
    )
    DB_AVAILABLE = True
except ImportError:
    print("⚠️ Database integration not available - falling back to file-based storage")
    DB_AVAILABLE = False


class FlexibleFormExtractor:
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or OPENROUTER_API_KEY
        # Use GPT-5 Mini as primary model for best document extraction performance
        self.model = model or OPENROUTER_EXTRACTION_MODELS.get("gpt_5_mini", "openai/gpt-5-mini")
        self.base_url = OPENROUTER_URL or "https://openrouter.ai/api/v1/chat/completions"
        
        # Set up headers
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://yourdomain.com",  # Replace with your domain
            "X-Title": "BOL Document Extraction"
        }
        
        if not self.api_key or self.api_key == "your_openrouter_api_key_here":
            raise ValueError("Please set your OpenRouter API key in config.py")
        
        # Check database availability
        if DB_AVAILABLE:
            try:
                check_database_schema()
            except Exception as e:
                print(f"⚠️ Database check failed: {e}")

    def process_document(self, file_path: Path, save_to_file: bool = True, 
                        order_number: str = None, save_to_db: bool = True) -> Dict[str, Any]:
        """Process bill of lading or arrival notice using Claude Sonnet 4 via OpenRouter"""
        print(f"🔄 Processing: {file_path.name}")

        try:
            # Convert PDF to image for OpenRouter compatibility
            image_data_url = self._convert_pdf_to_image(file_path)
            print(f"📸 PDF converted to image successfully")

            # Create the extraction prompt
            extraction_prompt = self._create_extraction_prompt()
            
            # Send request to OpenRouter with image
            response = self._send_to_openrouter_with_image(extraction_prompt, image_data_url)
            extracted_data = self._parse_openrouter_response(response)
            
            # Add metadata
            metadata = {
                "extraction_timestamp": datetime.now().isoformat(),
                "source_file": str(file_path),
                "processor": "claude_sonnet_4_via_openrouter",
                "model": self.model,
                "document_type": self._detect_document_type(extracted_data),
                "processing_method": "pdf_to_image_conversion"
            }
            
            extracted_data["_metadata"] = metadata
            
            # BOL Number Validation and Recheck
            extracted_data = self._validate_and_fix_bol_number(extracted_data, image_data_url)
            
            # Save to database if available and requested
            if save_to_db and DB_AVAILABLE and order_number:
                try:
                    self._save_to_database(extracted_data, file_path, order_number, metadata)
                except Exception as e:
                    print(f"⚠️ Failed to save to database: {e}")
                    print("   Falling back to file-based storage")
                    save_to_file = True
            
            # Save to file if requested or if database save failed
            if save_to_file:
                self.save_results(extracted_data)
            
            return extracted_data
            
        except Exception as e:
            print(f"❌ Error processing with OpenRouter: {e}")
            return {
                'status': 'failed',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }

    def _create_extraction_prompt(self) -> str:
        """Create extraction prompt for comprehensive data extraction"""
        return """You are a document extraction specialist. Your task is to analyze this Bill of Lading or Arrival Notice document and extract ALL information present in the document.

CRITICAL: You MUST respond with ONLY a valid JSON object. Do not include any markdown formatting, explanations, or additional text.

Extract ALL data from the document and organize it logically. Include:
- All names, addresses, and contact information
- All dates in their original format
- All numbers, codes, and identifiers
- All locations, ports, and destinations
- All vessel and shipping information
- All cargo and commodity details
- All weights, measures, and quantities
- All charges, fees, and costs
- Any other information visible in the document

Use descriptive field names that match what you see in the document. If you see multiple similar fields, include them all with descriptive names.

Example structure (adapt based on what you actually see):
{
    "document_type": "Bill of Lading or Arrival Notice",
    "document_number": "any document number you see",
    "date_issued": "date when document was issued",
    "shipper": {
        "name": "shipper company name",
        "address": "complete shipper address",
        "contact": "any contact information"
    },
    "consignee": {
        "name": "consignee name", 
        "address": "complete consignee address",
        "contact": "any contact information"
    },
    "vessel_info": {
        "vessel_name": "vessel name",
        "voyage_number": "voyage number",
        "flag": "vessel flag if visible"
    },
    "ports": {
        "origin": "port of origin",
        "loading": "port of loading", 
        "discharge": "port of discharge",
        "destination": "port of destination"
    },
    "cargo": {
        "description": "cargo description",
        "weight": "weight information",
        "measurement": "measurement information",
        "packages": "package information",
        "marks_numbers": "marks and numbers"
    },
    "containers": "container information if present",
    "charges": "any charges or fees information",
    "additional_info": "any other information you see"
}

Extract EVERYTHING you can see in the document. Don't leave out any information.

CRITICAL INSTRUCTIONS FOR CHARGES EXTRACTION:
- Look for ANY table containing charges/fees in the document
- Extract ALL rows from the charges table, regardless of charge type names
- Common charge types include: FREIGHT, PSS, HANDLING, WHARFAGE, AGENCY FEE, GCT, STRIPPING, DOCUMENTATION FEE, etc.
- Tables typically have columns like: Charge Type, Currency, Prepaid Amount, Collect Amount, Local Prepaid Amount, Local Collect Amount
- Extract the EXACT charge type names as they appear (including parentheses, abbreviations)
- Include ALL amounts even if they are 0.00 or .00
- If table structure is different, adapt the format but capture all charge information
- Do not skip any charges - extract everything from the charges/fees table

Other extraction guidelines:
- Extract dates in DD/MM/YYYY format
- If multiple containers, extract the first/primary one
- For commodity, include both description and any marks/numbers
- Extract exact text as it appears in the document
- If a field is not found, use null
- Return ONLY the JSON object, no additional text, no markdown formatting
- Ensure the JSON is valid and complete

Be comprehensive in extracting ALL charges from any charges/fees table found in the document."""

    def _convert_pdf_to_image(self, file_path: Path) -> str:
        """Convert PDF to optimized image data URL for OpenRouter"""
        try:
            import fitz  # PyMuPDF
            
            # Open PDF
            pdf_document = fitz.open(file_path)
            
            # Convert first page to image (most BOLs are single page)
            page = pdf_document[0]
            
            # Use lower DPI for BOL documents to reduce file size (200 DPI instead of 300)
            mat = fitz.Matrix(200/72, 200/72)  # 200 DPI transformation matrix
            pix = page.get_pixmap(matrix=mat)
            
            # Convert to JPEG instead of PNG for smaller file size
            img_data = pix.tobytes("jpeg", jpg_quality=85)  # 85% quality for good balance
            pdf_document.close()
            
            # Check file size and compress further if needed (OpenRouter has ~5MB limit)
            max_size_mb = 4  # Conservative limit
            if len(img_data) > max_size_mb * 1024 * 1024:
                print(f"⚠️ Image too large ({len(img_data)/1024/1024:.1f}MB), compressing further...")
                # Re-process with lower quality
                pdf_document = fitz.open(file_path)
                page = pdf_document[0]
                mat = fitz.Matrix(150/72, 150/72)  # Lower DPI
                pix = page.get_pixmap(matrix=mat)
                img_data = pix.tobytes("jpeg", jpg_quality=70)  # Lower quality
                pdf_document.close()
            
            # Encode as base64
            img_base64 = base64.b64encode(img_data).decode('utf-8')
            
            print(f"📏 Final image size: {len(img_data)/1024/1024:.1f}MB")
            
            # Return as data URL with JPEG format
            return f"data:image/jpeg;base64,{img_base64}"
            
        except ImportError:
            # Fallback: Try with pdf2image if PyMuPDF not available
            try:
                from pdf2image import convert_from_path
                import io
                from PIL import Image
                
                # Convert PDF to images with lower DPI
                images = convert_from_path(file_path, dpi=200, first_page=1, last_page=1)
                
                if not images:
                    raise Exception("No images generated from PDF")
                
                # Get first page image
                image = images[0]
                
                # Convert to JPEG bytes with compression
                img_buffer = io.BytesIO()
                image.save(img_buffer, format='JPEG', quality=85, optimize=True)
                img_data = img_buffer.getvalue()
                
                # Check size and compress further if needed
                max_size_mb = 4
                if len(img_data) > max_size_mb * 1024 * 1024:
                    print(f"⚠️ Image too large ({len(img_data)/1024/1024:.1f}MB), compressing further...")
                    img_buffer = io.BytesIO()
                    # Resize image if too large
                    image = image.resize((int(image.width * 0.7), int(image.height * 0.7)), Image.LANCZOS)
                    image.save(img_buffer, format='JPEG', quality=70, optimize=True)
                    img_data = img_buffer.getvalue()
                
                # Encode as base64
                img_base64 = base64.b64encode(img_data).decode('utf-8')
                
                print(f"📏 Final image size: {len(img_data)/1024/1024:.1f}MB")
                
                # Return as data URL
                return f"data:image/jpeg;base64,{img_base64}"
                
            except ImportError:
                raise Exception("PDF conversion requires PyMuPDF (pip install PyMuPDF) or pdf2image (pip install pdf2image)")

    def _send_to_openrouter_with_image(self, prompt: str, image_data_url: str) -> Dict[str, Any]:
        """Send request to OpenRouter API with image data"""
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_data_url,
                                "detail": "high"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 4000,
            "temperature": 0.1
        }
        
        print(f"🚀 Sending BOL request to OpenRouter with model: {self.model}")
        print(f"🚀 Payload keys: {list(payload.keys())}")
        print(f"🚀 Image data URL length: {len(image_data_url)}")
        
        try:
            response = requests.post(self.base_url, headers=self.headers, json=payload)
            print(f"🚀 BOL Response status: {response.status_code}")
            print(f"🚀 BOL Response headers: {dict(response.headers)}")
            
            response.raise_for_status()
            response_data = response.json()
            print(f"🚀 BOL Response data keys: {list(response_data.keys())}")
            
            return response_data
        except requests.exceptions.HTTPError as e:
            print(f"HTTP Error: {e}")
            print(f"Response status: {e.response.status_code}")
            print(f"Response content: {e.response.text if hasattr(e, 'response') else 'No response content'}")
            raise
        except Exception as e:
            print(f"Request Error: {e}")
            raise

    def _parse_openrouter_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Parse OpenRouter's response and extract structured data"""
        try:
            # Extract content from OpenRouter's response (OpenAI-compatible format)
            choices = response.get('choices', [])
            if choices and len(choices) > 0:
                message = choices[0].get('message', {})
                text_content = message.get('content', '')
                
                print(f"🔍 Raw LLM Response: {text_content[:500]}...")  # Debug: Show first 500 chars
                
                # First, try to extract JSON from response
                json_match = re.search(r'\{.*\}', text_content, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    print(f"🔍 Extracted JSON: {json_str[:500]}...")  # Debug: Show extracted JSON
                    
                    try:
                        extracted_data = json.loads(json_str)
                        
                        # Clean and validate the extracted data
                        cleaned_data = self._clean_extracted_data(extracted_data)
                        
                        print(f"🔍 Cleaned Data Keys: {list(cleaned_data.keys())}")  # Debug: Show what keys we have
                        if 'shipper' in cleaned_data:
                            print(f"🔍 Shipper Data: {cleaned_data['shipper']}")
                        if 'consignee_name' in cleaned_data:
                            print(f"🔍 Consignee Data: {cleaned_data['consignee_name']}")
                        if 'bill_of_lading' in cleaned_data:
                            print(f"🔍 BOL Number: {cleaned_data['bill_of_lading']}")
                        
                        return cleaned_data
                    except json.JSONDecodeError as e:
                        print(f"⚠️ JSON parsing failed, trying markdown parsing: {e}")
                        # Fall back to markdown parsing
                        return self._parse_markdown_response(text_content)
                else:
                    print(f"⚠️ No JSON found in response, using markdown parsing")
                    # Use markdown parsing as fallback
                    return self._parse_markdown_response(text_content)
            else:
                print(f"❌ No choices in response: {response}")  # Debug: Show full response structure
                return {
                    'status': 'error',
                    'error': 'No content in OpenRouter response',
                    'full_response': response,
                    'timestamp': datetime.now().isoformat()
                }
                
        except Exception as e:
            print(f"❌ Unexpected Error: {e}")  # Debug: Show unexpected error
            return {
                'status': 'error',
                'error': f'Unexpected error parsing response: {e}',
                'raw_response': response,
                'timestamp': datetime.now().isoformat()
            }

    def _parse_markdown_response(self, text_content: str) -> Dict[str, Any]:
        """Parse markdown response when JSON parsing fails"""
        print("🔄 Parsing BOL markdown response as fallback...")
        
        extracted_data = {
            "reported_date": None,
            "consignee_name": None,
            "consignee_address": None,
            "consignee_tel#": None,
            "shipper": None,
            "shipper_address": None,
            "master_bill_of_lading": None,
            "voyage_number": None,
            "bill_of_lading": None,
            "last_departure_date": None,
            "port_of_origin": None,
            "port_of_loading": None,
            "port_of_destination": None,
            "vessel": None,
            "manifest/registration_#": None,
            "Wharfinger": None,
            "vessel_flag": None,
            "berth": None,
            "container": None,
            "weight": None,
            "package_type": None,
            "measure": None,
            "commodity": None,
            "charges": []
        }
        
        # Extract shipper information
        shipper_match = re.search(r'\*\s*Shipper:\s*([^*\n]+)', text_content, re.IGNORECASE)
        if shipper_match:
            extracted_data["shipper"] = shipper_match.group(1).strip()
        
        # Extract consignee information
        consignee_match = re.search(r'\*\s*Consignee Name:\s*([^*\n]+)', text_content, re.IGNORECASE)
        if consignee_match:
            extracted_data["consignee_name"] = consignee_match.group(1).strip()
        
        consignee_addr_match = re.search(r'\*\s*Consignee Address:\s*([^*\n]+)', text_content, re.IGNORECASE)
        if consignee_addr_match:
            extracted_data["consignee_address"] = consignee_addr_match.group(1).strip()
        
        # Extract vessel information
        vessel_match = re.search(r'\*\s*Vessel:\s*([^*\n]+)', text_content, re.IGNORECASE)
        if vessel_match:
            extracted_data["vessel"] = vessel_match.group(1).strip()
        
        voyage_match = re.search(r'\*\s*Actual Voyage Number:\s*([^*\n]+)', text_content, re.IGNORECASE)
        if voyage_match:
            extracted_data["voyage_number"] = voyage_match.group(1).strip()
        
        # Extract BOL numbers
        bol_match = re.search(r'\*\s*Bill Of Lading:\s*([^*\n]+)', text_content, re.IGNORECASE)
        if bol_match:
            extracted_data["bill_of_lading"] = bol_match.group(1).strip()
        
        master_bol_match = re.search(r'\*\s*Master Bill Of Lading:\s*([^*\n]+)', text_content, re.IGNORECASE)
        if master_bol_match:
            extracted_data["master_bill_of_lading"] = master_bol_match.group(1).strip()
        
        # Extract dates
        reported_match = re.search(r'\*\s*Reported Date:\s*([^*\n]+)', text_content, re.IGNORECASE)
        if reported_match:
            extracted_data["reported_date"] = reported_match.group(1).strip()
        
        # Extract ports
        port_loading_match = re.search(r'\*\s*Port of Loading:\s*([^*\n]+)', text_content, re.IGNORECASE)
        if port_loading_match:
            extracted_data["port_of_loading"] = port_loading_match.group(1).strip()
        
        port_dest_match = re.search(r'\*\s*Port of Destination:\s*([^*\n]+)', text_content, re.IGNORECASE)
        if port_dest_match:
            extracted_data["port_of_destination"] = port_dest_match.group(1).strip()
        
        # Extract container information
        container_match = re.search(r'\*\s*Container Number:\s*([^*\n]+)', text_content, re.IGNORECASE)
        if container_match:
            extracted_data["container"] = container_match.group(1).strip()
        
        # Extract charges
        charges_section = re.search(r'\*\*Charge Information\*\*.*?(\*\s*Charge Type:.*?)(?=\*\*|$)', text_content, re.DOTALL | re.IGNORECASE)
        if charges_section:
            charge_blocks = re.findall(r'\*\s*Charge Type:\s*([^*\n]+).*?Currency:\s*([^*\n]+).*?Prepaid Amount:\s*([^*\n]+).*?Collect Amount:\s*([^*\n]+).*?Local Prepaid Amount:\s*([^*\n]+).*?Local Collect Amount:\s*([^*\n]+)', 
                                     charges_section.group(1), re.DOTALL | re.IGNORECASE)
            
            for charge_block in charge_blocks:
                charge_data = {
                    "charge_type": charge_block[0].strip(),
                    "currency": charge_block[1].strip(),
                    "prepaid_amount": charge_block[2].strip(),
                    "collect_amount": charge_block[3].strip(),
                    "local_prepaid_amount": charge_block[4].strip(),
                    "local_collect_amount": charge_block[5].strip()
                }
                extracted_data["charges"].append(charge_data)
        
        print(f"🔍 BOL Markdown parsing completed. Extracted {len([k for k, v in extracted_data.items() if v])} fields")
        return extracted_data

    def _clean_extracted_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Clean and validate extracted data (flexible approach)"""
        cleaned = {}
        
        # Clean all fields from the extracted data (don't limit to predefined fields)
        for key, value in data.items():
            if value is not None and str(value).strip() and str(value).lower() not in ['null', 'none', 'n/a']:
                if isinstance(value, (dict, list)):
                    cleaned[key] = value  # Keep complex structures as-is
                else:
                    cleaned[key] = str(value).strip()
            else:
                cleaned[key] = None
        
        # Handle charges separately with flexible structure
        if 'charges' in data and isinstance(data['charges'], list):
            cleaned['charges'] = []
            for charge in data['charges']:
                if isinstance(charge, dict):
                    clean_charge = {}
                    
                    # Required fields
                    if 'charge_type' in charge and charge['charge_type']:
                        clean_charge['charge_type'] = str(charge['charge_type']).strip()
                    if 'currency' in charge and charge['currency']:
                        clean_charge['currency'] = str(charge['currency']).strip()
                    
                    # Optional amount fields - include any that exist
                    amount_fields = ['prepaid_amount', 'collect_amount', 'local_prepaid_amount', 'local_collect_amount', 'amount']
                    for field in amount_fields:
                        if field in charge and charge[field] is not None:
                            # Clean amount (remove commas, keep decimals)
                            amount_str = str(charge[field]).strip().replace(',', '')
                            if amount_str and amount_str != 'null':
                                clean_charge[field] = amount_str
                    
                    # Only add charge if we have charge_type and currency
                    if len(clean_charge) >= 2:  
                        cleaned['charges'].append(clean_charge)
        else:
            cleaned['charges'] = []
        
        return cleaned

    def _detect_document_type(self, extracted_data: Dict[str, Any]) -> str:
        """Detect document type based on extracted content"""
        # Check for arrival notice indicators
        if extracted_data.get('reported_date') or extracted_data.get('Wharfinger'):
            return "Arrival Notice"
        # Check for bill of lading indicators
        elif extracted_data.get('master_bill_of_lading') or extracted_data.get('bill_of_lading'):
            return "Bill of Lading"
        else:
            return "Shipping Document"
    
    def _validate_and_fix_bol_number(self, extracted_data: Dict[str, Any], image_data_url: str) -> Dict[str, Any]:
        """
        Validate that BOL number is present and attempt to fix if missing
        
        Args:
            extracted_data: Initial extraction results
            image_data_url: Image data for re-extraction if needed
            
        Returns:
            Dict: Updated extraction data with BOL number fixed if possible
        """
        # Check if bill_of_lading field is empty or null
        bol_number = extracted_data.get('bill_of_lading')
        master_bol = extracted_data.get('master_bill_of_lading')
        
        # If bill_of_lading is empty but master_bill_of_lading has a value, move it
        if (not bol_number or bol_number.strip() == '' or bol_number.lower() == 'null') and master_bol:
            print(f"⚠️ BOL number missing in 'bill_of_lading' field, found in 'master_bill_of_lading': {master_bol}")
            print(f"🔄 Moving BOL number from master_bill_of_lading to bill_of_lading")
            extracted_data['bill_of_lading'] = master_bol
            extracted_data['master_bill_of_lading'] = None
            print(f"✅ BOL number fixed: {master_bol}")
            return extracted_data
        
        # If both fields are empty, try to re-extract with a focused prompt
        if (not bol_number or bol_number.strip() == '' or bol_number.lower() == 'null') and \
           (not master_bol or master_bol.strip() == '' or master_bol.lower() == 'null'):
            print(f"❌ No BOL number found in either field - attempting re-extraction")
            return self._recheck_bol_number(extracted_data, image_data_url)
        
        # If we have a valid BOL number, validate it
        if bol_number and bol_number.strip() and bol_number.lower() != 'null':
            print(f"✅ BOL number validation passed: {bol_number}")
            return extracted_data
        
        return extracted_data
    
    def _recheck_bol_number(self, extracted_data: Dict[str, Any], image_data_url: str) -> Dict[str, Any]:
        """
        Re-extract BOL number using a focused prompt
        
        Args:
            extracted_data: Current extraction results
            image_data_url: Image data for re-extraction
            
        Returns:
            Dict: Updated extraction data with BOL number if found
        """
        try:
            print(f"🔍 Attempting BOL number re-extraction...")
            
            # Create a focused prompt just for BOL number extraction
            bol_focus_prompt = """You are a document analysis specialist. Your task is to find the Bill of Lading (BOL) number in this document.

CRITICAL: You MUST respond with ONLY a valid JSON object containing the BOL number.

Look for:
- "Bill of Lading" or "B/L" followed by a number
- "BOL" followed by a number  
- "House Bill" followed by a number
- Any alphanumeric code that looks like a BOL number (typically 8-15 characters)

Respond with this EXACT JSON format:
{
    "bill_of_lading": "the_bol_number_you_find",
    "master_bill_of_lading": "master_bol_if_different",
    "bol_confidence": "high/medium/low"
}

If you cannot find a BOL number, use null for bill_of_lading.
Return ONLY the JSON object, no additional text."""

            # Send focused request
            response = self._send_to_openrouter_with_image(bol_focus_prompt, image_data_url)
            bol_data = self._parse_openrouter_response(response)
            
            # Check if we found a BOL number
            found_bol = bol_data.get('bill_of_lading')
            if found_bol and found_bol.strip() and found_bol.lower() != 'null':
                print(f"✅ BOL number found during recheck: {found_bol}")
                extracted_data['bill_of_lading'] = found_bol
                extracted_data['master_bill_of_lading'] = bol_data.get('master_bill_of_lading')
                
                # Add recheck metadata
                if '_metadata' in extracted_data:
                    extracted_data['_metadata']['bol_recheck'] = True
                    extracted_data['_metadata']['bol_confidence'] = bol_data.get('bol_confidence', 'unknown')
            else:
                print(f"❌ BOL number recheck failed - no BOL number found")
                if '_metadata' in extracted_data:
                    extracted_data['_metadata']['bol_recheck'] = False
                    extracted_data['_metadata']['bol_validation_failed'] = True
            
            return extracted_data
            
        except Exception as e:
            print(f"❌ BOL number recheck failed with error: {e}")
            if '_metadata' in extracted_data:
                extracted_data['_metadata']['bol_recheck'] = False
                extracted_data['_metadata']['bol_recheck_error'] = str(e)
            return extracted_data

    def save_results(self, data: Dict[str, Any], output_dir: Path = None) -> Path:
        """Save extraction results to JSON file"""
        if output_dir is None:
            output_dir = Path("extracted_data")
        
        output_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        doc_type = data.get("_metadata", {}).get("document_type", "shipping_document").lower().replace(' ', '_')
        output_file = output_dir / f"{doc_type}_extracted_{timestamp}.json"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Results saved to: {output_file}")
        return output_file

    def print_summary(self, data: Dict[str, Any]):
        """Print extraction summary"""
        print(f"\n✅ Document processed successfully!")
        print(f"📄 Document Type: {data.get('_metadata', {}).get('document_type', 'Unknown')}")
        
        # Print key fields
        key_fields = [
            "consignee_name", "shipper", "vessel", "container", 
            "port_of_loading", "port_of_destination"
        ]
        
        print(f"📊 Key Information Extracted:")
        for field in key_fields:
            value = data.get(field, 'Not found')
            if value and value != 'Not found':
                print(f"   {field}: {value}")
        
        # Print charges
        charges = data.get('charges', [])
        if charges:
            print(f"💰 Charges Found: {len(charges)}")
            for charge in charges:
                charge_type = charge.get('charge_type', '')
                currency = charge.get('currency', '')
                
                # Show different amount types if available
                if 'collect_amount' in charge and charge['collect_amount'] not in ['0.00', '.00', '0']:
                    print(f"   {charge_type}: {currency} {charge['collect_amount']} (Collect)")
                elif 'local_collect_amount' in charge and charge['local_collect_amount'] not in ['0.00', '.00', '0']:
                    print(f"   {charge_type}: {currency} {charge['local_collect_amount']} (Local Collect)")
                elif 'prepaid_amount' in charge and charge['prepaid_amount'] not in ['0.00', '.00', '0']:
                    print(f"   {charge_type}: {currency} {charge['prepaid_amount']} (Prepaid)")
                elif 'amount' in charge:
                    print(f"   {charge_type}: {currency} {charge['amount']}")
                else:
                    print(f"   {charge_type}: {currency} (No amount found)")
        else:
            print("💰 No charges found")

    def _save_to_database(self, extracted_data: Dict[str, Any], file_path: Path, 
                         order_number: str, metadata: Dict[str, Any]) -> bool:
        """Save BOL extraction to database"""
        try:
            # Create or get order
            order = create_or_get_order(order_number)
            if not order:
                print("❌ Failed to create/get order")
                return False
            
            # Create document record
            document = create_document_record(
                order_id=order["id"],
                file_name=file_path.name,
                file_path=str(file_path),
                document_type="bol",
                description="Bill of Lading document",
                file_size=file_path.stat().st_size if file_path.exists() else None
            )
            if not document:
                print("❌ Failed to create document record")
                return False
            
            # Save BOL extraction
            extraction = save_bol_extraction(
                document_id=document["id"],
                order_id=order["id"],
                extracted_data=extracted_data,
                metadata=metadata
            )
            if not extraction:
                print("❌ Failed to save BOL extraction")
                return False
            
            print(f"✅ Successfully saved BOL extraction to database for order {order_number}")
            return True
            
        except Exception as e:
            print(f"❌ Error saving to database: {e}")
            return False


# Main execution
def main():
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python bol_extract.py <bol_file_path>")
        return
    
    file_path = Path(sys.argv[1])
    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        return
    
    try:
        extractor = FlexibleFormExtractor()
        result = extractor.process_document(file_path)
        
        if result.get('status') == 'error':
            print(f"❌ Extraction failed: {result.get('error')}")
        else:
            extractor.print_summary(result)
            
    except Exception as e:
        print(f"❌ Failed to process document: {e}")


if __name__ == "__main__":
    main() 