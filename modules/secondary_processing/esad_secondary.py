"""
ESAD Secondary Processing Orchestrator

This script orchestrates all secondary processing modules to enhance and validate
ESAD field data extracted from primary processing. It coordinates the execution
of various secondary processing scripts and saves results to the esad_fields_processed table.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

# Import secondary processing modules
from .esad_regime import RegimeTypeProcessor
from .esad_trans_type import TransactionTypeProcessor
from .esad_incoterms import IncotermsProcessor
from .esad_currency import CurrencyProcessor
from .esad_amount import AmountProcessor
from .esad_transport import TransportProcessor
from .esad_location import LocationProcessor
from .esad_marks import MarksProcessor
from .esad_pkg import PackageProcessor
from .esad_product import ProductProcessor
from .esad_country import CountryProcessor
from .esad_weight import WeightProcessor
from .esad_procedure import ProcedureProcessor
from .esad_document import DocumentProcessor
from .esad_office import OfficeProcessor
from .esad_manifest import ManifestProcessor
from .esad_ref_number import ReferenceNumberProcessor
from .esad_address import AddressProcessor

# Import database client
from ..supabase_client import SupabaseClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ESADSecondaryProcessor:
    """
    Orchestrates secondary processing for ESAD fields.
    
    This class coordinates the execution of various secondary processing modules
    and saves the enhanced data to the esad_fields_processed table.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the secondary processor.
        
        Args:
            config: Configuration dictionary containing API keys and settings
        """
        self.config = config
        self.supabase_client = SupabaseClient(config)
        
        # Initialize all secondary processing modules
        self.processors = {
            'regime_type': RegimeTypeProcessor(config),
            'transaction_type': TransactionTypeProcessor(config),
            'incoterms': IncotermsProcessor(config),
            'currency': CurrencyProcessor(config),
            'amount': AmountProcessor(config),
            'transport': TransportProcessor(config),
            'location': LocationProcessor(config),
            'marks': MarksProcessor(config),
            'package': PackageProcessor(config),
            'product': ProductProcessor(config),
            'country': CountryProcessor(config),
            'weight': WeightProcessor(config),
            'procedure': ProcedureProcessor(config),
            'document': DocumentProcessor(config),
            'office': OfficeProcessor(config),
            'manifest': ManifestProcessor(config),
            'reference_number': ReferenceNumberProcessor(config),
            'address': AddressProcessor(config)
        }
        
        # Load field mappings
        self.field_mappings = self._load_field_mappings()
        
        logger.info("✅ ESAD Secondary Processor initialized with all modules")
    
    def _load_field_mappings(self) -> Dict[str, str]:
        """Load ESAD field mappings from field_mapping.json"""
        try:
            mapping_file = Path(__file__).parent / "field_mapping.json"
            with open(mapping_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Extract field mappings from the JSON structure
            mappings = {}
            for field_name, field_info in data.get("field_script_mapping", {}).items():
                output_field = field_info.get("output_field")
                if output_field:
                    mappings[field_name] = output_field
            
            logger.info(f"✅ Loaded {len(mappings)} field mappings from field_mapping.json")
            return mappings
            
        except Exception as e:
            logger.error(f"❌ Error loading field mappings: {e}")
            return {}
    
    def process_order(self, order_id: str, primary_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an order through all secondary processing modules.
        
        Args:
            order_id: The order identifier
            primary_data: Data extracted from primary processing
            
        Returns:
            Dictionary containing all processed ESAD fields
        """
        logger.info(f"🔄 Starting secondary processing for order: {order_id}")
        
        try:
            # Initialize results dictionary
            processed_results = {
                'order_id': order_id,
                'processing_timestamp': datetime.now().isoformat(),
                'fields': {}
            }
            
            # Process each field through appropriate secondary processor
            for field_name, processor in self.processors.items():
                try:
                    logger.info(f"🔄 Processing {field_name}...")
                    
                    # Get input data for this processor
                    input_data = self._get_input_data_for_processor(field_name, primary_data)
                    
                    if input_data:
                        # Process the data
                        result = processor.process(input_data)
                        
                        # Store the result
                        processed_results['fields'][field_name] = result
                        logger.info(f"✅ {field_name} processing completed")
                    else:
                        logger.warning(f"⚠️ No input data found for {field_name}")
                        
                except Exception as e:
                    logger.error(f"❌ Error processing {field_name}: {e}")
                    processed_results['fields'][field_name] = {
                        'error': str(e),
                        'status': 'failed'
                    }
            
            # Save results to database
            self._save_to_database(order_id, processed_results)
            
            logger.info(f"✅ Secondary processing completed for order: {order_id}")
            return processed_results
            
        except Exception as e:
            logger.error(f"❌ Fatal error in secondary processing: {e}")
            raise
    
    def _get_input_data_for_processor(self, processor_name: str, primary_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract relevant input data for a specific processor from primary data.
        
        Args:
            processor_name: Name of the processor
            primary_data: Data from primary processing
            
        Returns:
            Relevant input data for the processor
        """
        # Map processor names to input field names
        processor_input_mapping = {
            'regime_type': ['regime_type', 'transaction_type'],
            'transaction_type': ['transaction_type', 'payment_terms'],
            'incoterms': ['delivery_terms', 'freight_terms'],
            'currency': ['currency', 'currency_code'],
            'amount': ['amount', 'total_amount', 'invoice_amount'],
            'transport': ['transport_mode', 'vessel', 'flight_number'],
            'location': ['port_of_loading', 'port_of_destination', 'location'],
            'marks': ['marks', 'container_number', 'seal_number'],
            'package': ['package_type', 'package_count', 'package_description'],
            'product': ['commodity_description', 'product_name'],
            'country': ['country', 'origin_country', 'destination_country'],
            'weight': ['weight', 'gross_weight', 'net_weight'],
            'procedure': ['procedure_code', 'customs_procedure'],
            'document': ['document_number', 'reference_number'],
            'office': ['office_code', 'customs_office'],
            'manifest': ['manifest_number', 'registration_number'],
            'reference_number': ['order_id', 'invoice_number', 'po_number'],
            'address': ['address', 'shipper_address', 'consignee_address']
        }
        
        input_fields = processor_input_mapping.get(processor_name, [])
        input_data = {}
        
        for field in input_fields:
            if field in primary_data:
                input_data[field] = primary_data[field]
        
        return input_data if input_data else None
    
    def _save_to_database(self, order_id: str, processed_results: Dict[str, Any]):
        """
        Save processed results to the esad_fields_processed table.
        
        Args:
            order_id: The order identifier
            processed_results: Results from secondary processing
        """
        try:
            logger.info(f"💾 Saving secondary processing results to database for order: {order_id}")
            
            # Prepare data for database insertion
            db_data = {
                'order_id': order_id,
                'processing_status': 'completed',
                'validation_status': 'unvalidated',
                'processed_at': datetime.now().isoformat()
            }
            
            # Add processed field values
            for field_name, result in processed_results['fields'].items():
                if isinstance(result, dict) and 'value' in result:
                    # Map field name to database column
                    db_column = self.field_mappings.get(field_name)
                    if db_column:
                        db_data[db_column] = result['value']
            
            # Insert into esad_fields_processed table
            response = self.supabase_client.table('esad_fields_processed').insert(db_data).execute()
            
            if response.data:
                logger.info(f"✅ Successfully saved {len(response.data)} records to database")
            else:
                logger.warning("⚠️ No data was inserted into database")
                
        except Exception as e:
            logger.error(f"❌ Error saving to database: {e}")
            raise
    
    def get_processing_summary(self, order_id: str) -> Dict[str, Any]:
        """
        Get a summary of secondary processing results for an order.
        
        Args:
            order_id: The order identifier
            
        Returns:
            Summary of processing results
        """
        try:
            # Query the database for processing results
            response = self.supabase_client.table('esad_fields_processed')\
                .select('*')\
                .eq('order_id', order_id)\
                .execute()
            
            if response.data:
                return {
                    'order_id': order_id,
                    'total_fields_processed': len(response.data),
                    'processing_status': 'completed',
                    'last_updated': response.data[0].get('updated_at'),
                    'fields': response.data
                }
            else:
                return {
                    'order_id': order_id,
                    'total_fields_processed': 0,
                    'processing_status': 'not_found',
                    'message': 'No processing results found for this order'
                }
                
        except Exception as e:
            logger.error(f"❌ Error retrieving processing summary: {e}")
            return {
                'order_id': order_id,
                'error': str(e),
                'processing_status': 'error'
            }


def main():
    """Main function for testing the secondary processor."""
    # Load configuration
    config = {
        'SUPABASE_URL': 'your_supabase_url',
        'SUPABASE_KEY': 'your_supabase_key'
    }
    
    # Initialize processor
    processor = ESADSecondaryProcessor(config)
    
    # Example usage
    order_id = "ORD-20250817-001"
    primary_data = {
        'regime_type': 'import',
        'transaction_type': 'sale',
        'currency': 'USD',
        'amount': 1500.00
    }
    
    # Process the order
    results = processor.process_order(order_id, primary_data)
    print(f"Processing results: {json.dumps(results, indent=2)}")
    
    # Get summary
    summary = processor.get_processing_summary(order_id)
    print(f"Processing summary: {json.dumps(summary, indent=2)}")


if __name__ == "__main__":
    main()
