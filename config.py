import os
import random
from typing import List, Optional

class APIKeyManager:
    """Manages API key rotation with failover for Gemini models"""
    
    def __init__(self):
        # Load all 15 main Gemini API keys
        self.gemini_keys = []
        for i in range(1, 16):
            key = os.getenv(f'GEMINI_API_KEY_{i}')
            if key:
                self.gemini_keys.append(key)
        
        # Load 2 Lite API keys as backup
        self.lite_keys = []
        for i in range(1, 3):
            key = os.getenv(f'GEMINI_LITE_API_KEY_{i}')
            if key:
                self.lite_keys.append(key)
        
        # Current key indices
        self.current_gemini_index = 0
        self.current_lite_index = 0
        
        print(f"Loaded {len(self.gemini_keys)} Gemini keys and {len(self.lite_keys)} Lite keys")
    
    def get_gemini_key(self) -> Optional[str]:
        """Get next available Gemini API key"""
        if not self.gemini_keys:
            return None
        
        key = self.gemini_keys[self.current_gemini_index]
        self.current_gemini_index = (self.current_gemini_index + 1) % len(self.gemini_keys)
        return key
    
    def get_lite_key(self) -> Optional[str]:
        """Get next available Lite API key"""
        if not self.lite_keys:
            return None
        
        key = self.lite_keys[self.current_lite_index]
        self.current_lite_index = (self.current_lite_index + 1) % len(self.lite_keys)
        return key
    
    def get_working_key(self, prefer_gemini=True) -> Optional[str]:
        """Get any working key, preferring Gemini over Lite"""
        if prefer_gemini and self.gemini_keys:
            return self.get_gemini_key()
        elif self.lite_keys:
            return self.get_lite_key()
        elif self.gemini_keys:
            return self.get_gemini_key()
        return None

# Configuration settings
class Config:
    # API Key Manager
    api_keys = APIKeyManager()
    
    # Gemini Models
    GEMINI_PRO_MODEL = "gemini-2.5-pro"
    GEMINI_FLASH_MODEL = "gemini-2.5-flash-preview-09-2025"
    
    # Supabase Configuration
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_KEY = os.getenv('SUPABASE_KEY')
    TRADES_SUPABASE_URL = os.getenv('TRADES_SUPABASE_URL')
    TRADES_SUPABASE_KEY = os.getenv('TRADES_SUPABASE_KEY')
    
    # Trading Configuration
    TRADING_ENABLED = True
    PAPER_TRADING = True
    DEFAULT_TRADE_AMOUNT = 100
    MAX_POSITION_SIZE = 1000
    
    # Data Configuration (Reduced for prompt optimization)
    REQUIRED_4H_CANDLES = 50   # Reduced from 100
    REQUIRED_1H_CANDLES = 100  # Reduced from 168
    REQUIRED_15M_CANDLES = 50  # Reduced from 96
    FLASH_1H_CANDLES = 24
    FLASH_15M_CANDLES = 48
    FLASH_1M_CANDLES = 100
    
    # Timing Configuration
    STRATEGIC_INTERVAL = 3600  # 1 hour in seconds
    FLASH_INTERVAL = 60        # 1 minute in seconds
    
    # API Configuration
    MAX_RETRIES = 3
    API_TIMEOUT = 30
    
    # Logging
    LOG_LEVEL = "INFO"

# Global config instance
config = Config()
