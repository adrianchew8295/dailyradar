import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import datetime
import io

# =====================================================================
# 1. 頁面配置
# =====================================================================
st.set_page_config(
    page_title="QQQ & 17 Core Swing Engine Pro",
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
# 2. 量化計算核心 (Adam Grimes + VPA + QQQ Magnitude Engine)
# =====================================================================
def calculate_grimes_levels(df):
    if len(df) < 60:
        return None
    
    df = df.copy()
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['SMA200'] = df['Close'].rolling(window=200).mean()
    
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
    
    if pivot_highs:
        major_high = max(pivot_highs)
    else:
        major_high = df['High'].iloc[-60:].max()
        
    sbr_top = round(float(major_high + 0.25 * latest_atr), 2)
    sbr_bot = round(float(major_high - 0.50 * latest_atr), 2)
    
    if pivot_lows:
        major_low = min(pivot_lows[-3:]) if len(pivot_lows) >= 3 else min(pivot_lows)
    else:
        major_low = df['Low'].iloc[-60:].min()
        
    rbs_top = round(float(major_low + 0.50 * latest_atr), 2)
    rbs_bot = round(float(major_low - 0.25 * latest_atr), 2)
    
    latest_vol = df['Volume'].iloc[-1]
    latest_vol_ma = df['VOL_MA20'].iloc[-1]
    rvol = round(float(latest_vol / latest_vol_ma), 2) if latest_vol_ma > 0 else 1.0
    
    prev_close = df['Close'].iloc[-2]
    latest_open = df['Open'].iloc[-1]
    latest_ema20 = df['EMA20'].iloc[-1]
    
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
        "SBR_TOP": sbr_top,
        "SBR_BOT": sbr_bot,
        "RBS_TOP": rbs_top,
        "RBS_BOT": rbs_bot,
        "RVOL": rvol,
        "STATUS": status,
        "ATR20": round(float(latest_atr), 2),
        "SCORE": score
    }

# =====================================================================
# 3. 側邊欄控制台
# =====================================================================
st.sidebar.title("🎛️ CONTROL CENTER")

tickers_input = st.sidebar.text_area(
    "Asset Universe",
    value=", ".join(DEFAULT_TICKERS),
    height=130
)
tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]

st.sidebar.markdown("---")
st.sidebar.subheader("⏳ PASS RECORD (歷史時光機)")
audit_date = st.sidebar.date_input(
    "選擇基準計算日期 (Target Date)",
    value=datetime.date.today(),
    max_value=datetime.date.today()
)

scan_btn = st.sidebar.button("🚀 執行全域掃描 (RUN SCAN)", type="primary")

# =====================================================================
# 4. 數據下載與清洗
# =====================================================================
st.title("🧭 QQQ & 17 CORE ASSETS - SWING ROTATION ENGINE")
st.caption(f"基準計算日: **{audit_date.strftime('%Y-%m-%d')}** | 框架: Adam Grimes Dual-Range + Breadth Magnitude")

start_date = audit_date - datetime.timedelta(days=730)
end_date = audit_date + datetime.timedelta(days=1)

@st.cache_data(ttl=3600)
def fetch_all_data(ticker_list, start, end):
    data = {}
    for t in ticker_list:
        try:
            df = yf.download(t, start=start, end=end, progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            if len(df) > 0:
                data[t] = df
        except Exception as e:
            st.error(f"下載 {t} 失敗: {e}")
    return data

with st.spinner("正在下載並清洗全資產池數據..."):
    all_data = fetch_all_data(tickers, start_date, end_date)

results = []
for t in tickers:
    if t in all_data and len(all_data[t]) >= 60:
        res = calculate_grimes_levels(all_data[t])
        if res:
            res["TICKER"] = t
            results.append(res)

if results:
    df_res = pd.DataFrame(results)
    
    # =================================================================
    # 5. 🌟 QQQ 精確漲跌幅度與目標落地區 (MAGNITUDE ENGINE)
    # =================================================================
    st.markdown("### 🎯 QQQ 大盤方向、漲跌幅度與目標落地區間")
    
    qqq_data = df_res[df_res["TICKER"] == "QQQ"].iloc[0] if "QQQ" in df_res["TICKER"].values else None
    stock_rows = df_res[df_res["TICKER"] != "QQQ"]
    
    if qqq_data is not None and len(stock_rows) > 0:
        qqq_close = qqq_data["Close"]
        sbr_target = qqq_data["SBR_BOT"]
        rbs_target = qqq_data["RBS_TOP"]
        
        # 漲跌幅度空間測算
        upside_pts = round(max(sbr_target - qqq_close, 0.0), 2)
        upside_pct = round((upside_pts / qqq_close) * 100, 2)
        
        downside_pts = round(max(qqq_close - rbs_target, 0.0), 2)
        downside_pct = round((downside_pts / qqq_close) * 100, 2)
        
        rr_ratio = round(upside_pct / max(downside_pct, 0.1), 2)
        
        # 綜合多空概率
        avg_score = stock_rows["SCORE"].mean()
        bull_prob = int(np.clip((avg_score + 1.0) / 2.0 * 100, 5, 95))
        bear_prob = 100 - bull_prob
        
        # 寬度指標
        above_ema_cnt = sum(stock_rows["Close"] > stock_rows["EMA20"])
        total_stocks = len(stock_rows)
        breadth_pct = int(above_ema_cnt / total_stocks * 100)
        
        # 背離檢測
        divergence = (bull_prob >= 60) and (breadth_pct <= 35)
        
        # 動態總持倉配置建議
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

        # 頂部 4 大核心卡片
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        with col_m1:
            st.metric("🟢 QQQ 看漲目標區 (SBR)", f"${sbr_target}", f"+{upside_pct}% (+${upside_pts})")
        with col_m2:
            st.metric("🔴 QQQ 防守回調區 (RBS)", f"${rbs_target}", f"-{downside_pct}% (-${downside_pts})", delta_color="inverse")
        with col_m3:
            st.metric("🧭 預測概率 (多/空)", f"{bull_prob}% 多 / {bear_prob}% 空")
        with col_m4:
            st.metric("⚖️ 空間盈虧比 (R:R)", f"1 : {rr_ratio}", f"寬度: {breadth_pct}% 站上均線")

        # 戰術決策橫幅
        if divergence:
            st.error(f"🛑 **【嚴重警報：頂部背離 (DIVERGENCE)】** 指數表面偏多，但 17 支權重股僅 {breadth_pct}% 站在 20 EMA 上！做市商正在拉指數掩護出貨，隨時瀑布，嚴禁追高！")
        elif bull_prob >= 65 and rr_ratio >= 1.5:
            st.success(f"🚀 **【戰術指令：大波段進攻】** 目標直指 **`${sbr_target}` (+{upside_pct}%)**，回調底座 **`${rbs_target}`** 支撐極強。空間 R:R 為 1:{rr_ratio}。**{rec_cash}**")
        elif bear_prob >= 65:
            st.error(f"🔴 **【戰術指令：空頭防守收割】** 預期回調至 **`${rbs_target}` (-{downside_pct}%)**。大面積股票進入派發區。**{rec_cash}**")
        else:
            st.warning(f"🟡 **【戰術指令：多空僵持 / 看著辦】** 當前處於半空中震盪，上漲空間 +{upside_pct}% vs 回調空間 -{downside_pct}%。**{rec_cash}**")

    st.markdown("---")

    # =================================================================
    # 6. 全域看板視圖 (RADAR VIEW)
    # =================================================================
    st.subheader("📊 17 支核心資產 + QQQ 全域量化看板")
    cols = ["TICKER", "STATUS", "Close", "EMA20", "RBS_BOT", "RBS_TOP", "SBR_BOT", "SBR_TOP", "RVOL", "ATR20"]
    st.dataframe(
        df_res[cols].style.applymap(
            lambda v: "background-color: #1b4332; color: #d8f3dc; font-weight: bold;" if "BUY" in str(v)
            else "background-color: #5c4d00; color: #fff3b0;" if "RBS" in str(v)
            else "background-color: #49111c; color: #ffccd5;" if "SBR" in str(v)
            else "",
            subset=["STATUS"]
        ),
        use_container_width=True,
        height=500
    )

    # =================================================================
    # 7. EXCEL 報告導出
    # =================================================================
    col_dl1, col_dl2 = st.columns([2, 8])
    with col_dl1:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_res[cols].to_excel(writer, index=False, sheet_name=f"Scan_{audit_date.strftime('%Y%m%d')}")
        excel_data = output.getvalue()
        
        st.download_button(
            label="📥 下載 EXCEL 完整量化報告 (.xlsx)",
            data=excel_data,
            file_name=f"QQQ_Swing_Report_{audit_date.strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    # =================================================================
    # 8. 單股 / QQQ 富途參數複製座艙
    # =================================================================
    st.markdown("---")
    st.subheader("🎯 單股 / QQQ 富途參數複製座艙")
    
    selected_stock = st.selectbox("選擇要查看或複製代碼的標的 (SELECT ASSET):", tickers, index=0)
    stock_data = df_res[df_res["TICKER"] == selected_stock].iloc[0]
    
    col_c1, col_c2 = st.columns([1, 1])
    with col_c1:
        st.markdown(f"#### 【{selected_stock}】 結構數據")
        st.markdown(f"* **當前狀態 (STATUS):** `{stock_data['STATUS']}`")
        st.markdown(f"* **收盤價 (CLOSE):** `${stock_data['Close']}` | **20 EMA:** `${stock_data['EMA20']}`")
        st.markdown(f"* **🟢 底部買盤箱體 (RBS):** `${stock_data['RBS_BOT']} ~ ${stock_data['RBS_TOP']}`")
        st.markdown(f"* **🔴 頂部阻力箱體 (SBR):** `${stock_data['SBR_BOT']} ~ ${stock_data['SBR_TOP']}`")
        st.markdown(f"* **相對成交量 (RVOL):** `{stock_data['RVOL']}x`")
        
    with col_c2:
        st.markdown("#### 📋 複製到富途指標前 4 行 (點擊右上角複製)")
        futu_code = f"""SBR_TOP := {stock_data['SBR_TOP']:.2f};  {{ 頂部阻力箱體頂沿 }}
SBR_BOT := {stock_data['SBR_BOT']:.2f};  {{ 頂部阻力箱體底沿 }}

RBS_TOP := {stock_data['RBS_TOP']:.2f};  {{ 底部買盤箱體頂沿 }}
RBS_BOT := {stock_data['RBS_BOT']:.2f};  {{ 底部買盤箱體底沿 }}"""
        st.code(futu_code, language="pascal")

    # =================================================================
    # 9. 歷史軌跡日誌
    # =================================================================
    with st.expander(f"🔍 展開查看 {selected_stock} 過去 30 個交易日的行情記錄"):
        hist_df = all_data[selected_stock].tail(30).copy()
        hist_df['EMA20'] = hist_df['Close'].ewm(span=20, adjust=False).mean()
        st.dataframe(hist_df[['Open', 'High', 'Low', 'Close', 'Volume', 'EMA20']].round(2).sort_index(ascending=False), use_container_width=True)

else:
    st.warning("數據載入中或未檢索到數據，請確認網絡連接。")
