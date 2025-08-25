#!/usr/bin/env python3
"""
Transaction Types Overview
Shows all available transaction types and when they would be selected
"""

def show_all_transaction_types():
    """Display all available transaction types with examples"""
    
    print("📊 Complete Transaction Types Available for Box 24")
    print("=" * 60)
    
    print("\n🎯 CODE 1: Purchase or Sale")
    print("-" * 30)
    print("   1.1: Outright purchase or sale")
    print("       → Standard commercial transactions (like Amazon order)")
    print("       → Invoice with payment terms, shipping, tax")
    print("       → Different buyer and seller parties")
    
    print("\n   1.2: Sale, after approval or trial")
    print("       → Goods sent for testing/approval first")
    print("       → Sale confirmed after customer approval")
    print("       → Trial period before final purchase")
    
    print("\n   1.3: Barter trade (Compensation in kind)")
    print("       → Goods exchanged for other goods")
    print("       → No monetary payment")
    print("       → Trade agreements between parties")
    
    print("\n   1.4: Financing Lease (Hire-purchase)")
    print("       → Equipment leased with option to buy")
    print("       → Monthly payments over time")
    print("       → Ownership transfers after final payment")
    
    print("\n   1.9: Other")
    print("       → Other purchase/sale arrangements")
    print("       → Special commercial terms")
    
    print("\n🔄 CODE 2: Return of goods free of charge")
    print("-" * 40)
    print("   2.1: Return of Goods")
    print("       → Customer returns defective goods")
    print("       → No charge for return shipping")
    print("       → Warranty or quality issues")
    
    print("\n   2.2: Replacement of returned goods")
    print("       → New goods sent to replace returns")
    print("       → Same or equivalent items")
    print("       → No additional charge")
    
    print("\n   2.3: Replacement for goods not returned")
    print("       → New goods sent without return")
    print("       → Customer keeps original items")
    print("       → Goodwill or service recovery")
    
    print("\n🎁 CODE 3: Transfer of goods - No compensation")
    print("-" * 45)
    print("   3.1: Transfer of goods - Aid program")
    print("       → Humanitarian aid shipments")
    print("       → Government or NGO assistance")
    print("       → Disaster relief or development aid")
    
    print("\n   3.2: Other aid shipments - Public Admin")
    print("       → Government assistance programs")
    print("       → Public sector support")
    print("       → Official aid initiatives")
    
    print("\n   3.3: Other aid shipments - Private Organisations")
    print("       → Charity donations")
    print("       → Non-profit assistance")
    print("       → Private sector aid")
    
    print("\n⚙️ CODE 4: For (Inward) Processing - Contract")
    print("-" * 45)
    print("   4.1: Goods returned to member state")
    print("       → Processing completed abroad")
    print("       → Goods returned after processing")
    print("       → Contract manufacturing")
    
    print("\n   4.2: Goods not returned to member state")
    print("       → Processing completed abroad")
    print("       → Goods remain in processing country")
    print("       → Offshore manufacturing")
    
    print("\n🔧 CODE 5: After (Outward) Processing - Contract")
    print("-" * 45)
    print("   5.1: Goods returned to member state")
    print("       → Processing completed domestically")
    print("       → Goods returned after processing")
    print("       → Domestic contract manufacturing")
    
    print("\n   5.2: Goods not returned to member state")
    print("       → Processing completed domestically")
    print("       → Goods remain in processing country")
    print("       → Export processing")
    
    print("\n🔨 CODE 6: Repairs & Maintenance")
    print("-" * 30)
    print("   6.1: For Repair/Maintenance - With Compensation")
    print("       → Paid repair services")
    print("       → Maintenance contracts")
    print("       → Service fees charged")
    
    print("\n   6.2: After Repair Maintenance - With compensation")
    print("       → Repaired goods returned")
    print("       → Service fees paid")
    print("       → Warranty or paid repairs")
    
    print("\n   6.3: For Repair/Maintenance - No Compensation")
    print("       → Free warranty repairs")
    print("       → No-charge maintenance")
    print("       → Service included in purchase")
    
    print("\n   6.4: After Repair Maintenance - No compensation")
    print("       → Free repairs completed")
    print("       → No-charge service")
    print("       → Warranty service")
    
    print("\n🤝 CODE 7: Joint intergovernment programme")
    print("-" * 40)
    print("   7.0: Joint intergovernmental programme")
    print("       → Government cooperation agreements")
    print("       → International partnerships")
    print("       → Official collaboration programs")
    
    print("\n📋 CODE 8: Contract - No separate invoicing")
    print("-" * 40)
    print("   8.1: Rent, operate lease over 24 months")
    print("       → Long-term equipment rental")
    print("       → Operating lease agreements")
    print("       → No separate invoices per use")
    
    print("\n   8.2: Stock movement - No compensation")
    print("       → Internal stock transfers")
    print("       → Warehouse movements")
    print("       → No commercial transaction")
    
    print("\n❓ CODE 9: Other")
    print("-" * 15)
    print("   9.9: Other")
    print("       → Special arrangements")
    print("       → Unique transaction types")
    print("       → Custom agreements")
    
    print("\n📝 Current Amazon Order Classification:")
    print("-" * 40)
    print("Based on the extracted data:")
    print("   • Supplier: Amazon.com")
    print("   • Buyer: Rafer Johnson")
    print("   • Payment: Mastercard")
    print("   • Shipping: Standard")
    print("   • Invoice: $1,399 + $97.93 tax")
    print("   • Freight: USD 211.71")
    print("\n   🎯 SELECTED: Code 1.1 (Outright purchase or sale)")
    print("   This is the standard commercial transaction type")

if __name__ == "__main__":
    show_all_transaction_types()
