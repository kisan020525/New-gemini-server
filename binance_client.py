import requests
import asyncio
import aiohttp
from datetime import datetime
from typing import List, Dict, Optional
from config import config

class BinanceClient:
    """Binance API client for fetching multi-timeframe candle data"""
    
    def __init__(self):
        self.base_url = "https://api.binance.com/api/v3"
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def get_klines(self, symbol: str, interval: str, limit: int) -> List[Dict]:
        """Fetch klines from Binance API"""
        url = f"{self.base_url}/klines"
        params = {
            'symbol': symbol,
            'interval': interval,
            'limit': limit
        }
        
        try:
            if self.session:
                async with self.session.get(url, params=params, timeout=config.API_TIMEOUT) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self.format_candles(data)
                    else:
                        raise Exception(f"Binance API error: {response.status}")
            else:
                # Fallback to requests for sync calls
                response = requests.get(url, params=params, timeout=config.API_TIMEOUT)
                if response.status_code == 200:
                    return self.format_candles(response.json())
                else:
                    raise Exception(f"Binance API error: {response.status_code}")
        except Exception as e:
            print(f"Error fetching {interval} candles: {e}")
            return []
    
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
        """Get current Bitcoin price"""
        url = f"{self.base_url}/ticker/price"
        params = {'symbol': symbol}
        
        try:
            if self.session:
                async with self.session.get(url, params=params, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        return float(data['price'])
            else:
                response = requests.get(url, params=params, timeout=10)
                if response.status_code == 200:
                    return float(response.json()['price'])
        except Exception as e:
            print(f"Error fetching current price: {e}")
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
