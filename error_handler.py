import asyncio
import traceback
from datetime import datetime, timezone
from typing import Dict, Optional, Callable, Any
from config import config
from supabase_client import supabase_manager

class ErrorHandler:
    """Comprehensive error handling with API key failover"""
    
    def __init__(self):
        self.error_counts = {}
        self.failed_keys = set()
        self.last_error_time = {}
    
    async def safe_execute(self, 
                          func: Callable, 
                          component: str, 
                          *args, 
                          max_retries: int = None,
                          **kwargs) -> Optional[Any]:
        """Safely execute function with error handling and retries"""
        
        max_retries = max_retries or config.MAX_RETRIES
        last_error = None
        
        for attempt in range(max_retries):
            try:
                # Execute the function
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                # Reset error count on success
                if component in self.error_counts:
                    self.error_counts[component] = 0
                
                return result
                
            except Exception as e:
                last_error = e
                self.error_counts[component] = self.error_counts.get(component, 0) + 1
                
                error_msg = f"Attempt {attempt + 1}/{max_retries} failed: {str(e)}"
                print(f"❌ {component}: {error_msg}")
                
                # Log error to database
                await self.log_error(component, error_msg, {
                    'attempt': attempt + 1,
                    'max_retries': max_retries,
                    'function': func.__name__,
                    'error_type': type(e).__name__,
                    'traceback': traceback.format_exc()
                })
                
                # Wait before retry (exponential backoff)
                if attempt < max_retries - 1:
                    wait_time = min(2 ** attempt, 30)  # Max 30 seconds
                    await asyncio.sleep(wait_time)
        
        # All retries failed
        await self.handle_critical_error(component, last_error)
        return None
    
    async def safe_api_call(self, 
                           api_func: Callable, 
                           component: str,
                           use_key_rotation: bool = True,
                           *args, 
                           **kwargs) -> Optional[Any]:
        """Safely execute API call with key rotation"""
        
        if not use_key_rotation:
            return await self.safe_execute(api_func, component, *args, **kwargs)
        
        # Try with different API keys
        for attempt in range(config.MAX_RETRIES):
            # Get next available key
            api_key = config.api_keys.get_working_key(prefer_gemini=True)
            
            if not api_key:
                await self.log_error(component, "No API keys available", {
                    'failed_keys_count': len(self.failed_keys),
                    'total_keys': len(config.api_keys.gemini_keys) + len(config.api_keys.lite_keys)
                })
                return None
            
            # Skip if key already failed recently
            if api_key in self.failed_keys:
                continue
            
            try:
                # Execute API call with this key
                if asyncio.iscoroutinefunction(api_func):
                    result = await api_func(api_key, *args, **kwargs)
                else:
                    result = api_func(api_key, *args, **kwargs)
                
                # Success - remove from failed keys if it was there
                self.failed_keys.discard(api_key)
                return result
                
            except Exception as e:
                error_msg = f"API key {api_key[:10]}... failed: {str(e)}"
                print(f"❌ {component}: {error_msg}")
                
                # Mark key as failed
                self.failed_keys.add(api_key)
                
                # Log the error
                await self.log_error(component, error_msg, {
                    'api_key_prefix': api_key[:10],
                    'error_type': type(e).__name__,
                    'attempt': attempt + 1
                })
                
                # Check if it's a rate limit or quota error
                if self.is_rate_limit_error(e):
                    print(f"⏰ {component}: Rate limit hit, waiting...")
                    await asyncio.sleep(60)  # Wait 1 minute for rate limits
                
                # Continue to next key
                continue
        
        # All keys failed
        await self.handle_critical_error(component, Exception("All API keys failed"))
        return None
    
    def is_rate_limit_error(self, error: Exception) -> bool:
        """Check if error is due to rate limiting"""
        error_str = str(error).lower()
        rate_limit_indicators = [
            'rate limit',
            'quota exceeded',
            'too many requests',
            '429',
            'resource_exhausted'
        ]
        return any(indicator in error_str for indicator in rate_limit_indicators)
    
    def is_api_key_error(self, error: Exception) -> bool:
        """Check if error is due to invalid API key"""
        error_str = str(error).lower()
        key_error_indicators = [
            'invalid api key',
            'unauthorized',
            'authentication failed',
            '401',
            '403'
        ]
        return any(indicator in error_str for indicator in key_error_indicators)
    
    async def handle_critical_error(self, component: str, error: Exception):
        """Handle critical errors that prevent system operation"""
        error_msg = f"Critical error in {component}: {str(error)}"
        print(f"🚨 CRITICAL: {error_msg}")
        
        await self.log_error(component, error_msg, {
            'error_type': type(error).__name__,
            'traceback': traceback.format_exc(),
            'severity': 'CRITICAL'
        })
        
        # Check if we should pause the system
        if self.error_counts.get(component, 0) > 10:
            print(f"🛑 {component}: Too many errors, pausing for 5 minutes...")
            await asyncio.sleep(300)  # Pause for 5 minutes
    
    async def log_error(self, component: str, message: str, details: Dict = None):
        """Log error to database and console"""
        try:
            await supabase_manager.log_system_error(component, message, details)
        except Exception as e:
            # Fallback to console if database logging fails
            print(f"❌ Failed to log error to database: {e}")
            print(f"❌ Original error - {component}: {message}")
    
    async def reset_failed_keys(self):
        """Reset failed keys periodically (every hour)"""
        while True:
            await asyncio.sleep(3600)  # Wait 1 hour
            
            if self.failed_keys:
                print(f"🔄 Resetting {len(self.failed_keys)} failed API keys")
                self.failed_keys.clear()
    
    def get_system_health(self) -> Dict:
        """Get current system health status"""
        total_keys = len(config.api_keys.gemini_keys) + len(config.api_keys.lite_keys)
        working_keys = total_keys - len(self.failed_keys)
        
        return {
            'total_api_keys': total_keys,
            'working_keys': working_keys,
            'failed_keys': len(self.failed_keys),
            'error_counts': self.error_counts.copy(),
            'health_percentage': (working_keys / total_keys * 100) if total_keys > 0 else 0
        }

class RetryableError(Exception):
    """Exception that should trigger a retry"""
    pass

class CriticalError(Exception):
    """Exception that indicates a critical system failure"""
    pass

# Decorator for automatic error handling
def handle_errors(component: str, max_retries: int = None):
    """Decorator to automatically handle errors in functions"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            return await error_handler.safe_execute(
                func, component, *args, max_retries=max_retries, **kwargs
            )
        return wrapper
    return decorator

# Global error handler
error_handler = ErrorHandler()
