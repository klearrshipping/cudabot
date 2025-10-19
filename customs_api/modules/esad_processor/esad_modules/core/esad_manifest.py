#!/usr/bin/env python3
"""
eSAD Manifest Tracker - Clean Version
Automates BOL tracking on Jamaica Customs website and extracts manifest data
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time
import json
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

@dataclass
class ManifestResult:
    """Complete manifest tracking result"""
    bol_number: str
    entries: List[Dict]
    total_entries: int
    tracking_url: str
    extraction_time: str
    success: bool
    error_message: Optional[str] = None

class ManifestTracker:
    """
    A scraper for Jamaica Customs BOL (Bill of Lading) tracking system.
    Uses Selenium to handle JavaScript-rendered modal dialogs.
    """
    
    def __init__(self, headless: bool = True):
        """
        Initialize the tracker with Selenium WebDriver.
        
        Args:
            headless: Run browser in headless mode (default: True)
        """
        self.base_url = "https://jets.jacustoms.gov.jm/portal/services/docTracking/track.jsf"
        
        # Setup Chrome options
        options = webdriver.ChromeOptions()
        if headless:
            options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        
        # SSL certificate error handling
        options.add_argument('--ignore-certificate-errors')
        options.add_argument('--ignore-ssl-errors')
        options.add_argument('--allow-insecure-localhost')
        
        # Suppress all Chrome logging
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        options.add_argument('--log-level=3')
        options.add_argument('--silent')
        options.add_argument('--disable-logging')
        
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        self.driver = webdriver.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, 20)  # Increased timeout
    
    def track_bol(self, bol_number: str, verbose: bool = True) -> ManifestResult:
        """
        Track a BOL number and return the results from the modal.
        
        Args:
            bol_number: The Bill of Lading number to track (e.g., 'B870Y28X3TL')
            verbose: Show detailed progress output (default: True)
            
        Returns:
            ManifestResult object with tracking data
        """
        try:
            if verbose:
                print(f"\n{'='*60}")
                print(f"STEP 1: Initializing BOL Tracking")
                print(f"{'='*60}")
                print(f"BOL Number: {bol_number}")
            
            # Load the page
            if verbose:
                print(f"\nSTEP 2: Loading Jamaica Customs Portal...")
            self.driver.get(self.base_url)
            
            # Check for SSL warning page and bypass if present
            try:
                proceed_link = WebDriverWait(self.driver, 3).until(
                    EC.presence_of_element_located((By.ID, "proceed-link"))
                )
                if verbose:
                    print(f"   ⚠ SSL Warning detected - bypassing...")
                proceed_link.click()
                time.sleep(2)
            except TimeoutException:
                if verbose:
                    print(f"   ✓ Portal loaded successfully")
            
            # Wait for the input field to be present
            input_field = self.wait.until(
                EC.presence_of_element_located((By.ID, "bolTracking:par3"))
            )
            
            # Enter BOL number
            if verbose:
                print(f"\nSTEP 3: Submitting BOL Query...")
            input_field.clear()
            input_field.send_keys(bol_number)
            
            # Click the submit button
            submit_button = self.driver.find_element(By.ID, "bolTracking:j_idt92")
            submit_button.click()
            
            # Give the AJAX request time to initiate
            time.sleep(1)
            
            # Wait for the modal dialog to appear
            if verbose:
                print(f"   ✓ Request submitted")
                print(f"\nSTEP 4: Waiting for response...")
            modal = self.wait.until(
                EC.visibility_of_element_located((By.ID, "bolTracking:j_idt93"))
            )
            
            # Wait specifically for the table tbody to be present and populated
            tbody = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#bolTracking\\:j_idt98 tbody.ui-datatable-data"))
            )
            
            # Wait for at least one row to appear in the tbody
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#bolTracking\\:j_idt98 tbody.ui-datatable-data tr"))
            )
            
            # Critical: Wait for actual data cells (td elements) to be populated
            self.wait.until(
                lambda driver: len(driver.find_elements(By.CSS_SELECTOR, "#bolTracking\\:j_idt98 tbody.ui-datatable-data tr td")) >= 4
            )
            
            # Additional wait to ensure all data is rendered
            time.sleep(1)
            
            if verbose:
                print(f"   ✓ Response received")
                print(f"\nSTEP 5: Extracting tracking data...")
            
            # Extract BOL code from the modal
            try:
                bol_code_input = self.driver.find_element(By.NAME, "bolTracking:j_idt97")
                bol_code = bol_code_input.get_attribute('value')
            except:
                bol_code = bol_number
            
            # Extract table data
            table = self.driver.find_element(By.ID, "bolTracking:j_idt98")
            tbody = table.find_element(By.CSS_SELECTOR, "tbody.ui-datatable-data")
            rows = tbody.find_elements(By.TAG_NAME, "tr")
            
            results = []
            
            for idx, row in enumerate(rows):
                try:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    
                    if len(cells) >= 4:
                        office = cells[0].text.strip()
                        reference_id = cells[1].text.strip()
                        status = cells[3].text.strip()
                        
                        # Extract all records, not just "Direct Validate"
                        record = {
                            'office': office,
                            'reference_id': reference_id,
                            'manifest_reg_no': f"{office} {reference_id}",
                            'date': cells[2].text.strip(),
                            'status': status
                        }
                        results.append(record)
                except Exception as e:
                    if verbose:
                        print(f"   ⚠ Warning: Error processing row {idx}: {str(e)}")
                    continue
            
            if verbose:
                if results:
                    print(f"   ✓ Found {len(results)} manifest record(s)")
                    print(f"\n{'='*60}")
                    print(f"RESULTS (JSON Format)")
                    print(f"{'='*60}\n")
                    print(json.dumps(results, indent=2))
                else:
                    print(f"   ⚠ No manifest records found")
            
            return ManifestResult(
                bol_number=bol_number,
                entries=results,
                total_entries=len(results),
                tracking_url=self.base_url,
                extraction_time=datetime.now().isoformat(),
                success=True
            )
            
        except TimeoutException:
            if verbose:
                print(f"\n{'='*60}")
                print(f"ERROR: Timeout waiting for tracking data")
                print(f"{'='*60}")
            return ManifestResult(
                bol_number=bol_number,
                entries=[],
                total_entries=0,
                tracking_url=self.base_url,
                extraction_time=datetime.now().isoformat(),
                success=False,
                error_message="Timeout waiting for tracking data"
            )
        except Exception as e:
            if verbose:
                print(f"\n{'='*60}")
                print(f"ERROR: {str(e)}")
                print(f"{'='*60}")
            return ManifestResult(
                bol_number=bol_number,
                entries=[],
                total_entries=0,
                tracking_url=self.base_url,
                extraction_time=datetime.now().isoformat(),
                success=False,
                error_message=str(e)
            )
    
    def track_multiple_bols(self, bol_numbers: List[str], verbose: bool = True) -> Dict[str, List[Dict]]:
        """
        Track multiple BOL numbers.
        
        Args:
            bol_numbers: List of BOL numbers to track
            verbose: Show detailed progress output (default: True)
            
        Returns:
            Dictionary mapping BOL numbers to their tracking results
        """
        results = {}
        for i, bol in enumerate(bol_numbers, 1):
            if verbose:
                print(f"\n\n{'#'*60}")
                print(f"Processing BOL {i} of {len(bol_numbers)}")
                print(f"{'#'*60}")
            results[bol] = self.track_bol(bol, verbose=verbose)
            time.sleep(1)  # Be nice to the server
        return results
    
    def close(self):
        """Close the browser and clean up."""
        if self.driver:
            self.driver.quit()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
    def save_manifest_results(self, result: ManifestResult) -> Dict[str, Any]:
        """Return manifest results as dictionary for consolidation (no longer saves separate files)"""
        
        # Convert dataclass to dict for JSON serialization
        result_dict = {
            'bol_number': result.bol_number,
            'entries': result.entries,
            'total_entries': result.total_entries,
            'tracking_url': result.tracking_url,
            'extraction_time': result.extraction_time,
            'success': result.success,
            'error_message': result.error_message,
            'timestamp': datetime.now().isoformat()
        }
        
        print(f"💾 Manifest results prepared for consolidation: {result.bol_number}")
        return result_dict


class ManifestProcessor:
    """Processor for manifest registration numbers"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the manifest processor"""
        self.config = config
    
    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process manifest registration number.
        
        Args:
            input_data: Dictionary containing manifest_registration_number
            
        Returns:
            Dictionary containing processed manifest data
        """
        try:
            manifest_number = input_data.get('manifest_registration_number')
            
            if not manifest_number:
                return {
                    'success': False,
                    'error': 'No manifest registration number found',
                    'manifest_processed': None
                }
            
            # For now, just return the manifest number as processed
            # In the future, this could include validation or formatting
            return {
                'success': True,
                'manifest_processed': manifest_number,
                'original_manifest': manifest_number,
                'error': None
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Manifest processing failed: {str(e)}',
                'manifest_processed': None
            }


def process_manifest_fields(manifest_fields: Dict[str, str], verbose: bool = False) -> Dict[str, Any]:
    """
    Process manifest-related fields from eSAD data using Jamaica Customs BOL tracking.
    
    Args:
        manifest_fields: Dictionary containing manifest_registration_number
        verbose: Show detailed output (default: False)
        
    Returns:
        Dictionary containing processed manifest data with tracking results
    """
    try:
        manifest_number = manifest_fields.get('manifest_registration_number', '')
        
        if not manifest_number:
            return {
                'success': False,
                'error': 'No manifest registration number found',
                'manifest_processed': None
            }
        
        if verbose:
            print(f"🔍 Tracking manifest number: {manifest_number}")
            print(f"🌐 Connecting to Jamaica Customs portal...")
        
        # Use ManifestTracker to actually track the BOL on Jamaica Customs website
        with ManifestTracker(headless=True) as tracker:
            if verbose:
                print(f"📡 Submitting BOL tracking request...")
            
            # Track the BOL number and get detailed results
            manifest_result = tracker.track_bol(manifest_number, verbose=verbose)
            
            if manifest_result.success:
                if verbose:
                    print(f"✅ BOL tracking successful!")
                    print(f"📋 Total entries found: {manifest_result.total_entries}")
                    if manifest_result.entries:
                        print(f"🏢 Office: {manifest_result.entries[0].get('office', 'N/A')}")
                        print(f"🆔 Reference ID: {manifest_result.entries[0].get('reference_id', 'N/A')}")
                        print(f"📅 Date: {manifest_result.entries[0].get('date', 'N/A')}")
                        print(f"✅ Status: {manifest_result.entries[0].get('status', 'N/A')}")
                
                # Consolidate results - if office, reference_id, and manifest_reg_no are the same, return simplified format
                consolidated_results = []
                seen_combinations = set()
                
                for entry in manifest_result.entries:
                    key = (entry['office'], entry['reference_id'], entry['manifest_reg_no'])
                    if key not in seen_combinations:
                        consolidated_results.append({
                            'office': entry['office'],
                            'reference_id': entry['reference_id'],
                            'manifest_reg_no': entry['manifest_reg_no']
                        })
                        seen_combinations.add(key)
                
                # Prepare comprehensive result
                result = {
                    'success': True,
                    'manifest_processed': manifest_number,
                    'tracking_results': consolidated_results[0] if consolidated_results else None,
                    'error': None
                }
                
                if verbose:
                    print(f"✅ Manifest tracking completed successfully")
                
                return result
            else:
                error_msg = manifest_result.error_message or "BOL tracking failed"
                if verbose:
                    print(f"❌ BOL tracking failed: {error_msg}")
                
                return {
                    'success': False,
                    'error': error_msg,
                    'manifest_processed': None,
                    'tracking_results': None
                }
        
    except Exception as e:
        error_msg = f'Manifest processing failed: {str(e)}'
        if verbose:
            print(f"❌ {error_msg}")
        
        return {
            'success': False,
            'error': error_msg,
            'manifest_processed': None,
            'tracking_results': None
        }


def main(manifest_number: str = None, verbose: bool = True):
    """
    Main function for processing manifest data.
    
    Args:
        manifest_number: The manifest/BOL number to process (if None, will look for test data)
        verbose: Show detailed output (default: True)
        
    Returns:
        Dictionary containing processed manifest data
    """
    import json
    import os
    
    # Suppress additional warnings
    os.environ['WDM_LOG'] = '0'
    
    # Use provided manifest number or fallback to test data
    if not manifest_number:
        manifest_number = "PSHFHKIN25072146"  # Fallback for standalone testing
        if verbose:
            print("🧪 Using fallback test data for standalone execution")
    
    if verbose:
        print(f"🔍 Processing manifest number: {manifest_number}")
    
    # Prepare manifest fields
    manifest_fields = {
        'manifest_registration_number': manifest_number
    }
    
    # Process manifest fields
    result = process_manifest_fields(manifest_fields, verbose=verbose)
    
    if verbose:
        print(f"\n📋 Final Result: {json.dumps(result, indent=2, ensure_ascii=False)}")
    
    return result


# Example usage
if __name__ == "__main__":
    import json
    import os
    
    # Suppress additional warnings
    os.environ['WDM_LOG'] = '0'
    
    # Single BOL tracking
    with ManifestTracker(headless=True) as tracker:
        result = tracker.track_bol("B870Y28X3TL", verbose=True)
        
        if result.success and result.entries:
            print(f"\n{'='*60}")
            print(f"RESULTS (JSON Format)")
            print(f"{'='*60}\n")
            print(json.dumps(result.entries, indent=2))
        else:
            print("\n✗ No results found")
    
    # Multiple BOL tracking example
    # bol_numbers = ["B870Y28X3TL", "ANOTHER_BOL_NUMBER"]
    # with ManifestTracker(headless=True) as tracker:
    #     all_results = {}
    #     for bol in bol_numbers:
    #         result = tracker.track_bol(bol, verbose=True)
    #         all_results[bol] = result.entries
    #     
    #     print(json.dumps(all_results, indent=2))