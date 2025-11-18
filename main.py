"""
Gemini Trading Bot - Strategic Pro + Flash System
Updated: 2025-11-18 12:47 - Force Railway Deploy
"""

import asyncio
import signal
import sys
from datetime import datetime, timezone
from typing import Dict, Optional

from config import config
from strategic_pro import strategic_pro
from flash import flash
from binance_client import market_data
from supabase_client import supabase_manager
from error_handler import error_handler

class GeminiTradingBot:
    """Main orchestration system for Gemini Trading Bot"""
    
    def __init__(self):
        self.running = False
        self.strategic_task = None
        self.flash_task = None
        self.error_reset_task = None
        self.current_directive = None
        
        # System statistics
        self.stats = {
            'start_time': None,
            'strategic_analyses': 0,
            'flash_decisions': 0,
            'trades_executed': 0,
            'errors': 0,
            'version': '2025-11-18_12:40'  # Force redeploy timestamp
        }
    
    async def start(self):
        """Start the trading bot system"""
        print("🚀 Starting Gemini Trading Bot...")
        print(f"📊 Strategic Pro: {config.GEMINI_PRO_MODEL}")
        print(f"⚡ Flash: {config.GEMINI_FLASH_MODEL}")
        
        self.running = True
        self.stats['start_time'] = datetime.now(timezone.utc)
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        # Start background tasks
        self.strategic_task = asyncio.create_task(self.strategic_loop())
        self.flash_task = asyncio.create_task(self.flash_loop())
        self.error_reset_task = asyncio.create_task(error_handler.reset_failed_keys())
        
        # Log system startup
        await supabase_manager.log_system_error(
            'main', 
            'Gemini Trading Bot started successfully', 
            {'config': self.get_system_info()}
        )
        
        print("✅ All systems operational!")
        
        # Keep running until stopped
        try:
            await asyncio.gather(
                self.strategic_task,
                self.flash_task,
                self.error_reset_task
            )
        except asyncio.CancelledError:
            print("🛑 System shutdown initiated...")
    
    async def strategic_loop(self):
        """Strategic Pro analysis loop (every hour)"""
        print("🧠 Strategic Pro loop started")
        
        while self.running:
            try:
                print(f"\n⏰ {datetime.now(timezone.utc).strftime('%H:%M:%S')} - Strategic Analysis Starting...")
                
                # Perform strategic analysis
                directive = await error_handler.safe_execute(
                    strategic_pro.analyze_market,
                    'strategic_pro'
                )
                
                if directive:
                    self.current_directive = directive
                    self.stats['strategic_analyses'] += 1
                    
                    # Log to database
                    await supabase_manager.log_strategic_analysis(directive)
                    
                    print(f"📋 Strategic Directive: {directive['bias']} (Confidence: {directive['confidence']}/10)")
                    print(f"🎯 Entry Zones: {len(directive.get('entry_zones', []))}")
                    print(f"⏱️  Valid for: {directive.get('valid_for_hours', 4)} hours")
                else:
                    print("❌ Strategic analysis failed")
                    self.stats['errors'] += 1
                
                # Wait for next hour (or until shutdown)
                await self.wait_with_shutdown_check(config.STRATEGIC_INTERVAL)
                
            except Exception as e:
                await error_handler.log_error('strategic_loop', f"Strategic loop error: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retry
    
    async def flash_loop(self):
        """Flash tactical loop (every minute)"""
        print("⚡ Flash loop started")
        
        while self.running:
            try:
                current_time = datetime.now(timezone.utc)
                
                # Only execute if we have a strategic directive
                if self.current_directive:
                    # Check if directive is still valid
                    directive = strategic_pro.get_current_directive()
                    
                    if directive:
                        print(f"\n⚡ {current_time.strftime('%H:%M:%S')} - Flash Analysis...")
                        
                        # Make tactical decision
                        decision = await error_handler.safe_execute(
                            flash.execute_tactical_decision,
                            'flash',
                            directive
                        )
                        
                        if decision:
                            self.stats['flash_decisions'] += 1
                            
                            # Log decision
                            await supabase_manager.log_flash_decision(decision)
                            
                            # Execute trade if decision is to enter
                            if decision['action'] in ['ENTER_LONG', 'ENTER_SHORT']:
                                await self.execute_trade(decision, directive)
                            
                            print(f"⚡ Flash: {decision['action']} (Confidence: {decision['confidence']}/10)")
                        else:
                            print("❌ Flash decision failed")
                            self.stats['errors'] += 1
                    else:
                        print("💤 No valid strategic directive")
                else:
                    print("⏳ Waiting for Strategic Pro analysis...")
                
                # Wait for next minute
                await self.wait_with_shutdown_check(config.FLASH_INTERVAL)
                
            except Exception as e:
                await error_handler.log_error('flash_loop', f"Flash loop error: {e}")
                await asyncio.sleep(30)  # Wait 30 seconds before retry
    
    async def execute_trade(self, decision: Dict, directive: Dict):
        """Execute actual trade based on Flash decision"""
        try:
            print(f"💰 Executing trade: {decision['action']} at ${decision['entry_price']:.2f}")
            
            # Get current portfolio
            portfolio = await supabase_manager.get_portfolio_status()
            
            # Calculate position size (simple example)
            if decision['action'] == 'ENTER_LONG':
                # Buy Bitcoin with USD
                usd_to_spend = min(config.DEFAULT_TRADE_AMOUNT, portfolio.get('usd_balance', 0))
                btc_quantity = usd_to_spend / decision['entry_price']
                
                # Update portfolio (paper trading)
                new_btc = portfolio.get('btc_balance', 0) + btc_quantity
                new_usd = portfolio.get('usd_balance', 0) - usd_to_spend
                
            elif decision['action'] == 'ENTER_SHORT':
                # Sell Bitcoin for USD (if we have any)
                btc_to_sell = min(0.001, portfolio.get('btc_balance', 0))  # Sell small amount
                usd_received = btc_to_sell * decision['entry_price']
                
                # Update portfolio (paper trading)
                new_btc = portfolio.get('btc_balance', 0) - btc_to_sell
                new_usd = portfolio.get('usd_balance', 0) + usd_received
            
            # Log trade execution
            trade_data = {
                **decision,
                'strategic_reasoning': directive.get('reasoning', ''),
                'quantity': btc_quantity if decision['action'] == 'ENTER_LONG' else btc_to_sell
            }
            
            trade_id = await supabase_manager.log_trade_execution(trade_data)
            
            # Update portfolio
            total_value = new_btc * decision['entry_price'] + new_usd
            await supabase_manager.update_portfolio(new_btc, new_usd, total_value)
            
            self.stats['trades_executed'] += 1
            print(f"✅ Trade executed successfully (ID: {trade_id})")
            
        except Exception as e:
            await error_handler.log_error('trade_execution', f"Trade execution failed: {e}")
    
    async def wait_with_shutdown_check(self, seconds: int):
        """Wait for specified seconds while checking for shutdown"""
        for _ in range(seconds):
            if not self.running:
                break
            await asyncio.sleep(1)
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print(f"\n🛑 Received signal {signum}, shutting down gracefully...")
        self.running = False
    
    async def shutdown(self):
        """Graceful shutdown"""
        print("🛑 Shutting down Gemini Trading Bot...")
        self.running = False
        
        # Cancel all tasks
        if self.strategic_task:
            self.strategic_task.cancel()
        if self.flash_task:
            self.flash_task.cancel()
        if self.error_reset_task:
            self.error_reset_task.cancel()
        
        # Log shutdown
        await supabase_manager.log_system_error(
            'main', 
            'Gemini Trading Bot shutdown', 
            {'stats': self.stats, 'health': error_handler.get_system_health()}
        )
        
        print("✅ Shutdown complete")
    
    def get_system_info(self) -> Dict:
        """Get current system information"""
        return {
            'gemini_pro_model': config.GEMINI_PRO_MODEL,
            'gemini_flash_model': config.GEMINI_FLASH_MODEL,
            'api_keys_available': len(config.api_keys.gemini_keys) + len(config.api_keys.lite_keys),
            'trading_enabled': config.TRADING_ENABLED,
            'paper_trading': config.PAPER_TRADING,
            'strategic_interval': config.STRATEGIC_INTERVAL,
            'flash_interval': config.FLASH_INTERVAL
        }
    
    def print_status(self):
        """Print current system status"""
        uptime = datetime.now(timezone.utc) - self.stats['start_time'] if self.stats['start_time'] else None
        health = error_handler.get_system_health()
        
        print(f"\n📊 SYSTEM STATUS")
        print(f"⏱️  Uptime: {uptime}")
        print(f"🧠 Strategic Analyses: {self.stats['strategic_analyses']}")
        print(f"⚡ Flash Decisions: {self.stats['flash_decisions']}")
        print(f"💰 Trades Executed: {self.stats['trades_executed']}")
        print(f"❌ Errors: {self.stats['errors']}")
        print(f"🔑 API Keys Health: {health['working_keys']}/{health['total_api_keys']} ({health['health_percentage']:.1f}%)")
        print(f"📋 Current Directive: {self.current_directive['bias'] if self.current_directive else 'None'}")

async def main():
    """Main entry point"""
    bot = GeminiTradingBot()
    
    try:
        await bot.start()
    except KeyboardInterrupt:
        pass
    finally:
        await bot.shutdown()

if __name__ == "__main__":
    # Run the bot
    asyncio.run(main())
