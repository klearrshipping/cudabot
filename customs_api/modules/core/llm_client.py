import requests
import os

class LLMClient:
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

    def send_prompt(self, prompt, model=None):
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
        try:
            resp = requests.post(self.api_base, headers=self.headers, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            # Try to extract the LLM's response text
            if 'choices' in data and data['choices']:
                return data['choices'][0]['message']['content']
            # Fallback: try to extract from other fields
            return data.get('content', '')
        except Exception as e:
            print(f"❌ LLMClient error: {e}")
            return ""
