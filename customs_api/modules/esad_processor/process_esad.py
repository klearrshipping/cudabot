import os
import json
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

# Import eSAD processing modules
try:
    # Try relative imports first (when used as module)
    from .esad_modules.core.esad_product import ProductProcessor
    from .esad_modules.core.esad_regime import RegimeTypeProcessor
    from .esad_modules.core.esad_manifest import ManifestProcessor, ManifestTracker
    from .esad_modules.core.esad_cif import CIFProcessor
    
    # Import secondary modules
    from .esad_modules.secondary.esad_address import AddressFormatter
    from .esad_modules.secondary.esad_pkg import PackageProcessor
    from .esad_modules.secondary.esad_transport_mode import TransportModeProcessor
    from .esad_modules.secondary.esad_weight import process_weight_data
    from .esad_modules.secondary.esad_marks import MarksProcessor
    from .esad_modules.secondary.esad_warehouse import WarehouseProcessor
    from .esad_modules.secondary.esad_country import process_country_fields
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
    
    # Import secondary modules
    from esad_modules.secondary.esad_address import AddressFormatter
    from esad_modules.secondary.esad_pkg import PackageProcessor
    from esad_modules.secondary.esad_transport_mode import TransportModeProcessor
    from esad_modules.secondary.esad_weight import process_weight_data
    from esad_modules.secondary.esad_marks import MarksProcessor
    from esad_modules.secondary.esad_warehouse import WarehouseProcessor
    from esad_modules.secondary.esad_country import process_country_fields
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
        base_path = Path("customs_api/processed_orders")
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
    
    def process_esad(self, order_number: str) -> bool:
        """
        Main processing function for eSAD generation.
        
        Args:
            order_number: The order number to process
            
        Returns:
            True if processing was successful, False otherwise
        """
        print(f"Starting eSAD processing for order: {order_number}")
        
        # Load the order data
        bol_data, invoice_data = self.load_order_data(order_number)
        
        if bol_data is None or invoice_data is None:
            print("Failed to load required data for eSAD processing")
            return False
        
        print("Successfully loaded both bill of lading and invoice data")
        
        # Display critical data only
        print("=" * 50)
        
        # Display invoice data - all fields
        if invoice_data:
            invoice_count = invoice_data.get('_invoice_count', 1)
            if invoice_count > 1:
                print(f"✅ Loaded {invoice_count} invoice files")
                all_invoices = invoice_data.get('_all_invoices', {})
                for invoice_key, invoice_info in all_invoices.items():
                    print(f"📋 {invoice_key.upper()}:")
                    self._print_invoice_details(invoice_info)
            else:
                print("📋 Invoice Data:")
                self._print_invoice_details(invoice_data)
        
        # Display BOL data - all fields
        if bol_data:
            print("📋 BOL Data:")
            self._print_bol_details(bol_data)
        
        print("=" * 50)
        
        # Initialize all processors
        print("🔍 Initializing eSAD processors...")
        product_processor = ProductProcessor()
        regime_processor = RegimeTypeProcessor()
        manifest_processor = ManifestProcessor({})
        cif_processor = CIFProcessor()
        
        # Prepare base input data structure
        base_input_data = {
            'invoice_data': invoice_data,
            'bol_data': bol_data,
            'fields': [],
            'existing_fields': {}
        }
        
        # Process product information using ProductProcessor
        print("\n📦 Processing product information...")
        print("=" * 50)
        
        # Handle multiple invoices for product processing
        if invoice_data and invoice_data.get('_invoice_count', 1) > 1:
            print(f"   Processing {invoice_data.get('_invoice_count', 1)} invoices for product classification...")
            
            # Process each invoice separately
            all_invoices = invoice_data.get('_all_invoices', {})
            product_results = {}
            
            for invoice_key, invoice_info in all_invoices.items():
                print(f"   Processing {invoice_key}...")
                
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
        
        # Display product processing results and save commodity code data
        for invoice_key, product_result in product_results.items():
            print(f"\n--- {invoice_key.upper()} PRODUCT CLASSIFICATION ---")
            if product_result['success']:
                print(f"✅ Success: {product_result['success']}")
                print(f"📋 Commercial Description: {product_result['commercial_description']}")
                print(f"🏷️  Commodity Code: {product_result['commodity_code']}")
                print(f"🔢 HS Code: {product_result['hs_code']}")
                print(f"📝 HS Description: {product_result['hs_description']}")
                print(f"📄 Original Description: {product_result['original_description']}")
                print(f"📊 Processing Notes: {product_result['processing_notes']}")
            else:
                print(f"❌ Processing Failed: {product_result['error']}")
                print(f"📋 Commercial Description: {product_result['commercial_description']}")
                print(f"🏷️  Commodity Code: {product_result['commodity_code']}")
            
            # Save commodity code data to JSON file
            order_number = base_input_data.get('existing_fields', {}).get('order_number', 'UNKNOWN')
            if order_number != 'UNKNOWN':
                save_commodity_code_data(order_number, invoice_key, product_result)
        
        # Process CIF components using CIFProcessor
        print("\n💰 Processing CIF components...")
        print("=" * 50)
        
        cif_result = cif_processor.process(base_input_data)
        if cif_result['success']:
            print(f"✅ CIF Processing Successful")
            print(f"📋 Invoice Total: ${cif_result.get('val_note_invoice_total_including_freight', 0):,.2f}" if cif_result.get('val_note_invoice_total_including_freight') else "📋 Invoice Total: Not found")
            print(f"📦 Goods Value: ${cif_result.get('val_note_invoice_value_goods_only', 0):,.2f}" if cif_result.get('val_note_invoice_value_goods_only') else "📦 Goods Value: Not found")
            print(f"🚢 Freight (Invoice): ${cif_result.get('val_note_freight_charges_invoice', 0):,.2f}" if cif_result.get('val_note_freight_charges_invoice') else "🚢 Freight (Invoice): Not found")
            print(f"🛡️ Insurance: ${cif_result.get('val_note_insurance_charges_invoice', 0):,.2f}" if cif_result.get('val_note_insurance_charges_invoice') else "🛡️ Insurance: Not found")
            print(f"💵 Cost & Freight: ${cif_result.get('val_note_cost_and_freight', 0):,.2f}" if cif_result.get('val_note_cost_and_freight') else "💵 Cost & Freight: Not calculated")
            print(f"🌍 CIF (Cost + Insurance + Freight): ${cif_result.get('val_note_cif', 0):,.2f}" if cif_result.get('val_note_cif') else "🌍 CIF: Not calculated")
            print(f"💱 Invoice Currency: {cif_result.get('invoice_currency', 'Not found')}")
            print(f"📋 Incoterms: {cif_result.get('incoterms', 'Not found')}")
        else:
            print(f"❌ CIF Processing Failed: {cif_result['error']}")
        
        # Process regime type using RegimeTypeProcessor (after CIF processing)
        print("\n🏛️ Processing regime type...")
        print("=" * 50)
        
        # Add CIF result to input data for regime determination
        base_input_data['cif_result'] = cif_result
        
        regime_result = regime_processor.determine_regime_type(base_input_data)
        print(f"✅ Regime Type: {regime_result.regime_type}")
        print(f"📋 Description: {regime_result.description}")
        print(f"🔢 Procedure Code: {regime_result.procedure_code}")
        print(f"📊 Confidence: {regime_result.confidence}")
        print(f"💭 Reasoning: {regime_result.reasoning}")
        print(f"🌍 Direction: {regime_result.import_export_direction}")
        print(f"🏢 Commercial: {regime_result.commercial_determination}")
        
        # Process manifest using ManifestProcessor
        print("\n📋 Processing manifest...")
        print("=" * 50)
        
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
        
        if bol_number:
            print(f"🎯 Found BOL number: {bol_number}")
            
            # Initialize manifest tracker
            manifest_tracker = ManifestTracker()
            
            # Track BOL (this will open browser and extract manifest data)
            manifest_result = manifest_tracker.track_bol(bol_number)
            
            if manifest_result.success:
                print(f"✅ Manifest Tracking Successful")
                print(f"📋 Total Entries: {manifest_result.total_entries}")
                print(f"🌐 Tracking URL: {manifest_result.tracking_url}")
                
                # Save manifest results
                manifest_file = manifest_tracker.save_manifest_results(manifest_result)
                print(f"💾 Manifest saved to: {manifest_file}")
                
                # Process manifest data
                manifest_input = {'manifest_registration_number': bol_number}
                manifest_processed = manifest_processor.process(manifest_input)
                
                if manifest_processed['success']:
                    print(f"✅ Manifest Processed: {manifest_processed['manifest_processed']}")
                else:
                    print(f"❌ Manifest Processing Failed: {manifest_processed['error']}")
            else:
                print(f"❌ Manifest Tracking Failed: {manifest_result.error_message}")
        else:
            print("❌ No BOL number found for manifest tracking")
        
        # Process secondary eSAD fields using Secondary Processors
        print("\n🔧 Processing secondary eSAD fields...")
        print("=" * 50)
        
        # Initialize secondary processors
        address_formatter = AddressFormatter()
        package_processor = PackageProcessor()
        transport_processor = TransportModeProcessor()
        marks_processor = MarksProcessor()
        warehouse_processor = WarehouseProcessor()
        # country processing uses functions, not a class
        location_processor = LocationProcessor()
        locode_processor = LocodeProcessor()
        ref_number_processor = CommercialReferenceProcessor()
        trans_type_processor = TransactionTypeProcessor()
        trn_processor = TRNLookupProcessor()
        
        # Process addresses
        print("\n🏠 Processing addresses...")
        try:
            # Process importer address
            if bol_data and bol_data.get('consignee'):
                consignee_address = f"{bol_data['consignee'].get('address_line1', '')} {bol_data['consignee'].get('city', '')} {bol_data['consignee'].get('country', '')}".strip()
                if consignee_address:
                    importer_result = address_formatter.format_address(consignee_address)
                    print(f"✅ Importer Address: {importer_result.formatted}")
            
            # Process exporter address  
            if bol_data and bol_data.get('shipper'):
                shipper_address = f"{bol_data['shipper'].get('address_line1', '')} {bol_data['shipper'].get('city', '')} {bol_data['shipper'].get('country', '')}".strip()
                if shipper_address:
                    exporter_result = address_formatter.format_address(shipper_address)
                    print(f"✅ Exporter Address: {exporter_result.formatted}")
        except Exception as e:
            print(f"❌ Address processing failed: {e}")
        
        # Process package types
        print("\n📦 Processing package types...")
        try:
            package_input = base_input_data.copy()
            package_result = package_processor.process(package_input)
            if package_result['success']:
                print(f"✅ Package Type: {package_result.get('package_code', 'N/A')}")
            else:
                print(f"❌ Package processing failed: {package_result.get('error', 'Unknown error')}")
        except Exception as e:
            print(f"❌ Package processing failed: {e}")
        
        # Process transport mode
        print("\n🚢 Processing transport mode...")
        try:
            transport_input = base_input_data.copy()
            transport_result = transport_processor.process(transport_input)
            if transport_result['success']:
                print(f"✅ Transport Mode: {transport_result.get('transport_code', 'N/A')}")
            else:
                print(f"❌ Transport processing failed: {transport_result.get('error', 'Unknown error')}")
        except Exception as e:
            print(f"❌ Transport processing failed: {e}")
        
        # Process weights
        print("\n⚖️ Processing weights...")
        try:
            # Extract weight data from BOL cargo
            weight_data = {}
            if bol_data and bol_data.get('cargo'):
                cargo = bol_data['cargo']
                if isinstance(cargo, list) and len(cargo) > 0:
                    cargo_item = cargo[0]
                    weight_data = {
                        'net_weight': cargo_item.get('net_weight', ''),
                        'gross_weight': cargo_item.get('gross_weight_kg', '')
                    }
                elif isinstance(cargo, dict):
                    weight_data = {
                        'net_weight': cargo.get('net_weight', ''),
                        'gross_weight': cargo.get('gross_weight', '')
                    }
            
            if weight_data:
                processed_weights = process_weight_data(
                    weight_data.get('net_weight', ''),
                    weight_data.get('gross_weight', '')
                )
                print(f"✅ Net Weight: {processed_weights.get('net_weight', 'N/A')}")
                print(f"✅ Gross Weight: {processed_weights.get('gross_weight', 'N/A')}")
            else:
                print("❌ No weight data found")
        except Exception as e:
            print(f"❌ Weight processing failed: {e}")
        
        # Process marks and numbers
        print("\n📝 Processing marks and numbers...")
        try:
            marks_input = base_input_data.copy()
            marks_result = marks_processor.process(marks_input)
            if marks_result['success']:
                print(f"✅ Marks: {marks_result.get('marks_and_numbers', 'N/A')}")
            else:
                print(f"❌ Marks processing failed: {marks_result.get('error', 'Unknown error')}")
        except Exception as e:
            print(f"❌ Marks processing failed: {e}")
        
        # Process warehouse information
        print("\n🏢 Processing warehouse information...")
        try:
            warehouse_input = base_input_data.copy()
            warehouse_result = warehouse_processor.process(warehouse_input)
            if warehouse_result['success']:
                print(f"✅ Warehouse: {warehouse_result.get('warehouse_code', 'N/A')}")
            else:
                print(f"❌ Warehouse processing failed: {warehouse_result.get('error', 'Unknown error')}")
        except Exception as e:
            print(f"❌ Warehouse processing failed: {e}")
        
        # Process country codes
        print("\n🌍 Processing country codes...")
        try:
            # Load countries data
            from modules.esad_processor.esad_modules.secondary.esad_country import load_countries_data
            countries = load_countries_data()
            
            # Extract country fields from BOL and invoice data
            country_fields = {}
            if bol_data:
                if bol_data.get('shipper', {}).get('country'):
                    country_fields['shipper_country'] = bol_data['shipper']['country']
                if bol_data.get('consignee', {}).get('country'):
                    country_fields['consignee_country'] = bol_data['consignee']['country']
            
            if country_fields:
                country_result = process_country_fields(country_fields, countries)
                print(f"✅ Country Processing: {country_result.get('shipper_country', 'N/A')} -> {country_result.get('consignee_country', 'N/A')}")
            else:
                print("❌ No country data found")
        except Exception as e:
            print(f"❌ Country processing failed: {e}")
        
        # Process location information
        print("\n📍 Processing location information...")
        try:
            location_input = base_input_data.copy()
            location_result = location_processor.process(location_input)
            if location_result['success']:
                print(f"✅ Location Processing: {location_result.get('location_code', 'N/A')}")
            else:
                print(f"❌ Location processing failed: {location_result.get('error', 'Unknown error')}")
        except Exception as e:
            print(f"❌ Location processing failed: {e}")
        
        # Process LOCODE information
        print("\n🚢 Processing LOCODE information...")
        try:
            locode_input = base_input_data.copy()
            locode_result = locode_processor.process(locode_input)
            if locode_result['success']:
                print(f"✅ LOCODE Processing: {locode_result.get('locode', 'N/A')}")
            else:
                print(f"❌ LOCODE processing failed: {locode_result.get('error', 'Unknown error')}")
        except Exception as e:
            print(f"❌ LOCODE processing failed: {e}")
        
        # Process reference numbers
        print("\n🔢 Processing reference numbers...")
        try:
            ref_input = base_input_data.copy()
            ref_result = ref_number_processor.process(ref_input)
            if ref_result['success']:
                print(f"✅ Reference Number: {ref_result.get('reference_number', 'N/A')}")
            else:
                print(f"❌ Reference processing failed: {ref_result.get('error', 'Unknown error')}")
        except Exception as e:
            print(f"❌ Reference processing failed: {e}")
        
        # Process transaction type
        print("\n💼 Processing transaction type...")
        try:
            trans_input = base_input_data.copy()
            trans_result = trans_type_processor.process(trans_input)
            if trans_result['success']:
                print(f"✅ Transaction Type: {trans_result.get('transaction_type', 'N/A')}")
            else:
                print(f"❌ Transaction processing failed: {trans_result.get('error', 'Unknown error')}")
        except Exception as e:
            print(f"❌ Transaction processing failed: {e}")
        
        # Process TRN (Tax Registration Number)
        print("\n🏛️ Processing TRN...")
        try:
            trn_input = base_input_data.copy()
            trn_result = trn_processor.process(trn_input)
            if trn_result['success']:
                print(f"✅ TRN: {trn_result.get('trn', 'N/A')}")
            else:
                print(f"❌ TRN processing failed: {trn_result.get('error', 'Unknown error')}")
        except Exception as e:
            print(f"❌ TRN processing failed: {e}")
        
        # eSAD Processing Complete
        
        return True

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
        if bol_data.get('shipper_account_number'):
            print(f"   Shipper Account: {bol_data.get('shipper_account_number')}")
        if bol_data.get('date_issued'):
            print(f"   Date Issued: {bol_data.get('date_issued')}")
        
        # Shipper information
        if 'shipper' in bol_data and bol_data['shipper']:
            shipper = bol_data['shipper']
            print(f"   Shipper: {shipper.get('name', 'N/A')}")
            if shipper.get('name_line1'):
                print(f"   Shipper ID: {shipper.get('name_line1')}")
            if shipper.get('address_line1'):
                print(f"   Shipper Address 1: {shipper.get('address_line1')}")
            if shipper.get('address_line2'):
                print(f"   Shipper Address 2: {shipper.get('address_line2')}")
            if shipper.get('country'):
                print(f"   Shipper Country: {shipper.get('country')}")
        
        # Consignee information
        if 'consignee' in bol_data and bol_data['consignee']:
            consignee = bol_data['consignee']
            print(f"   Consignee: {consignee.get('name', 'N/A')}")
            if consignee.get('address_line1'):
                print(f"   Consignee Address: {consignee.get('address_line1')}")
            if consignee.get('city'):
                print(f"   Consignee City: {consignee.get('city')}")
            if consignee.get('contact_phone'):
                print(f"   Consignee Phone: {consignee.get('contact_phone')}")
            if consignee.get('account_number'):
                print(f"   Consignee Account: {consignee.get('account_number')}")
        
        # Issuer/Carrier information
        if 'issuer' in bol_data and bol_data['issuer']:
            issuer = bol_data['issuer']
            if issuer.get('carrier_name'):
                print(f"   Carrier: {issuer.get('carrier_name')}")
            if issuer.get('logo_present'):
                print(f"   Logo Present: {issuer.get('logo_present')}")
        
        # Agent information
        if 'agent' in bol_data and bol_data['agent']:
            agent = bol_data['agent']
            if agent.get('agent_iata_code'):
                print(f"   Agent IATA Code: {agent.get('agent_iata_code')}")
            if agent.get('account_no'):
                print(f"   Agent Account: {agent.get('account_no')}")
        
        # Airport information
        if 'airport_info' in bol_data and bol_data['airport_info']:
            airport = bol_data['airport_info']
            if airport.get('airport_of_departure_code'):
                print(f"   Departure Airport Code: {airport.get('airport_of_departure_code')}")
            if airport.get('airport_of_departure_name'):
                print(f"   Departure Airport: {airport.get('airport_of_departure_name')}")
            if airport.get('airport_of_destination'):
                print(f"   Destination Airport: {airport.get('airport_of_destination')}")
            if 'routing_and_destination' in airport and airport['routing_and_destination']:
                routing = airport['routing_and_destination']
                if routing.get('TO'):
                    print(f"   Routing TO: {routing.get('TO')}")
                if routing.get('BY_FIRST_CARRIER'):
                    print(f"   First Carrier: {routing.get('BY_FIRST_CARRIER')}")
        
        # Currency and payment
        if 'currency_and_payment' in bol_data and bol_data['currency_and_payment']:
            payment = bol_data['currency_and_payment']
            if payment.get('currency'):
                print(f"   Currency: {payment.get('currency')}")
            if payment.get('payment_terms_box'):
                print(f"   Payment Terms: {payment.get('payment_terms_box')}")
            if payment.get('wtval_ppd_mark'):
                print(f"   Weight Value PPD: {payment.get('wtval_ppd_mark')}")
            if payment.get('other_ppd_mark'):
                print(f"   Other PPD: {payment.get('other_ppd_mark')}")
        
        # Declared values
        if 'declared_values' in bol_data and bol_data['declared_values']:
            values = bol_data['declared_values']
            if values.get('declared_value_for_carriage'):
                print(f"   Declared Value for Carriage: {values.get('declared_value_for_carriage')}")
            if values.get('declared_value_for_customs'):
                print(f"   Declared Value for Customs: {values.get('declared_value_for_customs')}")
        
        # Flight and transport info
        if 'flight_and_transport_info' in bol_data and bol_data['flight_and_transport_info']:
            flight = bol_data['flight_and_transport_info']
            if flight.get('flight_number'):
                print(f"   Flight Number: {flight.get('flight_number')}")
            if flight.get('flight_date'):
                print(f"   Flight Date: {flight.get('flight_date')}")
            if flight.get('tail_number'):
                print(f"   Tail Number: {flight.get('tail_number')}")
            if flight.get('tracking_number'):
                print(f"   Tracking Number: {flight.get('tracking_number')}")
            if flight.get('first_carrier'):
                print(f"   First Carrier: {flight.get('first_carrier')}")
        
        # Handling information
        if bol_data.get('handling_information'):
            print(f"   Handling Information: {bol_data.get('handling_information')}")
        
        # Cargo summary
        if 'cargo_summary' in bol_data and bol_data['cargo_summary']:
            cargo = bol_data['cargo_summary']
            if cargo.get('total_pieces'):
                print(f"   Total Pieces: {cargo.get('total_pieces')}")
            if cargo.get('total_gross_weight'):
                print(f"   Total Gross Weight: {cargo.get('total_gross_weight')}")
            if cargo.get('total_chargeable_weight'):
                print(f"   Total Chargeable Weight: {cargo.get('total_chargeable_weight')}")
        
        # Cargo details
        if 'cargo_details' in bol_data and bol_data['cargo_details']:
            print(f"   Cargo Details ({len(bol_data['cargo_details'])}):")
            for i, cargo in enumerate(bol_data['cargo_details'], 1):
                print(f"     {i}. {cargo.get('description_of_goods', 'N/A')}")
                print(f"        Pieces: {cargo.get('no_of_pieces', 'N/A')} | Weight: {cargo.get('gross_weight', 'N/A')}")
                print(f"        Freight Charges: {cargo.get('freight_charges', 'N/A')} {cargo.get('freight_charges_currency', '')}")
                if cargo.get('marks_and_numbers'):
                    print(f"        Marks & Numbers: {cargo.get('marks_and_numbers')}")
        
        # Weights and measures
        if 'weights_and_measures' in bol_data and bol_data['weights_and_measures']:
            weights = bol_data['weights_and_measures']
            if weights.get('piece_count'):
                print(f"   Piece Count: {weights.get('piece_count')}")
            if weights.get('gross_weight_display'):
                print(f"   Gross Weight: {weights.get('gross_weight_display')}")
            if weights.get('chargeable_weight_display'):
                print(f"   Chargeable Weight: {weights.get('chargeable_weight_display')}")
        
        # Charges
        if 'charges' in bol_data and bol_data['charges']:
            print(f"   Charges ({len(bol_data['charges'])}):")
            for i, charge in enumerate(bol_data['charges'], 1):
                print(f"     {i}. {charge.get('charge_type', 'N/A')}: {charge.get('prepaid_amount', 'N/A')} {charge.get('currency', '')}")
        
        # Signatures and execution
        if 'signatures_and_execution' in bol_data and bol_data['signatures_and_execution']:
            sig = bol_data['signatures_and_execution']
            if sig.get('signed_by'):
                print(f"   Signed By: {sig.get('signed_by')}")
            if sig.get('executed_on'):
                print(f"   Executed On: {sig.get('executed_on')}")
            if sig.get('place'):
                print(f"   Place: {sig.get('place')}")
            if sig.get('time'):
                print(f"   Time: {sig.get('time')}")
        
        # References and codes
        if 'references_and_codes' in bol_data and bol_data['references_and_codes']:
            refs = bol_data['references_and_codes']
            if refs.get('awb_number_top'):
                print(f"   AWB Number: {refs.get('awb_number_top')}")
            if refs.get('internal_shipper_code'):
                print(f"   Internal Shipper Code: {refs.get('internal_shipper_code')}")
            if refs.get('asycuda_ref'):
                print(f"   ASYCUDA Ref: {refs.get('asycuda_ref')}")
            if refs.get('additional_ref'):
                print(f"   Additional Ref: {refs.get('additional_ref')}")
        
        # Bill of Lading numbers
        if bol_data.get('bill_of_lading'):
            print(f"   BOL Number: {bol_data.get('bill_of_lading')}")
        if bol_data.get('master_bill_of_lading'):
            print(f"   Master BOL: {bol_data.get('master_bill_of_lading')}")
        
        # Additional text
        if bol_data.get('copies_note'):
            print(f"   Copies Note: {bol_data.get('copies_note')}")
        
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
