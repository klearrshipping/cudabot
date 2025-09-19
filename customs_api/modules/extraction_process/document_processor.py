#!/usr/bin/env python3
"""
document_processor.py
────────────────────
Document extraction orchestrator
Handles extraction of data from invoice and bill of lading documents using Claude Sonnet 4 via OpenRouter

This class focuses solely on document extraction orchestration.
It does NOT handle order management, database operations, or eSAD processing.

Usage:
    python document_processor.py <invoice_path> <bol_path>
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import traceback

# Add the root directory to the path for imports
current_dir = Path(__file__).parent
root_dir = current_dir.parent.parent
sys.path.insert(0, str(root_dir))

# No database imports - this is a pure extraction tool

# Configuration print for OpenRouter-based processing
print(f"📋 Document Extraction Processor Configuration:")
print(f"   🤖 Processor: Claude Sonnet 4 via OpenRouter")
print(f"   📄 Invoice Processing: OpenRouter API")
print(f"   📋 BOL Processing: OpenRouter API")


class DocumentProcessor:
    """
    Document Extraction Orchestrator
    
    This class focuses solely on orchestrating document extraction.
    It does NOT handle order management, database operations, or eSAD processing.
    """
    
    def __init__(self, base_dir: str = "processed_orders"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)
    
    def process_order_documents(self, order_number: str) -> Dict[str, Any]:
        """
        Process documents for a specific order number
        
        Args:
            order_number (str): The order number to process
            
        Returns:
            dict: Processing results for all documents
        """
        print(f"🔄 Starting document processing for order: {order_number}")
        
        # Get the order directory
        order_dir = self.base_dir / order_number
        if not order_dir.exists():
            return {"error": f"Order directory not found: {order_dir}"}
        
        # Find invoice and BOL files in the file_uploads directory (where they are initially stored)
        invoice_files = list((order_dir / "file_uploads").glob("*invoice*.pdf")) + list((order_dir / "file_uploads").glob("*invoice*.jpg")) + list((order_dir / "file_uploads").glob("*invoice*.png"))
        bol_files = list((order_dir / "file_uploads").glob("*bill_of_lading*.pdf")) + list((order_dir / "file_uploads").glob("*bill_of_lading*.jpg")) + list((order_dir / "file_uploads").glob("*bill_of_lading*.png"))
        
        if not invoice_files:
            return {"error": f"No invoice files found in {order_dir / 'file_uploads'}"}
        
        if not bol_files:
            return {"error": f"No BOL files found in {order_dir / 'file_uploads'}"}
        
        # Use the first files found (you might want to implement logic to handle multiple files)
        invoice_path = str(invoice_files[0])
        bol_path = str(bol_files[0])
        
        print(f"   📄 Found invoice: {invoice_path}")
        print(f"   📋 Found BOL: {bol_path}")
        
        # Process documents and save to the order directory
        return self._process_documents_for_order(invoice_path, bol_path, order_number)
    
    def _process_documents_for_order(self, invoice_path: str, bol_path: str, order_number: str) -> Dict[str, Any]:
        """
        Process documents and save JSON files to the order directory structure
        
        Args:
            invoice_path (str): Path to invoice document
            bol_path (str): Path to bill of lading document
            order_number (str): Order number
            
        Returns:
            dict: Processing results for both documents
        """
        print(f"🔄 Starting document extraction for order: {order_number}")
        print(f"   Invoice: {invoice_path}")
        print(f"   BOL: {bol_path}")
        
        # Validate input files
        invoice_file = Path(invoice_path)
        bol_file = Path(bol_path)
        
        if not invoice_file.exists():
            return {"error": f"Invoice file not found: {invoice_path}"}
        
        if not bol_file.exists():
            return {"error": f"BOL file not found: {bol_path}"}
        
        # Get the order directory
        order_dir = self.base_dir / order_number
        
        # Process documents in parallel
        processing_results = self._process_documents_parallel_for_order(
            invoice_path, bol_path, order_dir, order_number
        )
        
        # Check results
        successful_docs = sum(1 for result in processing_results.values() if result.get('status') == 'success')
        total_docs = len(processing_results)
        
        if successful_docs == total_docs and total_docs > 0:
            print(f"✅ All documents extracted successfully")
        else:
            print(f"⚠️ Document extraction completed with some failures")
        
        print(f"[EXTRACT] Order {order_number} completed. Successes={successful_docs}/{total_docs}")
        print(f"✅ Document extraction completed")
        return processing_results
    
    def process_documents(self, invoice_path: str, bol_path: str, output_prefix: str = "extraction") -> Dict[str, Any]:
        """
        Process invoice and bill of lading documents
        
        Args:
            invoice_path (str): Path to invoice document
            bol_path (str): Path to bill of lading document
            output_prefix (str): Prefix for output files
            
        Returns:
            dict: Processing results for both documents
        """
        print(f"🔄 Starting document extraction...")
        print(f"   Invoice: {invoice_path}")
        print(f"   BOL: {bol_path}")
        
        # Validate input files
        invoice_file = Path(invoice_path)
        bol_file = Path(bol_path)
        
        if not invoice_file.exists():
            return {"error": f"Invoice file not found: {invoice_path}"}
        
        if not bol_file.exists():
            return {"error": f"BOL file not found: {bol_path}"}
        
        # Create output directory for this extraction
        extraction_dir = self.output_dir / f"{output_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        extraction_dir.mkdir(parents=True, exist_ok=True)
        
        # Process documents in parallel
        processing_results = self._process_documents_parallel(
            invoice_path, bol_path, extraction_dir, output_prefix
        )
        
        # Check results
        successful_docs = sum(1 for result in processing_results.values() if result.get('status') == 'success')
        total_docs = len(processing_results)
        
        if successful_docs == total_docs and total_docs > 0:
            print(f"✅ All documents extracted successfully")
        else:
            print(f"⚠️ Document extraction completed with some failures")
        
        print(f"✅ Document extraction completed")
        return processing_results
    
    def _process_documents_parallel(self, invoice_path: str, bol_path: str, output_dir: Path, output_prefix: str) -> Dict[str, Any]:
        """
        Process documents in parallel using ThreadPoolExecutor
        
        Args:
            invoice_path (str): Path to invoice document
            bol_path (str): Path to bill of lading document
            output_dir (Path): Directory to save processed results
            output_prefix (str): Prefix for output files
            
        Returns:
            dict: Processing results for each document
        """
        results = {}
        
        with ThreadPoolExecutor(max_workers=2) as executor:
            # Submit processing tasks
            future_to_doc = {}
            
            # Submit invoice processing
            future_invoice = executor.submit(
                self._process_invoice, 
                invoice_path, 
                output_dir, 
                f"{output_prefix}_invoice"
            )
            future_to_doc[future_invoice] = 'invoice'
            
            # Submit BOL processing
            future_bol = executor.submit(
                self._process_bill_of_lading, 
                bol_path, 
                output_dir, 
                f"{output_prefix}_bol"
            )
            future_to_doc[future_bol] = 'bill_of_lading'
            
            # Collect results
            for future in as_completed(future_to_doc):
                doc_type = future_to_doc[future]
                
                try:
                    result = future.result()
                    results[doc_type] = result
                    
                    if result.get('status') == 'success':
                        print(f"✅ {doc_type} extraction completed")
                    else:
                        print(f"❌ {doc_type} extraction failed")
                        
                except Exception as e:
                    print(f"❌ {doc_type} processing error: {e}")
                    results[doc_type] = {
                        'status': 'failed',
                        'document_type': doc_type,
                        'error': str(e),
                        'timestamp': datetime.now().isoformat()
                    }
        
        return results
    
    def _process_documents_parallel_for_order(self, invoice_path: str, bol_path: str, order_dir: Path, order_number: str) -> Dict[str, Any]:
        """
        Process documents in parallel for a specific order
        
        Args:
            invoice_path (str): Path to invoice document
            bol_path (str): Path to bill of lading document
            order_dir (Path): Order directory path
            order_number (str): Order number
            
        Returns:
            dict: Processing results for each document
        """
        results = {}
        
        with ThreadPoolExecutor(max_workers=2) as executor:
            # Submit processing tasks
            future_to_doc = {}
            
            # Submit invoice processing
            future_invoice = executor.submit(
                self._process_invoice_for_order, 
                invoice_path, 
                order_dir, 
                order_number
            )
            future_to_doc[future_invoice] = 'invoice'
            
            # Submit BOL processing
            future_bol = executor.submit(
                self._process_bill_of_lading_for_order, 
                bol_path, 
                order_dir, 
                order_number
            )
            future_to_doc[future_bol] = 'bill_of_lading'
            
            # Collect results
            for future in as_completed(future_to_doc):
                doc_type = future_to_doc[future]
                
                try:
                    result = future.result()
                    results[doc_type] = result
                    
                    if result.get('status') == 'success':
                        print(f"✅ {doc_type.replace('_', ' ').title()} processed successfully")
                    else:
                        print(f"❌ {doc_type.replace('_', ' ').title()} processing failed: {result.get('error', 'Unknown error')}")
                        
                except Exception as e:
                    error_result = {
                        'status': 'failed',
                        'error': str(e),
                        'document_type': doc_type
                    }
                    results[doc_type] = error_result
                    print(f"❌ {doc_type.replace('_', ' ').title()} processing failed with exception: {e}")
        
        return results
    
    def _process_invoice(self, file_path: str, output_dir: Path, output_prefix: str) -> Dict[str, Any]:
        """
        Process invoice document using Claude Sonnet 4 via OpenRouter
        """
        try:
            # Import the OpenRouter-based invoice extractor
            from modules.extraction_process.invoice_extract import InvoiceExtractor
            
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
            
            # Save extracted data to our output directory
            extracted_file = output_dir / f"{output_prefix}_extract.json"
            with open(extracted_file, 'w', encoding='utf-8') as f:
                json.dump(extracted_data, f, indent=2, ensure_ascii=False)
            
            # Calculate metrics for OpenRouter extraction
            items_count = len(extracted_data.get('items', []))
            
            # Count total extracted fields across all sections (flexible)
            extracted_fields_count = self._count_all_fields_recursive(extracted_data)
            
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
    
    def _process_bill_of_lading(self, file_path: str, output_dir: Path, output_prefix: str) -> Dict[str, Any]:
        """
        Process bill of lading document using Claude Sonnet 4 via OpenRouter
        """
        try:
            # Import the OpenRouter-based BOL extractor
            from modules.extraction_process.bol_extract import FlexibleFormExtractor
            
            # Initialize extractor
            extractor = FlexibleFormExtractor()
            
            # Process BOL
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                raise FileNotFoundError(f"BOL file not found: {file_path}")
            
            # Extract data (don't save to individual extractor's directory)
            extracted_data = extractor.process_document(file_path_obj, save_to_file=False)
            
            # Check if extraction was successful
            if extracted_data.get('status') == 'failed':
                raise Exception(f"Extraction failed: {extracted_data.get('error', 'Unknown error')}")
            
            # Save extracted data to our output directory
            extracted_file = output_dir / f"{output_prefix}_extract.json"
            with open(extracted_file, 'w', encoding='utf-8') as f:
                json.dump(extracted_data, f, indent=2, ensure_ascii=False)
            
            # Calculate metrics for OpenRouter extraction (BOL-specific)
            extracted_fields_count = self._count_bol_fields(extracted_data)
            
            # Analyze extraction quality
            quality_metrics = self._analyze_extraction_quality(extracted_data)
            
            # Create detailed section status
            sections_extracted = self._get_section_status(extracted_data)
            
            return {
                'status': 'success',
                'document_type': 'bill_of_lading',
                'processor_type': 'claude_sonnet_4_via_openrouter',
                'extracted_data_file': str(extracted_file),
                'extracted_fields_count': extracted_fields_count,
                'structure_version': 'v4_claude_sonnet_openrouter',
                'sections_extracted': sections_extracted,
                'quality_metrics': quality_metrics,
                'extraction_summary': {
                    'shipper_identified': bool(extracted_data.get('shipper')),
                    'consignee_identified': bool(extracted_data.get('consignee_name')),
                    'vessel_found': bool(extracted_data.get('vessel')),
                    'voyage_found': bool(extracted_data.get('voyage_number')),
                    'port_origin_found': bool(extracted_data.get('port_of_origin')),
                    'port_destination_found': bool(extracted_data.get('port_of_destination')),
                    'commodity_found': bool(extracted_data.get('commodity')),
                    'weight_found': bool(extracted_data.get('weight')),
                    'confidence': extracted_data.get('extraction_confidence', 'unknown')
                },
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"❌ BOL processing error: {e}")
            traceback.print_exc()
            return {
                'status': 'failed',
                'document_type': 'bill_of_lading',
                'processor_type': 'claude_sonnet_4_via_openrouter',
                'error': str(e),
                'error_details': traceback.format_exc(),
                'timestamp': datetime.now().isoformat()
            }
    
    def _count_invoice_fields(self, extracted_data: Dict[str, Any]) -> int:
        """Count extracted fields from invoice extraction structure"""
        field_count = 0
        
        # Count fields in each invoice section
        sections_to_count = [
            'supplier', 'buyer', 'invoice_details', 'shipping', 
            'totals', 'payment_terms'
        ]
        
        for section_name in sections_to_count:
            section_data = extracted_data.get(section_name, {})
            if isinstance(section_data, dict):
                field_count += self._count_nested_fields(section_data)
        
        # Count items
        items = extracted_data.get('items', [])
        if isinstance(items, list):
            field_count += len(items)
        
        return field_count
    
    def _count_bol_fields(self, extracted_data: Dict[str, Any]) -> int:
        """Count extracted fields from BOL extraction structure (flexible)"""
        return self._count_all_fields_recursive(extracted_data)
    
    def _count_all_fields_recursive(self, data: Dict[str, Any]) -> int:
        """Recursively count all non-null fields in the data structure"""
        count = 0
        
        if isinstance(data, dict):
            for key, value in data.items():
                if value is not None:
                    if isinstance(value, (dict, list)):
                        count += self._count_all_fields_recursive(value)
                    elif str(value).strip() and str(value).lower() not in ['null', 'none', 'n/a']:
                        count += 1
        elif isinstance(data, list):
            for item in data:
                if item is not None:
                    if isinstance(item, (dict, list)):
                        count += self._count_all_fields_recursive(item)
                    elif str(item).strip() and str(item).lower() not in ['null', 'none', 'n/a']:
                        count += 1
        
        return count
    
    def _count_nested_fields(self, data: Dict[str, Any]) -> int:
        """Count fields in nested dictionary structure"""
        count = 0
        for key, value in data.items():
            if value is not None and str(value).strip():
                count += 1
        return count
    
    def _get_section_status(self, extracted_data: Dict[str, Any]) -> Dict[str, bool]:
        """Get status of each extraction section"""
        sections = {
            'supplier': 'supplier',
            'buyer': 'buyer', 
            'invoice_details': 'invoice_details',
            'shipping': 'shipping',
            'totals': 'totals',
            'payment_terms': 'payment_terms',
            'items': 'items'
        }
        
        status = {}
        for section_key, section_name in sections.items():
            section_data = extracted_data.get(section_key, {})
            if isinstance(section_data, dict):
                status[section_name] = len([v for v in section_data.values() if v is not None and str(v).strip()]) > 0
            elif isinstance(section_data, list):
                status[section_name] = len(section_data) > 0
            else:
                status[section_name] = False
        
        return status
    
    def _analyze_extraction_quality(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze the quality of extraction results"""
        quality_metrics = {
            'completeness_score': 0,
            'data_quality_score': 0,
            'extraction_confidence': extracted_data.get('extraction_confidence', 'unknown'),
            'total_fields_extracted': 0,
            'critical_fields_present': 0,
            'warnings': [],
            'recommendations': []
        }
        
        # Count total fields
        total_fields = 0
        populated_fields = 0
        
        # Critical fields for invoice
        critical_invoice_fields = ['supplier', 'buyer', 'invoice_details', 'totals']
        critical_present = 0
        
        for section in critical_invoice_fields:
            section_data = extracted_data.get(section, {})
            if isinstance(section_data, dict):
                section_fields = len([v for v in section_data.values() if v is not None and str(v).strip()])
                total_fields += len(section_data)
                populated_fields += section_fields
                
                if section_fields > 0:
                    critical_present += 1
        
        # Calculate scores
        if total_fields > 0:
            quality_metrics['completeness_score'] = round((populated_fields / total_fields) * 100, 2)
        
        quality_metrics['critical_fields_present'] = critical_present
        quality_metrics['total_fields_extracted'] = populated_fields
        
        # Data quality assessment
        if quality_metrics['completeness_score'] >= 80:
            quality_metrics['data_quality_score'] = 90
        elif quality_metrics['completeness_score'] >= 60:
            quality_metrics['data_quality_score'] = 70
        else:
            quality_metrics['data_quality_score'] = 50
        
        # Add warnings and recommendations
        if quality_metrics['completeness_score'] < 60:
            quality_metrics['warnings'].append("Low extraction completeness - manual review recommended")
            quality_metrics['recommendations'].append("Consider improving document quality or extraction prompts")
        
        if critical_present < 3:
            quality_metrics['warnings'].append("Missing critical invoice sections")
            quality_metrics['recommendations'].append("Verify document contains all required invoice elements")
        
        return quality_metrics
    
    def get_extraction_summary(self, extraction_dir: Path) -> Dict[str, Any]:
        """
        Get summary of extraction results
        
        Args:
            extraction_dir (Path): Directory containing extraction results
            
        Returns:
            dict: Extraction summary
        """
        try:
            summary = {
                'extraction_directory': str(extraction_dir),
                'files_created': [],
                'overall_status': 'unknown'
            }
            
            # Check for invoice extraction
            invoice_files = list(extraction_dir.glob("*invoice*extract.json"))
            if invoice_files:
                summary['files_created'].extend([str(f) for f in invoice_files])
                summary['invoice_status'] = 'completed'
            else:
                summary['invoice_status'] = 'missing'
            
            # Check for BOL extraction
            bol_files = list(extraction_dir.glob("*bol*extract.json"))
            if bol_files:
                summary['files_created'].extend([str(f) for f in bol_files])
                summary['bol_status'] = 'completed'
            else:
                summary['bol_status'] = 'missing'
        
        # Determine overall status
            completed_docs = sum(1 for status in [summary.get('invoice_status'), summary.get('bol_status')] if status == 'completed')
            if completed_docs == 2:
                summary['overall_status'] = 'completed'
            elif completed_docs > 0:
                summary['overall_status'] = 'partial'
            else:
                summary['overall_status'] = 'failed'
        
            return summary
            
        except Exception as e:
            return {"error": f"Failed to get extraction summary: {str(e)}"}

    def _process_invoice_for_order(self, file_path: str, order_dir: Path, order_number: str) -> Dict[str, Any]:
        """
        Process invoice document for a specific order and save to the order directory
        
        Args:
            file_path (str): Path to invoice document
            order_dir (Path): Order directory path
            order_number (str): Order number
            
        Returns:
            dict: Processing results
        """
        try:
            # Import the OpenRouter-based invoice extractor
            from modules.extraction_process.invoice_extract import InvoiceExtractor
            
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
            
            # Save extracted data to the invoices folder within the order directory
            invoice_dir = order_dir / "invoices"
            invoice_dir.mkdir(exist_ok=True)
            extracted_file = invoice_dir / f"invoice_{order_number}_primary_extract.json"
            
            with open(extracted_file, 'w', encoding='utf-8') as f:
                json.dump(extracted_data, f, indent=2, ensure_ascii=False)
            
            # Calculate metrics for OpenRouter extraction
            items_count = len(extracted_data.get('items', []))
            extracted_fields_count = self._count_all_fields_recursive(extracted_data)
            quality_metrics = self._analyze_extraction_quality(extracted_data)
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
    
    def _process_bill_of_lading_for_order(self, file_path: str, order_dir: Path, order_number: str) -> Dict[str, Any]:
        """
        Process bill of lading document for a specific order and save to the order directory
        
        Args:
            file_path (str): Path to BOL document
            order_dir (Path): Order directory path
            order_number (str): Order number
            
        Returns:
            dict: Processing results
        """
        try:
            # Import the OpenRouter-based BOL extractor
            from modules.extraction_process.bol_extract import FlexibleFormExtractor
            
            # Initialize extractor
            extractor = FlexibleFormExtractor()
            
            # Process BOL
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                raise FileNotFoundError(f"BOL file not found: {file_path}")
            
            # Extract data (don't save to individual extractor's directory)
            extracted_data = extractor.process_document(file_path_obj, save_to_file=False)
            
            # Check if extraction was successful
            if extracted_data.get('status') == 'failed':
                raise Exception(f"Extraction failed: {extracted_data.get('error', 'Unknown error')}")
            
            # Save extracted data to the bills_of_lading folder within the order directory
            bol_dir = order_dir / "bills_of_lading"
            bol_dir.mkdir(exist_ok=True)
            extracted_file = bol_dir / f"bill_of_lading_{order_number}_primary_extract.json"
            
            with open(extracted_file, 'w', encoding='utf-8') as f:
                json.dump(extracted_data, f, indent=2, ensure_ascii=False)
            
            # Calculate metrics for OpenRouter extraction (BOL-specific)
            extracted_fields_count = self._count_bol_fields(extracted_data)
            quality_metrics = self._analyze_extraction_quality(extracted_data)
            sections_extracted = self._get_section_status(extracted_data)
            
            return {
                'status': 'success',
                'document_type': 'bill_of_lading',
                'processor_type': 'claude_sonnet_4_via_openrouter',
                'extracted_data_file': str(extracted_file),
                'extracted_fields_count': extracted_fields_count,
                'structure_version': 'v4_claude_sonnet_openrouter',
                'sections_extracted': sections_extracted,
                'quality_metrics': quality_metrics,
                'extraction_summary': {
                    'shipper_identified': bool(extracted_data.get('shipper')),
                    'consignee_identified': bool(extracted_data.get('consignee_name')),
                    'vessel_found': bool(extracted_data.get('vessel')),
                    'voyage_found': bool(extracted_data.get('voyage_number')),
                    'port_origin_found': bool(extracted_data.get('port_of_origin')),
                    'port_destination_found': bool(extracted_data.get('port_of_destination')),
                    'commodity_found': bool(extracted_data.get('commodity')),
                    'weight_found': bool(extracted_data.get('weight')),
                    'confidence': extracted_data.get('extraction_confidence', 'unknown')
                },
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"❌ BOL processing error: {e}")
            traceback.print_exc()
            return {
                'status': 'failed',
                'document_type': 'bill_of_lading',
                'processor_type': 'claude_sonnet_4_via_openrouter',
                'error': str(e),
                'error_details': traceback.format_exc(),
                'timestamp': datetime.now().isoformat()
            }


def main():
    """Main function for command line usage"""
    if len(sys.argv) < 3:
        print("Usage: python document_processor.py <invoice_path> <bol_path> [output_prefix]")
        sys.exit(1)
    
    invoice_path = sys.argv[1]
    bol_path = sys.argv[2]
    output_prefix = sys.argv[3] if len(sys.argv) > 3 else "extraction"
    
    try:
        processor = DocumentProcessor()
        results = processor.process_documents(invoice_path, bol_path, output_prefix)
        
        print(f"\n📊 Extraction Results Summary:")
        print("=" * 50)
        
        for doc_type, result in results.items():
            if isinstance(result, dict):
                status = result.get('status', 'unknown')
                print(f"{doc_type}: {status}")
                
                if status == 'success':
                    fields_count = result.get('extracted_fields_count', 0)
                    print(f"  Fields extracted: {fields_count}")
                    print(f"  File: {result.get('extracted_data_file', 'N/A')}")
                elif status == 'failed':
                    print(f"  Error: {result.get('error', 'Unknown error')}")
        
        # Get overall summary
        extraction_dir = processor.output_dir / f"{output_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        summary = processor.get_extraction_summary(extraction_dir)
        print(f"\nOverall Status: {summary.get('overall_status', 'unknown')}")
        
    except Exception as e:
        print(f"❌ Processing failed: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
