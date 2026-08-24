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
    page_title="QQQ & 17 Core Swing Engine (Live Pre-market)",
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
st.sidebar.success("🛡️ 实时盘前抓取 (Live Pre-market 04:00-09:30 ET)")

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
# 4. 1-Hour 大周期与 5M 实时盘前双引擎抓取
# =====================================================================
@st.cache_data(ttl=60, show_spinner=False)
def fetch_complete_data(ticker, token):
    # 4.1 抓取 1H 历史大周期 (用来算 1H SBR / RBS)
    df_1h = None
    start_date = (datetime.datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    url = f"https://api.tiingo.com/iex/{ticker}/prices?startDate={start_date}&resampleFreq=1hour&token={token}&columns=open,high,low,close,volume"
    headers = {'Content-Type': 'application/json'}
    try:
        resp = requests.get(url, headers=headers, timeout=6)
        if resp.status_code == 200:
            data = resp.json()
            if data and isinstance(data, list) and len(data) >= 20:
                df_t = pd.DataFrame(data)
                df_t['date'] = pd.to_datetime(df_t['date'])
                df_t.set_index('date', inplace=True)
                df_t.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'}, inplace=True)
                df_1h = df_t[['Open', 'High', 'Low', 'Close', 'Volume']].sort_index()
    except Exception:
        pass

    if df_1h is None:
        try:
            df_yf_1h = yf.download(ticker, period="1mo", interval="1h", progress=False)
            if df_yf_1h is not None and not df_yf_1h.empty:
                if isinstance(df_yf_1h.columns, pd.MultiIndex):
                    df_yf_1h.columns = df_yf_1h.columns.get_level_values(0)
                df_1h = df_yf_1h[['Open', 'High', 'Low', 'Close', 'Volume']].dropna().sort_index()
        except Exception:
            pass

    # 4.2 专门抓取包含盘前盘后 (prepost=True) 的最近 5M K 线，用于精准提取 PMH / PML
    pmh, pml, live_price = None, None, None
    src = "Tiingo + yfinance(Pre-market)"
    try:
        df_5m = yf.download(ticker, period="5d", interval="5m", prepost=True, progress=False)
        if df_5m is not None and not df_5m.empty:
            if isinstance(df_5m.columns, pd.MultiIndex):
                df_5m.columns = df_5m.columns.get_level_values(0)
            
            # 转为美东时间
            df_5m = df_5m.tz_convert("America/New_York")
            latest_bar = df_5m.iloc[-1]
            live_price = float(latest_bar['Close'])
            
            # 过滤出今天美东时间 04:00 之后的盘前 K 线
            today_ny = datetime.datetime.now(tz_ny).date()
            premarket_df = df_5m[(df_5m.index.date == today_ny) & (df_5m.index.hour >= 4) & (df_5m.index.hour < 10)]
            
            if not premarket_df.empty:
                pmh = float(premarket_df['High'].max())
                pml = float(premarket_df['Low'].min())
            else:
                # 若今天盘前还未产生数据，取最近 4 根 5M 的极值
                pmh = float(df_5m['High'].iloc[-12:].max())
                pml = float(df_5m['Low'].iloc[-12:].min())
    except Exception:
        src = "Fallback Source"

    return df_1h, pmh, pml, live_price, src

# =====================================================================
# 5. 严格几何结构与盘前融合计算
# =====================================================================
def calculate_levels_with_premarket(df_1h, pmh_live, pml_live, live_price):
    if df_1h is None or len(df_1h) < 20:
        return None
    
    df = df_1h.copy()
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    
    # 优先使用实时盘前现价，若无则使用 1H 最新收盘价
    latest_close = float(live_price) if live_price is not None else float(df['Close'].iloc[-1])
    
    subset = df.iloc[-40:].copy()
    highs = subset['High'].values
    lows = subset['Low'].values
    opens = subset['Open'].values
    closes = subset['Close'].values
    
    pivots_high_list = []
    pivots_low_list = []
    
    for i in range(2, len(subset) - 2):
        if highs[i] == max(highs[i-2:i+3]):
            s_top = float(highs[i])
            s_bot = float(max(opens[i], closes[i]))
            if s_bot > latest_close:
                pivots_high_list.append((s_top, s_bot))
                
        if lows[i] == min(lows[i-2:i+3]):
            r_bot = float(lows[i])
            r_top = float(min(opens[i], closes[i]))
            if r_top < latest_close:
                pivots_low_list.append((r_top, r_bot))
                
    if pivots_high_list:
        pivots_high_list.sort(key=lambda x: x[1])
        sbr_top, sbr_bot = pivots_high_list[0]
    else:
        above_closes = subset[subset['Close'] > latest_close]
        if not above_closes.empty:
            sbr_top = float(above_closes['High'].max())
            sbr_bot = float(np.maximum(above_closes['Open'], above_closes['Close']).min())
        else:
            sbr_top = round(latest_close * 1.015, 2)
            sbr_bot = round(latest_close * 1.008, 2)
        
    if pivots_low_list:
        pivots_low_list.sort(key=lambda x: x[0], reverse=True)
        rbs_top, rbs_bot = pivots_low_list[0]
    else:
        below_closes = subset[subset['Close'] < latest_close]
        if not below_closes.empty:
            rbs_bot = float(below_closes['Low'].min())
            rbs_top = float(np.minimum(below_closes['Open'], below_closes['Close']).max())
        else:
            rbs_top = round(latest_close * 0.992, 2)
            rbs_bot = round(latest_close * 0.985, 2)
            
    # 提取昨日正规交易时段极值 (PDH / PDL)
    pdh_val = round(float(subset['High'].iloc[-14:-7].max()), 2) if len(subset) >= 14 else round(float(subset['High'].max()), 2)
    pdl_val = round(float(subset['Low'].iloc[-14:-7].min()), 2) if len(subset) >= 14 else round(float(subset['Low'].min()), 2)
    
    # 真实盘前极值 (若未抓到则兜底)
    pmh_val = round(float(pmh_live), 2) if pmh_live is not None else round(float(subset['High'].iloc[-4:].max()), 2)
    pml_val = round(float(pml_live), 2) if pml_live is not None else round(float(subset['Low'].iloc[-4:].min()), 2)
    
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
# 6. 主程序渲染
# =====================================================================
st.title("🧭 QQQ & 17 CORE ASSETS (LIVE PRE-MARKET ENGINE)")
st.caption("1H 纯客观非重叠几何 + 5M 实时盘前极值 (04:00-09:30 ET Live)")

results = []
with st.spinner("抓取实时盘前价格与 1H 结构中..."):
    for t in tickers:
        df_1h, pmh, pml, live_price, src = fetch_complete_data(t, TIINGO_TOKEN)
        res = calculate_levels_with_premarket(df_1h, pmh, pml, live_price)
        if res:
            res["TICKER"] = t
            res["SOURCE"] = src
            results.append(res)

if results:
    df_res = pd.DataFrame(results)
    
    st.subheader("🎯 5M 执行参数一键复制座舱 (实时盘前对齐版)")
    selected_stock = st.selectbox("选择标的:", tickers, index=0)
    stock_data = df_res[df_res["TICKER"] == selected_stock].iloc[0]
    
    col_c1, col_c2 = st.columns([1, 1])
    with col_c1:
        st.markdown(f"#### 【{selected_stock}】 盘前实时数据")
        st.markdown(f"* **当前最新价 (含盘前):** `${stock_data['Close']}`")
        st.markdown(f"* **🔴 1H SBR 阻力带 (现价上方):** `${stock_data['SBR_BOT']} ~ ${stock_data['SBR_TOP']}`")
        st.markdown(f"* **🟢 1H RBS 支撑带 (现价下方):** `${stock_data['RBS_BOT']} ~ ${stock_data['RBS_TOP']}`")
        st.markdown(f"* **📌 昨日极值 (PDL / PDH):** `${stock_data['PDL']} ~ ${stock_data['PDH']}`")
        st.markdown(f"* **⚡ 真实盘前极值 (PML / PMH):** `${stock_data['PML']} ~ ${stock_data['PMH']}`")
        st.caption(f"数据通道: `{stock_data['SOURCE']}`")
        
    with col_c2:
        st.markdown("#### 📋 复制到富途 5M 指标顶部的 9 行代码")
        futu_code = f"""TREND_BIAS := {int(stock_data['TREND_BIAS'])};       {{ 宏观偏向: 1=多, -1=空 }}
SBR_TOP    := {stock_data['SBR_TOP']:.2f};   {{ 1H 阻力顶沿 }}
SBR_BOT    := {stock_data['SBR_BOT']:.2f};   {{ 1H 阻力底沿 }}
RBS_TOP    := {stock_data['RBS_TOP']:.2f};   {{ 1H 支撑顶沿 }}
RBS_BOT    := {stock_data['RBS_BOT']:.2f};   {{ 1H 支撑底沿 }}
PDH_LINE   := {stock_data['PDH']:.2f};   {{ 昨日最高价 PDH }}
PDL_LINE   := {stock_data['PDL']:.2f};   {{ 昨日最低价 PDL }}
PMH_LINE   := {stock_data['PMH']:.2f};   {{ 实时盘前最高价 PMH }}
PML_LINE   := {stock_data['PML']:.2f};   {{ 实时盘前最低价 PML }}"""
        st.code(futu_code, language="pascal")
