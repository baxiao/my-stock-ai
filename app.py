import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas_ta as ta

# -------------------------------
# 页面配置
# -------------------------------
st.set_page_config(
    page_title="简易股票分析工具",
    page_icon="📈",
    layout="wide"
)

st.title("📊 简易股票分析工具（yfinance + Streamlit）")
st.markdown("支持美股、A股、港股等几乎所有 yfinance 可取得的标的")

# -------------------------------
# 侧边栏 - 参数选择
# -------------------------------
with st.sidebar:
    st.header("分析参数")
    
    ticker = st.text_input("输入股票代码", value="AAPL").upper().strip()
    # 常见A股/港股例子提示
    st.markdown("""
    常见代码示例：
    - 美股：AAPL, TSLA, NVDA, MSFT
    - A股：600519.SS（贵州茅台）, 000001.SZ（平安银行）
    - 港股：0700.HK（腾讯）, 9988.HK（阿里巴巴）
    """)
    
    period = st.selectbox(
        "数据区间",
        ["1mo", "3mo", "6mo", "1y", "2y", "5y", "max"],
        index=3
    )
    
    interval = st.selectbox(
        "K线周期",
        ["1d", "1wk", "1mo"],
        index=0
    )
    
    show_volume = st.checkbox("显示成交量", value=True)
    show_bb = st.checkbox("显示布林带", value=True)
    show_macd = st.checkbox("显示MACD", value=True)
    show_rsi = st.checkbox("显示RSI", value=True)

# -------------------------------
# 主程序逻辑
# -------------------------------
if ticker:
    try:
        with st.spinner(f"正在获取 {ticker} 数据..."):
            # 下载数据
            df = yf.download(
                ticker,
                period=period,
                interval=interval,
                progress=False,
                auto_adjust=True
            )
            
            if df.empty:
                st.error(f"无法获取 {ticker} 的数据！请检查代码是否正确或网络连接。")
                st.stop()
                
            # 计算技术指标
            df['SMA20'] = ta.sma(df['Close'], length=20)
            df['SMA50'] = ta.sma(df['Close'], length=50)
            df['SMA200'] = ta.sma(df['Close'], length=200)
            
            bbands = ta.bbands(df['Close'], length=20, std=2)
            if bbands is not None and not bbands.empty:
                df = pd.concat([df, bbands], axis=1)
            
            macd = ta.macd(df['Close'])
            if macd is not None and not macd.empty:
                df = pd.concat([df, macd], axis=1)
                
            df['RSI'] = ta.rsi(df['Close'], length=14)
            
            # 最新数据
            latest = df.iloc[-1]
            
        # -------------------------------
        # 基本信息卡片
        # -------------------------------
        col1, col2, col3, col4 = st.columns(4)
        
        price_change = latest['Close'] - df.iloc[-2]['Close']
        pct_change = price_change / df.iloc[-2]['Close'] * 100
        
        col1.metric("最新收盘价", f"{latest['Close']:.2f}", 
                   f"{price_change:+.2f} ({pct_change:+.2f}%)")
        
        col2.metric("最高/最低(区间)", 
                   f"{df['High'].max():.2f} / {df['Low'].min():.2f}")
        
        col3.metric("成交量(最新)", f"{latest['Volume']:,.0f}")
        
        info = yf.Ticker(ticker).info
        if 'marketCap' in info:
            col4.metric("市值", f"{info.get('marketCap',0)/1e9:.1f}B")
        
        # -------------------------------
        # K线主图
        # -------------------------------
        st.subheader("K线图 + 技术指标")
        
        fig = make_subplots(
            rows=3 if show_macd or show_rsi else 2,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.08,
            row_heights=[0.60, 0.20, 0.20],
            subplot_titles=("价格与均线/布林带", "成交量" if show_volume else "", "MACD / RSI")
        )
        
        # K线
        fig.add_trace(
            go.Candlestick(
                x=df.index,
                open=df['Open'], high=df['High'],
                low=df['Low'], close=df['Close'],
                name='K线',
                increasing_line_color='red', decreasing_line_color='green'
            ),
            row=1, col=1
        )
        
        # 均线
        for ma, color in [('SMA20', '#00CC94'), ('SMA50', '#FF6B6B'), ('SMA200', '#4D96FF')]:
            if ma in df.columns and df[ma].notna().any():
                fig.add_trace(
                    go.Scatter(x=df.index, y=df[ma], name=ma, line=dict(color=color)),
                    row=1, col=1
                )
        
        # 布林带
        if show_bb and all(col in df.columns for col in ['BBL_20_2.0', 'BBM_20_2.0', 'BBU_20_2.0']):
            fig.add_trace(go.Scatter(x=df.index, y=df['BBU_20_2.0'], 
                                    name='布林上轨', line=dict(color='#FFD93D', dash='dash')), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['BBL_20_2.0'], 
                                    name='布林下轨', line=dict(color='#FFD93D', dash='dash'),
                                    fill='tonexty', fillcolor='rgba(255,217,61,0.08)'), row=1, col=1)
        
        # 成交量
        if show_volume:
            fig.add_trace(
                go.Bar(x=df.index, y=df['Volume'], name='成交量', marker_color='rgba(100,149,237,0.6)'),
                row=2, col=1
            )
        
        # MACD
        if show_macd and all(col in df.columns for col in ['MACD_12_26_9', 'MACDs_12_26_9', 'MACDh_12_26_9']):
            fig.add_trace(go.Scatter(x=df.index, y=df['MACD_12_26_9'], name='MACD', line=dict(color='#2962FF')), row=3, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MACDs_12_26_9'], name='Signal', line=dict(color='#FF5252')), row=3, col=1)
            fig.add_trace(go.Bar(x=df.index, y=df['MACDh_12_26_9'], name='Histogram', marker_color='#26A69A'), row=3, col=1)
        
        # RSI
        if show_rsi and 'RSI' in df.columns:
            row_idx = 3 if show_macd else 2
            fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], name='RSI(14)', line=dict(color='#AB47BC')), row=row_idx, col=1)
            fig.add_hline(y=70, line_dash="dash", line_color="red", row=row_idx, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="green", row=row_idx, col=1)
        
        fig.update_layout(
            height=900,
            showlegend=True,
            xaxis_rangeslider_visible=False,
            template="plotly_dark" if st.session_state.get('theme') == 'dark' else "plotly_white"
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 数据表格（可选）
        if st.checkbox("显示原始数据表（最近100条）", value=False):
            st.dataframe(df.tail(100))
            
    except Exception as e:
        st.error(f"发生错误：{e}")
        st.info("常见原因：网络问题、代码错误、该股票暂无数据、Yahoo接口临时故障等")
else:
    st.info("请输入股票代码开始分析～")