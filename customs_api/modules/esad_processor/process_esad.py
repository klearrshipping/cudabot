import os
import json
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

# Import eSAD processing modules
try:
    # Try relative imports first (when used as module)
    from .esad_modules.core.esad_product import ProductProcessor
    from .esad_modules.core.esad_regime import RegimeTypeProcessor
    from .esad_modules.core.esad_manifest import ManifestProcessor
except ImportError:
    # Fallback to absolute imports (when run directly)
    from esad_modules.core.esad_product import ProductProcessor
    from esad_modules.core.esad_regime import RegimeTypeProcessor
    from esad_modules.core.esad_manifest import ManifestProcessor


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
        
        # Display raw data
        print("=" * 50)
        
        # Display invoice data
        if invoice_data:
            invoice_count = invoice_data.get('_invoice_count', 1)
            if invoice_count > 1:
                print(f"✅ Loaded {invoice_count} invoice files")
                print()
                print("📋 Multiple Invoice Data:")
                
                # Display each invoice separately
                all_invoices = invoice_data.get('_all_invoices', {})
                for invoice_key, invoice_info in all_invoices.items():
                    print(f"\n--- {invoice_key.upper()} ---")
                    invoice_fields = len(invoice_info)
                    print(f"Fields: {invoice_fields}")
                    
                    # Display key information without circular references
                    if 'supplier' in invoice_info:
                        supplier = invoice_info['supplier']
                        print(f"Supplier: {supplier.get('name', 'N/A')}")
                    
                    if 'invoice_details' in invoice_info:
                        details = invoice_info['invoice_details']
                        print(f"Invoice Number: {details.get('invoice_number', 'N/A')}")
                        print(f"Date: {details.get('date', 'N/A')}")
                        print(f"Currency: {details.get('currency', 'N/A')}")
                    
                    if 'items' in invoice_info:
                        items = invoice_info['items']
                        print(f"Items Count: {len(items) if isinstance(items, list) else 'N/A'}")
                    
                    if 'totals' in invoice_info:
                        totals = invoice_info['totals']
                        print(f"Total Amount: {totals.get('total_amount', 'N/A')}")
            else:
                invoice_fields = len(invoice_data)
                print(f"✅ Loaded invoice data: {invoice_fields} fields")
                print()
                print("📋 Invoice Data:")
                
                # Display key information without circular references
                if 'supplier' in invoice_data:
                    supplier = invoice_data['supplier']
                    print(f"Supplier: {supplier.get('name', 'N/A')}")
                
                if 'invoice_details' in invoice_data:
                    details = invoice_data['invoice_details']
                    print(f"Invoice Number: {details.get('invoice_number', 'N/A')}")
                    print(f"Date: {details.get('date', 'N/A')}")
                    print(f"Currency: {details.get('currency', 'N/A')}")
                
                if 'items' in invoice_data:
                    items = invoice_data['items']
                    print(f"Items Count: {len(items) if isinstance(items, list) else 'N/A'}")
                
                if 'totals' in invoice_data:
                    totals = invoice_data['totals']
                    print(f"Total Amount: {totals.get('total_amount', 'N/A')}")
        
        print()
        
        # Display BOL data
        if bol_data:
            bol_fields = len(bol_data)
            print(f"✅ Loaded BOL data: {bol_fields} fields")
            print()
            print("📋 BOL Data:")
            
            # Display key BOL information without circular references
            if 'document_number' in bol_data:
                print(f"Document Number: {bol_data['document_number']}")
            
            if 'sea_waybill_no' in bol_data:
                print(f"Sea Waybill No: {bol_data['sea_waybill_no']}")
            
            if 'carrier' in bol_data:
                carrier = bol_data['carrier']
                print(f"Carrier: {carrier.get('name', 'N/A')}")
            
            if 'vessel_info' in bol_data:
                vessel = bol_data['vessel_info']
                print(f"Vessel: {vessel.get('vessel_name', 'N/A')}")
                print(f"Voyage: {vessel.get('voyage_number', 'N/A')}")
            
            if 'shipper' in bol_data:
                shipper = bol_data['shipper']
                print(f"Shipper: {shipper.get('name', 'N/A')}")
            
            if 'consignee' in bol_data:
                consignee = bol_data['consignee']
                print(f"Consignee: {consignee.get('name', 'N/A')}")
        
        print("=" * 50)
        
        # Process product information using ProductProcessor
        print("🔍 Processing product information...")
        product_processor = ProductProcessor()
        
        # Handle multiple invoices for product processing
        if invoice_data and invoice_data.get('_invoice_count', 1) > 1:
            print(f"   Processing {invoice_data.get('_invoice_count', 1)} invoices for product classification...")
            
            # Process each invoice separately
            all_invoices = invoice_data.get('_all_invoices', {})
            product_results = {}
            
            for invoice_key, invoice_info in all_invoices.items():
                print(f"   Processing {invoice_key}...")
                
                # Prepare input data for ProductProcessor
                input_data = {
                    'invoice_data': invoice_info,
                    'bol_data': bol_data,
                    'fields': [],
                    'existing_fields': {}
                }
                
                # Process the product information for this invoice
                product_result = product_processor.process(input_data)
                product_results[invoice_key] = product_result
        else:
            # Single invoice processing (backward compatibility)
            input_data = {
                'invoice_data': invoice_data,
                'bol_data': bol_data,
                'fields': [],
                'existing_fields': {}
            }
            
            # Process the product information
            product_result = product_processor.process(input_data)
            product_results = {'invoice_1': product_result}
        
        # Display product processing results
        print("\n📦 Product Processing Results:")
        print("=" * 50)
        
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
        
        print("=" * 50)
        
        # TODO: Add additional eSAD processing logic here
        print("Additional eSAD processing logic to be implemented...")
        
        return True


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
