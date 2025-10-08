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
                        
                        # Only include "Direct Validate" status
                        if status.lower() == "direct validate":
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
                    print(f"   ✓ Found 'Direct Validate' record")
                    print(f"\n{'='*60}")
                    print(f"RESULTS (JSON Format)")
                    print(f"{'='*60}\n")
                    print(json.dumps(results, indent=2))
                else:
                    print(f"   ⚠ No 'Direct Validate' record found")
            
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
    
    def save_manifest_results(self, result: ManifestResult) -> Path:
        """Save manifest results to JSON file"""
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Create output directory if it doesn't exist
        output_dir = Path("manifest_results")
        output_dir.mkdir(exist_ok=True)
        
        # Convert dataclass to dict for JSON serialization
        result_dict = {
            'bol_number': result.bol_number,
            'entries': result.entries,
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