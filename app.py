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
# 3. 双模数据抓取引擎
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
            if data and isinstance(data, list) and len(data) >= 25:
                df_t = pd.DataFrame(data)
                df_t['date'] = pd.to_datetime(df_t['date'])
                df_t.set_index('date', inplace=True)
                df_t.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'}, inplace=True)
                df_1h = df_t[['Open', 'High', 'Low', 'Close', 'Volume']].sort_index()
                df_1h.index = df_1h.index.tz_localize("UTC").tz_convert("America/New_York") if df_1h.index.tz is None else df_1h.index.tz_convert("America/New_York")
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
                df_1h.index = df_1h.index.tz_localize("UTC").tz_convert("America/New_York") if df_1h.index.tz is None else df_1h.index.tz_convert("America/New_York")
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
            df_5m.index = df_5m.index.tz_localize("UTC").tz_convert("America/New_York") if df_5m.index.tz is None else df_5m.index.tz_convert("America/New_York")
            source_5m = "YahooFinance (Live 5M Pre-market)"
    except Exception:
        pass

    return df_1h, source_1h, df_5m, source_5m

# =====================================================================
# 4. 三维共振算法与战术点位解析
# =====================================================================
def calculate_audited_levels(df_1h, source_1h, df_5m, source_5m, ticker):
    if df_1h is None or len(df_1h) < 20:
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

    # 1H 结构带提取 (Grimes 拐点)
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

    # 涨跌幅与轮动状态
    prev_close = float(df_1h['Close'].iloc[-2])
    chg_pct = (live_price - prev_close) / prev_close * 100
    
    # 单股贡献打分 (用于宏观概率)
    stock_score = 0.0
    if live_price <= rbs_top:
        action = "🟢 支撑轮动 (BUY)"
        stock_score += 0.40
    elif live_price >= sbr_bot:
        action = "🔴 止盈高抛 (PROFIT)"
        stock_score -= 0.40
    elif live_price > ema20_now:
        action = "📈 多头持仓 (HOLD)"
        stock_score += 0.35
    else:
        action = "📉 偏弱观望 (WEAK)"
        stock_score -= 0.35

    return {
        "TICKER": ticker,
        "Group": "Mag 7" if ticker in BIG_SEVEN else ("Index" if ticker == "QQQ" else "Growth"),
        "Close": round(live_price, 2),
        "Change%": round(chg_pct, 2),
        "Action": action,
        "TREND_BIAS": final_bias,
        "TOTAL_SCORE": total_score,
        "STOCK_SCORE": stock_score,
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
# 5. 主程序运算与宽屏座舱渲染
# =====================================================================
st.title("🧭 QQQ 期权决策中枢 & 17 核心股轮动雷达")

results = []
all_hist_data = {}
with st.spinner("扫描 QQQ 与 17 支核心个股宏观量化数据中..."):
    for t in ALL_TICKERS:
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

    # --- 5.1 顶部宏观定调: CALL % vs PUT % 概率计算 ---
    avg_score = df_stocks["STOCK_SCORE"].mean()
    call_prob = int(np.clip((avg_score + 1.0) / 2.0 * 100, 5, 95))
    put_prob = 100 - call_prob

    up_cnt = sum(df_stocks["Change%"] > 0)
    down_cnt = sum(df_stocks["Change%"] <= 0)
    mag7_up = sum(df_stocks[df_stocks["Group"] == "Mag 7"]["Change%"] > 0)
    breadth_pct = int(sum(df_stocks["Close"] > df_stocks["EMA20"]) / len(df_stocks) * 100)
    divergence = (call_prob >= 60) and (breadth_pct <= 35)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("🎯 QQQ 实时点位", f"${qqq_row['Close']}", f"{qqq_row['Change%']}%")
    m2.metric("🧭 QQQ 宏观定调概率", f"🟢 CALL {call_prob}% vs 🔴 PUT {put_prob}%", f"三维共振: {qqq_row['TOTAL_SCORE']}分")
    m3.metric("📊 17 股市场宽度", f"{up_cnt} 涨 / {down_cnt} 跌", f"{breadth_pct}% 站上 20EMA")
    m4.metric("👑 Big 7 权重动能", f"{mag7_up} / 7 支上涨", "指数核心引擎")

    if divergence:
        st.error(f"🛑 **【严重警报：顶部背离】** QQQ 定调偏多，但 17 支权重股仅 {breadth_pct}% 站在 20 EMA 上！谨防假突破诱多瀑布！")
    elif call_prob >= 65:
        st.success(f"🚀 **【战术指令：多头主导 (CALL)】** CALL 胜率 {call_prob}%，全市场宽度良好，开盘重点寻找 5M RBS/PDL 企稳做多机会。")
    elif put_prob >= 65:
        st.error(f"🔴 **【战术指令：空头主导 (PUT)】** PUT 胜率 {put_prob}%，大势偏弱，开盘重点寻找 5M SBR/PDH 遇阻做空机会。")
    else:
        st.warning(f"🟡 **【战术指令：多空均衡震荡】** CALL {call_prob}% vs PUT {put_prob}%，多空双向均需严格等待 5M 战区形态确认。")

    st.markdown("---")

    # --- 5.2 宽屏左右分栏实战座舱 ---
    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.subheader("⚡ 今日实战买卖雷达 (谁买 / 谁卖)")
        
        # 提取买卖分组
        buy_list = df_stocks[df_stocks["Action"].str.contains("BUY")]
        profit_list = df_stocks[df_stocks["Action"].str.contains("PROFIT")]
        hold_list = df_stocks[~df_stocks["Action"].str.contains("BUY|PROFIT")]

        st.markdown("##### 🟢 【立即轮动买入区 (ROTATION IN)】")
        if not buy_list.empty:
            for _, r in buy_list.iterrows():
                st.markdown(f"* **`{r['TICKER']}`** : `${r['Close']}` ({r['Change%']}%) $\\rightarrow$ **踩入 1H RBS 支撑带** (`${r['RBS_BOT']} ~ ${r['RBS_TOP']}`)")
            st.caption("💡 *动作：QQQ 期权获利资金，优先定投加仓以上触及支撑的个股。*")
        else:
            st.info("暂无踩入 RBS 支撑带的个股（暂不追高加仓）")

        st.markdown("##### 🔴 【立即止盈高抛区 (TAKE PROFIT)】")
        if not profit_list.empty:
            for _, r in profit_list.iterrows():
                st.markdown(f"* **`{r['TICKER']}`** : `${r['Close']}` (+{r['Change%']}%) $\\rightarrow$ **冲入 1H SBR 阻力带** (`${r['SBR_BOT']} ~ ${r['SBR_TOP']}`)")
            st.caption("💡 *动作：原有正股多头仓位建议在此分批止盈收回现金。*")
        else:
            st.info("暂无冲入 SBR 阻力带的个股（继续持股待涨）")

        st.markdown("##### ⚪ 【待命中立区 (HOLDING)】")
        st.markdown(f"**持仓运行中 ({len(hold_list)} 支):** " + ", ".join([f"`{t}`" for t in hold_list["TICKER"].tolist()]))
        
        st.markdown("---")
        btn_refresh = st.button("🧹 清除缓存并强制刷新全域数据", type="secondary", use_container_width=True)
        if btn_refresh:
            st.cache_data.clear()
            st.rerun()

    with col_right:
        st.subheader("📋 【QQQ 专属】富途 5M 复制座舱")
        st.markdown(f"* **现价:** `${qqq_row['Close']}` *(通道: `{qqq_row['SOURCE_5M']}`)*")
        st.markdown(f"* **⚡ 盘前极值:** `${qqq_row['PMH']}` (PMH) ~ `${qqq_row['PML']}` (PML) `[{qqq_row['PMH_TIME']}]`")
        st.markdown(f"* **📌 昨日极值:** `${qqq_row['PDH']}` (PDH) ~ `${qqq_row['PDL']}` (PDL) `[{qqq_row['PDH_TIME']}]`")
        st.markdown(f"* **🔴 1H SBR 阻力带:** `${qqq_row['SBR_BOT']} ~ ${qqq_row['SBR_TOP']}` `[{qqq_row['SBR_TIME']}]`")
        st.markdown(f"* **🟢 1H RBS 支撑带:** `${qqq_row['RBS_BOT']} ~ ${qqq_row['RBS_TOP']}` `[{qqq_row['RBS_TIME']}]`")
        
        futu_code = f"""TREND_BIAS := {int(qqq_row['TREND_BIAS'])};       {{ 宏观: CALL {call_prob}% vs PUT {put_prob}% [得分: {qqq_row['TOTAL_SCORE']}] }}
SBR_TOP    := {qqq_row['SBR_TOP']:.2f};   {{ 1H 阻力顶沿 [{qqq_row['SBR_TIME']}] }}
SBR_BOT    := {qqq_row['SBR_BOT']:.2f};   {{ 1H 阻力底沿 [{qqq_row['SBR_TIME']}] }}
RBS_TOP    := {qqq_row['RBS_TOP']:.2f};   {{ 1H 支撑顶沿 [{qqq_row['RBS_TIME']}] }}
RBS_BOT    := {qqq_row['RBS_BOT']:.2f};   {{ 1H 支撑底沿 [{qqq_row['RBS_TIME']}] }}
PDH_LINE   := {qqq_row['PDH']:.2f};   {{ 昨日最高价 PDH [{qqq_row['PDH_TIME']}] }}
PDL_LINE   := {qqq_row['PDL']:.2f};   {{ 昨日最低价 PDL [{qqq_row['PDL_TIME']}] }}
PMH_LINE   := {qqq_row['PMH']:.2f};   {{ 盘前最高价 PMH [{qqq_row['PMH_TIME']}] }}
PML_LINE   := {qqq_row['PML']:.2f};   {{ 盘前最低价 PML [{qqq_row['PML_TIME']}] }}"""
        st.code(futu_code, language="pascal")

    # --- 5.3 底部全量看板与 Excel 导出 ---
    st.markdown("---")
    st.subheader("🗺️ 17 支核心个股全景数据看板 (按涨跌幅排序)")
    
    def highlight_action(val):
        if "PROFIT" in str(val) or "止盈" in str(val):
            return "background-color: #49111c; color: #ffccd5; font-weight: bold;"
        elif "BUY" in str(val) or "轮动" in str(val):
            return "background-color: #1b4332; color: #d8f3dc; font-weight: bold;"
        return ""

    display_cols = ["TICKER", "Group", "Close", "Change%", "Action", "EMA20", "RBS_TOP", "SBR_BOT", "PDL", "PDH", "SOURCE_5M"]
    styler = df_stocks[display_cols].sort_values(by="Change%", ascending=False).style
    if hasattr(styler, 'map'):
        styled_df = styler.map(highlight_action, subset=["Action"])
    else:
        styled_df = styler.applymap(highlight_action, subset=["Action"])
    st.dataframe(styled_df, use_container_width=True, height=450)

    # 导出报表
    col_dl1, col_dl2 = st.columns([2, 8])
    with col_dl1:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_res.to_excel(writer, index=False, sheet_name="Market_Report")
        st.download_button(
            label="📥 导出今日全量复盘报表 (.xlsx)",
            data=output.getvalue(),
            file_name=f"QQQ_Portfolio_Report_{datetime.date.today().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
