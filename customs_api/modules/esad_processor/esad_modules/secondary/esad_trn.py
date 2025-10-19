#!/usr/bin/env python3
"""
ESAD TRN Lookup Script
Retrieves TRN numbers from client table based on company names
"""

import json
import re
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

# Import Supabase client for database operations
try:
    from config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
    from supabase import create_client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    print("⚠️ Supabase integration not available")

@dataclass
class TRNLookupResult:
    """Result of TRN lookup operation"""
    success: bool
    trn_number: Optional[str] = None
    company_name: Optional[str] = None
    match_type: Optional[str] = None  # 'exact', 'fuzzy', 'partial'
    confidence_score: Optional[float] = None
    error_message: Optional[str] = None
    multiple_matches: Optional[List[Dict[str, Any]]] = None

class TRNLookupProcessor:
    """
    TRN Lookup Processor
    Retrieves TRN numbers from client table using company name matching
    """
    
    def __init__(self):
        self.supabase = None
        
        if SUPABASE_AVAILABLE:
            try:
                self.supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
                print(f"✅ Connected to Supabase for TRN lookup (using service role)")
            except Exception as e:
                print(f"⚠️ Failed to connect to Supabase: {e}")
                self.supabase = None
    
    def lookup_trn_by_company_name(self, company_name: str, company_type: str = "importer") -> TRNLookupResult:
        """
        Lookup TRN number by company name
        
        Args:
            company_name: Company name to search for
            company_type: Type of company ('importer' or 'exporter') - kept for compatibility but not used in lookup
            
        Returns:
            TRNLookupResult: Result of the lookup operation
        """
        if not self.supabase:
            return TRNLookupResult(
                success=False,
                error_message="Supabase not available"
            )
        
        if not company_name or not company_name.strip():
            return TRNLookupResult(
                success=False,
                error_message="Company name is required"
            )
        
        try:
            print(f"🔍 Looking up TRN for company: {company_name}")
            
            # Clean and normalize company name
            cleaned_name = self._clean_company_name(company_name)
            print(f"  🧹 Cleaned company name: {cleaned_name}")
            
            # Try exact match first
            exact_match = self._exact_match_lookup(cleaned_name)
            if exact_match:
                print(f"  ✅ Exact match found: {exact_match['company_name']} -> TRN: {exact_match['trn_number']}")
                return TRNLookupResult(
                    success=True,
                    trn_number=exact_match['trn_number'],
                    company_name=exact_match['company_name'],
                    match_type='exact',
                    confidence_score=1.0
                )
            
            # Try fuzzy matching if no exact match
            fuzzy_matches = self._fuzzy_match_lookup(cleaned_name)
            if fuzzy_matches:
                if len(fuzzy_matches) == 1:
                    # Single fuzzy match
                    match = fuzzy_matches[0]
                    confidence = self._calculate_confidence(cleaned_name, match['company_name'])
                    print(f"  🔍 Fuzzy match found: {match['company_name']} -> TRN: {match['trn_number']} (confidence: {confidence:.2f})")
                    return TRNLookupResult(
                        success=True,
                        trn_number=match['trn_number'],
                        company_name=match['company_name'],
                        match_type='fuzzy',
                        confidence_score=confidence
                    )
                else:
                    # Multiple fuzzy matches
                    print(f"  ⚠️ Multiple fuzzy matches found ({len(fuzzy_matches)} matches)")
                    return TRNLookupResult(
                        success=False,
                        error_message=f"Multiple potential matches found for '{cleaned_name}'",
                        multiple_matches=fuzzy_matches
                    )
            
            # No matches found
            print(f"  ❌ No TRN found for company: {cleaned_name}")
            return TRNLookupResult(
                success=False,
                error_message=f"No TRN found for company: {cleaned_name}"
            )
            
        except Exception as e:
            print(f"  ❌ Error during TRN lookup: {e}")
            return TRNLookupResult(
                success=False,
                error_message=f"Error during TRN lookup: {str(e)}"
            )
    
    def _clean_company_name(self, company_name: str) -> str:
        """Clean and normalize company name for better matching"""
        if not company_name:
            return ""
        
        # Convert to uppercase and remove extra whitespace
        cleaned = re.sub(r'\s+', ' ', company_name.upper().strip())
        
        # Remove common business suffixes that don't affect matching
        suffixes_to_remove = [
            ' INC', ' LLC', ' LTD', ' CORP', ' CORPORATION', ' COMPANY', ' CO',
            ' PTY', ' PROPRIETARY', ' TRADING', ' ENTERPRISES', ' GROUP',
            ' INTERNATIONAL', ' INT\'L', ' INT', ' GLOBAL', ' WORLDWIDE'
        ]
        
        for suffix in suffixes_to_remove:
            if cleaned.endswith(suffix):
                cleaned = cleaned[:-len(suffix)]
                break
        
        # Remove punctuation
        cleaned = re.sub(r'[^\w\s]', '', cleaned)
        
        return cleaned.strip()
    
    def _exact_match_lookup(self, company_name: str) -> Optional[Dict[str, Any]]:
        """Look for exact match in client table"""
        try:
            # Query client table for exact entity name match
            query = self.supabase.table("clients").select("*").eq("entity_name", company_name)
            
            result = query.execute()
            
            if result.data and len(result.data) > 0:
                client = result.data[0]
                return {
                    "company_name": client.get("entity_name"),
                    "trn_number": client.get("trn_num"),
                    "client_id": client.get("id")
                }
            
            return None
            
        except Exception as e:
            print(f"    ❌ Error in exact match lookup: {e}")
            return None
    
    def _fuzzy_match_lookup(self, company_name: str) -> List[Dict[str, Any]]:
        """Look for fuzzy matches in client table"""
        try:
            # Query client table for partial matches
            query = self.supabase.table("clients").select("*")
            
            result = query.execute()
            
            if not result.data:
                return []
            
            # Find partial matches
            matches = []
            company_words = set(company_name.split())
            
            for client in result.data:
                client_name = client.get("entity_name", "")
                if client_name:
                    client_words = set(self._clean_company_name(client_name).split())
                    
                    # Calculate word overlap
                    common_words = company_words.intersection(client_words)
                    if len(common_words) >= 2:  # At least 2 words in common
                        confidence = len(common_words) / max(len(company_words), len(client_words))
                        if confidence >= 0.3:  # Minimum confidence threshold
                            matches.append({
                                "company_name": client.get("entity_name"),
                                "trn_number": client.get("trn_num"),
                                "client_id": client.get("id"),
                                "confidence": confidence
                            })
            
            # Sort by confidence score (highest first)
            matches.sort(key=lambda x: x["confidence"], reverse=True)
            
            return matches[:5]  # Return top 5 matches
            
        except Exception as e:
            print(f"    ❌ Error in fuzzy match lookup: {e}")
            return []
    
    def _calculate_confidence(self, search_name: str, match_name: str) -> float:
        """Calculate confidence score for fuzzy match"""
        search_words = set(search_name.split())
        match_words = set(match_name.split())
        
        if not search_words or not match_words:
            return 0.0
        
        # Calculate Jaccard similarity
        intersection = len(search_words.intersection(match_words))
        union = len(search_words.union(match_words))
        
        if union == 0:
            return 0.0
        
        return intersection / union
    
    def lookup_trn_from_documents(self, bol_data: Dict[str, Any], invoice_data: Dict[str, Any], address_data: Dict[str, Any] = None) -> Dict[str, TRNLookupResult]:
        """
        Extract company names from documents and lookup TRNs
        
        Args:
            bol_data: Bill of lading data
            invoice_data: Invoice data
            address_data: Optional address data with country information for consignor/consignee
            
        Returns:
            dict: TRN lookup results for exporter and importer
        """
        results = {}
        
        # Helper function to check if country is Jamaica
        def is_jamaican(country: Optional[str]) -> bool:
            if not country:
                return False
            country_upper = str(country).upper().strip()
            return country_upper in ['JAMAICA', 'JM', 'JAM']
        
        # Extract exporter/consignor information
        exporter_name = self._extract_exporter_name(bol_data)
        exporter_country = None
        if address_data and 'consignor' in address_data:
            exporter_country = address_data['consignor'].get('country')
        
        if exporter_name:
            print(f"📋 Extracted exporter name: {exporter_name}")
            
            # Check if exporter is Jamaican
            if is_jamaican(exporter_country):
                print(f"  🇯🇲 Exporter is Jamaican - TRN lookup required")
                results["exporter"] = self.lookup_trn_by_company_name(exporter_name, "exporter")
            else:
                country_display = exporter_country if exporter_country else "Unknown"
                print(f"  🌍 Exporter is non-Jamaican ({country_display}) - TRN not required")
                results["exporter"] = TRNLookupResult(
                    success=True,
                    trn_number=None,
                    company_name=exporter_name,
                    match_type='not_required',
                    confidence_score=None,
                    error_message=None
                )
        else:
            print("⚠️ Could not extract exporter name from BOL")
            results["exporter"] = TRNLookupResult(
                success=False,
                error_message="Could not extract exporter name from BOL"
            )
        
        # Extract importer/consignee information
        importer_name = self._extract_importer_name(bol_data)
        importer_country = None
        if address_data and 'consignee' in address_data:
            importer_country = address_data['consignee'].get('country')
        
        if importer_name:
            print(f"📋 Extracted importer name: {importer_name}")
            
            # Check if importer is Jamaican
            if is_jamaican(importer_country):
                print(f"  🇯🇲 Importer is Jamaican - TRN lookup required")
                results["importer"] = self.lookup_trn_by_company_name(importer_name, "importer")
            else:
                country_display = importer_country if importer_country else "Unknown"
                print(f"  🌍 Importer is non-Jamaican ({country_display}) - TRN not required")
                results["importer"] = TRNLookupResult(
                    success=True,
                    trn_number=None,
                    company_name=importer_name,
                    match_type='not_required',
                    confidence_score=None,
                    error_message=None
                )
        else:
            print("⚠️ Could not extract importer name from BOL")
            results["importer"] = TRNLookupResult(
                success=False,
                error_message="Could not extract importer name from BOL"
            )
        
        return results
    
    def _extract_exporter_name(self, bol_data: Dict[str, Any]) -> Optional[str]:
        """Extract exporter/consignor name from BOL data"""
        # Try different possible field names for exporter
        shipper = bol_data.get("shipper", "")
        
        # Handle nested structure (shipper as dict with 'name' key)
        if isinstance(shipper, dict):
            shipper = shipper.get("name", "")
        
        exporter_candidates = [
            shipper,
            bol_data.get("shipper_name", ""),
            bol_data.get("consignor", ""),
            bol_data.get("exporter", ""),
            bol_data.get("sender", "")
        ]
        
        # Return the first non-empty exporter name
        for exporter in exporter_candidates:
            if isinstance(exporter, dict):
                exporter = exporter.get("name", "")
            if exporter and str(exporter).strip():
                return str(exporter).strip()
        
        return None
    
    def _extract_importer_name(self, bol_data: Dict[str, Any]) -> Optional[str]:
        """Extract importer/consignee name from BOL data"""
        # Try different possible field names for importer
        consignee = bol_data.get("consignee", "")
        
        # Handle nested structure (consignee as dict with 'name' key)
        if isinstance(consignee, dict):
            consignee = consignee.get("name", "")
        
        notify = bol_data.get("notify_party", "")
        if isinstance(notify, dict):
            notify = notify.get("name", "")
        
        importer_candidates = [
            bol_data.get("consignee_name", ""),
            consignee,
            bol_data.get("importer", ""),
            bol_data.get("receiver", ""),
            notify
        ]
        
        # Return the first non-empty importer name
        for importer in importer_candidates:
            if isinstance(importer, dict):
                importer = importer.get("name", "")
            if importer and str(importer).strip():
                return str(importer).strip()
        
        return None
    
    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process input data to determine TRN information.
        
        Args:
            input_data: Dictionary containing invoice_data, bol_data, fields, existing_fields, and address_data
            
        Returns:
            Dictionary with processing results
        """
        try:
            # Extract BOL and invoice data
            bol_data = input_data.get('bol_data', {})
            invoice_data = input_data.get('invoice_data', {})
            
            # Extract address data from result stages (if available)
            address_data = None
            if 'result' in input_data and 'stages' in input_data['result']:
                address_data = input_data['result']['stages'].get('secondary_processing', {}).get('addresses')
            
            if not bol_data and not invoice_data:
                return {
                    'success': False,
                    'error': 'No BOL or invoice data found',
                    'trn': None
                }
            
            # Lookup TRN from documents with address data for country checking
            results = self.lookup_trn_from_documents(bol_data, invoice_data, address_data)
            
            # Return the first successful result (exporter or importer)
            for entity_type, result in results.items():
                if result.success:
                    return {
                        'success': True,
                        'trn': result.trn_number,
                        'company_name': result.company_name,
                        'entity_type': entity_type,
                        'match_type': result.match_type,
                        'confidence_score': result.confidence_score
                    }
            
            # If no successful results, return the first error
            for entity_type, result in results.items():
                if not result.success:
                    return {
                        'success': False,
                        'error': result.error_message,
                        'trn': None
                    }
            
            return {
                'success': False,
                'error': 'No TRN lookup results available',
                'trn': None
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'trn': None
            }


def main():
    """Test the TRN lookup processor"""
    
    # Example BOL data for testing
    bol_data = {
        "shipper": "ABC TRADING COMPANY INC",
        "consignee_name": "XYZ IMPORT EXPORT LTD",
        "bill_of_lading": "BL123456",
        "port_of_loading": "SHANGHAI, CHINA",
        "port_of_destination": "KINGSTON, JAMAICA"
    }
    
    invoice_data = {
        "supplier": {"name": "ABC TRADING COMPANY INC"},
        "buyer": {"name": "XYZ IMPORT EXPORT LTD"},
        "currency": "USD",
        "total_amount": 15000.00
    }
    
    # Initialize processor
    processor = TRNLookupProcessor()
    
    # Test TRN lookup
    print("Testing TRN lookup processor...")
    results = processor.lookup_trn_from_documents(bol_data, invoice_data)
    
    print(f"\nTRN Lookup Results:")
    print(f"Exporter: {results['exporter']}")
    print(f"Importer: {results['importer']}")


if __name__ == "__main__":
    main()
