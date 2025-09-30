# ASYCUDA Configuration File

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from secret_manager import get_secret

# Application Path
JNLP_PATH = r"C:\Users\rafer\OneDrive\Desktop\AWLiveExternal.jnlp"

# AsycudaLogin Credentials - From Secret Manager
USERNAME = get_secret("asycuda-username")
PASSWORD = get_secret("asycuda-password")

# Supabase Configuration - From Secret Manager  
SUPABASE_URL = get_secret("supabase-url")
SUPABASE_ANON_KEY = get_secret("supabase-anon-key")
SUPABASE_SERVICE_ROLE_KEY = get_secret("supabase-service-role-key")

# Image Recognition Settings
CONFIDENCE_LEVEL = 0.8
WAIT_TIME = 10  # seconds to wait for application to load
TYPE_INTERVAL = 0.1  # seconds between keystrokes when typing

# Required: OpenRouter API Key for CAPTCHA solving - From Secret Manager
OPENROUTER_API_KEY = get_secret("openrouter-api-key")

# OpenRouter API Configuration
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_HEADERS = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": "https://github.com/your-repo",  # Optional. Site URL for rankings on openrouter.ai.
    "X-Title": "CUDA Project",  # Optional. Site title for rankings on openrouter.ai.
}

# OpenRouter Models - General Purpose (Used for general AI tasks)
OPENROUTER_GENERAL_MODELS = {
    "mistral_small": "mistralai/mistral-small-3.2-24b-instruct",
    "kimi": "moonshotai/kimi-k2:free",
    "kimi_standard": "moonshotai/kimi-k2",
    "grok_mini": "x-ai/grok-3-mini",
    "gpt_5_nano": "openai/gpt-5-nano",
    "gpt_5": "openai/gpt-5"
}

# OpenRouter Models - Document Extraction (Used for eSAD extraction scripts)
# Ranking: 1) gpt_5_mini, 2) llama, 3) gemini, 4) gpt_5_nano, 5) claude, 6) gpt_5
OPENROUTER_EXTRACTION_MODELS = {
    "gpt_5_mini": "openai/gpt-5-mini",                                    # 1st - Primary model
    "llama_3_2_11b_vision": "meta-llama/llama-3.2-11b-vision-instruct",  # 2nd - Secondary model
    "gemini_2_5_pro": "google/gemini-2.5-pro",                            # 3rd - Google alternative
    "gpt_5_nano": "openai/gpt-5-nano",                                    # 4th - Lightweight option
    "claude_sonnet_4": "anthropic/claude-sonnet-4",                       # 5th - Alternative option
    "gpt_5": "openai/gpt-5"                                               # 6th - High-end option
}

# Backward compatibility alias for existing modules
OPENROUTER_MODELS = OPENROUTER_EXTRACTION_MODELS

# Validation: Check if all secrets are accessible
def validate_config():
    """Validate that all required secrets are accessible."""
    required_secrets = [
        ('asycuda-username', 'USERNAME'),
        ('asycuda-password', 'PASSWORD'), 
        ('supabase-url', 'SUPABASE_URL'),
        ('supabase-anon-key', 'SUPABASE_ANON_KEY'),
        ('supabase-service-role-key', 'SUPABASE_SERVICE_ROLE_KEY'),
        ('openrouter-api-key', 'OPENROUTER_API_KEY')
    ]
    
    missing_secrets = []
    for secret_name, var_name in required_secrets:
        try:
            value = get_secret(secret_name)
            if not value:
                missing_secrets.append(secret_name)
        except Exception:
            missing_secrets.append(secret_name)
    
    if missing_secrets:
        raise ValueError(f"Cannot access required secrets: {', '.join(missing_secrets)}")
    
    return True

# Uncomment the line below if you want to validate config on import
# validate_config() 