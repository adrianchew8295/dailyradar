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
    page_title="QQQ & 17 Core Swing Engine (3D Bias Resonance)",
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
st.sidebar.success("🛡️ 三维大势客观共振引擎 (3D Resonance)")

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
# 4. 双模抓取与数据源追踪
# =====================================================================
@st.cache_data(ttl=60, show_spinner=False)
def fetch_complete_data_audited(ticker, token):
    df_1h = None
    source_1h = "None"
    
    start_date = (datetime.datetime.now() - timedelta(days=45)).strftime("%Y-%m-%d")
    url = f"https://api.tiingo.com/iex/{ticker}/prices?startDate={start_date}&resampleFreq=1hour&token={token}&columns=open,high,low,close,volume"
    headers = {'Content-Type': 'application/json'}
    try:
        resp = requests.get(url, headers=headers, timeout=6)
        if resp.status_code == 200:
            data = resp.json()
            if data and isinstance(data, list) and len(data) >= 30:
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
# 5. 三维共振 TREND_BIAS 算法与结构计算
# =====================================================================
def calculate_audited_levels(df_1h, source_1h, df_5m, source_5m):
    if df_1h is None or len(df_1h) < 30:
        return None
    
    today_ny = datetime.datetime.now(tz_ny).date()
    
    # 5.1 上一交易日 PDH / PDL (RTH 09:30 - 16:00 ET)
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

    # 5.3 结构带提取
    df_1h_calc = df_1h.copy()
    df_1h_calc['EMA20'] = df_1h_calc['Close'].ewm(span=20, adjust=False).mean()
    df_1h_calc['SMA50'] = df_1h_calc['Close'].rolling(window=50).mean()
    
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
            pivots_high.append((s_top, s_bot, times[i].strftime("%m-%d %H:%M ET"), highs[i]))
                
        if lows[i] == min(lows[i-2:i+3]):
            r_bot = float(lows[i])
            r_top = float(min(opens[i], closes[i]))
            pivots_low.append((r_top, r_bot, times[i].strftime("%m-%d %H:%M ET"), lows[i]))

    valid_highs = [p for p in pivots_high if p[1] > live_price]
    if valid_highs:
        valid_highs.sort(key=lambda x: x[1])
        sbr_top, sbr_bot, sbr_time, _ = valid_highs[0]
    else:
        sbr_top = float(subset['High'].max())
        sbr_bot = float(np.maximum(subset['Open'], subset['Close']).max())
        sbr_time = "Range High"

    valid_lows = [p for p in pivots_low if p[0] < live_price]
    if valid_lows:
        valid_lows.sort(key=lambda x: x[0], reverse=True)
        rbs_top, rbs_bot, rbs_time, _ = valid_lows[0]
    else:
        rbs_bot = float(subset['Low'].min())
        rbs_top = float(np.minimum(subset['Open'], subset['Close']).min())
        rbs_time = "Range Low"

    # =================================================================
    # 5.4 【三维共振客观判定 TREND_BIAS】
    # =================================================================
    # 维度一：双均线多头/空头排列 (EMA20 vs SMA50 & 价格位置)
    ema20_now = float(df_1h_calc['EMA20'].iloc[-1])
    sma50_now = float(df_1h_calc['SMA50'].iloc[-1]) if not np.isnan(df_1h_calc['SMA50'].iloc[-1]) else ema20_now
    
    score_ma = 0
    if live_price > ema20_now and ema20_now >= sma50_now:
        score_ma = 1
        ma_reason = "价格在20EMA之上且EMA金叉50SMA (多头排列)"
    elif live_price < ema20_now and ema20_now <= sma50_now:
        score_ma = -1
        ma_reason = "价格在20EMA之下且EMA死叉50SMA (空头排列)"
    else:
        score_ma = 0
        ma_reason = "均线交织缠绕 (震荡无明显排列)"

    # 维度二：Grimes 纯几何高低点结构 (HH/HL vs LH/LL)
    score_hhll = 0
    if len(pivots_high) >= 2 and len(pivots_low) >= 2:
        last_2_highs = [p[3] for p in pivots_high[-2:]]
        last_2_lows = [p[3] for p in pivots_low[-2:]]
        if last_2_highs[1] > last_2_highs[0] and last_2_lows[1] > last_2_lows[0]:
            score_hhll = 1
            hhll_reason = "近两个1H波段高低点持续抬高 (HH + HL 结构)"
        elif last_2_highs[1] < last_2_highs[0] and last_2_lows[1] < last_2_lows[0]:
            score_hhll = -1
            hhll_reason = "近两个1H波段高低点持续降低 (LH + LL 结构)"
        else:
            score_hhll = 0
            hhll_reason = "高低点结构扩张/收敛 (无单边方向)"
    else:
        hhll_reason = "拐点样本不足，默认中立"

    # 维度三：动量斜率 (20 EMA 斜率，排除走平震荡)
    ema20_prev = float(df_1h_calc['EMA20'].iloc[-5])
    ema_slope = (ema20_now - ema20_prev) / ema20_prev * 100
    score_slope = 0
    if ema_slope > 0.15:
        score_slope = 1
        slope_reason = f"20EMA向上倾斜 (+{ema_slope:.2f}%)"
    elif ema_slope < -0.15:
        score_slope = -1
        slope_reason = f"20EMA向下倾斜 ({ema_slope:.2f}%)"
    else:
        score_slope = 0
        slope_reason = f"20EMA走平 ({ema_slope:.2f}%)"

    # 三维总分裁决 (-3 ~ +3)
    total_score = score_ma + score_hhll + score_slope
    if total_score >= 2:
        final_bias = 1
        bias_desc = "🟢 强多头共振 (偏向做多)"
    elif total_score <= -2:
        final_bias = -1
        bias_desc = "🔴 强空头共振 (偏向做空)"
    else:
        final_bias = 0
        bias_desc = "⚪ 中立震荡 (多空双向均需严格形态)"

    return {
        "Close": round(live_price, 2),
        "TREND_BIAS": final_bias,
        "BIAS_DESC": bias_desc,
        "TOTAL_SCORE": total_score,
        "MA_REASON": ma_reason,
        "HHLL_REASON": hhll_reason,
        "SLOPE_REASON": slope_reason,
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
# 6. 渲染界面与全透明座舱
# =====================================================================
st.title("🧭 QQQ & 17 CORE ASSETS (3D BIAS RESONANCE ENGINE)")
st.caption("三维趋势共振 (均线排列 + HH/LL 结构 + 动量斜率) | 拒绝单均线送人头")

results = []
with st.spinner("执行三维趋势共振与日历级对齐运算中..."):
    for t in tickers:
        df_1h, src_1h, df_5m, src_5m = fetch_complete_data_audited(t, TIINGO_TOKEN)
        res = calculate_audited_levels(df_1h, src_1h, df_5m, src_5m)
        if res:
            res["TICKER"] = t
            results.append(res)

if results:
    df_res = pd.DataFrame(results)
    
    st.subheader("🎯 5M 执行参数一键复制座舱 (三维共振裁决版)")
    selected_stock = st.selectbox("选择标的:", tickers, index=0)
    stock_data = df_res[df_res["TICKER"] == selected_stock].iloc[0]
    
    col_c1, col_c2 = st.columns([1, 1])
    with col_c1:
        st.markdown(f"#### 【{selected_stock}】 三维大势与结构审计")
        st.markdown(f"* **宏观裁决:** `{stock_data['BIAS_DESC']}` (三维共振得分: `{stock_data['TOTAL_SCORE']} / 3`)")
        st.markdown(f"  - 1. 均线阶梯: `{stock_data['MA_REASON']}`")
        st.markdown(f"  - 2. 价格几何: `{stock_data['HHLL_REASON']}`")
        st.markdown(f"  - 3. 动量斜率: `{stock_data['SLOPE_REASON']}`")
        st.markdown("---")
        st.markdown(f"* **当前现价:** `${stock_data['Close']}` *(通道: `{stock_data['SOURCE_5M']}`)*")
        st.markdown(f"* **⚡ 真实盘前 (PMH / PML):** `${stock_data['PMH']}` ~ `${stock_data['PML']}` *(时间: `{stock_data['PMH_TIME']}`)*")
        st.markdown(f"* **📌 昨日极值 (PDH / PDL):** `${stock_data['PDH']}` ~ `${stock_data['PDL']}` *(时间: `{stock_data['PDH_TIME']}`)*")
        st.markdown(f"* **🔴 1H SBR 阻力带:** `${stock_data['SBR_BOT']} ~ ${stock_data['SBR_TOP']}` *(K线: `{stock_data['SBR_TIME']}`)*")
        st.markdown(f"* **🟢 1H RBS 支撑带:** `${stock_data['RBS_BOT']} ~ ${stock_data['RBS_TOP']}` *(K线: `{stock_data['RBS_TIME']}`)*")
        
    with col_c2:
        st.markdown("#### 📋 复制到富途 5M 指标顶部的 9 行代码")
        futu_code = f"""TREND_BIAS := {int(stock_data['TREND_BIAS'])};       {{ 宏观偏向: 1=多, -1=空, 0=中立 [得分: {stock_data['TOTAL_SCORE']}] }}
SBR_TOP    := {stock_data['SBR_TOP']:.2f};   {{ 1H 阻力顶沿 [{stock_data['SBR_TIME']}] }}
SBR_BOT    := {stock_data['SBR_BOT']:.2f};   {{ 1H 阻力底沿 [{stock_data['SBR_TIME']}] }}
RBS_TOP    := {stock_data['RBS_TOP']:.2f};   {{ 1H 支撑顶沿 [{stock_data['RBS_TIME']}] }}
RBS_BOT    := {stock_data['RBS_BOT']:.2f};   {{ 1H 支撑底沿 [{stock_data['RBS_TIME']}] }}
PDH_LINE   := {stock_data['PDH']:.2f};   {{ 昨日最高价 PDH [{stock_data['PDH_TIME']}] }}
PDL_LINE   := {stock_data['PDL']:.2f};   {{ 昨日最低价 PDL [{stock_data['PDL_TIME']}] }}
PMH_LINE   := {stock_data['PMH']:.2f};   {{ 盘前最高价 PMH [{stock_data['PMH_TIME']}] }}
PML_LINE   := {stock_data['PML']:.2f};   {{ 盘前最低价 PML [{stock_data['PML_TIME']}] }}"""
        st.code(futu_code, language="pascal")
