import json
import sys

sys.path.insert(0, 'customs_api')

from modules.esad_processor.esad_modules.core.esad_regime import RegimeTypeProcessor

# Load BOL and Invoice data
with open('customs_api/processed_orders/ORD-20251009-002/bills_of_lading/bill_of_lading_ORD-20251009-002_primary_extract.json') as f:
    bol_data = json.load(f)

with open('customs_api/processed_orders/ORD-20251009-002/invoices/invoice_ORD-20251009-002_invoice_1_extract.json') as f:
    invoice_data = json.load(f)

# Initialize processor
processor = RegimeTypeProcessor()

# Determine regime type
result = processor.determine_regime_type({
    'invoice_data': invoice_data,
    'bol_data': bol_data
})

# Display results
print('\n' + '='*70)
print('REGIME TYPE DETERMINATION RESULTS')
print('='*70)
print(f'Regime Type: {result.regime_type}')
print(f'Procedure Code: {result.procedure_code}')
print(f'Description: {result.description}')
print(f'Confidence: {result.confidence}')
print(f'Direction: {result.import_export_direction}')
print(f'Commercial Determination: {result.commercial_determination}')

print(f'\n{"="*70}')
print('REGIME SELECTION REASONING')
print('='*70)
print(result.reasoning)

# Product classification details
prod_class = result.contextual_factors.get('product_classification', {})
print(f'\n{"="*70}')
print('COMMERCIAL/PERSONAL CLASSIFICATION')
print('='*70)
print(f'Classification: {prod_class.get("classification", "Unknown")}')
print(f'Confidence: {prod_class.get("confidence", "unknown")}')
print(f'Products Analyzed: {prod_class.get("products_analyzed", 0)}')

reasoning = prod_class.get('reasoning', 'N/A')
print(f'\n{"="*70}')
print('CLASSIFICATION REASONING')
print('='*70)
print(reasoning)

contextual = prod_class.get('contextual_reasoning', 'N/A')
print(f'\n{"="*70}')
print('CONTEXTUAL REASONING')
print('='*70)
print(contextual)

consignee_analysis = prod_class.get('consignee_analysis', 'N/A')
print(f'\n{"="*70}')
print('CONSIGNEE ANALYSIS')
print('='*70)
print(consignee_analysis)

quantity_analysis = prod_class.get('quantity_analysis', 'N/A')
print(f'\n{"="*70}')
print('QUANTITY ANALYSIS')
print('='*70)
print(quantity_analysis)

commercial_indicators = prod_class.get('commercial_indicators', [])
if commercial_indicators:
    print(f'\n{"="*70}')
    print('COMMERCIAL INDICATORS')
    print('='*70)
    for ind in commercial_indicators:
        print(f'   • {ind}')

personal_indicators = prod_class.get('personal_indicators', [])
if personal_indicators:
    print(f'\n{"="*70}')
    print('PERSONAL INDICATORS')
    print('='*70)
    for ind in personal_indicators:
        print(f'   • {ind}')

grey_zone = prod_class.get('grey_zone_products', [])
if grey_zone:
    print(f'\n{"="*70}')
    print('GREY ZONE PRODUCTS')
    print('='*70)
    for prod in grey_zone:
        print(f'   • {prod}')

risk_flags = prod_class.get('risk_flags', [])
if risk_flags:
    print(f'\n{"="*70}')
    print('RISK FLAGS')
    print('='*70)
    for flag in risk_flags:
        print(f'   • {flag}')
else:
    print(f'\n{"="*70}')
    print('RISK FLAGS')
    print('='*70)
    print('   None identified')

# Simplified JSON Output
print(f'\n{"="*70}')
print('JSON OUTPUT')
print('='*70)
output = {
    'regime_type': result.regime_type,
    'procedure_code': result.procedure_code,
    'description': result.description,
    'confidence': result.confidence,
    'reasoning': result.reasoning,
    'import_export_direction': result.import_export_direction,
    'commercial_determination': result.commercial_determination,
    'product_classification': {
        'classification': prod_class.get('classification'),
        'confidence': prod_class.get('confidence'),
        'reasoning': prod_class.get('reasoning')
    }
}
print(json.dumps(output, indent=2))

