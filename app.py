import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import base64
from openai import OpenAI
import google.generativeai as genai
from datetime import datetime, timedelta
import pytz # Potřebné pro korektní časová pásma

# --- API Key Detection (Global Scope) ---
def get_api_credentials():
    """Dynamically fetch API keys from secrets to avoid caching issues."""
    gemini_key = st.secrets.get("GEMINI_API_KEY")
    openai_key = st.secrets.get("OPENAI_API_KEY")
    
    if gemini_key:
        return gemini_key, "Gemini"
    elif openai_key:
        return openai_key, "OpenAI"
    return None, None

# --- Streamlit Page Config ---
st.set_page_config(page_title="Trading Analyzer", layout="wide", initial_sidebar_state="expanded")

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

@st.cache_data(show_spinner="Načítám historická data...")
def fetch_data(ticker_symbol, period, interval="1d"):
    """Fetches historical market data with interval support."""
    ticker = yf.Ticker(ticker_symbol)
    try:
        df = ticker.history(period=period, interval=interval)
        if df.empty:
            return df
        df.index = df.index.tz_localize(None)
        return df
    except Exception as e:
        st.error(f"Chyba při stahování dat pro ticker {ticker_symbol}: {e}")
        return pd.DataFrame()

@st.cache_data(show_spinner="Načítám fundamentální data...")
def fetch_fundamentals(ticker_symbol):
    """Fetches fundamental data from yfinance."""
    ticker = yf.Ticker(ticker_symbol)
    info = ticker.info
    
    fundamentals = {}
    
    # Safely extract common metrics (might not exist for crypto/forex)
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
    """Fetches latest news from yfinance with robust parsing."""
    ticker = yf.Ticker(ticker_symbol)
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
        
    df = df.copy()
    
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
    indicator_adx = ta.trend.ADXIndicator(high=df['High'], low=df['Low'], close=df['Close'], window=14)
    df['ADX'] = indicator_adx.adx()
    df['DI_Plus'] = indicator_adx.adx_pos()
    df['DI_Minus'] = indicator_adx.adx_neg()
    
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

def plot_chart(df, ticker_symbol, config=None):
    """Creates a comprehensive Plotly chart dynamically based on config."""
    if config is None:
        config = {
            "chart_type": "Svíčkový (Candlestick)",
            "show_sma": True,
            "show_bb": True,
            "show_volume": True,
            "show_macd": True,
            "show_rsi": True
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
    """Creates a stylized mini-chart for Directional Movement (DXM) with Neon Glow."""
    df_mini = df.tail(14)
    fig = go.Figure()
    
    # Neon Glow effects using multiple lines with varying opacity
    fig.add_trace(go.Scatter(x=df_mini.index, y=df_mini['DI_Plus'], mode='lines', line=dict(color='rgba(16, 185, 129, 0.2)', width=8), hoverinfo='skip'))
    fig.add_trace(go.Scatter(x=df_mini.index, y=df_mini['DI_Plus'], mode='lines+markers', name='Long', line=dict(color='#10B981', width=3), marker=dict(size=6, color="#14161C", line=dict(width=2, color="#10B981"))))
    
    fig.add_trace(go.Scatter(x=df_mini.index, y=df_mini['DI_Minus'], mode='lines', line=dict(color='rgba(239, 68, 68, 0.2)', width=8), hoverinfo='skip'))
    fig.add_trace(go.Scatter(x=df_mini.index, y=df_mini['DI_Minus'], mode='lines+markers', name='Short', line=dict(color='#EF4444', width=3), marker=dict(size=6, color="#14161C", line=dict(width=2, color="#EF4444"))))
    
    fig.update_layout(
        margin=dict(l=0, r=0, t=10, b=0),
        height=150,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", zeroline=False, showticklabels=True),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", zeroline=False, showticklabels=True, range=[0, 100]),
        font=dict(family="Inter, sans-serif", color="#94A3B8", size=10)
    )
    return fig

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

def generate_analysis(ticker, df, fundamentals, news=None):
    """Generates the AI analysis using the selected provider."""
    
    # Summarize Fundamentals
    fund_str = json.dumps(fundamentals, indent=2, ensure_ascii=False) if fundamentals else "Žádná fundamentální data (pravděpodobně se jedná o krypto/komoditu/VIX)."
    
    # Summarize Technicals (Last available row)
    last_row = df.iloc[-1]
    prev_row = df.iloc[-2] if len(df) > 1 else df.iloc[-1]
    
    tech_str = f"""
    Poslední cena (Close): {last_row.get('Close', 0):.2f}
    RSI (14): {last_row.get('RSI', 0):.2f}
    MACD: {last_row.get('MACD', 0):.2f} (Signal: {last_row.get('MACD_Signal', 0):.2f})
    SMA 20: {last_row.get('SMA_20', 0):.2f}
    SMA 50: {last_row.get('SMA_50', 0):.2f}
    SMA 200: {last_row.get('SMA_200', 0):.2f}
    20-day Volatilita (BBand šířka %): {((float(last_row.get('BB_High', 0)) - float(last_row.get('BB_Low', 0))) / float(last_row.get('Close', 1)) * 100):.2f}%
    """

    news_str = ""
    if news:
        news_str = "Aktuální zprávy z trhu:\n" + "\n".join([f"- {n['title']} ({n['publisher']})" for n in news])

    sys_prompt = f"""
Jsi elitní kvantitativní analytik z prestižního hedgeového fondu. Tvou úlohou je provést rigorózní audit instrumentu: {ticker}
Pracuj jako "Auditor AI" - hledej rizika, likviditní pasti a potvrzuj signály více indikátory.

Základní fundamentální data:
{fund_str}

Technická data (poslední hodnoty):
{tech_str}

{news_str}

Požaduji, abys vygeneroval detailní odpověď jako validní JSON objekt bez Markdown tagů s touto strukturou:
{{
  "sentiment_score": číslo od -100 (Silný výprodej) do 100 (Silná akumulace),
  "sentiment_label": "Bullish" | "Bearish" | "Neutral",
  "technical_analysis": "Stručný, úderný rozbor techniky (price action, divergence)...",
  "fundamental_analysis": "Analýza makro/mikro kontextu...",
  "synthesis_and_defense": "Proč je tvůj setup platný? Postav se proti davu.",
  "trade_setup": {{
    "direction": "Long" | "Short",
    "entry": "Zóna vstupu",
    "tp": "Target",
    "sl": "Invalidace",
    "rationale": "Kalkulované riziko"
  }}
}}
"""

    # Refresh API key inside the function to ensure we use the latest from secrets
    api_key, provider = get_api_credentials()
    
    if not api_key:
        st.error("❌ Chybí API klíč! Prosím vložte jej do .streamlit/secrets.toml")
        return {}

    try:
        if provider == "OpenAI":
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-4o",
                response_format={ "type": "json_object" },
                messages=[
                    {"role": "system", "content": "Jsi expertní kvantitativní analytik. Navracíš striktně validní JSON."},
                    {"role": "user", "content": sys_prompt}
                ],
                temperature=0.7
            )
            return json.loads(response.choices[0].message.content)

        elif provider == "Gemini":
            genai.configure(api_key=api_key)
            # Robust Fallback Matrix
            models_to_try = [
                'models/gemini-2.5-flash',
                'models/gemini-2.0-flash',
                'models/gemini-3.1-pro-preview',
                'models/gemini-flash-latest',
                'models/gemini-pro-latest',
                'gemini-1.5-flash',
                'gemini-pro'
            ]
            
            last_err = None
            for model_name in models_to_try:
                try:
                    model = genai.GenerativeModel(model_name, generation_config={"response_mime_type": "application/json"})
                    response = model.generate_content(sys_prompt)
                    # Success!
                    return json.loads(response.text)
                except Exception as e:
                    last_err = f"{type(e).__name__}: {str(e)}"
                    if "429" in str(e):
                        st.warning("⚠️ Dosáhli jste denního limitu (Quota 429) u Google Gemini. Zkuste to prosím později nebo použijte klíč z nového projektu.")
                        break 
                    continue 
            
            # Ultra-Simplified Error Reporting
            if last_err:
                if "429" in last_err:
                    st.error("⚠️ AI analýza se nezdařila: Váš denní limit u Googlu je vyčerpán. Prosím použijte klíč z NOVÉHO PROJEKTU v AI Studiu nebo počkejte na zítřek.")
                else:
                    st.error(f"⚠️ AI analýza se nezdařila: {last_err}")
            return {}
            
    except Exception as e:
        st.error(f"⚠️ Chyba při komunikaci s AI ({provider}). Detail: {e}")
        return {}

    return {}


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
        <div class="sidebar-menu-item active">📊 Dashboard</div>
        <div class="sidebar-menu-item" style="color: #475569;">⚙️ Settings</div>
        <br>
    """, unsafe_allow_html=True)

    with st.expander("📚 Vysvětlivky pojmů", expanded=True):
        st.markdown("""
        <div style="font-size:0.85rem; color:#94A3B8;">
        <b>Score:</b> AI ohodnocení situace od -100 do 100.<br><br>
        <b>DXM:</b> Měří tržní sílu. <span style="color:#10B981;">Zelená</span> = Nákupy, <span style="color:#EF4444;">Červená</span> = Prodeje.<br><br>
        <b>COT:</b> Commitment of Traders. Ukazuje naklonění kapitálu institucí.
        </div>
        """, unsafe_allow_html=True)

    with st.expander("⚙️ Engine & Panel Settings", expanded=True):
        st.markdown("##### AI Data Engine")
        ticker = st.text_input("Aktivní Symbol:", value="EURUSD=X", help="Zadejte symbol z Yahoo Finance (např. EURUSD=X).")
        
        # Link sidebar tf to session state
        tf_options = ["1m", "5m", "15m", "30m", "1h", "1d", "1wk", "1mo"]
        current_tf_idx = tf_options.index(st.session_state.tf_interval) if st.session_state.tf_interval in tf_options else 5
        
        selected_interval = st.selectbox("Interval:", tf_options, index=current_tf_idx)
        if selected_interval != st.session_state.tf_interval:
            st.session_state.tf_interval = selected_interval
            # Auto-adjust period based on interval limits
            if selected_interval == "1m": st.session_state.tf_period = "7d"
            elif selected_interval in ["5m", "15m", "30m"]: st.session_state.tf_period = "60d"
            elif selected_interval == "1h": st.session_state.tf_period = "2y"
            elif selected_interval == "1mo": st.session_state.tf_period = "max"
            else: st.session_state.tf_period = "5y"
            st.rerun()

        # api_key and ai_provider are handled at the top of the script
        pass

        # If key is missing from secrets, allow manual input (hidden by default)
        if not api_key:
            api_key = st.text_input("Vložte API Key:", type="password", help="Vložte svůj Gemini nebo OpenAI API klíč.")
            ai_provider = st.radio("Provider:", ["Gemini", "OpenAI"], horizontal=True)

        st.divider()
        st.markdown("##### Mini-Widget Symbols")
        dxm_ticker = st.text_input("DXM Symbol:", value=ticker)
        cot_ticker = st.text_input("COT Symbol:", value=ticker)
        
    with st.expander("📈 Visual Settings", expanded=False):
        chart_type = st.radio("Cenový vývoj:", ["Svíčkový (Candlestick)", "Line Glow (Moderní)"], index=0)
        col_set1, col_set2 = st.columns(2)
        with col_set1:
            show_sma = st.checkbox("SMA", value=False)
            show_bb = st.checkbox("B. Bands", value=False)
            show_volume = st.checkbox("Volume", value=False)
        with col_set2:
            show_macd = st.checkbox("MACD", value=False)
            show_rsi = st.checkbox("RSI", value=False)
            
        chart_config = {
            "chart_type": chart_type,
            "show_sma": show_sma,
            "show_bb": show_bb,
            "show_volume": show_volume,
            "show_macd": show_macd,
            "show_rsi": show_rsi
        }

    if st.session_state.analysis_history:
        with st.expander("📂 Historie Analýz", expanded=False):
            for i, hist in enumerate(reversed(st.session_state.analysis_history)):
                hist_label = f"{hist['ticker']} ({hist['tf']}) - {hist['time']}"
                if st.button(hist_label, key=f"hist_{i}", use_container_width=True):
                    st.session_state.ai_analysis_data = hist['data']
                    st.session_state.current_analysis_ticker = f"{hist['ticker']}_{hist['tf']}"
                    st.session_state.chat_history = hist.get('chat', [])
                    st.rerun()

    generate_btn = st.button("Spustit Analyzer", type="primary", use_container_width=True)

# 1. Dashboard Header & Health Status
col_status1, col_status2 = st.columns([0.65, 0.35])
with col_status1:
    st.markdown(f"""
        <div style="display:flex; align-items:baseline; gap: 15px; margin-bottom: 5px;">
            <h1 style="margin:0; padding:0; line-height: 1; font-size: 2.2rem;">Dashboard</h1>
            <span style="color:#94A3B8; font-size: 0.9rem;">v3.1 Master</span>
        </div>
        <div style="display:flex; gap: 15px; margin-bottom: 20px;">
            <span style="color:#10B981; font-size:0.75rem;"><span class="pulse-dot"></span> System Online</span>
            <span style="color:#38BDF8; font-size:0.75rem;">● Data Feed: OK</span>
            <span style="color:{'#10B981' if api_key else '#EF4444'}; font-size:0.75rem;">● AI Engine: {'Online' if api_key else 'Missing Key'}</span>
        </div>
    """, unsafe_allow_html=True)

with col_status2:
    # Dynamický výpočet časů (NYC, LON, TOK)
    utc_now = datetime.now(pytz.utc)
    ny_time = utc_now.astimezone(pytz.timezone('America/New_York')).strftime('%H:%M')
    lon_time = utc_now.astimezone(pytz.timezone('Europe/London')).strftime('%H:%M')
    tok_time = utc_now.astimezone(pytz.timezone('Asia/Tokyo')).strftime('%H:%M')
    
    st.markdown(f"""
        <div style="text-align: right; margin-top: 10px; display: flex; justify-content: flex-end; gap: 8px;">
            <div class="time-badge">NYC <b>{ny_time}</b></div>
            <div class="time-badge">LON <b>{lon_time}</b></div>
            <div class="time-badge">TOK <b>{tok_time}</b></div>
        </div>
    """, unsafe_allow_html=True)

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
                if current_price >= 1:
                    price_fmt = f"${float(current_price):,.2f}"
                    change_fmt = f"${abs(price_change):.2f}"
                elif current_price >= 0.01:
                    price_fmt = f"${float(current_price):,.4f}"
                    change_fmt = f"${abs(price_change):.4f}"
                else:
                    price_fmt = f"${current_price:,.6f}"
                    change_fmt = f"${abs(price_change):.6f}"

                st.markdown(f"""
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 10px;">
                    <h3 style='margin:0; font-size: 1.2rem;'>Asset Price</h3>
                    <div style="font-size: 0.8rem; color:#94A3B8;">{ticker}</div>
                </div>
                <div style="padding: 6px 0;">
                    <div style="font-size: 2.2rem; font-weight: 700; color: #F8FAFC; line-height: 1.1;">
                        {price_fmt}
                    </div>
                    <div style="font-size: 1.0rem; color: {color}; font-weight: 600; margin-top: 5px;">
                        {arrow} {change_fmt} ({abs(pct_change):.2f}%)
                    </div>
                </div>
                """, unsafe_allow_html=True)

        with kpi_col2:
            # --- DXM WIDGET ---
            with st.container(border=True):
                st.markdown(f"""
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 5px;">
                    <h3 style='margin:0; font-size: 1.2rem;'>DXM</h3>
                    <div style="font-size: 0.8rem;"><span style="color:#EF4444;">🔴 Short</span> &nbsp;&nbsp; <span style="color:#10B981;">🟢 Long</span></div>
                </div>
                """, unsafe_allow_html=True)
                
                if dxm_ticker != ticker:
                    df_dxm = calculate_indicators(fetch_data(dxm_ticker, "1mo"))
                else:
                    df_dxm = df_processed
                
                if not df_dxm.empty and 'DI_Plus' in df_dxm.columns:
                    fig_dxm = plot_dxm_chart(df_dxm)
                    fig_dxm.update_layout(height=110, margin=dict(l=0, r=0, t=0, b=0))
                    st.plotly_chart(fig_dxm, use_container_width=True, config={'displayModeBar': False})
                else:
                    st.warning("Data pro DXM nejsou k dispozici.")

        with kpi_col3:
            # --- COT WIDGET ---
            with st.container(border=True):
                if cot_ticker != ticker:
                    df_cot_base = calculate_indicators(fetch_data(cot_ticker, "1mo"))
                else:
                    df_cot_base = df_processed
                
                if not df_cot_base.empty:
                    synth_long_pct, synth_short_pct = calculate_synthetic_sentiment(df_cot_base)
                    
                    st.markdown(f"""
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 0px;">
                        <h3 style='margin:0; font-size: 1.2rem;'>COT</h3>
                        <div style="font-size: 0.8rem;">
                            <span style="color:#10B981;">🟢 {synth_long_pct}%</span> &nbsp;&nbsp;
                            <span style="color:#EF4444;">🔴 {synth_short_pct}%</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    fig_cot = plot_cot_gauge("COT", synth_long_pct, synth_short_pct)
                    fig_cot.update_layout(height=115, margin=dict(l=0, r=0, t=0, b=0))
                    st.plotly_chart(fig_cot, use_container_width=True, config={'displayModeBar': False})
                else:
                    st.warning("Data pro COT nejsou k dispozici.")

        # --- Main Chart Section ---
        st.markdown("<br>", unsafe_allow_html=True)
        
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
        with st.container(border=True):
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

        # --- Technical Health Check Panel ---
        tech_signals = get_technical_signals(df_processed)
        if tech_signals:
            st.markdown("<div style='margin-top: 25px;'></div>", unsafe_allow_html=True)
            t_cols = st.columns(4)
            for i, (name, data) in enumerate(tech_signals.items()):
                with t_cols[i]:
                    st.markdown(f"""
                        <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.05); padding: 12px; border-radius: 10px; text-align: center;">
                            <div style="font-size: 0.7rem; color: #94A3B8; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 5px;">{name}</div>
                            <div style="font-size: 1rem; font-weight: 700; color: {data['color']};">{data['val']}</div>
                            <div style="font-size: 0.65rem; color: #475569; margin-top: 2px;">{data['status']}</div>
                        </div>
                    """, unsafe_allow_html=True)

        # --- News Feed Section ---
        news = fetch_news(ticker)
        if news:
            st.markdown("<h3 style='font-size: 1.2rem; margin-top: 20px;'>📰 Aktuální tržní zprávy</h3>", unsafe_allow_html=True)
            news_cols = st.columns(len(news))
            for i, article in enumerate(news):
                with news_cols[i]:
                    with st.container(border=True):
                        st.markdown(f"""
                            <div style="font-size: 0.8rem; color: #94A3B8; margin-bottom: 5px;">{article['publisher']}</div>
                            <div style="font-size: 0.9rem; font-weight: 600; min-height: 45px; margin-bottom: 10px;">
                                <a href="{article['link']}" target="_blank" style="text-decoration: none; color: #F8FAFC;">{article['title'][:60]}{'...' if len(article['title']) > 60 else ''}</a>
                            </div>
                        """, unsafe_allow_html=True)

        # --- AI Generated Trade Ideas Header ---
        st.markdown(f"""
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 20px; margin-top: 30px;">
                <h2 style="margin:0; font-size: 1.4rem;">AI generated trade ideas</h2>
                <span style="background: rgba(255,255,255,0.05); padding: 5px 12px; border-radius: 8px; font-weight:600; font-size:0.9rem; color:#00E676;">{ticker} • {st.session_state.tf_interval}</span>
            </div>
        """, unsafe_allow_html=True)

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
                with st.spinner("Sběr dat a generování posudku..."):
                    try:
                        fundamentals = fetch_fundamentals(ticker)
                        news_context = fetch_news(ticker)
                        ai_data = generate_analysis(ticker, df_processed, fundamentals, news=news_context)
                        
                        if ai_data:
                            st.session_state.ai_analysis_data = ai_data
                            st.session_state.current_analysis_ticker = f"{ticker}_{st.session_state.tf_interval}"
                            st.session_state.chat_history = [] # Reset chat for new analysis
                            
                            # Save to History
                            st.session_state.analysis_history.append({
                                "ticker": ticker,
                                "tf": st.session_state.tf_interval,
                                "time": datetime.now().strftime("%H:%M:%S"),
                                "data": ai_data,
                                "chat": []
                            })
                            # Limit history to last 10 items
                            if len(st.session_state.analysis_history) > 10:
                                st.session_state.analysis_history.pop(0)
                                
                    except Exception as e:
                        st.error(f"Při komunikaci s AI nastala chyba: {e}")
                        if "401" in str(e):
                            st.warning("Tip: Kód 401 značí neplatný API klíč. Zkontrolujte ho v Settings.")

        # Zobrazení AI dat ze session_state
        current_context = f"{ticker}_{st.session_state.tf_interval}"
        if st.session_state.ai_analysis_data and st.session_state.current_analysis_ticker == current_context:
            ai_data = st.session_state.ai_analysis_data
            sub_col1, sub_col2 = st.columns([1, 1], gap="medium")
            
            with sub_col1:
                with st.container(border=True):
                    # --- Vizualizace (Gauge Chart) ---
                    score = ai_data.get("sentiment_score", 0)
                    label = ai_data.get("sentiment_label", "Neutral")
                    
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
                    direction = setup.get("direction", "N/A")
                    if direction is None:
                        direction = "N/A"
                        
                    dir_class = "glow-long" if "Long" in direction else "glow-short" if "Short" in direction else ""
                    dot_class = "pulse-dot" if "Long" in direction else "pulse-dot short" if "Short" in direction else "pulse-dot"

                    st.markdown(f"""
                    <div style="display:flex; justify-content:space-between; padding: 10px 0; border-bottom: 1px solid #1E2129;">
                        <span style="color:#94A3B8; font-size:0.9rem;">Direction Bias</span>
                        <span class="{dir_class}" style="font-weight:600;"><span class="{dot_class}"></span>{direction}</span>
                    </div>
                    <div style="display:flex; justify-content:space-between; padding: 10px 0; border-bottom: 1px solid #1E2129;">
                        <span style="color:#94A3B8; font-size:0.9rem;">Entry Point</span>
                        <span style="font-weight:600;">{setup.get("entry", "N/A")}</span>
                    </div>
                    <div style="display:flex; justify-content:space-between; padding: 10px 0; border-bottom: 1px solid #1E2129;">
                        <span style="color:#94A3B8; font-size:0.9rem;">Take Profit</span>
                        <span style="color:#00E676; font-weight:600;">{setup.get("tp", "N/A")}</span>
                    </div>
                    <div style="display:flex; justify-content:space-between; padding: 10px 0;">
                        <span style="color:#94A3B8; font-size:0.9rem;">Stop Loss</span>
                        <span style="color:#F87171; font-weight:600;">{setup.get("sl", "N/A")}</span>
                    </div>
                    """, unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            
            # --- Detailní Rozbor (Expandery) ---
            with st.expander("📊 Detailní Technická Analýza"):
                st.write(ai_data.get("technical_analysis", "Data nenalezena."))
            
            with st.expander("🏢 Detailní Fundamentální Analýza"):
                st.write(ai_data.get("fundamental_analysis", "Data nenalezena."))
                
            with st.expander("⚖️ Syntéza a Rigorózní Obhajoba"):
                st.write(ai_data.get("synthesis_and_defense", "Data nenalezena."))
            
            if setup and setup.get("rationale"):
                st.markdown(f"""
                <div style="background: rgba(56, 189, 248, 0.1); border-left: 4px solid #38BDF8; padding: 16px; border-radius: 8px; margin-bottom: 25px;">
                    <span style="color: #38BDF8; font-weight: 700; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 1px;">🧠 Logika setupu</span><br>
                    <div style="color: #E2E8F0; font-size: 0.95rem; margin-top: 8px; line-height: 1.5;">{setup.get('rationale')}</div>
                </div>
                """, unsafe_allow_html=True)

            # --- Rychlý Export Section ---
            with st.expander("📤 Rychlý Export Setupu (Copy-Paste)"):
                export_text = f"""
🚀 TRADING SETUP: {ticker} ({st.session_state.tf_interval})
---
🧭 Směr: {direction}
🎯 Entry: {setup.get('entry', 'N/A')}
✅ Take Profit: {setup.get('tp', 'N/A')}
❌ Stop Loss: {setup.get('sl', 'N/A')}
---
🧠 Ratio: {setup.get('rationale', 'N/A')}
                """
                st.code(export_text.strip(), language="text")

