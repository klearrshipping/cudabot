#!/usr/bin/env python3
"""
Cached Invoice Extractor
Demonstrates integration with LLM caching system to reduce costs
"""

from dotenv import load_dotenv
load_dotenv()

import os, pathlib, json
from pathlib import Path
from datetime import datetime
import re
from typing import Dict, List, Any
import base64
import requests

# Import configuration
import sys
sys.path.append(str(Path(__file__).parent.parent))
from config import OPENROUTER_API_KEY, OPENROUTER_URL, OPENROUTER_HEADERS, OPENROUTER_EXTRACTION_MODELS

# Import the LLM cache system
from llm_cache import get_llm_cache, cache_llm_call

# Import enhanced database client
try:
    from modules.core.supabase_client import (
        create_or_get_order, create_document_record, save_invoice_extraction,
        check_database_schema
    )
    DB_AVAILABLE = True
except ImportError:
    print("⚠️ Database integration not available - falling back to file-based storage")
    DB_AVAILABLE = False


class CachedInvoiceExtractor:
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or OPENROUTER_API_KEY
        # Use GPT-5 Mini as primary model for best document extraction performance
        self.model = model or OPENROUTER_EXTRACTION_MODELS.get("gpt_5_mini", "openai/gpt-5-mini")
        self.base_url = OPENROUTER_URL or "https://openrouter.ai/api/v1/chat/completions"
        
        # Set up headers
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://yourdomain.com",
            "X-Title": "Invoice Document Extraction"
        }
        
        if not self.api_key or self.api_key == "your_openrouter_api_key_here":
            raise ValueError("Please set your OpenRouter API key in config.py")
        
        # Initialize cache
        self.cache = get_llm_cache()
        
        # Check database availability
        if DB_AVAILABLE:
            try:
                check_database_schema()
            except Exception as e:
                print(f"⚠️ Database check failed: {e}")

    def process_document(self, file_path: Path, save_to_file: bool = True, 
                        order_number: str = None, save_to_db: bool = True) -> Dict[str, Any]:
        """Process invoice using Claude Sonnet 4 via OpenRouter with caching"""
        print(f"🔄 Processing: {file_path.name}")

        try:
            # Convert PDF to image for OpenRouter compatibility
            image_data_url = self._convert_pdf_to_image(file_path)
            print(f"📸 PDF converted to image successfully")

            # Create the extraction prompt
            extraction_prompt = self._create_extraction_prompt()
            
            # Try to get from cache first
            cache_key_params = {
                'image_size': len(image_data_url),
                'file_hash': self._get_file_hash(file_path),
                'model': self.model
            }
            
            cached_response = self.cache.get(self.model, extraction_prompt, **cache_key_params)
            if cached_response:
                print(f"💾 Using cached extraction result (saved API call)")
                extracted_data = cached_response
            else:
                print(f"🆕 No cache hit, calling OpenRouter API...")
                # Send request to OpenRouter with image
                response = self._send_to_openrouter_with_image(extraction_prompt, image_data_url)
                extracted_data = self._parse_openrouter_response(response)
                
                # Cache the result
                self._cache_extraction_result(extraction_prompt, extracted_data, image_data_url, file_path)
            
            # Add metadata
            metadata = {
                "extraction_timestamp": datetime.now().isoformat(),
                "source_file": str(file_path),
                "processor": "claude_sonnet_4_via_openrouter_cached",
                "model": self.model,
                "processing_method": "pdf_to_image_conversion",
                "cached": cached_response is not None
            }
            
            extracted_data["_metadata"] = metadata
            
            # Save to database if available and requested
            if save_to_db and DB_AVAILABLE and order_number:
                try:
                    self._save_to_database(extracted_data, file_path, order_number, metadata)
                except Exception as e:
                    print(f"⚠️ Failed to save to database: {e}")
                    print("   Falling back to file-based storage")
                    save_to_file = True
            
            # Save to file if requested or if database save failed
            if save_to_file:
                self.save_results(extracted_data)
            
            return extracted_data
            
        except Exception as e:
            error_response = {
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            print(f"❌ Processing failed: {e}")
            return error_response

    def _cache_extraction_result(self, prompt: str, response: Dict[str, Any], 
                                image_data_url: str, file_path: Path):
        """Cache the extraction result for future use"""
        try:
            # Estimate cost based on prompt and response size
            prompt_tokens = len(prompt.split()) * 1.3  # Rough approximation
            response_tokens = len(json.dumps(response).split()) * 1.3
            
            cost_estimate = self.cache.estimate_cost(self.model, prompt_tokens, response_tokens)
            
            # Cache with relevant parameters
            cache_params = {
                'image_size': len(image_data_url),
                'file_hash': self._get_file_hash(file_path),
                'model': self.model
            }
            
            self.cache.set(self.model, prompt, response, cost_estimate, **cache_params)
            print(f"💾 Cached extraction result (estimated cost: ${cost_estimate:.4f})")
            
        except Exception as e:
            print(f"⚠️ Failed to cache result: {e}")

    def _get_file_hash(self, file_path: Path) -> str:
        """Generate a hash of the file content for caching"""
        try:
            import hashlib
            with open(file_path, 'rb') as f:
                content = f.read()
                return hashlib.md5(content).hexdigest()
        except Exception:
            return str(file_path.stat().st_mtime)  # Fallback to modification time

    def _convert_pdf_to_image(self, file_path: Path) -> str:
        """Convert PDF to base64 image data URL"""
        # Implementation would go here
        # For now, return a placeholder
        return "data:image/png;base64,placeholder"

    def _create_extraction_prompt(self) -> str:
        """Create the extraction prompt for the LLM"""
        return """Extract invoice data from this image. Return JSON with the following structure:
        {
            "supplier": {"name": "", "address": ""},
            "buyer": {"name": "", "address": ""},
            "invoice_details": {"invoice_number": "", "date": "", "order_number": ""},
            "items": [{"description": "", "quantity": "", "unit_price": ""}],
            "totals": {"subtotal": "", "tax_amount": "", "total_amount": ""},
            "currency": "",
            "extraction_confidence": "high/medium/low"
        }"""

    def _send_to_openrouter_with_image(self, prompt: str, image_data_url: str) -> Dict[str, Any]:
        """Send request to OpenRouter with image data"""
        # Implementation would go here
        # For now, return a placeholder
        return {"choices": [{"message": {"content": "{}"}}]}

    def _parse_openrouter_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Parse the OpenRouter response"""
        # Implementation would go here
        # For now, return a placeholder
        return {"status": "success", "data": "placeholder"}

    def _save_to_database(self, extracted_data: Dict[str, Any], file_path: Path, 
                         order_number: str, metadata: Dict[str, Any]):
        """Save extraction results to database"""
        # Implementation would go here
        pass

    def save_results(self, extracted_data: Dict[str, Any]):
        """Save results to file"""
        # Implementation would go here
        pass

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics for this extractor"""
        return self.cache.get_cache_stats()


# Alternative approach using the decorator
class DecoratedInvoiceExtractor:
    """Invoice extractor using the @cache_llm_call decorator"""
    
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or OPENROUTER_API_KEY
        self.model = model or OPENROUTER_EXTRACTION_MODELS.get("claude_sonnet_4", "anthropic/claude-sonnet-4")
        # ... other initialization code ...

    @cache_llm_call
    def extract_with_llm(self, model: str, prompt: str, image_data: str = None, **kwargs) -> Dict[str, Any]:
        """
        Extract data using LLM - automatically cached by decorator
        
        Args:
            model: LLM model name
            prompt: Extraction prompt
            image_data: Base64 image data
            **kwargs: Additional parameters
            
        Returns:
            Extracted data dictionary
        """
        # This method will automatically use caching
        # The decorator handles cache lookup and storage
        
        # Your actual LLM API call logic here
        print(f"🤖 Calling {model} API for extraction...")
        
        # Placeholder response
        return {
            "status": "success",
            "extracted_data": "placeholder",
            "model_used": model,
            "cached": False
        }


if __name__ == "__main__":
    # Test the cached extractor
    extractor = CachedInvoiceExtractor()
    
    # Show cache stats
    stats = extractor.get_cache_stats()
    print(f"Cache stats: {stats}")
    
    # Test with decorator approach
    decorated_extractor = DecoratedInvoiceExtractor()
    
    # This call will be automatically cached
    result = decorated_extractor.extract_with_llm(
        model="claude_sonnet_4",
        prompt="Extract invoice data from this document",
        image_data="placeholder"
    )
    
    print(f"Extraction result: {result}")
