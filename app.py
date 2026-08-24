import io
import datetime
from datetime import timedelta
import numpy as np
import pandas as pd
import pytz
import requests
import streamlit as st
import yfinance as yf

# =====================================================================
# 1. 核心凭证与配置
# =====================================================================
TIINGO_TOKEN = "bcffe3a5cf7eeef085e405cfa4a3e5691b976217"

st.set_page_config(
    page_title="QQQ & 17 Core Swing Engine (Wide Structural Zones)",
    page_icon="🧭",
    layout="wide"
)

DEFAULT_TICKERS = [
    "QQQ", "NVDA", "MU", "AAPL", "MSFT", "TSM", 
    "AMD", "AMZN", "GOOGL", "META", "AVGO", 
    "QCOM", "ARM", "ASML", "PLTR", "TSLA", 
    "NFLX", "INTC"
]

# =====================================================================
# 2. 人性化时间与倒计时引擎
# =====================================================================
tz_myt = pytz.timezone("Asia/Kuala_Lumpur")
tz_ny = pytz.timezone("America/New_York")

now_myt = datetime.datetime.now(tz_myt)
now_ny = datetime.datetime.now(tz_ny)

target_open_ny = now_ny.replace(hour=9, minute=30, second=0, microsecond=0)
if now_ny >= target_open_ny and now_ny.hour >= 16:
    target_open_ny += timedelta(days=1)
while target_open_ny.weekday() >= 5:
    target_open_ny += timedelta(days=1)

target_open_myt = target_open_ny.astimezone(tz_myt)
time_to_open = target_open_myt - now_myt

c_t1, c_t2, c_t3 = st.columns([1.5, 1.5, 2])
c_t1.info(f"🕒 **大马时间 (MYT):** {now_myt.strftime('%Y-%m-%d %H:%M:%S')}")
c_t2.info(f"🇺🇸 **美东时间 (ET):** {now_ny.strftime('%Y-%m-%d %H:%M:%S')}")

if 0 <= time_to_open.total_seconds() <= 86400:
    hours, remainder = divmod(int(time_to_open.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    c_t3.warning(f"⏳ **距离今晚开盘倒计时:** {hours}小时 {minutes}分 {seconds}秒")
else:
    c_t3.success("🟢 **美股交易中 / 盘后复盘阶段**")

# =====================================================================
# 3. 侧边栏配置 (支持宽战区倍数调节)
# =====================================================================
st.sidebar.title("🎛️ CONTROL CENTER")

zone_thickness_mult = st.sidebar.slider(
    "🧱 SBR / RBS 战区厚度系数 (ATR 倍数)",
    min_value=0.50,
    max_value=1.50,
    value=0.85,
    step=0.05,
    help="默认 0.85 ATR，提供扎实、清晰的供需缓冲厚度"
)

tickers_input = st.sidebar.text_area(
    "监控资产池 (QQQ + 17 核心标的)",
    value=", ".join(DEFAULT_TICKERS),
    height=120
)
tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]

btn_clear = st.sidebar.button("🧹 清除缓存并强制刷新", type="secondary")
if btn_clear:
    st.cache_data.clear()
    st.rerun()

# =====================================================================
# 4. 1-Hour 数据抓取引擎
# =====================================================================
@st.cache_data(ttl=300, show_spinner=False)
def fetch_1h_data(ticker, token):
    start_date = (datetime.datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    url = f"https://api.tiingo.com/iex/{ticker}/prices?startDate={start_date}&resampleFreq=1hour&token={token}&columns=open,high,low,close,volume"
    headers = {'Content-Type': 'application/json'}
    try:
        resp = requests.get(url, headers=headers, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            if data and isinstance(data, list) and len(data) >= 20:
                df = pd.DataFrame(data)
                df['date'] = pd.to_datetime(df['date'])
                df.set_index('date', inplace=True)
                df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'}, inplace=True)
                return df[['Open', 'High', 'Low', 'Close', 'Volume']].sort_index(), "Tiingo 1H"
    except Exception:
        pass

    try:
        df_yf = yf.download(ticker, period="1mo", interval="1h", progress=False)
        if df_yf is not None and not df_yf.empty:
            if isinstance(df_yf.columns, pd.MultiIndex):
                df_yf.columns = df_yf.columns.get_level_values(0)
            df_yf = df_yf[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
            df_yf.index = pd.to_datetime(df_yf.index)
            if len(df_yf) >= 20:
                return df_yf.sort_index(), "yfinance 1H"
    except Exception:
        pass

    return None, "Failed"

# =====================================================================
# 5. 1H 宽结构带计算核心
# =====================================================================
def calculate_1h_levels(df, mult: float):
    if len(df) < 20:
        return None
    
    df = df.copy()
    df['TR'] = np.maximum(
        df['High'] - df['Low'],
        np.maximum(
            (df['High'] - df['Close'].shift(1)).abs(),
            (df['Low'] - df['Close'].shift(1)).abs()
        )
    )
    df['ATR14'] = df['TR'].rolling(window=14).mean()
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    
    latest_close = df['Close'].iloc[-1]
    latest_atr = df['ATR14'].iloc[-1] if not np.isnan(df['ATR14'].iloc[-1]) else (latest_close * 0.008)
    
    subset = df.iloc[-40:].copy()
    highs = subset['High'].values
    lows = subset['Low'].values
    
    pivot_highs, pivot_lows = [], []
    for i in range(2, len(subset) - 2):
        if highs[i] == max(highs[i-2:i+3]):
            pivot_highs.append(highs[i])
        if lows[i] == min(lows[i-2:i+3]):
            pivot_lows.append(lows[i])
            
    upper_pivots = [p for p in pivot_highs if p > latest_close]
    sbr_base = min(upper_pivots) if upper_pivots else (latest_close + 1.5 * latest_atr)
    
    lower_pivots = [p for p in pivot_lows if p < latest_close]
    rbs_base = max(lower_pivots) if lower_pivots else (latest_close - 1.5 * latest_atr)
    
    # 扩大厚度：使用 mult (默认 0.85) 倍 ATR
    half_band = mult * latest_atr
    sbr_top = round(float(sbr_base + half_band), 2)
    sbr_bot = round(float(sbr_base - half_band), 2)
    rbs_top = round(float(rbs_base + half_band), 2)
    rbs_bot = round(float(rbs_base - half_band), 2)
    
    pdh_val = round(float(subset['High'].iloc[-14:-7].max()), 2) if len(subset) >= 14 else round(float(subset['High'].max()), 2)
    pdl_val = round(float(subset['Low'].iloc[-14:-7].min()), 2) if len(subset) >= 14 else round(float(subset['Low'].min()), 2)
    pmh_val = round(float(subset['High'].iloc[-4:].max()), 2)
    pml_val = round(float(subset['Low'].iloc[-4:].min()), 2)
    
    trend_bias = 1 if latest_close > df['EMA20'].iloc[-1] else -1
    
    return {
        "Close": round(float(latest_close), 2),
        "EMA20": round(float(df['EMA20'].iloc[-1]), 2),
        "TREND_BIAS": trend_bias,
        "ZONE_MULT": mult,
        "SBR_TOP": sbr_top,
        "SBR_BOT": sbr_bot,
        "RBS_TOP": rbs_top,
        "RBS_BOT": rbs_bot,
        "PDH": pdh_val,
        "PDL": pdl_val,
        "PMH": pmh_val,
        "PML": pml_val,
        "ATR14": round(float(latest_atr), 2)
    }

# =====================================================================
# 6. 渲染界面
# =====================================================================
st.title("🧭 QQQ & 17 CORE ASSETS (SOLID STRUCTURAL ZONES)")
st.caption(f"战区厚度: **{zone_thickness_mult}x 1H ATR** | 具备厚度的机构供需缓冲带")

all_data = {}
source_track = {}
with st.spinner("计算 1H 宽结构带中..."):
    for t in tickers:
        df_1h, src = fetch_1h_data(t, TIINGO_TOKEN)
        if df_1h is not None:
            all_data[t] = df_1h
            source_track[t] = src

results = []
for t in tickers:
    if t in all_data:
        res = calculate_1h_levels(all_data[t], zone_thickness_mult)
        if res:
            res["TICKER"] = t
            res["SOURCE"] = source_track.get(t, "1H")
            results.append(res)

if results:
    df_res = pd.DataFrame(results)
    
    st.subheader("🎯 5M 执行参数一键复制座舱 (扎实厚度版)")
    selected_stock = st.selectbox("选择标的:", tickers, index=0)
    stock_data = df_res[df_res["TICKER"] == selected_stock].iloc[0]
    
    col_c1, col_c2 = st.columns([1, 1])
    with col_c1:
        st.markdown(f"#### 【{selected_stock}】 1H 战区数据 (厚度: {stock_data['ZONE_MULT']}x ATR)")
        st.markdown(f"* **最新现价:** `${stock_data['Close']}` | **1H ATR:** `${stock_data['ATR14']}`")
        st.markdown(f"* **🔴 1H SBR 顶部阻力区:** `${stock_data['SBR_BOT']} ~ ${stock_data['SBR_TOP']}` (宽 {round(stock_data['SBR_TOP'] - stock_data['SBR_BOT'], 2)} 点)")
        st.markdown(f"* **🟢 1H RBS 底部支撑区:** `${stock_data['RBS_BOT']} ~ ${stock_data['RBS_TOP']}` (宽 {round(stock_data['RBS_TOP'] - stock_data['RBS_BOT'], 2)} 点)")
        st.markdown(f"* **📌 昨日极值 (PDL / PDH):** `${stock_data['PDL']} ~ ${stock_data['PDH']}`")
        st.markdown(f"* **🕒 盘前极值 (PML / PMH):** `${stock_data['PML']} ~ ${stock_data['PMH']}`")
        
    with col_c2:
        st.markdown("#### 📋 复制到富途 5M 指标顶部的 9 行代码")
        futu_code = f"""TREND_BIAS := {int(stock_data['TREND_BIAS'])};       {{ 宏观偏向: 1=多, -1=空 }}
SBR_TOP    := {stock_data['SBR_TOP']:.2f};   {{ 1H 阻力顶沿 }}
SBR_BOT    := {stock_data['SBR_BOT']:.2f};   {{ 1H 阻力底沿 }}
RBS_TOP    := {stock_data['RBS_TOP']:.2f};   {{ 1H 支撑顶沿 }}
RBS_BOT    := {stock_data['RBS_BOT']:.2f};   {{ 1H 支撑底沿 }}
PDH_LINE   := {stock_data['PDH']:.2f};   {{ 昨日最高价 PDH }}
PDL_LINE   := {stock_data['PDL']:.2f};   {{ 昨日最低价 PDL }}
PMH_LINE   := {stock_data['PMH']:.2f};   {{ 盘前最高价 PMH }}
PML_LINE   := {stock_data['PML']:.2f};   {{ 盘前最低价 PML }}"""
        st.code(futu_code, language="pascal")
