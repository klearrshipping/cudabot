#!/usr/bin/env python3
"""
LLM Cache Module
Caches expensive LLM API calls to reduce costs and improve performance
"""

import hashlib
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Union
from pathlib import Path
import sqlite3

class LLMCache:
    """
    Cache system for LLM API calls to reduce costs and improve performance
    """
    
    def __init__(self, cache_dir: str = "cache/llm", db_path: str = "cache/llm_cache.db"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self._init_database()
        
        # Cache statistics
        self.stats = {
            'hits': 0,
            'misses': 0,
            'saves': 0,
            'total_saved_cost': 0.0
        }
    
    def _init_database(self):
        """Initialize SQLite database for cache storage"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create cache table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS llm_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cache_key TEXT UNIQUE NOT NULL,
                    model_name TEXT NOT NULL,
                    prompt_hash TEXT NOT NULL,
                    response_data TEXT NOT NULL,
                    cost_estimate REAL DEFAULT 0.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    access_count INTEGER DEFAULT 1,
                    file_path TEXT,
                    metadata TEXT
                )
            ''')
            
            # Create index for faster lookups
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_cache_key ON llm_cache(cache_key)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_model_name ON llm_cache(model_name)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_prompt_hash ON llm_cache(prompt_hash)')
            
            conn.commit()
            conn.close()
            print(f"✅ LLM cache database initialized: {self.db_path}")
            
        except Exception as e:
            print(f"⚠️ Warning: Could not initialize LLM cache database: {e}")
            print("   Caching will use file-based storage only")
    
    def _generate_cache_key(self, model_name: str, prompt: str, **kwargs) -> str:
        """Generate a unique cache key for the request"""
        # Create a hash of the prompt and additional parameters
        content = f"{model_name}:{prompt}:{json.dumps(kwargs, sort_keys=True)}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    def _generate_prompt_hash(self, prompt: str) -> str:
        """Generate a hash of just the prompt content"""
        return hashlib.sha256(prompt.encode()).hexdigest()
    
    def get(self, model_name: str, prompt: str, **kwargs) -> Optional[Dict[str, Any]]:
        """
        Get cached response for a model + prompt combination
        
        Args:
            model_name: Name of the LLM model
            prompt: The prompt text
            **kwargs: Additional parameters that affect the response
            
        Returns:
            Cached response dict or None if not found
        """
        try:
            cache_key = self._generate_cache_key(model_name, prompt, **kwargs)
            
            # Try database cache first
            if self.db_path.exists():
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT response_data, cost_estimate, access_count 
                    FROM llm_cache 
                    WHERE cache_key = ?
                ''', (cache_key,))
                
                result = cursor.fetchone()
                if result:
                    response_data, cost_estimate, access_count = result
                    
                    # Update access statistics
                    cursor.execute('''
                        UPDATE llm_cache 
                        SET last_accessed = CURRENT_TIMESTAMP, access_count = access_count + 1
                        WHERE cache_key = ?
                    ''', (cache_key,))
                    
                    conn.commit()
                    conn.close()
                    
                    # Parse cached response
                    cached_response = json.loads(response_data)
                    
                    # Update statistics
                    self.stats['hits'] += 1
                    self.stats['total_saved_cost'] += cost_estimate
                    
                    print(f"💾 LLM Cache HIT for {model_name} (saved ~${cost_estimate:.4f})")
                    return cached_response
            
            # Try file-based cache as fallback
            prompt_hash = self._generate_prompt_hash(prompt)
            cache_file = self.cache_dir / f"{model_name}_{prompt_hash[:16]}.json"
            
            if cache_file.exists():
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        cached_data = json.load(f)
                    
                    # Check if parameters match
                    if cached_data.get('kwargs') == kwargs:
                        self.stats['hits'] += 1
                        print(f"💾 LLM Cache HIT (file) for {model_name}")
                        return cached_data.get('response')
                except Exception as e:
                    print(f"⚠️ Error reading cache file: {e}")
            
            self.stats['misses'] += 1
            return None
            
        except Exception as e:
            print(f"⚠️ Cache lookup error: {e}")
            return None
    
    def set(self, model_name: str, prompt: str, response: Dict[str, Any], 
            cost_estimate: float = 0.0, **kwargs) -> bool:
        """
        Cache a response for future use
        
        Args:
            model_name: Name of the LLM model
            prompt: The prompt text
            response: The response to cache
            cost_estimate: Estimated cost of the API call
            **kwargs: Additional parameters that affect the response
            
        Returns:
            True if successfully cached, False otherwise
        """
        try:
            cache_key = self._generate_cache_key(model_name, prompt, **kwargs)
            prompt_hash = self._generate_prompt_hash(prompt)
            
            # Prepare metadata
            metadata = {
                'model_name': model_name,
                'prompt_length': len(prompt),
                'response_length': len(json.dumps(response)),
                'parameters': kwargs,
                'cached_at': datetime.now().isoformat()
            }
            
            # Save to database
            if self.db_path.exists():
                try:
                    conn = sqlite3.connect(self.db_path)
                    cursor = conn.cursor()
                    
                    cursor.execute('''
                        INSERT OR REPLACE INTO llm_cache 
                        (cache_key, model_name, prompt_hash, response_data, cost_estimate, metadata)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        cache_key,
                        model_name,
                        prompt_hash,
                        json.dumps(response),
                        cost_estimate,
                        json.dumps(metadata)
                    ))
                    
                    conn.commit()
                    conn.close()
                    
                except Exception as e:
                    print(f"⚠️ Database cache save failed: {e}")
            
            # Also save to file as backup
            cache_file = self.cache_dir / f"{model_name}_{prompt_hash[:16]}.json"
            try:
                cache_data = {
                    'model_name': model_name,
                    'prompt': prompt,
                    'response': response,
                    'kwargs': kwargs,
                    'cost_estimate': cost_estimate,
                    'cached_at': datetime.now().isoformat()
                }
                
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(cache_data, f, indent=2, ensure_ascii=False)
                
            except Exception as e:
                print(f"⚠️ File cache save failed: {e}")
            
            self.stats['saves'] += 1
            print(f"💾 LLM Cache SAVED for {model_name} (cost: ~${cost_estimate:.4f})")
            return True
            
        except Exception as e:
            print(f"❌ Cache save error: {e}")
            return False
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics and performance metrics"""
        try:
            if self.db_path.exists():
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Get database stats
                cursor.execute('SELECT COUNT(*) FROM llm_cache')
                total_cached = cursor.fetchone()[0]
                
                cursor.execute('SELECT SUM(cost_estimate) FROM llm_cache')
                total_cached_cost = cursor.fetchone()[0] or 0.0
                
                cursor.execute('SELECT SUM(access_count) FROM llm_cache')
                total_accesses = cursor.fetchone()[0] or 0
                
                conn.close()
                
                # Calculate hit rate
                total_requests = self.stats['hits'] + self.stats['misses']
                hit_rate = (self.stats['hits'] / total_requests * 100) if total_requests > 0 else 0
                
                return {
                    'cache_hits': self.stats['hits'],
                    'cache_misses': self.stats['misses'],
                    'cache_saves': self.stats['saves'],
                    'total_requests': total_requests,
                    'hit_rate_percentage': round(hit_rate, 2),
                    'total_saved_cost': round(self.stats['total_saved_cost'], 4),
                    'total_cached_items': total_cached,
                    'total_cached_cost': round(total_cached_cost, 4),
                    'total_accesses': total_accesses,
                    'cache_efficiency': f"${self.stats['total_saved_cost']:.4f} saved from {total_requests} requests"
                }
            else:
                return {
                    'cache_hits': self.stats['hits'],
                    'cache_misses': self.stats['misses'],
                    'cache_saves': self.stats['saves'],
                    'total_requests': self.stats['hits'] + self.stats['misses'],
                    'hit_rate_percentage': 0,
                    'total_saved_cost': round(self.stats['total_saved_cost'], 4),
                    'error': 'Database not available'
                }
                
        except Exception as e:
            return {
                'error': f'Failed to get cache stats: {e}',
                'basic_stats': self.stats
            }
    
    def clear_cache(self, model_name: Optional[str] = None, older_than_days: Optional[int] = None):
        """Clear cache entries based on criteria"""
        try:
            if self.db_path.exists():
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                if model_name and older_than_days:
                    # Clear old entries for specific model
                    cutoff_date = datetime.now() - timedelta(days=older_than_days)
                    cursor.execute('''
                        DELETE FROM llm_cache 
                        WHERE model_name = ? AND created_at < ?
                    ''', (model_name, cutoff_date.isoformat()))
                    
                elif model_name:
                    # Clear all entries for specific model
                    cursor.execute('DELETE FROM llm_cache WHERE model_name = ?', (model_name,))
                    
                elif older_than_days:
                    # Clear old entries for all models
                    cutoff_date = datetime.now() - timedelta(days=older_than_days)
                    cursor.execute('DELETE FROM llm_cache WHERE created_at < ?', (cutoff_date.isoformat(),))
                    
                else:
                    # Clear all cache
                    cursor.execute('DELETE FROM llm_cache')
                
                deleted_count = cursor.rowcount
                conn.commit()
                conn.close()
                
                print(f"🗑️ Cleared {deleted_count} cache entries")
                
        except Exception as e:
            print(f"❌ Cache clear error: {e}")
    
    def estimate_cost(self, model_name: str, prompt_tokens: int, response_tokens: int) -> float:
        """
        Estimate the cost of an API call based on token counts
        
        Args:
            model_name: Name of the LLM model
            prompt_tokens: Number of input tokens
            response_tokens: Number of output tokens
            
        Returns:
            Estimated cost in USD
        """
        # Cost per 1K tokens (approximate, adjust based on actual pricing)
        cost_rates = {
            'claude_sonnet_4': {'input': 0.003, 'output': 0.015},  # $3/$15 per 1M tokens
            'kimi': {'input': 0.0005, 'output': 0.0015},           # $0.5/$1.5 per 1M tokens
            'mistral_small': {'input': 0.0002, 'output': 0.0006},  # $0.2/$0.6 per 1M tokens
            'grok_mini': {'input': 0.0001, 'output': 0.0003},     # $0.1/$0.3 per 1M tokens
        }
        
        # Get rates for model (default to claude if unknown)
        rates = cost_rates.get(model_name, cost_rates['claude_sonnet_4'])
        
        # Calculate cost
        input_cost = (prompt_tokens / 1000) * rates['input']
        output_cost = (response_tokens / 1000) * rates['output']
        
        return input_cost + output_cost


# Global cache instance
_llm_cache = None

def get_llm_cache() -> LLMCache:
    """Get the global LLM cache instance"""
    global _llm_cache
    if _llm_cache is None:
        _llm_cache = LLMCache()
    return _llm_cache


def cache_llm_call(func):
    """
    Decorator to automatically cache LLM function calls
    
    Usage:
        @cache_llm_call
        def my_llm_function(model, prompt, **kwargs):
            # Your LLM logic here
            pass
    """
    def wrapper(*args, **kwargs):
        cache = get_llm_cache()
        
        # Extract model and prompt from function arguments
        if len(args) >= 2:
            model_name = args[0]
            prompt = args[1]
        else:
            model_name = kwargs.get('model')
            prompt = kwargs.get('prompt')
        
        if not model_name or not prompt:
            return func(*args, **kwargs)
        
        # Try to get from cache
        cached_response = cache.get(model_name, prompt, **kwargs)
        if cached_response is not None:
            return cached_response
        
        # Call original function
        response = func(*args, **kwargs)
        
        # Estimate cost and cache response
        if response and not response.get('error'):
            # Rough token estimation (you can improve this with actual token counting)
            prompt_tokens = len(prompt.split()) * 1.3  # Rough approximation
            response_tokens = len(json.dumps(response).split()) * 1.3
            
            cost_estimate = cache.estimate_cost(model_name, prompt_tokens, response_tokens)
            cache.set(model_name, prompt, response, cost_estimate, **kwargs)
        
        return response
    
    return wrapper


if __name__ == "__main__":
    # Test the cache system
    cache = get_llm_cache()
    
    # Test caching
    test_prompt = "Extract invoice data from this document"
    test_response = {"status": "success", "data": "test data"}
    
    print("🧪 Testing LLM Cache System...")
    
    # Save to cache
    cache.set("test_model", test_prompt, test_response, 0.01)
    
    # Retrieve from cache
    cached = cache.get("test_model", test_prompt)
    print(f"Retrieved from cache: {cached}")
    
    # Show stats
    stats = cache.get_cache_stats()
    print(f"Cache stats: {stats}")
