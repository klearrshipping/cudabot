#!/usr/bin/env python3
"""
Example: Using CIF Processor with Transport Mode for Automatic Insurance Calculation
This script demonstrates how to integrate transport mode information with CIF processing
"""

from esad_cif import get_direct_cif_value, process_val_note_for_cif

def example_cif_calculation_with_transport():
    """Example showing how transport mode affects CIF calculation"""
    
    # Sample val_note data (goods value + freight + tax)
    val_note_data = """
    Invoice value (goods only): 1399.0
    Tax: 97.93
    Freight charges (BOL): 211.71
    Insurance charges: null
    """
    
    print("🚢 Example: CIF Calculation with Different Transport Modes")
    print("=" * 60)
    print(f"📋 Val_Note Data:")
    print(val_note_data.strip())
    print()
    
    # Calculate CIF for SEA transport (1.5% insurance)
    cif_sea = get_direct_cif_value(val_note_data, "SEA")
    print(f"💰 CIF Value (SEA Transport - 1.5% insurance): ${cif_sea:.2f}")
    
    # Calculate CIF for AIR transport (1.0% insurance)
    cif_air = get_direct_cif_value(val_note_data, "AIR")
    print(f"💰 CIF Value (AIR Transport - 1.0% insurance): ${cif_air:.2f}")
    
    # Calculate CIF for ROAD transport (1.0% default)
    cif_road = get_direct_cif_value(val_note_data, "ROAD")
    print(f"💰 CIF Value (ROAD Transport - 1.0% default): ${cif_road:.2f}")
    
    # Calculate CIF without transport mode (insurance = 0)
    cif_none = get_direct_cif_value(val_note_data)
    print(f"💰 CIF Value (No Transport Mode): ${cif_none:.2f}")
    
    print()
    print("📊 Insurance Calculation Breakdown:")
    print(f"   Goods Value: $1,399.00")
    print(f"   Tax: $97.93")
    print(f"   Freight: $211.71")
    print(f"   Insurance (SEA): $20.98 (1.5% of $1,399.00)")
    print(f"   Insurance (AIR): $13.99 (1.0% of $1,399.00)")
    print(f"   Insurance (ROAD): $13.99 (1.0% default)")
    print(f"   Insurance (None): $0.00")
    
    print()
    print("🔍 Key Points:")
    print("   • When insurance charges are null/nil/0, the system automatically calculates them")
    print("   • SEA transport uses 1.5% of goods value")
    print("   • AIR transport uses 1.0% of goods value")
    print("   • Other modes use 1.0% default rate")
    print("   • Transport mode comes from box 25 (Mode of transport at the border)")
    print("   • This ensures accurate CIF calculations for customs declarations")

if __name__ == "__main__":
    example_cif_calculation_with_transport()
