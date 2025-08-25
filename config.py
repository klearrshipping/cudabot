# ASYCUDA Configuration File

import os
from pathlib import Path

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    # Get the directory where this config.py file is located
    current_dir = Path(__file__).parent
    env_path = current_dir / '.env'
    load_dotenv(env_path)
except ImportError:
    # python-dotenv not installed, environment variables should be set manually
    print("python-dotenv not installed. Make sure environment variables are set manually.")
    pass

# Application Path
JNLP_PATH = r"C:\Users\rafer\OneDrive\Desktop\AWLiveExternal.jnlp"

# AsycudaLogin Credentials
USERNAME = os.environ.get("USERNAME")
PASSWORD = os.environ.get("PASSWORD")

# Supabase Configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

# Image Recognition Settings
CONFIDENCE_LEVEL = 0.8
WAIT_TIME = 10  # seconds to wait for application to load
TYPE_INTERVAL = 0.1  # seconds between keystrokes when typing

# Required: OpenRouter API Key for CAPTCHA solving
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

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
    "gpt_5_nano": "openai/gpt-5-nano"
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

# Validation: Check if critical environment variables are loaded
def validate_config():
    """Validate that all required environment variables are loaded."""
    required_vars = [
        'USERNAME', 'PASSWORD', 'SUPABASE_URL', 'SUPABASE_ANON_KEY', 
        'SUPABASE_SERVICE_ROLE_KEY', 'OPENROUTER_API_KEY'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not globals().get(var):
            missing_vars.append(var)
    
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
    
    return True

# Uncomment the line below if you want to validate config on import
# validate_config() 