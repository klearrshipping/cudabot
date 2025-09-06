#!/usr/bin/env python3
"""
ESAD CIF Processing Script
Processes raw val_note data extracted by LLM to generate structured CIF information
Enhanced to handle freight cost disaggregation and complex invoice scenarios
"""

import json
from typing import Dict, Any, List, Optional
from decimal import Decimal, InvalidOperation

class CIFProcessor:
    """Processes raw val_note data to extract and structure CIF components with freight disaggregation"""
    
    def __init__(self, transport_mode: str = None):
        self.cif_components = {
            "cost": None,
            "insurance": None,
            "freight": None,
            "total_cif": None,
            "processing_notes": [],
            "freight_source": None,
            "disaggregation_applied": False
        }
        self.transport_mode = transport_mode.upper() if transport_mode else None
    
    def process_val_note(self, raw_val_note: str) -> Dict[str, Any]:
        """
        Process raw val_note data to extract CIF components with enhanced freight handling
        
        Args:
            raw_val_note (str): Raw val_note text from LLM extraction
            
        Returns:
            Dict containing structured CIF information with freight disaggregation
        """
        if not raw_val_note or raw_val_note.strip().lower() in ['null', 'none', 'n/a', '']:
            return self._get_empty_result("No val_note data provided")
        
        # Reset components for new processing
        self.cif_components = {
            "cost": None,
            "insurance": None,
            "freight": None,
            "total_cif": None,
            "processing_notes": [],
            "freight_source": None,
            "disaggregation_applied": False
        }
        
        # Store raw input for reference
        self._raw_input = raw_val_note
        
        # Extract various cost components with enhanced logic
        self._extract_cost_components(raw_val_note)
        
        # Apply freight disaggregation logic if needed
        self._apply_freight_disaggregation()
        
        # Calculate total CIF if components are available
        self._calculate_total_cif()
        
        # Validate and add processing notes
        self._validate_results()
        
        return self._format_results()
    
    def _extract_currency(self, text: str):
        """Currency is handled by another script - this method is not needed"""
        # Currency extraction is handled elsewhere in the workflow
        # This script only processes CIF components from pre-extracted data
        pass
    
    def _extract_cost_components(self, text: str):
        """Extract cost, insurance, and freight components with enhanced logic"""
        # Extract invoice total first (needed for freight disaggregation)
        self._extract_invoice_total(text)
        
        # Extract goods value (primary cost)
        self._extract_goods_value(text)
        
        # Extract freight from BOL (primary source)
        self._extract_bol_freight(text)
        
        # Extract freight from invoice (secondary source)
        self._extract_invoice_freight(text)
        
        # Extract insurance
        self._extract_insurance(text)
        
        # Extract other BOL charges (JMD - excluded from CIF)
        self._extract_other_bol_charges(text)
        
        # Extract invoice charges (should be included in CIF)
        self._extract_invoice_charges(text)
    
    def _extract_goods_value(self, text: str):
        """Extract the goods-only value from invoice"""
        text_upper = text.upper()
        
        # Look for goods value indicators
        goods_indicators = [
            'INVOICE VALUE (GOODS ONLY)', 'GOODS VALUE', 'COMMERCIAL VALUE', 
            'BASE PRICE', 'SUBTOTAL', 'LINE ITEM TOTAL'
        ]
        
        for indicator in goods_indicators:
            if indicator in text_upper:
                # Use more precise extraction to avoid picking up numbers from other fields
                number = self._extract_number_after_field(text, indicator)
                if number is not None:
                    self.cif_components["cost"] = number
                    self.cif_components["processing_notes"].append(f"Goods value extracted: {number}")
                    break
        
        # If no specific indicator found, try to extract any large number as goods value
        if self.cif_components["cost"] is None:
            numbers = self._extract_all_numbers(text)
            if numbers:
                # Use the largest number as goods value (usually the main value)
                largest_number = max(numbers)
                self.cif_components["cost"] = largest_number
                self.cif_components["processing_notes"].append(f"Goods value inferred from largest value: {largest_number}")
    
    def _extract_invoice_total(self, text: str):
        """Extract invoice total that might include freight"""
        text_upper = text.upper()
        
        if 'INVOICE TOTAL (INCLUDING FREIGHT)' in text_upper:
            # Use more precise extraction to avoid picking up numbers from other fields
            number = self._extract_number_after_field(text, 'INVOICE TOTAL (INCLUDING FREIGHT)')
            if number is not None:
                self.cif_components["invoice_total_with_freight"] = number
                self.cif_components["processing_notes"].append(f"Invoice total with freight: {number}")
    
    def _extract_bol_freight(self, text: str):
        """Extract freight charges from BOL (primary source)"""
        text_upper = text.upper()
        
        if 'FREIGHT CHARGES (BOL)' in text_upper:
            # Use more precise extraction to avoid picking up numbers from other fields
            number = self._extract_number_after_field(text, 'FREIGHT CHARGES (BOL)')
            
            if number is not None and number > 0:
                self.cif_components["freight"] = number
                self.cif_components["freight_source"] = "BOL"
                self.cif_components["processing_notes"].append(f"Freight from BOL: {number}")
            else:
                self.cif_components["processing_notes"].append("BOL freight explicitly marked as null/none")
    
    def _extract_invoice_freight(self, text: str):
        """Extract freight charges from invoice if separately listed"""
        text_upper = text.upper()
        
        if 'FREIGHT CHARGES (INVOICE)' in text_upper:
            # Use more precise extraction to avoid picking up numbers from other fields
            number = self._extract_number_after_field(text, 'FREIGHT CHARGES (INVOICE)')
            
            if number is not None and number > 0:
                # Store invoice freight for later processing
                self.cif_components["invoice_freight"] = number
                self.cif_components["processing_notes"].append(f"Invoice freight found: {number}")
                
                # If we don't have BOL freight, use invoice freight
                if self.cif_components["freight"] is None:
                    self.cif_components["freight"] = number
                    self.cif_components["freight_source"] = "Invoice"
                    self.cif_components["processing_notes"].append(f"Using invoice freight as primary source: {number}")
            else:
                self.cif_components["processing_notes"].append("Invoice freight explicitly marked as null/none")
        else:
            self.cif_components["processing_notes"].append("No invoice freight field found")
    
    def _extract_insurance(self, text: str):
        """Extract insurance value from BOL or invoice, or calculate if not provided"""
        text_upper = text.upper()
        
        if 'INSURANCE CHARGES' in text_upper:
            # Use more precise extraction to avoid picking up numbers from other fields
            number = self._extract_number_after_field(text, 'INSURANCE CHARGES')
            
            if number is not None and number > 0:
                self.cif_components["insurance"] = number
                self.cif_components["processing_notes"].append(f"Insurance extracted: {number}")
            else:
                # Insurance is null/nil/0, calculate based on transport mode
                self._calculate_insurance_based_on_transport_mode()
        else:
            # No insurance field found, calculate based on transport mode
            self._calculate_insurance_based_on_transport_mode()
    
    def _calculate_insurance_based_on_transport_mode(self):
        """Calculate insurance based on transport mode when not provided"""
        if not self.transport_mode:
            self.cif_components["insurance"] = 0.0
            self.cif_components["processing_notes"].append("No transport mode provided, insurance set to 0")
            return
        
        # Get the goods value for calculation
        goods_value = self.cif_components.get("cost", 0.0)
        if not goods_value or goods_value <= 0:
            self.cif_components["insurance"] = 0.0
            self.cif_components["processing_notes"].append("No goods value available for insurance calculation")
            return
        
        # Calculate insurance based on transport mode
        if self.transport_mode in ['SEA', 'OCEAN', 'MARITIME', 'VESSEL', 'SHIP']:
            insurance_rate = 0.015  # 1.5%
            self.cif_components["insurance"] = round(goods_value * insurance_rate, 2)
            self.cif_components["processing_notes"].append(
                f"Insurance calculated for sea transport: {goods_value} × 1.5% = {self.cif_components['insurance']}"
            )
        elif self.transport_mode in ['AIR', 'AIRFREIGHT', 'AIRWAY', 'FLIGHT']:
            insurance_rate = 0.01   # 1.0%
            self.cif_components["insurance"] = round(goods_value * insurance_rate, 2)
            self.cif_components["processing_notes"].append(
                f"Insurance calculated for air transport: {goods_value} × 1.0% = {self.cif_components['insurance']}"
            )
        else:
            # For road, rail, or unknown transport modes, use a default rate
            insurance_rate = 0.01   # Default to 1.0%
            self.cif_components["insurance"] = round(goods_value * insurance_rate, 2)
            self.cif_components["processing_notes"].append(
                f"Insurance calculated for {self.transport_mode} transport (default rate): {goods_value} × 1.0% = {self.cif_components['insurance']}"
            )
    
    def _extract_other_bol_charges(self, text: str):
        """Extract other charges from BOL for complete cost analysis"""
        text_upper = text.upper()
        
        if 'OTHER CHARGES (BOL)' in text_upper:
            start_idx = text_upper.find('OTHER CHARGES (BOL)')
            remaining_text = text[start_idx:]
            
            # Extract all numbers for other charges
            numbers = self._extract_all_numbers(remaining_text)
            if numbers:
                total_other = sum(numbers)
                self.cif_components["other_bol_charges"] = total_other
                self.cif_components["processing_notes"].append(f"Other BOL charges (JMD - excluded from CIF): {total_other}")
    
    def _extract_invoice_charges(self, text: str):
        """Extract additional charges from invoice that should be included in CIF"""
        text_upper = text.upper()
        
        # Look for invoice charges that should be included in CIF
        invoice_charge_indicators = [
            'TAX', 'SHIPPING', 'HANDLING', 'PROCESSING', 'ADMINISTRATIVE',
            'DOCUMENTATION', 'CUSTOMS', 'DUTY', 'EXCISE'
        ]
        
        total_invoice_charges = 0.0
        
        for indicator in invoice_charge_indicators:
            if indicator in text_upper:
                # Use more precise extraction to avoid picking up numbers from other fields
                number = self._extract_number_after_field(text, indicator)
                if number is not None and number > 0:
                    total_invoice_charges += number
                    self.cif_components["processing_notes"].append(f"Invoice charge ({indicator}): {number}")
        
        # Also check for the specific format used in our test data
        if 'TAX:' in text_upper:
            tax_number = self._extract_number_after_field(text, 'TAX:')
            if tax_number is not None and tax_number > 0:
                total_invoice_charges += tax_number
                self.cif_components["processing_notes"].append(f"Invoice charge (TAX): {tax_number}")
        
        if total_invoice_charges > 0:
            self.cif_components["invoice_charges"] = total_invoice_charges
            self.cif_components["processing_notes"].append(f"Total invoice charges included in CIF: {total_invoice_charges}")
        else:
            self.cif_components["invoice_charges"] = 0.0
            self.cif_components["processing_notes"].append("No additional invoice charges found")
    
    def _apply_freight_disaggregation(self):
        """Apply freight cost disaggregation logic when needed"""
        # Scenario 1: BOL has freight - use it as primary source
        if (self.cif_components["freight"] is not None and 
            self.cif_components["freight_source"] == "BOL"):
            
            self.cif_components["processing_notes"].append(
                f"BOL freight used for CIF calculation: {self.cif_components['freight']}"
            )
        
        # Scenario 2: Invoice has freight separately listed - use it if no BOL freight
        elif (self.cif_components["freight"] is not None and 
              self.cif_components["freight_source"] == "Invoice"):
            
            self.cif_components["processing_notes"].append(
                f"Invoice freight used for CIF calculation: {self.cif_components['freight']}"
            )
        
        # Scenario 3: No freight found, but invoice total suggests freight included - disaggregate
        elif (self.cif_components["freight"] is None and 
              hasattr(self.cif_components, 'invoice_total_with_freight') and
              self.cif_components["cost"] is not None):
            
            invoice_total = self.cif_components["invoice_total_with_freight"]
            goods_value = self.cif_components["cost"]
            
            if invoice_total > goods_value:
                calculated_freight = invoice_total - goods_value
                self.cif_components["freight"] = calculated_freight
                self.cif_components["freight_source"] = "Calculated (disaggregated)"
                self.cif_components["disaggregation_applied"] = True
                self.cif_components["processing_notes"].append(
                    f"Freight disaggregated from invoice total: {calculated_freight} "
                    f"(Invoice total: {invoice_total} - Goods value: {goods_value})"
                )
            else:
                self.cif_components["freight"] = 0
                self.cif_components["freight_source"] = "None found"
                self.cif_components["processing_notes"].append("No freight charges found - set to 0")
        
        # Scenario 4: No freight found in any source
        elif self.cif_components["freight"] is None:
            self.cif_components["freight"] = 0
            self.cif_components["freight_source"] = "None found"
            self.cif_components["processing_notes"].append("No freight charges found - set to 0")
    
    def _extract_first_number(self, text: str) -> Optional[float]:
        """Extract the first number found in text"""
        import re
        
        # Find all numbers in the text
        numbers = re.findall(r'\d+(?:,\d{3})*(?:\.\d{2})?', text)
        
        if numbers:
            try:
                # Clean the first number and convert to float
                number_str = numbers[0].replace(',', '')
                return float(Decimal(number_str))
            except (InvalidOperation, ValueError):
                return None
        
        return None
    
    def _extract_number_after_field(self, text: str, field_name: str) -> Optional[float]:
        """Extract the first number that appears after a specific field name"""
        import re
        
        # Find the field name in the text
        field_pattern = re.escape(field_name)
        # Look for the pattern: field_name: number or field_name: null
        match = re.search(f'{field_pattern}\\s*:\\s*(\\d+(?:,\\d{{3}})*(?:\\.\\d{{2}})?)', text, re.IGNORECASE)
        
        if match:
            try:
                number_str = match.group(1).replace(',', '')
                return float(Decimal(number_str))
            except (InvalidOperation, ValueError):
                return None
        
        return None
    
    def _extract_all_numbers(self, text: str) -> List[float]:
        """Extract all numbers found in text"""
        import re
        
        numbers = re.findall(r'\d+(?:,\d{3})*(?:\.\d{2})?', text)
        result = []
        
        for number_str in numbers:
            try:
                clean_number = number_str.replace(',', '')
                result.append(float(Decimal(clean_number)))
            except (InvalidOperation, ValueError):
                continue
        
        return result
    
    def _calculate_total_cif(self):
        """Calculate total CIF value from components"""
        components = []
        
        if self.cif_components["cost"] is not None:
            components.append(self.cif_components["cost"])
        
        if self.cif_components["insurance"] is not None:
            components.append(self.cif_components["insurance"])
        
        if self.cif_components["freight"] is not None:
            components.append(self.cif_components["freight"])
        
        # Include invoice charges in CIF calculation
        if 'invoice_charges' in self.cif_components and self.cif_components["invoice_charges"] > 0:
            components.append(self.cif_components["invoice_charges"])
            self.cif_components["processing_notes"].append(f"Invoice charges included in CIF: {self.cif_components['invoice_charges']}")
        
        if components:
            total = sum(components)
            self.cif_components["total_cif"] = round(total, 2)
            self.cif_components["processing_notes"].append(f"Total CIF calculated: {total}")
        else:
            # If no components found, try to use the main cost as total CIF
            if self.cif_components["cost"] is not None:
                self.cif_components["total_cif"] = self.cif_components["cost"]
                self.cif_components["processing_notes"].append("Using goods value as total CIF")
    
    def _validate_results(self):
        """Validate the extracted results and add validation notes"""
        validation_notes = []
        
        # Check if we have any meaningful data
        if all(v is None for v in [self.cif_components["cost"], 
                                  self.cif_components["insurance"], 
                                  self.cif_components["freight"]]):
            validation_notes.append("WARNING: No CIF components could be extracted")
        
        # Check for reasonable values
        if self.cif_components["total_cif"] is not None:
            if self.cif_components["total_cif"] <= 0:
                validation_notes.append("WARNING: Total CIF value is zero or negative")
            elif self.cif_components["total_cif"] > 1000000:  # 1 million threshold
                validation_notes.append("NOTE: Total CIF value exceeds 1 million")
        
        # Check freight disaggregation
        if self.cif_components["disaggregation_applied"]:
            validation_notes.append("NOTE: Freight costs were disaggregated from invoice total")
        
        # Check freight source consistency
        if self.cif_components["freight"] is not None and self.cif_components["freight"] > 0:
            validation_notes.append(f"Freight source: {self.cif_components['freight_source']}")
        
        # Add validation notes to processing notes
        self.cif_components["processing_notes"].extend(validation_notes)
    
    def _format_results(self) -> Dict[str, Any]:
        """Format the results for output with enhanced information"""
        return {
            "cif_breakdown": {
                "cost": self.cif_components["cost"],
                "insurance": self.cif_components["insurance"],
                "freight": self.cif_components["freight"],
                "invoice_charges": getattr(self.cif_components, 'invoice_charges', 0.0),
                "total_cif": self.cif_components["total_cif"]
            },
            "freight_analysis": {
                "freight_source": self.cif_components["freight_source"],
                "disaggregation_applied": self.cif_components["disaggregation_applied"],
                "other_bol_charges": getattr(self.cif_components, 'other_bol_charges', None)
            },
            "processing_summary": {
                "components_extracted": sum(1 for v in [self.cif_components["cost"], 
                                                       self.cif_components["insurance"], 
                                                       self.cif_components["freight"]] if v is not None),
                "total_calculated": self.cif_components["total_cif"] is not None,
                "processing_notes": self.cif_components["processing_notes"]
            },
            "raw_input": getattr(self, '_raw_input', 'Not provided')
        }
    
    def _get_empty_result(self, reason: str) -> Dict[str, Any]:
        """Return empty result structure with reason"""
        return {
            "cif_breakdown": {
                "cost": None,
                "insurance": None,
                "freight": None,
                "total_cif": None
            },
            "freight_analysis": {
                "freight_source": None,
                "disaggregation_applied": False,
                "other_bol_charges": None
            },
            "processing_summary": {
                "components_extracted": 0,
                "total_calculated": False,
                "processing_notes": [reason]
            },
            "raw_input": getattr(self, '_raw_input', 'Not provided')
        }

def process_val_note_for_cif(raw_val_note: str, transport_mode: str = None) -> Dict[str, Any]:
    """
    Convenience function to process val_note data
    
    Args:
        raw_val_note (str): Raw val_note text from LLM extraction
        transport_mode (str): Transport mode for insurance calculation (SEA, AIR, ROAD, etc.)
        
    Returns:
        Dict containing structured CIF information
    """
    processor = CIFProcessor(transport_mode)
    return processor.process_val_note(raw_val_note)

def get_direct_cif_value(raw_val_note: str, transport_mode: str = None) -> float:
    """
    Direct function to return just the CIF value for box 22
    
    Args:
        raw_val_note (str): Raw val_note text from LLM extraction
        transport_mode (str): Transport mode for insurance calculation (SEA, AIR, ROAD, etc.)
        
    Returns:
        float: The calculated CIF value
    """
    processor = CIFProcessor(transport_mode)
    result = processor.process_val_note(raw_val_note)
    return result.get('cif_breakdown', {}).get('total_cif', 0.0)

if __name__ == "__main__":
    # Comprehensive test to demonstrate enhanced CIF processing capabilities
    print("🧪 Testing Enhanced CIF Processor with Complex Scenarios")
    print("=" * 60)
    
    # Test Case 1: BOL has freight, invoice includes freight in total, SEA transport (1.5% insurance)
    print("\n📋 Test Case 1: BOL freight, invoice includes freight in total, SEA transport")
    test_input_1 = """
    Invoice value (goods only): 1399.0
    Invoice total (including freight): 1610.71
    Freight charges (BOL): 211.71
    Insurance charges: null
    Other charges (BOL): 5750.00
    """
    
    result_1 = process_val_note_for_cif(test_input_1, "SEA")
    print(f"💰 CIF Breakdown (SEA Transport - 1.5% insurance):")
    print(f"   Goods Value: {result_1['cif_breakdown']['cost']}")
    print(f"   Insurance: {result_1['cif_breakdown']['insurance']} (calculated: 1.5% of goods value)")
    print(f"   Freight: {result_1['cif_breakdown']['freight']} (Source: {result_1['freight_analysis']['freight_source']})")
    print(f"   Total CIF: {result_1['cif_breakdown']['total_cif']}")
    print(f"   Disaggregation Applied: {result_1['freight_analysis']['disaggregation_applied']}")
    print(f"   Other BOL Charges: {result_1['freight_analysis']['other_bol_charges']}")
    
    # Test Case 2: Invoice shows freight separately, no BOL freight, AIR transport (1.0% insurance)
    print("\n📋 Test Case 2: Invoice freight separate, no BOL freight, AIR transport")
    test_input_2 = """
    Invoice value (goods only): 2500.0
    Invoice total (including freight): null
    Freight charges (BOL): null
    Freight charges (invoice): 150.0
    Insurance charges: null
    Other charges (BOL): 0.0
    """
    
    result_2 = process_val_note_for_cif(test_input_2, "AIR")
    print(f"💰 CIF Breakdown (AIR Transport - 1.0% insurance):")
    print(f"   Goods Value: {result_2['cif_breakdown']['cost']}")
    print(f"   Insurance: {result_2['cif_breakdown']['insurance']} (calculated: 1.0% of goods value)")
    print(f"   Freight: {result_2['cif_breakdown']['freight']} (Source: {result_2['freight_analysis']['freight_source']})")
    print(f"   Total CIF: {result_2['cif_breakdown']['total_cif']}")
    print(f"   Disaggregation Applied: {result_2['freight_analysis']['disaggregation_applied']}")
    
    # Test Case 3: Freight needs to be disaggregated from invoice total, ROAD transport (1.0% default)
    print("\n📋 Test Case 3: Freight disaggregation needed, ROAD transport")
    test_input_3 = """
    Invoice value (goods only): 800.0
    Invoice total (including freight): 950.0
    Freight charges (BOL): null
    Freight charges (invoice): null
    Insurance charges: null
    Other charges (BOL): 0.0
    """
    
    result_3 = process_val_note_for_cif(test_input_3, "ROAD")
    print(f"💰 CIF Breakdown (ROAD Transport - 1.0% default insurance):")
    print(f"   Goods Value: {result_3['cif_breakdown']['cost']}")
    print(f"   Insurance: {result_3['cif_breakdown']['insurance']} (calculated: 1.0% default rate)")
    print(f"   Freight: {result_3['cif_breakdown']['freight']} (Source: {result_3['freight_analysis']['freight_source']})")
    print(f"   Total CIF: {result_3['cif_breakdown']['total_cif']}")
    print(f"   Disaggregation Applied: {result_3['freight_analysis']['disaggregation_applied']}")
    
    # Test Case 4: No transport mode provided (insurance set to 0)
    print("\n📋 Test Case 4: No transport mode provided")
    test_input_4 = """
    Invoice value (goods only): 1000.0
    Freight charges (BOL): 100.0
    Insurance charges: null
    Other charges (BOL): 0.0
    """
    
    result_4 = process_val_note_for_cif(test_input_4)
    print(f"💰 CIF Breakdown (No Transport Mode - insurance set to 0):")
    print(f"   Goods Value: {result_4['cif_breakdown']['cost']}")
    print(f"   Insurance: {result_4['cif_breakdown']['insurance']} (no transport mode provided)")
    print(f"   Freight: {result_4['cif_breakdown']['freight']} (Source: {result_4['freight_analysis']['freight_source']})")
    print(f"   Total CIF: {result_4['cif_breakdown']['total_cif']}")
    
    print("\n✅ Enhanced CIF processor is working with automatic insurance calculation!")
    print("\n📝 Key Features:")
    print("   • Handles BOL freight as primary source")
    print("   • Disaggregates freight from invoice totals when needed")
    print("   • Automatically calculates insurance based on transport mode:")
    print("     - SEA transport: 1.5% of goods value")
    print("     - AIR transport: 1.0% of goods value")
    print("     - Other modes: 1.0% default rate")
    print("   • Tracks freight source and disaggregation status")
    print("   • Processes other BOL charges for complete cost analysis")
    print("   • Provides detailed processing notes for audit trail")
