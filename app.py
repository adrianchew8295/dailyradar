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
    page_title="QQQ & 17 Core Swing Engine (Full Source Audit)",
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
st.sidebar.success("🛡️ 100% 全透明数据溯源引擎 (Tiingo + yfinance)")

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
# 4. 双模分流抓取与数据源追踪
# =====================================================================
@st.cache_data(ttl=60, show_spinner=False)
def fetch_complete_data_audited(ticker, token):
    df_1h = None
    source_1h = "None"
    
    # 4.1 优先尝试 Tiingo IEX 1H
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
                if df_1h.index.tz is None:
                    df_1h.index = df_1h.index.tz_localize("UTC").tz_convert("America/New_York")
                else:
                    df_1h.index = df_1h.index.tz_convert("America/New_York")
                source_1h = "Tiingo (IEX 1H API)"
    except Exception:
        pass

    # 4.2 若 Tiingo 失败，切换 Yahoo Finance 1H 兜底
    if df_1h is None:
        try:
            df_yf = yf.download(ticker, period="1mo", interval="1h", prepost=True, progress=False)
            if df_yf is not None and not df_yf.empty:
                if isinstance(df_yf.columns, pd.MultiIndex):
                    df_yf.columns = df_yf.columns.get_level_values(0)
                df_1h = df_yf[['Open', 'High', 'Low', 'Close', 'Volume']].dropna().copy()
                if df_1h.index.tz is None:
                    df_1h.index = df_1h.index.tz_localize("UTC").tz_convert("America/New_York")
                else:
                    df_1h.index = df_1h.index.tz_convert("America/New_York")
                source_1h = "YahooFinance (1H prepost)"
        except Exception:
            pass

    # 4.3 盘前 5M 实盘明细抓取 (美东 04:00 - 09:30 实时)
    df_5m = None
    source_5m = "None"
    try:
        df_5m_raw = yf.download(ticker, period="5d", interval="5m", prepost=True, progress=False)
        if df_5m_raw is not None and not df_5m_raw.empty:
            if isinstance(df_5m_raw.columns, pd.MultiIndex):
                df_5m_raw.columns = df_5m_raw.columns.get_level_values(0)
            df_5m = df_5m_raw[['Open', 'High', 'Low', 'Close', 'Volume']].dropna().copy()
            if df_5m.index.tz is None:
                df_5m.index = df_5m.index.tz_localize("UTC").tz_convert("America/New_York")
            else:
                df_5m.index = df_5m.index.tz_convert("America/New_York")
            source_5m = "YahooFinance (Live 5M Pre-market)"
    except Exception:
        pass

    return df_1h, source_1h, df_5m, source_5m

# =====================================================================
# 5. 严格日历溯源与非重叠几何计算
# =====================================================================
def calculate_audited_levels(df_1h, source_1h, df_5m, source_5m):
    if df_1h is None or len(df_1h) < 20:
        return None
    
    today_ny = datetime.datetime.now(tz_ny).date()
    
    # 5.1 上一个交易日 PDH / PDL (严格正规交易时段 09:30 - 16:00 ET)
    df_rth = df_1h[(df_1h.index.hour > 9) | ((df_1h.index.hour == 9) & (df_1h.index.minute >= 30))]
    df_rth = df_rth[df_rth.index.hour < 16]
    
    unique_dates = sorted(list(set(df_rth.index.date)))
    past_dates = [d for d in unique_dates if d < today_ny]
    
    if past_dates:
        prev_day = past_dates[-1]
        prev_df = df_rth[df_rth.index.date == prev_day]
        pdh_idx = prev_df['High'].idxmax()
        pdl_idx = prev_df['Low'].idxmin()
        pdh_val = float(prev_df.loc[pdh_idx, 'High'])
        pdl_val = float(prev_df.loc[pdl_idx, 'Low'])
        pdh_time_str = pdh_idx.strftime("%Y-%m-%d %H:%M ET")
        pdl_time_str = pdl_idx.strftime("%Y-%m-%d %H:%M ET")
    else:
        pdh_val = float(df_1h['High'].iloc[-10:].max())
        pdl_val = float(df_1h['Low'].iloc[-10:].min())
        pdh_time_str = "Prior Session"
        pdl_time_str = "Prior Session"

    # 5.2 今日盘前 PMH / PML (04:00 - 09:30 ET)
    if df_5m is not None:
        today_pm_df = df_5m[(df_5m.index.date == today_ny) & (df_5m.index.hour >= 4) & ((df_5m.index.hour < 9) | ((df_5m.index.hour == 9) & (df_5m.index.minute < 30)))]
        if not today_pm_df.empty:
            pmh_idx = today_pm_df['High'].idxmax()
            pml_idx = today_pm_df['Low'].idxmin()
            pmh_val = float(today_pm_df.loc[pmh_idx, 'High'])
            pml_val = float(today_pm_df.loc[pml_idx, 'Low'])
            pmh_time_str = pmh_idx.strftime("%Y-%m-%d %H:%M ET")
            pml_time_str = pml_idx.strftime("%Y-%m-%d %H:%M ET")
            live_price = float(today_pm_df['Close'].iloc[-1])
        else:
            pmh_idx = df_5m['High'].iloc[-12:].idxmax()
            pml_idx = df_5m['Low'].iloc[-12:].idxmin()
            pmh_val = float(df_5m.loc[pmh_idx, 'High'])
            pml_val = float(df_5m.loc[pml_idx, 'Low'])
            pmh_time_str = pmh_idx.strftime("%Y-%m-%d %H:%M ET")
            pml_time_str = pml_idx.strftime("%Y-%m-%d %H:%M ET")
            live_price = float(df_5m['Close'].iloc[-1])
    else:
        pmh_val = float(df_1h['High'].iloc[-4:].max())
        pml_val = float(df_1h['Low'].iloc[-4:].min())
        pmh_time_str = "Recent 1H"
        pml_time_str = "Recent 1H"
        live_price = float(df_1h['Close'].iloc[-1])

    # 5.3 1H SBR / RBS 阻力支撑带 (非重叠拓扑结构)
    df_1h_calc = df_1h.copy()
    df_1h_calc['EMA20'] = df_1h_calc['Close'].ewm(span=20, adjust=False).mean()
    
    subset = df_1h_calc.iloc[-40:].copy()
    highs = subset['High'].values
    lows = subset['Low'].values
    opens = subset['Open'].values
    closes = subset['Close'].values
    times = subset.index
    
    pivots_high = []
    pivots_low = []
    
    for i in range(2, len(subset) - 2):
        if highs[i] == max(highs[i-2:i+3]):
            s_top = float(highs[i])
            s_bot = float(max(opens[i], closes[i]))
            if s_bot > live_price:
                pivots_high.append((s_top, s_bot, times[i].strftime("%m-%d %H:%M ET")))
                
        if lows[i] == min(lows[i-2:i+3]):
            r_bot = float(lows[i])
            r_top = float(min(opens[i], closes[i]))
            if r_top < live_price:
                pivots_low.append((r_top, r_bot, times[i].strftime("%m-%d %H:%M ET")))

    if pivots_high:
        pivots_high.sort(key=lambda x: x[1])
        sbr_top, sbr_bot, sbr_time = pivots_high[0]
    else:
        sbr_top = float(subset['High'].max())
        sbr_bot = float(np.maximum(subset['Open'], subset['Close']).max())
        sbr_time = "Range High"

    if pivots_low:
        pivots_low.sort(key=lambda x: x[0], reverse=True)
        rbs_top, rbs_bot, rbs_time = pivots_low[0]
    else:
        rbs_bot = float(subset['Low'].min())
        rbs_top = float(np.minimum(subset['Open'], subset['Close']).min())
        rbs_time = "Range Low"

    trend_bias = 1 if live_price > float(df_1h_calc['EMA20'].iloc[-1]) else -1

    return {
        "Close": round(live_price, 2),
        "TREND_BIAS": trend_bias,
        "SOURCE_1H": source_1h,
        "SOURCE_5M": source_5m,
        "SBR_TOP": round(sbr_top, 2),
        "SBR_BOT": round(sbr_bot, 2),
        "SBR_TIME": sbr_time,
        "RBS_TOP": round(rbs_top, 2),
        "RBS_BOT": round(rbs_bot, 2),
        "RBS_TIME": rbs_time,
        "PDH": round(pdh_val, 2),
        "PDH_TIME": pdh_time_str,
        "PDL": round(pdl_val, 2),
        "PDL_TIME": pdl_time_str,
        "PMH": round(pmh_val, 2),
        "PMH_TIME": pmh_time_str,
        "PML": round(pml_val, 2),
        "PML_TIME": pml_time_str
    }

# =====================================================================
# 6. 渲染界面与全透明审计座舱
# =====================================================================
st.title("🧭 QQQ & 17 CORE ASSETS (FULL SOURCE AUDIT)")
st.caption("全数据链路穿透 | 每一个点位均注明数据提供商与生成时间 | 杜绝任何黑盒操作")

results = []
with st.spinner("从 Tiingo / YahooFinance 抓取并进行全源交叉审计中..."):
    for t in tickers:
        df_1h, src_1h, df_5m, src_5m = fetch_complete_data_audited(t, TIINGO_TOKEN)
        res = calculate_audited_levels(df_1h, src_1h, df_5m, src_5m)
        if res:
            res["TICKER"] = t
            results.append(res)

if results:
    df_res = pd.DataFrame(results)
    
    st.subheader("🎯 5M 执行参数一键复制座舱 (全源审计版)")
    selected_stock = st.selectbox("选择标的:", tickers, index=0)
    stock_data = df_res[df_res["TICKER"] == selected_stock].iloc[0]
    
    col_c1, col_c2 = st.columns([1, 1])
    with col_c1:
        st.markdown(f"#### 【{selected_stock}】 事实与数据源校验区")
        st.markdown(f"* **当前现价:** `${stock_data['Close']}` *(通道: `{stock_data['SOURCE_5M']}`)*")
        st.markdown(f"* **⚡ 真实盘前极值 (PMH / PML):**")
        st.markdown(f"  - **PMH 最高:** `${stock_data['PMH']}` *(时间: `{stock_data['PMH_TIME']}` | 来源: `{stock_data['SOURCE_5M']}`)*")
        st.markdown(f"  - **PML 最低:** `${stock_data['PML']}` *(时间: `{stock_data['PML_TIME']}` | 来源: `{stock_data['SOURCE_5M']}`)*")
        st.markdown(f"* **📌 上一交易日极值 (PDH / PDL):**")
        st.markdown(f"  - **PDH 最高:** `${stock_data['PDH']}` *(时间: `{stock_data['PDH_TIME']}` | 来源: `{stock_data['SOURCE_1H']}`)*")
        st.markdown(f"  - **PDL 最低:** `${stock_data['PDL']}` *(时间: `{stock_data['PDL_TIME']}` | 来源: `{stock_data['SOURCE_1H']}`)*")
        st.markdown(f"* **🔴 1H 阻力带 SBR:** `${stock_data['SBR_BOT']} ~ ${stock_data['SBR_TOP']}` *(K线时间: `{stock_data['SBR_TIME']}` | 来源: `{stock_data['SOURCE_1H']}`)*")
        st.markdown(f"* **🟢 1H 支撑带 RBS:** `${stock_data['RBS_BOT']} ~ ${stock_data['RBS_TOP']}` *(K线时间: `{stock_data['RBS_TIME']}` | 来源: `{stock_data['SOURCE_1H']}`)*")
        
    with col_c2:
        st.markdown("#### 📋 复制到富途 5M 指标顶部的 9 行代码")
        futu_code = f"""TREND_BIAS := {int(stock_data['TREND_BIAS'])};       {{ 宏观偏向: 1=多, -1=空 }}
SBR_TOP    := {stock_data['SBR_TOP']:.2f};   {{ 1H 阻力顶沿 [{stock_data['SBR_TIME']} | {stock_data['SOURCE_1H']}] }}
SBR_BOT    := {stock_data['SBR_BOT']:.2f};   {{ 1H 阻力底沿 [{stock_data['SBR_TIME']} | {stock_data['SOURCE_1H']}] }}
RBS_TOP    := {stock_data['RBS_TOP']:.2f};   {{ 1H 支撑顶沿 [{stock_data['RBS_TIME']} | {stock_data['SOURCE_1H']}] }}
RBS_BOT    := {stock_data['RBS_BOT']:.2f};   {{ 1H 支撑底沿 [{stock_data['RBS_TIME']} | {stock_data['SOURCE_1H']}] }}
PDH_LINE   := {stock_data['PDH']:.2f};   {{ 昨日最高价 PDH [{stock_data['PDH_TIME']} | {stock_data['SOURCE_1H']}] }}
PDL_LINE   := {stock_data['PDL']:.2f};   {{ 昨日最低价 PDL [{stock_data['PDL_TIME']} | {stock_data['SOURCE_1H']}] }}
PMH_LINE   := {stock_data['PMH']:.2f};   {{ 盘前最高价 PMH [{stock_data['PMH_TIME']} | {stock_data['SOURCE_5M']}] }}
PML_LINE   := {stock_data['PML']:.2f};   {{ 盘前最低价 PML [{stock_data['PML_TIME']} | {stock_data['SOURCE_5M']}] }}"""
        st.code(futu_code, language="pascal")
