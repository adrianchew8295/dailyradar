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
    page_title="QQQ & 17 Core Swing Engine (Pure Structure)",
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
# 3. 侧边栏配置
# =====================================================================
st.sidebar.title("🎛️ CONTROL CENTER")
st.sidebar.success("🛡️ 纯客观 K 线几何引擎 (Zero Parameter)")

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
# 5. 纯客观 K 线结构解析 (已彻底修复 Series 比对 Bug)
# =====================================================================
def calculate_pure_structure_levels(df):
    if len(df) < 20:
        return None
    
    df = df.copy()
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    latest_close = float(df['Close'].iloc[-1])
    
    # 局部 40 根 1H K 线寻找局部高低拐点
    subset = df.iloc[-40:].copy()
    highs = subset['High'].values
    lows = subset['Low'].values
    opens = subset['Open'].values
    closes = subset['Close'].values
    
    # 纯几何寻找分形拐点并记录对应 K 线的实体与影线
    pivots_high_list = []
    pivots_low_list = []
    
    for i in range(2, len(subset) - 2):
        # 浪尖阻力拐点
        if highs[i] == max(highs[i-2:i+3]):
            top_val = float(highs[i])
            bot_val = float(max(opens[i], closes[i]))
            if top_val > latest_close:
                pivots_high_list.append((top_val, bot_val))
                
        # 浪底支撑拐点
        if lows[i] == min(lows[i-2:i+3]):
            bot_val = float(lows[i])
            top_val = float(min(opens[i], closes[i]))
            if bot_val < latest_close:
                pivots_low_list.append((top_val, bot_val))
                
    # 提取离当前价格最近的真实供需带 (使用 numpy 逐元素最大/最小修复 bug)
    if pivots_high_list:
        pivots_high_list.sort(key=lambda x: x[0])  # 取最靠近现价上方的阻力
        sbr_top, sbr_bot = pivots_high_list[0]
    else:
        sbr_top = float(subset['High'].max())
        body_top_series = np.maximum(subset['Open'].iloc[-5:].values, subset['Close'].iloc[-5:].values)
        sbr_bot = float(body_top_series.max())
        
    if pivots_low_list:
        pivots_low_list.sort(key=lambda x: x[1], reverse=True)  # 取最靠近现价下方的支撑
        rbs_top, rbs_bot = pivots_low_list[0]
    else:
        rbs_bot = float(subset['Low'].min())
        body_bot_series = np.minimum(subset['Open'].iloc[-5:].values, subset['Close'].iloc[-5:].values)
        rbs_top = float(body_bot_series.min())
        
    # 硬事实昨日与盘前极值
    pdh_val = round(float(subset['High'].iloc[-14:-7].max()), 2) if len(subset) >= 14 else round(float(subset['High'].max()), 2)
    pdl_val = round(float(subset['Low'].iloc[-14:-7].min()), 2) if len(subset) >= 14 else round(float(subset['Low'].min()), 2)
    pmh_val = round(float(subset['High'].iloc[-4:].max()), 2)
    pml_val = round(float(subset['Low'].iloc[-4:].min()), 2)
    
    trend_bias = 1 if latest_close > float(df['EMA20'].iloc[-1]) else -1
    
    return {
        "Close": round(latest_close, 2),
        "EMA20": round(float(df['EMA20'].iloc[-1]), 2),
        "TREND_BIAS": trend_bias,
        "SBR_TOP": round(float(sbr_top), 2),
        "SBR_BOT": round(float(sbr_bot), 2),
        "RBS_TOP": round(float(rbs_top), 2),
        "RBS_BOT": round(float(rbs_bot), 2),
        "PDH": pdh_val,
        "PDL": pdl_val,
        "PMH": pmh_val,
        "PML": pml_val
    }

# =====================================================================
# 6. 渲染界面与一键复制座舱
# =====================================================================
st.title("🧭 QQQ & 17 CORE ASSETS (PURE CANDLESTICK GEOMETRY)")
st.caption("基于真实 1H K 线影线与实体边界推导 | 零人工调节参数 | 100% 客观结构")

all_data = {}
source_track = {}
with st.spinner("解析 1H 真实蜡烛图结构中..."):
    for t in tickers:
        df_1h, src = fetch_1h_data(t, TIINGO_TOKEN)
        if df_1h is not None:
            all_data[t] = df_1h
            source_track[t] = src

results = []
for t in tickers:
    if t in all_data:
        res = calculate_pure_structure_levels(all_data[t])
        if res:
            res["TICKER"] = t
            res["SOURCE"] = source_track.get(t, "1H")
            results.append(res)

if results:
    df_res = pd.DataFrame(results)
    
    st.subheader("🎯 5M 执行参数一键复制座舱 (纯几何结构版)")
    selected_stock = st.selectbox("选择标的:", tickers, index=0)
    stock_data = df_res[df_res["TICKER"] == selected_stock].iloc[0]
    
    col_c1, col_c2 = st.columns([1, 1])
    with col_c1:
        st.markdown(f"#### 【{selected_stock}】 真实蜡烛几何战区")
        st.markdown(f"* **最新现价:** `${stock_data['Close']}`")
        st.markdown(f"* **🔴 1H SBR 阻力带 (实体上沿至最高影线):** `${stock_data['SBR_BOT']} ~ ${stock_data['SBR_TOP']}` (跨度 {round(stock_data['SBR_TOP'] - stock_data['SBR_BOT'], 2)} 点)")
        st.markdown(f"* **🟢 1H RBS 支撑带 (最低影线至实体下沿):** `${stock_data['RBS_BOT']} ~ ${stock_data['RBS_TOP']}` (跨度 {round(stock_data['RBS_TOP'] - stock_data['RBS_BOT'], 2)} 点)")
        st.markdown(f"* **📌 昨日极值 (PDL / PDH):** `${stock_data['PDL']} ~ ${stock_data['PDH']}`")
        st.markdown(f"* **🕒 盘前极值 (PML / PMH):** `${stock_data['PML']} ~ ${stock_data['PMH']}`")
        
    with col_c2:
        st.markdown("#### 📋 复制到富途 5M 指标顶部的 9 行代码")
        futu_code = f"""TREND_BIAS := {int(stock_data['TREND_BIAS'])};       {{ 宏观偏向: 1=多, -1=空 }}
SBR_TOP    := {stock_data['SBR_TOP']:.2f};   {{ 1H 阻力顶沿 (最高影线) }}
SBR_BOT    := {stock_data['SBR_BOT']:.2f};   {{ 1H 阻力底沿 (实体上沿) }}
RBS_TOP    := {stock_data['RBS_TOP']:.2f};   {{ 1H 支撑顶沿 (实体下沿) }}
RBS_BOT    := {stock_data['RBS_BOT']:.2f};   {{ 1H 支撑底沿 (最低影线) }}
PDH_LINE   := {stock_data['PDH']:.2f};   {{ 昨日最高价 PDH }}
PDL_LINE   := {stock_data['PDL']:.2f};   {{ 昨日最低价 PDL }}
PMH_LINE   := {stock_data['PMH']:.2f};   {{ 盘前最高价 PMH }}
PML_LINE   := {stock_data['PML']:.2f};   {{ 盘前最低价 PML }}"""
        st.code(futu_code, language="pascal")
