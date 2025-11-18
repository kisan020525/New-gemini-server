# Gemini Trading Bot

Advanced Bitcoin trading bot using Google Gemini 2.5 Pro and Flash models with multi-timeframe analysis.

## Architecture

### Strategic Pro (Gemini 2.5 Pro)
- **Frequency**: Every 1 hour
- **Data**: 100 4H + 168 1H + 96 15M candles
- **Purpose**: Strategic market analysis and trade planning
- **Output**: Entry zones, targets, stop losses, and tactical instructions

### Flash (Gemini 2.5 Flash)
- **Frequency**: Every 1 minute
- **Data**: 24 1H + 48 15M + 100 1M candles + current price
- **Purpose**: Tactical execution and precise timing
- **Output**: ENTER/WAIT/REJECT decisions with confidence scores

## Features

- ✅ **API Key Rotation**: 15 Gemini + 2 Lite keys with automatic failover
- ✅ **Multi-timeframe Analysis**: 4H, 1H, 15M, 1M candles from Binance
- ✅ **Error Handling**: Comprehensive error recovery and logging
- ✅ **Database Logging**: Complete audit trail in Supabase
- ✅ **Paper Trading**: Safe testing environment
- ✅ **Real-time Monitoring**: System health and performance metrics

## Environment Variables

### Required (Already set in Railway)
```bash
# Gemini API Keys (15 main keys)
GEMINI_API_KEY_1=your_key_here
GEMINI_API_KEY_2=your_key_here
# ... up to GEMINI_API_KEY_15

# Gemini Lite Keys (2 backup keys)
GEMINI_LITE_API_KEY_1=your_key_here
GEMINI_LITE_API_KEY_2=your_key_here

# Supabase Configuration
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
TRADES_SUPABASE_URL=your_trades_supabase_url
TRADES_SUPABASE_KEY=your_trades_supabase_key
```

## Database Schema

### Supabase Tables Required

#### 1. candles
```sql
CREATE TABLE candles (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(10) DEFAULT 'BTCUSD',
    timeframe VARCHAR(5) NOT NULL,
    open DECIMAL(15,8) NOT NULL,
    high DECIMAL(15,8) NOT NULL,
    low DECIMAL(15,8) NOT NULL,
    close DECIMAL(15,8) NOT NULL,
    volume DECIMAL(20,8) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### 2. trades
```sql
CREATE TABLE trades (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    action VARCHAR(10) NOT NULL,
    symbol VARCHAR(10) DEFAULT 'BTCUSD',
    price DECIMAL(15,8) NOT NULL,
    quantity DECIMAL(15,8) NOT NULL,
    confidence_score INTEGER,
    strategic_analysis TEXT,
    flash_signal TEXT,
    profit_loss DECIMAL(15,8),
    status VARCHAR(20) DEFAULT 'PENDING',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### 3. system_logs
```sql
CREATE TABLE system_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    level VARCHAR(10),
    component VARCHAR(50),
    message TEXT NOT NULL,
    error_details JSONB
);
```

#### 4. portfolio
```sql
CREATE TABLE portfolio (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    btc_balance DECIMAL(15,8) DEFAULT 0,
    usd_balance DECIMAL(15,8) DEFAULT 10000,
    total_value_usd DECIMAL(15,8)
);
```

## Deployment

### Railway Deployment
1. Push code to GitHub repository
2. Connect Railway to your GitHub repo
3. Environment variables are already configured
4. Deploy automatically

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Edit .env with your keys

# Run the bot
python main.py
```

## System Flow

1. **Strategic Pro** analyzes market every hour:
   - Fetches 100 4H + 168 1H + 96 15M candles
   - Identifies trends and key levels
   - Creates strategic directive with entry zones

2. **Flash** executes tactics every minute:
   - Fetches 24 1H + 48 15M + 100 1M candles + current price
   - Checks if price is in Strategic Pro's entry zones
   - Makes ENTER/WAIT/REJECT decision

3. **Trade Execution**:
   - Paper trading by default
   - Logs all decisions to Supabase
   - Updates portfolio status

## Monitoring

- **System Health**: API key status and error rates
- **Performance**: Analysis frequency and success rates
- **Trading**: Portfolio value and trade history
- **Logs**: Complete audit trail in Supabase

## Error Handling

- **API Key Rotation**: Automatic failover between 17 keys
- **Rate Limiting**: Intelligent backoff and retry
- **Data Validation**: Ensures data quality before analysis
- **Graceful Recovery**: System continues despite individual failures

## Safety Features

- **Paper Trading**: No real money at risk
- **Confidence Thresholds**: Only high-confidence trades executed
- **Stop Losses**: Automatic risk management
- **Position Limits**: Maximum position size controls

## Support

For issues or questions, check the system logs in Supabase or review the error handling output in Railway logs.
