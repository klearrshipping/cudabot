#!/usr/bin/env python3
"""
eSAD Manifest Tracker
Automates BOL tracking on Jamaica Customs website and extracts manifest data
"""

import json
import re
import time
import requests
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Add parent directory to path to import config
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

@dataclass
class ManifestEntry:
    """Single manifest entry from the tracking results"""
    office: str
    reference_id: str
    date: str
    status: str

@dataclass
class ManifestResult:
    """Complete manifest tracking result"""
    bol_number: str
    entries: List[ManifestEntry]
    total_entries: int
    tracking_url: str
    extraction_time: str
    success: bool
    error_message: Optional[str] = None

class ManifestTracker:
    """Automated BOL tracking on Jamaica Customs website"""
    
    def __init__(self):
        """Initialize the manifest tracker"""
        self.base_url = "https://jets.jacustoms.gov.jm/portal/services/docTracking/track.jsf"
        self.driver = None
        self.wait_timeout = 30
        
    def setup_driver(self):
        """Setup Chrome WebDriver with appropriate options"""
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Run in background - ENABLED FOR AUTOMATION
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.implicitly_wait(10)
            print("✅ WebDriver initialized successfully")
            return True
        except Exception as e:
            print(f"❌ Failed to initialize WebDriver: {e}")
            return False
    
    def navigate_to_tracking_page(self) -> bool:
        """Navigate to the BOL tracking page"""
        try:
            print(f"🌐 Navigating to: {self.base_url}")
            self.driver.get(self.base_url)
            
            # Wait for the page to load
            WebDriverWait(self.driver, self.wait_timeout).until(
                EC.presence_of_element_located((By.ID, "bolTracking"))
            )
            
            print("✅ Successfully loaded tracking page")
            return True
            
        except TimeoutException:
            print("❌ Timeout waiting for tracking page to load")
            return False
        except Exception as e:
            print(f"❌ Error navigating to tracking page: {e}")
            return False
    
    def enter_bol_number(self, bol_number: str) -> bool:
        """Enter BOL number into the tracking form"""
        try:
            # Find the BOL input field
            bol_input = self.driver.find_element(By.ID, "bolTracking:par3")
            
            # Clear any existing value and enter the BOL number
            bol_input.clear()
            bol_input.send_keys(bol_number)
            
            print(f"📝 Entered BOL number: {bol_number}")
            return True
            
        except NoSuchElementException:
            print("❌ Could not find BOL input field")
            return False
        except Exception as e:
            print(f"❌ Error entering BOL number: {e}")
            return False
    
    def submit_tracking_form(self) -> bool:
        """Submit the tracking form and wait for BOL results"""
        try:
            # Find and click the submit button
            submit_button = self.driver.find_element(By.ID, "bolTracking:j_idt92")
            submit_button.click()
            
            print("🔄 Submitting BOL tracking form...")
            
            # Wait for the BOL tracking modal to appear and be visible
            WebDriverWait(self.driver, self.wait_timeout).until(
                EC.visibility_of_element_located((By.ID, "bolTracking:j_idt93"))
            )
            
            # Wait for the BOL tracking table to be present
            WebDriverWait(self.driver, self.wait_timeout).until(
                EC.presence_of_element_located((By.ID, "bolTracking:j_idt98"))
            )
            
            # Wait for table data to load (either data rows or empty message)
            WebDriverWait(self.driver, self.wait_timeout).until(
                lambda driver: (
                    driver.find_elements(By.CSS_SELECTOR, "#bolTracking\\:j_idt98 tbody tr[data-ri]") or
                    driver.find_elements(By.CSS_SELECTOR, "#bolTracking\\:j_idt98 tbody .ui-datatable-empty-message")
                )
            )
            
            # Additional wait for JavaScript execution
            time.sleep(3)
            
            print("✅ BOL tracking results loaded")
            return True
            
        except TimeoutException:
            print("❌ Timeout waiting for BOL tracking results")
            return False
        except Exception as e:
            print(f"❌ Error submitting form: {e}")
            return False
    
    def extract_manifest_data(self) -> List[ManifestEntry]:
        """Extract manifest data from the BOL tracking results table"""
        entries = []
        
        try:
            print(f"🔍 Extracting BOL tracking results...")
            
            # Wait for the BOL modal to be visible
            WebDriverWait(self.driver, self.wait_timeout).until(
                EC.visibility_of_element_located((By.ID, "bolTracking:j_idt93"))
            )
            
            # Additional wait for data to load
            time.sleep(2)
            
            # Use JavaScript to extract data from the specific BOL tracking table
            js_script = """
            var entries = [];
            
            // Target the specific BOL tracking table
            var bolTable = document.getElementById('bolTracking:j_idt98');
            if (bolTable) {
                var tbody = bolTable.querySelector('tbody.ui-datatable-data');
                if (tbody) {
                    // Look for data rows (they have data-ri attribute)
                    var rows = tbody.querySelectorAll('tr[data-ri]');
                    
                    for (var i = 0; i < rows.length; i++) {
                        var cells = rows[i].querySelectorAll('td[role="gridcell"]');
                        
                        if (cells.length >= 4) {
                            var entry = {
                                office: cells[0].textContent.trim(),
                                reference_id: cells[1].textContent.trim(),
                                date: cells[2].textContent.trim(),
                                status: cells[3].textContent.trim()
                            };
                            entries.push(entry);
                        }
                    }
                }
            }
            
            return entries;
            """
            
            # Execute JavaScript to extract data
            js_result = self.driver.execute_script(js_script)
            
            # Convert to ManifestEntry objects
            for entry_data in js_result:
                entry = ManifestEntry(
                    office=entry_data['office'],
                    reference_id=entry_data['reference_id'],
                    date=entry_data['date'],
                    status=entry_data['status']
                )
                entries.append(entry)
                print(f"✅ Extracted: {entry.office} - {entry.reference_id} - {entry.date} - {entry.status}")
            
            print(f"📊 Extracted {len(entries)} manifest entries")
            return entries
            
        except Exception as e:
            print(f"❌ Error extracting manifest data: {e}")
            return []
    
    def track_bol(self, bol_number: str) -> ManifestResult:
        """Main method to track a BOL and extract manifest data"""
        
        print(f"🚀 Starting BOL tracking for: {bol_number}")
        
        try:
            # Setup WebDriver
            if not self.setup_driver():
                return ManifestResult(
                    bol_number=bol_number,
                    entries=[],
                    total_entries=0,
                    tracking_url=self.base_url,
                    extraction_time=datetime.now().isoformat(),
                    success=False,
                    error_message="Failed to initialize WebDriver"
                )
            
            # Navigate to tracking page
            if not self.navigate_to_tracking_page():
                return ManifestResult(
                    bol_number=bol_number,
                    entries=[],
                    total_entries=0,
                    tracking_url=self.base_url,
                    extraction_time=datetime.now().isoformat(),
                    success=False,
                    error_message="Failed to navigate to tracking page"
                )
            
            # Enter BOL number
            if not self.enter_bol_number(bol_number):
                return ManifestResult(
                    bol_number=bol_number,
                    entries=[],
                    total_entries=0,
                    tracking_url=self.base_url,
                    extraction_time=datetime.now().isoformat(),
                    success=False,
                    error_message="Failed to enter BOL number"
                )
            
            # Submit form
            if not self.submit_tracking_form():
                return ManifestResult(
                    bol_number=bol_number,
                    entries=[],
                    total_entries=0,
                    tracking_url=self.base_url,
                    extraction_time=datetime.now().isoformat(),
                    success=False,
                    error_message="Failed to submit tracking form"
                )
            
            # Extract manifest data
            entries = self.extract_manifest_data()
            
            # Create result
            result = ManifestResult(
                bol_number=bol_number,
                entries=entries,
                total_entries=len(entries),
                tracking_url=self.base_url,
                extraction_time=datetime.now().isoformat(),
                success=True
            )
            
            print(f"✅ BOL tracking completed successfully")
            print(f"📋 Found {len(entries)} manifest entries")
            
            return result
            
        except Exception as e:
            print(f"❌ Unexpected error during BOL tracking: {e}")
            return ManifestResult(
                bol_number=bol_number,
                entries=[],
                total_entries=0,
                tracking_url=self.base_url,
                extraction_time=datetime.now().isoformat(),
                success=False,
                error_message=str(e)
            )
        
        finally:
            # Clean up WebDriver
            if self.driver:
                self.driver.quit()
                print("🧹 WebDriver cleaned up")
    
    def save_manifest_results(self, result: ManifestResult) -> Path:
        """Save manifest results to JSON file"""
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Create output directory if it doesn't exist
        output_dir = Path("manifest_results")
        output_dir.mkdir(exist_ok=True)
        
        # Convert dataclass to dict for JSON serialization
        result_dict = {
            'bol_number': result.bol_number,
            'entries': [
                {
                    'office': entry.office,
                    'reference_id': entry.reference_id,
                    'date': entry.date,
                    'status': entry.status
                }
                for entry in result.entries
            ],
            'total_entries': result.total_entries,
            'tracking_url': result.tracking_url,
            'extraction_time': result.extraction_time,
            'success': result.success,
            'error_message': result.error_message
        }
        
        output_file = output_dir / f"manifest_{result.bol_number}_{timestamp}.json"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result_dict, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Manifest results saved to: {output_file}")
        return output_file

def extract_bol_from_data(extracted_data: Dict[str, Any]) -> Optional[str]:
    """Extract BOL number from extracted document data"""
    
    form_fields = extracted_data.get('form_fields', {})
    
    # Try different possible field names for BOL
    bol_candidates = [
        form_fields.get('bill_of_lading', ''),
        form_fields.get('transport_document', ''),
        form_fields.get('bol', ''),
        form_fields.get('bl_number', ''),
        form_fields.get('document_number', '')
    ]
    
    # Return the first non-empty BOL number
    for bol in bol_candidates:
        if bol and bol.strip():
            return bol.strip()
    
    return None

def main():
    """Test the manifest tracker with BOL from extracted data"""
    print("=== eSAD MANIFEST TRACKER TEST ===\n")
    
    # Load the most recent extracted data file
    extracted_data_dir = Path("extracted_data")
    if extracted_data_dir.exists():
        json_files = list(extracted_data_dir.glob("*.json"))
        if json_files:
            # Get the most recent file
            latest_file = max(json_files, key=lambda x: x.stat().st_mtime)
            print(f"📄 Loading data from: {latest_file}")
            
            with open(latest_file, 'r', encoding='utf-8') as f:
                extracted_data = json.load(f)
        else:
            print("❌ No JSON files found in extracted_data directory")
            return
    else:
        print("❌ extracted_data directory not found")
        return
    
    # Extract BOL number from the data
    bol_number = extract_bol_from_data(extracted_data)
    
    if not bol_number:
        print("❌ No BOL number found in extracted data")
        print("📋 Available fields:")
        form_fields = extracted_data.get('form_fields', {})
        for field, value in form_fields.items():
            if value:
                print(f"   {field}: {value}")
        return
    
    print(f"🎯 Found BOL number: {bol_number}")
    
    # Initialize tracker
    tracker = ManifestTracker()
    
    # Track BOL
    result = tracker.track_bol(bol_number)
    
    # Save results
    if result.success:
        output_file = tracker.save_manifest_results(result)
        
        print(f"\n📊 MANIFEST TRACKING RESULTS:")
        print(f"   BOL Number: {result.bol_number}")
        print(f"   Total Entries: {result.total_entries}")
        print(f"   Tracking URL: {result.tracking_url}")
        print(f"   Extraction Time: {result.extraction_time}")
        
        print(f"\n📋 MANIFEST ENTRIES:")
        for i, entry in enumerate(result.entries, 1):
            print(f"   {i}. Office: {entry.office}")
            print(f"      Reference ID: {entry.reference_id}")
            print(f"      Date: {entry.date}")
            print(f"      Status: {entry.status}")
            print()
    else:
        print(f"\n❌ MANIFEST TRACKING FAILED:")
        print(f"   Error: {result.error_message}")
    
    print(f"✅ Manifest tracking completed!")

if __name__ == "__main__":
    main() 