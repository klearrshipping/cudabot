#!/usr/bin/env python3
"""
Batch extract HS Codes from all PDFs in folder → Single CSV output
Skips PDFs that don't contain HS Code data
Preserves leading zeros in Heading and HS Code
"""

import pdfplumber
import pandas as pd
import re
import os

# 📍 Folder path where your PDFs are stored
pdf_folder = r"C:\Users\rafer\OneDrive\Desktop\projects\exim\pdfs"

# 📍 Output CSV file (single combined file)
output_csv = os.path.join(pdf_folder, "all_hs_codes.csv")

# Get list of PDF files
pdf_files = [f for f in os.listdir(pdf_folder) if f.lower().endswith(".pdf")]

if not pdf_files:
    print("⚠️ No PDF files found in folder:", pdf_folder)
    exit()

# Global data list
global_data = []

# Process each PDF file
for pdf_filename in pdf_files:
    pdf_path = os.path.join(pdf_folder, pdf_filename)
    print(f"\n📄 Processing {pdf_filename} ...")

    # Initialize data list for this PDF
    data = []

    # Track current heading & subcategory
    current_heading = ""
    current_heading_desc = ""
    current_subcategory = ""

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            lines = text.split('\n')

            for line in lines:
                line = line.strip()

                # Skip empty lines
                if not line:
                    continue

                # Detect Heading (ex: 01.01 Live horses...)
                match_heading = re.match(r'^(\d{1,2})\.(\d{1,2})\s+(.*)$', line)
                if match_heading:
                    # Force format 2 digits . 2 digits (leading 0s)
                    current_heading = "{:0>2}.{:0>2}".format(
                        int(match_heading.group(1)),
                        int(match_heading.group(2))
                    )
                    current_heading_desc = match_heading.group(3)
                    current_subcategory = ""  # Reset subcategory
                    continue

                # Detect Subcategory (ex: - Mammals :)
                match_subcat = re.match(r'^\s*-\s+(.*)\s+:$', line)
                if match_subcat:
                    current_subcategory = match_subcat.group(1)
                    continue

                # Detect HS Code line (ex: 0101.21 -- Pure-bred breeding animals)
                match_code = re.match(r'^(\d{1,4})\.(\d{1,2})\s+[-–]{1,2}\s+(.*)$', line)
                if match_code:
                    # Force format 4 digits . 2 digits (leading 0s)
                    hs_code = "{:0>4}.{:0>2}".format(
                        int(match_code.group(1)),
                        int(match_code.group(2))
                    )
                    hs_desc = match_code.group(3)

                    # Add row to data
                    data.append({
                        "Source File": pdf_filename,
                        "Heading": current_heading,
                        "Heading Description": current_heading_desc,
                        "Subcategory": current_subcategory,
                        "HS Code": hs_code,
                        "HS Description": hs_desc
                    })

    # If we found data in this PDF, append to global list
    if data:
        global_data.extend(data)
        print(f"✅ Extracted {len(data)} rows.")
    else:
        print("⏭️ Skipped (no HS code data found).")

# After all PDFs processed → save single CSV
if global_data:
    df = pd.DataFrame(global_data)
    df.to_csv(output_csv, index=False, encoding="utf-8-sig")
    print(f"\n🎉 All done! Saved combined CSV: {output_csv}")
    print(f"✅ Total rows extracted: {len(global_data)}")
else:
    print("\n⚠️ No HS code data found in any PDF.")
