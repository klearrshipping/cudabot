import requests
import os
import time
from typing import Optional, Tuple, Dict

class LLMClient:
    # Class-level rate limit tracking
    _rate_limited_models: Dict[str, float] = {}
    _rate_limit_duration = 300  # 5 minutes
    def __init__(self):
        # Load API key and endpoint from config or env
        try:
            from config import OPENROUTER_API_KEY, OPENROUTER_URL, OPENROUTER_HEADERS
            self.api_key = OPENROUTER_API_KEY
            self.api_base = OPENROUTER_URL
            self.headers = OPENROUTER_HEADERS
        except ImportError:
            self.api_key = os.getenv('OPENROUTER_API_KEY')
            self.api_base = os.getenv('OPENROUTER_URL')
            self.headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
        if not self.api_key or not self.api_base:
            raise RuntimeError("LLMClient: Missing OpenRouter API key or base URL.")

    @classmethod
    def is_model_rate_limited(cls, model: str) -> bool:
        """Check if a model is currently rate limited."""
        if model not in cls._rate_limited_models:
            return False
        
        # Check if rate limit has expired
        if time.time() - cls._rate_limited_models[model] > cls._rate_limit_duration:
            del cls._rate_limited_models[model]
            return False
        
        return True

    @classmethod
    def mark_model_rate_limited(cls, model: str):
        """Mark a model as rate limited."""
        cls._rate_limited_models[model] = time.time()
        print(f"🚫 Marked {model} as rate limited for {cls._rate_limit_duration}s")

    def send_prompt(self, prompt, model=None, retry_on_rate_limit=True, max_retries=3):
        """
        Send prompt to LLM with proper rate limit handling.
        
        Args:
            prompt: The prompt to send
            model: The model to use
            retry_on_rate_limit: Whether to retry on 429 errors
            max_retries: Maximum number of retries for rate limits
            
        Returns:
            Tuple of (response_text, success, error_type)
        """
        # Check if model is currently rate limited
        if self.is_model_rate_limited(model):
            print(f"⏭️  Skipping {model} - currently rate limited")
            return "", False, "rate_limit"
        
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
        
        for attempt in range(max_retries + 1):
            try:
                resp = requests.post(self.api_base, headers=self.headers, json=payload, timeout=60)
                
                # Handle rate limiting specifically
                if resp.status_code == 429:
                    if retry_on_rate_limit and attempt < max_retries:
                        # Exponential backoff: wait 2^attempt seconds
                        wait_time = 2 ** attempt
                        print(f"⏳ Rate limited (429), waiting {wait_time}s before retry {attempt + 1}/{max_retries}")
                        time.sleep(wait_time)
                        continue
                    else:
                        print(f"❌ Rate limit exceeded after {max_retries} retries")
                        # Mark model as rate limited for future requests
                        self.mark_model_rate_limited(model)
                        return "", False, "rate_limit"
                
                # Handle other HTTP errors
                resp.raise_for_status()
                
                # Parse successful response
                data = resp.json()
                if 'choices' in data and data['choices']:
                    response_text = data['choices'][0]['message']['content']
                    return response_text, True, None
                else:
                    return data.get('content', ''), True, None
                    
            except requests.exceptions.RequestException as e:
                if attempt < max_retries:
                    wait_time = 2 ** attempt
                    print(f"⏳ Request failed, waiting {wait_time}s before retry {attempt + 1}/{max_retries}: {e}")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"❌ LLMClient error after {max_retries} retries: {e}")
                    return "", False, "request_error"
            except Exception as e:
                print(f"❌ LLMClient unexpected error: {e}")
                return "", False, "unexpected_error"
        
        return "", False, "max_retries_exceeded"
