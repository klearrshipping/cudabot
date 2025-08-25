#!/usr/bin/env python3
"""
document_processor.py
────────────────────
Document processing orchestrator for customs declaration workflow
Handles parallel processing of invoice and bill of lading documents using Claude Sonnet 4 via OpenRouter

Usage:
    python document_processor.py <order_number>
"""

import os
import sys
import asyncio
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import traceback

# Add the root directory to the path for imports
current_dir = Path(__file__).parent
root_dir = current_dir.parent.parent
sys.path.insert(0, str(root_dir))

from orders.models import get_order_by_number, update_order_status
from documents.models import get_documents_by_order, update_document_status

# Configuration print for OpenRouter-based processing
print(f"📋 Document Processor Configuration:")
print(f"   🤖 Processor: Claude Sonnet 4 via OpenRouter")
print(f"   📄 Invoice Processing: OpenRouter API")
print(f"   📋 BOL Processing: OpenRouter API")

class DocumentProcessor:
    def __init__(self):
        self.processed_data_dir = Path("processed_data")
        self.processed_data_dir.mkdir(exist_ok=True)
        
        # Load field mappings from JSON file
        self.field_mappings = self._load_field_mappings()
        
    def _load_field_mappings(self) -> Dict[str, str]:
        """Load ESAD field mappings from field_mapping.json"""
        try:
            mapping_file = Path(__file__).parent.parent / "secondary_processing" / "field_mapping.json"
            with open(mapping_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Extract field mappings from the JSON structure
            mappings = {}
            for field_name, field_info in data.get("field_script_mapping", {}).items():
                output_field = field_info.get("output_field")
                if output_field:
                    mappings[field_name] = output_field
            
            print(f"✅ Loaded {len(mappings)} field mappings from field_mapping.json")
            return mappings
            
        except Exception as e:
            print(f"⚠️ Error loading field mappings: {e}")
            # Fallback to basic mappings
            return {
                'Regime Type': 'regime_type_processed',
                'Commercial reference number': 'commercial_ref_processed',
                'Delivery terms': 'delivery_terms_processed',
                'Nature of Transaction': 'transaction_type_processed',
                'Commodity code': 'commodity_code_processed',
                'Net Weight (kg)': 'net_weight_processed'
            }
    
    def process_order_documents(self, order_number: str) -> Dict[str, Any]:
        """
        Process all documents for a given order number
        
        Args:
            order_number (str): The order number to process
            
        Returns:
            dict: Processing results for all documents
        """
        print(f"🔄 Starting document processing for order: {order_number}")
        
        # Get order information
        order = get_order_by_number(order_number)
        if not order:
            print(f"❌ Order not found: {order_number}")
            return {"error": f"Order not found: {order_number}"}
        
        order_id = order['id']
        
        # Update order status to processing
        update_order_status(order_id, "processing")
        
        # Get documents for this order
        documents = get_documents_by_order(order_id)
        if not documents:
            print(f"❌ No documents found for order: {order_number}")
            update_order_status(order_id, "failed")
            return {"error": f"No documents found for order: {order_number}"}
        
        # Create processed data directory for this order
        order_processed_dir = self.processed_data_dir / "orders" / order_number
        order_processed_dir.mkdir(parents=True, exist_ok=True)
        
        # Process documents in parallel
        processing_results = self._process_documents_parallel(documents, order_processed_dir, order_number)
        
        # Update order status based on results
        successful_docs = sum(1 for result in processing_results.values() if result.get('status') == 'success')
        total_docs = len(processing_results)
        
        # If all documents processed successfully, run eSAD field population
        if successful_docs == total_docs and total_docs > 0:
            print(f"🔄 All documents processed successfully. Starting eSAD field population...")
            
            try:
                esad_result = self._process_esad_fields(order_processed_dir, order_number)
                processing_results['esad_processing'] = esad_result
                
                if esad_result.get('status') == 'success':
                    update_order_status(order_id, "completed")
                    print(f"✅ eSAD field population completed successfully")
                else:
                    update_order_status(order_id, "esad_failed")
                    print(f"⚠️ eSAD field population failed: {esad_result.get('error', 'Unknown error')}")
                    
            except Exception as e:
                print(f"❌ eSAD processing error: {e}")
                processing_results['esad_processing'] = {
                    'status': 'failed',
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                }
                update_order_status(order_id, "esad_failed")
        else:
            update_order_status(order_id, "failed")
        
        print(f"✅ Document processing completed for order: {order_number}")
        return processing_results
    
    def _process_documents_parallel(self, documents: List[Dict], output_dir: Path, order_number: str) -> Dict[str, Any]:
        """
        Process documents in parallel using ThreadPoolExecutor
        
        Args:
            documents (list): List of document records
            output_dir (Path): Directory to save processed results
            order_number (str): Order number for file naming
            
        Returns:
            dict: Processing results for each document
        """
        results = {}
        
        with ThreadPoolExecutor(max_workers=2) as executor:
            # Submit processing tasks
            future_to_doc = {}
            
            for doc in documents:
                doc_type = doc['document_type']
                file_path = doc['file_path']
                
                # Create primary_process directory under order
                primary_process_dir = output_dir / "primary_process"
                primary_process_dir.mkdir(exist_ok=True)
                
                # Submit processing task
                if doc_type == 'invoice':
                    future = executor.submit(self._process_invoice, file_path, primary_process_dir, doc['id'], order_number)
                elif doc_type == 'bill_of_lading':
                    future = executor.submit(self._process_bill_of_lading, file_path, primary_process_dir, doc['id'], order_number)
                else:
                    print(f"⚠️ Unknown document type: {doc_type}")
                    continue
                
                future_to_doc[future] = doc
            
            # Collect results
            for future in as_completed(future_to_doc):
                doc = future_to_doc[future]
                doc_type = doc['document_type']
                
                try:
                    result = future.result()
                    results[doc_type] = result
                    print(f"✅ {doc_type} processing completed")
                    
                    # Update document status
                    if result.get('status') == 'success':
                        update_document_status(doc['id'], 'completed')
                    else:
                        update_document_status(doc['id'], 'failed')
                        
                except Exception as e:
                    print(f"❌ {doc_type} processing failed: {e}")
                    results[doc_type] = {
                        'status': 'failed',
                        'error': str(e),
                        'timestamp': datetime.now().isoformat()
                    }
                    update_document_status(doc['id'], 'failed')
        
        return results
    
    def _process_invoice(self, file_path: str, output_dir: Path, document_id: int, order_number: str) -> Dict[str, Any]:
        """
        Process invoice document using Claude Sonnet 4 via OpenRouter
        """
        try:
            # Update document status to processing
            update_document_status(document_id, 'processing')
            
            # Import the OpenRouter-based invoice extractor
            from modules.primary_processing.invoice_extract import InvoiceExtractor
            
            # Initialize extractor
            extractor = InvoiceExtractor()
            
            # Process invoice
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                raise FileNotFoundError(f"Invoice file not found: {file_path}")
            
            # Extract data (don't save to individual extractor's directory)
            extracted_data = extractor.process_document(file_path_obj, save_to_file=False)
            
            # Check if extraction was successful
            if extracted_data.get('status') == 'failed':
                raise Exception(f"Extraction failed: {extracted_data.get('error', 'Unknown error')}")
            
            # Save extracted data to our output directory with order-specific naming
            extracted_file = output_dir / f"invoice_{order_number}_primary_extract.json"
            with open(extracted_file, 'w', encoding='utf-8') as f:
                json.dump(extracted_data, f, indent=2, ensure_ascii=False)
            
            # Save extracted data to database
            self._save_invoice_extraction_to_db(order_number, document_id, extracted_data)
            
            # Calculate metrics for OpenRouter extraction
            items_count = len(extracted_data.get('items', []))
            
            # Count total extracted fields across all sections
            extracted_fields_count = self._count_extracted_fields(extracted_data)
            
            # Analyze extraction quality
            quality_metrics = self._analyze_extraction_quality(extracted_data)
            
            # Create detailed section status
            sections_extracted = self._get_section_status(extracted_data)
            
            return {
                'status': 'success',
                'document_type': 'invoice',
                'processor_type': 'claude_sonnet_4_via_openrouter',
                'extracted_data_file': str(extracted_file),
                'extracted_fields_count': extracted_fields_count,
                'line_items_count': items_count,
                'structure_version': 'v4_claude_sonnet_openrouter',
                'sections_extracted': sections_extracted,
                'quality_metrics': quality_metrics,
                'extraction_summary': {
                    'supplier_identified': bool(extracted_data.get('supplier', {}).get('name')),
                    'buyer_identified': bool(extracted_data.get('buyer', {}).get('name')),
                    'invoice_number_found': bool(extracted_data.get('invoice_details', {}).get('invoice_number')),
                    'date_found': bool(extracted_data.get('invoice_details', {}).get('date')),
                    'total_amount_found': bool(extracted_data.get('totals', {}).get('total_amount')),
                    'items_extracted': items_count,
                    'currency_detected': extracted_data.get('currency', 'Unknown'),
                    'confidence': extracted_data.get('extraction_confidence', 'unknown')
                },
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"❌ Invoice processing error: {e}")
            traceback.print_exc()
            return {
                'status': 'failed',
                'document_type': 'invoice',
                'processor_type': 'claude_sonnet_4_via_openrouter',
                'error': str(e),
                'error_details': traceback.format_exc(),
                'timestamp': datetime.now().isoformat()
            }
    
    def _count_extracted_fields(self, extracted_data: Dict[str, Any]) -> int:
        """Count extracted fields from OpenRouter extraction structure"""
        field_count = 0
        
        # Count fields in each section
        sections_to_count = [
            'supplier', 'buyer', 'invoice_details', 'shipping', 
            'totals', 'payment_terms'
        ]
        
        for section_name in sections_to_count:
            section_data = extracted_data.get(section_name, {})
            if isinstance(section_data, dict):
                # Count non-empty values recursively
                field_count += self._count_nested_fields(section_data)
        
        # Count currency if present
        if extracted_data.get('currency'):
            field_count += 1
            
        # Count document type if present
        if extracted_data.get('document_type'):
            field_count += 1
        
        return field_count
    
    def _count_nested_fields(self, data: Dict[str, Any]) -> int:
        """Helper method to count nested fields"""
        count = 0
        for key, value in data.items():
            if isinstance(value, dict):
                count += self._count_nested_fields(value)
            elif value and str(value).strip():
                count += 1
        return count
    
    def _get_section_status(self, extracted_data: Dict[str, Any]) -> Dict[str, bool]:
        """Get extraction status for each section (OpenRouter structure)"""
        supplier = extracted_data.get('supplier', {})
        buyer = extracted_data.get('buyer', {})
        invoice_details = extracted_data.get('invoice_details', {})
        items = extracted_data.get('items', [])
        totals = extracted_data.get('totals', {})
        shipping = extracted_data.get('shipping', {})
        payment_terms = extracted_data.get('payment_terms', {})
        
        return {
            'supplier': bool(supplier.get('name')),
            'buyer': bool(buyer.get('name')),
            'invoice_details': bool(invoice_details.get('invoice_number') or invoice_details.get('date')),
            'items': len(items) > 0,
            'totals': bool(totals.get('total_amount')),
            'shipping': bool(shipping.get('method') or shipping.get('delivery_terms')),
            'payment': bool(payment_terms.get('method')),
            'currency': bool(extracted_data.get('currency'))
        }
    
    def _analyze_extraction_quality(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze extraction quality (OpenRouter structure)"""
        # Calculate completeness scores
        supplier = extracted_data.get('supplier', {})
        buyer = extracted_data.get('buyer', {})
        invoice_details = extracted_data.get('invoice_details', {})
        items = extracted_data.get('items', [])
        totals = extracted_data.get('totals', {})
        
        # Essential fields for customs declaration
        essential_fields = {
            'supplier_name': bool(supplier.get('name')),
            'supplier_address': bool(supplier.get('address')),
            'buyer_name': bool(buyer.get('name')),
            'buyer_address': bool(buyer.get('address')),
            'invoice_number': bool(invoice_details.get('invoice_number')),
            'invoice_date': bool(invoice_details.get('date')),
            'total_amount': bool(totals.get('total_amount')),
            'currency': bool(extracted_data.get('currency')),
            'items': len(items) > 0
        }
        
        # Calculate scores
        essential_score = sum(essential_fields.values()) / len(essential_fields)
        
        # Item completeness
        item_completeness = 0
        if items:
            item_fields = ['description', 'quantity', 'unit_price']
            total_item_fields = len(items) * len(item_fields)
            completed_item_fields = sum(
                1 for item in items 
                for field in item_fields 
                if item.get(field) and str(item.get(field)).strip()
            )
            item_completeness = completed_item_fields / total_item_fields if total_item_fields > 0 else 0
        
        # Overall quality score
        overall_score = (essential_score * 0.7) + (item_completeness * 0.3)
        
        return {
            'essential_fields_score': round(essential_score * 100, 1),
            'item_completeness_score': round(item_completeness * 100, 1),
            'overall_quality_score': round(overall_score * 100, 1),
            'essential_fields_status': essential_fields,
            'missing_critical_fields': [
                field for field, present in essential_fields.items() 
                if not present
            ],
            'extraction_confidence': 'high' if overall_score >= 0.8 else 'medium' if overall_score >= 0.6 else 'low'
        }
    
    def _process_bill_of_lading(self, file_path: str, output_dir: Path, document_id: int, order_number: str) -> Dict[str, Any]:
        """
        Process bill of lading document using Claude Sonnet 4 via OpenRouter
        """
        try:
            # Update document status to processing
            update_document_status(document_id, 'processing')
            
            # Import bill of lading extractor
            from modules.primary_processing.bol_extract import FlexibleFormExtractor
            
            # Initialize extractor
            extractor = FlexibleFormExtractor()
            
            # Process bill of lading
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                raise FileNotFoundError(f"Bill of lading file not found: {file_path}")
            
            # Extract data (don't save to individual extractor's directory)
            extracted_data = extractor.process_document(file_path_obj, save_to_file=False)
            
            # Check if extraction was successful
            if extracted_data.get('status') == 'failed':
                raise Exception(f"Extraction failed: {extracted_data.get('error', 'Unknown error')}")
            
            # Save extracted data to our output directory with order-specific naming
            extracted_file = output_dir / f"bill_of_lading_{order_number}_primary_extract.json"
            with open(extracted_file, 'w', encoding='utf-8') as f:
                json.dump(extracted_data, f, indent=2, ensure_ascii=False)
            
            # Save extracted data to database
            self._save_bol_extraction_to_db(order_number, document_id, extracted_data)
            
            # Calculate metrics for bill of lading (OpenRouter structure)
            consignee_found = bool(extracted_data.get('consignee_name'))
            shipper_found = bool(extracted_data.get('shipper'))
            vessel_found = bool(extracted_data.get('vessel'))
            container_found = bool(extracted_data.get('container'))
            charges_count = len(extracted_data.get('charges', []))
            
            return {
                'status': 'success',
                'document_type': 'bill_of_lading',
                'processor_type': 'claude_sonnet_4_via_openrouter',
                'extracted_data_file': str(extracted_file),
                'consignee_found': consignee_found,
                'shipper_found': shipper_found,
                'vessel_found': vessel_found,
                'container_found': container_found,
                'charges_count': charges_count,
                'extraction_summary': {
                    'document_type': extracted_data.get('_metadata', {}).get('document_type', 'Unknown'),
                    'processing_method': extracted_data.get('_metadata', {}).get('processing_method', 'Unknown')
                },
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"❌ Bill of lading processing error: {e}")
            traceback.print_exc()
            return {
                'status': 'failed',
                'document_type': 'bill_of_lading',
                'processor_type': 'claude_sonnet_4_via_openrouter',
                'error': str(e),
                'error_details': traceback.format_exc(),
                'timestamp': datetime.now().isoformat()
            }
    
    def _process_esad_fields(self, output_dir: Path, order_number: str) -> Dict[str, Any]:
        """
        Process eSAD field population using extracted invoice and BOL data
        
        Args:
            output_dir (Path): Directory containing extracted data
            order_number (str): Order number for file naming
            
        Returns:
            dict: eSAD processing results
        """
        try:
            print(f"🔄 Starting eSAD field population for order: {order_number}")
            
            # Import the eSAD primary processor
            from .esad_primary import ESADPrimaryProcessor
            
            # Check if both invoice and BOL files exist
            invoice_file = output_dir / "primary_process" / f"invoice_{order_number}_primary_extract.json"
            bol_file = output_dir / "primary_process" / f"bill_of_lading_{order_number}_primary_extract.json"
            
            if not invoice_file.exists():
                raise FileNotFoundError(f"Invoice extraction file not found: {invoice_file}")
            if not bol_file.exists():
                raise FileNotFoundError(f"Bill of lading extraction file not found: {bol_file}")
            
            # Load extracted data
            with open(invoice_file, 'r', encoding='utf-8') as f:
                invoice_data = json.load(f)
            
            with open(bol_file, 'r', encoding='utf-8') as f:
                bol_data = json.load(f)
            
            # Initialize ESAD primary processor with Mistral Small model
            processor = ESADPrimaryProcessor(model="mistral_small")
            print(f"🤖 Running eSAD field population with Mistral Small model...")
            
            # Get order ID for processing
            order = get_order_by_number(order_number)
            if not order:
                raise ValueError(f"Order not found for order number: {order_number}")
            
            # Process the order using the new API
            esad_result = processor.process_order(order['id'], bol_data, invoice_data)
            
            # The process_order method already handles secondary processing internally
            # and generates the esad_fields.json file
            
            print(f"✅ eSAD field population completed")
            print(f"📊 Fields populated: {esad_result.get('fields_populated', 0)}")
            print(f"📊 Fields saved to DB: {esad_result.get('fields_saved_to_db', 0)}")
            print(f"📄 ESAD fields JSON: {esad_result.get('esad_fields_json_path', 'Not generated')}")
            
            return {
                'status': 'success',
                'processor_type': 'esad_primary_processor_llm_manifest_enhanced',
                'esad_result_file': esad_result.get('esad_fields_json_path', ''),
                'fields_populated': esad_result.get('fields_populated', 0),
                'fields_saved_to_db': esad_result.get('fields_saved_to_db', 0),
                'processing_status': esad_result.get('processing_status', 'unknown'),
                'timestamp': esad_result.get('processing_timestamp', datetime.now().isoformat())
            }
            
        except Exception as e:
            print(f"❌ eSAD field population error: {e}")
            traceback.print_exc()
            return {
                'status': 'failed',
                'processor_type': 'esad_field_populator_mistral_small',
                'error': str(e),
                'error_details': traceback.format_exc(),
                'timestamp': datetime.now().isoformat()
            }
    
    def _ensure_json_serializable(self, obj):
        """
        Ensure an object is JSON serializable by converting custom objects to dictionaries
        
        Args:
            obj: Object to make JSON serializable
            
        Returns:
            JSON serializable object
        """
        try:
            if hasattr(obj, '_asdict'):
                # Convert dataclasses to dictionary
                result = obj._asdict()
                # Recursively process the result to handle nested dataclasses
                return self._ensure_json_serializable(result)
            elif hasattr(obj, '__dict__'):
                # Convert custom objects to dictionary
                result = obj.__dict__
                # Recursively process the result to handle nested objects
                return self._ensure_json_serializable(result)
            elif isinstance(obj, (list, tuple)):
                # Handle lists and tuples
                return [self._ensure_json_serializable(item) for item in obj]
            elif isinstance(obj, dict):
                # Handle dictionaries
                return {key: self._ensure_json_serializable(value) for key, value in obj.items()}
            else:
                # Basic types should be fine
                return obj
        except Exception as e:
            print(f"⚠️ Error in _ensure_json_serializable: {e}")
            # Fallback: try to convert to string
            return str(obj)
    
    def _run_secondary_processing(self, esad_result: Dict[str, Any], bol_data: Dict[str, Any], 
                                 invoice_data: Dict[str, Any], order_number: str) -> Dict[str, Any]:
        """
        Run comprehensive secondary processing steps to enhance ESAD fields
        
        Args:
            esad_result: Initial ESAD field population result
            bol_data: Bill of lading extraction data
            invoice_data: Invoice extraction data
            order_number: Order number for processing
            
        Returns:
            dict: Enhanced ESAD result with secondary processing
        """
        try:
            print(f"🔄 Starting comprehensive secondary processing...")
            enhanced_result = esad_result.copy()
            
            # 1. Address formatting and validation
            try:
                from modules.secondary_processing.esad_address import AddressFormatter
                print(f"📍 Processing address formatting...")
                address_formatter = AddressFormatter()
                
                # Format shipper address
                if bol_data.get('shipper_address'):
                    shipper_address = address_formatter.format_address(bol_data['shipper_address'])
                    if shipper_address:
                        # Convert FormattedAddress to dictionary for JSON serialization
                        enhanced_result['shipper_address_formatted'] = {
                            'original': shipper_address.original,
                            'formatted': shipper_address.formatted,
                            'components': {
                                'street_town': shipper_address.components.street_town,
                                'city': shipper_address.components.city,
                                'state_province_parish': shipper_address.components.state_province_parish,
                                'country': shipper_address.components.country
                            },
                            'confidence': shipper_address.confidence,
                            'issues': shipper_address.issues
                        }
                
                # Format consignee address
                if bol_data.get('consignee_address'):
                    consignee_address = address_formatter.format_address(bol_data['consignee_address'])
                    if consignee_address:
                        # Convert FormattedAddress to dictionary for JSON serialization
                        enhanced_result['consignee_address_formatted'] = {
                            'original': consignee_address.original,
                            'formatted': consignee_address.formatted,
                            'components': {
                                'street_town': consignee_address.components.street_town,
                                'city': consignee_address.components.city,
                                'state_province_parish': consignee_address.components.state_province_parish,
                                'country': consignee_address.components.country
                            },
                            'confidence': consignee_address.confidence,
                            'issues': consignee_address.issues
                        }
                        
                print(f"✅ Address formatting completed")
            except Exception as e:
                print(f"⚠️ Address formatting failed: {e}")
            
            # 2. Package type classification
            try:
                from modules.secondary_processing.esad_pkg import ask_llm_for_best_package_type
                print(f"📦 Processing package type classification...")
                
                if bol_data.get('commodity'):
                    package_type = ask_llm_for_best_package_type(bol_data['commodity'], [])
                    if package_type:
                        enhanced_result['package_type_classified'] = package_type
                        
                print(f"✅ Package type classification completed")
            except Exception as e:
                print(f"⚠️ Package type classification failed: {e}")
            
            # 3. Transaction type classification and regime type determination
            try:
                print(f"💳 Processing transaction type classification and regime type...")
                
                # Get transaction details from invoice
                transaction_details = ""
                if invoice_data.get('items'):
                    transaction_details = " ".join([item.get('description', '') for item in invoice_data['items']])
                
                # Determine regime type based on transaction characteristics
                regime_type = self._determine_regime_type(bol_data, invoice_data, transaction_details)
                if regime_type:
                    enhanced_result['regime_type_determined'] = regime_type
                    # Update the ESAD mandatory fields
                    if 'esad_mandatory_fields' in enhanced_result:
                        if 'declaration_details' not in enhanced_result['esad_mandatory_fields']:
                            enhanced_result['esad_mandatory_fields']['declaration_details'] = {}
                        enhanced_result['esad_mandatory_fields']['declaration_details']['regime_type'] = {
                            'value': regime_type,
                            'source': 'secondary_processing_derived',
                            'confidence': 'high',
                            'box': '1',
                            'field_name': 'Regime Type',
                            'description': 'Code that identifies the model of declaration being presented',
                            'mandatory_type': 'always',
                            'data_type': 'alphanumeric'
                        }
                
                # Determine nature of transaction
                nature_of_transaction = self._determine_nature_of_transaction(bol_data, invoice_data, transaction_details)
                if nature_of_transaction:
                    enhanced_result['nature_of_transaction_determined'] = nature_of_transaction
                    # Update the ESAD mandatory fields
                    if 'esad_mandatory_fields' in enhanced_result:
                        if 'commercial_information' not in enhanced_result['esad_mandatory_fields']:
                            enhanced_result['esad_mandatory_fields']['commercial_information'] = {}
                        enhanced_result['esad_mandatory_fields']['commercial_information']['nature_of_transaction'] = {
                            'value': nature_of_transaction,
                            'source': 'secondary_processing_derived',
                            'confidence': 'high',
                            'box': '24',
                            'field_name': 'Nature of Transaction',
                            'description': 'Type of contract between buyer and seller',
                            'mandatory_type': 'always',
                            'data_type': 'code'
                        }
                        
                print(f"✅ Transaction type classification and regime type determination completed")
            except Exception as e:
                print(f"⚠️ Transaction type classification failed: {e}")
            
            # 4. Country code processing (using available functions)
            try:
                from modules.secondary_processing.esad_country import get_country_data, ask_llm_for_country_iso2
                print(f"🌍 Processing country code classification...")
                
                countries = get_country_data()
                
                # Process shipper country
                if bol_data.get('shipper_address'):
                    # Extract country from address (simple approach)
                    address_lower = bol_data['shipper_address'].lower()
                    if 'united states' in address_lower or 'usa' in address_lower:
                        enhanced_result['shipper_country_code'] = 'US'
                    elif 'jamaica' in address_lower:
                        enhanced_result['shipper_country_code'] = 'JM'
                    elif 'canada' in address_lower:
                        enhanced_result['shipper_country_code'] = 'CA'
                
                # Process consignee country
                if bol_data.get('consignee_address'):
                    address_lower = bol_data['consignee_address'].lower()
                    if 'jamaica' in address_lower:
                        enhanced_result['consignee_country_code'] = 'JM'
                    elif 'united states' in address_lower or 'usa' in address_lower:
                        enhanced_result['consignee_country_code'] = 'US'
                        
                print(f"✅ Country code processing completed")
            except Exception as e:
                print(f"⚠️ Country code processing failed: {e}")
            
            # 5. Weight and measurement processing (enhanced)
            try:
                print(f"⚖️ Processing weight and measurements...")
                
                if bol_data.get('weight'):
                    weight_str = str(bol_data['weight'])
                    # Extract numeric weight value
                    import re
                    weight_match = re.search(r'(\d+\.?\d*)', weight_str)
                    if weight_match:
                        weight_value = float(weight_match.group(1))
                        enhanced_result['weight_kg'] = weight_value
                        
                        # Calculate net weight (estimate 95% of gross weight for packaging)
                        net_weight = weight_value * 0.95
                        enhanced_result['net_weight_kg'] = round(net_weight, 2)
                        
                        # Update ESAD mandatory fields
                        if 'esad_mandatory_fields' in enhanced_result:
                            if 'goods_information' not in enhanced_result['esad_mandatory_fields']:
                                enhanced_result['esad_mandatory_fields']['goods_information'] = {}
                            if 'classification_weights' not in enhanced_result['esad_mandatory_fields']['goods_information']:
                                enhanced_result['esad_mandatory_fields']['goods_information']['classification_weights'] = {}
                            
                            enhanced_result['esad_mandatory_fields']['goods_information']['classification_weights']['net_weight'] = {
                                'value': enhanced_result['net_weight_kg'],
                                'source': 'secondary_processing_calculated',
                                'confidence': 'medium',
                                'box': '38',
                                'field_name': 'Net Weight (kg)',
                                'description': 'Net weight in kilograms without packaging',
                                'mandatory_type': 'always',
                                'data_type': 'decimal'
                            }
                        
                print(f"✅ Weight processing completed")
            except Exception as e:
                print(f"⚠️ Weight processing failed: {e}")
            
            # 6. Commercial reference number extraction
            try:
                print(f"📋 Processing commercial reference number...")
                
                # Try to get order number from invoice
                commercial_ref = None
                if invoice_data.get('invoice_details', {}).get('order_number'):
                    commercial_ref = invoice_data['invoice_details']['order_number']
                elif invoice_data.get('invoice_details', {}).get('invoice_number'):
                    commercial_ref = invoice_data['invoice_details']['invoice_number']
                elif bol_data.get('bill_of_lading'):
                    commercial_ref = bol_data['bill_of_lading']
                
                if commercial_ref:
                    enhanced_result['commercial_reference_determined'] = commercial_ref
                    # Update the ESAD mandatory fields
                    if 'esad_mandatory_fields' in enhanced_result:
                        if 'declaration_details' not in enhanced_result['esad_mandatory_fields']:
                            enhanced_result['esad_mandatory_fields']['declaration_details'] = {}
                        enhanced_result['esad_mandatory_fields']['declaration_details']['commercial_reference_number'] = {
                            'value': commercial_ref,
                            'source': 'secondary_processing_extracted',
                            'confidence': 'high',
                            'box': '7',
                            'field_name': 'Commercial reference number',
                            'description': 'Reference number given by declarant to identify and record this declaration',
                            'mandatory_type': 'always',
                            'data_type': 'alphanumeric'
                        }
                        
                print(f"✅ Commercial reference number processing completed")
            except Exception as e:
                print(f"⚠️ Commercial reference number processing failed: {e}")
            
            # 7. Delivery terms determination
            try:
                print(f"🚢 Processing delivery terms...")
                
                # Determine delivery terms based on invoice and BOL data
                delivery_terms = self._determine_delivery_terms(bol_data, invoice_data)
                if delivery_terms:
                    enhanced_result['delivery_terms_determined'] = delivery_terms
                    # Update the ESAD mandatory fields
                    if 'esad_mandatory_fields' in enhanced_result:
                        if 'transport_information' not in enhanced_result['esad_mandatory_fields']:
                            enhanced_result['esad_mandatory_fields']['transport_information'] = {}
                        enhanced_result['esad_mandatory_fields']['transport_information']['delivery_terms'] = {
                            'value': delivery_terms,
                            'source': 'secondary_processing_derived',
                            'confidence': 'high',
                            'box': '20',
                            'field_name': 'Delivery terms',
                            'description': 'International standard INCOTERMS code',
                            'mandatory_type': 'always',
                            'data_type': 'code'
                        }
                        
                print(f"✅ Delivery terms processing completed")
            except Exception as e:
                print(f"⚠️ Delivery terms processing failed: {e}")
            
            # 8. Commodity code classification
            try:
                print(f"🏷️ Processing commodity code classification...")
                
                # Use LLM to classify commodity code based on description
                commodity_code = self._classify_commodity_code(bol_data, invoice_data)
                if commodity_code:
                    enhanced_result['commodity_code_classified'] = commodity_code
                    # Update the ESAD mandatory fields
                    if 'esad_mandatory_fields' in enhanced_result:
                        if 'goods_information' not in enhanced_result['esad_mandatory_fields']:
                            enhanced_result['esad_mandatory_fields']['goods_information'] = {}
                        if 'classification_weights' not in enhanced_result['esad_mandatory_fields']['goods_information']:
                            enhanced_result['esad_mandatory_fields']['goods_information']['classification_weights'] = {}
                        
                        enhanced_result['esad_mandatory_fields']['goods_information']['classification_weights']['commodity_code'] = {
                            'value': commodity_code,
                            'source': 'secondary_processing_llm_classified',
                            'confidence': 'medium',
                            'box': '33',
                            'field_name': 'Commodity code',
                            'description': 'Tariff code classifying goods according to Jamaica Common External Tariff',
                            'mandatory_type': 'always',
                            'data_type': 'numeric'
                        }
                        
                print(f"✅ Commodity code classification completed")
            except Exception as e:
                print(f"⚠️ Commodity code classification failed: {e}")
            
            # 9. Customs procedure code determination
            try:
                print(f"📋 Processing customs procedure code...")
                
                # Determine procedure code based on transaction type
                procedure_code = self._determine_procedure_code(bol_data, invoice_data)
                if procedure_code:
                    enhanced_result['procedure_code_determined'] = procedure_code
                    # Update the ESAD mandatory fields
                    if 'esad_mandatory_fields' in enhanced_result:
                        if 'goods_information' not in enhanced_result['esad_mandatory_fields']:
                            enhanced_result['esad_mandatory_fields']['goods_information'] = {}
                        if 'procedures_valuation' not in enhanced_result['esad_mandatory_fields']['goods_information']:
                            enhanced_result['esad_mandatory_fields']['goods_information']['procedures_valuation'] = {}
                        
                        enhanced_result['esad_mandatory_fields']['goods_information']['procedures_valuation']['procedure'] = {
                            'value': procedure_code,
                            'source': 'secondary_processing_derived',
                            'confidence': 'high',
                            'box': '37',
                            'field_name': 'Procedure',
                            'description': 'Customs Procedure Code (CPC) and Additional National Codes (ANC)',
                            'mandatory_type': 'always',
                            'data_type': 'alphanumeric'
                        }
                        
                print(f"✅ Customs procedure code processing completed")
            except Exception as e:
                print(f"⚠️ Customs procedure code processing failed: {e}")
            
            print(f"✅ Comprehensive secondary processing completed")
            return enhanced_result
            
        except Exception as e:
            print(f"❌ Secondary processing error: {e}")
            # Return original result if secondary processing fails
            return esad_result
    
    def _determine_regime_type(self, bol_data: Dict[str, Any], invoice_data: Dict[str, Any], transaction_details: str) -> str:
        """Determine regime type based on transaction characteristics"""
        try:
            # Check if this is a commercial import (most common)
            if bol_data.get('shipper') and invoice_data.get('supplier', {}).get('name'):
                # Commercial import with supplier and buyer
                return "40"  # Standard import declaration
            
            # Check if this is a personal import
            if bol_data.get('consignee_name') and not invoice_data.get('supplier', {}).get('name'):
                # Personal import without commercial supplier
                return "42"  # Personal effects import
            
            # Default to standard import
            return "40"
        except Exception as e:
            print(f"⚠️ Error determining regime type: {e}")
            return "40"  # Default fallback
    
    def _determine_nature_of_transaction(self, bol_data: Dict[str, Any], invoice_data: Dict[str, Any], transaction_details: str) -> str:
        """Determine nature of transaction based on invoice and BOL data"""
        try:
            # Check if this is a sale/purchase
            if invoice_data.get('supplier', {}).get('name') and invoice_data.get('buyer', {}).get('name'):
                return "1"  # Sale/purchase
            
            # Check if this is a gift
            if 'gift' in transaction_details.lower() or 'donation' in transaction_details.lower():
                return "2"  # Gift
            
            # Check if this is personal effects
            if bol_data.get('consignee_name') and not invoice_data.get('supplier', {}).get('name'):
                return "3"  # Personal effects
            
            # Default to sale/purchase
            return "1"
        except Exception as e:
            print(f"⚠️ Error determining nature of transaction: {e}")
            return "1"  # Default fallback
    
    def _determine_delivery_terms(self, bol_data: Dict[str, Any], invoice_data: Dict[str, Any]) -> str:
        """Determine delivery terms based on invoice and BOL data"""
        try:
            # Check if freight charges are included in invoice
            invoice_total = invoice_data.get('totals', {}).get('total_amount', 0)
            freight_charges = invoice_data.get('totals', {}).get('freight_amount', 0)
            
            # If freight is included in invoice total, likely CIF
            if freight_charges and freight_charges > 0:
                return "CIF"  # Cost, Insurance, and Freight
            
            # If no freight in invoice but BOL has freight charges, likely FOB
            if bol_data.get('charges') and any('FREIGHT' in str(charge).upper() for charge in bol_data['charges']):
                return "FOB"  # Free On Board
            
            # Default based on common import patterns
            return "CIF"  # Most common for imports to Jamaica
        except Exception as e:
            print(f"⚠️ Error determining delivery terms: {e}")
            return "CIF"  # Default fallback
    
    def _classify_commodity_code(self, bol_data: Dict[str, Any], invoice_data: Dict[str, Any]) -> str:
        """Classify commodity code using LLM based on description"""
        try:
            # Get commodity description
            commodity_desc = ""
            if bol_data.get('commodity'):
                commodity_desc = bol_data['commodity']
            elif invoice_data.get('items'):
                commodity_desc = " ".join([item.get('description', '') for item in invoice_data['items']])
            
            if not commodity_desc:
                return None
            
            # Use LLM to classify (simplified approach for now)
            # In a full implementation, this would call the LLM API
            commodity_lower = commodity_desc.lower()
            
            # Simple rule-based classification for common items
            if 'solar' in commodity_lower or 'generator' in commodity_lower:
                return "8504.40.00"  # Solar generators
            elif 'battery' in commodity_lower or 'power station' in commodity_lower:
                return "8507.60.00"  # Lithium batteries
            elif 'panel' in commodity_lower and 'solar' in commodity_lower:
                return "8541.40.00"  # Solar panels
            
            # Default to a general electrical equipment code
            return "8504.40.00"
        except Exception as e:
            print(f"⚠️ Error classifying commodity code: {e}")
            return None
    
    def _determine_procedure_code(self, bol_data: Dict[str, Any], invoice_data: Dict[str, Any]) -> str:
        """Determine customs procedure code based on transaction type"""
        try:
            # Standard import procedure
            return "4000"  # Standard import for home use
        except Exception as e:
            print(f"⚠️ Error determining procedure code: {e}")
            return "4000"  # Default fallback
    
    def retry_failed_document(self, document_id: int) -> Dict[str, Any]:
        """
        Retry processing a failed document
        
        Args:
            document_id (int): Document ID to retry
            
        Returns:
            dict: Retry results
        """
        # Get document information
        from documents.models import get_document_by_id
        
        document = get_document_by_id(document_id)
        if not document:
            return {"error": f"Document not found: {document_id}"}
        
        # Get order information
        order = get_order_by_number(document['order_id'])
        if not order:
            return {"error": f"Order not found for document: {document_id}"}
        
        # Create output directory
        order_processed_dir = self.processed_data_dir / "orders" / order['order_number']
        primary_process_dir = order_processed_dir / "primary_process"
        primary_process_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"🔄 Retrying processing for document ID: {document_id} ({document['document_type']})")
        
        # Retry processing
        if document['document_type'] == 'invoice':
            result = self._process_invoice(document['file_path'], primary_process_dir, document_id, order['order_number'])
        elif document['document_type'] == 'bill_of_lading':
            result = self._process_bill_of_lading(document['file_path'], primary_process_dir, document_id, order['order_number'])
        else:
            return {"error": f"Unknown document type: {document['document_type']}"}
        
        # Update document status based on retry result
        if result.get('status') == 'success':
            update_document_status(document_id, 'completed')
            print(f"✅ Retry successful for document ID: {document_id}")
            
            # Check if we should trigger eSAD processing after successful retry
            # Get all documents for this order to see if both invoice and BOL are now complete
            order_documents = get_documents_by_order(order['id'])
            completed_docs = [doc for doc in order_documents if doc['status'] == 'completed']
            
            if len(completed_docs) == 2:  # Both invoice and BOL completed
                print(f"🔄 Both documents now complete. Triggering eSAD field population...")
                try:
                    esad_result = self._process_esad_fields(order_processed_dir, order['order_number'])
                    if esad_result.get('status') == 'success':
                        print(f"✅ eSAD field population completed after retry")
                    else:
                        print(f"⚠️ eSAD field population failed after retry: {esad_result.get('error', 'Unknown error')}")
                except Exception as e:
                    print(f"❌ eSAD processing error after retry: {e}")
        else:
            update_document_status(document_id, 'failed')
            print(f"❌ Retry failed for document ID: {document_id}")
        
        return result
    
    def process_esad_for_order(self, order_number: str) -> Dict[str, Any]:
        """
        Manually trigger eSAD field population for an order
        
        Args:
            order_number (str): The order number to process
            
        Returns:
            dict: eSAD processing results
        """
        print(f"🔄 Manually triggering eSAD field population for order: {order_number}")
        
        # Get order information
        order = get_order_by_number(order_number)
        if not order:
            return {"error": f"Order not found: {order_number}"}
        
        # Create processed data directory for this order
        order_processed_dir = self.processed_data_dir / "orders" / order_number
        
        if not order_processed_dir.exists():
            return {"error": f"No processed data directory found for order: {order_number}"}
        
        # Process eSAD fields
        try:
            esad_result = self._process_esad_fields(order_processed_dir, order_number)
            
            if esad_result.get('status') == 'success':
                print(f"✅ Manual eSAD field population completed successfully")
            else:
                print(f"⚠️ Manual eSAD field population failed: {esad_result.get('error', 'Unknown error')}")
            
            return esad_result
            
        except Exception as e:
            print(f"❌ Manual eSAD processing error: {e}")
            return {
                'status': 'failed',
                'processor_type': 'manual_esad_field_populator',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def get_processing_summary(self, order_number: str) -> Dict[str, Any]:
        """
        Get a summary of processing results for an order
        
        Args:
            order_number (str): The order number to summarize
            
        Returns:
            dict: Processing summary
        """
        order_processed_dir = self.processed_data_dir / "orders" / order_number / "primary_process"
        
        if not order_processed_dir.exists():
            return {"error": f"No processing data found for order: {order_number}"}
        
        summary = {
            "order_number": order_number,
            "processing_date": datetime.now().isoformat(),
            "documents_processed": [],
            "overall_status": "unknown"
        }
        
        # Check for processed files
        processed_files = list(order_processed_dir.glob("*_primary_extract.json"))
        esad_files = list(order_processed_dir.glob("*_populated_fields.json"))
        
        for file_path in processed_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                doc_type = "unknown"
                if "invoice" in file_path.name:
                    doc_type = "invoice"
                elif "bill_of_lading" in file_path.name:
                    doc_type = "bill_of_lading"
                
                doc_summary = {
                    "document_type": doc_type,
                    "file_path": str(file_path),
                    "extraction_successful": True
                }
                
                # Add document-specific summary
                if doc_type == "invoice":
                    doc_summary.update({
                        "items_count": len(data.get('items', [])),
                        "supplier_found": bool(data.get('supplier', {}).get('name')),
                        "buyer_found": bool(data.get('buyer', {}).get('name')),
                        "total_amount": data.get('totals', {}).get('total_amount'),
                        "currency": data.get('currency'),
                        "confidence": data.get('extraction_confidence', 'unknown')
                    })
                elif doc_type == "bill_of_lading":
                    doc_summary.update({
                        "vessel_found": bool(data.get('vessel')),
                        "shipper_found": bool(data.get('shipper')),
                        "consignee_found": bool(data.get('consignee_name')),
                        "container_found": bool(data.get('container')),
                        "charges_count": len(data.get('charges', [])),
                        "document_type": data.get('_metadata', {}).get('document_type', 'Unknown')
                    })
                
                summary["documents_processed"].append(doc_summary)
                
            except Exception as e:
                print(f"⚠️ Error reading processed file {file_path}: {e}")
                summary["documents_processed"].append({
                    "document_type": "unknown",
                    "file_path": str(file_path),
                    "extraction_successful": False,
                    "error": str(e)
                })
        
        # Add eSAD processing summary
        summary["esad_processing"] = {}
        for esad_file in esad_files:
            try:
                with open(esad_file, 'r', encoding='utf-8') as f:
                    esad_data = json.load(f)
                
                summary["esad_processing"].update({
                    "esad_file": str(esad_file),
                    "field_coverage": esad_data.get('data_quality', {}).get('field_coverage', 'N/A'),
                    "ready_for_submission": esad_data.get('data_quality', {}).get('ready_for_submission', False),
                    "missing_mandatory_fields": esad_data.get('data_quality', {}).get('missing_mandatory_fields', []),
                    "data_quality_issues": esad_data.get('data_quality', {}).get('data_quality_issues', []),
                    "recommendations": esad_data.get('data_quality', {}).get('recommendations', [])
                })
                
            except Exception as e:
                print(f"⚠️ Error reading eSAD file {esad_file}: {e}")
                summary["esad_processing"] = {
                    "error": str(e)
                }
        
        # Determine overall status
        if not summary["documents_processed"]:
            summary["overall_status"] = "no_documents"
        elif all(doc.get("extraction_successful", False) for doc in summary["documents_processed"]):
            # Check if eSAD processing was successful
            if summary["esad_processing"] and not summary["esad_processing"].get("error"):
                summary["overall_status"] = "success_with_esad"
            else:
                summary["overall_status"] = "success"
        elif any(doc.get("extraction_successful", False) for doc in summary["documents_processed"]):
            summary["overall_status"] = "partial_success"
        else:
            summary["overall_status"] = "failed"
        
        return summary
    
    def _save_invoice_extraction_to_db(self, order_number: str, document_id: int, extracted_data: Dict[str, Any]) -> bool:
        """Save invoice extraction data to database"""
        try:
            # Import database functions
            from orders.models import get_order_by_number
            from modules.core.supabase_client import get_supabase_client
            
            # Get order ID
            order = get_order_by_number(order_number)
            if not order:
                print(f"❌ Cannot save invoice extraction - order not found: {order_number}")
                return False
            
            # Get Supabase client
            supabase = get_supabase_client()
            
            # Prepare data for database
            invoice_data = {
                'order_id': order['id'],
                'document_id': document_id,
                'invoice_number': extracted_data.get('invoice_details', {}).get('invoice_number'),
                'invoice_date': extracted_data.get('invoice_details', {}).get('date'),
                'seller_name': extracted_data.get('supplier', {}).get('name'),
                'seller_address': extracted_data.get('supplier', {}).get('address'),
                'buyer_name': extracted_data.get('buyer', {}).get('name'),
                'buyer_address': extracted_data.get('buyer', {}).get('address'),
                'currency': extracted_data.get('currency'),
                'total_amount': extracted_data.get('totals', {}).get('total_amount'),
                'subtotal': extracted_data.get('totals', {}).get('subtotal'),
                'tax_amount': extracted_data.get('totals', {}).get('tax_amount'),
                'freight_amount': extracted_data.get('totals', {}).get('freight_amount'),
                'insurance_amount': extracted_data.get('totals', {}).get('insurance_amount'),
                'order_number': extracted_data.get('invoice_details', {}).get('order_number'),
                'extraction_timestamp': datetime.now().isoformat(),
                'processor': 'claude_sonnet_4_via_openrouter',
                'model': 'claude_sonnet_4',
                'processing_method': 'openrouter_api',
                'confidence_score': self._normalize_confidence_score(extracted_data.get('extraction_confidence', 0.8)),
                'extraction_status': 'success',
                'raw_extraction_data': extracted_data,
                'product_details': extracted_data.get('items', [])
            }
            
            # Insert into database
            result = supabase.table('invoice_extractions').insert(invoice_data).execute()
            
            if result.data:
                print(f"✅ Saved invoice extraction to database with ID: {result.data[0]['id']}")
                print(f"📊 Invoice Data Saved:")
                print(f"   • Invoice Number: {invoice_data['invoice_number']}")
                print(f"   • Seller: {invoice_data['seller_name']}")
                print(f"   • Buyer: {invoice_data['buyer_name']}")
                print(f"   • Total Amount: {invoice_data['currency']} {invoice_data['total_amount']}")
                print(f"   • Items: {len(invoice_data['product_details'])}")
                return True
            else:
                print("❌ Failed to save invoice extraction to database")
                return False
                
        except Exception as e:
            print(f"❌ Error saving invoice extraction to database: {e}")
            return False
     
    def _save_esad_results_to_db(self, order_number: str, esad_result: Dict[str, Any]) -> bool:
        """Save ESAD processing results to database"""
        try:
            # Import database functions
            from orders.models import get_order_by_number
            from modules.core.supabase_client import get_supabase_client
            
            # Get order ID
            order = get_order_by_number(order_number)
            if not order:
                print(f"❌ Cannot save ESAD results - order not found: {order_number}")
                return False
            
            # Save to esad_fields_processed table with all secondary processing data
            fields_saved = self._save_to_esad_fields_processed(order['id'], esad_result)
            
            if fields_saved:
                print(f"✅ Saved ESAD fields to esad_fields_processed table")
                print(f"📊 ESAD Data Saved:")
                print(f"   • Fields saved: {fields_saved}")
                return True
            else:
                print("⚠️ No ESAD fields saved to esad_fields_processed table")
                return False
                 
        except Exception as e:
            print(f"❌ Error saving ESAD results to database: {e}")
            return False
    
    def _save_to_esad_fields_processed(self, order_id: int, esad_result: Dict[str, Any]) -> bool:
        """Save all ESAD fields and secondary processing data to esad_fields_processed table"""
        try:
            # Get Supabase client
            from modules.core.supabase_client import get_supabase_client
            supabase = get_supabase_client()
            
            # Prepare the record for the esad_fields_processed table
            processed_record = {
                'order_id': order_id,
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            
            # 1. Process ESAD mandatory fields
            if "esad_mandatory_fields" in esad_result:
                self._map_esad_fields_to_columns(esad_result["esad_mandatory_fields"], processed_record)
            
            # 2. Process ESAD optional fields if they exist
            if "esad_optional_fields" in esad_result:
                self._map_esad_fields_to_columns(esad_result["esad_optional_fields"], processed_record)
            
            # 3. Process secondary processing enhancements
            self._map_secondary_processing_to_columns(esad_result, processed_record)
            
            # 4. Handle any top-level fields that might not be in the nested structure
            for key, value in esad_result.items():
                if key not in ['_metadata', 'error', 'data_quality', 'esad_mandatory_fields', 'esad_optional_fields']:
                    if value is not None and str(value).strip():
                        # Skip complex fields that require special handling for now
                        # We'll handle these in a future update when the table schema is finalized
                        pass
            
            # Insert into the esad_fields_processed table
            result = supabase.table('esad_fields_processed').insert(processed_record).execute()
            
            if result.data:
                print(f"✅ Saved ESAD fields to esad_fields_processed table for order {order_id}")
                return True
            else:
                print("❌ Failed to save ESAD fields to esad_fields_processed table")
                return False
                
        except Exception as e:
            print(f"❌ Error saving to esad_fields_processed table: {e}")
            return False
    
    def _map_secondary_processing_to_columns(self, esad_result: Dict[str, Any], processed_record: Dict[str, Any]):
        """Map secondary processing enhancements to columns"""
        try:
            # Map to ACTUAL columns that exist in the database
            
            # Package type classification
            if 'package_type_classified' in esad_result:
                processed_record['package_type_processed'] = esad_result['package_type_classified']
            
            # Country codes - map to existing columns
            if 'shipper_country_code' in esad_result:
                processed_record['origin_country_processed'] = esad_result['shipper_country_code']
            
            if 'consignee_country_code' in esad_result:
                processed_record['last_consignment_country_processed'] = esad_result['consignee_country_code']
            
            # Weight processing - map to existing columns
            if 'weight_kg' in esad_result:
                processed_record['gross_weight_processed'] = esad_result['weight_kg']
            
            if 'net_weight_kg' in esad_result:
                processed_record['net_weight_processed'] = esad_result['net_weight_kg']
            
            # Secondary processing determinations - map to existing columns
            if 'regime_type_determined' in esad_result:
                processed_record['regime_type_processed'] = esad_result['regime_type_determined']
            
            if 'nature_of_transaction_determined' in esad_result:
                processed_record['transaction_type_processed'] = esad_result['nature_of_transaction_determined']
            
            if 'delivery_terms_determined' in esad_result:
                processed_record['delivery_terms_processed'] = esad_result['delivery_terms_determined']
            
            if 'commodity_code_classified' in esad_result:
                processed_record['commodity_code_processed'] = esad_result['commodity_code_classified']
            
            if 'commercial_reference_determined' in esad_result:
                processed_record['commercial_ref_processed'] = esad_result['commercial_reference_determined']
            
            # Set standard values for required columns
            processed_record['processing_status'] = 'completed'
            processed_record['validation_status'] = 'unvalidated'
            
        except Exception as e:
            print(f"⚠️ Error mapping secondary processing to columns: {e}")
    
    def _map_esad_fields_to_columns(self, section_data: Dict[str, Any], esad_record: Dict[str, Any]):
        """Map ESAD fields from nested structure to column names"""
        
        # Get valid columns to prevent database errors
        valid_columns = self._get_valid_esad_columns()
        
        # Fields that are computation steps, not actual ESAD fields - should be ignored
        computation_fields = {
            'Bill of Lading Charges',
            'Excluded Charges (JMD)',
            'Invoice Amount',  # Redundant with Amount field
            'Statistical Units',
            'V.M. (Valuation Method)'
        }
        
        def process_nested_section(section):
            if isinstance(section, dict):
                for key, value in section.items():
                    if isinstance(value, dict) and "value" in value:
                        # This is a field with metadata (value, box, field_name, etc.)
                        field_value = value.get("value")
                        field_name = value.get("field_name", key)
                        
                        # Skip fields with no value
                        if field_value is None or str(field_value).strip() == "":
                            continue
                        
                        # Skip computation fields that aren't actual ESAD fields
                        if field_name in computation_fields:
                            continue
                        
                        # Map field name to column name - all fields should be mapped
                        column_name = self._get_column_name_for_field(field_name)
                        if column_name and column_name in valid_columns:
                            esad_record[column_name] = field_value
                        else:
                            # Only warn for actual ESAD fields that should be mapped
                            if field_name not in computation_fields:
                                print(f"⚠️ Field '{field_name}' not mapped to any column - check mapping configuration")
                    else:
                        # Recursively process nested sections
                        process_nested_section(value)
        
        process_nested_section(section_data)
    
    def _get_valid_esad_columns(self):
        """Get list of valid columns that exist in esad_fields_processed table"""
        # Base columns that always exist
        base_columns = {
            'id', 'order_id', 'created_at', 'updated_at',
            'processing_status', 'validation_status', 'processed_at'
        }
        
        # Add all mapped columns from field_mapping.json
        mapped_columns = set(self.field_mappings.values())
        
        # Combine base and mapped columns
        all_columns = base_columns.union(mapped_columns)
        
        print(f"✅ Valid columns: {len(all_columns)} total ({len(mapped_columns)} mapped from JSON)")
        return all_columns
    
    def _save_individual_esad_fields(self, order_id: int, esad_result: Dict[str, Any]) -> bool:
        """Save individual ESAD fields to esad_fields table with column-based structure"""
        try:
            # Get Supabase client
            from modules.core.supabase_client import get_supabase_client
            supabase = get_supabase_client()
            
            # Prepare the record for the column-based structure
            esad_record = {
                'order_id': order_id,
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            
            # Process ESAD mandatory fields and map to columns
            if "esad_mandatory_fields" in esad_result:
                self._map_esad_fields_to_columns(esad_result["esad_mandatory_fields"], esad_record)
            
            # Process ESAD optional fields if they exist
            if "esad_optional_fields" in esad_result:
                self._map_esad_fields_to_columns(esad_result["esad_optional_fields"], esad_record)
            
            # Handle any top-level fields that might not be in the nested structure
            for key, value in esad_result.items():
                if key not in ['_metadata', 'error', 'data_quality', 'esad_mandatory_fields', 'esad_optional_fields']:
                    if value is not None and str(value).strip():
                        # Handle complex fields with special normalization
                        if key == 'total_amount' and isinstance(value, dict):
                            self._map_total_amount_to_columns(value, esad_record)
            
            # Insert into the esad_fields table
            result = supabase.table('esad_fields').insert(esad_record).execute()
            
            if result.data:
                print(f"✅ Saved ESAD fields to esad_fields table for order {order_id}")
                return True
            else:
                print("❌ Failed to save ESAD fields to esad_fields table")
                return False
                
        except Exception as e:
            print(f"❌ Error saving individual ESAD fields to database: {e}")
            return False
    
    def _map_total_amount_to_columns(self, total_amount_data: Dict[str, Any], esad_record: Dict[str, Any]):
        """Map total_amount complex field to individual columns"""
        
        # Extract invoice amount - map to existing column
        if 'invoice' in total_amount_data and 'amount' in total_amount_data['invoice']:
            esad_record['amount_processed'] = total_amount_data['invoice']['amount']
        
        # Extract currency - map to existing column
        if 'invoice' in total_amount_data and 'currency' in total_amount_data['invoice']:
            esad_record['currency_code_processed'] = total_amount_data['invoice']['currency']
    
    def _get_column_name_for_field(self, field_name: str) -> str:
        """Map ESAD field names to database column names using field_mapping.json"""
        
        # Use the loaded field mappings from JSON file
        return self.field_mappings.get(field_name)
    
    def _determine_field_type(self, field_name: str, field_value: Any) -> str:
        """Determine the data type for a field"""
        if isinstance(field_value, (int, float)):
            return "number"
        elif field_name in ["currency"]:
            return "currency"
        elif "date" in field_name.lower():
            return "date"
        elif "amount" in field_name.lower() or "price" in field_name.lower():
            return "amount"
        elif "weight" in field_name.lower():
            return "weight"
        elif "count" in field_name.lower() or "quantity" in field_name.lower():
            return "count"
        else:
            return "text"
    
    def _normalize_confidence_score(self, confidence_value) -> float:
        """Normalize confidence score to a numeric value between 0 and 1"""
        if isinstance(confidence_value, (int, float)):
            return float(confidence_value)
        elif isinstance(confidence_value, str):
            confidence_lower = confidence_value.lower()
            if confidence_lower in ['high', 'very high', 'excellent']:
                return 0.9
            elif confidence_lower in ['medium', 'moderate', 'good']:
                return 0.7
            elif confidence_lower in ['low', 'poor']:
                return 0.3
            else:
                try:
                    # Try to parse as float
                    return float(confidence_value)
                except (ValueError, TypeError):
                    return 0.8  # Default fallback
        else:
            return 0.8  # Default fallback
    
    def _normalize_weight(self, weight_value):
        """Normalize weight value to extract numeric component"""
        if weight_value is None:
            return None
        elif isinstance(weight_value, (int, float)):
            return float(weight_value)
        elif isinstance(weight_value, str):
            # Extract numeric value from strings like "78.93 KGM"
            import re
            match = re.search(r'(\d+\.?\d*)', str(weight_value))
            if match:
                try:
                    return float(match.group(1))
                except (ValueError, TypeError):
                    return None
            return None
        else:
            return None

    def _normalize_total_amount_field(self, order_id: int, total_amount_data: Dict[str, Any]) -> int:
        """Normalize complex total_amount field into individual charge components"""
        try:
            from modules.core.supabase_client import get_supabase_client
            supabase = get_supabase_client()
            
            fields_saved = 0
            
            # Extract invoice details
            if 'invoice' in total_amount_data:
                invoice_data = total_amount_data['invoice']
                if 'amount' in invoice_data and invoice_data['amount'] is not None:
                    fields_saved += self._save_normalized_field(
                        supabase, order_id, 'invoice_amount', 
                        invoice_data['amount'], 'amount'
                    )
                if 'currency' in invoice_data and invoice_data['currency']:
                    fields_saved += self._save_normalized_field(
                        supabase, order_id, 'invoice_currency', 
                        invoice_data['currency'], 'currency'
                    )
            
            # Extract bill of lading details
            if 'bill_of_lading' in total_amount_data:
                bol_data = total_amount_data['bill_of_lading']
                
                # Always save individual charge fields (0 if not found)
                if 'freight_charges' in bol_data:
                    fields_saved += self._save_normalized_field(
                        supabase, order_id, 'freight_charges', 
                        bol_data['freight_charges'], 'amount'
                    )
                else:
                    # Create field with 0 value if not present
                    fields_saved += self._save_normalized_field(
                        supabase, order_id, 'freight_charges', 
                        0, 'amount'
                    )
                
                if 'insurance_charges' in bol_data:
                    fields_saved += self._save_normalized_field(
                        supabase, order_id, 'insurance_charges', 
                        bol_data['insurance_charges'], 'amount'
                    )
                else:
                    # Create field with 0 value if not present
                    fields_saved += self._save_normalized_field(
                        supabase, order_id, 'insurance_charges', 
                        0, 'amount'
                    )
                
                # BOL total charges
                if 'total_charges' in bol_data and bol_data['total_charges'] is not None:
                    fields_saved += self._save_normalized_field(
                        supabase, order_id, 'bol_total_charges', 
                        bol_data['total_charges'], 'amount'
                    )
                
                # BOL charges by currency (only freight and insurance)
                if 'charges_by_currency' in bol_data and bol_data['charges_by_currency']:
                    for currency, amount in bol_data['charges_by_currency'].items():
                        if amount is not None:
                            fields_saved += self._save_normalized_field(
                                supabase, order_id, f'bol_charges_{currency.lower()}', 
                                amount, 'amount'
                            )
                            fields_saved += self._save_normalized_field(
                                supabase, order_id, f'bol_charges_{currency.lower()}_currency', 
                                currency, 'currency'
                            )
                
                # Excluded charges
                if 'excluded_charges' in bol_data and bol_data['excluded_charges']:
                    for currency, amount in bol_data['excluded_charges'].items():
                        if amount is not None:
                            fields_saved += self._save_normalized_field(
                                supabase, order_id, f'excluded_charges_{currency.lower()}', 
                                amount, 'amount'
                            )
                            fields_saved += self._save_normalized_field(
                                supabase, order_id, f'excluded_charges_{currency.lower()}_currency', 
                                currency, 'currency'
                            )
            
            # Extract customs declaration details
            if 'customs_declaration' in total_amount_data:
                customs_data = total_amount_data['customs_declaration']
                if 'total_value' in customs_data and customs_data['total_value'] is not None:
                    fields_saved += self._save_normalized_field(
                        supabase, order_id, 'customs_total_value', 
                        customs_data['total_value'], 'amount'
                    )
                if 'primary_currency' in customs_data and customs_data['primary_currency']:
                    fields_saved += self._save_normalized_field(
                        supabase, order_id, 'customs_currency', 
                        customs_data['primary_currency'], 'currency'
                    )
            
            # Extract source information
            if 'source' in total_amount_data and total_amount_data['source']:
                fields_saved += self._save_normalized_field(
                    supabase, order_id, 'extraction_source', 
                    total_amount_data['source'], 'text'
                )
            
            # Save the original complex structure as a backup field
            import json
            fields_saved += self._save_normalized_field(
                supabase, order_id, 'total_amount_full', 
                json.dumps(total_amount_data), 'json'
            )
            
            print(f"✅ Normalized total_amount into {fields_saved} individual fields")
            return fields_saved
            
        except Exception as e:
            print(f"❌ Error normalizing total_amount field: {e}")
            return 0

    def _save_normalized_field(self, supabase, order_id: int, field_name: str, field_value: Any, data_type: str) -> int:
        """Helper method to save a normalized field to the database"""
        try:
            # Include fields that have values (including 0) but exclude None and empty strings
            if field_value is not None and str(field_value).strip() != "":
                field_data = {
                    'processing_result_id': order_id,
                    'field_name': field_name,
                    'field_value': str(field_value),
                    'data_type': data_type,
                    'confidence': 'high',
                    'extraction_timestamp': datetime.now().isoformat()
                }
                
                result = supabase.table('esad_fields').insert(field_data).execute()
                if result.data:
                    return 1
            return 0
        except Exception as e:
            print(f"❌ Error saving normalized field {field_name}: {e}")
            return 0

    def _save_bol_extraction_to_db(self, order_number: str, document_id: int, extracted_data: Dict[str, Any]) -> bool:
        """Save BOL extraction data to database"""
        try:
            # Import database functions
            from orders.models import get_order_by_number
            from modules.core.supabase_client import get_supabase_client
            
            # Get order ID
            order = get_order_by_number(order_number)
            if not order:
                print(f"❌ Cannot save BOL extraction - order not found: {order_number}")
                return False
            
            # Get Supabase client
            supabase = get_supabase_client()
            
            # Prepare data for database
            bol_data = {
                'order_id': order['id'],
                'document_id': document_id,
                'reported_date': extracted_data.get('reported_date'),
                'consignee_name': extracted_data.get('consignee_name'),
                'consignee_address': extracted_data.get('consignee_address'),
                'consignee_tel': extracted_data.get('consignee_tel'),
                'shipper': extracted_data.get('shipper'),
                'shipper_address': extracted_data.get('shipper_address'),
                'master_bill_of_lading': extracted_data.get('master_bill_of_lading'),
                'voyage_number': extracted_data.get('voyage_number'),
                'bill_of_lading': extracted_data.get('bill_of_lading'),
                'last_departure_date': extracted_data.get('last_departure_date'),
                'port_of_origin': extracted_data.get('port_of_origin'),
                'port_of_loading': extracted_data.get('port_of_loading'),
                'port_of_destination': extracted_data.get('port_of_destination'),
                'vessel': extracted_data.get('vessel'),
                'manifest_registration_number': extracted_data.get('manifest/registration_#'),
                'package_type': extracted_data.get('package_type'),
                'package_count': extracted_data.get('package_count'),
                'gross_weight': self._normalize_weight(extracted_data.get('weight')),
                'measurement': extracted_data.get('measurement'),
                'commodity': extracted_data.get('commodity'),
                'berth': extracted_data.get('berth'),
                'wharfinger': extracted_data.get('Wharfinger'),
                'extraction_timestamp': datetime.now().isoformat(),
                'processor': 'claude_sonnet_4_via_openrouter',
                'model': 'claude_sonnet_4',
                'processing_method': 'openrouter_api',
                'confidence_score': self._normalize_confidence_score(extracted_data.get('extraction_confidence', 0.8)),
                'extraction_status': 'success',
                'raw_extraction_data': extracted_data,
                'charges_data': extracted_data.get('charges', [])
            }
            
            # Insert into database
            result = supabase.table('bol_extractions').insert(bol_data).execute()
            
            if result.data:
                print(f"✅ Saved BOL extraction to database with ID: {result.data[0]['id']}")
                print(f"📊 BOL Data Saved:")
                print(f"   • Bill of Lading: {bol_data['bill_of_lading']}")
                print(f"   • Shipper: {bol_data['shipper']}")
                print(f"   • Consignee: {bol_data['consignee_name']}")
                print(f"   • Vessel: {bol_data['vessel']}")
                print(f"   • Port of Loading: {bol_data['port_of_loading']}")
                print(f"   • Port of Destination: {bol_data['port_of_destination']}")
                print(f"   • Commodity: {bol_data['commodity']}")
                print(f"   • Charges: {len(bol_data['charges_data'])}")
                return True
            else:
                print("❌ Failed to save BOL extraction to database")
                return False
                
        except Exception as e:
            print(f"❌ Error saving BOL extraction to database: {e}")
            return False


# Main execution
def main():
    if len(sys.argv) not in [2, 3, 4]:
        print("Usage: python document_processor.py <order_number> [--summary]")
        print("       python document_processor.py <order_number> --esad")
        print("       python document_processor.py <order_number> --summary")
        return
    
    order_number = sys.argv[1]
    show_summary = len(sys.argv) >= 3 and sys.argv[2] == "--summary"
    process_esad = len(sys.argv) >= 3 and sys.argv[2] == "--esad"
    
    # Initialize processor
    processor = DocumentProcessor()
    
    try:
        if show_summary:
            # Show processing summary for existing order
            summary = processor.get_processing_summary(order_number)
            
            if 'error' in summary:
                print(f"❌ {summary['error']}")
                return
            
            print(f"\n📊 Processing Summary for Order: {order_number}")
            print("=" * 60)
            print(f"Overall Status: {summary['overall_status']}")
            print(f"Documents Processed: {len(summary['documents_processed'])}")
            
            for doc in summary['documents_processed']:
                status = "✅" if doc.get('extraction_successful') else "❌"
                print(f"\n{status} {doc['document_type'].upper()}:")
                if doc['document_type'] == 'invoice' and doc.get('extraction_successful'):
                    print(f"   • Items: {doc.get('items_count', 'N/A')}")
                    print(f"   • Supplier: {'✓' if doc.get('supplier_found') else '✗'}")
                    print(f"   • Buyer: {'✓' if doc.get('buyer_found') else '✗'}")
                    print(f"   • Total: ${doc.get('total_amount', 'N/A')} {doc.get('currency', '')}")
                    print(f"   • Confidence: {doc.get('confidence', 'N/A')}")
                elif doc['document_type'] == 'bill_of_lading' and doc.get('extraction_successful'):
                    print(f"   • Vessel: {'✓' if doc.get('vessel_found') else '✗'}")
                    print(f"   • Shipper: {'✓' if doc.get('shipper_found') else '✗'}")
                    print(f"   • Consignee: {'✓' if doc.get('consignee_found') else '✗'}")
                    print(f"   • Container: {'✓' if doc.get('container_found') else '✗'}")
                    print(f"   • Charges: {doc.get('charges_count', 'N/A')}")
                    print(f"   • Type: {doc.get('document_type', 'N/A')}")
                elif not doc.get('extraction_successful'):
                    print(f"   • Error: {doc.get('error', 'Unknown error')}")
        else:
            # Process documents for the order
            results = processor.process_order_documents(order_number)
            
            if 'error' in results:
                print(f"❌ Processing failed: {results['error']}")
            else:
                print(f"✅ Processing completed for order: {order_number}")
                
                # Print document-specific results
                successful_docs = sum(1 for result in results.values() if result.get('status') == 'success')
                total_docs = len(results)
                print(f"📄 Documents Processed: {successful_docs}/{total_docs}")
                
                for doc_type, result in results.items():
                    status = "✅" if result.get('status') == 'success' else "❌"
                    print(f"   {status} {doc_type}: {result.get('status', 'unknown')}")
                    
                    # Show additional details for successful extractions
                    if result.get('status') == 'success':
                        if doc_type == 'invoice':
                            quality = result.get('quality_metrics', {})
                            print(f"      • Fields extracted: {result.get('extracted_fields_count', 0)}")
                            print(f"      • Items found: {result.get('line_items_count', 0)}")
                            print(f"      • Quality score: {quality.get('overall_quality_score', 'N/A')}%")
                            print(f"      • Confidence: {result.get('extraction_summary', {}).get('confidence', 'N/A')}")
                        elif doc_type == 'bill_of_lading':
                            print(f"      • Consignee: {'✓' if result.get('consignee_found') else '✗'}")
                            print(f"      • Shipper: {'✓' if result.get('shipper_found') else '✗'}")
                            print(f"      • Vessel: {'✓' if result.get('vessel_found') else '✗'}")
                            print(f"      • Container: {'✓' if result.get('container_found') else '✗'}")
                            print(f"      • Charges: {result.get('charges_count', 0)}")
        
    except Exception as e:
        print(f"❌ Document processing failed: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()