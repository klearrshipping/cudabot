#!/usr/bin/env python3
"""
invoice_extract.py
─────────────────────────
Invoice extractor using Claude Sonnet 4 via OpenRouter with PDF-to-Image conversion
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
        create_or_get_order, create_document_record, save_invoice_extraction,
        check_database_schema
    )
    DB_AVAILABLE = True
except ImportError:
    print("⚠️ Database integration not available - falling back to file-based storage")
    DB_AVAILABLE = False


class InvoiceExtractor:
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
            "X-Title": "Invoice Document Extraction"
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
        """Process invoice using Claude Sonnet 4 via OpenRouter with PDF-to-Image conversion"""
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
                "processing_method": "pdf_to_image_conversion"
            }
            
            extracted_data["_metadata"] = metadata
            
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

    def _convert_pdf_to_image(self, file_path: Path) -> str:
        """Convert PDF to optimized image data URL for OpenRouter"""
        try:
            import fitz  # PyMuPDF
            
            # Open PDF
            pdf_document = fitz.open(file_path)
            
            # Convert first page to image (most invoices are single page)
            page = pdf_document[0]
            
            # Use optimized DPI for good quality while keeping file size manageable
            mat = fitz.Matrix(250/72, 250/72)  # 250 DPI transformation matrix
            pix = page.get_pixmap(matrix=mat)
            
            # Convert to JPEG instead of PNG for smaller file size
            img_data = pix.tobytes("jpeg", jpg_quality=90)  # 90% quality for invoices (need good text clarity)
            pdf_document.close()
            
            # Encode as base64
            img_base64 = base64.b64encode(img_data).decode('utf-8')
            
            # Return as data URL with JPEG format
            return f"data:image/jpeg;base64,{img_base64}"
            
        except ImportError:
            # Fallback: Try with pdf2image if PyMuPDF not available
            try:
                from pdf2image import convert_from_path
                import io
                from PIL import Image
                
                # Convert PDF to images with optimized DPI
                images = convert_from_path(file_path, dpi=250, first_page=1, last_page=1)
                
                if not images:
                    raise Exception("No images generated from PDF")
                
                # Get first page image
                image = images[0]
                
                # Convert to JPEG bytes with compression
                img_buffer = io.BytesIO()
                image.save(img_buffer, format='JPEG', quality=90, optimize=True)
                img_data = img_buffer.getvalue()
                
                # Encode as base64
                img_base64 = base64.b64encode(img_data).decode('utf-8')
                
                # Return as data URL
                return f"data:image/jpeg;base64,{img_base64}"
                
            except ImportError:
                raise Exception("PDF conversion requires PyMuPDF (pip install PyMuPDF) or pdf2image (pip install pdf2image)")

    def _create_extraction_prompt(self) -> str:
        """Create a comprehensive prompt for Claude to extract invoice data"""
        return """You are a document extraction specialist. Your task is to analyze this invoice document and extract all relevant information.

CRITICAL: You MUST respond with ONLY a valid JSON object. Do not include any markdown formatting, explanations, or additional text.

Extract the information in this EXACT JSON structure:

{
    "supplier": {
        "name": "extracted supplier company name",
        "address": "extracted supplier complete address",
        "contact": {
            "phone": "extracted supplier phone number if available",
            "email": "extracted supplier email if available"
        }
    },
    "buyer": {
        "name": "extracted buyer name",
        "address": "extracted buyer complete address",
        "contact": {
            "phone": "extracted buyer phone if available",
            "email": "extracted buyer email if available"
        }
    },
    "invoice_details": {
        "invoice_number": "extracted invoice number",
        "date": "extracted invoice date",
        "due_date": "extracted due date if available",
        "order_number": "extracted order number if available",
        "reference": "extracted reference number if available"
    },
    "items": [
        {
            "description": "detailed item description",
            "quantity": "item quantity as number",
            "unit_price": "unit price as number",
            "total_price": "total price for this item as number",
            "sku": "SKU or product code if available"
        }
    ],
    "totals": {
        "subtotal": "subtotal amount as number",
        "shipping_handling": "shipping and handling amount as number",
        "tax": "tax amount as number",
        "discount_amount": "discount amount if available",
        "total_amount": "final total amount as number"
    },
    "shipping": {
        "method": "shipping method if specified",
        "delivery_terms": "delivery terms (e.g., CIF, FOB, etc.)",
        "tracking_number": "tracking number if available",
        "delivery_date": "expected delivery date if available"
    },
    "payment_terms": {
        "method": "payment method if specified",
        "terms": "payment terms (e.g., Net 30)",
        "due_date": "payment due date if different from invoice date"
    },
    "currency": "currency code (USD, EUR, etc.)",
    "document_type": "invoice",
    "extraction_confidence": "high/medium/low based on clarity of document"
}

IMPORTANT INSTRUCTIONS:
- For numerical values, extract only the number without currency symbols
- If you cannot extract a field, use null
- For addresses, include the complete address including city, state, and postal code if available
- Pay special attention to distinguishing between shipping addresses and billing addresses
- Return ONLY the JSON object, no additional text, no markdown formatting
- Ensure the JSON is valid and complete"""

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
        
        print(f"🚀 Sending request to OpenRouter with model: {self.model}")
        print(f"🚀 Payload keys: {list(payload.keys())}")
        print(f"🚀 Image data URL length: {len(image_data_url)}")
        
        try:
            response = requests.post(self.base_url, headers=self.headers, json=payload)
            print(f"🚀 Response status: {response.status_code}")
            print(f"🚀 Response headers: {dict(response.headers)}")
            
            response.raise_for_status()
            response_data = response.json()
            print(f"🚀 Response data keys: {list(response_data.keys())}")
            
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
                        if 'supplier' in cleaned_data:
                            print(f"🔍 Supplier Data: {cleaned_data['supplier']}")
                        if 'buyer' in cleaned_data:
                            print(f"🔍 Buyer Data: {cleaned_data['buyer']}")
                        if 'invoice_details' in cleaned_data:
                            print(f"🔍 Invoice Details: {cleaned_data['invoice_details']}")
                        
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
        print("🔄 Parsing markdown response as fallback...")
        
        extracted_data = {
            "supplier": {"name": None, "address": None, "contact": {"phone": None, "email": None}},
            "buyer": {"name": None, "address": None, "contact": {"phone": None, "email": None}},
            "invoice_details": {"invoice_number": None, "date": None, "due_date": None, "order_number": None, "reference": None},
            "items": [],
            "totals": {"subtotal": None, "shipping_handling": None, "tax": None, "discount_amount": None, "total_amount": None},
            "shipping": {"method": None, "delivery_terms": None, "tracking_number": None, "delivery_date": None},
            "payment_terms": {"method": None, "terms": None, "due_date": None},
            "currency": None,
            "document_type": "invoice",
            "extraction_confidence": "medium"
        }
        
        # Extract supplier information
        supplier_match = re.search(r'\*\*Supplier Information\*\*\s*\*\s*Name:\s*([^*\n]+)', text_content, re.IGNORECASE)
        if supplier_match:
            extracted_data["supplier"]["name"] = supplier_match.group(1).strip()
        
        supplier_addr_match = re.search(r'\*\s*Address:\s*([^*\n]+)', text_content, re.IGNORECASE)
        if supplier_addr_match:
            extracted_data["supplier"]["address"] = supplier_addr_match.group(1).strip()
        
        # Extract buyer information
        buyer_match = re.search(r'\*\*Buyer Information\*\*\s*\*\s*Name:\s*([^*\n]+)', text_content, re.IGNORECASE)
        if buyer_match:
            extracted_data["buyer"]["name"] = buyer_match.group(1).strip()
        
        buyer_addr_match = re.search(r'\*\s*Address:\s*([^*\n]+)', text_content, re.IGNORECASE)
        if buyer_addr_match:
            extracted_data["buyer"]["address"] = buyer_addr_match.group(1).strip()
        
        # Extract invoice details
        invoice_num_match = re.search(r'\*\s*Invoice Number:\s*([^*\n]+)', text_content, re.IGNORECASE)
        if invoice_num_match:
            extracted_data["invoice_details"]["invoice_number"] = invoice_num_match.group(1).strip()
        
        date_match = re.search(r'\*\s*Date:\s*([^*\n]+)', text_content, re.IGNORECASE)
        if date_match:
            extracted_data["invoice_details"]["date"] = date_match.group(1).strip()
        
        order_num_match = re.search(r'\*\s*Order Number:\s*([^*\n]+)', text_content, re.IGNORECASE)
        if order_num_match:
            extracted_data["invoice_details"]["order_number"] = order_num_match.group(1).strip()
        
        # Extract totals
        total_match = re.search(r'\*\s*Total Amount:\s*\$?([^*\n]+)', text_content, re.IGNORECASE)
        if total_match:
            total_str = total_match.group(1).strip()
            # Clean up the amount
            total_str = re.sub(r'[^\d.]', '', total_str)
            try:
                extracted_data["totals"]["total_amount"] = float(total_str)
            except ValueError:
                extracted_data["totals"]["total_amount"] = total_str
        
        # Extract currency
        currency_match = re.search(r'\*\s*Currency\*\*:\s*([^*\n]+)', text_content, re.IGNORECASE)
        if currency_match:
            extracted_data["currency"] = currency_match.group(1).strip()
        
        # Extract items
        items_section = re.search(r'\*\*Items\*\*.*?\*\s*Description:\s*([^*\n]+)', text_content, re.DOTALL | re.IGNORECASE)
        if items_section:
            description = items_section.group(1).strip()
            quantity_match = re.search(r'\*\s*Quantity:\s*(\d+)', text_content, re.IGNORECASE)
            quantity = int(quantity_match.group(1)) if quantity_match else 1
            
            unit_price_match = re.search(r'\*\s*Unit Price:\s*\$?([^*\n]+)', text_content, re.IGNORECASE)
            unit_price = None
            if unit_price_match:
                price_str = unit_price_match.group(1).strip()
                price_str = re.sub(r'[^\d.]', '', price_str)
                try:
                    unit_price = float(price_str)
                except ValueError:
                    unit_price = price_str
            
            total_price_match = re.search(r'\*\s*Total Price:\s*\$?([^*\n]+)', text_content, re.IGNORECASE)
            total_price = None
            if total_price_match:
                price_str = total_price_match.group(1).strip()
                price_str = re.sub(r'[^\d.]', '', price_str)
                try:
                    total_price = float(price_str)
                except ValueError:
                    total_price = price_str
            
            extracted_data["items"].append({
                "description": description,
                "quantity": quantity,
                "unit_price": unit_price,
                "total_price": total_price,
                "sku": None
            })
        
        print(f"🔍 Markdown parsing completed. Extracted {len([k for k, v in extracted_data.items() if v])} fields")
        return extracted_data

    def _clean_extracted_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Clean and validate the extracted data"""
        cleaned = {}
        
        # Clean supplier information
        if 'supplier' in data:
            cleaned['supplier'] = {}
            supplier_data = data['supplier']
            
            # Handle basic supplier fields
            for field in ['name', 'address']:
                if field in supplier_data and supplier_data[field]:
                    cleaned['supplier'][field] = str(supplier_data[field]).strip()
            
            # Handle nested contact information
            if 'contact' in supplier_data and isinstance(supplier_data['contact'], dict):
                cleaned['supplier']['contact'] = self._clean_entity_data(supplier_data['contact'])
            elif any(field in supplier_data for field in ['phone', 'email']):
                # Handle flat structure - move phone/email to nested contact
                cleaned['supplier']['contact'] = {}
                for field in ['phone', 'email']:
                    if field in supplier_data and supplier_data[field]:
                        cleaned['supplier']['contact'][field] = str(supplier_data[field]).strip()
        
        # Clean buyer information
        if 'buyer' in data:
            cleaned['buyer'] = {}
            buyer_data = data['buyer']
            
            # Handle basic buyer fields
            for field in ['name', 'address']:
                if field in buyer_data and buyer_data[field]:
                    cleaned['buyer'][field] = str(buyer_data[field]).strip()
            
            # Handle nested contact information
            if 'contact' in buyer_data and isinstance(buyer_data['contact'], dict):
                cleaned['buyer']['contact'] = self._clean_entity_data(buyer_data['contact'])
            elif any(field in buyer_data for field in ['phone', 'email']):
                # Handle flat structure - move phone/email to nested contact
                cleaned['buyer']['contact'] = {}
                for field in ['phone', 'email']:
                    if field in buyer_data and buyer_data[field]:
                        cleaned['buyer']['contact'][field] = str(buyer_data[field]).strip()
        
        # Clean invoice details
        if 'invoice_details' in data:
            cleaned['invoice_details'] = self._clean_entity_data(data['invoice_details'])
        
        # Clean line items
        if 'items' in data and isinstance(data['items'], list):
            cleaned['items'] = []
            for item in data['items']:
                if isinstance(item, dict):
                    cleaned_item = self._clean_entity_data(item)
                    # Ensure numeric fields are properly formatted
                    for field in ['quantity', 'unit_price', 'total_price']:
                        if field in cleaned_item and cleaned_item[field]:
                            try:
                                cleaned_item[field] = float(str(cleaned_item[field]).replace(',', ''))
                            except (ValueError, TypeError):
                                cleaned_item[field] = None
                    cleaned['items'].append(cleaned_item)
        
        # Clean totals
        if 'totals' in data:
            cleaned['totals'] = self._clean_entity_data(data['totals'])
            # Ensure numeric fields are properly formatted
            for field in ['subtotal', 'shipping_handling', 'tax', 'discount_amount', 'total_amount']:
                if field in cleaned['totals'] and cleaned['totals'][field]:
                    try:
                        cleaned['totals'][field] = float(str(cleaned['totals'][field]).replace(',', ''))
                    except (ValueError, TypeError):
                        cleaned['totals'][field] = None
        
        # Clean shipping
        if 'shipping' in data:
            cleaned['shipping'] = self._clean_entity_data(data['shipping'])
        
        # Clean payment terms
        if 'payment_terms' in data:
            cleaned['payment_terms'] = self._clean_entity_data(data['payment_terms'])
        
        # Add other top-level fields
        for field in ['currency', 'document_type', 'extraction_confidence']:
            if field in data and data[field]:
                cleaned[field] = data[field]
        
        return cleaned

    def _clean_entity_data(self, entity_data: Dict[str, Any]) -> Dict[str, Any]:
        """Clean individual entity data"""
        if not isinstance(entity_data, dict):
            return {}
        
        cleaned = {}
        for key, value in entity_data.items():
            if value is not None and value != "" and str(value).strip():
                # Clean string values
                if isinstance(value, str):
                    cleaned_value = value.strip()
                    if cleaned_value.lower() in ['null', 'none', 'n/a', '']:
                        continue
                    cleaned[key] = cleaned_value
                else:
                    cleaned[key] = value
        
        return cleaned

    def save_results(self, data: Dict[str, Any], output_dir: Path = None) -> Path:
        """Save extracted results to JSON file"""
        if output_dir is None:
            output_dir = Path("extracted_invoices")
        
        output_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"invoice_extract_{timestamp}.json"
        filepath = output_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Results saved to: {filepath}")
        return filepath

    def _save_to_database(self, extracted_data: Dict[str, Any], file_path: Path, 
                         order_number: str, metadata: Dict[str, Any]) -> bool:
        """Save invoice extraction to database"""
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
                document_type="invoice",
                description="Invoice document",
                file_size=file_path.stat().st_size if file_path.exists() else None
            )
            if not document:
                print("❌ Failed to create document record")
                return False
            
            # Save invoice extraction
            extraction = save_invoice_extraction(
                document_id=document["id"],
                order_id=order["id"],
                extracted_data=extracted_data,
                metadata=metadata
            )
            if not extraction:
                print("❌ Failed to save invoice extraction")
                return False
            
            print(f"✅ Successfully saved invoice extraction to database for order {order_number}")
            return True
            
        except Exception as e:
            print(f"❌ Error saving to database: {e}")
            return False

    def print_summary(self, data: Dict[str, Any]):
        """Print extraction summary"""
        print(f"\n✅ Document processed successfully!")
        print(f"📄 Document Type: {data.get('document_type', 'Unknown')}")
        
        # Print key fields
        key_fields = [
            ("supplier_name", data.get('supplier', {}).get('name')),
            ("buyer_name", data.get('buyer', {}).get('name')),
            ("invoice_number", data.get('invoice_details', {}).get('invoice_number')),
            ("total_amount", data.get('totals', {}).get('total_amount')),
            ("currency", data.get('currency'))
        ]
        
        print(f"📊 Key Information Extracted:")
        for field_name, value in key_fields:
            if value and value != 'Not found':
                print(f"   {field_name}: {value}")
        
        # Print items
        items = data.get('items', [])
        if items:
            print(f"📦 Items Found: {len(items)}")
            for i, item in enumerate(items[:3]):  # Show first 3 items
                desc = item.get('description', 'No description')[:50]
                qty = item.get('quantity', 'N/A')
                price = item.get('unit_price', 'N/A')
                print(f"   Item {i+1}: {desc}... (Qty: {qty}, Price: {price})")
            if len(items) > 3:
                print(f"   ... and {len(items) - 3} more items")
        else:
            print("📦 No items found")


# Main execution
def main():
    """Test the invoice extractor"""
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python invoice_extract.py <invoice_file_path>")
        return
    
    file_path = Path(sys.argv[1])
    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        return
    
    try:
        extractor = InvoiceExtractor()
        result = extractor.process_document(file_path)
        
        if result.get('status') == 'error':
            print(f"❌ Extraction failed: {result.get('error')}")
        else:
            extractor.print_summary(result)
            
    except Exception as e:
        print(f"❌ Failed to process document: {e}")


if __name__ == "__main__":
    main()