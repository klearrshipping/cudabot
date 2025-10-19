# Log Source Mapping - Complete Workflow

This document maps each log output to its source file in the customs_api application.

## Server Startup Logs
**Source:** `customs_api/app.py` (lines 13-37)
```
⚠️ Database models not available - running in file-only mode
🚀 Starting Customs Declaration API Server...
📋 Available endpoints:
   GET  /                    - Upload interface
   POST /api/upload-documents - Upload documents
   GET  /api/orders/{id}     - Get order
   GET  /api/health          - Health check
🌐 Server will be available at: http://localhost:8000
INFO:     Started server process [1060]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

---

## Order Creation
**Source:** `customs_api/modules/order_process/process_order.py` (line 182)
```
✅ Order ORD-20251010-001 created successfully!
```

---

## Extraction Configuration
**Source:** `customs_api/modules/extraction_process/document_processor.py` (lines 31-34)
```
📋 Document Extraction Processor Configuration:
   🤖 Processor: Claude Sonnet 4 via OpenRouter
   📄 Invoice Processing: OpenRouter API
   📋 BOL Processing: OpenRouter API
```

---

## Workflow Orchestration
**Source:** `customs_api/app.py` (workflow management function)
- Line 168: `[WF] Scheduling complete workflow for ORD-20251010-001`
- Line 394: `[WF] Begin complete workflow: ORD-20251010-001`
- Line 176: `🔄 Started automatic complete workflow for order: ORD-20251010-001`
- Line 397: `📄 STAGE 1: Document Extraction`
- Line 414: `[WF] Extraction finished: ORD-20251010-001 result_keys=['bill_of_lading', 'invoices']`
- Line 418: `🔧 STAGE 2: eSAD Processing`
- Line 441: `[WF] ESAD start: ORD-20251010-001`
- Line 445: `[WF] ESAD done: ORD-20251010-001 status=success`
- Line 446: `✅ eSAD processing completed successfully!`
- Line 453: `🎉 COMPLETE WORKFLOW FINISHED`

---

## STAGE 1: Document Extraction

### Main Extraction Process
**Source:** `customs_api/modules/extraction_process/document_processor.py`
- Line 61: `🔄 Starting document processing for order: ORD-20251010-001`
- Line 126: `✅ Processing completed:`
- Lines 127-128: Invoice/BOL success counts

### BOL Extraction
**Source:** `customs_api/modules/extraction_process/bol_extract.py`
- Line 125: `✅ BOL extraction succeeded on attempt 1 with normal quality`
- Quality attempt logs (DPI, image size)
- PDF conversion logs

---

## STAGE 2: eSAD Processing

### Main eSAD Processor
**Source:** `customs_api/modules/esad_processor/process_esad.py`

#### Data Loading (lines 281-323)
```
Starting eSAD processing for order: ORD-20251010-001
Successfully loaded bills_of_lading from: ...
Successfully loaded invoice 1 from: ...
Successfully loaded both bill of lading and invoice data
==================================================
📋 Invoice Data:
   [invoice details printed by _print_invoice_details() at line 905]
📋 BOL Data:
   [BOL details printed by _print_bol_details() at line 974]
==================================================
🔍 Initializing eSAD processors...
```

#### Product Processing (lines 342-405)
```
📦 Processing product information...
==================================================
--- INVOICE_1 PRODUCT CLASSIFICATION ---
✅ Success: True
CLASSIFICATION RESULTS (JSON Format)
📄 Original Description: ...
📊 Processing Notes: ...
```
**Actual classification:** `customs_api/modules/esad_processor/esad_modules/core/esad_product.py`

#### CIF Processing (lines 407-443)
```
💰 Processing CIF components...
==================================================
✅ CIF Processing Successful
CIF RESULTS (JSON Format)
📋 Invoice Total: ...
💱 Invoice Currency: ...
📋 Incoterms: ...
```
**Actual processing:** `customs_api/modules/esad_processor/esad_modules/core/esad_cif.py`

#### Regime Type (lines 446-507)
```
🏛️ Processing regime type...
==================================================
📦 COMMERCIAL/PERSONAL CLASSIFICATION:
   └── Classification: Personal
   └── Confidence: high
   ...
🏛️ REGIME TYPE DETERMINATION:
✅ Regime Type: IMS4
📋 Description: IMS
🔢 Procedure Code: 4
...
```
**Actual processing:** `customs_api/modules/esad_processor/esad_modules/core/esad_regime.py`

#### Manifest Processing (lines 509-579)
```
📋 Processing manifest...
==================================================
🎯 Found BOL number: PSHFHKIN25072146
DevTools listening on ws://...
STEP 1: Initializing BOL Tracking
STEP 2: Loading Jamaica Customs Portal...
   ✓ Portal loaded successfully
...
✅ Manifest Tracking Successful
💾 Manifest saved to: ...
✅ Manifest Processed: PSHFHKIN25072146
```
**Actual processing:** `customs_api/modules/esad_processor/esad_modules/core/esad_manifest.py`

---

## Secondary eSAD Fields
**Source:** `customs_api/modules/esad_processor/process_esad.py` (line 582)
```
🔧 Processing secondary eSAD fields...
==================================================
```

### Initialization Messages (printed when processors initialize)
**Sources:**
- `esad_transport_mode.py` line 46: `✅ Loaded 5 transport mode codes`
- `esad_location.py` line 75: `✅ Loaded 67 LOCODE records for Jamaican ports`
- `esad_trn.py` line 44: `✅ Connected to Supabase for TRN lookup (using service role)`

### Individual Secondary Processors

#### Addresses (Box 2 & 8)
**Source:** `process_esad.py` lines 602-632
**Processor:** `esad_modules/secondary/esad_address.py`
```
🏠 BOX 2 & BOX 8: Processing addresses (Exporter/Consignee)...
Created TensorFlow Lite XNNPACK delegate for CPU.
"consignor": { ... }
"consignee": { ... }
```

#### Package Types (Box 31)
**Source:** `process_esad.py` lines 635-647
**Processor:** `esad_modules/secondary/esad_pkg.py`
```
📦 BOX 31: Processing package types...
Testing model: gpt-5   <-- ❌ THIS IS THE PROBLEM (invalid model)
✅ Model returned code: BX
✅ Package Type: BX
```

#### Transport Mode (Box 25)
**Source:** `process_esad.py` lines 650-662
**Processor:** `esad_modules/secondary/esad_transport_mode.py`
```
🚢 BOX 25: Processing transport mode at border...
✅ Transport Mode: 1
```

#### Weights (Box 35 & 38)
**Source:** `process_esad.py` lines 665-702
**Processor:** `esad_modules/secondary/esad_weight.py`
```
⚖️ BOX 35 (Gross) & BOX 38 (Net): Processing weights...
⚖️ Processing weight data:
   Original Net Weight: ''
   Original Gross Weight: '254 KGS'
...
✅ Net Weight: 254 (fallback_from_gross)
✅ Gross Weight: 254
   JSON: {...}
```

#### Marks (Box 31)
**Source:** `process_esad.py` lines 705-717
**Processor:** `esad_modules/secondary/esad_marks.py`
```
📝 BOX 31: Processing marks and numbers...
✅ Marks: N/A
```

#### Warehouse (Box 49)
**Source:** `process_esad.py` lines 720-740
**Processor:** `esad_modules/secondary/esad_warehouse.py`
```
🏢 BOX 49: Processing warehouse information...
✅ Box 49 left blank (no warehousing CPC)
```

#### Country Processing (Silent)
**Source:** `process_esad.py` lines 743-751
**Processor:** `esad_modules/secondary/esad_country.py`
**THIS IS WHERE 404 ERRORS OCCUR** - uses invalid `openai/gpt-5-nano` model

#### Office Code (Silent)
**Source:** `process_esad.py` lines 754-762
**Processor:** `esad_modules/core/esad_office_code.py`

#### Location (Box 30)
**Source:** `process_esad.py` lines 765-780
**Processor:** `esad_modules/secondary/esad_location.py`
```
📍 BOX 30 (Location of goods): Processing warehouse location...
✅ Warehouse Code: OSC01
   └─ Warehouse: KINGSTON ONE STOP CUSTOMS
   └─ Office ID: JMOSC
```

#### LOCODE (Box 27)
**Source:** `process_esad.py` lines 783-797
**Processor:** `esad_modules/secondary/esad_locode.py`
```
🚢 BOX 27 (Place of unloading): Processing LOCODE...
✅ Jamaican Port: Kingston
   └─ LOCODE: JMKIN
   └─ Location: Kingston
```

#### Reference Numbers (Box 7)
**Source:** `process_esad.py` lines 800-812
**Processor:** `esad_modules/secondary/esad_ref_number.py`
```
🔢 BOX 7: Processing reference numbers...
❌ Reference processing failed: No order ID found
```

#### Transaction Type (Box 24)
**Source:** `process_esad.py` lines 815-827
**Processor:** `esad_modules/secondary/esad_trans_type.py`
```
💼 BOX 24: Processing transaction type...
✅ Transaction Type: 1.1
```

#### TRN Lookup (Boxes 2/8)
**Source:** `process_esad.py` lines 830-842
**Processor:** `esad_modules/secondary/esad_trn.py`
```
🏛️ IDs (Boxes 2/8): Processing TRN...
📋 Extracted exporter name: ...
🔍 Looking up TRN for company: ...
  🧹 Cleaned company name: ...
  ❌ No TRN found for company: ...
  🔍 Fuzzy match found: ...
✅ TRN: 1141034960000
```

---

## Completion
**Source:** `process_esad.py` line 846
```
✅ eSAD Processing Complete
```

---

## 404 ERROR SOURCES

The 404 errors occur in **TWO locations**:

### 1. Country Processing (Silent Operation)
**File:** `customs_api/modules/esad_processor/esad_modules/secondary/esad_country.py`
**Line:** 141
**Problem:** Uses `"openai/gpt-5-nano"` which doesn't exist
```python
priority_models = [
    "openai/gpt-5-nano",  # ❌ INVALID MODEL
    "moonshotai/kimi-k2:free"
]
```

### 2. Package Type Processing
**File:** `customs_api/modules/esad_processor/esad_modules/secondary/esad_pkg.py`
**Line:** 81
**Problem:** Uses `OPENROUTER_GENERAL_MODELS["gpt_5"]` which maps to `"openai/gpt-5"`
```python
priority_models = [
    OPENROUTER_GENERAL_MODELS["gpt_5"],  # ❌ MAPS TO "openai/gpt-5" (invalid)
    OPENROUTER_GENERAL_MODELS["kimi_standard"]
]
```

---

## Summary of All Source Files

### Main Application Flow
1. `customs_api/app.py` - Server startup, workflow orchestration
2. `customs_api/modules/order_process/process_order.py` - Order creation
3. `customs_api/modules/extraction_process/document_processor.py` - Document extraction config
4. `customs_api/modules/extraction_process/bol_extract.py` - BOL extraction

### eSAD Processing (Core)
5. `customs_api/modules/esad_processor/process_esad.py` - Main orchestrator
6. `customs_api/modules/esad_processor/esad_modules/core/esad_product.py` - Product classification
7. `customs_api/modules/esad_processor/esad_modules/core/esad_cif.py` - CIF calculation
8. `customs_api/modules/esad_processor/esad_modules/core/esad_regime.py` - Regime determination
9. `customs_api/modules/esad_processor/esad_modules/core/esad_manifest.py` - Manifest tracking
10. `customs_api/modules/esad_processor/esad_modules/core/esad_office_code.py` - Office code lookup

### eSAD Processing (Secondary)
11. `customs_api/modules/esad_processor/esad_modules/secondary/esad_address.py` - Address formatting
12. `customs_api/modules/esad_processor/esad_modules/secondary/esad_pkg.py` - Package types (❌ 404 errors)
13. `customs_api/modules/esad_processor/esad_modules/secondary/esad_transport_mode.py` - Transport mode
14. `customs_api/modules/esad_processor/esad_modules/secondary/esad_weight.py` - Weight processing
15. `customs_api/modules/esad_processor/esad_modules/secondary/esad_marks.py` - Marks and numbers
16. `customs_api/modules/esad_processor/esad_modules/secondary/esad_warehouse.py` - Warehouse lookup
17. `customs_api/modules/esad_processor/esad_modules/secondary/esad_country.py` - Country codes (❌ 404 errors)
18. `customs_api/modules/esad_processor/esad_modules/secondary/esad_location.py` - Location/warehouse
19. `customs_api/modules/esad_processor/esad_modules/secondary/esad_locode.py` - Port LOCODE
20. `customs_api/modules/esad_processor/esad_modules/secondary/esad_ref_number.py` - Reference numbers
21. `customs_api/modules/esad_processor/esad_modules/secondary/esad_trans_type.py` - Transaction type
22. `customs_api/modules/esad_processor/esad_modules/secondary/esad_trn.py` - TRN lookup

---

## Recommendations for Log Efficiency

### Issues Identified:
1. **Too much verbose output** - Each processor prints its own initialization messages
2. **Duplicate information** - Invoice/BOL data printed in full detail
3. **Silent failures** - Country processing fails silently in background
4. **Mixed logging levels** - Some processors print, others don't
5. **No structured logging** - All `print()` statements, no log levels

### Suggested Improvements:
1. Implement proper Python `logging` module with levels (DEBUG, INFO, WARNING, ERROR)
2. Add `--verbose` flag to control output detail
3. Move initialization messages to DEBUG level
4. Consolidate all `[WF]` workflow messages to INFO level
5. Create a single summary table at the end instead of individual processor outputs
6. Use structured JSON logging for machine parsing
7. Suppress processor initialization messages by default

