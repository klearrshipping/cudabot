#!/usr/bin/env python3
"""
eSAD Modules Independent Testing Script
Minimal test script that loads data and calls eSAD modules with verbose output
"""

import json
import time
import sys
import os

class ESADTester:
    def __init__(self):
        """Initialize the tester and load test data."""
        self.invoice_data = None
        self.bol_data = None
        self.results = {}
        self.load_test_data()
    
    def load_test_data(self):
        """Load invoice and BOL JSON files."""
        try:
            invoice_file = r"C:\Users\rafer\OneDrive\Desktop\projects\cuda\customs_api\processed_orders\ORD-20251015-001\invoices\invoice_ORD-20251015-001_invoice_1_extract.json"
            bol_file = r"C:\Users\rafer\OneDrive\Desktop\projects\cuda\customs_api\processed_orders\ORD-20251015-001\bills_of_lading\bill_of_lading_ORD-20251015-001_primary_extract.json"
            
            with open(invoice_file, 'r', encoding='utf-8') as f:
                self.invoice_data = json.load(f)
            
            with open(bol_file, 'r', encoding='utf-8') as f:
                self.bol_data = json.load(f)
                
        except Exception as e:
            print(f"❌ Error loading test data: {e}")
            sys.exit(1)
    
    def test_esad_cif(self):
        """Test CIF component extraction."""
        print("\n🧮 Testing esad_cif.py - CIF Component Extraction")
        print("-" * 50)
        
        try:
            from modules.esad_processor.esad_modules.core.esad_cif import process_cif_fields
            
            start_time = time.time()
            result = process_cif_fields(self.invoice_data, self.bol_data, verbose=False)
            processing_time = time.time() - start_time
            
            self.results['esad_cif'] = {
                'success': True,
                'processing_time': processing_time,
                'result': result
            }
            
            # Display clean JSON result
            if result.get('success') != False:
                print(f"\n📋 Final Result: {json.dumps(result, indent=2, ensure_ascii=False)}")
            else:
                print(f"❌ Error: {result.get('error', 'Unknown error')}")
            
        except ImportError as e:
            self.results['esad_cif'] = {'success': False, 'error': str(e)}
        except Exception as e:
            self.results['esad_cif'] = {'success': False, 'error': str(e)}
    
    def test_esad_regime(self):
        """Test regime type determination."""
        print("\n📋 Testing esad_regime.py - Regime Type Determination")
        print("-" * 50)
        
        try:
            from modules.esad_processor.esad_modules.core.esad_regime import RegimeTypeProcessor
            
            processor = RegimeTypeProcessor()
            extracted_data = {
                'invoice_data': self.invoice_data,
                'bol_data': self.bol_data
            }
            
            start_time = time.time()
            result = processor.process_regime_type(extracted_data)
            processing_time = time.time() - start_time
            
            self.results['esad_regime'] = {
                'success': True,
                'processing_time': processing_time,
                'result': result
            }
            
            # Display clean JSON result
            if result.get('success'):
                clean_result = {
                    "success": result['success'],
                    "regime_type": result.get('regime_type'),
                    "confidence": result.get('confidence'),
                    "reasoning": result.get('reasoning')
                }
                print(f"\n📋 Final Result: {json.dumps(clean_result, indent=2, ensure_ascii=False)}")
            else:
                print(f"❌ Error: {result.get('error', 'Unknown error')}")
            
        except ImportError as e:
            self.results['esad_regime'] = {'success': False, 'error': str(e)}
        except Exception as e:
            self.results['esad_regime'] = {'success': False, 'error': str(e)}
    
    def test_esad_office_code(self):
        """Test office code extraction."""
        print("\n🏢 Testing esad_office_code.py - Office Code Extraction")
        print("-" * 50)
        
        try:
            from modules.esad_processor.esad_modules.core.esad_office_code import extract_office_code
            
            start_time = time.time()
            result = extract_office_code(self.bol_data, verbose=True)
            processing_time = time.time() - start_time
            
            self.results['esad_office_code'] = {
                'success': True,
                'processing_time': processing_time,
                'result': result
            }
            
        except ImportError as e:
            self.results['esad_office_code'] = {'success': False, 'error': str(e)}
        except Exception as e:
            self.results['esad_office_code'] = {'success': False, 'error': str(e)}
    
    def test_esad_ports(self):
        """Test port extraction."""
        print("\n🚢 Testing esad_ports.py - Port Extraction")
        print("-" * 50)
        
        try:
            from modules.esad_processor.esad_modules.core.esad_ports import extract_ports_from_bol
            
            start_time = time.time()
            result = extract_ports_from_bol(self.bol_data, self.invoice_data, verbose=True)
            processing_time = time.time() - start_time
            
            self.results['esad_ports'] = {
                'success': True,
                'processing_time': processing_time,
                'result': result
            }
            
        except ImportError as e:
            self.results['esad_ports'] = {'success': False, 'error': str(e)}
        except Exception as e:
            self.results['esad_ports'] = {'success': False, 'error': str(e)}
    
    def test_esad_product_classification(self):
        """Test product classification."""
        print("\n🏷️  Testing esad_product_classification.py - Product Classification")
        print("-" * 50)
        
        try:
            from modules.esad_processor.esad_modules.core.esad_product_classification import classify_product_commercial_vs_personal
            
            start_time = time.time()
            result = classify_product_commercial_vs_personal(self.invoice_data, self.bol_data, verbose=False)
            processing_time = time.time() - start_time
            
            self.results['esad_product_classification'] = {
                'success': True,
                'processing_time': processing_time,
                'result': result
            }
            
            # Display clean JSON result
            if result.get('success'):
                clean_result = {
                    "success": result['success'],
                    "is_commercial": result.get('is_commercial'),
                    "confidence": result.get('confidence'),
                    "reasoning": result.get('reasoning'),
                    "key_indicators": result.get('key_indicators')
                }
                print(f"\n📋 Final Result: {json.dumps(clean_result, indent=2, ensure_ascii=False)}")
            else:
                print(f"❌ Error: {result.get('error', 'Unknown error')}")
            
        except ImportError as e:
            self.results['esad_product_classification'] = {'success': False, 'error': str(e)}
        except Exception as e:
            self.results['esad_product_classification'] = {'success': False, 'error': str(e)}
    
    def test_esad_product(self):
        """Test product name extraction."""
        print("\n📦 Testing esad_product.py - Product Name Extraction")
        print("-" * 50)
        
        try:
            from modules.esad_processor.esad_modules.core.esad_product import ProductProcessor
            
            processor = ProductProcessor()
            
            # Prepare input data with invoice and BOL data
            input_data = {
                'invoice_data': self.invoice_data,
                'bol_data': self.bol_data
            }
            
            start_time = time.time()
            result = processor.process(input_data)
            processing_time = time.time() - start_time
            
            self.results['esad_product'] = {
                'success': True,
                'processing_time': processing_time,
                'result': result
            }
            
            # Display clean JSON result
            if result.get('success'):
                clean_result = {
                    "success": result['success'],
                    "product_name": result.get('product_name'),
                    "commercial_description": result.get('commercial_description'),
                    "hs_code": result.get('hs_code'),
                    "commodity_code": result.get('commodity_code'),
                    "hs_description": result.get('hs_description'),
                    "processing_notes": result.get('processing_notes')
                }
                print(f"\n📋 Final Result: {json.dumps(clean_result, indent=2, ensure_ascii=False)}")
            elif result.get('success') == False:
                print(f"❌ Error: {result.get('error', 'Unknown error')}")
            else:
                print(f"❌ Error: Unexpected result format")
            
        except ImportError as e:
            self.results['esad_product'] = {'success': False, 'error': str(e)}
        except Exception as e:
            self.results['esad_product'] = {'success': False, 'error': str(e)}
    
    def test_esad_country(self):
        """Test country ISO2 matching."""
        print("\n🌍 Testing esad_country.py - Country ISO2 Matching")
        print("-" * 50)
        
        try:
            from modules.esad_processor.esad_modules.secondary.esad_country import process_country_iso2_codes
            
            start_time = time.time()
            result = process_country_iso2_codes(self.bol_data, self.invoice_data, verbose=True)
            processing_time = time.time() - start_time
            
            self.results['esad_country'] = {
                'success': True,
                'processing_time': processing_time,
                'result': result
            }
            
        except ImportError as e:
            self.results['esad_country'] = {'success': False, 'error': str(e)}
        except Exception as e:
            self.results['esad_country'] = {'success': False, 'error': str(e)}
    
    def test_esad_pkg(self):
        """Test package type classification."""
        print("\n📦 Testing esad_pkg.py - Package Type Classification")
        print("-" * 50)
        
        try:
            from modules.esad_processor.esad_modules.secondary.esad_pkg import PackageProcessor
            
            processor = PackageProcessor()
            
            # Extract package information from BOL data
            kind_of_packages = ""
            if 'containers_packages' in self.bol_data:
                for container in self.bol_data['containers_packages']:
                    if 'packages' in container:
                        kind_of_packages = container['packages']
                        break
            
            if not kind_of_packages:
                kind_of_packages = "Box"  # Default test value
            
            start_time = time.time()
            result = processor.process_package_type(kind_of_packages, verbose=True)
            processing_time = time.time() - start_time
            
            self.results['esad_pkg'] = {
                'success': True,
                'processing_time': processing_time,
                'result': result
            }
            
            # Display clean JSON result
            if result.get('success'):
                clean_result = {
                    "success": result['success'],
                    "package_code": result.get('package_code'),
                    "package_description": result.get('package_description'),
                    "confidence": result.get('confidence'),
                    "reasoning": result.get('reasoning')
                }
                print(f"\n📋 Final Result: {json.dumps(clean_result, indent=2, ensure_ascii=False)}")
            else:
                print(f"❌ Error: {result.get('error', 'Unknown error')}")
            
        except ImportError as e:
            self.results['esad_pkg'] = {'success': False, 'error': str(e)}
        except Exception as e:
            self.results['esad_pkg'] = {'success': False, 'error': str(e)}
    
    def test_esad_address(self):
        """Test address formatting."""
        print("\n🏠 Testing esad_address.py - Address Formatting")
        print("-" * 50)
        
        try:
            from modules.esad_processor.esad_modules.secondary.esad_address import AddressFormatter
            
            formatter = AddressFormatter()
            
            # Extract address information from invoice data
            test_addresses = []
            if 'buyer' in self.invoice_data and 'address' in self.invoice_data['buyer']:
                test_addresses.append(self.invoice_data['buyer']['address'])
            if 'supplier' in self.invoice_data and 'address' in self.invoice_data['supplier']:
                test_addresses.append(self.invoice_data['supplier']['address'])
            
            if not test_addresses:
                test_addresses = ["123 Main St, Kingston, Jamaica"]  # Default test value
            
            start_time = time.time()
            results = []
            for address in test_addresses:
                result = formatter.format_address(address)
                results.append({
                    'original': address,
                    'formatted': result.formatted,
                    'confidence': result.confidence
                })
            processing_time = time.time() - start_time
            
            self.results['esad_address'] = {
                'success': True,
                'processing_time': processing_time,
                'result': results
            }
            
            # Display clean JSON result
            if results:
                clean_result = {
                    "success": True,
                    "formatted_addresses": results
                }
                print(f"\n📋 Final Result: {json.dumps(clean_result, indent=2, ensure_ascii=False)}")
            else:
                print(f"❌ Error: No addresses processed")
            
        except ImportError as e:
            self.results['esad_address'] = {'success': False, 'error': str(e)}
        except Exception as e:
            self.results['esad_address'] = {'success': False, 'error': str(e)}
    
    def test_esad_trans_type(self):
        """Test transaction type determination."""
        print("\n💼 Testing esad_trans_type.py - Transaction Type Determination")
        print("-" * 50)
        
        try:
            from modules.esad_processor.esad_modules.secondary.esad_trans_type import TransactionTypeProcessor
            
            processor = TransactionTypeProcessor()
            
            # Prepare input data
            input_data = {
                'bol_data': self.bol_data,
                'invoice_data': self.invoice_data
            }
            
            start_time = time.time()
            result = processor.process(input_data)
            processing_time = time.time() - start_time
            
            self.results['esad_trans_type'] = {
                'success': True,
                'processing_time': processing_time,
                'result': result
            }
            
            # Display clean JSON result
            if result.get('success'):
                clean_result = {
                    "success": result['success'],
                    "transaction_type": result.get('transaction_type'),
                    "transaction_description": result.get('transaction_description'),
                    "detail_description": result.get('detail_description'),
                    "reasoning": result.get('reasoning')
                }
                print(f"\n📋 Final Result: {json.dumps(clean_result, indent=2, ensure_ascii=False)}")
            else:
                print(f"❌ Error: {result.get('error', 'Unknown error')}")
            
        except ImportError as e:
            self.results['esad_trans_type'] = {'success': False, 'error': str(e)}
        except Exception as e:
            self.results['esad_trans_type'] = {'success': False, 'error': str(e)}
    
    def test_esad_locode(self):
        """Test LOCODE processing."""
        print("\n🌐 Testing esad_locode.py - LOCODE Processing")
        print("-" * 50)
        
        try:
            from modules.esad_processor.esad_modules.secondary.esad_locode import LocodeProcessor
            
            processor = LocodeProcessor()
            
            # Prepare input data
            input_data = {
                'bol_data': self.bol_data
            }
            
            start_time = time.time()
            result = processor.process(input_data)
            processing_time = time.time() - start_time
            
            self.results['esad_locode'] = {
                'success': True,
                'processing_time': processing_time,
                'result': result
            }
            
        except ImportError as e:
            self.results['esad_locode'] = {'success': False, 'error': str(e)}
        except Exception as e:
            self.results['esad_locode'] = {'success': False, 'error': str(e)}
    
    def test_esad_marks(self):
        """Test marks and numbers processing."""
        print("\n🔢 Testing esad_marks.py - Marks and Numbers Processing")
        print("-" * 50)
        
        try:
            from modules.esad_processor.esad_modules.secondary.esad_marks import MarksProcessor
            
            processor = MarksProcessor()
            
            # Prepare input data
            input_data = {
                'bol_data': self.bol_data,
                'invoice_data': self.invoice_data
            }
            
            start_time = time.time()
            result = processor.process(input_data)
            processing_time = time.time() - start_time
            
            self.results['esad_marks'] = {
                'success': True,
                'processing_time': processing_time,
                'result': result
            }
            
        except ImportError as e:
            self.results['esad_marks'] = {'success': False, 'error': str(e)}
        except Exception as e:
            self.results['esad_marks'] = {'success': False, 'error': str(e)}
    
    def test_esad_manifest(self):
        """Test manifest processing."""
        print("\n📋 Testing esad_manifest.py - Manifest Processing")
        print("-" * 50)
        
        try:
            from modules.esad_processor.esad_modules.core.esad_manifest import main
            
            # Extract manifest number from BOL data
            manifest_number = ""
            if 'bill_of_lading' in self.bol_data:
                manifest_number = self.bol_data['bill_of_lading']
            elif 'bol_number' in self.bol_data:
                manifest_number = self.bol_data['bol_number']
            elif 'manifest_registration_number' in self.bol_data:
                manifest_number = self.bol_data['manifest_registration_number']
            
            if not manifest_number:
                manifest_number = "TEST123456"  # Default test value
            
            start_time = time.time()
            result = main(manifest_number=manifest_number, verbose=True)  # Pass real data to main function
            processing_time = time.time() - start_time
            
            self.results['esad_manifest'] = {
                'success': True,
                'processing_time': processing_time,
                'result': result
            }
            
        except ImportError as e:
            self.results['esad_manifest'] = {'success': False, 'error': str(e)}
        except Exception as e:
            self.results['esad_manifest'] = {'success': False, 'error': str(e)}
    
    def test_esad_location(self):
        """Test location processing."""
        print("\n📍 Testing esad_location.py - Location Processing")
        print("-" * 50)
        
        try:
            from modules.esad_processor.esad_modules.secondary.esad_location import LocationProcessor
            
            processor = LocationProcessor()
            
            # Prepare input data
            input_data = {
                'bol_data': self.bol_data
            }
            
            start_time = time.time()
            result = processor.process(input_data)
            processing_time = time.time() - start_time
            
            self.results['esad_location'] = {
                'success': True,
                'processing_time': processing_time,
                'result': result
            }
            
        except ImportError as e:
            self.results['esad_location'] = {'success': False, 'error': str(e)}
        except Exception as e:
            self.results['esad_location'] = {'success': False, 'error': str(e)}
    
    def test_esad_ref_number(self):
        """Test reference number processing."""
        print("\n🔢 Testing esad_ref_number.py - Reference Number Processing")
        print("-" * 50)
        
        try:
            from modules.esad_processor.esad_modules.secondary.esad_ref_number import CommercialReferenceProcessor
            
            processor = CommercialReferenceProcessor()
            
            # Prepare input data
            input_data = {
                'bol_data': self.bol_data,
                'invoice_data': self.invoice_data
            }
            
            start_time = time.time()
            result = processor.process(input_data)
            processing_time = time.time() - start_time
            
            self.results['esad_ref_number'] = {
                'success': True,
                'processing_time': processing_time,
                'result': result
            }
            
        except ImportError as e:
            self.results['esad_ref_number'] = {'success': False, 'error': str(e)}
        except Exception as e:
            self.results['esad_ref_number'] = {'success': False, 'error': str(e)}
    
    def test_esad_transport_mode(self):
        """Test transport mode processing."""
        print("\n🚚 Testing esad_transport_mode.py - Transport Mode Processing")
        print("-" * 50)
        
        try:
            from modules.esad_processor.esad_modules.secondary.esad_transport_mode import TransportModeProcessor
            
            processor = TransportModeProcessor()
            
            # Prepare input data
            input_data = {
                'bol_data': self.bol_data
            }
            
            start_time = time.time()
            result = processor.process(input_data)
            processing_time = time.time() - start_time
            
            self.results['esad_transport_mode'] = {
                'success': True,
                'processing_time': processing_time,
                'result': result
            }
            
        except ImportError as e:
            self.results['esad_transport_mode'] = {'success': False, 'error': str(e)}
        except Exception as e:
            self.results['esad_transport_mode'] = {'success': False, 'error': str(e)}
    
    def test_esad_trn(self):
        """Test TRN (Tax Registration Number) processing."""
        print("\n🏛️ Testing esad_trn.py - TRN Processing")
        print("-" * 50)
        
        try:
            from modules.esad_processor.esad_modules.secondary.esad_trn import TRNLookupProcessor
            
            processor = TRNLookupProcessor()
            
            # Prepare input data
            input_data = {
                'bol_data': self.bol_data,
                'invoice_data': self.invoice_data
            }
            
            start_time = time.time()
            result = processor.process(input_data)
            processing_time = time.time() - start_time
            
            self.results['esad_trn'] = {
                'success': True,
                'processing_time': processing_time,
                'result': result
            }
            
        except ImportError as e:
            self.results['esad_trn'] = {'success': False, 'error': str(e)}
        except Exception as e:
            self.results['esad_trn'] = {'success': False, 'error': str(e)}
    
    def test_esad_warehouse(self):
        """Test warehouse processing."""
        print("\n🏪 Testing esad_warehouse.py - Warehouse Processing")
        print("-" * 50)
        
        try:
            from modules.esad_processor.esad_modules.secondary.esad_warehouse import WarehouseProcessor
            
            processor = WarehouseProcessor()
            
            # Prepare input data
            input_data = {
                'bol_data': self.bol_data
            }
            
            start_time = time.time()
            result = processor.process(input_data)
            processing_time = time.time() - start_time
            
            self.results['esad_warehouse'] = {
                'success': True,
                'processing_time': processing_time,
                'result': result
            }
            
        except ImportError as e:
            self.results['esad_warehouse'] = {'success': False, 'error': str(e)}
        except Exception as e:
            self.results['esad_warehouse'] = {'success': False, 'error': str(e)}
    
    def test_esad_weight(self):
        """Test weight processing."""
        print("\n⚖️ Testing esad_weight.py - Weight Processing")
        print("-" * 50)
        
        try:
            from modules.esad_processor.esad_modules.secondary.esad_weight import WeightProcessor
            
            processor = WeightProcessor()
            
            # Prepare input data
            input_data = {
                'bol_data': self.bol_data,
                'invoice_data': self.invoice_data
            }
            
            start_time = time.time()
            result = processor.process(input_data)
            processing_time = time.time() - start_time
            
            self.results['esad_weight'] = {
                'success': True,
                'processing_time': processing_time,
                'result': result
            }
            
        except ImportError as e:
            self.results['esad_weight'] = {'success': False, 'error': str(e)}
        except Exception as e:
            self.results['esad_weight'] = {'success': False, 'error': str(e)}
    
    def test_all_modules(self):
        """Test all modules in batch."""
        print("\n🔄 Testing All Modules (Batch)")
        print("=" * 60)
        
        test_functions = [
            # Core modules
            self.test_esad_cif,
            self.test_esad_regime,
            self.test_esad_office_code,
            self.test_esad_ports,
            self.test_esad_product_classification,
            self.test_esad_product,
            self.test_esad_manifest,
            
            # Secondary modules
            self.test_esad_country,
            self.test_esad_pkg,
            self.test_esad_address,
            self.test_esad_trans_type,
            self.test_esad_locode,
            self.test_esad_marks,
            self.test_esad_location,
            self.test_esad_ref_number,
            self.test_esad_transport_mode,
            self.test_esad_trn,
            self.test_esad_warehouse,
            self.test_esad_weight
        ]
        
        for test_func in test_functions:
            try:
                test_func()
            except Exception as e:
                # Swallow unexpected errors; store to results when possible
                name = getattr(test_func, '__name__', 'unknown')
                self.results[name] = {'success': False, 'error': str(e)}
        
        print("\n✅ All modules tested!")
    
    def inspect_data(self):
        """Inspect loaded test data."""
        print("\n🔍 Inspecting Loaded Data")
        print("=" * 40)
        print(f"📄 Invoice data loaded: {len(json.dumps(self.invoice_data))} characters")
        print(f"📄 BOL data loaded: {len(json.dumps(self.bol_data))} characters")
        print("✅ Test data loaded successfully!")
    
    def view_results_summary(self):
        """View test results summary."""
        print("\n📊 Test Results Summary")
        print("=" * 40)
        
        if not self.results:
            print("No test results available. Run some tests first.")
            return
        
        for module_name, result in self.results.items():
            status = "✅ Success" if result.get('success') else "❌ Failed"
            processing_time = result.get('processing_time', 0)
            print(f"{module_name}: {status} ({processing_time:.2f}s)")
            
            if not result.get('success'):
                print(f"  Error: {result.get('error', 'Unknown error')}")
    
    def run(self):
        """Main interactive loop."""
        print("🔬 eSAD Modules Independent Testing Script")
        print("Loading test data...")
        print("✅ Test data loaded successfully!")
        
        while True:
            self.show_menu()
            try:
                choice = input("\nEnter your choice (0-22): ").strip()
                
                if choice == '0':
                    print("👋 Goodbye!")
                    break
                elif choice == '1':
                    self.test_esad_cif()
                elif choice == '2':
                    self.test_esad_regime()
                elif choice == '3':
                    self.test_esad_office_code()
                elif choice == '4':
                    self.test_esad_ports()
                elif choice == '5':
                    self.test_esad_product_classification()
                elif choice == '6':
                    self.test_esad_product()
                elif choice == '7':
                    self.test_esad_manifest()
                elif choice == '8':
                    self.test_esad_country()
                elif choice == '9':
                    self.test_esad_pkg()
                elif choice == '10':
                    self.test_esad_address()
                elif choice == '11':
                    self.test_esad_trans_type()
                elif choice == '12':
                    self.test_esad_locode()
                elif choice == '13':
                    self.test_esad_marks()
                elif choice == '14':
                    self.test_esad_location()
                elif choice == '15':
                    self.test_esad_ref_number()
                elif choice == '16':
                    self.test_esad_transport_mode()
                elif choice == '17':
                    self.test_esad_trn()
                elif choice == '18':
                    self.test_esad_warehouse()
                elif choice == '19':
                    self.test_esad_weight()
                elif choice == '20':
                    self.test_all_modules()
                elif choice == '21':
                    self.inspect_data()
                elif choice == '22':
                    self.view_results_summary()
                else:
                    print("❌ Invalid choice. Please try again.")
                
                input("\nPress Enter to continue...")
                
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception:
                # Swallow unexpected loop errors
                input("\nPress Enter to continue...")
    
    def show_menu(self):
        """Display the main menu."""
        print("\n" + "=" * 60)
        print("🔬 eSAD MODULES INDEPENDENT TESTING")
        print("=" * 60)
        print("CORE MODULES:")
        print("1.  esad_cif.py - CIF component extraction")
        print("2.  esad_regime.py - Regime type determination")
        print("3.  esad_office_code.py - Office code extraction")
        print("4.  esad_ports.py - Port extraction")
        print("5.  esad_product_classification.py - Product classification")
        print("6.  esad_product.py - Product name extraction")
        print("7.  esad_manifest.py - Manifest processing")
        print("")
        print("SECONDARY MODULES:")
        print("8.  esad_country.py - Country ISO2 matching")
        print("9.  esad_pkg.py - Package type classification")
        print("10. esad_address.py - Address formatting")
        print("11. esad_trans_type.py - Transaction type determination")
        print("12. esad_locode.py - LOCODE processing")
        print("13. esad_marks.py - Marks and numbers processing")
        print("14. esad_location.py - Location processing")
        print("15. esad_ref_number.py - Reference number processing")
        print("16. esad_transport_mode.py - Transport mode processing")
        print("17. esad_trn.py - TRN processing")
        print("18. esad_warehouse.py - Warehouse processing")
        print("19. esad_weight.py - Weight processing")
        print("")
        print("UTILITY OPTIONS:")
        print("20. Test all modules (batch)")
        print("21. Inspect loaded data")
        print("22. View test results summary")
        print("0.  Exit")
        print("=" * 60)


def main():
    """Main entry point."""
    # Add project paths for imports
    current_dir = os.path.dirname(os.path.abspath(__file__))
    customs_api_dir = os.path.join(current_dir, 'customs_api')
    sys.path.insert(0, customs_api_dir)
    sys.path.insert(0, current_dir)
    
    tester = ESADTester()
    tester.run()


if __name__ == "__main__":
    main()