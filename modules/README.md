# CUDA Modules Structure

## Overview
This directory contains all the processing modules organized by their function in the customs declaration workflow.

## Directory Structure

### 📁 `primary_processing/`
**First stage: Document extraction and parsing**
- `document_processor.py` - Main orchestrator for document processing
- `bol_extract.py` - Bill of lading extraction
- `invoice_extract.py` - Invoice extraction  
- `invoice_extract_cached.py` - Cached invoice extraction
- `shared/` - Shared utilities for primary processing

### 📁 `secondary_processing/`
**Second stage: ESAD field population and validation**
- `esad_primary.py` - Main ESAD field populator
- `esad_address.py` - Address-specific ESAD fields
- `esad_country.py` - Country-related ESAD fields
- `esad_manifest.py` - Manifest-specific ESAD fields
- `esad_marks.py` - Marks and numbers processing
- `esad_pkg.py` - Package information processing
- `esad_product.py` - Product/commodity details
- `esad_ref_number.py` - Reference number processing
- `esad_regime.py` - Regime type processing
- `esad_trans_type.py` - Transaction type processing
- `esad_weight.py` - Weight calculations
- `eSAD.json` - ESAD field definitions
- `shared/` - Shared utilities for ESAD processing

### 📁 `core/`
**Core system modules**
- `supabase_client.py` - Database client
- `llm_client.py` - LLM integration client
- `llm_cache.py` - Caching layer

### 📁 `utils/`
**General utilities**
- `file_utils.py` - File handling utilities
- `order_generator.py` - Order generation utilities

## Processing Flow
```
Documents → Primary Processing → Extracted Data → Secondary Processing → ESAD Fields
    ↓              ↓                    ↓              ↓
Invoice      bol_extract.py      BOL Data      esad_primary.py
BOL          invoice_extract.py  Invoice Data  esad_address.py
             document_processor.py              esad_manifest.py
```

## Import Guidelines
- Use relative imports within packages: `from .module import Class`
- Use absolute imports for cross-package dependencies: `from modules.core.supabase_client import get_supabase_client`
- Update import paths when moving files between directories
