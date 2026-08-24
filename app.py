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
# 1. 核心凭证与资产池定义
# =====================================================================
TIINGO_TOKEN = "bcffe3a5cf7eeef085e405cfa4a3e5691b976217"

st.set_page_config(
    page_title="QQQ Engine & 17 Core Portfolio Radar",
    page_icon="🧭",
    layout="wide"
)

TICKER_QQQ = "QQQ"
BIG_SEVEN = ["NVDA", "AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA"]
LEADERS = ["MU", "TSM", "AMD", "AVGO", "QCOM", "ARM", "ASML", "PLTR", "NFLX", "INTC"]
ALL_TICKERS = [TICKER_QQQ] + BIG_SEVEN + LEADERS

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
# 3. 侧边栏与时光机配置
# =====================================================================
st.sidebar.title("🎛️ CONTROL CENTER")
st.sidebar.success("🛡️ 双模容错引擎 (Tiingo + yfinance)")

tickers_input = st.sidebar.text_area(
    "监控资产池 (QQQ + 17 核心标的)",
    value=", ".join(ALL_TICKERS),
    height=100
)
tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]

st.sidebar.markdown("---")
st.sidebar.subheader("⏳ PASS RECORD (历史时光机)")
audit_date = st.sidebar.date_input(
    "选择基准复盘日期",
    value=datetime.date.today(),
    max_value=datetime.date.today()
)

btn_clear = st.sidebar.button("🧹 清除缓存并强制刷新", type="secondary")
if btn_clear:
    st.cache_data.clear()
    st.rerun()

# =====================================================================
# 4. 双模高可靠数据抓取引擎 (Tiingo 优先，429 自动无缝切换 yfinance)
# =====================================================================
@st.cache_data(ttl=60, show_spinner=False)
def fetch_complete_data_audited(ticker, token):
    df_1h = None
    source_1h = "None"
    start_date = (datetime.datetime.now() - timedelta(days=45)).strftime("%Y-%m-%d")
    
    # 4.1 优先请求 Tiingo 1H
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
                df_1h.index = df_1h.index.tz_localize("UTC").tz_convert("America/New_York") if df_1h.index.tz is None else df_1h.index.tz_convert("America/New_York")
                source_1h = "Tiingo (IEX 1H API)"
    except Exception:
        pass

    # 4.2 兜底请求 yfinance 1H
    if df_1h is None:
        try:
            df_yf = yf.download(ticker, period="1mo", interval="1h", prepost=True, progress=False)
            if df_yf is not None and not df_yf.empty:
                if isinstance(df_yf.columns, pd.MultiIndex):
                    df_yf.columns = df_yf.columns.get_level_values(0)
                df_1h = df_yf[['Open', 'High', 'Low', 'Close', 'Volume']].dropna().copy()
                df_1h.index = df_1h.index.tz_localize("UTC").tz_convert("America/New_York") if df_1h.index.tz is None else df_1h.index.tz_convert("America/New_York")
                source_1h = "YahooFinance (1H prepost)"
        except Exception:
            pass

    # 4.3 请求 yfinance 5M 实时盘前
    df_5m = None
    source_5m = "None"
    try:
        df_5m_raw = yf.download(ticker, period="5d", interval="5m", prepost=True, progress=False)
        if df_5m_raw is not None and not df_5m_raw.empty:
            if isinstance(df_5m_raw.columns, pd.MultiIndex):
                df_5m_raw.columns = df_5m_raw.columns.get_level_values(0)
            df_5m = df_5m_raw[['Open', 'High', 'Low', 'Close', 'Volume']].dropna().copy()
            df_5m.index = df_5m.index.tz_localize("UTC").tz_convert("America/New_York") if df_5m.index.tz is None else df_5m.index.tz_convert("America/New_York")
            source_5m = "YahooFinance (Live 5M Pre-market)"
    except Exception:
        pass

    return df_1h, source_1h, df_5m, source_5m

# =====================================================================
# 5. 三维共振算法与结构计算核心
# =====================================================================
def calculate_audited_levels(df_1h, source_1h, df_5m, source_5m, ticker):
    if df_1h is None or len(df_1h) < 25:
        return None
    
    today_ny = datetime.datetime.now(tz_ny).date()
    
    # 昨日 RTH 极值 (09:30 - 16:00 ET)
    df_rth = df_1h[(df_1h.index.hour > 9) | ((df_1h.index.hour == 9) & (df_1h.index.minute >= 30))]
    df_rth = df_rth[df_rth.index.hour < 16]
    past_dates = sorted(list(set(df_rth.index.date)))
    past_dates = [d for d in past_dates if d < today_ny]
    
    if past_dates:
        prev_df = df_rth[df_rth.index.date == past_dates[-1]]
        pdh_idx, pdl_idx = prev_df['High'].idxmax(), prev_df['Low'].idxmin()
        pdh_val, pdl_val = float(prev_df.loc[pdh_idx, 'High']), float(prev_df.loc[pdl_idx, 'Low'])
        pdh_time_str, pdl_time_str = pdh_idx.strftime("%Y-%m-%d %H:%M ET"), pdl_idx.strftime("%Y-%m-%d %H:%M ET")
    else:
        pdh_val, pdl_val = float(df_1h['High'].iloc[-10:].max()), float(df_1h['Low'].iloc[-10:].min())
        pdh_time_str, pdl_time_str = "Prior Session", "Prior Session"

    # 今日盘前极值 (04:00 - 09:30 ET)
    if df_5m is not None:
        today_pm = df_5m[(df_5m.index.date == today_ny) & (df_5m.index.hour >= 4) & ((df_5m.index.hour < 9) | ((df_5m.index.hour == 9) & (df_5m.index.minute < 30)))]
        if not today_pm.empty:
            pmh_idx, pml_idx = today_pm['High'].idxmax(), today_pm['Low'].idxmin()
            pmh_val, pml_val = float(today_pm.loc[pmh_idx, 'High']), float(today_pm.loc[pml_idx, 'Low'])
            pmh_time_str, pml_time_str = pmh_idx.strftime("%Y-%m-%d %H:%M ET"), pml_idx.strftime("%Y-%m-%d %H:%M ET")
            live_price = float(today_pm['Close'].iloc[-1])
        else:
            pmh_idx, pml_idx = df_5m['High'].iloc[-12:].idxmax(), df_5m['Low'].iloc[-12:].idxmin()
            pmh_val, pml_val = float(df_5m.loc[pmh_idx, 'High']), float(df_5m.loc[pml_idx, 'Low'])
            pmh_time_str, pml_time_str = pmh_idx.strftime("%Y-%m-%d %H:%M ET"), pml_idx.strftime("%Y-%m-%d %H:%M ET")
            live_price = float(df_5m['Close'].iloc[-1])
    else:
        pmh_val, pml_val = float(df_1h['High'].iloc[-4:].max()), float(df_1h['Low'].iloc[-4:].min())
        pmh_time_str, pml_time_str = "Recent 1H", "Recent 1H"
        live_price = float(df_1h['Close'].iloc[-1])

    # 1H 结构带提取
    df_1h_calc = df_1h.copy()
    df_1h_calc['EMA20'] = df_1h_calc['Close'].ewm(span=20, adjust=False).mean()
    df_1h_calc['SMA50'] = df_1h_calc['Close'].rolling(window=50).mean()
    
    subset = df_1h_calc.iloc[-40:].copy()
    highs, lows, opens, closes, times = subset['High'].values, subset['Low'].values, subset['Open'].values, subset['Close'].values, subset.index
    
    pivots_high, pivots_low = [], []
    for i in range(2, len(subset) - 2):
        if highs[i] == max(highs[i-2:i+3]):
            pivots_high.append((float(highs[i]), float(max(opens[i], closes[i])), times[i].strftime("%m-%d %H:%M ET"), highs[i]))
        if lows[i] == min(lows[i-2:i+3]):
            pivots_low.append((float(min(opens[i], closes[i])), float(lows[i]), times[i].strftime("%m-%d %H:%M ET"), lows[i]))

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

    # 三维共振判决
    ema20_now = float(df_1h_calc['EMA20'].iloc[-1])
    sma50_now = float(df_1h_calc['SMA50'].iloc[-1]) if not np.isnan(df_1h_calc['SMA50'].iloc[-1]) else ema20_now
    score_ma = 1 if (live_price > ema20_now and ema20_now >= sma50_now) else (-1 if (live_price < ema20_now and ema20_now <= sma50_now) else 0)

    score_hhll = 0
    if len(pivots_high) >= 2 and len(pivots_low) >= 2:
        last_2_h, last_2_l = [p[3] for p in pivots_high[-2:]], [p[3] for p in pivots_low[-2:]]
        if last_2_h[1] > last_2_h[0] and last_2_l[1] > last_2_l[0]: score_hhll = 1
        elif last_2_h[1] < last_2_h[0] and last_2_l[1] < last_2_l[0]: score_hhll = -1

    ema20_prev = float(df_1h_calc['EMA20'].iloc[-5])
    ema_slope = (ema20_now - ema20_prev) / ema20_prev * 100
    score_slope = 1 if ema_slope > 0.15 else (-1 if ema_slope < -0.15 else 0)

    total_score = score_ma + score_hhll + score_slope
    final_bias = 1 if total_score >= 2 else (-1 if total_score <= -2 else 0)

    # 涨跌幅与轮动动作
    prev_close = float(df_1h['Close'].iloc[-2])
    chg_pct = (live_price - prev_close) / prev_close * 100
    
    if live_price >= sbr_bot: action = "🔴 止盈高抛 (Take Profit)"
    elif live_price <= rbs_top: action = "🟢 支撑轮动 (Rotation In)"
    elif live_price > ema20_now: action = "📈 多头持仓 (Holding)"
    else: action = "📉 偏弱观望 (Weak)"

    return {
        "TICKER": ticker,
        "Group": "Mag 7" if ticker in BIG_SEVEN else ("Index" if ticker == "QQQ" else "Growth"),
        "Close": round(live_price, 2),
        "Change%": round(chg_pct, 2),
        "Action": action,
        "TREND_BIAS": final_bias,
        "TOTAL_SCORE": total_score,
        "EMA20": round(ema20_now, 2),
        "SBR_TOP": round(sbr_top, 2), "SBR_BOT": round(sbr_bot, 2), "SBR_TIME": sbr_time,
        "RBS_TOP": round(rbs_top, 2), "RBS_BOT": round(rbs_bot, 2), "RBS_TIME": rbs_time,
        "PDH": round(pdh_val, 2), "PDH_TIME": pdh_time_str,
        "PDL": round(pdl_val, 2), "PDL_TIME": pdl_time_str,
        "PMH": round(pmh_val, 2), "PMH_TIME": pmh_time_str,
        "PML": round(pml_val, 2), "PML_TIME": pml_time_str,
        "SOURCE_1H": source_1h, "SOURCE_5M": source_5m
    }

# =====================================================================
# 6. 主程序渲染与时光机交互
# =====================================================================
st.title("🧭 QQQ 日内交易座舱 & 17 核心资产轮动雷达")

results = []
all_hist_data = {}
with st.spinner("执行三维共振运算与实时盘前对齐中..."):
    for t in tickers:
        df_1h, src_1h, df_5m, src_5m = fetch_complete_data_audited(t, TIINGO_TOKEN)
        if df_1h is not None:
            all_hist_data[t] = df_1h
        res = calculate_audited_levels(df_1h, src_1h, df_5m, src_5m, t)
        if res:
            results.append(res)

if results:
    df_res = pd.DataFrame(results)
    df_stocks = df_res[df_res["TICKER"] != "QQQ"]
    qqq_row = df_res[df_res["TICKER"] == "QQQ"].iloc[0]

    # --- 6.1 顶部战况与市场宽度指标卡 ---
    up_cnt = sum(df_stocks["Change%"] > 0)
    down_cnt = sum(df_stocks["Change%"] <= 0)
    mag7_up = sum(df_stocks[df_stocks["Group"] == "Mag 7"]["Change%"] > 0)
    breadth_pct = int(sum(df_stocks["Close"] > df_stocks["EMA20"]) / len(df_stocks) * 100)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("🎯 QQQ 最新现价", f"${qqq_row['Close']}", f"{qqq_row['Change%']}%")
    m2.metric("📊 17 股多空分布", f"{up_cnt} 涨 / {down_cnt} 跌", f"宽度: {breadth_pct}% > 20EMA")
    m3.metric("👑 Big 7 巨头动能", f"{mag7_up} / 7 支上涨", "决定 QQQ 真实推力")
    bias_desc = "🟢 偏多 (CALL)" if qqq_row['TREND_BIAS'] == 1 else ("🔴 偏空 (PUT)" if qqq_row['TREND_BIAS'] == -1 else "⚪ 震荡 (NEUTRAL)")
    m4.metric("🧭 QQQ 宏观定调", bias_desc, f"共振得分: {qqq_row['TOTAL_SCORE']} / 3")

    st.markdown("---")

    # --- 6.2 QQQ 专属 9 行参数一键复制区 (置顶固定) ---
    col_q1, col_q2 = st.columns([1, 1])
    with col_q1:
        st.subheader("📋 【QQQ 专属】富途 5M 复制区")
        st.markdown(f"* **现价通道:** `{qqq_row['SOURCE_5M']}` | **1H 通道:** `{qqq_row['SOURCE_1H']}`")
        st.markdown(f"* **⚡ 今日盘前极值:** `${qqq_row['PMH']}` ~ `${qqq_row['PML']}` *(时间: `{qqq_row['PMH_TIME']}`)*")
        st.markdown(f"* **📌 昨日常规极值:** `${qqq_row['PDH']}` ~ `${qqq_row['PDL']}` *(时间: `{qqq_row['PDH_TIME']}`)*")
        st.markdown(f"* **🔴 1H SBR 阻力区:** `${qqq_row['SBR_BOT']} ~ ${qqq_row['SBR_TOP']}` *(K线: `{qqq_row['SBR_TIME']}`)*")
        st.markdown(f"* **🟢 1H RBS 支撑区:** `${qqq_row['RBS_BOT']} ~ ${qqq_row['RBS_TOP']}` *(K线: `{qqq_row['RBS_TIME']}`)*")
    with col_q2:
        st.markdown("#### 复制到富途 5M 指标顶部 9 行代码")
        futu_code = f"""TREND_BIAS := {int(qqq_row['TREND_BIAS'])};       {{ 宏观偏向: 1=多, -1=空, 0=中立 [得分: {qqq_row['TOTAL_SCORE']}] }}
SBR_TOP    := {qqq_row['SBR_TOP']:.2f};   {{ 1H 阻力顶沿 [{qqq_row['SBR_TIME']}] }}
SBR_BOT    := {qqq_row['SBR_BOT']:.2f};   {{ 1H 阻力底沿 [{qqq_row['SBR_TIME']}] }}
RBS_TOP    := {qqq_row['RBS_TOP']:.2f};   {{ 1H 支撑顶沿 [{qqq_row['RBS_TIME']}] }}
RBS_BOT    := {qqq_row['RBS_BOT']:.2f};   {{ 1H 支撑底沿 [{qqq_row['RBS_TIME']}] }}
PDH_LINE   := {qqq_row['PDH']:.2f};   {{ 昨日最高价 PDH [{qqq_row['PDH_TIME']}] }}
PDL_LINE   := {qqq_row['PDL']:.2f};   {{ 昨日最低价 PDL [{qqq_row['PDL_TIME']}] }}
PMH_LINE   := {qqq_row['PMH']:.2f};   {{ 盘前最高价 PMH [{qqq_row['PMH_TIME']}] }}
PML_LINE   := {qqq_row['PML']:.2f};   {{ 盘前最低价 PML [{qqq_row['PML_TIME']}] }}"""
        st.code(futu_code, language="pascal")

    st.markdown("---")

    # --- 6.3 17 股轮动与止盈看板 ---
    st.subheader("🗺️ 17 支核心个股全景雷达 (轮动与止盈监控)")
    
    def highlight_action(val):
        if "止盈" in str(val):
            return "background-color: #49111c; color: #ffccd5; font-weight: bold;"
        elif "轮动" in str(val):
            return "background-color: #1b4332; color: #d8f3dc; font-weight: bold;"
        return ""

    display_cols = ["TICKER", "Group", "Close", "Change%", "Action", "EMA20", "RBS_TOP", "SBR_BOT", "PDL", "PDH", "SOURCE_5M"]
    styler = df_stocks[display_cols].sort_values(by="Change%", ascending=False).style
    if hasattr(styler, 'map'):
        styled_df = styler.map(highlight_action, subset=["Action"])
    else:
        styled_df = styler.applymap(highlight_action, subset=["Action"])
    st.dataframe(styled_df, use_container_width=True, height=480)

    # --- 6.4 历史时光机明细与导出 (Pass Record) ---
    st.markdown("---")
    st.subheader("⏳ 历史复盘时光机与数据导出 (Pass Record)")
    
    col_p1, col_p2 = st.columns([2, 8])
    with col_p1:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_res.to_excel(writer, index=False, sheet_name="Market_Report")
        st.download_button(
            label="📥 导出今日全量复盘报表 (.xlsx)",
            data=output.getvalue(),
            file_name=f"QQQ_Portfolio_Report_{audit_date.strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    
    with st.expander("🔍 展开查看 QQQ 与 17 股近 6 个交易日 1H 历史 K 线明细"):
        inspect_ticker = st.selectbox("选择复盘标的:", ALL_TICKERS, index=0)
        if inspect_ticker in all_hist_data:
            h_df = all_hist_data[inspect_ticker].tail(42).copy() # 约 6 个交易日
            h_df['EMA20'] = h_df['Close'].ewm(span=20, adjust=False).mean()
            st.dataframe(h_df.round(2).sort_index(ascending=False), use_container_width=True)
