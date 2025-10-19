import os
import json
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime

# Import log formatter
try:
    from modules.utils.log_formatter import LogFormatter
except ImportError:
    # Fallback if log_formatter not available
    class LogFormatter:
        @staticmethod
        def print_section_header(num, title):
            print(f"\n{'=' * 80}\n## {num}. {title}\n{'=' * 80}")
        @staticmethod
        def print_subsection_header(num, title):
            print(f"\n### {num} {title}\n{'-' * 60}")
        @staticmethod
        def print_json(data, indent=2):
            import json
            print(json.dumps(data, indent=indent))
        @staticmethod
        def print_status(msg, status="info"):
            emoji = {"success": "✅", "error": "❌", "warning": "⚠️", "processing": "🔄"}.get(status, "•")
            print(f"{emoji} {msg}")

# Import eSAD processing modules
try:
    # Try relative imports first (when used as module)
    from .esad_modules.core.esad_product import ProductProcessor
    from .esad_modules.core.esad_regime import RegimeTypeProcessor
    from .esad_modules.core.esad_manifest import ManifestProcessor, ManifestTracker
    from .esad_modules.core.esad_cif import CIFProcessor
    from .esad_modules.core.esad_office_code import OfficeCodeProcessor
    
    # Import secondary modules
    from .esad_modules.secondary.esad_address import AddressFormatter
    from .esad_modules.secondary.esad_pkg import PackageProcessor
    from .esad_modules.secondary.esad_transport_mode import TransportModeProcessor
    from .esad_modules.secondary.esad_weight import process_weight_data
    from .esad_modules.secondary.esad_marks import MarksProcessor
    from .esad_modules.secondary.esad_warehouse import WarehouseProcessor
    from .esad_modules.secondary.esad_country import CountryProcessor
    from .esad_modules.secondary.esad_location import LocationProcessor
    from .esad_modules.secondary.esad_locode import LocodeProcessor
    from .esad_modules.secondary.esad_ref_number import CommercialReferenceProcessor
    from .esad_modules.secondary.esad_trans_type import TransactionTypeProcessor
    from .esad_modules.secondary.esad_trn import TRNLookupProcessor
except ImportError:
    # Fallback to absolute imports (when run from application context)
    import sys
    import os
    
    # Add the esad_processor directory to the path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, current_dir)
    
    from esad_modules.core.esad_product import ProductProcessor
    from esad_modules.core.esad_regime import RegimeTypeProcessor
    from esad_modules.core.esad_manifest import ManifestProcessor, ManifestTracker
    from esad_modules.core.esad_cif import CIFProcessor
    from esad_modules.core.esad_office_code import OfficeCodeProcessor
    
    # Import secondary modules
    from esad_modules.secondary.esad_address import AddressFormatter
    from esad_modules.secondary.esad_pkg import PackageProcessor
    from esad_modules.secondary.esad_transport_mode import TransportModeProcessor
    from esad_modules.secondary.esad_weight import process_weight_data
    from esad_modules.secondary.esad_marks import MarksProcessor
    from esad_modules.secondary.esad_warehouse import WarehouseProcessor
    from esad_modules.secondary.esad_country import CountryProcessor
    from esad_modules.secondary.esad_location import LocationProcessor
    from esad_modules.secondary.esad_locode import LocodeProcessor
    from esad_modules.secondary.esad_ref_number import CommercialReferenceProcessor
    from esad_modules.secondary.esad_trans_type import TransactionTypeProcessor
    from esad_modules.secondary.esad_trn import TRNLookupProcessor


def save_commodity_code_data(order_number: str, invoice_key: str, product_result: Dict[str, Any]) -> bool:
    """
    Save commodity code classification data to JSON file in the order's commodity_code directory.
    
    Args:
        order_number: The order number (e.g., "ORD-20250927-001")
        invoice_key: The invoice key (e.g., "invoice_1")
        product_result: Dictionary containing product classification results
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Define the base path for processed orders
        base_path = Path("processed_orders")
        order_path = base_path / order_number
        commodity_code_path = order_path / "commodity_code"
        
        # Create commodity_code directory if it doesn't exist
        commodity_code_path.mkdir(parents=True, exist_ok=True)
        
        # Create filename based on invoice key
        filename = f"{invoice_key}_classification.json"
        file_path = commodity_code_path / filename
        
        # Prepare the data structure
        commodity_data = {
            "invoice_key": invoice_key,
            "timestamp": datetime.now().isoformat(),
            "classification": {
                "success": product_result.get('success', False),
                "commercial_description": product_result.get('commercial_description', ''),
                "commodity_code": product_result.get('commodity_code', ''),
                "hs_code": product_result.get('hs_code', ''),
                "hs_description": product_result.get('hs_description', ''),
                "original_description": product_result.get('original_description', ''),
                "processing_notes": product_result.get('processing_notes', ''),
                "error": product_result.get('error', '') if not product_result.get('success', False) else None
            },
            "metadata": {
                "order_number": order_number,
                "processing_date": datetime.now().strftime("%Y-%m-%d"),
                "processing_time": datetime.now().strftime("%H:%M:%S")
            }
        }
        
        # Write to JSON file
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(commodity_data, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Saved commodity code data: {file_path}")
        return True
        
    except Exception as e:
        print(f"❌ Error saving commodity code data: {e}")
        return False


class ESADProcessor:
    """
    Main processor for handling eSAD (electronic Single Administrative Document) 
    generation from extracted bill of lading and invoice data.
    """
    
    def __init__(self, base_processed_orders_path: str = None):
        """
        Initialize the ESAD processor.
        
        Args:
            base_processed_orders_path: Base path to processed orders directory
        """
        if base_processed_orders_path is None:
            # Default to the project's processed_orders directory
            current_dir = Path(__file__).parent.parent.parent
            self.base_path = current_dir / "processed_orders"
        else:
            self.base_path = Path(base_processed_orders_path)
    
    def locate_order_folder(self, order_number: str) -> Optional[Path]:
        """
        Locate the folder for a specific order number in the processed_orders directory.
        
        Args:
            order_number: The order number to locate (e.g., 'ORD-20250915-007')
            
        Returns:
            Path to the order folder if found, None otherwise
        """
        order_path = self.base_path / order_number
        
        if order_path.exists() and order_path.is_dir():
            return order_path
        else:
            print(f"Order folder not found: {order_path}")
            return None
    
    def load_document_data(self, order_folder: Path, document_type: str) -> Optional[Dict[str, Any]]:
        """
        Load document data from the order folder.
        
        Args:
            order_folder: Path to the order folder
            document_type: Type of document to load (e.g., 'bills_of_lading', 'invoices')
            
        Returns:
            Dictionary containing document data, None if not found
        """
        doc_folder = order_folder / document_type
        
        if not doc_folder.exists():
            print(f"{document_type} folder not found: {doc_folder}")
            return None
        
        # Look for JSON files in the document folder
        json_files = list(doc_folder.glob("*.json"))
        
        if not json_files:
            print(f"No JSON files found in {document_type} folder: {doc_folder}")
            return None
        
        # Load the first JSON file found
        doc_file = json_files[0]
        
        try:
            with open(doc_file, 'r', encoding='utf-8') as f:
                doc_data = json.load(f)
            print(f"Successfully loaded {document_type} from: {doc_file.name}")
            return doc_data
        except Exception as e:
            print(f"Error loading {document_type} from {doc_file}: {e}")
            return None
    
    
    def load_order_data(self, order_number: str) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """
        Load both bill of lading and invoice data for a specific order.
        
        Args:
            order_number: The order number to load data for
            
        Returns:
            Tuple of (bill_of_lading_data, invoice_data)
        """
        order_folder = self.locate_order_folder(order_number)
        
        if order_folder is None:
            return None, None
        
        bol_data = self.load_document_data(order_folder, "bills_of_lading")
        invoice_data = self.load_multiple_invoices(order_folder)
        
        return bol_data, invoice_data
    
    def load_multiple_invoices(self, order_folder: Path) -> Optional[Dict[str, Any]]:
        """
        Load all invoice data from the order folder.
        
        Args:
            order_folder: Path to the order folder
            
        Returns:
            Dictionary containing all invoice data, None if not found
        """
        invoice_folder = order_folder / "invoices"
        
        if not invoice_folder.exists():
            print(f"Invoices folder not found: {invoice_folder}")
            return None
        
        # Look for all JSON files in the invoices folder
        json_files = list(invoice_folder.glob("*.json"))
        
        if not json_files:
            print(f"No JSON files found in invoices folder: {invoice_folder}")
            return None
        
        # Load all invoice files
        invoices_data = {}
        for i, invoice_file in enumerate(json_files):
            try:
                with open(invoice_file, 'r', encoding='utf-8') as f:
                    invoice_data = json.load(f)
                invoices_data[f"invoice_{i+1}"] = invoice_data
                print(f"Successfully loaded invoice {i+1} from: {invoice_file.name}")
            except Exception as e:
                print(f"Error loading invoice {i+1} from {invoice_file}: {e}")
        
        if not invoices_data:
            return None
        
        # Return the first invoice for backward compatibility, but include all invoices
        first_invoice = list(invoices_data.values())[0]
        first_invoice['_all_invoices'] = invoices_data
        first_invoice['_invoice_count'] = len(invoices_data)
        
        return first_invoice
    
    def process_esad(self, order_number: str, json_mode: bool = False) -> Dict[str, Any]:
        """
        Main processing function for eSAD generation.
        
        Args:
            order_number: The order number to process
            json_mode: If True, suppress console output and return JSON. If False, print to console and return simple status.
            
        Returns:
            Dict containing all processing results in structured JSON format
        """
        # Initialize result structure
        result = {
            "order_number": order_number,
            "success": False,
            "timestamp": datetime.now().isoformat(),
            "stages": {},
            "errors": []
        }
        
        def log(message: str, level: str = "info"):
            """Helper to log messages conditionally based on json_mode"""
            if not json_mode:
                print(message)
        
        # Log eSAD processing start with structured format
        if not json_mode:
            start_data = {
                "event": "esad_processing_start",
                "order_id": order_number,
                "status": "starting"
            }
            LogFormatter.print_json(start_data)
            LogFormatter.print_status(f"Starting eSAD processing for order: {order_number}", "processing")
        
        # Load the order data
        bol_data, invoice_data = self.load_order_data(order_number)
        
        if bol_data is None or invoice_data is None:
            error_msg = "Failed to load required data for eSAD processing"
            log(error_msg)
            result["errors"].append(error_msg)
            result["success"] = False
            return result if json_mode else False
        
        if not json_mode:
            LogFormatter.print_subsection_header("6.1", "Data Loading")
            data_loading_result = {
                "event": "esad_data_loading",
                "order_id": order_number,
                "status": "success",
                "data_loaded": {
                    "bills_of_lading": bol_data is not None,
                    "invoices": invoice_data.get('_invoice_count', 1)
                }
            }
            LogFormatter.print_json(data_loading_result)
            LogFormatter.print_status("Successfully loaded both bill of lading and invoice data", "success")
        
        result["stages"]["data_loading"] = {
            "success": True,
            "invoice_count": invoice_data.get('_invoice_count', 1),
            "bol_present": bol_data is not None
        }
        
        # Display critical data only
        log("=" * 50)
        
        # Display invoice data - all fields
        if invoice_data:
            invoice_count = invoice_data.get('_invoice_count', 1)
            if invoice_count > 1:
                log(f"✅ Loaded {invoice_count} invoice files")
                all_invoices = invoice_data.get('_all_invoices', {})
                for invoice_key, invoice_info in all_invoices.items():
                    log(f"📋 {invoice_key.upper()}:")
                    if not json_mode:
                        self._print_invoice_details(invoice_info)
            else:
                log("📋 Invoice Data:")
                if not json_mode:
                    self._print_invoice_details(invoice_data)
        
        # Display BOL data - all fields
        if bol_data:
            log("📋 BOL Data:")
            if not json_mode:
                self._print_bol_details(bol_data)
        
        log("=" * 50)
        
        # Initialize all processors
        log("🔍 Initializing eSAD processors...")
        product_processor = ProductProcessor()
        regime_processor = RegimeTypeProcessor()
        manifest_processor = ManifestProcessor({})
        cif_processor = CIFProcessor()
        
        # Prepare base input data structure
        base_input_data = {
            'invoice_data': invoice_data,
            'bol_data': bol_data,
            'fields': [],
            'existing_fields': {
                'order_number': order_number,
                'order_id': order_number
            }
        }
        
        # Process product information using ProductProcessor
        if not json_mode:
            LogFormatter.print_subsection_header("6.2", "Product Classification")
        log("\n📦 Processing product information...")
        log("=" * 50)
        
        # Handle multiple invoices for product processing
        if invoice_data and invoice_data.get('_invoice_count', 1) > 1:
            log(f"   Processing {invoice_data.get('_invoice_count', 1)} invoices for product classification...")
            
            # Process each invoice separately
            all_invoices = invoice_data.get('_all_invoices', {})
            product_results = {}
            
            for invoice_key, invoice_info in all_invoices.items():
                log(f"   Processing {invoice_key}...")
                
                # Prepare input data for ProductProcessor
                input_data = base_input_data.copy()
                input_data['invoice_data'] = invoice_info
                
                # Process the product information for this invoice
                product_result = product_processor.process(input_data)
                product_results[invoice_key] = product_result
        else:
            # Single invoice processing (backward compatibility)
            product_result = product_processor.process(base_input_data)
            product_results = {'invoice_1': product_result}
        
        # Capture product processing results
        result["stages"]["product_processing"] = {}
        
        # Display product processing results and save commodity code data
        for invoice_key, product_result in product_results.items():
            log(f"\n--- {invoice_key.upper()} PRODUCT CLASSIFICATION ---")
            
            # Add to JSON result
            result["stages"]["product_processing"][invoice_key] = product_result
            
            if product_result['success']:
                log(f"✅ Success: {product_result['success']}")
                
                # Output JSON format
                classification_data = {
                    "commercial_description": product_result['commercial_description'],
                    "hs_code": product_result['hs_code'],
                    "hs_description": product_result['hs_description'],
                    "commodity_code": product_result['commodity_code']
                }
                log(f"\n{'='*60}")
                log(f"CLASSIFICATION RESULTS (JSON Format)")
                log(f"{'='*60}\n")
                if not json_mode:
                    print(json.dumps(classification_data, indent=2))
                
                log(f"\n📄 Original Description: {product_result['original_description']}")
                log(f"📊 Processing Notes: {product_result['processing_notes']}")
            else:
                log(f"❌ Processing Failed: {product_result['error']}")
                log(f"📋 Commercial Description: {product_result['commercial_description']}")
                log(f"🏷️  Commodity Code: {product_result['commodity_code']}")
            
            # Commodity code data will be saved as part of consolidated ESAD results
        
        # Process CIF components using CIFProcessor
        if not json_mode:
            LogFormatter.print_subsection_header("6.3", "CIF Processing")
        log("\n💰 Processing CIF components...")
        log("=" * 50)
        
        cif_result = cif_processor.process(base_input_data)
        result["stages"]["cif_processing"] = cif_result
        
        if cif_result['success']:
            log(f"✅ CIF Processing Successful")
            
            # Output JSON format
            cif_data = {
                "cost": cif_result.get('val_note_invoice_value_goods_only', 0) or 0,
                "freight": cif_result.get('val_note_freight_charges_invoice', 0) or cif_result.get('val_note_freight_charges_bol', 0) or 0,
                "cost_and_freight": cif_result.get('val_note_cost_and_freight', 0) or 0,
                "insurance": cif_result.get('val_note_insurance_charges_invoice', 0) or cif_result.get('val_note_insurance_charges_bol', 0) or 0,
                "cif_value": cif_result.get('val_note_cif', 0) or 0
            }
            log(f"\n{'='*60}")
            log(f"CIF RESULTS (JSON Format)")
            log(f"{'='*60}\n")
            if not json_mode:
                print(json.dumps(cif_data, indent=2))
            
            # Safely display invoice total
            invoice_total = cif_result.get('val_note_invoice_total_including_freight')
            if invoice_total is not None:
                try:
                    log(f"\n📋 Invoice Total: ${float(invoice_total):,.2f}")
                except (ValueError, TypeError):
                    log(f"\n📋 Invoice Total: {invoice_total}")
            else:
                log("\n📋 Invoice Total: Not found")
            
            log(f"💱 Invoice Currency: {cif_result.get('invoice_currency', 'Not found')}")
            log(f"📋 Incoterms: {cif_result.get('incoterms', 'Not found')}")
        else:
            log(f"❌ CIF Processing Failed: {cif_result['error']}")
        
        # Process regime type using RegimeTypeProcessor (after CIF processing)
        if not json_mode:
            LogFormatter.print_subsection_header("6.4", "Regime Type Determination")
        log("\n🏛️ Processing regime type...")
        log("=" * 50)
        
        # Add CIF result to input data for regime determination
        base_input_data['cif_result'] = cif_result
        
        regime_result = regime_processor.determine_regime_type(base_input_data)
        
        # Capture regime result to JSON (convert RegimeTypeResult to dict)
        result["stages"]["regime_determination"] = {
            "regime_type": regime_result.regime_type,
            "procedure_code": regime_result.procedure_code,
            "description": regime_result.description,
            "confidence": regime_result.confidence,
            "reasoning": regime_result.reasoning,
            "import_export_direction": regime_result.import_export_direction,
            "commercial_determination": regime_result.commercial_determination,
            "contextual_factors": regime_result.contextual_factors,
            "processing_time": regime_result.processing_time,
            "model": regime_result.model
        }
        
        # Display commercial/personal classification reasoning first
        product_classification = regime_result.contextual_factors.get('product_classification', {})
        if product_classification:
            log(f"\n📦 COMMERCIAL/PERSONAL CLASSIFICATION:")
            log(f"   └── Classification: {product_classification.get('classification', 'Unknown')}")
            log(f"   └── Confidence: {product_classification.get('confidence', 'unknown')}")
            log(f"   └── Products Analyzed: {product_classification.get('products_analyzed', 0)}")
            
            # Display reasoning
            reasoning = product_classification.get('reasoning', '')
            if reasoning:
                log(f"   └── Reasoning: {reasoning}")
            
            # Display contextual reasoning if available
            contextual_reasoning = product_classification.get('contextual_reasoning', '')
            if contextual_reasoning:
                log(f"   └── Contextual Analysis: {contextual_reasoning}")
            
            # Display indicators
            commercial_indicators = product_classification.get('commercial_indicators', [])
            if commercial_indicators:
                log(f"   └── Commercial Indicators: {', '.join(commercial_indicators)}")
            
            personal_indicators = product_classification.get('personal_indicators', [])
            if personal_indicators:
                log(f"   └── Personal Indicators: {', '.join(personal_indicators)}")
            
            grey_zone = product_classification.get('grey_zone_products', [])
            if grey_zone:
                log(f"   └── Grey Zone Products: {', '.join(grey_zone)}")
        
        # Display regime type determination
        log(f"\n🏛️ REGIME TYPE DETERMINATION:")
        log(f"✅ Regime Type: {regime_result.regime_type}")
        log(f"📋 Description: {regime_result.description}")
        log(f"🔢 Procedure Code: {regime_result.procedure_code}")
        log(f"📊 Confidence: {regime_result.confidence}")
        log(f"💭 Reasoning: {regime_result.reasoning}")
        log(f"🌍 Direction: {regime_result.import_export_direction}")
        log(f"🏢 Commercial: {regime_result.commercial_determination}")
        
        # Process manifest using ManifestProcessor
        if not json_mode:
            LogFormatter.print_subsection_header("6.5", "Manifest Processing")
        log("\n📋 Processing manifest...")
        log("=" * 50)
        
        # Extract BOL number for manifest tracking
        bol_number = None
        if bol_data:
            bol_candidates = [
                bol_data.get('sea_waybill_no', ''),
                bol_data.get('air_waybill_number', ''),
                bol_data.get('document_number', ''),
                bol_data.get('bill_of_lading', '')
            ]
            
            for bol in bol_candidates:
                if bol and bol.strip():
                    bol_number = bol.strip()
                    break
        
        manifest_data = {}
        if bol_number:
            log(f"🎯 Found BOL number: {bol_number}")
            
            # Initialize manifest tracker
            manifest_tracker = ManifestTracker()
            
            # Track BOL (this will open browser and extract manifest data)
            manifest_result = manifest_tracker.track_bol(bol_number)
            
            if manifest_result.success:
                log(f"✅ Manifest Tracking Successful")
                log(f"📋 Total Entries: {manifest_result.total_entries}")
                log(f"🌐 Tracking URL: {manifest_result.tracking_url}")
                
                # Get manifest results for consolidation
                manifest_results = manifest_tracker.save_manifest_results(manifest_result)
                log(f"💾 Manifest results prepared for consolidation")
                
                # Process manifest data
                manifest_input = {'manifest_registration_number': bol_number}
                manifest_processed = manifest_processor.process(manifest_input)
                
                if manifest_processed['success']:
                    log(f"✅ Manifest Processed: {manifest_processed['manifest_processed']}")
                else:
                    log(f"❌ Manifest Processing Failed: {manifest_processed['error']}")
                
                # Capture manifest data for consolidation
                manifest_data = {
                    "success": True,
                    "bol_number": bol_number,
                    "total_entries": manifest_result.total_entries,
                    "tracking_url": manifest_result.tracking_url,
                    "manifest_results": manifest_results,
                    "processed": manifest_processed
                }
            else:
                log(f"❌ Manifest Tracking Failed: {manifest_result.error_message}")
                manifest_data = {
                    "success": False,
                    "bol_number": bol_number,
                    "error": manifest_result.error_message
                }
        else:
            log("❌ No BOL number found for manifest tracking")
            manifest_data = {
                "success": False,
                "error": "No BOL number found"
            }
        
        result["stages"]["manifest_processing"] = manifest_data
        
        # Process secondary eSAD fields using Secondary Processors
        if not json_mode:
            LogFormatter.print_section_header(7, "SECONDARY eSAD FIELDS")
        log("\n🔧 Processing secondary eSAD fields...")
        log("=" * 50)
        
        # Initialize secondary processors
        address_formatter = AddressFormatter()
        package_processor = PackageProcessor()
        transport_processor = TransportModeProcessor()
        marks_processor = MarksProcessor()
        warehouse_processor = WarehouseProcessor()
        country_processor = CountryProcessor()
        location_processor = LocationProcessor()
        locode_processor = LocodeProcessor()
        ref_number_processor = CommercialReferenceProcessor()
        trans_type_processor = TransactionTypeProcessor()
        trn_processor = TRNLookupProcessor()
        
        # Initialize secondary results dict
        result["stages"]["secondary_processing"] = {}
        
        # Process addresses
        if not json_mode:
            LogFormatter.print_subsection_header("7.2", "Addresses (Box 2 & 8)")
        log("\n🏠 BOX 2 & BOX 8: Processing addresses (Exporter/Consignee)...")
        try:
            # Extract detailed consignor/consignee information
            if bol_data:
                address_result = address_formatter.extract_consignor_consignee(bol_data)
                result["stages"]["secondary_processing"]["addresses"] = address_result
                
                # Format Consignor output vertically
                if not json_mode:
                    print('"consignor": {')
                    consignor = address_result['consignor']
                    print(f'    "name": "{consignor["name"]}",')
                    print(f'    "street": "{consignor["street"]}",')
                    print(f'    "city": "{consignor["city"]}",')
                    print(f'    "country": "{consignor["country"]}"')
                    print('  }')
                    
                    # Format Consignee output vertically
                    print('"consignee": {')
                    consignee = address_result['consignee']
                    print(f'    "name": "{consignee["name"]}",')
                    print(f'    "street": "{consignee["street"]}",')
                    print(f'    "city": "{consignee["city"]}",')
                    print(f'    "country": "{consignee["country"]}"')
                    print('  }')
        except Exception as e:
            error_msg = f"Address processing failed: {e}"
            log(f"❌ {error_msg}")
            result["stages"]["secondary_processing"]["addresses"] = {"success": False, "error": str(e)}
        
        # Process package types
        if not json_mode:
            LogFormatter.print_subsection_header("7.3", "Package Types (Box 31)")
        log("\n📦 BOX 31: Processing package types...")
        try:
            package_input = base_input_data.copy()
            package_result = package_processor.process(package_input)
            result["stages"]["secondary_processing"]["package"] = package_result
            if package_result['success']:
                log(f"✅ Package Type: {package_result.get('package_code', 'N/A')}")
            else:
                log(f"❌ Package processing failed: {package_result.get('error', 'Unknown error')}")
        except Exception as e:
            error_msg = f"Package processing failed: {e}"
            log(f"❌ {error_msg}")
            result["stages"]["secondary_processing"]["package"] = {"success": False, "error": str(e)}
        
        # Process transport mode
        if not json_mode:
            LogFormatter.print_subsection_header("7.4", "Transport Mode (Box 25)")
        log("\n🚢 BOX 25: Processing transport mode at border...")
        try:
            transport_input = base_input_data.copy()
            transport_result = transport_processor.process(transport_input)
            result["stages"]["secondary_processing"]["transport"] = transport_result
            if transport_result['success']:
                log(f"✅ Transport Mode: {transport_result.get('transport_code', 'N/A')}")
            else:
                log(f"❌ Transport processing failed: {transport_result.get('error', 'Unknown error')}")
        except Exception as e:
            error_msg = f"Transport processing failed: {e}"
            log(f"❌ {error_msg}")
            result["stages"]["secondary_processing"]["transport"] = {"success": False, "error": str(e)}
        
        # Process weights
        if not json_mode:
            LogFormatter.print_subsection_header("7.5", "Weights (Box 35 & 38)")
        log("\n⚖️ BOX 35 (Gross) & BOX 38 (Net): Processing weights...")
        try:
            # Use generic recursive search for weight data
            gross_weight = self._search_for_field(bol_data, ['weight', 'gross_weight', 'gross', 'weight_kg', 'weight_kgs'])
            net_weight = self._search_for_field(bol_data, ['net_weight', 'net', 'nett_weight'])
            
            # If we found any weight data, process it
            if gross_weight or net_weight:
                processed_weights = process_weight_data(
                    net_weight or '',
                    gross_weight or ''
                )
                result["stages"]["secondary_processing"]["weights"] = processed_weights
                
                # Display results
                log(f"✅ Net Weight: {processed_weights.get('final_net_weight', 'N/A')} ({processed_weights.get('net_weight_source', 'N/A')})")
                log(f"✅ Gross Weight: {processed_weights.get('final_gross_weight', 'N/A')}")
                # Display validation status
                if processed_weights.get('validation_status'):
                    log(f"   Validation: ✅ {processed_weights.get('validation_reason', '')}")
                else:
                    log(f"   Validation: ⚠️ {processed_weights.get('validation_reason', '')}")
                # Display as JSON
                weight_json = {
                    'net_weight': processed_weights.get('final_net_weight'),
                    'gross_weight': processed_weights.get('final_gross_weight'),
                    'net_weight_source': processed_weights.get('net_weight_source'),
                    'validation': processed_weights.get('validation_status')
                }
                if not json_mode:
                    print(f"   JSON: {json.dumps(weight_json)}")
            else:
                log("❌ No weight data found")
                result["stages"]["secondary_processing"]["weights"] = {"success": False, "error": "No weight data found"}
        except Exception as e:
            error_msg = f"Weight processing failed: {e}"
            log(f"❌ {error_msg}")
            result["stages"]["secondary_processing"]["weights"] = {"success": False, "error": str(e)}
        
        # Process marks and numbers
        if not json_mode:
            LogFormatter.print_subsection_header("7.6", "Marks and Numbers (Box 31)")
        log("\n📝 BOX 31: Processing marks and numbers...")
        try:
            marks_input = base_input_data.copy()
            marks_result = marks_processor.process(marks_input)
            result["stages"]["secondary_processing"]["marks"] = marks_result
            if marks_result['success']:
                log(f"✅ Marks: {marks_result.get('marks_and_numbers', 'N/A')}")
            else:
                log(f"❌ Marks processing failed: {marks_result.get('error', 'Unknown error')}")
        except Exception as e:
            error_msg = f"Marks processing failed: {e}"
            log(f"❌ {error_msg}")
            result["stages"]["secondary_processing"]["marks"] = {"success": False, "error": str(e)}
        
        # Process warehouse information
        if not json_mode:
            LogFormatter.print_subsection_header("7.7", "Warehouse (Box 49)")
        log("\n🏢 BOX 49: Processing warehouse information...")
        try:
            warehouse_input = base_input_data.copy()
            warehouse_result = warehouse_processor.process(warehouse_input)
            result["stages"]["secondary_processing"]["warehouse"] = warehouse_result
            if warehouse_result['success']:
                if warehouse_result.get('requires_warehouse', False):
                    log(f"✅ Warehouse: {warehouse_result.get('warehouse_code', 'N/A')}")
                    if warehouse_result.get('warehouse_name'):
                        log(f"   Name: {warehouse_result.get('warehouse_name')}")
                else:
                    log(f"✅ Box 49 left blank (no warehousing CPC)")
            else:
                if warehouse_result.get('requires_warehouse', False):
                    log(f"❌ Warehouse processing failed: {warehouse_result.get('error', 'Unknown error')}")
                else:
                    log(f"✅ Box 49 not required (no warehousing CPC)")
        except Exception as e:
            error_msg = f"Warehouse processing failed: {e}"
            log(f"❌ {error_msg}")
            result["stages"]["secondary_processing"]["warehouse"] = {"success": False, "error": str(e)}
        
        # Convert country codes
        if not json_mode:
            LogFormatter.print_subsection_header("7.8", "Country Processing (Box 15 & 17)")
        log("\n🌍 Processing country codes...")
        try:
            country_input = base_input_data.copy()
            country_input['regime_result'] = regime_result
            country_result = country_processor.process(country_input)
            result["stages"]["secondary_processing"]["countries"] = country_result
            if country_result.get('success'):
                log(f"✅ Country codes processed successfully")
            else:
                log(f"⚠️ Country processing completed with fallback")
        except Exception as e:
            error_msg = f"Country processing failed: {e}"
            log(f"❌ {error_msg}")
            result["stages"]["secondary_processing"]["countries"] = {"success": False, "error": str(e)}
        
        # Process office code and warehouse information
        if not json_mode:
            LogFormatter.print_subsection_header("7.9", "Office Code & Manifest Info")
        log("\n🏢 Processing office code and manifest information...")
        try:
            office_code_processor = OfficeCodeProcessor()
            office_code_input = base_input_data.copy()
            office_code_result = office_code_processor.process(office_code_input)
            result["stages"]["secondary_processing"]["office_code"] = office_code_result
            
            if office_code_result.get('success'):
                log(f"✅ Office code processing successful")
                if office_code_result.get('office_of_submission'):
                    log(f"   └─ Office of Submission: {office_code_result.get('office_of_submission')}")
                if office_code_result.get('asycuda_number'):
                    log(f"   └─ Asycuda/Manifest Number: {office_code_result.get('asycuda_number')}")
                if office_code_result.get('wharfinger'):
                    log(f"   └─ Wharfinger: {office_code_result.get('wharfinger')}")
                if office_code_result.get('matched_warehouse'):
                    warehouse = office_code_result.get('matched_warehouse', {})
                    log(f"   └─ Matched Warehouse: {warehouse.get('warehouse', 'N/A')}")
                    log(f"   └─ Office ID: {warehouse.get('office_id', 'N/A')}")
            else:
                log(f"⚠️ Office code processing completed with fallback")
                if office_code_result.get('error'):
                    log(f"   └─ Error: {office_code_result.get('error')}")
        except Exception as e:
            log(f"❌ Office code processing failed: {e}")
            office_code_result = {"success": False, "error": str(e)}
            result["stages"]["secondary_processing"]["office_code"] = office_code_result
        
        # Process location information (uses office_code_result)
        if not json_mode:
            LogFormatter.print_subsection_header("7.10", "Location (Box 30)")
        log("\n📍 BOX 30 (Location of goods): Processing warehouse location...")
        try:
            location_input = base_input_data.copy()
            location_input['office_code_result'] = office_code_result
            location_result = location_processor.process(location_input)
            result["stages"]["secondary_processing"]["location"] = location_result
            if location_result['success']:
                log(f"✅ Warehouse Code: {location_result.get('location_code', 'N/A')}")
                log(f"   └─ Warehouse: {location_result.get('warehouse_name', 'N/A')}")
                log(f"   └─ Office ID: {location_result.get('office_id', 'N/A')}")
            else:
                log(f"❌ Location processing failed: {location_result.get('error', 'Unknown error')}")
        except Exception as e:
            error_msg = f"Location processing failed: {e}"
            log(f"❌ {error_msg}")
            result["stages"]["secondary_processing"]["location"] = {"success": False, "error": str(e)}
        
        # Process LOCODE information
        if not json_mode:
            LogFormatter.print_subsection_header("7.11", "LOCODE (Box 27)")
        log("\n🚢 BOX 27 (Place of unloading): Processing LOCODE...")
        try:
            locode_input = base_input_data.copy()
            locode_result = locode_processor.process(locode_input)
            result["stages"]["secondary_processing"]["locode"] = locode_result
            if locode_result['success']:
                log(f"✅ Jamaican Port: {locode_result.get('jamaican_port', 'N/A')}")
                log(f"   └─ LOCODE: {locode_result.get('locode', 'N/A')}")
                log(f"   └─ Location: {locode_result.get('location_name', 'N/A')}")
            else:
                log(f"❌ LOCODE processing failed: {locode_result.get('error', 'Unknown error')}")
        except Exception as e:
            error_msg = f"LOCODE processing failed: {e}"
            log(f"❌ {error_msg}")
            result["stages"]["secondary_processing"]["locode"] = {"success": False, "error": str(e)}
        
        # Process reference numbers
        if not json_mode:
            LogFormatter.print_subsection_header("7.12", "Reference Numbers (Box 7)")
        log("\n🔢 BOX 7: Processing reference numbers...")
        try:
            ref_input = base_input_data.copy()
            ref_result = ref_number_processor.process(ref_input)
            result["stages"]["secondary_processing"]["reference_numbers"] = ref_result
            if ref_result['success']:
                log(f"✅ Reference Number: {ref_result.get('reference_number', 'N/A')}")
            else:
                log(f"❌ Reference processing failed: {ref_result.get('error', 'Unknown error')}")
        except Exception as e:
            error_msg = f"Reference processing failed: {e}"
            log(f"❌ {error_msg}")
            result["stages"]["secondary_processing"]["reference_numbers"] = {"success": False, "error": str(e)}
        
        # Process transaction type
        if not json_mode:
            LogFormatter.print_subsection_header("7.13", "Transaction Type (Box 24)")
        log("\n💼 BOX 24: Processing transaction type...")
        try:
            trans_input = base_input_data.copy()
            trans_result = trans_type_processor.process(trans_input)
            result["stages"]["secondary_processing"]["transaction_type"] = trans_result
            if trans_result['success']:
                log(f"✅ Transaction Type: {trans_result.get('transaction_type', 'N/A')}")
            else:
                log(f"❌ Transaction processing failed: {trans_result.get('error', 'Unknown error')}")
        except Exception as e:
            error_msg = f"Transaction processing failed: {e}"
            log(f"❌ {error_msg}")
            result["stages"]["secondary_processing"]["transaction_type"] = {"success": False, "error": str(e)}
        
        # Process TRN (Tax Registration Number)
        if not json_mode:
            LogFormatter.print_subsection_header("7.14", "TRN Lookup (Boxes 2/8)")
        log("\n🏛️ IDs (Boxes 2/8): Processing TRN...")
        try:
            trn_input = base_input_data.copy()
            # Pass the result object so TRN processor can access address data for country checking
            trn_input['result'] = result
            trn_result = trn_processor.process(trn_input)
            result["stages"]["secondary_processing"]["trn"] = trn_result
            if trn_result['success']:
                log(f"✅ TRN: {trn_result.get('trn', 'N/A')}")
            else:
                log(f"❌ TRN processing failed: {trn_result.get('error', 'Unknown error')}")
        except Exception as e:
            error_msg = f"TRN processing failed: {e}"
            log(f"❌ {error_msg}")
            result["stages"]["secondary_processing"]["trn"] = {"success": False, "error": str(e)}
        
        # eSAD Processing Complete
        result["success"] = True
        
        if not json_mode:
            LogFormatter.print_subsection_header("8", "eSAD PROCESSING COMPLETION")
            completion_data = {
                "event": "esad_processing_complete",
                "order_id": order_number,
                "status": "success",
                "timestamp": datetime.now().isoformat()
            }
            LogFormatter.print_json(completion_data)
            LogFormatter.print_status("eSAD Processing Complete", "success")
        
        # Save consolidated ESAD results to order's esad_files folder
        self._save_consolidated_esad_results(order_number, result)
        
        # Return structured JSON when in json_mode, otherwise return boolean for backward compatibility
        if json_mode:
            return result
        else:
            return True
    
    def _save_consolidated_esad_results(self, order_number: str, result: Dict[str, Any]) -> bool:
        """
        Save all ESAD processing results to a single consolidated JSON file in the order's esad_files folder.
        
        Args:
            order_number: The order number
            result: Complete ESAD processing result dictionary
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Define the path for the order's esad_files directory
            order_dir = Path("processed_orders") / order_number
            esad_files_dir = order_dir / "esad_files"
            
            # Create esad_files directory if it doesn't exist
            esad_files_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"esad_processing_results_{timestamp}.json"
            file_path = esad_files_dir / filename
            
            # Prepare consolidated data structure
            consolidated_data = {
                "order_number": order_number,
                "processing_timestamp": datetime.now().isoformat(),
                "processing_status": result.get("success", False),
                "esad_processing": result,
                "metadata": {
                    "generated_by": "ESAD Processor",
                    "version": "1.0",
                    "total_stages": len(result.get("stages", {})),
                    "errors_count": len(result.get("errors", [])),
                    "file_type": "consolidated_esad_results"
                }
            }
            
            # Write consolidated results to JSON file
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(consolidated_data, f, indent=2, ensure_ascii=False)
            
            print(f"💾 Consolidated ESAD results saved to: {file_path}")
            return True
            
        except Exception as e:
            print(f"❌ Error saving consolidated ESAD results: {e}")
            return False
    
    def _search_for_field(self, data: Any, field_names: List[str], depth: int = 0, max_depth: int = 5) -> Optional[str]:
        """
        Recursively search for a field by name in any nested structure.
        Returns the first matching non-empty string value found.
        
        Args:
            data: The data structure to search (dict, list, or primitive)
            field_names: List of field names to search for (case-insensitive)
            depth: Current recursion depth
            max_depth: Maximum recursion depth to prevent infinite loops
            
        Returns:
            The first matching field value as a string, or None if not found
        """
        if depth > max_depth:
            return None
        
        # If it's a dict, search through keys and values
        if isinstance(data, dict):
            # First, look for keys that match our field names (highest priority)
            for key in data.keys():
                key_lower = str(key).lower()
                if any(field_name.lower() == key_lower or field_name.lower() in key_lower for field_name in field_names):
                    value = data[key]
                    if isinstance(value, str) and value.strip():
                        # Validate it's actually weight data (contains units)
                        if any(unit in value.upper() for unit in ['KG', 'LB', 'TON', 'MT', 'TONNE', 'G']):
                            return value.strip()
                    elif isinstance(value, (int, float)):
                        return str(value)
                    elif isinstance(value, (dict, list)):
                        result = self._search_for_field(value, field_names, depth + 1, max_depth)
                        if result:
                            return result
            
            # Then search through all values recursively
            for value in data.values():
                if isinstance(value, (dict, list)):
                    result = self._search_for_field(value, field_names, depth + 1, max_depth)
                    if result:
                        return result
        
        # If it's a list, search through items
        elif isinstance(data, list):
            for item in data:
                result = self._search_for_field(item, field_names, depth + 1, max_depth)
                if result:
                    return result
        
        return None

    def _print_invoice_details(self, invoice_data: Dict[str, Any]) -> None:
        """Print all invoice details in a structured format"""
        # Supplier information
        if 'supplier' in invoice_data and invoice_data['supplier']:
            supplier = invoice_data['supplier']
            print(f"   Supplier: {supplier.get('name', 'N/A')}")
            if 'contact' in supplier and supplier['contact']:
                contact = supplier['contact']
                if contact.get('telephone_header'):
                    print(f"   Supplier Tel: {contact.get('telephone_header')}")
                if contact.get('fax_header'):
                    print(f"   Supplier Fax: {contact.get('fax_header')}")
                if contact.get('contacter_name'):
                    print(f"   Contact Person: {contact.get('contacter_name')}")
                if contact.get('contacter_tel'):
                    print(f"   Contact Tel: {contact.get('contacter_tel')}")
        
        # Buyer information
        if 'buyer' in invoice_data and invoice_data['buyer']:
            buyer = invoice_data['buyer']
            print(f"   Buyer: {buyer.get('name', 'N/A')}")
            if buyer.get('address'):
                print(f"   Buyer Address: {buyer.get('address')}")
        
        # Invoice details
        if 'invoice_details' in invoice_data and invoice_data['invoice_details']:
            details = invoice_data['invoice_details']
            print(f"   Document Type: {details.get('document_title', 'N/A')}")
            print(f"   Invoice Number: {details.get('invoice_number', 'N/A')}")
            print(f"   Date: {details.get('date', 'N/A')}")
        
        # Items
        if 'items' in invoice_data and invoice_data['items']:
            print(f"   Items ({len(invoice_data['items'])}):")
            for i, item in enumerate(invoice_data['items'], 1):
                print(f"     {i}. {item.get('description', 'N/A')}")
                print(f"        Item No: {item.get('item_no', 'N/A')}")
                print(f"        Qty: {item.get('quantity', 'N/A')} | Unit Price: ${item.get('unit_price', 'N/A')} | Total: ${item.get('total_price', 'N/A')}")
        
        # Totals
        if 'totals' in invoice_data and invoice_data['totals']:
            totals = invoice_data['totals']
            print(f"   Subtotal: ${totals.get('subtotal', 'N/A')}")
            if totals.get('tax_amount'):
                print(f"   Tax: ${totals.get('tax_amount')}")
            if totals.get('shipping_cost'):
                print(f"   Shipping: ${totals.get('shipping_cost')}")
            print(f"   Total Amount: ${totals.get('total_amount', 'N/A')}")
            if totals.get('currency'):
                print(f"   Currency: {totals.get('currency')}")
        
        # Additional fields
        if invoice_data.get('shipping'):
            shipping = invoice_data['shipping']
            if shipping.get('method'):
                print(f"   Shipping Method: {shipping.get('method')}")
        
        if invoice_data.get('payment_terms'):
            print(f"   Payment Terms: {invoice_data.get('payment_terms')}")
        
        if invoice_data.get('currency'):
            print(f"   Currency: {invoice_data.get('currency')}")
        
        if invoice_data.get('document_type'):
            print(f"   Document Type: {invoice_data.get('document_type')}")
        
        if invoice_data.get('extraction_confidence'):
            print(f"   Extraction Confidence: {invoice_data.get('extraction_confidence')}")

    def _print_bol_details(self, bol_data: Dict[str, Any]) -> None:
        """Print all BOL details in a structured format"""
        # Document information
        if bol_data.get('document_type'):
            print(f"   Document Type: {bol_data.get('document_type')}")
        if bol_data.get('document_number'):
            print(f"   Document Number: {bol_data.get('document_number')}")
        if bol_data.get('document_title'):
            print(f"   Document Title: {bol_data.get('document_title')}")
        
        # BOL Numbers
        if bol_data.get('bill_of_lading'):
            print(f"   BOL Number: {bol_data.get('bill_of_lading')}")
        if bol_data.get('master_bill_of_lading'):
            print(f"   Master BOL: {bol_data.get('master_bill_of_lading')}")
        if bol_data.get('booking_number'):
            print(f"   Booking Number: {bol_data.get('booking_number')}")
        
        # Shipper information
        if 'shipper' in bol_data and bol_data['shipper']:
            shipper = bol_data['shipper']
            if shipper.get('name'):
                print(f"   Shipper: {shipper.get('name')}")
            if shipper.get('address'):
                print(f"   Shipper Address: {shipper.get('address')}")
            if shipper.get('country'):
                print(f"   Shipper Country: {shipper.get('country')}")
        
        # Consignee information
        if 'consignee' in bol_data and bol_data['consignee']:
            consignee = bol_data['consignee']
            if consignee.get('name'):
                print(f"   Consignee: {consignee.get('name')}")
            if consignee.get('address'):
                print(f"   Consignee Address: {consignee.get('address')}")
            if consignee.get('city'):
                print(f"   Consignee City: {consignee.get('city')}")
            if consignee.get('country'):
                print(f"   Consignee Country: {consignee.get('country')}")
        
        # Notify party
        if 'notify' in bol_data and bol_data['notify']:
            notify = bol_data['notify']
            if notify.get('name'):
                print(f"   Notify Party: {notify.get('name')}")
            if notify.get('address'):
                print(f"   Notify Address: {notify.get('address')}")
        
        # Vessel and voyage information
        if 'vessel_info' in bol_data and bol_data['vessel_info']:
            vessel = bol_data['vessel_info']
            if vessel.get('vessel_name'):
                print(f"   Vessel: {vessel.get('vessel_name')}")
            if vessel.get('voyage_number'):
                print(f"   Voyage: {vessel.get('voyage_number')}")
            if vessel.get('vessel_flag'):
                print(f"   Flag: {vessel.get('vessel_flag')}")
            if vessel.get('carrier_code'):
                print(f"   Carrier Code: {vessel.get('carrier_code')}")
        
        # Dates
        if 'dates' in bol_data and bol_data['dates']:
            dates = bol_data['dates']
            if dates.get('reported_date'):
                print(f"   Reported Date: {dates.get('reported_date')}")
            if dates.get('departure_date'):
                print(f"   Departure Date: {dates.get('departure_date')}")
            if dates.get('arrival_date'):
                print(f"   Arrival Date: {dates.get('arrival_date')}")
        elif bol_data.get('date_issued'):
            print(f"   Date Issued: {bol_data.get('date_issued')}")
        
        # Ports
        if 'ports' in bol_data and bol_data['ports']:
            ports = bol_data['ports']
            if ports.get('port_of_loading'):
                print(f"   Port of Loading: {ports.get('port_of_loading')}")
            if ports.get('port_of_discharge') or ports.get('port_of_destination'):
                dest = ports.get('port_of_discharge') or ports.get('port_of_destination')
                print(f"   Port of Discharge: {dest}")
            if ports.get('berth'):
                print(f"   Berth: {ports.get('berth')}")
        
        # Container and cargo
        if 'container_and_cargo' in bol_data and bol_data['container_and_cargo']:
            container_data = bol_data['container_and_cargo']
            
            # Containers
            if 'containers' in container_data and container_data['containers']:
                print(f"   Containers ({len(container_data['containers'])}):")
                for i, container in enumerate(container_data['containers'], 1):
                    print(f"     {i}. {container.get('container_number', 'N/A')} ({container.get('type', 'N/A')})")
                    if container.get('weight'):
                        print(f"        Weight: {container.get('weight')}")
                    if container.get('measure'):
                        print(f"        Measure: {container.get('measure')}")
            
            # Commodity
            if 'commodity' in container_data and container_data['commodity']:
                commodity = container_data['commodity']
                if commodity.get('description'):
                    print(f"   Commodity: {commodity.get('description')}")
                if commodity.get('weight'):
                    print(f"   Weight: {commodity.get('weight')}")
                if commodity.get('packages'):
                    print(f"   Packages: {commodity.get('packages')}")
        
        # Charges table
        if 'charges_table' in bol_data and bol_data['charges_table']:
            charges = bol_data['charges_table']
            if 'rows' in charges and charges['rows']:
                print(f"   Charges ({len(charges['rows'])}):")
                for i, charge in enumerate(charges['rows'], 1):
                    charge_name = charge.get('Charge') or charge.get('charge_type', 'N/A')
                    currency = charge.get('Currency') or charge.get('currency', '')
                    collect = charge.get('Foreign Collect Amount') or charge.get('collect_amount', '')
                    prepaid = charge.get('Foreign Prepaid Amount') or charge.get('prepaid_amount', '')
                    
                    if collect and collect != '.00':
                        print(f"     {i}. {charge_name}: {currency} {collect} (Collect)")
                    elif prepaid and prepaid != '.00':
                        print(f"     {i}. {charge_name}: {currency} {prepaid} (Prepaid)")
                
                # Totals
                if 'totals' in charges:
                    totals = charges['totals']
                    print(f"   Totals:")
                    if totals.get('Total_Foreign_Collect'):
                        print(f"     Foreign Collect: {totals.get('Total_Foreign_Collect')}")
                    if totals.get('Total_Foreign_Prepaid'):
                        print(f"     Foreign Prepaid: {totals.get('Total_Foreign_Prepaid')}")
                    if totals.get('Total_Local_Collect'):
                        print(f"     Local Collect: {totals.get('Total_Local_Collect')}")
        
        # ASYCUDA and office info
        if bol_data.get('asycuda_number'):
            print(f"   ASYCUDA Number: {bol_data.get('asycuda_number')}")
        if bol_data.get('office_of_submission'):
            print(f"   Office of Submission: {bol_data.get('office_of_submission')}")
        if bol_data.get('wharfinger'):
            print(f"   Wharfinger: {bol_data.get('wharfinger')}")
        
        # Extraction metadata
        if '_metadata' in bol_data and bol_data['_metadata']:
            meta = bol_data['_metadata']
            if meta.get('bol_confidence'):
                print(f"   BOL Confidence: {meta.get('bol_confidence')}")
            if meta.get('bol_recheck'):
                print(f"   BOL Recheck: {meta.get('bol_recheck')}")


def process_order(order_number: str) -> bool:
    """
    Process a specific order for eSAD generation.
    
    Args:
        order_number: The order number to process (e.g., 'ORD-20250921-011')
        
    Returns:
        True if processing was successful, False otherwise
    """
    # Initialize the processor
    processor = ESADProcessor()
    
    print(f"Processing eSAD for order: {order_number}")
    print("=" * 50)
    
    # Process the order
    success = processor.process_esad(order_number)
    
    if success:
        print("eSAD processing completed successfully")
    else:
        print("eSAD processing failed")
    
    return success


def main():
    """
    Main function for running the ESAD processor.
    """
    # Process the specified order
    order_number = "ORD-20250921-011"
    
    # Process the order
    process_order(order_number)


if __name__ == "__main__":
    main()
