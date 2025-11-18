import google.generativeai as genai
import json
from datetime import datetime, timezone
from typing import Dict, Optional
from config import config
from binance_client import market_data

class StrategicProAgent:
    """Strategic Pro - Master market strategist using Gemini 2.5 Pro"""
    
    def __init__(self):
        self.model_name = config.GEMINI_PRO_MODEL
        self.model = None
        self.current_directive = None
        self.last_analysis_time = None
    
    def initialize_model(self, api_key: str) -> bool:
        """Initialize Gemini Pro model with API key"""
        try:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel(self.model_name)
            return True
        except Exception as e:
            print(f"Failed to initialize Strategic Pro with key: {e}")
            return False
    
    def create_strategic_prompt(self, market_data_dict: Dict, current_price: float) -> str:
        """Create the strategic analysis prompt"""
        
        # Limit candle data to prevent prompt overflow
        formatted_4h = market_data.format_candles_for_prompt(market_data_dict['4h'], limit=50)  # Reduced from 100
        formatted_1h = market_data.format_candles_for_prompt(market_data_dict['1h'], limit=100)  # Reduced from 168
        formatted_15m = market_data.format_candles_for_prompt(market_data_dict['15m'], limit=50)  # Reduced from 96
        
        prompt = f"""
You are Gemini 2.5 PRO, a master market strategist specializing in Bitcoin. Your role is to provide a clear, strategic directive for the next 1-4 hours to your tactical AI, Gemini Flash.

Your analysis MUST be based on the provided 4H, 1H, and 15m data to identify high-probability swing trading opportunities.

=== MARKET DATA ===

1. 4H CANDLES (Last 50 - Primary Trend & Structure):
{formatted_4h}

2. 1H CANDLES (Last 100 - Momentum & Secondary Structure):
{formatted_1h}

3. 15m CANDLES (Last 50 - Recent Price Action):
{formatted_15m}

Current Bitcoin Price: ${current_price:.2f}

=== YOUR MISSION ===

Analyze the multi-timeframe data and produce a STRATEGIC DIRECTIVE.

1. **Determine the 4H Trend:** Is the market in a clear UPTREND (Higher Highs/Higher Lows), DOWNTREND (Lower Highs/Lower Lows), or RANGE?
2. **Identify Key Zones:** Pinpoint the most significant 4H Supply (resistance) and Demand (support) zones.
3. **Establish Strategic Bias:** Based on the 4H trend, decide the overall mission: LONG_BIAS, SHORT_BIAS, or NEUTRAL.
4. **Define High-Probability Entry Zones:** Where should Flash look for tactical entries? These must be within or near your identified Supply/Demand zones.
5. **Set Invalidation Level:** At what price level is this entire strategic plan wrong? This will be the basis for the Stop Loss.
6. **Provide Instructions for Flash:** Give clear, actionable guidance. What specific patterns or confirmations should Flash look for?

=== RESPONSE FORMAT (JSON ONLY) ===

Respond ONLY with a valid JSON object. Do not include any text before or after the JSON.

{{
    "bias": "LONG_BIAS",
    "reasoning": "Detailed strategic analysis of the 4H/1H structure, key levels, and why this bias was chosen. Explain the big picture.",
    "trend_4h": "UPTREND",
    "confidence": 8,
    "entry_zones": [
        {{"min": 91000.0, "max": 91500.0, "priority": "PRIMARY"}},
        {{"min": 90500.0, "max": 91000.0, "priority": "BACKUP"}}
    ],
    "invalidation_level": 90000.0,
    "targets": [
        {{"price": 92000.0, "level": "TP1"}},
        {{"price": 92500.0, "level": "TP2"}},
        {{"price": 93000.0, "level": "TP3"}}
    ],
    "flash_instructions": {{
        "message": "Wait for price to enter a designated entry zone. Look for bullish confirmation patterns on the 15m or 1m timeframe before executing. Volume must confirm the move.",
        "required_confirmations": [
            "Bullish candlestick pattern (e.g., engulfing, pin bar)",
            "Volume spike above 20-period average",
            "15m momentum alignment"
        ],
        "avoid_if": [
            "Price is ranging with low volume",
            "There are signs of a liquidity grab (stop hunt)",
            "During major news events"
        ]
    }},
    "valid_for_hours": 4
}}
"""
        return prompt
    
    async def analyze_market(self) -> Optional[Dict]:
        """Perform strategic market analysis"""
        print("🧠 Strategic Pro: Starting market analysis...")
        
        # Fetch market data
        try:
            data = await market_data.fetch_strategic_data()
            current_price = 0.0
            
            # Get current price
            async with market_data.binance as client:
                current_price = await client.get_current_price()
            
            if not data['4h'] or not data['1h'] or not data['15m']:
                print("❌ Strategic Pro: Insufficient market data")
                return None
            
            print(f"📊 Strategic Pro: Analyzing {len(data['4h'])} 4H, {len(data['1h'])} 1H, {len(data['15m'])} 15M candles")
            
        except Exception as e:
            print(f"❌ Strategic Pro: Data fetch error: {e}")
            return None
        
        # Try each API key until one works
        for attempt in range(config.MAX_RETRIES):
            api_key = config.api_keys.get_working_key(prefer_gemini=True)
            if not api_key:
                print("❌ Strategic Pro: No API keys available")
                return None
            
            # Skip keys that are known to be quota exceeded
            if api_key in getattr(self, 'quota_exceeded_keys', set()):
                print(f"⏭️ Strategic Pro: Skipping quota exceeded key {api_key[:10]}...")
                continue
            
            if not self.initialize_model(api_key):
                continue
            
            try:
                prompt = self.create_strategic_prompt(data, current_price)
                
                print("🤖 Strategic Pro: Generating analysis...")
                response = self.model.generate_content(prompt)
                
                if response and response.text:
                    response_text = response.text.strip()
                    print(f"📝 Strategic Pro: Raw response length: {len(response_text)} chars")
                    
                    # Debug: Show first 200 chars of response
                    if len(response_text) > 0:
                        print(f"📝 Response preview: {response_text[:200]}...")
                        
                        # Clean response - remove markdown formatting
                        if response_text.startswith('json'):
                            response_text = response_text[4:].strip()
                        if response_text.startswith('```json'):
                            response_text = response_text[7:].strip()
                        if response_text.endswith('```'):
                            response_text = response_text[:-3].strip()
                        
                        print(f"📝 Cleaned response length: {len(response_text)} chars")
                    else:
                        print("📝 Empty response from Gemini Pro")
                        continue
                    
                    # Parse JSON response
                    directive = json.loads(response_text)
                    
                    # Validate directive
                    if self.validate_directive(directive):
                        self.current_directive = directive
                        self.last_analysis_time = datetime.now(timezone.utc)
                        
                        print(f"✅ Strategic Pro: Analysis complete - {directive['bias']} (Confidence: {directive['confidence']}/10)")
                        return directive
                    else:
                        print("❌ Strategic Pro: Invalid directive format")
                        continue
                else:
                    print("❌ Strategic Pro: No response from Gemini Pro")
                    continue
                
            except json.JSONDecodeError as e:
                print(f"❌ Strategic Pro: JSON parse error: {e}")
                continue
            except Exception as e:
                error_str = str(e)
                if "quota" in error_str.lower() or "429" in error_str:
                    print(f"⏰ Strategic Pro: Quota exceeded for key {api_key[:10]}..., trying next key")
                    # Mark this key as quota exceeded
                    if not hasattr(self, 'quota_exceeded_keys'):
                        self.quota_exceeded_keys = set()
                    self.quota_exceeded_keys.add(api_key)
                    continue
                else:
                    print(f"❌ Strategic Pro: Analysis error with key {api_key[:10]}...: {e}")
                    continue
        
        print("❌ Strategic Pro: All API keys failed or quota exceeded")
        return None
    
    def validate_directive(self, directive: Dict) -> bool:
        """Validate strategic directive format"""
        required_fields = [
            'bias', 'reasoning', 'trend_4h', 'confidence',
            'entry_zones', 'invalidation_level', 'targets', 'flash_instructions'
        ]
        
        for field in required_fields:
            if field not in directive:
                return False
        
        # Validate confidence is integer 1-10
        if not isinstance(directive['confidence'], int) or not 1 <= directive['confidence'] <= 10:
            return False
        
        # Validate bias
        if directive['bias'] not in ['LONG_BIAS', 'SHORT_BIAS', 'NEUTRAL']:
            return False
        
        return True
    
    def get_current_directive(self) -> Optional[Dict]:
        """Get current strategic directive"""
        if not self.current_directive:
            return None
        
        # Check if directive is still valid
        if self.last_analysis_time:
            hours_since = (datetime.now(timezone.utc) - self.last_analysis_time).total_seconds() / 3600
            valid_hours = self.current_directive.get('valid_for_hours', 4)
            
            if hours_since > valid_hours:
                print("⏰ Strategic Pro: Directive expired")
                return None
        
        return self.current_directive

# Global Strategic Pro instance
strategic_pro = StrategicProAgent()
