import google.generativeai as genai
import json
from datetime import datetime, timezone
from typing import Dict, Optional
from config import config
from binance_client import market_data

class FlashAgent:
    """Flash - Tactical execution AI using Gemini 2.5 Flash"""
    
    def __init__(self):
        self.model_name = config.GEMINI_FLASH_MODEL
        self.model = None
    
    def initialize_model(self, api_key: str) -> bool:
        """Initialize Gemini Flash model with API key"""
        try:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel(self.model_name)
            return True
        except Exception as e:
            print(f"Failed to initialize Flash with key: {e}")
            return False
    
    def create_flash_prompt(self, market_data_dict: Dict, current_price: float, pro_directive: Dict) -> str:
        """Create the tactical execution prompt"""
        
        formatted_1h = market_data.format_candles_for_prompt(market_data_dict['1h'])
        formatted_15m = market_data.format_candles_for_prompt(market_data_dict['15m'])
        formatted_1m = market_data.format_candles_for_prompt(market_data_dict['1m'])
        current_time_utc = datetime.now(timezone.utc).isoformat()
        
        prompt = f"""
You are Gemini 2.5 FLASH, a tactical execution AI. Your mission is to execute the strategic plan provided by your commander, Gemini Pro, with precision.

=== STRATEGIC DIRECTIVE FROM PRO COMMANDER ===
{json.dumps(pro_directive, indent=2)}

=== CURRENT BATTLEFIELD DATA (Real-Time) ===

Current Price: ${current_price:.2f}
Time: {current_time_utc} UTC

1. 1H CANDLES (Last 24 - Immediate Context):
{formatted_1h}

2. 15m CANDLES (Last 48 - Building Momentum):
{formatted_15m}

3. 1m CANDLES (Last 100 - Entry Pattern Recognition):
{formatted_1m}

=== YOUR TACTICAL DECISION ===

Analyze the real-time data against Pro's strategic directive.

1. **Zone Check:** Is the current price inside one of Pro's designated `entry_zones`?
2. **Confirmation Check:** Are Pro's `required_confirmations` (e.g., candlestick patterns, volume) visible on the 15m or 1m charts RIGHT NOW?
3. **Avoidance Check:** Are any of Pro's `avoid_if` conditions present?
4. **Final Decision:** Based on the above, should you EXECUTE the entry, WAIT for a better moment, or REJECT the setup?

=== RESPONSE FORMAT (JSON ONLY) ===

Respond ONLY with a valid JSON object.

{{
    "action": "ENTER_LONG" | "ENTER_SHORT" | "WAIT" | "REJECT",
    "reasoning": "Brief tactical analysis. Example: 'Price is in primary entry zone and a 15m bullish engulfing pattern just formed with a volume spike. Executing LONG.'",
    "confidence": "An integer from 1-10. Only set 9+ for perfect setups that meet all criteria.",
    "pattern_detected": "Bullish Engulfing on 15m" | "1m Double Bottom" | "None",
    "entry_price": {current_price},
    "stop_loss": {pro_directive.get('invalidation_level', current_price * 0.95)},
    "take_profit": {pro_directive.get('targets', [{'price': current_price * 1.05}])[0]['price'] if pro_directive.get('targets') else current_price * 1.05}
}}
"""
        return prompt
    
    async def execute_tactical_decision(self, pro_directive: Dict) -> Optional[Dict]:
        """Make tactical execution decision based on Strategic Pro's directive"""
        print("⚡ Flash: Analyzing tactical opportunity...")
        
        if not pro_directive:
            print("❌ Flash: No strategic directive available")
            return None
        
        # Fetch real-time market data
        try:
            data = await market_data.fetch_flash_data()
            current_price = data.get('current_price', 0.0)
            
            if not data['1h'] or not data['15m'] or not data['1m'] or current_price == 0:
                print("❌ Flash: Insufficient real-time data")
                return None
            
            print(f"📊 Flash: Analyzing price ${current_price:.2f} with {len(data['1m'])} 1M candles")
            
        except Exception as e:
            print(f"❌ Flash: Data fetch error: {e}")
            return None
        
        # Check if price is in entry zones
        in_entry_zone = self.check_entry_zones(current_price, pro_directive.get('entry_zones', []))
        if not in_entry_zone:
            print(f"💤 Flash: Price ${current_price:.2f} not in entry zones")
            return {
                "action": "WAIT",
                "reasoning": "Price not in Strategic Pro's designated entry zones",
                "confidence": 5,
                "pattern_detected": "None",
                "entry_price": current_price,
                "stop_loss": pro_directive.get('invalidation_level', current_price * 0.95),
                "take_profit": pro_directive.get('targets', [{'price': current_price * 1.05}])[0]['price'] if pro_directive.get('targets') else current_price * 1.05
            }
        
        # Try each API key until one works
        for attempt in range(config.MAX_RETRIES):
            api_key = config.api_keys.get_working_key(prefer_gemini=True)
            if not api_key:
                print("❌ Flash: No API keys available")
                return None
            
            if not self.initialize_model(api_key):
                continue
            
            try:
                prompt = self.create_flash_prompt(data, current_price, pro_directive)
                
                print("🤖 Flash: Generating tactical decision...")
                response = self.model.generate_content(prompt)
                
                if response and response.text:
                    # Parse JSON response
                    decision = json.loads(response.text.strip())
                    
                    # Validate decision
                    if self.validate_decision(decision):
                        print(f"✅ Flash: Decision - {decision['action']} (Confidence: {decision['confidence']}/10)")
                        return decision
                    else:
                        print("❌ Flash: Invalid decision format")
                        continue
                
            except json.JSONDecodeError as e:
                print(f"❌ Flash: JSON parse error: {e}")
                continue
            except Exception as e:
                print(f"❌ Flash: Decision error with key {api_key[:10]}...: {e}")
                continue
        
        print("❌ Flash: All API keys failed")
        return None
    
    def check_entry_zones(self, current_price: float, entry_zones: list) -> bool:
        """Check if current price is within any entry zone"""
        for zone in entry_zones:
            if zone.get('min', 0) <= current_price <= zone.get('max', 0):
                print(f"🎯 Flash: Price in {zone.get('priority', 'UNKNOWN')} entry zone")
                return True
        return False
    
    def validate_decision(self, decision: Dict) -> bool:
        """Validate tactical decision format"""
        required_fields = [
            'action', 'reasoning', 'confidence', 'pattern_detected',
            'entry_price', 'stop_loss', 'take_profit'
        ]
        
        for field in required_fields:
            if field not in decision:
                return False
        
        # Validate confidence is integer 1-10
        if not isinstance(decision['confidence'], int) or not 1 <= decision['confidence'] <= 10:
            return False
        
        # Validate action
        if decision['action'] not in ['ENTER_LONG', 'ENTER_SHORT', 'WAIT', 'REJECT']:
            return False
        
        return True

# Global Flash instance
flash = FlashAgent()
