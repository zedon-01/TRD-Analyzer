import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import base64
from openai import OpenAI
from google import genai
from datetime import datetime, timedelta
import pytz # Potřebné pro korektní časová pásma
import os
os.makedirs("scratch", exist_ok=True)

# --- API Key Detection (Global Scope) ---
def get_api_credentials():
    """Dynamically fetch API keys, prioritizing persistent session overrides over secrets."""
    manual_key = st.session_state.get("persistent_api_key", "").strip()
    manual_provider = st.session_state.get("persistent_api_provider", "Gemini")
    
    if manual_key:
        return manual_key, manual_provider
        
    # Bypass st.secrets cache by reading TOML directly
    try:
        import tomllib
        with open(".streamlit/secrets.toml", "rb") as f:
            data = tomllib.load(f)
            gemini_key = data.get("GEMINI_API_KEY", "").strip()
            openai_key = data.get("OPENAI_API_KEY", "").strip()
    except Exception:
        gemini_key = st.secrets.get("GEMINI_API_KEY", "").strip()
        openai_key = st.secrets.get("OPENAI_API_KEY", "").strip()
    
    if gemini_key:
        return gemini_key, "Gemini"
    elif openai_key:
        return openai_key, "OpenAI"
    return None, None

# Initialize global vars for UI checks
api_key, ai_provider = get_api_credentials()

# --- Streamlit Page Config ---
st.set_page_config(page_title="Trading Analyzer", layout="wide", initial_sidebar_state="expanded")

# --- Session State Initialization ---
if 'current_page' not in st.session_state:
    st.session_state.current_page = "Dashboard"
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = ["BTC-USD", "ETH-USD", "EURUSD=X", "GC=F", "^IXIC"]
if 'dxm_symbol' not in st.session_state:
    st.session_state.dxm_symbol = "EURUSD=X"
if 'cot_symbol' not in st.session_state:
    st.session_state.cot_symbol = "EURUSD=X"
if 'tf_period' not in st.session_state:
    st.session_state.tf_period = "1y"
if 'tf_interval' not in st.session_state:
    st.session_state.tf_interval = "1d"
if 'ai_analysis_data' not in st.session_state:
    st.session_state.ai_analysis_data = None
if 'analysis_history' not in st.session_state:
    st.session_state.analysis_history = []
if 'persistent_api_key' not in st.session_state or not st.session_state.persistent_api_key:
    st.session_state.persistent_api_key = api_key if api_key else ""
if 'persistent_api_provider' not in st.session_state:
    st.session_state.persistent_api_provider = ai_provider if ai_provider else "Gemini"
if 'persistent_model_name' not in st.session_state:
    st.session_state.persistent_model_name = "gemini-2.5-flash"

def sync_api_credentials():
    if "input_api_key" in st.session_state:
        st.session_state.persistent_api_key = st.session_state.input_api_key
    if "input_api_provider" in st.session_state:
        st.session_state.persistent_api_provider = st.session_state.input_api_provider
    if "input_model_name" in st.session_state:
        st.session_state.persistent_model_name = st.session_state.input_model_name

# No base64 needed, pure CSS logo used.

# --- CSS Injection ---
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
}

[data-testid="stAppViewContainer"] {
    background-color: #0A0B0E;
}

[data-testid="stSidebar"] {
    background-color: #0E1015;
    border-right: 1px solid #1E2129;
}

/* Hide original Streamlit sidebar divider */
[data-testid="stSidebar"] hr {
    display: none;
}

/* Sidebar Custom CSS Logo */
.custom-logo-wrapper {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 40px;
    margin-top: 10px;
}
.brand-bars {
    display: flex;
    align-items: flex-end;
    gap: 3px;
    height: 32px;
}
.brand-bar {
    width: 6px;
    border-radius: 2px;
}
.brand-bar-1 { height: 16px; background: #94A3B8; }
.brand-bar-2 { height: 24px; background: #00E676; box-shadow: 0 0 10px rgba(0,230,118,0.5); }
.brand-bar-3 { height: 32px; background: #FBBF24; box-shadow: 0 0 10px rgba(251,191,36,0.5); }
.sidebar-logo-text {
    font-size: 1.25rem;
    font-weight: 700;
    color: #F8FAFC;
    line-height: 1.1;
    letter-spacing: -0.5px;
    text-transform: uppercase;
}
.sidebar-menu-item {
    padding: 10px 16px;
    border-radius: 8px;
    color: #94A3B8;
    margin-bottom: 4px;
    display: flex;
    align-items: center;
    gap: 12px;
    cursor: pointer;
    font-size: 0.95rem;
    font-weight: 500;
    transition: all 0.2s;
}
.sidebar-menu-item.active {
    background-color: #1E2129;
    color: #F8FAFC;
}
.sidebar-menu-item:hover {
    background-color: rgba(30, 33, 41, 0.6);
    color: #F8FAFC;
}

/* Table Style Fake Overrides for Main Container */
.custom-pairs-table {
    width: 100%;
    color: #94A3B8;
    border-collapse: collapse;
}
.custom-pairs-table th {
    text-align: left;
    padding: 12px 10px;
    font-size: 0.8rem;
    font-weight: 500;
    border-bottom: 1px solid #1E2129;
}
.custom-pairs-table td {
    padding: 16px 10px;
    border-bottom: 1px solid rgba(255,255,255,0.02);
    font-size: 0.9rem;
    color: #F8FAFC;
}

/* Custom styles for metric cards to look like Dashboard Mockup */
[data-testid="stMetric"] {
    background-color: #14161C;
    border: 1px solid #1E2129;
    padding: 1.5rem;
    border-radius: 16px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
    transition: all 0.3s ease;
}

[data-testid="stMetric"]:hover {
    border-color: #383e4a;
    transform: translateY(-2px);
}

[data-testid="stMetricValue"] {
    font-size: 2rem;
    font-weight: 700;
    color: #E2E8F0;
}

[data-testid="stMetricLabel"] {
    color: #94A3B8;
    font-weight: 500;
}

/* Hide Streamlit exact tooltip icon for cleaner look */
[data-testid="stTooltipIcon"] {
    display: none; 
}

/* Remove baby-blue st.info and make it dark & glass */
[data-testid="stAlert"] {
    background-color: rgba(20, 22, 28, 0.55) !important;
    backdrop-filter: blur(12px) !important;
    border: 1px solid rgba(56, 189, 248, 0.4) !important;
    border-left: 4px solid #38BDF8 !important;
    color: #E2E8F0 !important;
    border-radius: 8px !important;
    box-shadow: 0 4px 15px rgba(0,0,0,0.2) !important;
}
[data-testid="stAlert"] p {
    color: #E2E8F0 !important;
    font-size: 0.95rem;
}

/* Style the Expanders as Cards */
[data-testid="stExpander"] {
    background-color: rgba(20, 22, 28, 0.4) !important;
    backdrop-filter: blur(10px) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 12px !important;
    box-shadow: 0 4px 30px rgba(0,0,0,0.3) !important;
    transition: all 0.3s ease !important;
}

[data-testid="stExpander"]:hover {
    border-color: rgba(0, 230, 118, 0.4) !important;
    box-shadow: 0 0 20px rgba(0, 230, 118, 0.05) !important;
}

/* Institutional Header Styles */
.status-indicator {
    padding: 6px 12px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 500;
    border: 1px solid rgba(255,255,255,0.1);
    background: rgba(20, 22, 28, 0.8);
    color: #94A3B8;
}
.status-indicator.active {
    color: #10B981;
    border-color: rgba(16, 185, 129, 0.3);
}
.time-badge {
    background: #14161C;
    border: 1px solid #1E2129;
    padding: 6px 14px;
    border-radius: 20px;
    margin-left: 10px;
    font-size: 0.8rem;
    color: #94A3B8;
}
.time-badge b { color: white; }


[data-testid="stExpander"] summary {
    font-weight: 600;
    color: #F8FAFC;
    padding: 0.8rem 1rem !important;
}

/* Better glowing text helper */
.st-emotion-cache-10trblm h1, .st-emotion-cache-10trblm h2, .st-emotion-cache-10trblm h3 {
    color: #F8FAFC;
}

/* Premium Containers */
[data-testid="stVerticalBlockBorderWrapper"] {
    background-color: #14161C !important;
    border: 1px solid #1E2129 !important;
    border-radius: 16px !important;
    padding: 20px !important;
    box-shadow: 0 4px 30px rgba(0, 0, 0, 0.4) !important;
}

[data-testid="column"] {
    padding: 0 10px !important;
}

.stButton>button {
    background-color: #1E293B;
    color: #F8FAFC;
    border-radius: 8px;
    font-weight: 600;
    border: 1px solid #334155;
    transition: all 0.3s;
}

.stButton>button:hover {
    background-color: #00E676;
    color: #0F172A;
    border-color: #00E676;
    box-shadow: 0 0 15px rgba(0, 230, 118, 0.4);
}

/* Status Dots and Glows */
.pulse-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background-color: #10B981;
    box-shadow: 0 0 8px #10B981;
    animation: pulse 2s infinite;
    margin-right: 6px;
}
.pulse-dot.short {
    background-color: #EF4444;
    box-shadow: 0 0 8px #EF4444;
}
@keyframes pulse {
    0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.4); }
    70% { box-shadow: 0 0 0 6px rgba(16, 185, 129, 0); }
    100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
}
.glow-long { color: #10B981; text-shadow: 0 0 10px rgba(16, 185, 129, 0.4); }
.glow-short { color: #EF4444; text-shadow: 0 0 10px rgba(239, 68, 68, 0.4); }

/* --- Custom Loading Status Widget (Replaces Running Man) --- */
[data-testid="stStatusWidget"] img, [data-testid="stStatusWidget"] label {
    display: none !important;
}
[data-testid="stStatusWidget"] {
    background-color: rgba(20, 22, 28, 0.9) !important;
    border: 1px solid rgba(16, 185, 129, 0.4) !important;
    border-radius: 20px !important;
    padding: 8px 16px !important;
    box-shadow: 0 0 15px rgba(16, 185, 129, 0.2) !important;
}
[data-testid="stStatusWidget"]::before {
    content: "⚡ AI Engine Syncing...";
    color: #10B981;
    font-weight: 600;
    font-size: 0.9rem;
    animation: pulse-glow 1.5s infinite alternate;
}
@keyframes pulse-glow {
    from { text-shadow: 0 0 5px rgba(16, 185, 129, 0.2); }
    to { text-shadow: 0 0 15px rgba(16, 185, 129, 0.8); }
}
</style>
""", unsafe_allow_html=True)

# --- Session State Initialization ---
if 'tf_interval' not in st.session_state:
    st.session_state.tf_interval = "1d"
if 'tf_period' not in st.session_state:
    st.session_state.tf_period = "1y"
if 'analysis_history' not in st.session_state:
    st.session_state.analysis_history = []
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

# --- Functions ---

try:
    from curl_cffi import requests as curl_requests
except ImportError:
    import requests as curl_requests

import random
import time

def get_yfinance_session():
    """Create a session with curl_cffi and rotating user agents to avoid Yahoo's bot detection."""
    session = curl_requests.Session()
    
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:122.0) Gecko/20100101 Firefox/122.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0 Safari/537.36'
    ]
    
    session.headers.update({
        'User-Agent': random.choice(user_agents),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
    })
    return session

@st.cache_data(show_spinner="Načítám historická data...", ttl=300)
def fetch_data(ticker_symbol, period, interval="1d"):
    """Fetches historical market data with robust fallback mechanisms."""
    try:
        # Method 1: Ticker with custom session
        session = get_yfinance_session()
        ticker = yf.Ticker(ticker_symbol, session=session)
        df = ticker.history(period=period, interval=interval)
        
        if not df.empty:
            df.index = df.index.tz_localize(None)
            return df
            
    except Exception as e:
        pass # Fallback to method 2
        
    try:
        # Method 2: yf.download (often bypasses some restrictions)
        time.sleep(1) # Small delay before retry
        df = yf.download(tickers=ticker_symbol, period=period, interval=interval, progress=False)
        if not df.empty:
            # yf.download sometimes returns MultiIndex columns if multiple tickers, 
            # but for single ticker it returns normal columns. Let's ensure it's flat.
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
            df.index = df.index.tz_localize(None)
            return df
            
    except Exception as e:
        if "Rate limited" in str(e) or "429" in str(e):
            st.warning(f"📡 Yahoo Finance dočasně omezilo přístup (Rate Limit). Zkuste to prosím za chvíli.")
        else:
            st.error(f"Chyba při stahování dat pro ticker {ticker_symbol}: {e}")
        
    return pd.DataFrame()

@st.cache_data(show_spinner="Načítám fundamentální data...", ttl=3600)
def fetch_fundamentals(ticker_symbol):
    """Fetches fundamental data from yfinance with a hard timeout to prevent hangs."""
    import concurrent.futures
    session = get_yfinance_session()
    ticker = yf.Ticker(ticker_symbol, session=session)
    
    fundamentals = {}
    
    try:
        # ticker.info is notoriously slow and can hang indefinitely
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(lambda: ticker.info)
            info = future.result(timeout=12) # 12 second hard timeout
    except Exception:
        # If it hangs or fails, return empty so the app can continue
        return {}
    
    # Safely extract common metrics
    metrics_to_extract = [
        "shortName", "sector", "industry", "marketCap", 
        "trailingPE", "forwardPE", "trailingEps", 
        "debtToEquity", "revenueGrowth", "profitMargins",
        "52WeekChange", "dividendYield"
    ]
    
    for metric in metrics_to_extract:
        if metric in info and info[metric] is not None:
            fundamentals[metric] = info[metric]
            
    return fundamentals

@st.cache_data(show_spinner="Načítám aktuální zprávy...", ttl=900)
def fetch_news(ticker_symbol):
    """Fetches latest news from yfinance with robust parsing and custom session."""
    session = get_yfinance_session()
    ticker = yf.Ticker(ticker_symbol, session=session)
    try:
        news_data = ticker.news
        if not news_data:
            return []
        
        parsed_news = []
        for article in news_data[:4]:
            # Handle both flat and nested (recent yfinance) structures
            content = article.get("content", article)
            
            title = content.get("title", article.get("title", "No Title"))
            
            # Publisher / Provider
            provider = content.get("provider", {})
            publisher = provider.get("displayName", content.get("publisher", article.get("publisher", "Unknown Publisher")))
            
            # URL / Link
            canonical = content.get("canonicalUrl", {})
            link = canonical.get("url", content.get("link", article.get("link", "#")))
            
            # Fallback for link if still #
            if link == "#":
                link = article.get("link", "#")

            parsed_news.append({
                "title": title,
                "publisher": publisher,
                "link": link,
                "timestamp": content.get("pubDate", article.get("providerPublishTime", 0))
            })
        return parsed_news
    except Exception:
        return []

def get_technical_signals(df):
    """Generates a summary of technical signals for the Health Check panel."""
    if df.empty: return {}
    
    # Check if indicators are present
    required_cols = ['RSI', 'MACD', 'MACD_Signal', 'SMA_50']
    if not all(col in df.columns for col in required_cols):
        return {} # Not enough data to show signals
        
    last = df.iloc[-1]
    
    signals = {
        "RSI": {"val": f"{last['RSI']:.1f}", "status": "Neutral", "color": "#94A3B8"},
        "MACD": {"val": "Cross", "status": "Neutral", "color": "#94A3B8"},
        "SMA": {"val": "Price", "status": "Neutral", "color": "#94A3B8"},
        "Bollinger": {"val": "Range", "status": "Neutral", "color": "#94A3B8"}
    }
    
    # RSI Logic
    if last['RSI'] > 70: signals["RSI"] = {"val": f"{last['RSI']:.1f}", "status": "Overbought", "color": "#EF4444"}
    elif last['RSI'] < 30: signals["RSI"] = {"val": f"{last['RSI']:.1f}", "status": "Oversold", "color": "#10B981"}
    
    # MACD Logic
    if last['MACD'] > last['MACD_Signal']: signals["MACD"] = {"val": "Bullish", "status": "Upward", "color": "#10B981"}
    else: signals["MACD"] = {"val": "Bearish", "status": "Downward", "color": "#EF4444"}
    
    # SMA Logic
    if last['Close'] > last['SMA_50']: signals["SMA"] = {"val": "Above SMA50", "status": "Bullish", "color": "#10B981"}
    else: signals["SMA"] = {"val": "Below SMA50", "status": "Bearish", "color": "#EF4444"}
    
    return signals

def calculate_indicators(df):
    """Calculates technical indicators using the 'ta' library."""
    # Ensure we have data
    if df.empty or len(df) < 20: 
        return df
        
    if df.empty:
        return df
        
    df = df.copy()
    
    # Minimum data length check for complex indicators
    if len(df) < 30:
        return df
    
    # SMAs
    df['SMA_20'] = ta.trend.sma_indicator(df['Close'], window=20)
    df['SMA_50'] = ta.trend.sma_indicator(df['Close'], window=50)
    df['SMA_200'] = ta.trend.sma_indicator(df['Close'], window=200)
    
    # Bollinger Bands
    indicator_bb = ta.volatility.BollingerBands(close=df['Close'], window=20, window_dev=2)
    df['BB_High'] = indicator_bb.bollinger_hband()
    df['BB_Low'] = indicator_bb.bollinger_lband()
    
    # RSI
    df['RSI'] = ta.momentum.rsi(df['Close'], window=14)
    
    # MACD
    indicator_macd = ta.trend.MACD(close=df['Close'])
    df['MACD'] = indicator_macd.macd()
    df['MACD_Signal'] = indicator_macd.macd_signal()
    df['MACD_Hist'] = indicator_macd.macd_diff()
    
    # ADX (Trend Strength)
    try:
        indicator_adx = ta.trend.ADXIndicator(high=df['High'], low=df['Low'], close=df['Close'], window=14)
        df['ADX'] = indicator_adx.adx()
        df['DI_Plus'] = indicator_adx.adx_pos()
        df['DI_Minus'] = indicator_adx.adx_neg()
    except Exception:
        df['ADX'] = pd.Series([20] * len(df))
        df['DI_Plus'] = pd.Series([0] * len(df))
        df['DI_Minus'] = pd.Series([0] * len(df))
    
    return df

def calculate_synthetic_sentiment(df):
    """Calculates a highly sophisticated, ADX-weighted sentiment percentage (Synthetic Institutional COT)."""
    if df.empty or len(df) < 20:
        return 50, 50
        
    last_row = df.iloc[-1]
    
    # 1. Trend Factor (Price vs SMAs)
    # We look at relation to 20, 50, and 200 to get a 'stacked' trend view
    close = last_row['Close']
    sma20 = last_row['SMA_20'] if not pd.isna(last_row.get('SMA_20')) else close
    sma50 = last_row['SMA_50'] if not pd.isna(last_row.get('SMA_50')) else close
    sma200 = last_row['SMA_200'] if not pd.isna(last_row.get('SMA_200')) else close
    
    trend_val = (
        (0.5 * (close / sma20 - 1)) +
        (0.3 * (close / sma50 - 1)) +
        (0.2 * (close / sma200 - 1))
    ) * 1000 # Normalized scale
    
    # 2. Momentum Factor (RSI)
    rsi = last_row['RSI'] if not pd.isna(last_row.get('RSI')) else 50
    rsi_score = (rsi - 50)
    
    # 3. Velocity Factor (MACD Histogram Slope)
    macd_hist = last_row['MACD_Hist'] if not pd.isna(last_row.get('MACD_Hist')) else 0
    macd_score = (macd_hist / close) * 5000 if close > 0 else 0
    
    # 4. ADX Weighting (The 'Institutional' switch)
    adx = last_row['ADX'] if not pd.isna(last_row.get('ADX')) else 20
    
    if adx > 25:
        total_score = (trend_val * 0.6) + (macd_score * 0.3) + (rsi_score * 0.1)
    elif adx < 20:
        total_score = (rsi_score * 0.6) + (macd_score * 0.2) + (trend_val * 0.2)
    else:
        total_score = (trend_val * 0.4) + (rsi_score * 0.3) + (macd_score * 0.3)
    
    # Final safety check for NaN
    if pd.isna(total_score):
        total_score = 0
        
    long_pct = min(max(int(50 + total_score), 5), 95)
    short_pct = 100 - long_pct
    
    return long_pct, short_pct

def detect_orderblocks(df, lookback=150):
    """Detects simple visual orderblocks (Bullish & Bearish) for the chart."""
    df_ob = df.copy()
    if len(df_ob) < lookback:
        lookback = len(df_ob)
        
    df_ob['Body'] = abs(df_ob['Close'] - df_ob['Open'])
    avg_body = df_ob['Body'].rolling(window=20).mean()
    
    bullish_obs = []
    bearish_obs = []
    
    for i in range(len(df_ob) - lookback, len(df_ob) - 1):
        if i < 20: continue
        
        # Bullish OB
        if df_ob['Close'].iloc[i] < df_ob['Open'].iloc[i]: # Bearish candle
            # Next candle is strong bullish and breaks high
            if df_ob['Close'].iloc[i+1] > df_ob['Open'].iloc[i+1] and df_ob['Body'].iloc[i+1] > 1.2 * avg_body.iloc[i]:
                if df_ob['Close'].iloc[i+1] > df_ob['High'].iloc[i]:
                    bullish_obs.append({
                        'start': df_ob.index[i],
                        'end': df_ob.index[-1],
                        'top': df_ob['High'].iloc[i],
                        'bottom': df_ob['Low'].iloc[i]
                    })
                    
        # Bearish OB
        if df_ob['Close'].iloc[i] > df_ob['Open'].iloc[i]: # Bullish candle
            # Next candle is strong bearish and breaks low
            if df_ob['Close'].iloc[i+1] < df_ob['Open'].iloc[i+1] and df_ob['Body'].iloc[i+1] > 1.2 * avg_body.iloc[i]:
                if df_ob['Close'].iloc[i+1] < df_ob['Low'].iloc[i]:
                    bearish_obs.append({
                        'start': df_ob.index[i],
                        'end': df_ob.index[-1],
                        'top': df_ob['High'].iloc[i],
                        'bottom': df_ob['Low'].iloc[i]
                    })
                    
    # Return last 3 to keep chart clean
    return bullish_obs[-3:], bearish_obs[-3:]

def determine_htf_bias(ticker_symbol, current_interval):
    """
    Determines the higher timeframe trend bias (Bullish/Bearish/Neutral) 
    using 4h or 1d data to ensure we do not trade against the HTF trend.
    """
    if current_interval in ["1m", "5m", "15m"]:
        htf_interval = "1h"
        htf_period = "1mo"
    elif current_interval in ["30m", "1h"]:
        htf_interval = "4h"
        htf_period = "3mo"
    elif current_interval == "4h":
        htf_interval = "1d"
        htf_period = "1y"
    else: # 1d, 1wk, 1mo
        htf_interval = "1wk"
        htf_period = "5y"
        
    try:
        df_htf = fetch_data(ticker_symbol, htf_period, htf_interval)
        if df_htf.empty or len(df_htf) < 50:
            df_htf = fetch_data(ticker_symbol, "1y", "1d")
            
        if not df_htf.empty and len(df_htf) >= 20:
            df_htf = calculate_indicators(df_htf)
            last_row = df_htf.iloc[-1]
            close = last_row['Close']
            sma50 = last_row.get('SMA_50')
            sma200 = last_row.get('SMA_200')
            
            if sma50 is not None and sma200 is not None and not pd.isna(sma50) and not pd.isna(sma200):
                if close > sma50 and close > sma200:
                    return "Bullish", htf_interval
                elif close < sma50 and close < sma200:
                    return "Bearish", htf_interval
                
            slope = df_htf['Close'].tail(20).diff().mean()
            if slope > 0:
                return "Bullish (Slope)", htf_interval
            elif slope < 0:
                return "Bearish (Slope)", htf_interval
                
    except Exception:
        pass
        
    return "Neutral / Range", "1d"

def detect_session_liquidity(df):
    """
    Identifies Asian Session High/Low (00:00 - 08:00 UTC) and London Session High/Low (08:00 - 16:00 UTC).
    """
    if not isinstance(df.index, pd.DatetimeIndex):
        return {"asian_high": None, "asian_low": None, "london_high": None, "london_low": None}
        
    try:
        df_utc = df.copy()
        if df_utc.index.tz is None:
            df_utc.index = df_utc.index.tz_localize('UTC')
        else:
            df_utc.index = df_utc.index.tz_convert('UTC')
    except Exception:
        df_utc = df.copy()
        
    df_recent = df_utc.tail(200)
    
    asian_candles = df_recent[(df_recent.index.hour >= 0) & (df_recent.index.hour < 8)]
    london_candles = df_recent[(df_recent.index.hour >= 8) & (df_recent.index.hour < 16)]
    
    asian_high = float(asian_candles['High'].max()) if not asian_candles.empty else None
    asian_low = float(asian_candles['Low'].min()) if not asian_candles.empty else None
    
    london_high = float(london_candles['High'].max()) if not london_candles.empty else None
    london_low = float(london_candles['Low'].min()) if not london_candles.empty else None
    
    return {
        "asian_high": asian_high,
        "asian_low": asian_low,
        "london_high": london_high,
        "london_low": london_low
    }

def detect_market_structure_elements(df, k=5):
    """
    Identifies Swing Highs & Lows, and detects BOS (Break of Structure) 
    and CHoCH (Change of Character).
    """
    if len(df) < 2 * k + 1:
        return {
            "swing_highs": [], "swing_lows": [],
            "bos": [], "choch": [],
            "current_structure": "Neutral"
        }
    
    df_ms = df.copy()
    highs = df_ms['High'].values
    lows = df_ms['Low'].values
    closes = df_ms['Close'].values
    times = df_ms.index
    
    swing_highs = []
    swing_lows = []
    
    # 1. Identify Swing Points
    for i in range(k, len(df_ms) - k):
        is_high = True
        is_low = True
        for j in range(1, k + 1):
            if highs[i] <= highs[i - j] or highs[i] <= highs[i + j]:
                is_high = False
            if lows[i] >= lows[i - j] or lows[i] >= lows[i + j]:
                is_low = False
        
        if is_high:
            swing_highs.append({"index": i, "time": times[i], "price": float(highs[i])})
        if is_low:
            swing_lows.append({"index": i, "time": times[i], "price": float(lows[i])})

    # 2. Track BOS and CHoCH
    bos = []
    choch = []
    
    if not swing_highs or not swing_lows:
        return {
            "swing_highs": swing_highs, "swing_lows": swing_lows,
            "bos": [], "choch": [],
            "current_structure": "Neutral"
        }
        
    last_high = swing_highs[0]["price"]
    last_low = swing_lows[0]["price"]
    
    trend = 0 # 1 = Bullish, -1 = Bearish, 0 = Neutral
    
    for i in range(max(swing_highs[0]["index"], swing_lows[0]["index"]) + 1, len(df_ms)):
        close_p = float(closes[i])
        
        active_highs = [sh for sh in swing_highs if sh["index"] < i]
        active_lows = [sl for sl in swing_lows if sl["index"] < i]
        
        if not active_highs or not active_lows:
            continue
            
        recent_sh = active_highs[-1]
        recent_sl = active_lows[-1]
        
        # Bullish break
        if close_p > recent_sh["price"]:
            if trend == 1:
                bos.append({"type": "BOS (Bullish)", "time": times[i], "broken_level": recent_sh["price"], "close": close_p})
            elif trend == -1 or trend == 0:
                choch.append({"type": "CHoCH (Bullish Reversal)", "time": times[i], "broken_level": recent_sh["price"], "close": close_p})
                trend = 1
                
        # Bearish break
        elif close_p < recent_sl["price"]:
            if trend == -1:
                bos.append({"type": "BOS (Bearish)", "time": times[i], "broken_level": recent_sl["price"], "close": close_p})
            elif trend == 1 or trend == 0:
                choch.append({"type": "CHoCH (Bearish Reversal)", "time": times[i], "broken_level": recent_sl["price"], "close": close_p})
                trend = -1

    current_structure = "Bullish" if trend == 1 else ("Bearish" if trend == -1 else "Neutral")
    
    return {
        "swing_highs": swing_highs[-10:],
        "swing_lows": swing_lows[-10:],
        "bos": bos[-5:],
        "choch": choch[-5:],
        "current_structure": current_structure
    }

def detect_liquidity_pools(df, swing_highs, swing_lows, tolerance_pct=0.0015):
    """
    Identifies Equal Highs (EQH/BSL) and Equal Lows (EQL/SSL) representing major liquidity pools,
    detects Session Liquidity levels, and detects BSL/SSL sweeps (including session high/low runs).
    """
    eqh = []
    eql = []
    sweeps = []
    
    # 1. Detect Equal Highs (EQH - BSL Pool)
    for i in range(len(swing_highs)):
        for j in range(i + 1, len(swing_highs)):
            p1 = swing_highs[i]["price"]
            p2 = swing_highs[j]["price"]
            diff = abs(p1 - p2) / max(p1, p2)
            if diff <= tolerance_pct:
                eqh.append({
                    "price": round((p1 + p2) / 2, 5),
                    "points": [swing_highs[i]["time"], swing_highs[j]["time"]]
                })
                
    # 2. Detect Equal Lows (EQL - SSL Pool)
    for i in range(len(swing_lows)):
        for j in range(i + 1, len(swing_lows)):
            p1 = swing_lows[i]["price"]
            p2 = swing_lows[j]["price"]
            diff = abs(p1 - p2) / max(p1, p2)
            if diff <= tolerance_pct:
                eql.append({
                    "price": round((p1 + p2) / 2, 5),
                    "points": [swing_lows[i]["time"], swing_lows[j]["time"]]
                })

    # Get session levels
    sessions = detect_session_liquidity(df)

    # 3. Detect Sweeps (BSL/SSL and Sessions)
    lookback = min(30, len(df))
    closes = df['Close'].values
    highs = df['High'].values
    lows = df['Low'].values
    opens = df['Open'].values
    times = df.index
    
    for i in range(len(df) - lookback, len(df)):
        active_sh = [sh for sh in swing_highs if sh["index"] < i]
        active_sl = [sl for sl in swing_lows if sl["index"] < i]
        
        # Check standard Swing High/Low sweeps
        if active_sh and active_sl:
            recent_sh_price = active_sh[-1]["price"]
            recent_sl_price = active_sl[-1]["price"]
            
            # Bearish Swing Sweep (BSL Sweep)
            if highs[i] > recent_sh_price and closes[i] < recent_sh_price:
                upper_shadow = highs[i] - max(opens[i], closes[i])
                body = abs(closes[i] - opens[i])
                if upper_shadow > 1.2 * body:
                    sweeps.append({
                        "type": "BSL Sweep (Bearish Rejection)",
                        "time": times[i],
                        "swept_level": recent_sh_price,
                        "high": float(highs[i]),
                        "close": float(closes[i])
                    })
                    
            # Bullish Swing Sweep (SSL Sweep)
            if lows[i] < recent_sl_price and closes[i] > recent_sl_price:
                lower_shadow = min(opens[i], closes[i]) - lows[i]
                body = abs(closes[i] - opens[i])
                if lower_shadow > 1.2 * body:
                    sweeps.append({
                        "type": "SSL Sweep (Bullish Rejection)",
                        "time": times[i],
                        "swept_level": recent_sl_price,
                        "low": float(lows[i]),
                        "close": float(closes[i])
                    })
                    
        # Check Session High/Low sweeps
        body = abs(closes[i] - opens[i])
        if body > 0:
            # Asian High sweep (BSL)
            ah = sessions.get("asian_high")
            if ah and highs[i] > ah and closes[i] < ah:
                if (highs[i] - max(opens[i], closes[i])) > 1.2 * body:
                    sweeps.append({
                        "type": "Asian High BSL Sweep (Bearish)",
                        "time": times[i],
                        "swept_level": ah,
                        "high": float(highs[i]),
                        "close": float(closes[i])
                    })
                    
            # Asian Low sweep (SSL)
            al = sessions.get("asian_low")
            if al and lows[i] < al and closes[i] > al:
                if (min(opens[i], closes[i]) - lows[i]) > 1.2 * body:
                    sweeps.append({
                        "type": "Asian Low SSL Sweep (Bullish)",
                        "time": times[i],
                        "swept_level": al,
                        "low": float(lows[i]),
                        "close": float(closes[i])
                    })

            # London High sweep (BSL)
            lh = sessions.get("london_high")
            if lh and highs[i] > lh and closes[i] < lh:
                if (highs[i] - max(opens[i], closes[i])) > 1.2 * body:
                    sweeps.append({
                        "type": "London High BSL Sweep (Bearish)",
                        "time": times[i],
                        "swept_level": lh,
                        "high": float(highs[i]),
                        "close": float(closes[i])
                    })

            # London Low sweep (SSL)
            ll = sessions.get("london_low")
            if ll and lows[i] < ll and closes[i] > ll:
                if (min(opens[i], closes[i]) - lows[i]) > 1.2 * body:
                    sweeps.append({
                        "type": "London Low SSL Sweep (Bullish)",
                        "time": times[i],
                        "swept_level": ll,
                        "low": float(lows[i]),
                        "close": float(closes[i])
                    })

    return {
        "equal_highs": eqh[-3:],
        "equal_lows": eql[-3:],
        "sweeps": sweeps[-5:],
        "session_levels": sessions
    }

def detect_execution_zones(df, lookback=100):
    """
    Detects unmitigated Fair Value Gaps (FVG) and Order Blocks (OB) in the market.
    """
    fvg = []
    
    closes = df['Close'].values
    highs = df['High'].values
    lows = df['Low'].values
    opens = df['Open'].values
    times = df.index
    
    start_idx = max(2, len(df) - lookback)
    
    for i in range(start_idx, len(df)):
        # Bullish FVG
        if opens[i-1] < closes[i-1] and lows[i] > highs[i-2]:
            gap_top = float(lows[i])
            gap_bottom = float(highs[i-2])
            
            mitigated = False
            for j in range(i + 1, len(df)):
                if lows[j] <= gap_bottom:
                    mitigated = True
                    break
                    
            if not mitigated:
                fvg.append({
                    "type": "Bullish FVG",
                    "time": times[i-1],
                    "top": gap_top,
                    "bottom": gap_bottom,
                    "mitigated": False
                })
                
        # Bearish FVG
        elif opens[i-1] > closes[i-1] and highs[i] < lows[i-2]:
            gap_top = float(lows[i-2])
            gap_bottom = float(highs[i])
            
            mitigated = False
            for j in range(i + 1, len(df)):
                if highs[j] >= gap_top:
                    mitigated = True
                    break
                    
            if not mitigated:
                fvg.append({
                    "type": "Bearish FVG",
                    "time": times[i-1],
                    "top": gap_top,
                    "bottom": gap_bottom,
                    "mitigated": False
                })

    bullish_obs_raw, bearish_obs_raw = detect_orderblocks(df, lookback=lookback)
    
    bullish_obs = []
    bearish_obs = []
    
    for ob in bullish_obs_raw:
        try:
            o_start = ob['start']
            # Find index if possible
            start_pos = -1
            for idx, val in enumerate(df.index):
                if val == o_start:
                    start_pos = idx
                    break
            
            if start_pos != -1:
                mitigated = False
                for j in range(start_pos + 2, len(df)):
                    if df['Low'].iloc[j] <= ob['top']:
                        mitigated = True
                        break
                ob['mitigated'] = mitigated
            else:
                ob['mitigated'] = False
            bullish_obs.append(ob)
        except Exception:
            ob['mitigated'] = False
            bullish_obs.append(ob)
            
    for ob in bearish_obs_raw:
        try:
            o_start = ob['start']
            start_pos = -1
            for idx, val in enumerate(df.index):
                if val == o_start:
                    start_pos = idx
                    break
            
            if start_pos != -1:
                mitigated = False
                for j in range(start_pos + 2, len(df)):
                    if df['High'].iloc[j] >= ob['bottom']:
                        mitigated = True
                        break
                ob['mitigated'] = mitigated
            else:
                ob['mitigated'] = False
            bearish_obs.append(ob)
        except Exception:
            ob['mitigated'] = False
            bearish_obs.append(ob)
            
    return {
        "fvg": fvg[-5:],
        "bullish_obs": bullish_obs,
        "bearish_obs": bearish_obs
    }

def calculate_volume_filters(df, window=20):
    """
    Computes Volume Spread Analysis (VSA) states and ATR volatility compression filters.
    """
    if len(df) < window:
        return {"vsa_state": "Neutral", "atr_filter": "Normal Volatility", "atr_value": 0.0, "vol_ma_ratio": 1.0}
        
    df_vol = df.copy()
    
    high_low = df_vol['High'] - df_vol['Low']
    high_close = abs(df_vol['High'] - df_vol['Close'].shift())
    low_close = abs(df_vol['Low'] - df_vol['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    atr = true_range.rolling(14).mean()
    
    df_vol['ATR'] = atr
    df_vol['Volume_MA'] = df_vol['Volume'].rolling(window).mean()
    df_vol['Volume_Std'] = df_vol['Volume'].rolling(window).std()
    
    last_row = df_vol.iloc[-1]
    last_vol = float(last_row['Volume'])
    last_vol_ma = float(last_row['Volume_MA'])
    last_vol_std = float(last_row['Volume_Std']) if not pd.isna(last_row['Volume_Std']) else 1.0
    
    last_range = float(last_row['High'] - last_row['Low'])
    last_atr = float(last_row['ATR']) if not pd.isna(last_row['ATR']) else 1.0
    
    vsa_state = "Normal Volume & Spread"
    if last_vol > last_vol_ma + 2.0 * last_vol_std:
        if last_range > 1.5 * last_atr:
            vsa_state = "Volume Climax (Strong Spread Breakout)"
        else:
            vsa_state = "Volume Churn / Absorption (High Volume, Low Spread)"
    elif last_vol < 0.5 * last_vol_ma:
        if last_range < 0.5 * last_atr:
            vsa_state = "No Demand / No Supply (Volume & Volatility Compression)"
        else:
            vsa_state = "Low Volume Breakout (Weak Participation)"
            
    atr_filter = "Normal Volatility"
    if last_atr > 0 and last_range / last_atr > 1.5:
        atr_filter = "Expansion (High Volatility)"
    elif last_atr > 0 and last_range / last_atr < 0.6:
        atr_filter = "Compression (Low Volatility)"
        
    return {
        "vsa_state": vsa_state,
        "atr_filter": atr_filter,
        "atr_value": round(last_atr, 5),
        "vol_ma_ratio": round(last_vol / last_vol_ma, 2) if last_vol_ma > 0 else 1.0
    }

def plot_chart(df, ticker_symbol, config=None):
    """Creates a comprehensive Plotly chart dynamically based on config."""
    if config is None:
        config = {
            "chart_type": "Svíčkový (Candlestick)",
            "show_sma": True,
            "show_bb": True,
            "show_volume": True,
            "show_macd": True,
            "show_rsi": True,
            "show_ob": False
        }
        
    # Dynamically compute subplots
    specs = [[{"secondary_y": False}]] # Main chart
    row_heights = [0.5] if (config["show_volume"] or config["show_macd"] or config["show_rsi"]) else [1.0]
    
    if config["show_volume"]:
        specs.append([{"secondary_y": False}])
        row_heights.append(0.15)
        
    if config["show_macd"]:
        specs.append([{"secondary_y": False}])
        row_heights.append(0.15)
        
    if config["show_rsi"]:
        specs.append([{"secondary_y": False}])
        row_heights.append(0.2)

    fig = make_subplots(
        rows=len(specs), cols=1, shared_xaxes=True, 
        vertical_spacing=0.03,
        row_heights=row_heights,
        specs=specs
    )

    # 1. Main Chart
    if config["chart_type"] == "Svíčkový (Candlestick)":
        fig.add_trace(go.Candlestick(
            x=df.index,
            open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
            name='Cena', increasing_line_color='#00E676', decreasing_line_color='#F87171'
        ), row=1, col=1)
        fig.update_layout(xaxis_rangeslider_visible=False)
    else:
        fig.add_trace(go.Scatter(
            x=df.index,
            y=df['Close'],
            mode='lines',
            name='Cena',
            line=dict(color='#FBBF24', width=2),
            fill='tozeroy',
            fillcolor='rgba(251, 191, 36, 0.03)' # yellow/gold glow effect
        ), row=1, col=1)
    
    # Overlays on Main Chart
    if config["show_sma"]:
        colors = {'SMA_20': '#38BDF8', 'SMA_50': '#FBBF24', 'SMA_200': '#F87171'}
        for col, color in colors.items():
            if col in df.columns:
                fig.add_trace(go.Scatter(x=df.index, y=df[col], line=dict(color=color, width=1.5, dash='dot'), name=col), row=1, col=1)

    if config["show_bb"] and 'BB_High' in df.columns and 'BB_Low' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['BB_High'], line=dict(color='rgba(255,255,255,0.2)', width=1), name='BB High'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['BB_Low'], fill='tonexty', fillcolor='rgba(255,255,255,0.02)', line=dict(color='rgba(255,255,255,0.2)', width=1), name='BB Low'), row=1, col=1)

    if config.get("show_ob", False):
        bull_obs, bear_obs = detect_orderblocks(df)
        for ob in bull_obs:
            fig.add_shape(type="rect", x0=ob['start'], y0=ob['bottom'], x1=ob['end'], y1=ob['top'],
                          fillcolor="rgba(16, 185, 129, 0.15)", line=dict(color="rgba(16, 185, 129, 0.4)", width=1),
                          layer="below", row=1, col=1)
        for ob in bear_obs:
            fig.add_shape(type="rect", x0=ob['start'], y0=ob['bottom'], x1=ob['end'], y1=ob['top'],
                          fillcolor="rgba(239, 68, 68, 0.15)", line=dict(color="rgba(239, 68, 68, 0.4)", width=1),
                          layer="below", row=1, col=1)

    # Dynamic Subplots assignment
    current_row = 2
    
    if config["show_volume"]:
        colors_vol = ['rgba(0, 230, 118, 0.5)' if close >= open else 'rgba(248, 113, 113, 0.5)' for close, open in zip(df['Close'], df['Open'])]
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=colors_vol, name='Objem', marker_line_width=0), row=current_row, col=1)
        fig.update_yaxes(showgrid=False, zeroline=False, showticklabels=False, row=current_row, col=1)
        current_row += 1

    if config["show_macd"] and 'MACD' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['MACD'], line=dict(color='#38BDF8', width=2), name='MACD'), row=current_row, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MACD_Signal'], line=dict(color='#FBBF24', width=2), name='Signal'), row=current_row, col=1)
        colors_macd = ['rgba(0, 230, 118, 0.6)' if val >= 0 else 'rgba(248, 113, 113, 0.6)' for val in df['MACD_Hist']]
        fig.add_trace(go.Bar(x=df.index, y=df['MACD_Hist'], marker_color=colors_macd, name='MACD Hist', marker_line_width=0), row=current_row, col=1)
        fig.update_yaxes(showgrid=False, zeroline=False, row=current_row, col=1)
        current_row += 1

    if config["show_rsi"] and 'RSI' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='#A78BFA', width=2), name='RSI'), row=current_row, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="rgba(248, 113, 113, 0.5)", row=current_row, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="rgba(0, 230, 118, 0.5)", row=current_row, col=1)
        fig.update_yaxes(showgrid=True, gridcolor="rgba(255,255,255,0.05)", zeroline=False, row=current_row, col=1)
        current_row += 1
        
    # Formatting for Pro Terminal Look
    fig.update_layout(
        title=dict(
            text=f"<b style='color:white;'>{ticker_symbol}</b> <span style='color:#94A3B8; font-size:14px;'>• Institutional Audit Terminal</span>",
            font=dict(size=22),
            x=0.02
        ),
        yaxis_title="",
        xaxis_rangeslider_visible=True, # Added slider
        height=850 if len(specs) > 1 else 600,
        margin=dict(l=50, r=50, t=100, b=50),
        showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        hovermode="x unified",
        hoverlabel=dict(bgcolor="#1E2129", font_size=13, font_family="Inter, sans-serif"),
        font=dict(family="Inter, sans-serif", color="#94A3B8")
    )
    
    # Adding Range Selector Buttons
    fig.update_xaxes(
        rangeselector=dict(
            buttons=list([
                dict(count=1, label="1D", step="day", stepmode="backward"),
                dict(count=5, label="5D", step="day", stepmode="backward"),
                dict(count=1, label="1M", step="month", stepmode="backward"),
                dict(count=1, label="YTD", step="year", stepmode="todate"),
                dict(step="all", label="ALL")
            ]),
            bgcolor="rgba(30, 33, 41, 0.8)",
            activecolor="#00E676",
            font=dict(color="#F8FAFC", size=11)
        ),
        row=len(specs), col=1
    )
    
    # Adaptive Initial Zoom (TradingView Style)
    # If we have a lot of data, zoom into the last 100-150 points for better visibility
    if len(df) > 100:
        last_date = df.index[-1]
        # Show roughly the last ~100 candles
        first_visible_date = df.index[-100]
        fig.update_xaxes(range=[first_visible_date, last_date], row=1, col=1)

    # Pro-style Watermark
    fig.add_annotation(
        text=ticker_symbol.split('=')[0],
        xref="paper", yref="paper",
        x=0.5, y=0.5,
        showarrow=False,
        font=dict(size=120, color="rgba(255, 255, 255, 0.03)", family="Inter, sans-serif"),
        textangle=-20
    )

    # High-Performance Terminal Spikelines and Axis Polish
    for r in range(1, len(specs) + 1):
        fig.update_xaxes(
            showgrid=True, gridcolor="rgba(255,255,255,0.03)", 
            showline=True, linecolor="rgba(255,255,255,0.1)",
            spikemode="across", spikesnap="cursor", spikedash="dot", spikecolor="rgba(255,255,255,0.3)", spikethickness=1,
            row=r, col=1
        )
        fig.update_yaxes(
            showgrid=True, gridcolor="rgba(255,255,255,0.05)", 
            showline=True, linecolor="rgba(255,255,255,0.1)",
            side="right" if r == 1 else "left",
            row=r, col=1
        )
    
    # Hide x-axis labels on all subplots except the last one
    for r in range(1, len(specs)):
        fig.update_xaxes(showgrid=False, zeroline=False, showline=False, showticklabels=False, row=r, col=1)
        
    # The last row
    fig.update_xaxes(title_text="", showgrid=False, zeroline=False, showline=False, showticklabels=True, row=len(specs), col=1)
    
    # Main chart y-axis
    fig.update_yaxes(showgrid=True, gridcolor="rgba(255,255,255,0.15)", zeroline=False, row=1, col=1)
    
    return fig

def plot_dxm_chart(df):
    """Creates a clean ADX Bar Chart colored by trend direction."""
    df_mini = df.tail(14).copy()
    
    fig = go.Figure()
    
    colors = []
    for _, row in df_mini.iterrows():
        if row['ADX'] < 20:
            colors.append('#475569') # Grey for ranging
        elif row['DI_Plus'] > row['DI_Minus']:
            colors.append('#10B981') # Green for Up
        else:
            colors.append('#EF4444') # Red for Down
            
    fig.add_trace(go.Bar(
        x=df_mini.index, 
        y=df_mini['ADX'], 
        marker_color=colors,
        name='ADX (Síla Trendu)',
        marker_line_width=0
    ))
    
    # 20 threshold line for trend confirmation
    fig.add_hline(y=20, line_dash="dash", line_color="rgba(255, 255, 255, 0.2)")

    # Dynamic y-axis range
    max_val = max(df_mini['ADX'].max() + 5, 40)

    fig.update_layout(
        margin=dict(l=0, r=0, t=5, b=0),
        height=100,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", zeroline=True, zerolinecolor="rgba(255,255,255,0.1)", showticklabels=True, range=[0, max_val]),
        font=dict(family="Inter, sans-serif", color="#94A3B8", size=10)
    )
    
    # Current status for header
    last_row = df_mini.iloc[-1]
    if last_row['ADX'] > 25:
        status_text = "UP TREND" if last_row['DI_Plus'] > last_row['DI_Minus'] else "DOWN TREND"
        status_color = "#10B981" if last_row['DI_Plus'] > last_row['DI_Minus'] else "#EF4444"
        icon = "🔥" if last_row['ADX'] > 35 else ("🟢" if status_color == "#10B981" else "🔴")
    elif last_row['ADX'] >= 20:
        status_text = "SLÁBNOUCÍ TREND"
        status_color = "#FBBF24"
        icon = "⚠️"
    else:
        status_text = "RANGING (Bez trendu)"
        status_color = "#94A3B8"
        icon = "⚖️"
        
    status_html = f'<span style="color:{status_color}; font-weight:700; font-size:0.75rem;">{icon} {status_text}</span>'
    
    return fig, status_html

def plot_cot_gauge(title, long_pct, short_pct):
    """Creates a circular Donut chart for COT with Percentage Label."""
    fig = go.Figure(data=[go.Pie(
        labels=['Long', 'Short'],
        values=[long_pct, short_pct],
        hole=0.75,
        marker=dict(colors=['#10B981', '#EF4444']),
        textinfo='none',
        hoverinfo='label+percent'
    )])
    
    fig.add_annotation(
        text=f"{long_pct}%",
        x=0.5, y=0.5, showarrow=False,
        font=dict(size=24, color="white", family="Inter, sans-serif", weight="bold")
    )
    
    fig.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        height=140,
        showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)"
    )
    return fig

def find_available_gemini_models(api_key):
    """Automatically find models available for this API key and cache them."""
    if 'cached_gemini_models' in st.session_state and st.session_state.get('cached_api_key') == api_key:
        return st.session_state.cached_gemini_models

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        available_models = []
        for m in client.models.list():
            if hasattr(m, 'name'):
                available_models.append(m.name)
        
        # Cache the results
        st.session_state.cached_gemini_models = available_models
        st.session_state.cached_api_key = api_key
        return available_models
    except Exception:
        return []


import concurrent.futures

def _do_generate(m, c_prompt, client):
    from google.genai import types
    return client.models.generate_content(
        model=m,
        contents=c_prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        )
    )

def generate_analysis(ticker_symbol, df, fundamentals, news=None):
    """Main AI Engine for trading synthesis with dynamic model selection."""
    api_key, provider = get_api_credentials()
    
    if not api_key:
        return None

    # Summarize Fundamentals
    fund_str = json.dumps(fundamentals, indent=2, ensure_ascii=False) if fundamentals else "Žádná fundamentální data."
    
    # Summarize Technicals (Last available row)
    last_row = df.iloc[-1]
    
    # Get last 10 rows for Price Action context
    recent_ohlc = df[['Open', 'High', 'Low', 'Close', 'Volume']].tail(10).to_string()
    
    tech_str = f"""
    AKTUÁLNÍ HODNOTY:
    Cena (Close): {float(last_row.get('Close', 0)):.2f}
    RSI (14): {float(last_row.get('RSI', 0)):.2f}
    MACD: {float(last_row.get('MACD', 0)):.2f} (Signal: {float(last_row.get('MACD_Signal', 0)):.2f}, Hist: {float(last_row.get('MACD_Hist', 0)):.2f})
    ADX (Trend Strength): {float(last_row.get('ADX', 0)):.2f} (DI+: {float(last_row.get('DI_Plus', 0)):.2f}, DI-: {float(last_row.get('DI_Minus', 0)):.2f})
    Bollinger Bands: High {float(last_row.get('BB_High', 0)):.2f}, Low {float(last_row.get('BB_Low', 0)):.2f}
    SMA 50: {float(last_row.get('SMA_50', 0)):.2f}
    SMA 200: {float(last_row.get('SMA_200', 0)):.2f}
    
    POSLEDNÍCH 10 SVÍČEK (PRICE ACTION):
    {recent_ohlc}
    """

    news_str = ""
    if news:
        news_str = "HLAVNÍ ZPRÁVY Z TRHU:\n" + "\n".join([f"- {n['title']} (Zdroj: {n['publisher']})" for n in news[:5]])

    # Calculate synthetic sentiment context
    l_pct, s_pct = calculate_synthetic_sentiment(df)
    sentiment_context = f"Syntetický sentiment (DXM/COT Model): {l_pct}% Long vs {s_pct}% Short"
    # 1. Multi-Timeframe Trend Bias
    htf_bias, htf_tf = determine_htf_bias(ticker_symbol, st.session_state.tf_interval)
    
    # 2. Market Structure
    struct_data = detect_market_structure_elements(df)
    bos_str = "\n".join([f"- {b['type']} na hladině {b['broken_level']:.5f} ({b['time']})" for b in struct_data["bos"]]) if struct_data["bos"] else "Žádné recentní BOS"
    choch_str = "\n".join([f"- {c['type']} na hladině {c['broken_level']:.5f} ({c['time']})" for c in struct_data["choch"]]) if struct_data["choch"] else "Žádné recentní CHoCH"
    
    struct_summary = f"""
    Aktuální tržní struktura (nižší TF): {struct_data['current_structure']}
    Hlavní trendový bias na vyšším TF ({htf_tf}): {htf_bias}
    Poslední zlom struktury (BOS):
    {bos_str}
    Poslední změna charakteru (CHoCH):
    {choch_str}
    """
    
    # 3. Liquidity Engine & Sessions
    liq_data = detect_liquidity_pools(df, struct_data["swing_highs"], struct_data["swing_lows"])
    eqh_str = "\n".join([f"- EQH (BSL) na hladině {e['price']:.5f} ({', '.join([str(p) for p in e['points']])})" for e in liq_data["equal_highs"]]) if liq_data["equal_highs"] else "Žádné zřejmé EQH (BSL)"
    eql_str = "\n".join([f"- EQL (SSL) na hladině {e['price']:.5f} ({', '.join([str(p) for p in e['points']])})" for e in liq_data["equal_lows"]]) if liq_data["equal_lows"] else "Žádné zřejmé EQL (SSL)"
    sweeps_str = "\n".join([f"- {s['type']} na hladině {s['swept_level']:.5f} (Čas: {s['time']}, High/Low: {s['high'] if 'high' in s else s['low']:.5f})" for s in liq_data["sweeps"]]) if liq_data["sweeps"] else "Žádné recentní vymetení likvidity"
    
    sessions_data = liq_data.get("session_levels", {})
    asian_h_p = f"{sessions_data.get('asian_high')}" if sessions_data.get('asian_high') else "N/A"
    asian_l_p = f"{sessions_data.get('asian_low')}" if sessions_data.get('asian_low') else "N/A"
    london_h_p = f"{sessions_data.get('london_high')}" if sessions_data.get('london_high') else "N/A"
    london_l_p = f"{sessions_data.get('london_low')}" if sessions_data.get('london_low') else "N/A"
    
    liq_summary = f"""
    Buy-Side Liquidity (BSL / EQH):
    {eqh_str}
    Sell-Side Liquidity (SSL / EQL):
    {eql_str}
    Likvidita obchodních seancí (Session Liquidity):
    - Asijské maximum (Asian High BSL): {asian_h_p}
    - Asijské minimum (Asian Low SSL): {asian_l_p}
    - Londýnské maximum (London High BSL): {london_h_p}
    - Londýnské minimum (London Low SSL): {london_l_p}
    Poslední vymetení likvidity (Liquidity Sweeps):
    {sweeps_str}
    """
    
    # 4. Execution Zones
    zone_data = detect_execution_zones(df)
    fvg_str = "\n".join([f"- {f['type']} mezi {f['bottom']:.5f} a {f['top']:.5f} ({f['time']})" for f in zone_data["fvg"] if not f["mitigated"]]) if zone_data["fvg"] else "Všechny FVG v lookbacku zaplněny"
    bull_ob_str = "\n".join([f"- Bullish OB: zóna {ob['bottom']:.5f} - {ob['top']:.5f} ({ob['start']}) [{'Mitigován' if ob['mitigated'] else 'Nemitigován'}]" for ob in zone_data["bullish_obs"]]) if zone_data["bullish_obs"] else "Žádné Bullish OB"
    bear_ob_str = "\n".join([f"- Bearish OB: zóna {ob['bottom']:.5f} - {ob['top']:.5f} ({ob['start']}) [{'Mitigován' if ob['mitigated'] else 'Nemitigován'}]" for ob in zone_data["bearish_obs"]]) if zone_data["bearish_obs"] else "Žádné Bearish OB"
    
    zones_summary = f"""
    Nezaplněné neefektivity (Unmitigated FVGs):
    {fvg_str}
    Order Blocks (OB):
    {bull_ob_str}
    {bear_ob_str}
    """
    
    # 5. Volume & Mathematical Filters
    vol_filters = calculate_volume_filters(df)
    vol_summary = f"""
    VSA Analýza (Volume Spread Analysis): {vol_filters['vsa_state']}
    ATR (14) Volatilitní filtr: {vol_filters['atr_filter']} (ATR hodnota: {vol_filters['atr_value']:.5f})
    Poměr objemu k MA(20): {vol_filters['vol_ma_ratio']}x
    """

    # 6. Golden Zone calculation
    gz_str = ""
    if struct_data["swing_highs"] and struct_data["swing_lows"]:
        last_sh = struct_data["swing_highs"][-1]["price"]
        last_sl = struct_data["swing_lows"][-1]["price"]
        gz_range = abs(last_sh - last_sl)
        
        if struct_data['current_structure'] == "Bullish":
            gz_top = last_sh - 0.5 * gz_range
            gz_bottom = last_sh - 0.786 * gz_range
            gz_opt_start = last_sh - 0.618 * gz_range
            gz_str = f"NÁKUPNÍ RETRACEMENT (Discount): zóna {gz_bottom:.5f} - {gz_opt_start:.5f} (Fibonacci hladiny: 50%={gz_top:.5f}, 61.8%={gz_opt_start:.5f}, 78.6%={gz_bottom:.5f})"
        else:
            gz_bottom = last_sl + 0.5 * gz_range
            gz_top = last_sl + 0.786 * gz_range
            gz_opt_start = last_sl + 0.618 * gz_range
            gz_str = f"PRODEJNÍ RETRACEMENT (Premium): zóna {gz_opt_start:.5f} - {gz_top:.5f} (Fibonacci hladiny: 50%={gz_bottom:.5f}, 61.8%={gz_opt_start:.5f}, 78.6%={gz_top:.5f})"
    else:
        gz_str = "Nedostatek swing bodů pro výpočet."

    sys_prompt = f"""
    Jsi špičkový kvantitativní analytik pro institucionální hedge-fond. Tvým úkolem je provést nekompromisní RIGORÓZNÍ AUDIT instrumentu {ticker_symbol} s využitím metodologie Smart Money Concepts (SMC) a Multi-Timeframe (MTF) analýzy.
    
    ### ZÁVAZNÁ PRAVIDLA PRO ANALÝZU:
    1. **Vážení Fundament vs. Technika**: Fundament má VŽDY vyšší váhu. Pokud jde technický signál (např. RSI nákup) proti silnému negativnímu fundamentu (např. špatné HDP), NESMÍŠ doporučit Long. V takovém případě musíš snížit skóre o 20 % a do analýzy vložit varování: "CONTRARIAN TRADE - HIGH RISK".
    2. **Multi-Timeframe (MTF) Bias a CHoCH**:
       - Vyšší timeframe ({htf_tf}) určuje hlavní směr trhu (SMC Trend Bias: {htf_bias}).
       - Nikdy negeneruj obchody proti hlavnímu vyššímu trendovému biasu (např. SHORT v Bullish trendu), DOKUD na nižším timeframe neproběhne zřetelná změna charakteru trendu (CHoCH - Change of Character).
    3. **Detekce Reakce na Vymetení Likvidity (Direction Bias)**:
       - Sleduj sweeps: Pokud cena vymetla Sell-Side Likviditu (SSL, např. EQL, Asian Low, London Low) a vykazuje rychlou býčí reakci (Bullish Rejection Sweep) směřující k zaplnění FVG gapu výše, vyhodnoť to jako příležitost pro **LONG (Reakce na Sweep)**, i když je celkový trend podle indikátorů klesající.
       - Stejně tak pro vymetení Buy-Side Likvidity (BSL) a návrat dolů: vyhodnoť to jako **SHORT (Reakce na Sweep)**.
    4. **Premium vs. Discount zóny**:
       - **SHORT (Prodej)**: Vstupujeme výhradně v **PREMIUM** zóně (nad 50% Fibonacciho retracementu, ideálně v rozmezí Golden Zone 61.8% - 78.6% celkového impulsu). Chceme prodávat drahé.
       - **LONG (Nákup)**: Vstupujeme výhradně v **DISCOUNT** zóně (pod 50% Fibonacciho retracementu, ideálně v rozmezí Golden Zone 61.8% - 78.6% celkového impulsu). Chceme kupovat levné.
    5. **Pravidla pro přesný ENTRY, SL a TP (SMC Invalidation)**:
       - **ENTRY (Vstup)**: Musí ležet přesně v příslušné zóně (Premium pro Short / Discount pro Long) v Golden Zone a krýt se s unmitigovaným Order Blockem (OB) nebo Fair Value Gapem (FVG).
       - **STOP LOSS (SL)**: Musí být co nejtěsnější pro vysoké RRR. Umísti ho těsně za invalidační úroveň SMC (tj. těsně za opačný konec Order Blocku, FVG zóny nebo swingového HH/LL, který způsobil zlom struktury BOS/CHoCH) s drobným offsetem na spread (např. 1-2 pips). **NIKDY neumisťuj SL na nebo do blízkosti poolů likvidity (EQH/EQL)**, protože ty jsou magnetem pro trh a instituce je záměrně vymete!
       - **TAKE PROFIT (TP)**: Cíle se umisťují těsně PŘED protilehlé pooly likvidity (EQH/EQL, asijské/londýnské high/low), protože tam chceme vybrat zisk z jejich vymetení.
    6. **Pravidlo minimálního RRR >= 1:2.5**:
       - Každý doporučený setup (LONG nebo SHORT) **musí** splňovat poměr Risk-to-Reward (RRR) minimálně **1:2.5** (ideálně 1:3 a více).
       - Pokud po započtení strukturálního Stop Lossu a cílového Take Profitu u nejbližší likvidity nevychází RRR aspoň 1:2.5, **NESMÍŠ** doporučit obchod a musíš vrátit směr `direction: "WAIT"`.
    7. **Ekonomická Logika**: Špatná makro data pro danou zemi (nezaměstnanost, HDP) znamenají TLAK NA OSLABENÍ měny. Nehalucinuj o "prostoru pro nákup" bez jasného fundamentálního důvodu (např. spekulace na pivot banky).
    
    ### VSTUPNÍ DATA:
    - TECHNICKÝ STAV: {tech_str}
    - ADVANCED MARKET STRUCTURE: {struct_summary}
    - LIQUIDITY ENGINE DATA: {liq_summary}
    - EXECUTION ZONES (FVG & OB): {zones_summary}
    - VOLUME & MATHEMATICAL FILTERS: {vol_summary}
    - GOLDEN ZONE FIBONACCI RETRACEMENT: {gz_str}
    - SENTIMENT TRHU: {sentiment_context}
    - FUNDAMENTY: {fund_str}
    - ZPRÁVY: {news_str}
    
    ### POŽADAVKY NA VÝSTUP (PŘÍSNĚ VALIDNÍ JSON V ČEŠTINĚ):
    {{
      "trade_setup": {{
        "direction": "LONG / SHORT / WAIT",
        "entry": "Konkrétní cenová hladina nebo zóna (Pokud WAIT, napiš 'N/A')",
        "tp": "První a druhý cílový profit (Pokud WAIT, napiš 'N/A')",
        "sl": "Hladina invalidace setupu (Pokud WAIT, napiš 'N/A')",
        "rationale": "Důkladné 3-4 věty vysvětlující konfluenci indikátorů, NEBO zdůvodnění proč se má čekat (WAIT).",
        "when_to_ask_again": "Napiš, za jakých podmínek se má uživatel znovu zeptat (např. 'Až cena dosáhne X', 'Za 2 hodiny' atd.). Pokud je to LONG/SHORT, napiš 'N/A'."
      }},
      "golden_zone": {{
        "range": "Vypočtená cenová hladina nebo zóna (např. '1.1410 - 1.1435') odpovídající Fibonacciho 61.8% - 78.6% retracementu",
        "rationale": "Krátké 2-3 věty vysvětlující, proč je tato zóna důležitá a jak na ni cena reaguje vzhledem k trendu a struktuře."
      }},
      "liquidity_setup": {{
        "buy_liquidity_placement": "Kam a jak doporučuješ nastavit nákupní limity/objednávky vzhledem k pools likvidity a EQL (např. 'Nákupní limit na 1.1400 těsně pod EQL pro zachycení stop runu' nebo 'N/A')",
        "sell_liquidity_placement": "Kam a jak doporučuješ nastavit prodejní limity/objednávky vzhledem k pools likvidity a EQH (např. 'Prodejní limit na 1.1480 těsně nad EQH' nebo 'N/A')"
      }},
      "sentiment_score": Číslo od -100 (Bearish) do 100 (Bullish),
      "confidence_pct": Číslo od 0 do 100 (Reálná pravděpodobnost úspěchu dle pravidel výše),
      "technical_analysis": "Rozbor trendu (SMA), volatility (BB) a síly (ADX). Hledej divergence. Min 60 slov.",
      "fundamental_analysis": "Analýza makro kontextu a vlivu zpráv. Musí odpovídat ekonomické logice! Min 60 slov.",
      "synthesis_and_defense": "PROČ JE TENTO SETUP PLATNÝ? Identifikuj pasti na retail. Pokud je setup protitrendový, uveď 'CONTRARIAN TRADE - HIGH RISK'. Min 80 slov."
    }}
    
    Odpovídej POUZE ve formátu JSON v českém jazyce.
    """

    try:
        if provider == "OpenAI":
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-4o",
                response_format={ "type": "json_object" },
                messages=[{"role": "system", "content": "Jsi analytik. Vracíš JSON."}, {"role": "user", "content": sys_prompt}],
                temperature=0.7
            )
            return json.loads(response.choices[0].message.content)

        elif provider == "Gemini":
            import subprocess
            
            model_name = 'gemini-2.5-flash'
            st.session_state.persistent_model_name = model_name
            
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            
            try:
                # Try with JSON mode first
                payload = {
                    "contents": [{"parts": [{"text": sys_prompt}]}],
                    "generationConfig": {
                        "temperature": 0.7,
                        "responseMimeType": "application/json",
                        "maxOutputTokens": 8192
                    }
                }
                
                payload_json = json.dumps(payload)
                res = subprocess.run(
                    ["curl", "-s", "-X", "POST", "-H", "Content-Type: application/json", "-d", payload_json, url],
                    capture_output=True,
                    text=True,
                    timeout=45.0
                )
                
                if res.returncode != 0:
                    raise Exception(f"Curl failed with return code {res.returncode}: {res.stderr}")
                    
                resp_json = json.loads(res.stdout)
                if "error" in resp_json:
                    err_msg = resp_json["error"].get("message", str(resp_json["error"]))
                    raise Exception(f"Gemini API Error: {err_msg}")
                    
                raw_text = resp_json["candidates"][0]["content"]["parts"][0]["text"]
                
                # Verify JSON parses correctly in first try, otherwise raise exception to trigger fallback
                text = raw_text
                if "```json" in text: text = text.split("```json")[1].split("```")[0].strip()
                elif "```" in text: text = text.split("```")[1].split("```")[0].strip()
                
                res_json = json.loads(text)
                return res_json
            except Exception as e:
                # Fallback to plain text
                try:
                    payload["generationConfig"] = {
                        "temperature": 0.7,
                        "maxOutputTokens": 8192
                    } # Remove JSON mode
                    payload_json = json.dumps(payload)
                    res = subprocess.run(
                        ["curl", "-s", "-X", "POST", "-H", "Content-Type: application/json", "-d", payload_json, url],
                        capture_output=True,
                        text=True,
                        timeout=45.0
                    )
                    
                    if res.returncode != 0:
                        raise Exception(f"Curl failed with return code {res.returncode}: {res.stderr}")
                        
                    resp_json = json.loads(res.stdout)
                    if "error" in resp_json:
                        err_msg = resp_json["error"].get("message", str(resp_json["error"]))
                        raise Exception(f"Gemini API Error: {err_msg}")
                        
                    raw_text = resp_json["candidates"][0]["content"]["parts"][0]["text"]
                    
                    text = raw_text
                    if "```json" in text: text = text.split("```json")[1].split("```")[0].strip()
                    elif "```" in text: text = text.split("```")[1].split("```")[0].strip()
                    
                    start = text.find("{")
                    end = text.rfind("}")
                    if start != -1 and end != -1:
                        text = text[start:end+1]
                        
                    res_json = json.loads(text)
                    return res_json
                except Exception as fallback_e:
                    last_err = str(fallback_e)
                    if "429" in last_err or "quota" in last_err.lower() or "exhausted" in last_err.lower():
                        st.error("⚠️ AI Limit: Google vás dočasně omezil (Too Many Requests). Počkejte minutu nebo použijte jiný klíč.")
                    with open("scratch/error.log", "w") as f:
                        f.write(f"Gemini API Error Trace: {last_err}\nText: {raw_text if 'raw_text' in locals() else ''}")
                    return {"error": f"Gemini API Error: {last_err}"}
            
    except Exception as e:
        st.error(f"Chyba AI: {e}")
        return {}

def chat_with_ai(prompt, analysis_data):
    """Allows follow-up questions about the current analysis."""
    api_key, provider = get_api_credentials()
    if not api_key: return "Chybí API klíč."
    
    context = f"Analýza: {json.dumps(analysis_data, ensure_ascii=False)}"
    
    try:
        if provider == "OpenAI":
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            resp = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": f"Jsi analytik. Odpovídej k věci na základě této analýzy: {context}"},
                    {"role": "user", "content": prompt}
                ]
            )
            return resp.choices[0].message.content
        else:
            from google import genai
            client = genai.Client(api_key=api_key)
            model_name = "gemini-2.5-flash"
            resp = client.models.generate_content(
                model=model_name,
                contents=f"Kontext: {context}\n\nUživatel se ptá: {prompt}"
            )
            return resp.text
    except Exception as e:
        return f"Chyba chatu: {e}"


# --- UI Layout ---

with st.sidebar:
    st.markdown("""
<div style="padding: 10px 0 30px 0; border-bottom: 1px solid rgba(255,255,255,0.05); margin-bottom: 30px;">
    <div style="display: flex; align-items: center; gap: 12px;">
        <div style="width: 38px; height: 38px; background: linear-gradient(135deg, #00E676 0%, #00C853 100%); border-radius: 10px; display: flex; align-items: center; justify-content: center; box-shadow: 0 0 20px rgba(0, 230, 118, 0.3);">
            <span style="color: #0F172A; font-size: 20px; font-weight: 800;">A</span>
        </div>
        <div>
            <div style="font-size: 16px; font-weight: 800; color: #F8FAFC; line-height: 1; letter-spacing: -0.5px;">TRADING</div>
            <div style="font-size: 10px; color: #00E676; font-weight: 600; letter-spacing: 2px;">ANALYZER</div>
        </div>
    </div>
</div>
<br>
""", unsafe_allow_html=True)

    with st.expander("📚 Vysvětlivky pojmů", expanded=True):
        st.markdown('<div style="font-size:0.85rem; color:#94A3B8;"><b>Score:</b> AI ohodnocení situace od -100 do 100.<br><br><b>DXM:</b> Měří tržní sílu. <span style="color:#10B981;">Zelená</span> = Nákupy, <span style="color:#EF4444;">Červená</span> = Prodeje.<br><br><b>COT:</b> Commitment of Traders. Ukazuje naklonění kapitálu institucí.</div>', unsafe_allow_html=True)

    # --- Sidebar Navigation ---
    st.markdown("### 🧭 Navigace")
    if st.button("📊 Dashboard", use_container_width=True, type="primary" if st.session_state.current_page == "Dashboard" else "secondary"):
        st.session_state.current_page = "Dashboard"
        st.rerun()
    if st.button("⚙️ Nastavení", use_container_width=True, type="primary" if st.session_state.current_page == "Settings" else "secondary"):
        st.session_state.current_page = "Settings"
        st.rerun()
    
    st.divider()

    # --- Global Sidebar Inputs (Always Defined) ---
    with st.expander("⚙️ Konfigurace Symbolů", expanded=st.session_state.current_page == "Dashboard"):
        ticker = st.text_input("Aktivní Symbol:", value="EURUSD=X", help="Zadejte symbol z Yahoo Finance (např. EURUSD=X).")
        dxm_ticker = st.text_input("DXM Symbol:", value=st.session_state.dxm_symbol)
        cot_ticker = st.text_input("COT Symbol:", value=st.session_state.cot_symbol)

    if st.session_state.current_page == "Dashboard":
        # --- Dashboard specific sidebar tools ---
        with st.expander("🕒 Timeframe & Engine", expanded=True):
            # Link sidebar tf to session state
            tf_options = ["1m", "5m", "15m", "30m", "1h", "1d", "1wk", "1mo"]
            current_tf_idx = tf_options.index(st.session_state.tf_interval) if st.session_state.tf_interval in tf_options else 5
            
            selected_interval = st.selectbox("Interval:", tf_options, index=current_tf_idx)
            if selected_interval != st.session_state.tf_interval:
                st.session_state.tf_interval = selected_interval
                if selected_interval == "1m": st.session_state.tf_period = "7d"
                elif selected_interval in ["5m", "15m", "30m"]: st.session_state.tf_period = "60d"
                elif selected_interval == "1h": st.session_state.tf_period = "2y"
                elif selected_interval == "1mo": st.session_state.tf_period = "max"
                else: st.session_state.tf_period = "5y"
                st.rerun()
            
        with st.expander("📈 Visual Settings", expanded=False):
            chart_type = st.radio("Cenový vývoj:", ["Svíčkový (Candlestick)", "Line Glow (Moderní)"], index=0)
            col_set1, col_set2 = st.columns(2)
            with col_set1:
                show_sma = st.checkbox("SMA", value=False)
                show_bb = st.checkbox("B. Bands", value=False)
                show_volume = st.checkbox("Volume", value=True)
            with col_set2:
                show_macd = st.checkbox("MACD", value=False)
                show_rsi = st.checkbox("RSI", value=False)
                show_ob = st.checkbox("OB", value=False)
            
            chart_config = {
                "chart_type": chart_type,
                "show_sma": show_sma,
                "show_bb": show_bb,
                "show_volume": show_volume,
                "show_macd": show_macd,
                "show_rsi": show_rsi,
                "show_ob": show_ob
            }

        if st.session_state.analysis_history:
            with st.expander("📂 Historie Analýz", expanded=False):
                for i, hist in enumerate(reversed(st.session_state.analysis_history)):
                    if st.button(f"{hist['ticker']} ({hist['tf']}) - {hist['time']}", key=f"hist_{i}", use_container_width=True):
                        st.session_state.current_ticker = hist['ticker']
                        st.session_state.tf_interval = hist['tf']
                        
                        # Recalculate tf_period
                        if hist['tf'] == "1m": st.session_state.tf_period = "7d"
                        elif hist['tf'] in ["5m", "15m", "30m"]: st.session_state.tf_period = "60d"
                        elif hist['tf'] == "1h": st.session_state.tf_period = "2y"
                        elif hist['tf'] == "1mo": st.session_state.tf_period = "max"
                        else: st.session_state.tf_period = "5y"
                        
                        st.session_state.current_analysis_ticker = f"{hist['ticker']}_{hist['tf']}"
                        st.session_state.ai_analysis_data = hist['data']
                        st.rerun()

        generate_btn = st.button("Spustit Analyzer", type="primary", use_container_width=True)
    else:
        st.info("💡 Upravte globální nastavení v hlavní sekci.")
        generate_btn = False

# --- Main Area Rendering ---
if st.session_state.current_page == "Dashboard":

    # 1. Dashboard Header & Health Status
    col_status1, col_status2 = st.columns([0.65, 0.35])
    with col_status1:
        st.markdown(f'<div style="display:flex; align-items:baseline; gap: 15px; margin-bottom: 5px;"><h1 style="margin:0; padding:0; line-height: 1; font-size: 2.2rem;">Dashboard</h1><span style="color:#94A3B8; font-size: 0.9rem;">v3.1 Master</span></div><div style="display:flex; gap: 15px; margin-bottom: 20px;"><span style="color:#10B981; font-size:0.75rem;"><span class="pulse-dot"></span> System Online</span><span style="color:#38BDF8; font-size:0.75rem;">● Data Feed: OK</span><span style="color:{"#10B981" if (get_api_credentials()[0] and len(get_api_credentials()[0]) > 5) else "#EF4444"}; font-size:0.75rem;">● AI Engine: {"Online" if (get_api_credentials()[0] and len(get_api_credentials()[0]) > 5) else "Offline"}</span></div>', unsafe_allow_html=True)

    with col_status2:
        # Dynamický výpočet časů (NYC, LON, TOK)
        utc_now = datetime.now(pytz.utc)
        ny_time = utc_now.astimezone(pytz.timezone('America/New_York')).strftime('%H:%M')
        lon_time = utc_now.astimezone(pytz.timezone('Europe/London')).strftime('%H:%M')
        tok_time = utc_now.astimezone(pytz.timezone('Asia/Tokyo')).strftime('%H:%M')
    
        st.markdown(f'<div style="text-align: right; margin-top: 10px; display: flex; justify-content: flex-end; gap: 8px;"><div class="time-badge">NYC <b>{ny_time}</b></div><div class="time-badge">LON <b>{lon_time}</b></div><div class="time-badge">TOK <b>{tok_time}</b></div></div>', unsafe_allow_html=True)

    # 2. Main Grid Layout Data Fetch
    if ticker:
        # Unify timeframe from session state
        c_period = st.session_state.tf_period
        c_interval = st.session_state.tf_interval
    
        df_raw = fetch_data(ticker, c_period, c_interval)
        if df_raw.empty:
            st.error(f"Nelze načíst data pro ticker '{ticker}' (Period: {c_period}, Interval: {c_interval}).")
        else:
            df_processed = calculate_indicators(df_raw)
        
            # --- Top KPI Row ---
            kpi_col1, kpi_col2, kpi_col3 = st.columns([1, 1, 1], gap="medium")

            with kpi_col1:
                with st.container(border=True):
                    current_price = float(df_processed['Close'].iloc[-1])
                    prev_price = float(df_processed['Close'].iloc[-2]) if len(df_processed) > 1 else current_price
                    price_change = float(current_price - prev_price)
                    pct_change = (price_change / prev_price) * 100 if prev_price != 0 else 0
                
                    color = "#10B981" if price_change >= 0 else "#EF4444"
                    arrow = "▲" if price_change >= 0 else "▼"
                
                    # Adaptive rounding based on price magnitude
                    if current_price >= 1000:
                        price_fmt = f"${float(current_price):,.2f}"
                        change_fmt = f"${abs(price_change):.2f}"
                    elif current_price >= 10:
                        price_fmt = f"${float(current_price):,.3f}"
                        change_fmt = f"${abs(price_change):.3f}"
                    elif current_price >= 0.01:
                        price_fmt = f"${float(current_price):,.5f}"
                        change_fmt = f"${abs(price_change):.5f}"
                    else:
                        price_fmt = f"${current_price:,.6f}"
                        change_fmt = f"${abs(price_change):.6f}"

                    st.markdown(f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 10px;"><h3 style="margin:0; font-size: 1.2rem;">Cena aktiva</h3><div style="font-size: 0.8rem; color:#94A3B8;">{ticker}</div></div><div style="padding: 6px 0;"><div style="font-size: 2.2rem; font-weight: 700; color: #F8FAFC; line-height: 1.1;">{price_fmt}</div><div style="font-size: 1.0rem; color: {color}; font-weight: 600; margin-top: 5px;">{arrow} {change_fmt} ({abs(pct_change):.2f}%)</div></div>', unsafe_allow_html=True)

            with kpi_col2:
                # --- DXM WIDGET ---
                with st.container(border=True):
                    if dxm_ticker != ticker:
                        df_dxm = calculate_indicators(fetch_data(dxm_ticker, "3mo"))
                    else:
                        df_dxm = df_processed
                
                    if not df_dxm.empty and 'DI_Plus' in df_dxm.columns:
                        fig_dxm, status_html = plot_dxm_chart(df_dxm)
                        st.markdown(f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 5px;"><h3 style="margin:0; font-size: 1.2rem;">DXM</h3><div style="font-size: 0.8rem;">{status_html}</div></div>', unsafe_allow_html=True)
                        fig_dxm.update_layout(height=110, margin=dict(l=0, r=0, t=0, b=0))
                        st.plotly_chart(fig_dxm, use_container_width=True, config={'displayModeBar': False})
                    else:
                        st.markdown(f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 5px;"><h3 style="margin:0; font-size: 1.2rem;">DXM</h3></div>', unsafe_allow_html=True)
                        st.warning("Data pro DXM nejsou k dispozici.")

            with kpi_col3:
                # --- COT WIDGET ---
                with st.container(border=True):
                    if cot_ticker != ticker:
                        df_cot_base = calculate_indicators(fetch_data(cot_ticker, "3mo"))
                    else:
                        df_cot_base = df_processed
                
                    if not df_cot_base.empty:
                        synth_long_pct, synth_short_pct = calculate_synthetic_sentiment(df_cot_base)
                    
                        st.markdown(f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 0px;"><h3 style="margin:0; font-size: 1.2rem;">COT</h3><div style="font-size: 0.8rem;"><span style="color:#10B981;">🟢 {synth_long_pct}%</span> &nbsp;&nbsp;<span style="color:#EF4444;">🔴 {synth_short_pct}%</span></div></div>', unsafe_allow_html=True)
                    
                        fig_cot = plot_cot_gauge("COT", synth_long_pct, synth_short_pct)
                        fig_cot.update_layout(height=115, margin=dict(l=0, r=0, t=0, b=0))
                        st.plotly_chart(fig_cot, use_container_width=True, config={'displayModeBar': False})
                    else:
                        st.warning("Data pro COT nejsou k dispozici.")

            # --- Main Chart Section ---
            st.markdown("<br>", unsafe_allow_html=True)
        
            with st.expander("📈 Graf trhu", expanded=True):
                # TradingView-Style Timeframe Toolbar
                tftimeframes = ["1m", "5m", "15m", "30m", "1h", "1d", "1wk", "1mo"]
                cols_tf = st.columns(len(tftimeframes))
                for i, tf in enumerate(tftimeframes):
                    is_active = st.session_state.tf_interval == tf
                    btn_label = f"**{tf}**" if is_active else tf
                    if cols_tf[i].button(btn_label, key=f"tf_btn_{tf}", use_container_width=True):
                        st.session_state.tf_interval = tf
                        if tf == "1m": st.session_state.tf_period = "7d"
                        elif tf in ["5m", "15m", "30m"]: st.session_state.tf_period = "60d"
                        elif tf == "1h": st.session_state.tf_period = "2y"
                        else: st.session_state.tf_period = "1y"
                        st.rerun()

                # Chart Display
                fig = plot_chart(df_processed, ticker, chart_config)
                st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

            # --- Advanced Market Structure UI Widget ---
            with st.expander("🔍 Pokročilá Tržní Struktura & Likvidita", expanded=False):
                st.markdown("<h4 style='margin-top:0;'>Strukturální a objemová diagnostika</h4>", unsafe_allow_html=True)
                
                # Calculate metrics
                ms_elements = detect_market_structure_elements(df_processed)
                lp_elements = detect_liquidity_pools(df_processed, ms_elements["swing_highs"], ms_elements["swing_lows"])
                ez_elements = detect_execution_zones(df_processed)
                v_filters = calculate_volume_filters(df_processed)
                
                col_ui1, col_ui2, col_ui3 = st.columns(3)
                with col_ui1:
                    st.markdown("<b style='font-size:1.1rem;'>Tržní struktura</b>", unsafe_allow_html=True)
                    s_color = "#10B981" if ms_elements["current_structure"] == "Bullish" else ("#EF4444" if ms_elements["current_structure"] == "Bearish" else "#64748B")
                    st.markdown(f"Struktura: <span style='background:{s_color}22; color:{s_color}; padding:3px 8px; border-radius:4px; font-weight:bold;'>{ms_elements['current_structure']}</span>", unsafe_allow_html=True)
                    
                    # Fetch HTF trend bias
                    htf_bias, htf_tf = determine_htf_bias(ticker, st.session_state.tf_interval)
                    h_color = "#10B981" if "Bullish" in htf_bias else ("#EF4444" if "Bearish" in htf_bias else "#64748B")
                    st.markdown(f"HTF Bias ({htf_tf}): <span style='color:{h_color}; font-weight:bold;'>{htf_bias}</span>", unsafe_allow_html=True)

                    st.write("**Poslední zlom (BOS):**")
                    if ms_elements["bos"]:
                        last_b = ms_elements["bos"][-1]
                        st.markdown(f"<span style='color:#38BDF8;'>{last_b['type']}</span> na `{last_b['broken_level']:.5f}`", unsafe_allow_html=True)
                    else:
                        st.write("Žádný v lookbacku")
                        
                    st.write("**Změna charakteru (CHoCH):**")
                    if ms_elements["choch"]:
                        last_c = ms_elements["choch"][-1]
                        st.markdown(f"<span style='color:#FBBF24;'>{last_c['type']}</span> na `{last_c['broken_level']:.5f}`", unsafe_allow_html=True)
                    else:
                        st.write("Žádná v lookbacku")
                
                with col_ui2:
                    st.markdown("<b style='font-size:1.1rem;'>Likvidita & Bloky</b>", unsafe_allow_html=True)
                    
                    st.write("**Seance (Session Liquidity):**")
                    s_levels = lp_elements.get("session_levels", {})
                    if s_levels.get("asian_high"):
                        st.markdown(f"🌏 **Asian Range:** `{s_levels.get('asian_low'):.5f} - {s_levels.get('asian_high'):.5f}`")
                    if s_levels.get("london_high"):
                        st.markdown(f"🌍 **London Range:** `{s_levels.get('london_low'):.5f} - {s_levels.get('london_high'):.5f}`")

                    st.write("**Pools likvidity (EQH/EQL):**")
                    eq_found = False
                    if lp_elements["equal_highs"]:
                        st.markdown(f"🟢 **EQH (BSL):** `{lp_elements['equal_highs'][-1]['price']:.5f}`")
                        eq_found = True
                    if lp_elements["equal_lows"]:
                        st.markdown(f"🔴 **EQL (SSL):** `{lp_elements['equal_lows'][-1]['price']:.5f}`")
                        eq_found = True
                    if not eq_found:
                        st.write("Žádné významné EQH/EQL")
                        
                    st.write("**Order Blocks (Aktivní):**")
                    active_obs = [ob for ob in ez_elements["bullish_obs"] + ez_elements["bearish_obs"] if not ob.get("mitigated", False)]
                    if active_obs:
                        for ob in active_obs[-2:]:
                            ob_type = "Bullish" if ob in ez_elements["bullish_obs"] else "Bearish"
                            ob_color = "#10B981" if ob_type == "Bullish" else "#EF4444"
                            st.markdown(f"<span style='color:{ob_color};'>{ob_type} OB</span>: `{ob['bottom']:.5f} - {ob['top']:.5f}`", unsafe_allow_html=True)
                    else:
                        st.write("Žádné neotestované OB")
                        
                with col_ui3:
                    st.markdown("<b style='font-size:1.1rem;'>Neefektivity & Objem</b>", unsafe_allow_html=True)
                    st.write("**Fair Value Gaps (FVG):**")
                    active_fvgs = [f for f in ez_elements["fvg"] if not f["mitigated"]]
                    if active_fvgs:
                        for fvg in active_fvgs[-2:]:
                            fvg_color = "#10B981" if "Bullish" in fvg["type"] else "#EF4444"
                            st.markdown(f"<span style='color:{fvg_color};'>{fvg['type']}</span>: `{fvg['bottom']:.5f} - {fvg['top']:.5f}`", unsafe_allow_html=True)
                    else:
                        st.write("Všechny FVG zaplněny")
                        
                    st.write("**Objem a ATR:**")
                    st.markdown(f"VSA stav: **{v_filters['vsa_state']}**")
                    st.markdown(f"ATR stav: **{v_filters['atr_filter']}** (ATR: `{v_filters['atr_value']:.5f}`)")

            # --- Technical Health Check Panel ---
            tech_signals = get_technical_signals(df_processed)
            if tech_signals:
                st.markdown("<div style='margin-top: 25px;'></div>", unsafe_allow_html=True)
                t_cols = st.columns(4)
                for i, (name, data) in enumerate(tech_signals.items()):
                    with t_cols[i]:
                        st.markdown(f'<div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.05); padding: 12px; border-radius: 10px; text-align: center;"><div style="font-size: 0.7rem; color: #94A3B8; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 5px;">{name}</div><div style="font-size: 1rem; font-weight: 700; color: {data["color"]};">{data["val"]}</div><div style="font-size: 0.65rem; color: #475569; margin-top: 2px;">{data["status"]}</div></div>', unsafe_allow_html=True)

            # --- News Feed Section ---
            news = fetch_news(ticker)
            if news:
                st.markdown("<h3 style='font-size: 1.2rem; margin-top: 20px;'>📰 Aktuální tržní zprávy</h3>", unsafe_allow_html=True)
                news_cols = st.columns(len(news))
                for i, article in enumerate(news):
                    with news_cols[i]:
                        with st.container(border=True):
                            st.markdown(f'<div style="font-size: 0.8rem; color: #94A3B8; margin-bottom: 5px;">{article["publisher"]}</div><div style="font-size: 0.9rem; font-weight: 600; min-height: 45px; margin-bottom: 10px;"><a href="{article["link"]}" target="_blank" style="text-decoration: none; color: #F8FAFC;">{article["title"][:60]}{"..." if len(article["title"]) > 60 else ""}</a></div>', unsafe_allow_html=True)

            # --- AI Generated Trade Ideas Header ---
            ai_info = st.session_state.get('ai_analysis_data')
            conf_html = ""
            if ai_info:
                c_pct = ai_info.get('confidence_pct', 50)
                conf_html = f'<div style="text-align: right;"><div style="font-size: 0.7rem; color: #94A3B8; text-transform: uppercase; letter-spacing: 1px;">Confidence</div><div style="font-size: 1.3rem; font-weight: 800; color: #38BDF8;">{c_pct}%</div></div>'

            st.markdown(f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 20px; margin-top: 30px;"><h2 style="margin:0; font-size: 1.4rem;">AI obchodní nápady</h2><div style="display:flex; align-items:center; gap:20px;"><span style="background: rgba(255,255,255,0.05); padding: 5px 12px; border-radius: 8px; font-weight:600; font-size:0.9rem; color:#00E676;">{ticker} • {st.session_state.tf_interval}</span>{conf_html}</div></div>', unsafe_allow_html=True)

            # Uchování analýzy ve stavu (aby nezmizela při kliknutí na expander)
            if 'ai_analysis_data' not in st.session_state:
                st.session_state.ai_analysis_data = None
            if 'current_analysis_ticker' not in st.session_state:
                st.session_state.current_analysis_ticker = None

            if generate_btn:
                api_key, ai_provider = get_api_credentials()
                if not api_key:
                    st.error("Zadejte prosím API klíč do .streamlit/secrets.toml pro spuštění AI analýzy.")
                else:
                    status = st.status("🧠 AI analyzuje trh...", expanded=True)
                    try:
                        # 1. Reuse existing fundamentals (or fetch if missing)
                        step1 = status.empty()
                        step1.markdown("⏳ 🏢 Získávám fundamentální ukazatele...")
                        try:
                            fundamentals = fetch_fundamentals(ticker)
                            step1.markdown("✅ 🏢 Získávám fundamentální ukazatele...")
                        except Exception:
                            fundamentals = {}
                            step1.markdown("⚠️ 🏢 Fundamenty nedostupné (pokračuji).")

                        # 2. Reuse existing news if available, or fetch
                        step2 = status.empty()
                        step2.markdown("⏳ 📰 Prohledávám tržní zprávy...")
                        if 'news' not in locals() or not news:
                            try:
                                news_context = fetch_news(ticker)
                                step2.markdown("✅ 📰 Prohledávám tržní zprávy...")
                            except Exception:
                                news_context = []
                                step2.markdown("⚠️ 📰 Tržní zprávy nedostupné (pokračuji).")
                        else:
                            news_context = news
                            step2.markdown("✅ 📰 Prohledávám tržní zprávy...")

                        # 3. AI Analysis
                        step3 = status.empty()
                        step3.markdown("⏳ ⚡ Generuji finální posudek a setup... (Tento model může zpracovávat data 1-2 minuty, PROSÍM NEOBNOVUJTE STRÁNKU)")
                        import time
                        t0 = time.time()
                        ai_data = generate_analysis(ticker, df_processed, fundamentals, news=news_context)
                        if ai_data and "error" not in ai_data:
                            step3.markdown("✅ ⚡ Generuji finální posudek a setup...")
                        t1 = time.time()
                        with open("scratch/success.log", "a") as f:
                            f.write(f"[{time.strftime('%H:%M:%S')}] Generování trvalo {t1-t0:.1f}s. Keys: {list(ai_data.keys()) if isinstance(ai_data, dict) else 'Not a dict'}\n")
                        
                        if ai_data and "error" not in ai_data:
                            status.update(label="✅ Analýza dokončena!", state="complete", expanded=False)
                            st.session_state.ai_analysis_data = ai_data
                            st.session_state.current_analysis_ticker = f"{ticker}_{st.session_state.tf_interval}"
                            st.session_state.chat_history = [] 
                        
                            # Save to History
                            st.session_state.analysis_history.append({
                                "ticker": ticker,
                                "tf": st.session_state.tf_interval,
                                "time": datetime.now().strftime("%H:%M:%S"),
                                "data": ai_data,
                                "chat": []
                            })
                            if len(st.session_state.analysis_history) > 10:
                                st.session_state.analysis_history.pop(0)
                        else:
                            status.update(label="❌ AI selhala", state="error", expanded=False)
                            st.error(ai_data.get("error", "Neznámá chyba při generování analýzy."))
                            st.session_state.ai_analysis_data = None
                                
                    except Exception as e:
                        if "429" in str(e) or "Too Many Requests" in str(e):
                            st.error("🚦 Limit požadavků vyčerpán. Yahoo Finance nebo AI blokuje další dotazy. Zkuste to za minutu.")
                        else:
                            st.error(f"Při generování analýzy nastala chyba: {e}")

            # Zobrazení AI dat ze session_state
            current_context = f"{ticker}_{st.session_state.tf_interval}"
            if st.session_state.ai_analysis_data and st.session_state.current_analysis_ticker == current_context:
                ai_data = st.session_state.ai_analysis_data
                
                # Robustness check: Ensure ai_data is a dictionary
                if isinstance(ai_data, str):
                    try:
                        import json
                        ai_data = json.loads(ai_data)
                    except Exception:
                        ai_data = {}
                if not isinstance(ai_data, dict):
                    ai_data = {}
                    
                sub_col1, sub_col2 = st.columns([1, 1], gap="medium")
            
                with sub_col1:
                    with st.container(border=True):
                        # --- Vizualizace (Gauge Chart) ---
                        try:
                            score = float(ai_data.get("sentiment_score", 0))
                        except Exception:
                            score = 0.0
                            
                        if "sentiment_label" in ai_data:
                            label = str(ai_data["sentiment_label"])
                        else:
                            label = "Bullish" if score >= 20 else ("Bearish" if score <= -20 else "Neutral")
                    
                        fig_gauge = go.Figure(go.Indicator(
                            mode = "gauge+number",
                            value = score,
                            number = {'font': {'size': 85, 'color': 'white'}},
                            domain = {'x': [0, 1], 'y': [0, 1]},
                            title = {'text': f"<span style='font-size: 1rem; color: #94A3B8'>Tržní Sentiment</span><br><b style='font-size: 1.5rem; color: {'#10B981' if score > 10 else '#EF4444' if score < -10 else '#F59E0B'}'>{label}</b>"},
                            gauge = {
                                'axis': {'range': [-100, 100], 'tickwidth': 0, 'visible': False},
                                'bar': {'color': "rgba(0,0,0,0)", 'thickness': 0},
                                'bgcolor': "rgba(255,255,255,0.05)",
                                'borderwidth': 0,
                                'steps': [
                                    {'range': [-100, -30], 'color': "#EF4444"},
                                    {'range': [-30, 30], 'color': "#F59E0B"},
                                    {'range': [30, 100], 'color': "#10B981"}],
                                'threshold': {
                                    'line': {'color': "#FBBF24", 'width': 4},
                                    'thickness': 0.8,
                                    'value': score}
                            }
                        ))
                        fig_gauge.update_layout(
                            height=220, 
                            margin=dict(t=60, b=0, l=10, r=10), 
                            paper_bgcolor="rgba(0,0,0,0)", 
                            font={'color': "white"}
                        )
                        st.plotly_chart(fig_gauge, use_container_width=True, config={'displayModeBar': False})

                with sub_col2:
                    with st.container(border=True):
                        st.markdown("<h3 style='margin-top:0; margin-bottom:15px; font-size: 1.1rem;'>Score overview</h3>", unsafe_allow_html=True)
                    
                        setup = ai_data.get("trade_setup", {})
                        if isinstance(setup, str):
                            try: setup = json.loads(setup)
                            except Exception: setup = {}
                        if not isinstance(setup, dict): setup = {}
                        
                        direction = str(setup.get("direction", "N/A"))
                        dir_lower = direction.lower()
                        
                        dir_class = "glow-long" if "long" in dir_lower else ("glow-short" if "short" in dir_lower else "")
                        dot_class = "pulse-dot" if "long" in dir_lower else ("pulse-dot short" if "short" in dir_lower else "pulse-dot")

                        if direction == "WAIT":
                            st.markdown(f'<div style="display:flex; justify-content:space-between; padding: 10px 0; border-bottom: 1px solid #1E2129;"><span style="color:#94A3B8; font-size:0.9rem;">Direction Bias</span><span style="color:#F59E0B; font-weight:600;"><span class="pulse-dot" style="background-color:#F59E0B; box-shadow:0 0 8px #F59E0B;"></span>WAIT (No Trade)</span></div><div style="padding: 20px 10px; text-align: center; color: #94A3B8; line-height: 1.5;"><b>Proč čekat:</b> {setup.get("rationale", "Nedostatek jasných signálů.")}<br><br><span style="color: #38BDF8; font-weight: 600;">Kdy se zeptat znovu:</span> {setup.get("when_to_ask_again", "Zkuste to později.")}</div>', unsafe_allow_html=True)
                        else:
                            st.markdown(f'<div style="display:flex; justify-content:space-between; padding: 10px 0; border-bottom: 1px solid #1E2129;"><span style="color:#94A3B8; font-size:0.9rem;">Direction Bias</span><span class="{dir_class}" style="font-weight:600;"><span class="{dot_class}"></span>{direction}</span></div><div style="display:flex; justify-content:space-between; padding: 10px 0; border-bottom: 1px solid #1E2129;"><span style="color:#94A3B8; font-size:0.9rem;">Entry Point</span><span style="font-weight:600;">{setup.get("entry", "N/A")}</span></div><div style="display:flex; justify-content:space-between; padding: 10px 0; border-bottom: 1px solid #1E2129;"><span style="color:#94A3B8; font-size:0.9rem;">Take Profit</span><span style="color:#00E676; font-weight:600;">{setup.get("tp", "N/A")}</span></div><div style="display:flex; justify-content:space-between; padding: 10px 0;"><span style="color:#94A3B8; font-size:0.9rem;">Stop Loss</span><span style="color:#F87171; font-weight:600;">{setup.get("sl", "N/A")}</span></div>', unsafe_allow_html=True)

                st.markdown("<br>", unsafe_allow_html=True)
            
                # --- Detailní Rozbor (Expandery) ---
                with st.expander("📊 Detailní Technická Analýza"):
                    st.write(ai_data.get("technical_analysis", "Data nenalezena."))
            
                with st.expander("🏢 Detailní Fundamentální Analýza"):
                    st.write(ai_data.get("fundamental_analysis", "Data nenalezena."))
                
                with st.expander("⚖️ Syntéza a Rigorózní Obhajoba"):
                    st.write(ai_data.get("synthesis_and_defense", "Data nenalezena."))
            
                # --- Golden Zone & Liquidity placement expanders ---
                golden_zone = ai_data.get("golden_zone", {})
                if golden_zone:
                    with st.expander("🏆 Zlatá Retracement Zóna (Golden Zone)"):
                        st.markdown(f"**Rozpětí (Fibonacci 61.8% - 78.6%):** `{golden_zone.get('range', 'N/A')}`")
                        st.markdown(f"**Zdůvodnění a chování ceny:**\n{golden_zone.get('rationale', 'Data nenalezena.')}")
                
                liq_setup = ai_data.get("liquidity_setup", {})
                if liq_setup:
                    with st.expander("💧 Nastavení Likvidity & Limitních Hladin"):
                        st.markdown(f"🎯 **Nákupní likvidita (Buy Limit orders):**\n{liq_setup.get('buy_liquidity_placement', 'N/A')}")
                        st.markdown(f"🎯 **Prodejní likvidita (Sell Limit orders):**\n{liq_setup.get('sell_liquidity_placement', 'N/A')}")
            
                if setup and setup.get("rationale"):
                    st.markdown(f'<div style="background: rgba(56, 189, 248, 0.1); border-left: 4px solid #38BDF8; padding: 16px; border-radius: 8px; margin-bottom: 25px;"><span style="color: #38BDF8; font-weight: 700; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 1px;">🧠 Logika setupu</span><br><div style="color: #E2E8F0; font-size: 0.95rem; margin-top: 8px; line-height: 1.5;">{str(setup.get("rationale")).strip()}</div></div>', unsafe_allow_html=True)

                # --- Rychlý Export Section ---
                with st.expander("📤 Rychlý Export Setupu (Copy-Paste)"):
                    if direction == "WAIT":
                        export_text = f"""
🚀 TRADING SETUP: {ticker} ({st.session_state.tf_interval})
---
🧭 Směr: WAIT (No Trade)
🧠 Důvod: {setup.get('rationale', 'N/A')}
⏳ Kdy zkontrolovat: {setup.get('when_to_ask_again', 'N/A')}
                        """
                    else:
                        export_text = f"""
🚀 TRADING SETUP: {ticker} ({st.session_state.tf_interval})
---
🧭 Směr: {direction}
🎯 Vstup: {setup.get('entry', 'N/A')}
✅ Cíl (TP): {setup.get('tp', 'N/A')}
❌ Stop Loss: {setup.get('sl', 'N/A')}
---
🧠 Důvod: {setup.get('rationale', 'N/A')}
                        """
                    st.code(export_text.strip(), language="text")
            
                # --- INTERAKTIVNÍ CHAT ---
                st.markdown("---")
                st.markdown("### 💬 Dotaz na AI k této analýze")
                
                # Zobrazení historie chatu
                for msg in st.session_state.chat_history:
                    with st.chat_message(msg["role"]):
                        st.write(msg["content"])
                
                # Input pro nový dotaz
                if chat_input := st.chat_input("Zeptejte se na detaily analýzy..."):
                    st.session_state.chat_history.append({"role": "user", "content": chat_input})
                    with st.chat_message("user"):
                        st.write(chat_input)
                    
                    with st.chat_message("assistant"):
                        with st.spinner("AI přemýšlí..."):
                            response = chat_with_ai(chat_input, ai_data)
                            st.write(response)
                            st.session_state.chat_history.append({"role": "assistant", "content": response})


else:
    # --- Settings Page Content ---
    st.markdown("## ⚙️ Globální Nastavení Terminálu")
    st.markdown("---")
    
    set_col1, set_col2 = st.columns(2)
    
    with set_col1:
        with st.container(border=True):
            st.markdown("### 🌐 Watchlist & Symboly")
            current_watchlist_str = ", ".join(st.session_state.watchlist)
            new_watchlist_str = st.text_area("Sledované symboly (oddělené čárkou):", value=current_watchlist_str)
            
            st.divider()
            new_dxm = st.text_input("Symbol pro DXM Widget:", value=st.session_state.dxm_symbol)
            new_cot = st.text_input("Symbol pro COT Widget:", value=st.session_state.cot_symbol)
            
            if st.button("💾 Uložit Symboly", type="primary", use_container_width=True):
                st.session_state.watchlist = [s.strip() for s in new_watchlist_str.split(",") if s.strip()]
                st.session_state.dxm_symbol = new_dxm
                st.session_state.cot_symbol = new_cot
                st.success("Symboly byly úspěšně aktualizovány!")
                st.rerun()

    with set_col2:
        with st.container(border=True):
            st.markdown("### 🧠 AI Engine & API")
            st.info("Zde můžete vložit svůj API klíč. Změna se uloží automaticky po stisku Enter.")
            
            # Decoupled widget state from persistent session storage
            st.text_input("Vlastní API Key:", type="password", key="input_api_key", value=st.session_state.persistent_api_key, on_change=sync_api_credentials, help="Vložte klíč z Google AI Studio nebo OpenAI.")
            st.radio("Vyberte poskytovatele:", ["Gemini", "OpenAI"], key="input_api_provider", index=0 if st.session_state.persistent_api_provider == "Gemini" else 1, on_change=sync_api_credentials, horizontal=True)
            
            st.divider()
            
            if st.button("🔍 Otestovat připojení", use_container_width=True):
                sync_api_credentials()
                test_key, test_provider = get_api_credentials()
                if not test_key or not test_key.strip():
                    st.error("Chybí klíč pro testování! Vložte jej do pole výše.")
                else:
                    with st.spinner("Testuji připojení..."):
                        # Use the actual generate_analysis engine logic for the test to be 100% sure
                        try:
                            if test_provider == "Gemini":
                                from google import genai
                                client = genai.Client(api_key=test_key.strip())
                                
                                # Use hardcoded working model instead of dynamic discovery which hangs
                                test_models = ['gemini-2.5-flash', 'gemini-flash-latest', 'gemini-2.0-flash']
                                
                                worked_model = None
                                last_test_err = None
                                
                                for tm in test_models:
                                    try:
                                        t_resp = client.models.generate_content(model=tm, contents="Say OK")
                                        if t_resp and t_resp.text:
                                            worked_model = tm
                                            break
                                    except Exception as e:
                                        last_test_err = str(e)
                                        continue
                                
                                if worked_model:
                                    st.success(f"✅ Gemini: Připojení je v pořádku! (Model: {worked_model})")
                                else:
                                    err_msg = f"\n\nDetail chyby: {last_test_err}" if last_test_err else ""
                                    st.error(f"❌ Test selhal. Zkontrolujte platnost API klíče.{err_msg}")
                            else:
                                from openai import OpenAI
                                client = OpenAI(api_key=test_key.strip())
                                client.chat.completions.create(model="gpt-3.5-turbo", messages=[{"role": "user", "content": "Say OK"}], max_tokens=5)
                                st.success(f"✅ OpenAI: Připojení je v pořádku!")
                        except Exception as e:
                            st.error(f"❌ Test selhal: {str(e)}")

            # Technical settings moved to an expander to keep UI clean
            with st.expander("🛠️ Pokročilá Diagnostika"):
                st.checkbox("Ladící režim (Debug Mode)", key="debug_mode")
                st.text_input("Manuální název modelu:", key="input_model_name", value=st.session_state.persistent_model_name, on_change=sync_api_credentials)
                if st.button("📋 Vylistovat dostupné modely", use_container_width=True):
                    test_key, _ = get_api_credentials()
                    if test_key:
                        try:
                            from google import genai
                            client = genai.Client(api_key=test_key.strip())
                            models = client.models.list()
                            model_names = [m.name for m in models if hasattr(m, 'name')]
                            st.code("\n".join(model_names))
                        except Exception as e:
                            st.error(str(e))
            
        with st.container(border=True):
            st.markdown("### 🛠️ Systémové Nástroje")
            if st.button("🧹 Vymazat Cache", use_container_width=True):
                st.cache_data.clear()
                st.success("Cache vymazána!")
            
            if st.button("🗑️ Resetovat Historii", use_container_width=True):
                st.session_state.analysis_history = []
                st.success("Historie byla vymazána.")
                st.rerun()
            
            if st.button("🔄 Obnovit výchozí klíč (ze secrets.toml)", use_container_width=True):
                st.session_state.persistent_api_key = ""
                if "input_api_key" in st.session_state:
                    st.session_state.input_api_key = ""
                st.success("Byl obnoven výchozí API klíč ze souboru secrets.toml.")
                st.rerun()

    st.markdown("<br><br>", unsafe_allow_html=True)
    st.info("💡 Změny provedené zde se projeví na Dashboardu ihned po návratu.")
