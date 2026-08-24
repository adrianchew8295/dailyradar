import io
import datetime
from datetime import timedelta
import numpy as np
import pandas as pd
import pytz
import requests
import streamlit as st

# =====================================================================
# 1. 核心憑證與資產配置 (已自動綁定 TIINGO TOKEN)
# =====================================================================
TIINGO_TOKEN = "bcffe3a5cf7eeef085e405cfa4a3e5691b976217"

st.set_page_config(
    page_title="QQQ & 17 Core Swing Engine (Tiingo)",
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
# 2. 人性化時間與倒計時引擎 (大馬時間 MYT & 美東時間 ET)
# =====================================================================
tz_myt = pytz.timezone("Asia/Kuala_Lumpur")
tz_ny = pytz.timezone("America/New_York")

now_myt = datetime.datetime.now(tz_myt)
now_ny = datetime.datetime.now(tz_ny)

target_open_ny = now_ny.replace(hour=9, minute=30, second=0, microsecond=0)
if now_ny >= target_open_ny and now_ny.hour >= 16:
    target_open_ny += timedelta(days=1)
while target_open_ny.weekday() >= 5:  # 跳過週末
    target_open_ny += timedelta(days=1)

target_open_myt = target_open_ny.astimezone(tz_myt)
time_to_open = target_open_myt - now_myt

c_t1, c_t2, c_t3 = st.columns([1.5, 1.5, 2])
c_t1.info(f"🕒 **大馬時間 (MYT):** {now_myt.strftime('%Y-%m-%d %H:%M:%S')}")
c_t2.info(f"🇺🇸 **美東時間 (ET):** {now_ny.strftime('%Y-%m-%d %H:%M:%S')}")

if 0 <= time_to_open.total_seconds() <= 86400:
    hours, remainder = divmod(int(time_to_open.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    c_t3.warning(f"⏳ **距離今晚開盤倒計時:** {hours}小時 {minutes}分 {seconds}秒")
else:
    c_t3.success("🟢 **美股交易中 / 盤後覆盤階段**")

# =====================================================================
# 3. 側邊欄配置
# =====================================================================
st.sidebar.title("🎛️ CONTROL CENTER")
st.sidebar.success("🔑 Tiingo API 連線就緒")

tickers_input = st.sidebar.text_area(
    "監控資產池 (QQQ + 17 核心標的)",
    value=", ".join(DEFAULT_TICKERS),
    height=120
)
tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]

st.sidebar.markdown("---")
st.sidebar.subheader("⏳ PASS RECORD (歷史時光機)")
audit_date = st.sidebar.date_input(
    "選擇基準覆盤日期 (Target Date)",
    value=datetime.date.today(),
    max_value=datetime.date.today()
)

scan_btn = st.sidebar.button("🚀 執行全域掃描 (RUN SCAN)", type="primary")

# =====================================================================
# 4. Tiingo 數據抓取引擎 (URL Query 鉴权 + 智能历史回溯)
# =====================================================================
@st.cache_data(ttl=3600)
def fetch_tiingo_data(ticker, start_str, token):
    url = f"https://api.tiingo.com/tiingo/daily/{ticker}/prices?startDate={start_str}&token={token}"
    headers = {'Content-Type': 'application/json'}
    try:
        response = requests.get(url, headers=headers, timeout=12)
        if response.status_code == 200:
            data = response.json()
            if not data or (isinstance(data, dict) and "detail" in data):
                return None
            df = pd.DataFrame(data)
            if df.empty or 'date' not in df.columns:
                return None
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            df.rename(columns={
                'open': 'Open',
                'high': 'High',
                'low': 'Low',
                'close': 'Close',
                'volume': 'Volume'
            }, inplace=True)
            return df[['Open', 'High', 'Low', 'Close', 'Volume']].sort_index()
        else:
            return None
    except Exception:
        return None

def calculate_lwma(series: pd.Series, period: int) -> pd.Series:
    """計算 200 LWMA"""
    weights = np.arange(1, period + 1)
    return series.rolling(period).apply(lambda prices: np.dot(prices, weights) / weights.sum(), raw=True)

# =====================================================================
# 5. Adam Grimes 宏觀寬幅雙箱體與 5M 對接核心
# =====================================================================
def calculate_grimes_levels(df):
    if len(df) < 50:
        return None
    
    df = df.copy()
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['SMA200'] = df['Close'].rolling(window=200).mean()
    df['LWMA200'] = calculate_lwma(df['Close'], min(200, len(df)))
    
    df['TR'] = np.maximum(
        df['High'] - df['Low'],
        np.maximum(
            (df['High'] - df['Close'].shift(1)).abs(),
            (df['Low'] - df['Close'].shift(1)).abs()
        )
    )
    df['ATR20'] = df['TR'].rolling(window=20).mean()
    df['VOL_MA20'] = df['Volume'].rolling(window=20).mean()
    
    lookback = min(len(df) - 5, 120)
    subset = df.iloc[-lookback:].copy()
    highs = subset['High'].values
    lows = subset['Low'].values
    
    pivot_highs, pivot_lows = [], []
    for i in range(2, len(subset) - 2):
        if highs[i] == max(highs[i-2:i+3]):
            pivot_highs.append(highs[i])
        if lows[i] == min(lows[i-2:i+3]):
            pivot_lows.append(lows[i])
            
    latest_atr = df['ATR20'].iloc[-1]
    latest_close = df['Close'].iloc[-1]
    
    # 昨日極值 (PDH / PDL)
    if len(df) >= 2:
        pdh_val = round(float(df['High'].iloc[-2]), 2)
        pdl_val = round(float(df['Low'].iloc[-2]), 2)
    else:
        pdh_val = round(float(df['High'].iloc[-1]), 2)
        pdl_val = round(float(df['Low'].iloc[-1]), 2)
        
    # 盤前通道估算 (PMH / PML)
    pmh_val = round(float(latest_close + 0.5 * latest_atr), 2)
    pml_val = round(float(latest_close - 0.5 * latest_atr), 2)
    
    # 宏觀頂部 SBR 箱體 (厚度約 2.0x ATR)
    if pivot_highs:
        major_high = max(pivot_highs)
    else:
        major_high = df['High'].iloc[-60:].max()
        
    sbr_top = round(float(major_high + 0.50 * latest_atr), 2)
    sbr_bot = round(float(major_high - 1.50 * latest_atr), 2)
    
    # 宏觀底部 RBS 箱體 (厚度約 2.0x ATR)
    if pivot_lows:
        major_low = min(pivot_lows[-3:]) if len(pivot_lows) >= 3 else min(pivot_lows)
    else:
        major_low = df['Low'].iloc[-60:].min()
        
    rbs_top = round(float(major_low + 1.50 * latest_atr), 2)
    rbs_bot = round(float(major_low - 0.50 * latest_atr), 2)
    
    latest_vol = df['Volume'].iloc[-1]
    latest_vol_ma = df['VOL_MA20'].iloc[-1]
    rvol = round(float(latest_vol / latest_vol_ma), 2) if latest_vol_ma > 0 else 1.0
    
    prev_close = df['Close'].iloc[-2]
    latest_open = df['Open'].iloc[-1]
    latest_ema20 = df['EMA20'].iloc[-1]
    latest_lwma200 = df['LWMA200'].iloc[-1]
    
    # 宏觀偏向 (TREND_BIAS)
    if not np.isnan(latest_lwma200):
        trend_bias = 1 if latest_close > latest_lwma200 else -1
    else:
        trend_bias = 0
    
    # 狀態機判定
    in_rbs = (df['Low'].iloc[-5:].min() <= rbs_top) and (latest_close >= rbs_bot)
    reclaimed_ema = (latest_close > latest_ema20) and (prev_close <= df['EMA20'].iloc[-2])
    is_bull = latest_close > latest_open
    
    if in_rbs and reclaimed_ema and is_bull and rvol >= 1.15:
        status = "🟢 BUY TRIGGER"
    elif in_rbs:
        status = "🟡 IN RBS ZONE"
    elif latest_close >= sbr_bot:
        status = "🔴 SBR HARVEST"
    else:
        status = "⚪ NEUTRAL"
        
    score = 0.0
    if in_rbs: score += 0.40
    elif latest_close >= sbr_bot: score -= 0.40
    
    if latest_close > latest_ema20: score += 0.35
    else: score -= 0.35
    
    if is_bull and rvol >= 1.15: score += 0.25
    elif not is_bull and rvol >= 1.15: score -= 0.25
        
    return {
        "Close": round(float(latest_close), 2),
        "EMA20": round(float(latest_ema20), 2),
        "LWMA200": round(float(latest_lwma200), 2) if not np.isnan(latest_lwma200) else 0.0,
        "TREND_BIAS": trend_bias,
        "SBR_TOP": sbr_top,
        "SBR_BOT": sbr_bot,
        "RBS_TOP": rbs_top,
        "RBS_BOT": rbs_bot,
        "PDH": pdh_val,
        "PDL": pdl_val,
        "PMH": pmh_val,
        "PML": pml_val,
        "RVOL": rvol,
        "STATUS": status,
        "ATR20": round(float(latest_atr), 2),
        "SCORE": score
    }

# =====================================================================
# 6. 主程序邏輯
# =====================================================================
st.title("🧭 QQQ & 17 CORE ASSETS - SWING ENGINE")
st.caption(f"基準計算日: **{audit_date.strftime('%Y-%m-%d')}** | 數據源: Tiingo Official API (宏觀寬幅 + 5M 參數聯動版)")

start_date_str = (audit_date - datetime.timedelta(days=730)).strftime('%Y-%m-%d')

all_data = {}
with st.spinner("正在透過 Tiingo API 請求全資產數據..."):
    for t in tickers:
        df_stock = fetch_tiingo_data(t, start_date_str, TIINGO_TOKEN)
        if df_stock is not None and len(df_stock) >= 50:
            all_data[t] = df_stock

results = []
for t in tickers:
    if t in all_data:
        res = calculate_grimes_levels(all_data[t])
        if res:
            res["TICKER"] = t
            results.append(res)

if results:
    df_res = pd.DataFrame(results)
    
    # 6.1 QQQ 幅度預測與市場寬度
    st.markdown("### 🎯 QQQ 大盤方向、漲跌幅度與目標落地區間")
    qqq_data = df_res[df_res["TICKER"] == "QQQ"].iloc[0] if "QQQ" in df_res["TICKER"].values else None
    stock_rows = df_res[df_res["TICKER"] != "QQQ"]
    
    if qqq_data is not None and len(stock_rows) > 0:
        qqq_close = qqq_data["Close"]
        sbr_target = qqq_data["SBR_BOT"]
        rbs_target = qqq_data["RBS_TOP"]
        
        upside_pts = round(max(sbr_target - qqq_close, 0.0), 2)
        upside_pct = round((upside_pts / qqq_close) * 100, 2)
        
        downside_pts = round(max(qqq_close - rbs_target, 0.0), 2)
        downside_pct = round((downside_pts / qqq_close) * 100, 2)
        
        rr_ratio = round(upside_pct / max(downside_pct, 0.1), 2)
        
        avg_score = stock_rows["SCORE"].mean()
        bull_prob = int(np.clip((avg_score + 1.0) / 2.0 * 100, 5, 95))
        bear_prob = 100 - bull_prob
        
        above_ema_cnt = sum(stock_rows["Close"] > stock_rows["EMA20"])
        total_stocks = len(stock_rows)
        breadth_pct = int(above_ema_cnt / total_stocks * 100)
        divergence = (bull_prob >= 60) and (breadth_pct <= 35)
        
        if divergence:
            rec_cash = "🛑 0% ~ 20% (頂部背離嚴重，強制防守)"
        elif bull_prob >= 65 and rr_ratio >= 1.5:
            rec_cash = "🚀 60% ~ 80% (高勝率 + 大空間，全力做多)"
        elif bull_prob >= 60:
            rec_cash = "📈 40% ~ 50% (中度多頭，標準底倉)"
        elif bear_prob >= 65:
            rec_cash = "🔴 0% ~ 20% (空頭主導，現金為王)"
        else:
            rec_cash = "🟡 20% ~ 30% (多空撕裂，輕倉觀望)"

        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        with col_m1:
            st.metric("🟢 QQQ 看漲目標區 (SBR)", f"${sbr_target}", f"+{upside_pct}% (+${upside_pts})")
        with col_m2:
            st.metric("🔴 QQQ 防守回調區 (RBS)", f"${rbs_target}", f"-{downside_pct}% (-${downside_pts})", delta_color="inverse")
        with col_m3:
            st.metric("🧭 預測概率 (多/空)", f"{bull_prob}% 多 / {bear_prob}% 空")
        with col_m4:
            st.metric("⚖️ 空間盈虧比 (R:R)", f"1 : {rr_ratio}", f"寬度: {breadth_pct}% 站上均線")

        if divergence:
            st.error(f"🛑 **【嚴重警報：頂部背離】** 指數偏多，但 17 支權重股僅 {breadth_pct}% 站在 20 EMA 上！隨時面臨瀑布，嚴禁追高！")
        elif bull_prob >= 65 and rr_ratio >= 1.5:
            st.success(f"🚀 **【戰術指令：大波段進攻】** 目標 **`${sbr_target}` (+{upside_pct}%)**，支撐 **`${rbs_target}`**。空間比 1:{rr_ratio}。**{rec_cash}**")
        elif bear_prob >= 65:
            st.error(f"🔴 **【戰術指令：空頭防守收割】** 預期回調至 **`${rbs_target}` (-{downside_pct}%)**。**{rec_cash}**")
        else:
            st.warning(f"🟡 **【戰術指令：多空僵持 / 看著辦】** 上漲 +{upside_pct}% vs 回調 -{downside_pct}%。**{rec_cash}**")

    st.markdown("---")

    # 6.2 全域量化看板 (兼容新舊版 Pandas 著色)
    st.subheader("📊 17 支核心資產 + QQQ 全域量化看板")
    cols = ["TICKER", "STATUS", "Close", "EMA20", "RBS_BOT", "RBS_TOP", "SBR_BOT", "SBR_TOP", "PDL", "PDH", "RVOL", "ATR20"]
    
    def highlight_status(val):
        s = str(val)
        if "BUY" in s:
            return "background-color: #1b4332; color: #d8f3dc; font-weight: bold;"
        elif "RBS" in s:
            return "background-color: #5c4d00; color: #fff3b0;"
        elif "SBR" in s:
            return "background-color: #49111c; color: #ffccd5;"
        return ""

    styler = df_res[cols].style
    if hasattr(styler, 'map'):
        styled_df = styler.map(highlight_status, subset=["STATUS"])
    else:
        styled_df = styler.applymap(highlight_status, subset=["STATUS"])
        
    st.dataframe(styled_df, use_container_width=True, height=500)

    # 6.3 EXCEL 下載
    col_dl1, col_dl2 = st.columns([2, 8])
    with col_dl1:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_res[cols].to_excel(writer, index=False, sheet_name=f"Scan_{audit_date.strftime('%Y%m%d')}")
        excel_data = output.getvalue()
        
        st.download_button(
            label="📥 下載 EXCEL 完整報告 (.xlsx)",
            data=excel_data,
            file_name=f"Tiingo_Swing_Report_{audit_date.strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    # 6.4 富途 5M 參數一鍵複製座艙 (完整 9 行對齊)
    st.markdown("---")
    st.subheader("🎯 單股 / QQQ 富途 5M 指標參數複製座艙")
    
    selected_stock = st.selectbox("選擇要複製代碼的標的:", tickers, index=0)
    stock_data = df_res[df_res["TICKER"] == selected_stock].iloc[0]
    
    col_c1, col_c2 = st.columns([1, 1])
    with col_c1:
        st.markdown(f"#### 【{selected_stock}】 結構數據")
        st.markdown(f"* **狀態:** `{stock_data['STATUS']}`")
        st.markdown(f"* **最新價:** `${stock_data['Close']}` | **20 EMA:** `${stock_data['EMA20']}`")
        st.markdown(f"* **🟢 底部 RBS 箱體:** `${stock_data['RBS_BOT']} ~ ${stock_data['RBS_TOP']}`")
        st.markdown(f"* **🔴 頂部 SBR 箱體:** `${stock_data['SBR_BOT']} ~ ${stock_data['SBR_TOP']}`")
        st.markdown(f"* **📌 昨日極值 (PDL / PDH):** `${stock_data['PDL']} ~ ${stock_data['PDH']}`")
        st.markdown(f"* **RVOL:** `{stock_data['RVOL']}x`")
        
    with col_c2:
        st.markdown("#### 📋 複製到富途 5M 指標頂部 9 行參數 (點擊右上角複製)")
        futu_code = f"""TREND_BIAS := {int(stock_data['TREND_BIAS'])};       {{ 宏觀偏向: 1=多, -1=空, 0=中立 }}
SBR_TOP    := {stock_data['SBR_TOP']:.2f};   {{ 1H 阻力頂沿 }}
SBR_BOT    := {stock_data['SBR_BOT']:.2f};   {{ 1H 阻力底沿 }}
RBS_TOP    := {stock_data['RBS_TOP']:.2f};   {{ 1H 支撑頂沿 }}
RBS_BOT    := {stock_data['RBS_BOT']:.2f};   {{ 1H 支撑底沿 }}
PDH_LINE   := {stock_data['PDH']:.2f};   {{ 昨日最高價 PDH }}
PDL_LINE   := {stock_data['PDL']:.2f};   {{ 昨日最低價 PDL }}
PMH_LINE   := {stock_data['PMH']:.2f};   {{ 盤前最高價 PMH }}
PML_LINE   := {stock_data['PML']:.2f};   {{ 盤前最低價 PML }}"""
        st.code(futu_code, language="pascal")

    # 6.5 歷史明細
    with st.expander(f"🔍 查看 {selected_stock} 歷史行情明細"):
        hist_df = all_data[selected_stock].tail(30).copy()
        hist_df['EMA20'] = hist_df['Close'].ewm(span=20, adjust=False).mean()
        st.dataframe(hist_df.round(2).sort_index(ascending=False), use_container_width=True)

else:
    st.error("⚠️ 未獲取到數據，請檢查網絡連接或確認 Tiingo 配額。")
