import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas_ta as ta
from openai import OpenAI
import time

# =====================================
# 頁面設定
# =====================================
st.set_page_config(
    page_title="股票分析工具 + DeepSeek AI",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📊 股票分析工具 + DeepSeek 智能分析")
st.caption("資料來源：yfinance | AI分析：DeepSeek | 支持美股/港股/A股等")

# =====================================
# 側邊欄設定
# =====================================
with st.sidebar:
    st.header("分析設定")
    
    ticker = st.text_input("股票代碼", value="AAPL").strip().upper()
    
    st.markdown("""
    **常見代碼範例：**
    - 美股：AAPL, TSLA, NVDA, MSFT, GOOGL
    - A股：600519.SS（貴州茅台） 000001.SZ（平安銀行）
    - 港股：0700.HK（騰訊） 9988.HK（阿里巴巴）
    """)
    
    period = st.selectbox("資料期間", ["1mo", "3mo", "6mo", "1y", "2y", "5y", "max"], index=3)
    interval = st.selectbox("K線週期", ["1d", "5d", "1wk", "1mo"], index=0)
    
    st.markdown("---")
    st.subheader("顯示選項")
    show_volume = st.checkbox("顯示成交量", value=True)
    show_ma = st.checkbox("顯示移動平均線 (20/50/200)", value=True)
    show_bb = st.checkbox("顯示布林通道", value=True)
    show_macd = st.checkbox("顯示 MACD", value=True)
    show_rsi = st.checkbox("顯示 RSI(14)", value=True)

# DeepSeek API Key（建議使用 st.secrets 管理）
DEEPSEEK_API_KEY = st.secrets.get("DEEPSEEK_API_KEY", None)

# =====================================
# 主程式
# =====================================
if ticker:
    try:
        with st.spinner(f"正在載入 {ticker} 資料..."):
            # 增加重試機制，應對 yfinance 不穩定
            for attempt in range(3):
                try:
                    time.sleep(1.5)  # 稍微延遲避免太快被 ban
                    df = yf.download(
                        ticker,
                        period=period,
                        interval=interval,
                        progress=False,
                        auto_adjust=True,
                        repair=True,
                        timeout=20
                    )
                    if not df.empty:
                        break
                except Exception as e:
                    if attempt == 2:
                        raise e
                    time.sleep(3)

            if df.empty:
                st.error(f"無法取得 {ticker} 的資料（已嘗試多次）")
                st.info("可能原因：Yahoo Finance 限制、網路問題、代碼錯誤")
                st.stop()

            # 計算技術指標
            if show_ma:
                df['MA20'] = ta.sma(df['Close'], length=20)
                df['MA50'] = ta.sma(df['Close'], length=50)
                df['MA200'] = ta.sma(df['Close'], length=200)
            
            if show_bb:
                bb = ta.bbands(df['Close'], length=20, std=2)
                if bb is not None:
                    df = pd.concat([df, bb], axis=1)
            
            if show_macd:
                macd = ta.macd(df['Close'])
                if macd is not None:
                    df = pd.concat([df, macd], axis=1)
            
            if show_rsi:
                df['RSI'] = ta.rsi(df['Close'], length=14)

            latest = df.iloc[-1]
            prev = df.iloc[-2] if len(df) > 1 else latest

            # 基本資訊
            try:
                info = yf.Ticker(ticker).info
            except:
                info = {}

        # -------------------------------
        # 關鍵數據卡片
        # -------------------------------
        col1, col2, col3, col4 = st.columns(4)
        
        change = latest['Close'] - prev['Close']
        pct = change / prev['Close'] * 100 if prev['Close'] != 0 else 0
        
        col1.metric("最新收盤", f"{latest['Close']:.2f}", f"{change:+.2f} ({pct:+.2f}%)")
        col2.metric("區間高/低", f"{df['High'].max():.2f} / {df['Low'].min():.2f}")
        col3.metric("最新成交量", f"{int(latest['Volume']):,}")
        col4.metric("市值", f"{info.get('marketCap', '—'):,}" if info.get('marketCap') else "—")

        # -------------------------------
        # K線圖
        # -------------------------------
        st.subheader("價格走勢與技術指標")

        rows = 1 + (1 if show_volume else 0) + (1 if show_macd or show_rsi else 0)
        fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, 
                           vertical_spacing=0.06, row_heights=[0.6] + [0.2]*(rows-1))

        # K線
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'],
                                    low=df['Low'], close=df['Close'], name='K線',
                                    increasing_line_color='#ef5350', decreasing_line_color='#26a69a'),
                      row=1, col=1)

        # 均線
        if show_ma:
            for name, col, color in [("MA20","#00C853"), ("MA50","#FF9800"), ("MA200","#2979FF")]:
                if col in df:
                    fig.add_trace(go.Scatter(x=df.index, y=df[col], name=name, line=dict(color=color)), row=1, col=1)

        # 布林帶
        if show_bb and all(c in df for c in ['BBU_20_2.0', 'BBL_20_2.0']):
            fig.add_trace(go.Scatter(x=df.index, y=df['BBU_20_2.0'], line=dict(color='#ffca28',dash='dash'), name="上軌"), row=1,col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['BBL_20_2.0'], line=dict(color='#ffca28',dash='dash'), name="下軌",
                                    fill='tonexty', fillcolor='rgba(255,202,40,0.08)'), row=1,col=1)

        current_row = 2
        if show_volume:
            fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name="成交量", marker_color='rgba(100,181,246,0.5)'), row=current_row, col=1)
            current_row += 1

        if show_macd and all(c in df for c in ['MACD_12_26_9', 'MACDs_12_26_9']):
            fig.add_trace(go.Scatter(x=df.index, y=df['MACD_12_26_9'], name='MACD', line=dict(color='#1976d2')), row=current_row, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MACDs_12_26_9'], name='訊號', line=dict(color='#d32f2f')), row=current_row, col=1)
            fig.add_trace(go.Bar(x=df.index, y=df['MACDh_12_26_9'], name='柱', marker_color=['#26a69a' if x>=0 else '#ef5350' for x in df['MACDh_12_26_9']]), row=current_row, col=1)
            current_row += 1

        if show_rsi and 'RSI' in df:
            fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], name='RSI(14)', line=dict(color='#8e24aa')), row=current_row, col=1)
            fig.add_hline(y=70, line_dash="dash", line_color="red", row=current_row, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="lime", row=current_row, col=1)

        fig.update_layout(height=800, showlegend=True, xaxis_rangeslider_visible=False,
                         template="plotly_dark" if "dark" in st.session_state.get("theme", "") else "plotly_white")

        st.plotly_chart(fig, use_container_width=True)

        # =====================================
        # DeepSeek AI 分析區塊
        # =====================================
        st.markdown("---")
        st.subheader("🤖 DeepSeek AI 分析（點擊按鈕啟動）")

        if st.button("使用 DeepSeek 進行深度分析", type="primary"):
            if not DEEPSEEK_API_KEY:
                st.error("尚未設定 DeepSeek API Key\n請在 Streamlit Cloud → Secrets 加入 DEEPSEEK_API_KEY")
            else:
                with st.spinner("DeepSeek 正在分析中...（約 8–25 秒）"):
                    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

                    data_summary = f"""
股票代碼：{ticker}
最新收盤：{latest['Close']:.2f}  漲跌：{change:+.2f} ({pct:+.2f}%)
區間最高/最低：{df['High'].max():.2f} / {df['Low'].min():.2f}
最新成交量：{latest['Volume']:,.0f}

技術指標（最新）：
MA20: {df.get('MA20', pd.Series([None])).iloc[-1]:.2f if 'MA20' in df else 'N/A'}
MA50: {df.get('MA50', pd.Series([None])).iloc[-1]:.2f if 'MA50' in df else 'N/A'}
MA200: {df.get('MA200', pd.Series([None])).iloc[-1]:.2f if 'MA200' in df else 'N/A'}
RSI(14): {df.get('RSI', pd.Series([None])).iloc[-1]:.2f if 'RSI' in df else 'N/A'}
MACD: {df.get('MACD_12_26_9', pd.Series([None])).iloc[-1]:.4f if 'MACD_12_26_9' in df else 'N/A'}

近10天收盤（由新到舊）：{', '.join(f'{x:.2f}' for x in df['Close'].tail(10)[::-1])}

公司名稱：{info.get('longName', '未知')}
行業：{info.get('industry', '未知')}
                    """.strip()

                    prompt = f"""你是一位經驗豐富且非常保守的股票分析師。
請根據以下最新數據，對這檔股票進行客觀分析，不要誇大、不做保證、不鼓勵追高殺低。

重點回覆內容：
1. 目前技術面大概處於什麼階段？（強勢、多頭、空頭、盤整）
2. 短期（1~4週）與中期（1~3個月）可能的方向與關鍵觀察點
3. 主要支撐與壓力位參考
4. 風險提醒
5. 給一般散戶的保守建議（強烈建議/建議/觀望/建議減持/強烈建議減持等）

數據如下：

{data_summary}

請用中文回覆，條理清晰，總長度控制在 450~700 字左右。"""

                    try:
                        response = client.chat.completions.create(
                            model="deepseek-reasoner",
                            messages=[
                                {"role": "system", "content": "你是專業、理性、保守的股票分析師。"},
                                {"role": "user", "content": prompt}
                            ],
                            temperature=0.35,
                            max_tokens=1000
                        )
                        st.markdown("### DeepSeek 分析結果")
                        st.markdown(response.choices[0].message.content)

                    except Exception as api_err:
                        st.error(f"DeepSeek API 呼叫失敗：{str(api_err)}")

    except Exception as e:
        st.error(f"程式執行發生錯誤：{str(e)}")
        st.info("常見原因：網路問題、Yahoo Finance 暫時限制、代碼輸入錯誤等")
else:
    st.info("請輸入股票代碼開始分析～")