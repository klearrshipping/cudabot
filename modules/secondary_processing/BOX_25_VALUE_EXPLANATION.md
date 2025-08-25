# Box Field 25: Mode of Transport at the Border

## 🎯 **What Value is Returned**

**Box Field 25 returns the TRANSPORT MODE CODE, not the description or other details.**

## 📊 **Transport Mode Codes**

| Code | Transport Mode | Description |
|------|----------------|-------------|
| **1** | **Ocean Transport** | Sea, maritime, vessel transport |
| **3** | **Road Transport** | Truck, vehicle, highway transport |
| **4** | **Air Transport** | Flight, airway, cargo transport |
| **5** | **Postal Transport** | Mail, courier, express delivery |
| **7** | **Fixed Transport Installation** | Pipeline, conveyor, cable transport |

## 🔍 **Example: Your Amazon Order**

**Input Data:**
```
Vessel SEABOARD GEMINI, Voyage SGM19, Port of Miami to Kingston, Berth B1
```

**Box 25 Value Returned:**
```
1
```

**What This Means:**
- **Box 25 displays:** `1`
- **Code 1 represents:** Ocean Transport
- **This is what appears in your ESAD form**

## ⚡ **Key Functions**

### `get_box_25_value(raw_transport_data)`
- **Returns:** Transport mode code (e.g., "1", "3", "4", "5", "7")
- **Never returns:** None or empty values
- **Default fallback:** "1" (Ocean Transport) if processing fails
- **Purpose:** This is what gets displayed in box field 25

### `process_transport_mode(raw_transport_data)`
- **Returns:** Full processing details including code, description, confidence
- **Use:** For debugging, logging, or when you need full information
- **Not for:** Box field 25 display (use `get_box_25_value` instead)

## 🚀 **Integration with ESAD System**

1. **Box 25** extracts transport mode data from documents
2. **esad_transport_mode.py** processes the data using `transport_mode.csv`
3. **Returns:** Transport mode code (e.g., "1")
4. **Box 25 displays:** The code value
5. **ESAD form shows:** Code 1 = Ocean Transport

## ✅ **Summary**

- **Box Field 25 returns:** Transport mode CODE (e.g., "1")
- **NOT:** Description, confidence scores, or other details
- **For your Amazon order:** Box 25 displays "1" (Ocean Transport)
- **This code:** Gets entered into the ESAD customs declaration form

The system is designed to return the exact value needed for the ESAD form field.
