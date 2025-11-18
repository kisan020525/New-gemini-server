from supabase import create_client, Client
from datetime import datetime, timezone
from typing import Dict, List, Optional
from config import config

class SupabaseManager:
    """Manages Supabase connections for market data and trades"""
    
    def __init__(self):
        # Market data client
        self.market_client: Optional[Client] = None
        # Trades client (can be same or different database)
        self.trades_client: Optional[Client] = None
        
        self.initialize_clients()
    
    def initialize_clients(self):
        """Initialize Supabase clients"""
        try:
            # Market data client
            if config.SUPABASE_URL and config.SUPABASE_KEY:
                self.market_client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
                print("✅ Market data Supabase client initialized")
            
            # Trades client
            if config.TRADES_SUPABASE_URL and config.TRADES_SUPABASE_KEY:
                self.trades_client = create_client(config.TRADES_SUPABASE_URL, config.TRADES_SUPABASE_KEY)
                print("✅ Trades Supabase client initialized")
            elif self.market_client:
                # Use same client for trades if separate not provided
                self.trades_client = self.market_client
                print("✅ Using market client for trades")
                
        except Exception as e:
            print(f"❌ Supabase initialization error: {e}")
    
    async def store_candles(self, candles: List[Dict], timeframe: str):
        """Store candle data in market database"""
        if not self.market_client or not candles:
            return False
        
        try:
            # Prepare candle data for insertion
            candle_records = []
            for candle in candles:
                record = {
                    'timestamp': candle['timestamp'],
                    'symbol': 'BTCUSD',
                    'timeframe': timeframe,
                    'open': candle['open'],
                    'high': candle['high'],
                    'low': candle['low'],
                    'close': candle['close'],
                    'volume': candle['volume']
                }
                candle_records.append(record)
            
            # Upsert candles (insert or update if exists)
            result = self.market_client.table('candles').upsert(
                candle_records,
                on_conflict='timestamp,symbol,timeframe'
            ).execute()
            
            print(f"📊 Stored {len(candle_records)} {timeframe} candles")
            return True
            
        except Exception as e:
            print(f"❌ Error storing {timeframe} candles: {e}")
            return False
    
    async def get_latest_candles(self, timeframe: str, limit: int = 100) -> List[Dict]:
        """Get latest candles from market database"""
        if not self.market_client:
            return []
        
        try:
            result = self.market_client.table('candles').select('*').eq(
                'timeframe', timeframe
            ).eq(
                'symbol', 'BTCUSD'
            ).order('timestamp', desc=True).limit(limit).execute()
            
            return result.data if result.data else []
            
        except Exception as e:
            print(f"❌ Error fetching {timeframe} candles: {e}")
            return []
    
    async def log_strategic_analysis(self, directive: Dict):
        """Log Strategic Pro analysis"""
        if not self.trades_client:
            return False
        
        try:
            log_record = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'component': 'strategic_pro',
                'level': 'INFO',
                'message': f"Strategic analysis: {directive['bias']} (Confidence: {directive['confidence']}/10)",
                'error_details': directive
            }
            
            result = self.trades_client.table('system_logs').insert(log_record).execute()
            return True
            
        except Exception as e:
            print(f"❌ Error logging strategic analysis: {e}")
            return False
    
    async def log_flash_decision(self, decision: Dict):
        """Log Flash tactical decision"""
        if not self.trades_client:
            return False
        
        try:
            log_record = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'component': 'flash',
                'level': 'INFO',
                'message': f"Flash decision: {decision['action']} (Confidence: {decision['confidence']}/10)",
                'error_details': decision
            }
            
            result = self.trades_client.table('system_logs').insert(log_record).execute()
            return True
            
        except Exception as e:
            print(f"❌ Error logging flash decision: {e}")
            return False
    
    async def log_trade_execution(self, trade_data: Dict):
        """Log actual trade execution"""
        if not self.trades_client:
            return False
        
        try:
            trade_record = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'action': trade_data['action'],
                'symbol': 'BTCUSD',
                'price': trade_data['entry_price'],
                'quantity': trade_data.get('quantity', 0.001),
                'confidence_score': trade_data['confidence'],
                'strategic_analysis': trade_data.get('strategic_reasoning', ''),
                'flash_signal': trade_data['reasoning'],
                'status': 'PENDING',
                'profit_loss': None
            }
            
            result = self.trades_client.table('trades').insert(trade_record).execute()
            
            if result.data:
                trade_id = result.data[0]['id']
                print(f"💰 Trade logged with ID: {trade_id}")
                return trade_id
            
            return True
            
        except Exception as e:
            print(f"❌ Error logging trade: {e}")
            return False
    
    async def update_portfolio(self, btc_balance: float, usd_balance: float, total_value: float):
        """Update portfolio status"""
        if not self.trades_client:
            return False
        
        try:
            portfolio_record = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'btc_balance': btc_balance,
                'usd_balance': usd_balance,
                'total_value_usd': total_value
            }
            
            result = self.trades_client.table('portfolio').insert(portfolio_record).execute()
            return True
            
        except Exception as e:
            print(f"❌ Error updating portfolio: {e}")
            return False
    
    async def get_portfolio_status(self) -> Dict:
        """Get current portfolio status"""
        if not self.trades_client:
            return {'btc_balance': 0.0, 'usd_balance': 10000.0, 'total_value': 10000.0}
        
        try:
            result = self.trades_client.table('portfolio').select('*').order(
                'timestamp', desc=True
            ).limit(1).execute()
            
            if result.data:
                return result.data[0]
            else:
                # Default portfolio
                return {'btc_balance': 0.0, 'usd_balance': 10000.0, 'total_value': 10000.0}
                
        except Exception as e:
            print(f"❌ Error getting portfolio: {e}")
            return {'btc_balance': 0.0, 'usd_balance': 10000.0, 'total_value': 10000.0}
    
    async def log_system_error(self, component: str, error_message: str, error_details: Dict = None):
        """Log system errors"""
        if not self.trades_client:
            return False
        
        try:
            error_record = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'component': component,
                'level': 'ERROR',
                'message': error_message,
                'error_details': error_details or {}
            }
            
            result = self.trades_client.table('system_logs').insert(error_record).execute()
            return True
            
        except Exception as e:
            print(f"❌ Error logging system error: {e}")
            return False

# Global Supabase manager
supabase_manager = SupabaseManager()
