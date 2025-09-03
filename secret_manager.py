"""
Simple Google Secret Manager helper using gcloud CLI.
Uses your existing gcloud authentication.
"""

import subprocess
import json
from functools import lru_cache

# Your project ID 
PROJECT_ID = "secrets-2025-12345"

@lru_cache(maxsize=128)
def get_secret(secret_name: str) -> str:
    """
    Get a secret using gcloud CLI (uses your existing login).
    
    Args:
        secret_name: The name of the secret to retrieve
        
    Returns:
        The secret value as a string
        
    Raises:
        Exception: If the secret cannot be retrieved
    """
    try:
        # Use gcloud CLI to get the secret (you're already logged in!)
        # Try different possible gcloud paths
        gcloud_paths = [
            "gcloud",  # If in PATH
            r"C:\Users\rafer\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd",
            r"C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd",
            r"C:\Program Files\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
        ]
        
        for gcloud_cmd in gcloud_paths:
            try:
                result = subprocess.run([
                    gcloud_cmd, "secrets", "versions", "access", "latest",
                    f"--secret={secret_name}",
                    f"--project={PROJECT_ID}"
                ], capture_output=True, text=True, check=True)
                return result.stdout.strip()
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
        
        raise Exception(f"Could not find gcloud command in any expected location")
        
    except Exception as e:
        raise Exception(f"Error getting secret '{secret_name}': {str(e)}")

def test_secret_access():
    """Test that we can access secrets."""
    try:
        # Test with a known secret
        test_value = get_secret("supabase-url")
        print(f"✅ Secret access working! (got: {test_value[:20]}...)")
        return True
    except Exception as e:
        print(f"❌ Secret access failed: {e}")
        return False

def get_secret_or_fallback(secret_name: str, fallback_env_var: str = None, default: str = None) -> str:
    """
    Get a secret with fallback to environment variable and default value.
    Useful during migration period.
    
    Args:
        secret_name: The name of the secret in Secret Manager
        fallback_env_var: Environment variable to check if secret fails
        default: Default value if both secret and env var fail
        
    Returns:
        The secret/env var/default value as a string
    """
    try:
        return get_secret(secret_name)
    except Exception as e:
        print(f"Warning: Could not get secret '{secret_name}': {e}")
        
        if fallback_env_var and os.environ.get(fallback_env_var):
            print(f"Using fallback environment variable '{fallback_env_var}'")
            return os.environ.get(fallback_env_var)
        
        if default:
            print(f"Using default value for '{secret_name}'")
            return default
            
        raise Exception(f"No secret, environment variable, or default available for '{secret_name}'")
