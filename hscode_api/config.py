"""
Configuration file for the HS Codes application.
Now uses Google Secret Manager for credentials.
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from secret_manager import get_secret

# Supabase credentials - HS Codes Project - From Secret Manager
SUPABASE_URL = get_secret("hs-codes-supabase-url")
SUPABASE_ANON_KEY = get_secret("hs-codes-supabase-anon-key")
SUPABASE_SERVICE_ROLE_KEY = get_secret("hs-codes-supabase-service-role-key")

# Backward compatibility alias for existing modules
SUPABASE_KEY = SUPABASE_ANON_KEY

# Required: OpenRouter API Key - From Secret Manager
OPENROUTER_API_KEY = get_secret("openrouter-api-key")

# OpenRouter API Configuration
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_HEADERS = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": "<YOUR_SITE_URL>",  # Optional. Site URL for rankings on openrouter.ai.
    "X-Title": "<YOUR_SITE_NAME>",  # Optional. Site title for rankings on openrouter.ai.
}

# Customs API Configuration
CUSTOMS_API_BASE_URL = "http://localhost:8000"  # customs_api runs on port 8000
CUSTOMS_API_TIMEOUT = 30  # seconds

# OpenRouter Models - General Purpose (Used for general AI tasks)
OPENROUTER_GENERAL_MODELS = {
    "mistral_small": {
        "name": "mistralai/mistral-small-3.2-24b-instruct",
        "description": "Mistral Small 3.2 24B Instruct",
        "temperature": 0.7,
        "max_tokens": 1000
    },
    "kimi_standard": {
        "name": "moonshotai/kimi-k2",
        "description": "Moonshot K2 Standard",
        "temperature": 0.7,
        "max_tokens": 1000
    },
    "claude_sonnet_4": {
        "name": "anthropic/claude-sonnet-4",
        "description": "Anthropic Claude Sonnet 4",
        "temperature": 0.7,
        "max_tokens": 1000
    },
    "gpt_5_mini": {
        "name": "openai/gpt-5-mini",
        "description": "OpenAI GPT-5 Mini",
        "temperature": 0.7,
        "max_tokens": 1000
    },
    "gpt_5": {
        "name": "openai/gpt-5",
        "description": "OpenAI GPT-5",
        "temperature": 0.7,
        "max_tokens": 1000
    }
}

# OpenRouter API configuration (matching expected format)
OPENROUTER_CONFIG = {
    "api_url": "https://openrouter.ai/api/v1/chat/completions",
    "headers": {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "<YOUR_SITE_URL>",
        "X-Title": "<YOUR_SITE_NAME>"
    }
}

# Backward compatibility alias for existing modules
OPENROUTER_MODELS = OPENROUTER_GENERAL_MODELS