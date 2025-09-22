#!/usr/bin/env python3
"""
ESAD Transport Mode Processing Script
Processes transport mode information from box field 25 and matches with transport_mode.csv
"""

import csv
import os
import re
from typing import Dict, Any, List, Optional

class TransportModeProcessor:
    """Processes transport mode data and matches with official codes"""
    
    def __init__(self):
        self.transport_codes = self._load_transport_codes()
        self.transport_indicators = {
            'sea': ['vessel', 'ship', 'boat', 'ocean', 'maritime', 'sea', 'port', 'harbor', 'dock', 'berth', 'voyage'],
            'air': ['air', 'flight', 'airplane', 'aircraft', 'airway', 'airfreight', 'cargo', 'terminal', 'runway'],
            'road': ['truck', 'vehicle', 'road', 'highway', 'motor', 'car', 'van', 'bus', 'trailer'],
            'rail': ['train', 'rail', 'railway', 'locomotive', 'freight', 'cargo'],
            'postal': ['post', 'mail', 'courier', 'express', 'delivery', 'parcel'],
            'fixed': ['pipeline', 'conveyor', 'cable', 'wire', 'transmission', 'fixed']
        }
    
    def _load_transport_codes(self) -> List[Dict[str, str]]:
        """Load transport mode codes from CSV file"""
        try:
            codes_path = "../../data/transport_mode.csv"
            if not os.path.exists(codes_path):
                print(f"⚠️ Transport mode CSV not found: {codes_path}")
                return []
            
            codes = []
            with open(codes_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('code') and row.get('description'):
                        codes.append({
                            'code': row['code'].strip(),
                            'description': row['description'].strip()
                        })
            
            print(f"✅ Loaded {len(codes)} transport mode codes")
            return codes
            
        except Exception as e:
            print(f"❌ Error loading transport mode codes: {e}")
            return []
    
    def _extract_transport_indicators(self, text: str) -> Dict[str, float]:
        """Extract transport mode indicators from text and calculate confidence scores"""
        text_lower = text.lower()
        scores = {}
        
        for mode, indicators in self.transport_indicators.items():
            score = 0.0
            for indicator in indicators:
                if indicator in text_lower:
                    score += 1.0
                    # Bonus for exact matches
                    if re.search(r'\b' + re.escape(indicator) + r'\b', text_lower):
                        score += 0.5
            
            if score > 0:
                scores[mode] = score
        
        return scores
    
    def _map_mode_to_code(self, mode: str) -> Optional[str]:
        """Map transport mode to official code"""
        mode_mapping = {
            'sea': '1',      # Ocean Transport
            'ocean': '1',    # Ocean Transport
            'maritime': '1', # Ocean Transport
            'air': '4',      # Air Transport
            'road': '3',     # Road Transport
            'rail': '3',     # Road Transport (closest match)
            'postal': '5',   # Postal Transport
            'post': '5',     # Postal Transport
            'mail': '5',     # Postal Transport
            'fixed': '7'     # Fixed Transport Installation
        }
        
        return mode_mapping.get(mode)
    
    def process_transport_mode(self, raw_transport_data: str) -> Dict[str, Any]:
        """
        Process raw transport mode data and return matched transport information
        
        Args:
            raw_transport_data (str): Raw transport mode data extracted from box field 25
            
        Returns:
            Dict containing processed transport mode information with code as primary value
        """
        try:
            if not raw_transport_data or not raw_transport_data.strip():
                return {
                    "success": False,
                    "error": "No transport mode data provided",
                    "raw_input": raw_transport_data,
                    "processed_result": None,
                    "processing_notes": ["Empty transport mode data"]
                }
            
            # Extract transport indicators
            indicators = self._extract_transport_indicators(raw_transport_data)
            
            if not indicators:
                return {
                    "success": False,
                    "error": "No transport mode indicators found",
                    "raw_input": raw_transport_data,
                    "processed_result": None,
                    "processing_notes": ["Could not identify transport mode from data"]
                }
            
            # Find the mode with highest confidence
            best_mode = max(indicators.items(), key=lambda x: x[1])
            mode_name, confidence = best_mode
            
            # Map to official code
            official_code = self._map_mode_to_code(mode_name)
            
            if not official_code:
                return {
                    "success": False,
                    "error": f"Could not map transport mode '{mode_name}' to official code",
                    "raw_input": raw_transport_data,
                    "processed_result": None,
                    "processing_notes": [f"Unrecognized transport mode: {mode_name}"]
                }
            
            # Find the official description
            official_description = None
            for code_info in self.transport_codes:
                if code_info['code'] == official_code:
                    official_description = code_info['description']
                    break
            
            # Build processing notes
            processing_notes = [
                f"Transport mode identified: {mode_name} (confidence: {confidence})",
                f"Mapped to official code: {official_code}",
                f"Official description: {official_description}"
            ]
            
            # Add alternative modes if confidence is close
            sorted_modes = sorted(indicators.items(), key=lambda x: x[1], reverse=True)
            if len(sorted_modes) > 1 and sorted_modes[1][1] >= confidence * 0.8:
                processing_notes.append(f"Alternative mode considered: {sorted_modes[1][0]} (confidence: {sorted_modes[1][1]})")
            
            return {
                "success": True,
                "raw_input": raw_transport_data,
                "processed_result": {
                    "transport_mode": mode_name,
                    "official_code": official_code,
                    "official_description": official_description,
                    "confidence_score": confidence,
                    "all_indicators": indicators
                },
                "processing_notes": processing_notes
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "raw_input": raw_transport_data,
                "processed_result": None,
                "processing_notes": [f"Exception during processing: {str(e)}"]
            }
    
    def get_transport_mode_code(self, raw_transport_data: str) -> Optional[str]:
        """
        Get just the transport mode code for the given data
        
        Args:
            raw_transport_data (str): Raw transport mode data
            
        Returns:
            Transport mode code or None if processing fails
        """
        result = self.process_transport_mode(raw_transport_data)
        if result["success"]:
            return result["processed_result"]["official_code"]
        return None

    def get_box_25_value(self, raw_transport_data: str) -> str:
        """
        Get the value to be displayed in box field 25 (Mode of transport at the border)
        
        Args:
            raw_transport_data (str): Raw transport mode data from documents
            
        Returns:
            str: Transport mode code (e.g., "1", "3", "4", "5", "7") for box field 25
        """
        result = self.process_transport_mode(raw_transport_data)
        if result["success"]:
            return result["processed_result"]["official_code"]
        else:
            # Return default value if processing fails
            return "1"  # Default to Ocean Transport if unable to determine

def process_transport_mode(raw_transport_data: str) -> Dict[str, Any]:
    """
    Convenience function to process transport mode data
    
    Args:
        raw_transport_data (str): Raw transport mode data from box field 25
        
    Returns:
        Dict containing processed transport mode information
    """
    processor = TransportModeProcessor()
    return processor.process_transport_mode(raw_transport_data)

def get_transport_mode_code(raw_transport_data: str) -> Optional[str]:
    """
    Convenience function to get just the transport mode code
    
    Args:
        raw_transport_data (str): Raw transport mode data from box field 25
        
    Returns:
        Transport mode code or None if processing fails
    """
    processor = TransportModeProcessor()
    return processor.get_transport_mode_code(raw_transport_data)

def get_box_25_value(raw_transport_data: str) -> str:
    """
    Convenience function to get the value for box field 25
    
    Args:
        raw_transport_data (str): Raw transport mode data from box field 25
        
    Returns:
        str: Transport mode code for box field 25 (never returns None)
    """
    processor = TransportModeProcessor()
    return processor.get_box_25_value(raw_transport_data)

# Test cases when run directly
if __name__ == "__main__":
    print("🧪 Testing ESAD Transport Mode Processing")
    print("=" * 50)
    
    processor = TransportModeProcessor()
    
    # Test case 1: Sea transport
    print("\n📋 Test Case 1: Sea Transport")
    sea_data = "Vessel SEABOARD GEMINI, Voyage SGM19, Port of Miami"
    result1 = processor.process_transport_mode(sea_data)
    print(f"Input: {sea_data}")
    print(f"Success: {result1['success']}")
    if result1['success']:
        print(f"Mode: {result1['processed_result']['transport_mode']}")
        print(f"Code: {result1['processed_result']['official_code']}")
        print(f"Description: {result1['processed_result']['official_description']}")
    
    # Test case 2: Air transport
    print("\n📋 Test Case 2: Air Transport")
    air_data = "Flight AA123, Airway Bill AWB456, Cargo Terminal"
    result2 = processor.process_transport_mode(air_data)
    print(f"Input: {air_data}")
    print(f"Success: {result2['success']}")
    if result2['success']:
        print(f"Mode: {result2['processed_result']['transport_mode']}")
        print(f"Code: {result2['processed_result']['official_code']}")
        print(f"Description: {result2['processed_result']['official_description']}")
    
    # Test case 3: Road transport
    print("\n📋 Test Case 3: Road Transport")
    road_data = "Truck delivery, Highway transport, Vehicle registration"
    result3 = processor.process_transport_mode(road_data)
    print(f"Input: {road_data}")
    print(f"Success: {result3['success']}")
    if result3['success']:
        print(f"Mode: {result3['processed_result']['transport_mode']}")
        print(f"Code: {result3['processed_result']['official_code']}")
        print(f"Description: {result3['processed_result']['official_description']}")
    
    # Test case 4: Box 25 value (what gets displayed in the field)
    print("\n📋 Test Case 4: Box 25 Value")
    print("=" * 35)
    
    # Test with real vessel data
    real_vessel_data = "Vessel SEABOARD GEMINI, Voyage SGM19, Port of Miami to Kingston"
    box_25_value = processor.get_box_25_value(real_vessel_data)
    print(f"Input: {real_vessel_data}")
    print(f"Box 25 Value: {box_25_value}")
    print(f"Box 25 Meaning: {box_25_value} = Ocean Transport")
    
    print("\n✅ Transport mode processing test completed!")
    print("\n📝 Key Point:")
    print("   • Box 25 'Mode of transport at the border' returns the CODE (e.g., '1')")
    print("   • NOT the description or other details")
    print("   • This code is what gets displayed in the ESAD form")
