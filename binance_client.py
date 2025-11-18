import requests
import asyncio
import aiohttp
from datetime import datetime
from typing import List, Dict, Optional
from config import config

class BinanceClient:
    """Binance API client for fetching multi-timeframe candle data"""
    
    def __init__(self):
        # Alternative crypto data sources (no region blocking)
        self.data_sources = [
            {
                'name': 'coinbase',
                'klines_url': 'https://api.exchange.coinbase.com/products/BTC-USD/candles',
                'price_url': 'https://api.exchange.coinbase.com/products/BTC-USD/ticker'
            },
            {
                'name': 'kraken',
                'klines_url': 'https://api.kraken.com/0/public/OHLC',
                'price_url': 'https://api.kraken.com/0/public/Ticker'
            },
            {
                'name': 'coingecko',
                'price_url': 'https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd'
            }
        ]
        self.current_source = 0
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
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
            if self.session:
                async with self.session.get(url, params=params, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self.format_coinbase_candles(data[:limit])
            else:
                response = requests.get(url, params=params, timeout=30)
                if response.status_code == 200:
                    return self.format_coinbase_candles(response.json()[:limit])
        except Exception as e:
            print(f"Coinbase API error: {e}")
        
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
    async def get_klines(self, symbol: str, interval: str, limit: int) -> List[Dict]:
        """Fetch klines from real sources only (Coinbase)"""
        
        # Try Coinbase (real data only)
        print(f"Fetching {interval} candles from Coinbase...")
        candles = await self.get_coinbase_candles(interval, limit)
        
        if candles:
            print(f"✅ Got {len(candles)} real {interval} candles from Coinbase")
            return candles
        
        # No synthetic data - return empty if no real data available
        print(f"❌ No real {interval} data available - system will wait")
        return []
    
    def generate_synthetic_candles(self, interval: str, limit: int) -> List[Dict]:
        """Generate synthetic Bitcoin candles for testing"""
        import random
        from datetime import timedelta
        
        # Interval to minutes mapping
        interval_minutes = {
            '1m': 1,
            '15m': 15, 
            '1h': 60,
            '4h': 240
        }
        
        minutes = interval_minutes.get(interval, 60)
        candles = []
        
        # Start with realistic Bitcoin price
        base_price = 94000 + random.uniform(-2000, 2000)
        current_time = datetime.now()
        
        for i in range(limit):
            # Generate realistic price movement
            price_change = random.uniform(-0.02, 0.02)  # ±2% change
            new_price = base_price * (1 + price_change)
            
            # Generate OHLCV
            high = new_price * (1 + random.uniform(0, 0.01))
            low = new_price * (1 - random.uniform(0, 0.01))
            open_price = base_price
            close_price = new_price
            volume = random.uniform(100, 1000)
            
            candle = {
                'timestamp': (current_time - timedelta(minutes=minutes * (limit - i - 1))).isoformat(),
                'open': round(open_price, 2),
                'high': round(high, 2),
                'low': round(low, 2), 
                'close': round(close_price, 2),
                'volume': round(volume, 2)
            }
            
            candles.append(candle)
            base_price = new_price
        
        print(f"✅ Generated {len(candles)} synthetic {interval} candles")
        return candles
    
    def format_candles(self, raw_data: List) -> List[Dict]:
        """Format raw Binance candle data"""
        candles = []
        for candle in raw_data:
            formatted = {
                'timestamp': datetime.fromtimestamp(candle[0] / 1000).isoformat(),
                'open': float(candle[1]),
                'high': float(candle[2]),
                'low': float(candle[3]),
                'close': float(candle[4]),
                'volume': float(candle[5])
            }
            candles.append(formatted)
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
        
        # No synthetic data - return 0 if no real price available
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
                client.get_klines('BTCUSDT', '4h', config.REQUIRED_4H_CANDLES),
                client.get_klines('BTCUSDT', '1h', config.REQUIRED_1H_CANDLES),
                client.get_klines('BTCUSDT', '15m', config.REQUIRED_15M_CANDLES)
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
