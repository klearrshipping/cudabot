# modules/esad_address.py
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
import json
from datetime import datetime
import requests
import os
from config import OPENROUTER_API_KEY

@dataclass
class AddressComponent:
    """Represents a component of an address"""
    street_town: str
    city: str
    state_province_parish: str
    country: str

@dataclass
class FormattedAddress:
    """Represents a formatted address"""
    original: str
    formatted: str
    components: AddressComponent
    confidence: float
    issues: List[str]

class AddressFormatter:
    """Formats addresses into the structure: Street name or Town, City, State/Province/Parish, Country using LLM assistance"""
    
    def __init__(self):
        self.api_key = OPENROUTER_API_KEY
        # Use general models for secondary processing tasks
        from config import OPENROUTER_GENERAL_MODELS
        self.primary_model = OPENROUTER_GENERAL_MODELS["mistral_small"]
        self.backup_model = OPENROUTER_GENERAL_MODELS["kimi_standard"]
        
        # Common Jamaican parishes
        self.jamaican_parishes = {
            'kingston', 'st. andrew', 'st. catherine', 'clarendon', 'manchester',
            'st. elizabeth', 'westmoreland', 'hanover', 'st. james', 'trelawny',
            'st. ann', 'st. mary', 'portland', 'st. thomas', 'st. elizabeth'
        }
        
        # Common Jamaican cities
        self.jamaican_cities = {
            'kingston', 'montego bay', 'spanish town', 'portmore', 'ochi rios',
            'may pen', 'mandeville', 'savanna-la-mar', 'lucea', 'falmouth',
            'st. ann\'s bay', 'port antonio', 'morant bay', 'black river'
        }
        
        # Common countries
        self.countries = {
            'jamaica', 'united states', 'usa', 'canada', 'united kingdom', 'uk',
            'china', 'japan', 'germany', 'france', 'spain', 'italy', 'brazil',
            'mexico', 'trinidad and tobago', 'barbados', 'guyana', 'suriname'
        }
        
        # Address patterns
        self.patterns = {
            'street_number': r'\b\d+\s+',
            'postal_code': r'\b\d{5}(?:-\d{4})?\b',
            'phone_number': r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
            'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        }
    
    def clean_address(self, address: str) -> str:
        """Clean and normalize address text"""
        if not address:
            return ""
        
        # Convert to lowercase for processing
        cleaned = address.lower().strip()
        
        # Remove common unwanted patterns
        cleaned = re.sub(self.patterns['postal_code'], '', cleaned)
        cleaned = re.sub(self.patterns['phone_number'], '', cleaned)
        cleaned = re.sub(self.patterns['email'], '', cleaned)
        
        # Remove extra whitespace and punctuation
        cleaned = re.sub(r'\s+', ' ', cleaned)
        cleaned = re.sub(r'[^\w\s,.-]', '', cleaned)
        cleaned = cleaned.strip()
        
        return cleaned
    
    def extract_components(self, address: str) -> AddressComponent:
        """Extract address components from cleaned address"""
        parts = [part.strip() for part in address.split(',') if part.strip()]
        
        # Initialize components
        street_town = ""
        city = ""
        state_province_parish = ""
        country = ""
        
        if len(parts) >= 1:
            street_town = parts[0]
        
        if len(parts) >= 2:
            city = parts[1]
        
        if len(parts) >= 3:
            state_province_parish = parts[2]
        
        if len(parts) >= 4:
            country = parts[3]
        
        return AddressComponent(
            street_town=street_town,
            city=city,
            state_province_parish=state_province_parish,
            country=country
        )
    
    def smart_parse_address(self, address: str) -> AddressComponent:
        """Intelligently parse address using pattern recognition"""
        cleaned = self.clean_address(address)
        issues = []
        
        # If already comma-separated, use that
        if ',' in cleaned:
            return self.extract_components(cleaned)
        
        # Try to identify components by keywords
        words = cleaned.split()
        components = {
            'street_town': [],
            'city': [],
            'state_province_parish': [],
            'country': []
        }
        
        i = 0
        while i < len(words):
            word = words[i].lower()
            
            # Check for country
            if word in self.countries or any(country in word for country in self.countries):
                components['country'].append(words[i])
                i += 1
                continue
            
            # Check for Jamaican parish
            if word in self.jamaican_parishes or any(parish in word for parish in self.jamaican_parishes):
                components['state_province_parish'].append(words[i])
                i += 1
                continue
            
            # Check for city
            if word in self.jamaican_cities or any(city in word for city in self.jamaican_cities):
                components['city'].append(words[i])
                i += 1
                continue
            
            # Default to street/town
            components['street_town'].append(words[i])
            i += 1
        
        return AddressComponent(
            street_town=' '.join(components['street_town']),
            city=' '.join(components['city']),
            state_province_parish=' '.join(components['state_province_parish']),
            country=' '.join(components['country'])
        )
    
    def call_llm_for_address_formatting(self, address: str) -> Dict:
        """Use LLM to format address with primary/backup model approach"""
        prompt = f"""
You are an expert address formatter for customs documentation. Format the following address into the structure: "Street name or Town, City, State/Province/Parish, Country"

Address to format: {address}

Requirements:
1. Extract street name or town
2. Identify the city
3. Identify state/province/parish
4. Identify the country
5. Format as: "Street/Town, City, State/Province/Parish, Country"
6. For Jamaican addresses, use proper parish names (St. Andrew, St. James, etc.)
7. Remove any phone numbers, emails, or postal codes
8. Keep only the essential address components

Return ONLY a JSON object with this structure:
{{
    "formatted_address": "Street/Town, City, State/Province/Parish, Country",
    "components": {{
        "street_town": "street name or town",
        "city": "city name",
        "state_province_parish": "state/province/parish",
        "country": "country name"
    }},
    "confidence": 0.95,
    "explanation": "brief explanation of formatting decisions"
}}
"""
        
        try:
            # Try primary model first
            response = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/your-repo",
                    "X-Title": "ESAD Address Formatter"
                },
                json={
                    "model": self.primary_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 500
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                return self._parse_llm_response(content, "primary")
            else:
                print(f"⚠️ Primary model failed, trying backup...")
                return self._call_backup_model(prompt)
                
        except Exception as e:
            print(f"❌ Primary model error: {e}")
            return self._call_backup_model(prompt)
    
    def _call_backup_model(self, prompt: str) -> Dict:
        """Call backup model when primary fails"""
        try:
            response = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/your-repo",
                    "X-Title": "ESAD Address Formatter"
                },
                json={
                    "model": self.backup_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 500
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                return self._parse_llm_response(content, "backup")
            else:
                raise Exception(f"Backup model failed with status {response.status_code}")
                
        except Exception as e:
            print(f"❌ Backup model error: {e}")
            return {
                "formatted_address": "",
                "components": {"street_town": "", "city": "", "state_province_parish": "", "country": ""},
                "confidence": 0.0,
                "explanation": f"Both LLM models failed: {str(e)}",
                "model_used": "none"
            }
    
    def _parse_llm_response(self, content: str, model_type: str) -> Dict:
        """Parse LLM response and extract formatted address"""
        try:
            # Clean the response
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            
            # Parse JSON
            result = json.loads(content)
            
            return {
                "formatted_address": result.get("formatted_address", ""),
                "components": result.get("components", {}),
                "confidence": result.get("confidence", 0.8),
                "explanation": result.get("explanation", ""),
                "model_used": model_type
            }
            
        except Exception as e:
            print(f"❌ Failed to parse LLM response: {e}")
            return {
                "formatted_address": "",
                "components": {"street_town": "", "city": "", "state_province_parish": "", "country": ""},
                "confidence": 0.0,
                "explanation": f"Failed to parse LLM response: {str(e)}",
                "model_used": model_type
            }
    
    def format_address(self, address: str) -> FormattedAddress:
        """Format address into the required structure using LLM assistance"""
        if not address:
            return FormattedAddress(
                original=address,
                formatted="",
                components=AddressComponent("", "", "", ""),
                confidence=0.0,
                issues=["Empty address provided"]
            )
        
        original = address
        issues = []
        
        print(f"🤖 Using LLM to format address: {address[:50]}...")
        
        # Use LLM for formatting
        llm_result = self.call_llm_for_address_formatting(address)
        
        # Extract components from LLM result
        components = AddressComponent(
            street_town=llm_result.get("components", {}).get("street_town", ""),
            city=llm_result.get("components", {}).get("city", ""),
            state_province_parish=llm_result.get("components", {}).get("state_province_parish", ""),
            country=llm_result.get("components", {}).get("country", "")
        )
        
        formatted = llm_result.get("formatted_address", "")
        confidence = llm_result.get("confidence", 0.0)
        model_used = llm_result.get("model_used", "unknown")
        
        # Add issues based on LLM processing
        if not formatted:
            issues.append("LLM failed to format address")
        if confidence < 0.5:
            issues.append(f"Low confidence formatting ({confidence:.2f})")
        if model_used == "backup":
            issues.append("Used backup model due to primary model failure")
        if model_used == "none":
            issues.append("Both LLM models failed, using fallback")
        
        # Fallback to rule-based formatting if LLM fails
        if not formatted or confidence < 0.3:
            print(f"⚠️ LLM formatting failed, using fallback method...")
            fallback_result = self._format_address_fallback(address)
            formatted = fallback_result.formatted
            components = fallback_result.components
            confidence = fallback_result.confidence
            issues.extend(fallback_result.issues)
            issues.append("Used fallback rule-based formatting")
        
        return FormattedAddress(
            original=original,
            formatted=formatted,
            components=components,
            confidence=confidence,
            issues=issues
        )
    
    def _format_address_fallback(self, address: str) -> FormattedAddress:
        """Fallback rule-based address formatting when LLM fails"""
        original = address
        issues = []
        confidence = 1.0
        
        # Clean the address
        cleaned = self.clean_address(address)
        if cleaned != address.lower().strip():
            issues.append("Address cleaned of unwanted characters")
            confidence -= 0.1
        
        # Parse components
        if ',' in cleaned:
            components = self.extract_components(cleaned)
        else:
            components = self.smart_parse_address(cleaned)
            issues.append("Address parsed using pattern recognition")
            confidence -= 0.2
        
        # Validate components
        if not components.street_town:
            issues.append("No street/town identified")
            confidence -= 0.3
        
        if not components.city:
            issues.append("No city identified")
            confidence -= 0.2
        
        if not components.state_province_parish:
            issues.append("No state/province/parish identified")
            confidence -= 0.2
        
        if not components.country:
            issues.append("No country identified")
            confidence -= 0.3
        
        # Format the address
        formatted_parts = []
        if components.street_town:
            formatted_parts.append(components.street_town)
        if components.city:
            formatted_parts.append(components.city)
        if components.state_province_parish:
            formatted_parts.append(components.state_province_parish)
        if components.country:
            formatted_parts.append(components.country)
        
        formatted = ", ".join(formatted_parts)
        
        return FormattedAddress(
            original=original,
            formatted=formatted,
            components=components,
            confidence=max(0.0, confidence),
            issues=issues
        )
    
    def process_esad_data(self, data: Dict) -> Dict:
        """Process ESAD data and format addresses"""
        results = {
            'importer_address': None,
            'exporter_address': None,
            'processing_timestamp': datetime.now().isoformat(),
            'summary': {
                'total_addresses_processed': 0,
                'successfully_formatted': 0,
                'issues_found': 0
            }
        }
        
        # Process importer address
        if 'importer_address' in data and data['importer_address']:
            importer_result = self.format_address(data['importer_address'])
            results['importer_address'] = {
                'original': importer_result.original,
                'formatted': importer_result.formatted,
                'components': {
                    'street_town': importer_result.components.street_town,
                    'city': importer_result.components.city,
                    'state_province_parish': importer_result.components.state_province_parish,
                    'country': importer_result.components.country
                },
                'confidence': importer_result.confidence,
                'issues': importer_result.issues
            }
            results['summary']['total_addresses_processed'] += 1
            if importer_result.formatted:
                results['summary']['successfully_formatted'] += 1
            if importer_result.issues:
                results['summary']['issues_found'] += 1
        
        # Process exporter address
        if 'exporter_address' in data and data['exporter_address']:
            exporter_result = self.format_address(data['exporter_address'])
            results['exporter_address'] = {
                'original': exporter_result.original,
                'formatted': exporter_result.formatted,
                'components': {
                    'street_town': exporter_result.components.street_town,
                    'city': exporter_result.components.city,
                    'state_province_parish': exporter_result.components.state_province_parish,
                    'country': exporter_result.components.country
                },
                'confidence': exporter_result.confidence,
                'issues': exporter_result.issues
            }
            results['summary']['total_addresses_processed'] += 1
            if exporter_result.formatted:
                results['summary']['successfully_formatted'] += 1
            if exporter_result.issues:
                results['summary']['issues_found'] += 1
        
        return results
    
    def save_results(self, results: Dict, output_dir: str = "address_results") -> Path:
        """Save formatted address results to JSON file"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        output_file = output_path / f"address_formatted_{timestamp}.json"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Address formatting results saved to: {output_file}")
        return output_file

def main():
    """Main function to demonstrate LLM-enhanced address formatting"""
    import sys
    formatter = AddressFormatter()

    # If a JSON file is provided as an argument, use it
    if len(sys.argv) > 1:
        input_path = sys.argv[1]
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # Try to extract addresses from result.extracted_fields
        extracted_fields = data.get('result', {}).get('extracted_fields', {})
        addresses = {
            'importer_address': extracted_fields.get('importer_address', ''),
            'exporter_address': extracted_fields.get('exporter_address', '')
        }
        print(f"🏠 ESAD Address Formatter: Processing addresses from {input_path}")
    else:
        # Fallback to hardcoded test addresses
        addresses = {
            'importer_address': 'Lot 226C Spanish Town Road Kingston 11 St. Andrew Jamaica',
            'exporter_address': '123 Main Street, Montego Bay, St. James, Jamaica'
        }
        print("🏠 ESAD Address Formatter with LLM Enhancement (Test Mode)")

    print("=" * 60)
    results = formatter.process_esad_data(addresses)

    print("\n📋 LLM-ENHANCED FORMATTING RESULTS:")
    print("-" * 40)
    for address_type, result in results.items():
        if result and isinstance(result, dict) and 'original' in result:
            print(f"📍 {address_type.replace('_', ' ').title()}:")
            print(f"   Original: {result['original']}")
            print(f"   Formatted: {result['formatted']}")
            print(f"   Confidence: {result['confidence']:.2f}")
            if result.get('components'):
                print(f"   Components:")
                for comp, value in result['components'].items():
                    if value:
                        print(f"     {comp.replace('_', ' ').title()}: {value}")
            if result.get('issues'):
                print(f"   Issues: {', '.join(result['issues'])}")
            print()
    print(f"📊 Summary:")
    print(f"   Total addresses processed: {results['summary']['total_addresses_processed']}")
    print(f"   Successfully formatted: {results['summary']['successfully_formatted']}")
    print(f"   Issues found: {results['summary']['issues_found']}")

    # Save results
    output_file = formatter.save_results(results)
    print(f"\n✅ Results saved to: {output_file}")

if __name__ == "__main__":
    main()