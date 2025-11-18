import requests
import asyncio
import aiohttp
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from config import config
from supabase import create_client

class BinanceClient:
    """Enhanced client for multi-source crypto data with Supabase 4H storage"""
    
    def __init__(self):
        # Supabase for 4H candles storage (use Railway environment variables)
        self.supabase_url = os.getenv('supabase_4h-candle-url', "https://smylsjwodvlvqybemshk.supabase.co")
        self.supabase_key = os.getenv('supabase_4h-candle-key', "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNteWxzandvZHZsdnF5YmVtc2hrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjMzNjk5MjAsImV4cCI6MjA3ODk0NTkyMH0.iKJ0NbFeGgGzVKQIBTntfx9TNznej3ffrL5-i1TUbbE")
        
        # Initialize Supabase client
        try:
            self.supabase = create_client(self.supabase_url, self.supabase_key)
            print("✅ Supabase client initialized for 4H candles")
        except Exception as e:
            print(f"❌ Supabase initialization error: {e}")
            self.supabase = None
        
        self.session = None
        self.last_4h_update = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def get_klines(self, symbol: str, interval: str, limit: int) -> List[Dict]:
        """Fetch klines - 4H from Supabase, others from Coinbase"""
        
        if interval == '4h':
            # Get 4H candles from Supabase
            return await self.get_4h_from_supabase(limit)
        else:
            # Get other timeframes from Coinbase
            return await self.get_coinbase_candles(interval, limit)
    
    async def get_4h_from_supabase(self, limit: int) -> List[Dict]:
        """Fetch 4H candles from Supabase storage"""
        if not self.supabase:
            print("❌ Supabase not available, trying Coinbase for 4H...")
            return await self.get_coinbase_candles('4h', limit)
        
        try:
            print(f"📊 Fetching {limit} 4H candles from Supabase...")
            
            result = self.supabase.table('candles').select('*').eq(
                'timeframe', '4h'
            ).eq(
                'symbol', 'BTCUSD'
            ).order('timestamp', desc=True).limit(limit).execute()
            
            if result.data and len(result.data) > 0:
                # Convert to our format and reverse (oldest first)
                candles = []
                for row in reversed(result.data):
                    candle = {
                        'timestamp': row['timestamp'],
                        'open': float(row['open']),
                        'high': float(row['high']),
                        'low': float(row['low']),
                        'close': float(row['close']),
                        'volume': float(row['volume'])
                    }
                    candles.append(candle)
                
                print(f"✅ Got {len(candles)} 4H candles from Supabase")
                
                # Check if we need to update with new 4H candle
                await self.check_and_update_4h_candles()
                
                return candles
            else:
                print("❌ No 4H candles found in Supabase, trying Coinbase...")
                return await self.get_coinbase_candles('4h', limit)
                
        except Exception as e:
            print(f"❌ Supabase 4H fetch error: {e}, trying Coinbase...")
            return await self.get_coinbase_candles('4h', limit)
                
        except Exception as e:
            print(f"❌ Supabase 4H fetch error: {e}")
            return []
    
    async def check_and_update_4h_candles(self):
        """Check if we need to add new 4H candle every 4 hours"""
        try:
            from datetime import timezone
            current_time = datetime.now(timezone.utc)
            
            # Check if 4 hours have passed since last update
            if self.last_4h_update:
                time_diff = current_time - self.last_4h_update
                if time_diff.total_seconds() < 14400:  # 4 hours = 14400 seconds
                    return
            
            # Get latest 4H candle from Supabase
            result = self.supabase.table('candles').select('timestamp').eq(
                'timeframe', '4h'
            ).order('timestamp', desc=True).limit(1).execute()
            
            if result.data:
                latest_timestamp_str = result.data[0]['timestamp']
                # Handle both formats: with and without timezone
                if latest_timestamp_str.endswith('Z'):
                    latest_timestamp = datetime.fromisoformat(latest_timestamp_str.replace('Z', '+00:00'))
                elif '+' in latest_timestamp_str or latest_timestamp_str.endswith('+00:00'):
                    latest_timestamp = datetime.fromisoformat(latest_timestamp_str)
                else:
                    # Assume UTC if no timezone info
                    latest_timestamp = datetime.fromisoformat(latest_timestamp_str).replace(tzinfo=timezone.utc)
                
                # Check if we need a new 4H candle (every 4 hours: 00:00, 04:00, 08:00, etc.)
                current_4h_boundary = current_time.replace(
                    hour=(current_time.hour // 4) * 4, 
                    minute=0, 
                    second=0, 
                    microsecond=0
                )
                
                if latest_timestamp < current_4h_boundary:
                    print("🔄 Time for new 4H candle update...")
                    await self.add_new_4h_candle()
                    self.last_4h_update = current_time
            
        except Exception as e:
            print(f"❌ 4H update check error: {e}")
            # Don't fail the whole system for update check errors
    
    async def add_new_4h_candle(self):
        """Add new 4H candle from Coinbase to Supabase"""
        try:
            print("📊 Fetching latest 4H candle from Coinbase...")
            
            # Get latest 4H candle from Coinbase
            candles = await self.get_coinbase_candles('4h', 1)
            
            if candles:
                new_candle = candles[0]
                
                # Format for Supabase
                supabase_candle = {
                    'timestamp': new_candle['timestamp'],
                    'symbol': 'BTCUSD',
                    'timeframe': '4h',
                    'open': new_candle['open'],
                    'high': new_candle['high'],
                    'low': new_candle['low'],
                    'close': new_candle['close'],
                    'volume': new_candle['volume']
                }
                
                # Insert into Supabase (upsert to handle duplicates)
                result = self.supabase.table('candles').upsert(supabase_candle).execute()
                
                if result.data:
                    print(f"✅ Added new 4H candle: ${new_candle['close']:.2f}")
                else:
                    print("❌ Failed to add new 4H candle")
            
        except Exception as e:
            print(f"❌ New 4H candle error: {e}")
    
    async def get_coinbase_candles(self, interval: str, limit: int) -> List[Dict]:
        """Fetch candles from Coinbase Pro API"""
        # Coinbase granularity mapping
        granularity_map = {
            '1m': 60,
            '15m': 900, 
            '1h': 3600,
            '4h': 14400
        }
        
        granularity = granularity_map.get(interval, 3600)
        url = f"https://api.exchange.coinbase.com/products/BTC-USD/candles"
        params = {
            'granularity': granularity
        }
        
        try:
            print(f"Fetching {interval} candles from Coinbase...")
            if self.session:
                async with self.session.get(url, params=params, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        candles = self.format_coinbase_candles(data[:limit])
                        print(f"✅ Got {len(candles)} {interval} candles from Coinbase")
                        return candles
            else:
                response = requests.get(url, params=params, timeout=30)
                if response.status_code == 200:
                    candles = self.format_coinbase_candles(response.json()[:limit])
                    print(f"✅ Got {len(candles)} {interval} candles from Coinbase")
                    return candles
        except Exception as e:
            print(f"Coinbase API error: {e}")
        
        print(f"❌ No {interval} data available")
        return []
    
    def format_coinbase_candles(self, raw_data: List) -> List[Dict]:
        """Format Coinbase candle data to our format"""
        candles = []
        for candle in raw_data:
            # Coinbase format: [timestamp, low, high, open, close, volume]
            formatted = {
                'timestamp': datetime.fromtimestamp(candle[0]).isoformat(),
                'open': float(candle[3]),
                'high': float(candle[2]), 
                'low': float(candle[1]),
                'close': float(candle[4]),
                'volume': float(candle[5])
            }
            candles.append(formatted)
        
        # Sort by timestamp (oldest first)
        candles.sort(key=lambda x: x['timestamp'])
        return candles
    
    async def get_current_price(self, symbol: str = 'BTCUSDT') -> float:
        """Get current Bitcoin price from real sources only"""
        
        # Try Coinbase first
        try:
            url = "https://api.exchange.coinbase.com/products/BTC-USD/ticker"
            if self.session:
                async with self.session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        price = float(data['price'])
                        print(f"✅ Current BTC price from Coinbase: ${price:.2f}")
                        return price
            else:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    price = float(response.json()['price'])
                    print(f"✅ Current BTC price from Coinbase: ${price:.2f}")
                    return price
        except Exception as e:
            print(f"Coinbase price error: {e}")
        
        # Try CoinGecko as backup
        try:
            url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
            if self.session:
                async with self.session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        price = float(data['bitcoin']['usd'])
                        print(f"✅ Current BTC price from CoinGecko: ${price:.2f}")
                        return price
            else:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    price = float(response.json()['bitcoin']['usd'])
                    print(f"✅ Current BTC price from CoinGecko: ${price:.2f}")
                    return price
        except Exception as e:
            print(f"CoinGecko price error: {e}")
        
        # No real price available
        print(f"❌ No real Bitcoin price available - system will wait")
        return 0.0

class MarketDataFetcher:
    """High-level market data fetcher for Strategic Pro and Flash"""
    
    def __init__(self):
        self.binance = BinanceClient()
    
    async def fetch_strategic_data(self) -> Dict:
        """Fetch data for Strategic Pro (every hour)"""
        async with BinanceClient() as client:
            tasks = [
                client.get_klines('BTCUSDT', '4h', config.REQUIRED_4H_CANDLES),    # From Supabase
                client.get_klines('BTCUSDT', '1h', config.REQUIRED_1H_CANDLES),    # From Coinbase
                client.get_klines('BTCUSDT', '15m', config.REQUIRED_15M_CANDLES)   # From Coinbase
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            return {
                '4h': results[0] if not isinstance(results[0], Exception) else [],
                '1h': results[1] if not isinstance(results[1], Exception) else [],
                '15m': results[2] if not isinstance(results[2], Exception) else []
            }
    
    async def fetch_flash_data(self) -> Dict:
        """Fetch data for Flash (every minute)"""
        async with BinanceClient() as client:
            tasks = [
                client.get_klines('BTCUSDT', '1h', config.FLASH_1H_CANDLES),
                client.get_klines('BTCUSDT', '15m', config.FLASH_15M_CANDLES),
                client.get_klines('BTCUSDT', '1m', config.FLASH_1M_CANDLES),
                client.get_current_price('BTCUSDT')
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            return {
                '1h': results[0] if not isinstance(results[0], Exception) else [],
                '15m': results[1] if not isinstance(results[1], Exception) else [],
                '1m': results[2] if not isinstance(results[2], Exception) else [],
                'current_price': results[3] if not isinstance(results[3], Exception) else 0.0
            }
    
    def format_candles_for_prompt(self, candles: List[Dict], limit: Optional[int] = None) -> str:
        """Format candles for AI prompt"""
        if not candles:
            return "No data available"
        
        if limit:
            candles = candles[-limit:]
        
        formatted = []
        for candle in candles:
            formatted.append(
                f"Time: {candle['timestamp']}, "
                f"O: {candle['open']:.2f}, "
                f"H: {candle['high']:.2f}, "
                f"L: {candle['low']:.2f}, "
                f"C: {candle['close']:.2f}, "
                f"V: {candle['volume']:.0f}"
            )
        
        return "\n".join(formatted)

# Global market data fetcher
market_data = MarketDataFetcher()
