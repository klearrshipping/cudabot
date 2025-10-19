# Result Source Mapping

This document maps each processing result to the script that produces it in the ESAD workflow.

## Order Creation Results

**Script:** `modules/order_process/process_order.py`
**Results:**
- Order directory creation (`processed_orders/ORD-XXXXX-XXX/`)
- Order metadata file (`order_metadata.json`)
- Database order record

## Document Extraction Results

**Script:** `modules/extraction_process/bol_extract.py`
**Results:**
- Bill of lading extraction (`bills_of_lading/bill_of_lading_ORD-XXXXX-XXX_primary_extract.json`)
- BOL confidence scoring
- BOL number validation and recheck

**Script:** `modules/extraction_process/invoice_extract.py`
**Results:**
- Invoice extraction (`invoices/invoice_ORD-XXXXX-XXX_invoice_X_extract.json`)
- Invoice confidence scoring
- Multiple invoice processing

## ESAD Processing Results

**Script:** `modules/esad_processor/process_esad.py`
**Results:**
- Consolidated ESAD processing results (`esad_files/esad_processing_results_YYYYMMDD_HHMMSS.json`)
- Complete workflow orchestration
- All stage coordination

### Product Classification Results

**Script:** `modules/esad_processor/esad_modules/secondary/esad_product_classification.py`
**Results:**
- Commercial description formatting
- HS code determination (e.g., `8507.60`)
- Commodity code generation (e.g., `8507600000`)
- Product classification reasoning

### CIF Processing Results

**Script:** `modules/esad_processor/esad_modules/secondary/esad_cif.py`
**Results:**
- Cost calculation
- Freight calculation
- Insurance calculation
- CIF value computation
- Currency processing

### Regime Type Determination Results

**Script:** `modules/esad_processor/esad_modules/core/esad_regime.py`
**Results:**
- Port and country extraction
- Trade lane determination (Import/Export)
- Commercial vs Personal classification
- Regime type selection (e.g., `IMS4`)
- Procedure code assignment
- Confidence scoring and reasoning

### Manifest Processing Results

**Script:** `modules/esad_processor/esad_modules/core/esad_manifest.py`
**Results:**
- BOL tracking via Jamaica Customs portal
- Manifest entry extraction
- Tracking URL generation
- Entry count and totals

## Secondary ESAD Field Processing Results

**Script:** `modules/esad_processor/esad_modules/secondary/esad_address.py`
**Results:**
- Exporter/consignor address extraction (Box 2)
- Importer/consignee address extraction (Box 8)
- Address formatting and validation
- Country code determination

**Script:** `modules/esad_processor/esad_modules/secondary/esad_package_types.py`
**Results:**
- Package type determination (Box 31)
- Package code assignment (e.g., `BX`)

**Script:** `modules/esad_processor/esad_modules/secondary/esad_transport_mode.py`
**Results:**
- Transport mode at border (Box 25)
- Transport code assignment (e.g., `1`)

**Script:** `modules/esad_processor/esad_modules/secondary/esad_weights.py`
**Results:**
- Net weight calculation (Box 35)
- Gross weight calculation (Box 38)
- Weight validation and fallback logic

**Script:** `modules/esad_processor/esad_modules/secondary/esad_marks_numbers.py`
**Results:**
- Marks and numbers processing (Box 31)
- Shipping marks extraction

**Script:** `modules/esad_processor/esad_modules/secondary/esad_warehouse.py`
**Results:**
- Warehouse information (Box 49)
- Warehouse code assignment (e.g., `OSC01`)

**Script:** `modules/esad_processor/esad_modules/secondary/esad_countries.py`
**Results:**
- Country of export (Box 15)
- Country of destination (Box 17)
- Country code validation

**Script:** `modules/esad_processor/esad_modules/secondary/esad_office_code.py`
**Results:**
- Office of submission determination
- ASYCUDA/manifest number generation
- Wharfinger identification
- Office ID assignment (e.g., `JMOSC`)

**Script:** `modules/esad_processor/esad_modules/secondary/esad_location.py`
**Results:**
- Location of goods (Box 30)
- Warehouse location mapping

**Script:** `modules/esad_processor/esad_modules/secondary/esad_locode.py`
**Results:**
- Place of unloading (Box 27)
- LOCODE assignment (e.g., `JMKIN`)
- Port location mapping

**Script:** `modules/esad_processor/esad_modules/secondary/esad_reference_numbers.py`
**Results:**
- Reference number generation (Box 7)
- Commercial reference creation (e.g., `ORD-000001`)
- Reference number configuration management

**Script:** `modules/esad_processor/esad_modules/secondary/esad_transaction_type.py`
**Results:**
- Transaction type determination (Box 24)
- Transaction code assignment (e.g., `1.1`)

**Script:** `modules/esad_processor/esad_modules/secondary/esad_trn.py`
**Results:**
- TRN lookup for Jamaican entities (Boxes 2/8)
- Company name fuzzy matching
- TRN validation and assignment

## File Organization

All results are now consolidated into:
```
processed_orders/ORD-XXXXX-XXX/
├── file_uploads/           # Original uploaded files
├── invoices/              # Invoice extraction results
├── bills_of_lading/       # BOL extraction results
└── esad_files/           # Consolidated ESAD processing results
    └── esad_processing_results_YYYYMMDD_HHMMSS.json
```

## Error Handling

**Script:** Various modules with error logging
**Results:**
- Processing error logs
- Fallback processing results
- Confidence scoring for error recovery
