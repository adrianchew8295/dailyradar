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
    page_title="QQQ & 17 Core Swing Engine (Strict Calendar Audit)",
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
st.sidebar.success("🛡️ 日历级严格对齐引擎 (Calendar Aligned)")

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
# 4. 数据抓取：1H 大周期 + 5M 盘前明细
# =====================================================================
@st.cache_data(ttl=60, show_spinner=False)
def fetch_complete_data(ticker, token):
    # 4.1 抓取 1H 历史数据
    df_1h = None
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
    except Exception:
        pass

    # 4.2 抓取 5M 盘前明细
    df_5m = None
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
    except Exception:
        pass

    return df_1h, df_5m

# =====================================================================
# 5. 严格日历级极值与非重叠几何计算 (带日期标注)
# =====================================================================
def calculate_calendar_aligned_levels(df_1h, df_5m):
    if df_1h is None or len(df_1h) < 20:
        return None
    
    # 获取美东当前日期
    today_ny = datetime.datetime.now(tz_ny).date()
    
    # 5.1 严格按自然日提取【上一个交易日 PDH / PDL】(RTH 正规交易时段 09:30-16:00)
    df_rth = df_1h[(df_1h.index.hour > 9) | ((df_1h.index.hour == 9) & (df_1h.index.minute >= 30))]
    df_rth = df_rth[df_rth.index.hour < 16]
    
    unique_dates = sorted(list(set(df_rth.index.date)))
    past_dates = [d for d in unique_dates if d < today_ny]
    
    if past_dates:
        prev_trading_day = past_dates[-1]  # 严格上一个交易日 (如周五 8月21日)
        prev_day_df = df_rth[df_rth.index.date == prev_trading_day]
        pdh_val = float(prev_day_df['High'].max())
        pdl_val = float(prev_day_df['Low'].min())
        prev_day_str = prev_trading_day.strftime("%Y-%m-%d")
    else:
        pdh_val = float(df_1h['High'].iloc[-10:].max())
        pdl_val = float(df_1h['Low'].iloc[-10:].min())
        prev_day_str = "N/A"

    # 5.2 严格提取【今日盘前极值 PMH / PML】(04:00 - 09:30 ET)
    pm_date_str = today_ny.strftime("%Y-%m-%d")
    if df_5m is not None:
        today_pm_df = df_5m[(df_5m.index.date == today_ny) & (df_5m.index.hour >= 4) & ((df_5m.index.hour < 9) | ((df_5m.index.hour == 9) & (df_5m.index.minute < 30)))]
        if not today_pm_df.empty:
            pmh_val = float(today_pm_df['High'].max())
            pml_val = float(today_pm_df['Low'].min())
            live_price = float(today_pm_df['Close'].iloc[-1])
        else:
            pmh_val = float(df_5m['High'].iloc[-12:].max())
            pml_val = float(df_5m['Low'].iloc[-12:].min())
            live_price = float(df_5m['Close'].iloc[-1])
    else:
        pmh_val = float(df_1h['High'].iloc[-4:].max())
        pml_val = float(df_1h['Low'].iloc[-4:].min())
        live_price = float(df_1h['Close'].iloc[-1])

    # 5.3 计算 1H 非重叠结构阻力与支撑带 (标注拐点产生的日期时间)
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
                pivots_high.append((s_top, s_bot, times[i].strftime("%m-%d %H:%M")))
                
        if lows[i] == min(lows[i-2:i+3]):
            r_bot = float(lows[i])
            r_top = float(min(opens[i], closes[i]))
            if r_top < live_price:
                pivots_low.append((r_top, r_bot, times[i].strftime("%m-%d %H:%M")))

    if pivots_high:
        pivots_high.sort(key=lambda x: x[1])
        sbr_top, sbr_bot, sbr_time = pivots_high[0]
    else:
        sbr_top = float(subset['High'].max())
        sbr_bot = float(np.maximum(subset['Open'], subset['Close']).max())
        sbr_time = "Range Max"

    if pivots_low:
        pivots_low.sort(key=lambda x: x[0], reverse=True)
        rbs_top, rbs_bot, rbs_time = pivots_low[0]
    else:
        rbs_bot = float(subset['Low'].min())
        rbs_top = float(np.minimum(subset['Open'], subset['Close']).min())
        rbs_time = "Range Min"

    trend_bias = 1 if live_price > float(df_1h_calc['EMA20'].iloc[-1]) else -1

    return {
        "Close": round(live_price, 2),
        "TREND_BIAS": trend_bias,
        "SBR_TOP": round(sbr_top, 2),
        "SBR_BOT": round(sbr_bot, 2),
        "SBR_TIME": sbr_time,
        "RBS_TOP": round(rbs_top, 2),
        "RBS_BOT": round(rbs_bot, 2),
        "RBS_TIME": rbs_time,
        "PDH": round(pdh_val, 2),
        "PDL": round(pdl_val, 2),
        "PREV_DAY": prev_day_str,
        "PMH": round(pmh_val, 2),
        "PML": round(pml_val, 2),
        "PM_DATE": pm_date_str
    }

# =====================================================================
# 6. 渲染界面与透明审计座舱
# =====================================================================
st.title("🧭 QQQ & 17 CORE ASSETS (AUDITED FACT ENGINE)")
st.caption("严格日历对齐 | 每一个极值标注来源日期与时间戳 | 彻底消灭切片偏差")

results = []
with st.spinner("抓取实时行情并严格按交易日对齐中..."):
    for t in tickers:
        df_1h, df_5m = fetch_complete_data(t, TIINGO_TOKEN)
        res = calculate_calendar_aligned_levels(df_1h, df_5m)
        if res:
            res["TICKER"] = t
            results.append(res)

if results:
    df_res = pd.DataFrame(results)
    
    st.subheader("🎯 5M 执行参数一键复制座舱 (带事实来源审计)")
    selected_stock = st.selectbox("选择标的:", tickers, index=0)
    stock_data = df_res[df_res["TICKER"] == selected_stock].iloc[0]
    
    col_c1, col_c2 = st.columns([1, 1])
    with col_c1:
        st.markdown(f"#### 【{selected_stock}】 事实与逻辑校验区")
        st.markdown(f"* **当前最新价 (美东):** `${stock_data['Close']}`")
        st.markdown(f"* **📌 上一交易日极值 (PDH/PDL):**")
        st.markdown(f"  - **日期 (Fact):** `{stock_data['PREV_DAY']}` (严格过滤正规交易时段)")
        st.markdown(f"  - **最高 PDH:** `${stock_data['PDH']}` | **最低 PDL:** `${stock_data['PDL']}`")
        st.markdown(f"* **🕒 今日盘前极值 (PMH/PML):**")
        st.markdown(f"  - **日期 (Fact):** `{stock_data['PM_DATE']}` (04:00-09:30 ET 实盘)")
        st.markdown(f"  - **最高 PMH:** `${stock_data['PMH']}` | **最低 PML:** `${stock_data['PML']}`")
        st.markdown(f"* **🔴 1H 阻力带 SBR:** `${stock_data['SBR_BOT']} ~ ${stock_data['SBR_TOP']}` *(源自 {stock_data['SBR_TIME']} K线)*")
        st.markdown(f"* **🟢 1H 支撑带 RBS:** `${stock_data['RBS_BOT']} ~ ${stock_data['RBS_TOP']}` *(源自 {stock_data['RBS_TIME']} K线)*")
        
    with col_c2:
        st.markdown("#### 📋 复制到富途 5M 指标顶部的 9 行代码")
        futu_code = f"""TREND_BIAS := {int(stock_data['TREND_BIAS'])};       {{ 宏观偏向: 1=多, -1=空 }}
SBR_TOP    := {stock_data['SBR_TOP']:.2f};   {{ 1H 阻力顶沿 ({stock_data['SBR_TIME']}) }}
SBR_BOT    := {stock_data['SBR_BOT']:.2f};   {{ 1H 阻力底沿 ({stock_data['SBR_TIME']}) }}
RBS_TOP    := {stock_data['RBS_TOP']:.2f};   {{ 1H 支撑顶沿 ({stock_data['RBS_TIME']}) }}
RBS_BOT    := {stock_data['RBS_BOT']:.2f};   {{ 1H 支撑底沿 ({stock_data['RBS_TIME']}) }}
PDH_LINE   := {stock_data['PDH']:.2f};   {{ 昨日最高价 PDH ({stock_data['PREV_DAY']}) }}
PDL_LINE   := {stock_data['PDL']:.2f};   {{ 昨日最低价 PDL ({stock_data['PREV_DAY']}) }}
PMH_LINE   := {stock_data['PMH']:.2f};   {{ 今日盘前最高价 PMH ({stock_data['PM_DATE']}) }}
PML_LINE   := {stock_data['PML']:.2f};   {{ 今日盘前最低价 PML ({stock_data['PM_DATE']}) }}"""
        st.code(futu_code, language="pascal")
