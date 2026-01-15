import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas_ta as ta

# 頁面基本設定
st.set_page_config(
    page_title="股票分析工具",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📊 股票分析工具")
st.caption("使用 yfinance • 支持美股 / A股 / 港股 / 其他國際市場")

# -------------------------------
# 側邊欄參數
# -------------------------------
with st.sidebar:
    st.header("分析設定")
    
    ticker = st.text_input("股票代碼", value="AAPL").strip().upper()
    
    st.markdown("""
    **常見代碼範例：**
    - 美股：AAPL, TSLA, NVDA, MSFT, GOOGL
    - A股：600519.SS（貴州茅台） 000001.SZ（平安銀行）
    - 港股：0700.HK（騰訊） 9988.HK（阿里）
    """)
    
    period_options = ["1mo", "3mo", "6mo", "1y", "2y", "5y", "max"]
    period = st.selectbox("資料期間", period_options, index=3)
    
    interval_options = ["1d", "5d", "1wk", "1mo"]
    interval = st.selectbox("K線週期", interval_options, index=0)
    
    st.markdown("---")
    st.subheader("技術指標顯示")
    show_volume = st.checkbox("顯示成交量", value=True)
    show_ma = st.checkbox("顯示移動平均線 (20/50/200)", value=True)
    show_bb = st.checkbox("顯示布林通道", value=True)
    show_macd = st.checkbox("顯示 MACD", value=True)
    show_rsi = st.checkbox("顯示 RSI(14)", value=True)

# -------------------------------
# 主程式
# -------------------------------
if ticker:
    try:
        with st.spinner(f"正在載入 {ticker} 的資料..."):
            # 取得股價資料
            df = yf.download(
                ticker,
                period=period,
                interval=interval,
                progress=False,
                auto_adjust=True,
                repair=True
            )
            
            if df.empty:
                st.error(f"無法取得 {ticker} 的資料，請確認代碼是否正確")
                st.stop()
                
            # 計算技術指標
            if show_ma:
                df['MA20'] = ta.sma(df['Close'], length=20)
                df['MA50'] = ta.sma(df['Close'], length=50)
                df['MA200'] = ta.sma(df['Close'], length=200)
            
            bb = ta.bbands(df['Close'], length=20, std=2) if show_bb else None
            macd = ta.macd(df['Close']) if show_macd else None
            rsi = ta.rsi(df['Close'], length=14) if show_rsi else None
            
            if bb is not None:
                df = pd.concat([df, bb], axis=1)
            if macd is not None:
                df = pd.concat([df, macd], axis=1)
            if rsi is not None:
                df['RSI'] = rsi

            latest = df.iloc[-1]
            prev = df.iloc[-2] if len(df) > 1 else latest

        # ---------------------------
        # 關鍵數據卡片
        # ---------------------------
        col1, col2, col3, col4 = st.columns(4)
        
        change = latest['Close'] - prev['Close']
        pct = change / prev['Close'] * 100 if prev['Close'] != 0 else 0
        
        col1.metric("最新收盤", f"{latest['Close']:.2f}", 
                   f"{change:+.2f}  ({pct:+.2f}%)",
                   delta_color="normal")
        
        col2.metric("區間最高/最低", f"{df['High'].max():.2f} / {df['Low'].min():.2f}")
        
        col3.metric("最新成交量", f"{int(latest['Volume']):,}")
        
        try:
            info = yf.Ticker(ticker).info
            market_cap = info.get('marketCap', None)
            if market_cap:
                col4.metric("市值", f"{market_cap/1e9:.1f} B")
            else:
                col4.metric("市值", "—")
        except:
            col4.metric("市值", "—")

        # ---------------------------
        # 主圖表
        # ---------------------------
        st.subheader("價格走勢與技術指標")

        rows = 1 + sum([show_volume, show_macd or show_rsi])
        row_heights = [0.58] + [0.21] * (rows - 1)
        
        fig = make_subplots(
            rows=rows, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.06,
            row_heights=row_heights,
            subplot_titles=("價格與指標",) + ("",) * (rows-1)
        )

        # K線
        fig.add_trace(
            go.Candlestick(
                x=df.index,
                open=df['Open'], high=df['High'],
                low=df['Low'], close=df['Close'],
                name='K線',
                increasing_line_color='#ef5350',
                decreasing_line_color='#26a69a'
            ),
            row=1, col=1
        )

        # 移動平均線
        if show_ma:
            for ma, name, color in [
                ('MA20', 'MA20', '#00c853'),
                ('MA50', 'MA50', '#ff9800'),
                ('MA200', 'MA200', '#2979ff')
            ]:
                if ma in df.columns:
                    fig.add_trace(
                        go.Scatter(x=df.index, y=df[ma], name=name, line=dict(color=color)),
                        row=1, col=1
                    )

        # 布林通道
        if show_bb and all(col in df.columns for col in ['BBL_20_2.0', 'BBU_20_2.0']):
            fig.add_trace(go.Scatter(x=df.index, y=df['BBU_20_2.0'],
                                    line=dict(color='#ffca28', width=1, dash='dash'), name='上軌'),
                         row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['BBL_20_2.0'],
                                    line=dict(color='#ffca28', width=1, dash='dash'), name='下軌',
                                    fill='tonexty', fillcolor='rgba(255,202,40,0.07)'),
                         row=1, col=1)

        # 成交量
        if show_volume:
            fig.add_trace(
                go.Bar(x=df.index, y=df['Volume'], name='成交量',
                       marker_color='rgba(100,181,246,0.5)'),
                row=2, col=1
            )

        # MACD
        current_row = 2 if show_volume else 1
        if show_macd and all(col in df.columns for col in ['MACD_12_26_9', 'MACDs_12_26_9']):
            fig.add_trace(go.Scatter(x=df.index, y=df['MACD_12_26_9'], name='MACD', line=dict(color='#1976d2')),
                         row=current_row+1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MACDs_12_26_9'], name='訊號線', line=dict(color='#d32f2f')),
                         row=current_row+1, col=1)
            fig.add_trace(go.Bar(x=df.index, y=df['MACDh_12_26_9'], name='柱狀圖',
                                marker_color=['#26a69a' if v>=0 else '#ef5350' for v in df['MACDh_12_26_9']]),
                         row=current_row+1, col=1)
            current_row += 1

        # RSI
        if show_rsi and 'RSI' in df.columns:
            fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], name='RSI(14)', line=dict(color='#8e24aa')),
                         row=current_row+1, col=1)
            fig.add_hline(y=70, line_dash="dash", line_color="#ef5350", row=current_row+1, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="#26a69a", row=current_row+1, col=1)

        fig.update_layout(
            height=800,
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis_rangeslider_visible=False,
            template="plotly_dark" if st.session_state.get('theme', 'light') == 'dark' else "plotly_white",
            margin=dict(t=80, b=60, l=60, r=40)
        )

        st.plotly_chart(fig, use_container_width=True)

        # 原始資料（可選）
        if st.checkbox("顯示最近100筆原始資料", False):
            st.dataframe(df.tail(100).style.format({
                col: "{:,.2f}" for col in ['Open','High','Low','Close']
            }))

    except Exception as e:
        st.error(f"發生錯誤：{str(e)}")
        st.info("常見原因：\n• 代碼輸入錯誤\n• 網路連線問題\n• Yahoo Finance 暫時無法提供該股票資料")
else:
    st.info("請在左側輸入股票代碼開始分析")