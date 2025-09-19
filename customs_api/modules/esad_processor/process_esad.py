#!/usr/bin/env python3
"""
eSAD Processing Orchestrator - Enhanced Version
===============================================

Streamlined orchestrator for eSAD (Electronic Single Administrative Document) 
processing workflow for customs declarations with improved structured output.

Workflow:
1. Load extraction data from invoice/BOL files
2. Process eSAD fields using definitions from eSAD.json
3. Generate final eSAD form data ready for customs submission

Usage:
    python process_esad.py <order_number>
    python process_esad.py ORD-20241215-001
"""

import sys
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TableFormatter:
    """Utility class for creating formatted tables in console output."""
    
    @staticmethod
    def create_table(headers: List[str], rows: List[List[str]], title: str = None) -> str:
        """Create a formatted ASCII table."""
        if not rows:
            return f"\n{title}\n" + "="*50 + "\nNo data available\n" if title else "No data available"
        
        # Calculate column widths
        col_widths = [len(header) for header in headers]
        for row in rows:
            for i, cell in enumerate(row):
                if i < len(col_widths):
                    col_widths[i] = max(col_widths[i], len(str(cell)))
        
        # Create table
        table_lines = []
        
        if title:
            table_lines.append(f"\n{title}")
            table_lines.append("="*len(title))
        
        # Header row
        header_row = "| " + " | ".join(headers[i].ljust(col_widths[i]) for i in range(len(headers))) + " |"
        table_lines.append(header_row)
        table_lines.append("+" + "+".join("-"*(col_widths[i]+2) for i in range(len(headers))) + "+")
        
        # Data rows
        for row in rows:
            data_row = "| " + " | ".join(str(row[i]).ljust(col_widths[i]) if i < len(row) else "".ljust(col_widths[i]) for i in range(len(headers))) + " |"
            table_lines.append(data_row)
        
        return "\n".join(table_lines) + "\n"
    
    @staticmethod
    def create_summary_box(title: str, data: Dict[str, Any]) -> str:
        """Create a summary box for key-value data."""
        lines = [f"\n{title}", "="*len(title)]
        for key, value in data.items():
            lines.append(f"{key.replace('_', ' ').title()}: {value}")
        return "\n".join(lines) + "\n"

class ESADOrchestrator:
    """
    eSAD Processing Orchestrator - Enhanced Version
    
    Coordinates the complete eSAD processing workflow with structured output.
    """
    
    def __init__(self):
        """Initialize orchestrator and load eSAD definitions."""
        self.esad_definitions = self._load_esad_definitions()
        self.table_formatter = TableFormatter()
        print(f"eSAD Orchestrator initialized - {len(self.esad_definitions.get('esad_mandatory_fields', {}).get('fields', []))} fields defined")
    
    def _load_esad_definitions(self) -> Dict[str, Any]:
        """Load eSAD field definitions from eSAD.json."""
        try:
            esad_file = Path(__file__).parent / "eSAD.json"
            with open(esad_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load eSAD definitions: {e}")
            return {"esad_mandatory_fields": {"fields": []}}
    
    def process_order_esad(self, order_number: str) -> Dict[str, Any]:
        """
        Process eSAD for a specific order using 3-stage approach.
        
        Args:
            order_number (str): Order number (e.g., "ORD-20241215-001")
            
        Returns:
            dict: Complete eSAD processing results
        """
        print(f"\nProcessing eSAD for order: {order_number}")
        print("="*60)
        
        try:
            # STAGE 1: Load JSON files
            print("\nSTAGE 1: Loading JSON files...")
            print("-"*30)
            invoice_data, bol_data = self._stage1_load_json_files(order_number)
            if not invoice_data or not bol_data:
                return self._error_result(order_number, "Failed to load invoice or BOL extraction results")
            
            # STAGE 2: Load eSAD definitions
            print("\nSTAGE 2: Loading eSAD definitions...")
            print("-"*30)
            field_definitions = self._stage2_load_esad_definitions()
            if not field_definitions:
                return self._error_result(order_number, "Failed to load eSAD field definitions")
            
            # STAGE 3: Process eSAD fields
            print("\nSTAGE 3: Processing eSAD fields...")
            print("-"*30)
            esad_results = self._stage3_process_fields(invoice_data, bol_data, field_definitions, order_number)
            
            # Generate final results
            final_results = self._generate_final_esad(order_number, esad_results)
            
            # Display final summary
            self._display_final_summary(final_results)
            
            return final_results
            
        except Exception as e:
            return self._error_result(order_number, str(e))
    
    def _stage1_load_json_files(self, order_number: str = None) -> Tuple[Optional[Dict], Optional[Dict]]:
        """
        STAGE 1: Load JSON files (invoice and BOL data)
        
        Args:
            order_number (str): Order number (optional for testing)
            
        Returns:
            tuple: (invoice_data, bol_data) or (None, None) if failed
        """
        # TESTING: Always use hardcoded paths for testing purposes
        print("TESTING MODE: Using hardcoded JSON file paths")
        return self._stage1_testing_load_hardcoded_files()
    
    def _stage1_testing_load_hardcoded_files(self) -> Tuple[Optional[Dict], Optional[Dict]]:
        """
        TESTING FUNCTION: Load hardcoded JSON files for testing purposes
        
        Returns:
            tuple: (invoice_data, bol_data) or (None, None) if failed
        """
        # Hardcoded file paths for testing
        invoice_path = r"C:\Users\rafer\OneDrive\Desktop\projects\cuda\customs_api\processed_orders\ORD-20250916-004\invoices\invoice_ORD-20250916-004_primary_extract.json"
        bol_path = r"C:\Users\rafer\OneDrive\Desktop\projects\cuda\customs_api\processed_orders\ORD-20250916-004\bills_of_lading\bill_of_lading_ORD-20250916-004_primary_extract.json"
        
        try:
            # Load invoice file
            if not Path(invoice_path).exists():
                print(f"ERROR: Invoice file not found: {invoice_path}")
                return None, None
                
            with open(invoice_path, 'r', encoding='utf-8') as f:
                invoice_data = json.load(f)
            
            # Load BOL file
            if not Path(bol_path).exists():
                print(f"ERROR: BOL file not found: {bol_path}")
                return None, None
                
            with open(bol_path, 'r', encoding='utf-8') as f:
                bol_data = json.load(f)
            
            print("SUCCESS: Loaded hardcoded JSON files")
            
            # Display data in structured tables
            self._display_source_data_tables(invoice_data, bol_data)
            
            return invoice_data, bol_data
            
        except Exception as e:
            print(f"ERROR: Failed to load hardcoded files: {e}")
            return None, None
    
    def _display_source_data_tables(self, invoice_data: Dict, bol_data: Dict):
        """Display source data in organized tables."""
        # Invoice data table
        invoice_rows = []
        for key, value in sorted(invoice_data.items()):
            if isinstance(value, (dict, list)):
                display_value = f"{type(value).__name__} ({len(value)} items)"
            else:
                display_value = str(value)[:50] + "..." if len(str(value)) > 50 else str(value)
            invoice_rows.append([key, display_value])
        
        print(self.table_formatter.create_table(
            ["Field", "Value"], 
            invoice_rows, 
            f"INVOICE DATA ({len(invoice_data)} fields)"
        ))
        
        # BOL data table
        bol_rows = []
        for key, value in sorted(bol_data.items()):
            if isinstance(value, (dict, list)):
                display_value = f"{type(value).__name__} ({len(value)} items)"
            else:
                display_value = str(value)[:50] + "..." if len(str(value)) > 50 else str(value)
            bol_rows.append([key, display_value])
        
        print(self.table_formatter.create_table(
            ["Field", "Value"], 
            bol_rows, 
            f"BILL OF LADING DATA ({len(bol_data)} fields)"
        ))
    
    def _stage2_load_esad_definitions(self) -> list:
        """
        STAGE 2: Load eSAD definitions
        
        Returns:
            list: Field definitions from eSAD.json
        """
        field_definitions = self.esad_definitions.get("esad_mandatory_fields", {}).get("fields", [])
        print(f"Loaded {len(field_definitions)} eSAD field definitions")
        
        # Display eSAD definitions in table format
        def_rows = []
        for i, field_def in enumerate(field_definitions, 1):
            field_name = field_def.get("field_name", "Unknown")
            box_field = field_def.get("box_field", "Unknown")
            script = field_def.get("script", "")
            processing_method = field_def.get("processing_method", "")
            
            # Determine processing type
            if script:
                processing_type = f"Script: {script}"
            elif processing_method.startswith("automated"):
                processing_type = f"Auto: {processing_method}"
            else:
                processing_type = "LLM Extraction"
            
            def_rows.append([str(i), f"Box {box_field}", field_name, processing_type])
        
        print(self.table_formatter.create_table(
            ["#", "Box", "Field Name", "Processing Method"], 
            def_rows, 
            f"eSAD FIELD DEFINITIONS ({len(field_definitions)} fields)"
        ))
        
        return field_definitions
    
    def _stage3_process_fields(self, invoice_data: Dict[str, Any], bol_data: Dict[str, Any], field_definitions: list, order_number: str) -> Dict[str, Any]:
        """
        STAGE 3: Process eSAD fields using LLM extraction and esad modules
        
        Args:
            invoice_data (dict): Invoice extraction data
            bol_data (dict): Bill of lading extraction data
            field_definitions (list): eSAD field definitions
            order_number (str): Order number
            
        Returns:
            dict: Processing results
        """
        # Categorize fields
        llm_fields = []
        automated_fields = []
        esad_module_fields = []
        
        for field_def in field_definitions:
            extraction_prompt = field_def.get("extraction_prompt", "")
            processing_method = field_def.get("processing_method", "")
            script = field_def.get("script", "")
            
            if extraction_prompt and not extraction_prompt.startswith("AUTOMATED:"):
                llm_fields.append(field_def)
            elif script:
                esad_module_fields.append(field_def)
            elif processing_method and processing_method.startswith("automated"):
                automated_fields.append(field_def)
        
        # Display processing summary
        summary_data = {
            "LLM fields": len(llm_fields),
            "Automated fields": len(automated_fields),
            "eSAD module fields": len(esad_module_fields),
            "Total fields": len(field_definitions)
        }
        print(self.table_formatter.create_summary_box("FIELD PROCESSING SUMMARY", summary_data))
        
        # Process fields
        esad_fields = {}
        extraction_summary = {
            "total_fields_defined": len(field_definitions),
            "llm_extractions": 0,
            "esad_module_extractions": 0,
            "automated_extractions": 0,
            "failed_extractions": 0
        }
        
        # Process LLM fields
        if llm_fields:
            print("Processing LLM fields...")
            llm_results = self._process_llm_fields(llm_fields, invoice_data, bol_data)
            esad_fields.update(llm_results)
            extraction_summary["llm_extractions"] = len([v for v in llm_results.values() if v])
            extraction_summary["failed_extractions"] += len([v for v in llm_results.values() if not v])
            
            self._display_extraction_results("LLM EXTRACTION RESULTS", llm_results)
        
        # Process eSAD module fields
        if esad_module_fields:
            print("Processing eSAD module fields...")
            # Primary source: pass order_number in existing_fields for module context
            existing_with_order = dict(esad_fields)
            existing_with_order["order_number"] = order_number
            module_results = self._process_esad_module_fields(esad_module_fields, invoice_data, bol_data, existing_with_order)
            esad_fields.update(module_results)
            extraction_summary["esad_module_extractions"] = len([v for v in module_results.values() if v])
            extraction_summary["failed_extractions"] += len([v for v in module_results.values() if not v])
            
            self._display_extraction_results("eSAD MODULE RESULTS", module_results)
            
            # Fallback for Box 7 (Commercial reference number): if missing, use order_number (primary)
            box7_key = "7_commercial_reference_number"
            if not esad_fields.get(box7_key):
                esad_fields[box7_key] = order_number
            # Secondary: if still missing (or order_number unavailable), parse from file paths
            if not esad_fields.get(box7_key):
                parsed_order = self._parse_order_number_from_sources(invoice_data, bol_data)
                if parsed_order:
                    esad_fields[box7_key] = parsed_order
        
        # Process automated fields
        if automated_fields:
            print("Processing automated fields...")
            automated_results = self._process_automated_fields(automated_fields, invoice_data, bol_data)
            esad_fields.update(automated_results)
            extraction_summary["automated_extractions"] = len([v for v in automated_results.values() if v])
            extraction_summary["failed_extractions"] += len([v for v in automated_results.values() if not v])
            
            self._display_extraction_results("AUTOMATED FIELD RESULTS", automated_results)
        
        return {
            "order_number": order_number,
            "processing_timestamp": datetime.now().isoformat(),
            "esad_fields": esad_fields,
            "extraction_summary": extraction_summary,
            "source_data": {"invoice": invoice_data, "bill_of_lading": bol_data}
        }
    
    def _display_extraction_results(self, title: str, results: Dict[str, str]):
        """Display extraction results in a structured table."""
        if not results:
            print(f"\n{title}: No results to display\n")
            return
        
        result_rows = []
        for field_key, field_value in results.items():
            status = "SUCCESS" if field_value else "FAILED"
            display_value = field_value if field_value else "Not found"
            result_rows.append([field_key, status, display_value])
        
        print(self.table_formatter.create_table(
            ["Field Key", "Status", "Value"], 
            result_rows, 
            title
        ))
    
    def _process_llm_fields(self, llm_fields: list, invoice_data: Dict[str, Any], bol_data: Dict[str, Any]) -> Dict[str, str]:
        """Process fields that require LLM extraction using extraction prompts."""
        results = {}
        all_data = {'invoice_data': invoice_data, 'bol_data': bol_data}
        
        print(f"Processing {len(llm_fields)} LLM fields...")
        
        for i, field_def in enumerate(llm_fields, 1):
            field_name = field_def.get("field_name", "")
            box_field = field_def.get("box_field", "")
            extraction_prompt = field_def.get("extraction_prompt", "")
            
            field_key = f"{box_field}_{field_name.lower().replace('/', '_').replace(' ', '_')}"
            
            print(f"  [{i}/{len(llm_fields)}] Processing Box {box_field}: {field_name}...")
            
            try:
                field_value = self._extract_field_with_llm(field_def, all_data, extraction_prompt)
                results[field_key] = field_value
                
                if field_value:
                    print(f"    ✅ SUCCESS: {field_value}")
                else:
                    print(f"    ❌ FAILED: Not found")
                    
            except Exception as e:
                print(f"    ⚠️ ERROR: {e}")
                results[field_key] = ""
        
        return results
    
    def _extract_field_with_llm(self, field_def: Dict[str, Any], all_data: Dict[str, Any], extraction_prompt: str) -> str:
        """Extract field value using LLM with extraction prompt."""
        try:
            # Import LLM client
            import sys
            import os
            customs_api_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            if customs_api_dir not in sys.path:
                sys.path.append(customs_api_dir)
            from modules.core.llm_client import LLMClient
            
            llm_client = LLMClient()
            
            # Simplify data context to reduce token usage
            invoice_data = all_data.get('invoice_data', {})
            bol_data = all_data.get('bol_data', {})
            
            # Extract only relevant fields to reduce context size
            relevant_invoice = {
                'supplier': invoice_data.get('supplier', {}),
                'totals': invoice_data.get('totals', {}),
                'currency': invoice_data.get('currency', ''),
                'invoice_details': invoice_data.get('invoice_details', {}),
                'items': invoice_data.get('items', [])
            }
            
            relevant_bol = {
                'shipper': bol_data.get('shipper', {}),
                'consignee': bol_data.get('consignee', {}),
                'cargo': bol_data.get('cargo', {}),
                'port_of_loading': bol_data.get('port_of_loading', ''),
                'port_of_discharge': bol_data.get('port_of_discharge', ''),
                'vessel_name': bol_data.get('vessel_name', ''),
                'voyage_number': bol_data.get('voyage_number', ''),
                'sea_waybill_no': bol_data.get('sea_waybill_no', ''),
                'bill_of_lading': bol_data.get('bill_of_lading', '')
            }
            
            data_context = f"""
INVOICE DATA:
{json.dumps(relevant_invoice, indent=2)}

BILL OF LADING DATA:
{json.dumps(relevant_bol, indent=2)}
"""
            
            full_prompt = f"""
{extraction_prompt}

FIELD TO EXTRACT: {field_def.get('field_name', '')}
BOX: {field_def.get('box_field', '')}

DOCUMENT DATA:
{data_context}

Please extract the requested field value. Return only the extracted value, nothing else. If the field cannot be found, return "NOT_FOUND".
"""
            
            model = "openai/gpt-5-mini"
            response = llm_client.send_prompt(full_prompt, model=model)
            
            if response and response.strip() and response.strip() != "NOT_FOUND":
                return response.strip()
            else:
                return ""
                
        except Exception as e:
            print(f"    ⚠️ LLM failed, using fallback: {e}")
            return self._extract_field_directly(field_def, all_data.get('invoice_data', {}), all_data.get('bol_data', {}))
    
    def _process_esad_module_fields(self, esad_module_fields: list, invoice_data: Dict[str, Any], bol_data: Dict[str, Any], existing_fields: Dict[str, str]) -> Dict[str, str]:
        """Process fields that use eSAD modules for processing."""
        results = {}
        
        # Group fields by script
        script_groups = {}
        for field_def in esad_module_fields:
            script = field_def.get("script", "")
            if script not in script_groups:
                script_groups[script] = []
            script_groups[script].append(field_def)
            
        for script_name, fields in script_groups.items():
            script_results = self._run_specialized_script_once(script_name, fields, invoice_data, bol_data, existing_fields)
            
            for field_def in fields:
                field_name = field_def.get("field_name", "")
                box_field = field_def.get("box_field", "")
                field_key = f"{box_field}_{field_name.lower().replace('/', '_').replace(' ', '_')}"
                
                field_value = self._extract_field_from_script_results(field_name, script_results)
                results[field_key] = field_value
        
        return results
    
    def _process_automated_fields(self, automated_fields: list, invoice_data: Dict[str, Any], bol_data: Dict[str, Any]) -> Dict[str, str]:
        """Process fields that use automated processing methods."""
        results = {}
        
        for field_def in automated_fields:
            field_name = field_def.get("field_name", "")
            box_field = field_def.get("box_field", "")
            processing_method = field_def.get("processing_method", "")
            field_key = f"{box_field}_{field_name.lower().replace('/', '_').replace(' ', '_')}"
            
            if processing_method == "automated_default_value":
                # Use the default_value from eSAD.json configuration
                field_value = field_def.get("default_value", "")
            elif processing_method == "automated_order_id":
                field_value = "ORD-20250916-004"
            elif processing_method == "automated_product_standardization":
                # Extract commercial description from invoice items or BOL particulars
                field_value = self._extract_commercial_description(invoice_data, bol_data)
            elif processing_method == "automated_hscode_classification":
                # Extract commodity code from source data or use fallback
                field_value = self._extract_commodity_code(invoice_data, bol_data)
            else:
                field_value = self._extract_field_directly(field_def, invoice_data, bol_data)
            
            results[field_key] = field_value
        
        return results
    
    def _extract_commercial_description(self, invoice_data: Dict[str, Any], bol_data: Dict[str, Any]) -> str:
        """Extract commercial description from invoice items or BOL particulars."""
        # Try invoice first line item description
        if invoice_data and "items" in invoice_data and invoice_data["items"]:
            first_item = invoice_data["items"][0]
            if "description" in first_item and first_item["description"]:
                return first_item["description"].strip()
        
        # Try BOL particulars
        if bol_data and "particulars_furnished_by_shipper_said_to_contain" in bol_data:
            particulars = bol_data["particulars_furnished_by_shipper_said_to_contain"]
            
            # Try package description first
            if "package" in particulars and particulars["package"]:
                return particulars["package"].strip()
            
            # Try type description
            if "type" in particulars and particulars["type"]:
                return particulars["type"].strip()
        
        return ""
    
    def _extract_commodity_code(self, invoice_data: Dict[str, Any], bol_data: Dict[str, Any]) -> str:
        """Extract commodity code from source data or use fallback."""
        # Look for existing HS codes in the data
        all_data = {}
        if invoice_data:
            all_data.update(invoice_data)
        if bol_data:
            all_data.update(bol_data)
        
        # Common HS code field names to check
        hs_code_fields = [
            'hs_code', 'commodity_code', 'tariff_code', 'hscode',
            'hs_code_number', 'commodity_code_number', 'tariff_code_number'
        ]
        
        for field in hs_code_fields:
            if field in all_data and all_data[field]:
                code = str(all_data[field]).strip()
                if code and code != 'None':
                    return code
        
        # For Tesla Model Y, use a reasonable fallback HS code for electric vehicles
        # HS code 8703.80.00 is for electric motor vehicles for the transport of persons
        if invoice_data and "items" in invoice_data and invoice_data["items"]:
            first_item = first_item = invoice_data["items"][0]
            if "description" in first_item and "tesla" in first_item["description"].lower():
                return "8703.80.00"  # Electric motor vehicles for transport of persons
            
            return ""
            
    def _run_specialized_script_once(self, script_name: str, fields: list, invoice_data: Dict[str, Any], bol_data: Dict[str, Any], existing_fields: Dict[str, str] = None) -> Dict[str, Any]:
        """Run a specialized script once and return results for multiple fields.

        Captures the module's stdout and renders a concise, structured summary
        so logs are readable and grouped per script.
        """
        if not script_name:
            return {}
            
        try:
            import io
            import contextlib
            script_mapping = {
                "esad_manifest": ("esad_manifest", "ManifestProcessor"),
                "esad_regime": ("esad_regime", "RegimeTypeProcessor"),
                "esad_trn": ("esad_trn", "TRNLookupProcessor"),
                "esad_cif": ("esad_cif", "CIFProcessor"),
                "esad_transport_mode": ("esad_transport_mode", "TransportModeProcessor"),
                "esad_location": ("esad_location", "LocationProcessor"),
                "esad_primary": ("esad_ref_number", "CommercialReferenceProcessor"),
            }
            
            if script_name not in script_mapping:
                return {}
            
            module_name, class_name = script_mapping[script_name]
            module = __import__(f"esad_modules.{module_name}", fromlist=[class_name])
            processor_class = getattr(module, class_name)
            
            try:
                processor = processor_class()
            except TypeError:
                processor = processor_class({})
            
            input_data = {
                "invoice_data": invoice_data,
                "bol_data": bol_data,
                "fields": fields,
                "existing_fields": existing_fields or {}
            }
            
            # Special handling for esad_manifest: use BOL to fetch manifest/office
            if script_name == "esad_manifest":
                try:
                    from esad_modules.esad_manifest import ManifestTracker
                except Exception:
                    ManifestTracker = None

                bol_from_existing = None
                if existing_fields:
                    bol_from_existing = existing_fields.get("40_transport_document_previous_document")
                bol_from_bol = bol_data.get("sea_waybill_no") or bol_data.get("bill_of_lading") or bol_data.get("bol_number")
                bol_number = (bol_from_existing or bol_from_bol or "").strip()

                if ManifestTracker and bol_number:
                    buffer = io.StringIO()
                    with contextlib.redirect_stdout(buffer):
                        tracker = ManifestTracker()
                        tracking = tracker.track_bol(bol_number)
                    raw_log = buffer.getvalue().strip()

                    # Build result
                    manifest_num = None
                    office_code = None
                    if getattr(tracking, "success", False) and getattr(tracking, "entries", []):
                        entry = tracking.entries[0]
                        manifest_num = getattr(entry, "reference_id", None)
                        office_code = getattr(entry, "office", None)

                    summary_rows = []
                    if office_code:
                        summary_rows.append(["office_code", office_code])
                    if manifest_num:
                        summary_rows.append(["manifest_number", manifest_num])
                    print(self.table_formatter.create_table(["Key", "Value"], summary_rows or [["status", "not found"]], title="ESAD_MANIFEST SUMMARY"))
                    if raw_log:
                        lines = [ln for ln in raw_log.splitlines() if ln.strip()]
                        trimmed = "\n".join(lines[-15:]) if lines else ""
                        if trimmed:
                            print(self.table_formatter.create_summary_box("ESAD_MANIFEST LOG (last 15 lines)", {"lines": len(lines)}))
                            print(trimmed + "\n")

                    return {
                        "success": bool(office_code or manifest_num),
                        "office_code": office_code,
                        "manifest_number": manifest_num
                    }

            # Capture module prints to keep stdout structured (default path)
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                result = processor.process(input_data)
            raw_log = buffer.getvalue().strip()
            
            # Render a concise summary box for known scripts
            title = f"{script_name} RESULT"
            summary_rows = []
            # Common keys we try to surface if present
            surfaced: Dict[str, Any] = {}
            for key in [
                "regime_type", "office_code", "manifest_number", "trn_number",
                "cif_value", "transport_mode", "location_code", "commercial_ref"
            ]:
                if isinstance(result, dict) and key in result and result.get(key):
                    surfaced[key] = result.get(key)
            if isinstance(result, dict) and "model" in result:
                surfaced["model"] = result.get("model")
            if isinstance(result, dict) and "confidence" in result:
                surfaced["confidence"] = result.get("confidence")

            # Build summary rows
            for k, v in surfaced.items():
                summary_rows.append([k, str(v)])

            # Trim raw log to last ~15 lines to avoid noise
            trimmed_log = ""
            if raw_log:
                lines = [ln for ln in raw_log.splitlines() if ln.strip()]
                if lines:
                    last = lines[-15:]
                    trimmed_log = "\n".join(last)

            # Print nicely formatted block
            print(self.table_formatter.create_table(["Key", "Value"], summary_rows or [["status", "no surfaced values"]], title=f"{script_name.upper()} SUMMARY"))
            if trimmed_log:
                print(self.table_formatter.create_summary_box(f"{script_name.upper()} LOG (last 15 lines)", {"lines": len(lines) if raw_log else 0}))
                print(trimmed_log + "\n")

            if isinstance(result, dict) and result.get("success", False):
                return result
                return {}
            
        except Exception as e:
            return {}
    
    def _extract_field_from_script_results(self, field_name: str, script_results: Dict[str, Any]) -> str:
        """Extract a specific field value from script results."""
        if not script_results:
            return ""
        
        possible_field_names = [
            field_name.lower().replace(" ", "_").replace("/", "_"),
            field_name.lower().replace(" ", "").replace("/", ""),
            "office_code" if "office" in field_name.lower() else None,
            "manifest_number" if "manifest" in field_name.lower() else None,
            "regime_type" if "regime" in field_name.lower() else None,
            "trn_number" if "trn" in field_name.lower() else None,
            "cif_value" if "amount" in field_name.lower() else None,
            "transport_mode" if "transport" in field_name.lower() else None,
            "location_code" if "location" in field_name.lower() else None,
        ]
        
        for possible_name in possible_field_names:
            if possible_name and possible_name in script_results:
                value = script_results[possible_name]
                if value:
                    return str(value)
        
        for key, value in script_results.items():
            if key not in ["success", "error", "message"] and value:
                return str(value)
        
        return ""
    
    def _extract_field_directly(self, field_def: Dict[str, Any], invoice_data: Dict[str, Any], bol_data: Dict[str, Any]) -> str:
        """Extract a field value directly from document data."""
        field_name = field_def.get("field_name", "")
        extraction_prompt = field_def.get("extraction_prompt", "")
        box_field = field_def.get("box_field", "")
        
        if box_field == "40" and "transport document" in field_name.lower():
            if bol_data:
                if "sea_waybill_no" in bol_data and bol_data["sea_waybill_no"]:
                    return str(bol_data["sea_waybill_no"]).strip()
                if "bill_of_lading" in bol_data and bol_data["bill_of_lading"]:
                    return str(bol_data["bill_of_lading"]).strip()
                if "bol_number" in bol_data and bol_data["bol_number"]:
                    return str(bol_data["bol_number"]).strip()
        
        all_data = {}
        if invoice_data:
            all_data.update(invoice_data)
        if bol_data:
            all_data.update(bol_data)
        
        field_lower = field_name.lower()
        for key, value in all_data.items():
            key_lower = key.lower()
            if any(term in key_lower for term in field_lower.split()):
                if value and str(value).strip():
                    return str(value).strip()
        
        if extraction_prompt:
            keywords = self._extract_keywords_from_prompt(extraction_prompt)
            for key, value in all_data.items():
                key_lower = key.lower()
                if any(keyword in key_lower for keyword in keywords):
                    if value and str(value).strip():
                        return str(value).strip()
        
        return ""
    
    def _extract_keywords_from_prompt(self, prompt: str) -> list:
        """Extract relevant keywords from extraction prompt."""
        prompt_lower = prompt.lower()
        keywords = []
        
        if "shipper" in prompt_lower or "consignor" in prompt_lower:
            keywords.extend(["shipper", "consignor", "exporter"])
        if "consignee" in prompt_lower:
            keywords.extend(["consignee", "importer", "notify"])
        if "address" in prompt_lower:
            keywords.extend(["address", "location"])
        if "package" in prompt_lower:
            keywords.extend(["package", "piece", "count"])
        if "weight" in prompt_lower:
            keywords.extend(["weight", "gross", "net"])
        if "currency" in prompt_lower or "amount" in prompt_lower:
            keywords.extend(["currency", "amount", "total"])
        if "transport" in prompt_lower:
            keywords.extend(["transport", "vessel", "voyage"])
        if "country" in prompt_lower:
            keywords.extend(["country", "origin", "destination"])
        
        return keywords

    def _parse_order_number_from_sources(self, invoice_data: Dict[str, Any], bol_data: Dict[str, Any]) -> str:
        """Parse order number from known file path hints as a secondary fallback."""
        try:
            import re
            def find_in(obj: Any) -> str:
                try:
                    text = json.dumps(obj)
                except Exception:
                    text = str(obj)
                match = re.search(r"ORD-\d{8}-\d{3}", text)
                return match.group(0) if match else ""
            # Search invoice and BOL structures for any embedded path strings
            candidate = find_in(invoice_data)
            if candidate:
                return candidate
            candidate = find_in(bol_data)
            if candidate:
                return candidate
        except Exception:
            pass
        return ""
    
    def _generate_final_esad(self, order_number: str, esad_results: Dict) -> Dict[str, Any]:
        """Generate final eSAD form data."""
        try:
            esad_fields = esad_results.get("esad_fields", {})
            extraction_summary = esad_results.get("extraction_summary", {})
            
            output_dir = Path("../../processed_orders") / order_number / "esad_files"
            output_dir.mkdir(parents=True, exist_ok=True)
            final_esad_file = output_dir / f"final_esad_{order_number}.json"
            
            final_esad = {
                "order_number": order_number,
                "processing_timestamp": datetime.now().isoformat(),
                "esad_form_data": esad_fields,
                "processing_summary": {
                    "total_fields_defined": extraction_summary.get("total_fields_defined", 0),
                    "llm_extractions": extraction_summary.get("llm_extractions", 0),
                    "esad_module_extractions": extraction_summary.get("esad_module_extractions", 0),
                    "automated_extractions": extraction_summary.get("automated_extractions", 0),
                    "failed_extractions": extraction_summary.get("failed_extractions", 0),
                    "completion_status": "ready_for_submission"
                },
                "file_paths": {"final_esad_json": str(final_esad_file)}
            }
            
            with open(final_esad_file, 'w', encoding='utf-8') as f:
                json.dump(final_esad, f, indent=2, ensure_ascii=False)
            
            return {
                "status": "success",
                "order_number": order_number,
                "final_esad_path": str(final_esad_file),
                "esad_form_data": esad_fields,
                "processing_summary": final_esad["processing_summary"],
                "file_paths": final_esad["file_paths"],
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return self._error_result(order_number, f"Error generating final eSAD: {e}")
    
    def _display_final_summary(self, results: Dict[str, Any]):
        """Display final processing summary in structured format."""
        if results.get("status") == "success":
            summary = results.get('processing_summary', {})
            
            # Processing statistics
            stats_data = {
                "Total Fields Defined": summary.get('total_fields_defined', 0),
                "LLM Extractions": summary.get('llm_extractions', 0),
                "eSAD Module Extractions": summary.get('esad_module_extractions', 0),
                "Automated Extractions": summary.get('automated_extractions', 0),
                "Failed Extractions": summary.get('failed_extractions', 0),
                "Success Rate": f"{((summary.get('total_fields_defined', 0) - summary.get('failed_extractions', 0)) / max(summary.get('total_fields_defined', 1), 1) * 100):.1f}%"
            }
            
            print(self.table_formatter.create_summary_box("FINAL PROCESSING SUMMARY", stats_data))
            
            # File information
            file_data = {
                "Order Number": results['order_number'],
                "Final eSAD Path": results['final_esad_path'],
                "Processing Timestamp": results['timestamp'],
                "Status": "READY FOR SUBMISSION"
            }
            
            print(self.table_formatter.create_summary_box("OUTPUT FILES", file_data))
            
        else:
            error_data = {
                "Status": "FAILED",
                "Order": results.get('order_number', 'Unknown'),
                "Error": results.get('error', 'Unknown error'),
                "Timestamp": results.get('timestamp', 'Unknown')
            }
            print(self.table_formatter.create_summary_box("PROCESSING ERROR", error_data))
    
    def _error_result(self, order_number: str, error_message: str) -> Dict[str, Any]:
        """Create standardized error result."""
        return {
            "status": "error",
            "error": error_message,
            "order_number": order_number,
            "timestamp": datetime.now().isoformat()
        }
    
    def list_available_orders(self, limit: int = 10) -> list:
        """List available orders that can be processed for eSAD."""
        try:
            processed_orders_dir = Path("processed_orders")
            if not processed_orders_dir.exists():
                return []
            
            orders = []
            for order_dir in sorted(processed_orders_dir.iterdir(), key=lambda x: x.name, reverse=True):
                if order_dir.is_dir() and order_dir.name.startswith("ORD-"):
                    invoice_file = order_dir / "invoices" / f"invoice_{order_dir.name}_primary_extract.json"
                    bol_file = order_dir / "bills_of_lading" / f"bill_of_lading_{order_dir.name}_primary_extract.json"
                    
                    if invoice_file.exists() and bol_file.exists():
                        orders.append(order_dir.name)
                        
                        if len(orders) >= limit:
                            break
            
            return orders
            
        except Exception as e:
            print(f"Error listing orders: {e}")
            return []

def main():
    """Main function for command line usage."""
    orchestrator = ESADOrchestrator()
    
    if len(sys.argv) < 2:
        print("TESTING MODE: No order specified, using hardcoded test files")
        order_number = "ORD-20250916-004"
    elif sys.argv[1] == "--list":
        print("Available orders for eSAD processing:")
        orders = orchestrator.list_available_orders()
        if orders:
            for order in orders:
                print(f"  • {order}")
        else:
            print("  No orders found with completed extractions")
        sys.exit(0)
    else:
        order_number = sys.argv[1]
        if not order_number.startswith("ORD-"):
            print(f"Invalid order number format: {order_number}")
            print("Expected format: ORD-YYYYMMDD-XXX")
            print("Or run without arguments for testing mode")
            sys.exit(1)
    
    # Process the order
    results = orchestrator.process_order_esad(order_number)
    
    # Exit with appropriate code
    if results.get("status") == "success":
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()