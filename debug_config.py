#!/usr/bin/env python3
"""
Debug script to check environment variable loading
"""

import os
from pathlib import Path
from dotenv import load_dotenv

print("🔍 Debugging Environment Variables")
print("=" * 50)

# Load .env file from root directory
root_dir = Path(__file__).parent
env_path = root_dir / "env.txt"
print(f"📁 Looking for env file at: {env_path}")
print(f"📁 File exists: {env_path.exists()}")

load_dotenv(env_path)

# Check OpenRouter API key
api_key = os.environ.get("OPENROUTER_API_KEY")
print(f"🔑 OPENROUTER_API_KEY: {api_key}")
if api_key:
    print(f"🔑 API Key length: {len(api_key)}")
    print(f"🔑 API Key starts with: {api_key[:10]}...")
else:
    print("❌ No API key found!")

# Check other variables
print(f"🌐 SUPABASE_URL: {os.environ.get('HS_CODES_SUPABASE_URL', 'NOT SET')}")
print(f"🔑 SUPABASE_ANON_KEY: {os.environ.get('HS_CODES_SUPABASE_ANON_KEY', 'NOT SET')[:20]}...")

# Try to import the config
print("\n📦 Testing config import...")
try:
    from hscode_api.config import OPENROUTER_API_KEY, OPENROUTER_CONFIG
    print(f"✅ Config imported successfully")
    print(f"🔑 Config OPENROUTER_API_KEY: {OPENROUTER_API_KEY}")
    print(f"🔧 Config OPENROUTER_CONFIG: {OPENROUTER_CONFIG}")
except Exception as e:
    print(f"❌ Config import failed: {e}")
