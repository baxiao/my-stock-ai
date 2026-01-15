import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas_ta as ta
from openai import OpenAI
import time
import re

# =====================================
# 页面设定
# =====================================
st.set_page_config(
    page_title="国产A股分析工具 + DeepSeek AI",
    page_icon="🇨🇳📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🇨🇳 国产A股分析工具 + DeepSeek 智能分析")
st.caption("专属国产A股 • 数据来源：yfinance • AI分析：DeepSeek")

# =====================================
# 侧边栏设定 - 只显示A股相关
# =====================================
with st.sidebar:
    st.header("分析设定（仅限A股）")
    
    ticker = st.text_input("A股代码（例：600519.SS）", value="600519.SS").strip().upper()
    
    st.markdown("""
    **国产A股常见代码示例：**
    - 600519.SS → 贵州茅台
    - 000001.SZ → 平安银行
    - 601318.SS → 中国平安
    - 300750.SZ → 宁德时代
    - 601012.SS → 隆基绿能
    - 688981.SH → 中芯国际（科创板用 .SH 也可，但推荐 .SS）
    
    **注意**：本工具目前**只支持A股**（.SS / .SZ 结尾），其他市场（如美股、港股）暂不支持。
    """)
    
    period = st.selectbox("资料期间", ["1mo", "3mo", "6mo", "1y", "2y", "5y", "max"], index=3)
    interval = st.selectbox("K线周期", ["1d", "5d", "1wk", "1mo"], index=0)
    
    st.markdown("---")
    st.subheader("显示选项")
    show_volume = st.checkbox("显示成交量", value=True)
    show_ma = st.checkbox("显示移动平均线 (20/50/200)", value=True)
    show_bb = st.checkbox("显示布林通道", value=True)
    show_macd = st.checkbox("显示 MACD", value=True)
    show_rsi = st.checkbox("显示 RSI(14)", value=True)

# DeepSeek API Key（建议使用 st.secrets）
DEEPSEEK_API_KEY = st.secrets.get("DEEPSEEK_API_KEY", None)

# =====================================
# 简单校验：只允许A股代码
# =====================================
if ticker:
    if not re.match(r'^(6|0|3)\d{5}\.(SS|SZ|SH)$', ticker):
        st.error("请输入正确的**国产A股**代码！\n必须以 .SS / .SZ / .SH 结尾，例如：600519.SS 或 300750.SZ")
        st.stop()

# =====================================
# 主程序
# =====================================
if ticker:
    try:
        with st.spinner(f"正在载入 {ticker} 国产A股数据..."):
            # yfinance 下载 + 重试机制
            for attempt in range(3):
                try:
                    time.sleep(1.5)
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
                st.error(f"无法取得 {ticker} 的数据（已尝试多次）")
                st.info("可能原因：Yahoo Finance 临时限制、网络问题、代码格式错误\n请尝试换个时间段或稍后再试")
                st.stop()

            # 计算技术指标（同之前）
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

            try:
                info = yf.Ticker(ticker).info
            except:
                info = {}

        # 关键数据卡片
        col1, col2, col3, col4 = st.columns(4)
        
        change = latest['Close'] - prev['Close']
        pct = change / prev['Close'] * 100 if prev['Close'] != 0 else 0
        
        col1.metric("最新收盘", f"{latest['Close']:.2f}", f"{change:+.2f} ({pct:+.2f}%)")
        col2.metric("区间高/低", f"{df['High'].max():.2f} / {df['Low'].min():.2f}")
        col3.metric("最新成交量", f"{int(latest['Volume']):,}")
        col4.metric("市值", f"{info.get('marketCap', '—'):,}" if info.get('marketCap') else "—")

        # K线图部分（保持原样）
        st.subheader("价格走势与技术指标")

        rows = 1 + (1 if show_volume else 0) + (1 if show_macd or show_rsi else 0)
        fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, 
                           vertical_spacing=0.06, row_heights=[0.6] + [0.2]*(rows-1))

        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'],
                                    low=df['Low'], close=df['Close'], name='K线',
                                    increasing_line_color='#ef5350', decreasing_line_color='#26a69a'),
                      row=1, col=1)

        if show_ma:
            for name, col, color in [("MA20","#00C853"), ("MA50","#FF9800"), ("MA200","#2979FF")]:
                if col in df.columns:
                    fig.add_trace(go.Scatter(x=df.index, y=df[col], name=name, line=dict(color=color)), row=1, col=1)

        if show_bb and all(c in df.columns for c in ['BBU_20_2.0', 'BBL_20_2.0']):
            fig.add_trace(go.Scatter(x=df.index, y=df['BBU_20_2.0'], line=dict(color='#ffca28',dash='dash'), name="上轨"), row=1,col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['BBL_20_2.0'], line=dict(color='#ffca28',dash='dash'), name="下轨",
                                    fill='tonexty', fillcolor='rgba(255,202,40,0.08)'), row=1,col=1)

        current_row = 2
        if show_volume:
            fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name="成交量", marker_color='rgba(100,181,246,0.5)'), row=current_row, col=1)
            current_row += 1

        if show_macd and all(c in df.columns for c in ['MACD_12_26_9', 'MACDs_12_26_9']):
            fig.add_trace(go.Scatter(x=df.index, y=df['MACD_12_26_9'], name='MACD', line=dict(color='#1976d2')), row=current_row, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MACDs_12_26_9'], name='讯号', line=dict(color='#d32f2f')), row=current_row, col=1)
            fig.add_trace(go.Bar(x=df.index, y=df['MACDh_12_26_9'], name='柱', marker_color=['#26a69a' if x>=0 else '#ef5350' for x in df['MACDh_12_26_9']]), row=current_row, col=1)
            current_row += 1

        if show_rsi and 'RSI' in df.columns:
            fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], name='RSI(14)', line=dict(color='#8e24aa')), row=current_row, col=1)
            fig.add_hline(y=70, line_dash="dash", line_color="red", row=current_row, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="lime", row=current_row, col=1)

        fig.update_layout(height=800, showlegend=True, xaxis_rangeslider_visible=False,
                         template="plotly_dark" if "dark" in st.session_state.get("theme", "") else "plotly_white")

        st.plotly_chart(fig, use_container_width=True)

        # DeepSeek AI 分析（提示语已调整为A股语境）
        st.markdown("---")
        st.subheader("🤖 DeepSeek AI 分析（国产A股专属）")

        if st.button("使用 DeepSeek 进行深度分析", type="primary"):
            if not DEEPSEEK_API_KEY:
                st.error("尚未设定 DeepSeek API Key\n请在 Streamlit Cloud → Secrets 加入 DEEPSEEK_API_KEY")
            else:
                with st.spinner("DeepSeek 正在分析这只国产A股...（约 8–25 秒）"):
                    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

                    data_summary = f"""
A股代码：{ticker}
最新收盘：{latest['Close']:.2f}  涨跌：{change:+.2f} ({pct:+.2f}%)
区间最高/最低：{df['High'].max():.2f} / {df['Low'].min():.2f}
最新成交量：{latest['Volume']:,.0f}

技术指标（最新）：
MA20: {df.get('MA20', pd.Series([None])).iloc[-1]:.2f if 'MA20' in df.columns else 'N/A'}
MA50: {df.get('MA50', pd.Series([None])).iloc[-1]:.2f if 'MA50' in df.columns else 'N/A'}
MA200: {df.get('MA200', pd.Series([None])).iloc[-1]:.2f if 'MA200' in df.columns else 'N/A'}
RSI(14): {df.get('RSI', pd.Series([None])).iloc[-1]:.2f if 'RSI' in df.columns else 'N/A'}
MACD: {df.get('MACD_12_26_9', pd.Series([None])).iloc[-1]:.4f if 'MACD_12_26_9' in df.columns else 'N/A'}

近10天收盘（由新到旧）：{', '.join(f'{x:.2f}' for x in df['Close'].tail(10)[::-1])}

公司名称：{info.get('longName', '未知')}
行业/板块：{info.get('industry', '未知')} / {info.get('sector', '未知')}
                    """.strip()

                    prompt = f"""你是一位经验丰富且非常保守的中国A股专业分析师。
请根据以下最新国产A股数据，对这只股票进行客观分析，不要夸大、不做收益保证、不鼓励追涨杀跌。

重点回覆内容：
1. 目前技术面大概处于什么阶段？（强势、多头、空头、震荡）
2. 短期（1~4周）与中期（1~3个月）可能方向及关键观察点
3. 主要支撑与压力位参考
4. A股市场常见风险提醒（政策、业绩、地缘等）
5. 给普通散户的保守操作建议

数据如下：

{data_summary}

请用简洁中文回覆，条理清晰，控制在450~700字。"""

                    try:
                        response = client.chat.completions.create(
                            model="deepseek-reasoner",
                            messages=[
                                {"role": "system", "content": "你是专业、理性、保守的中国A股分析师。"},
                                {"role": "user", "content": prompt}
                            ],
                            temperature=0.35,
                            max_tokens=1000
                        )
                        st.markdown("### DeepSeek A股分析结果")
                        st.markdown(response.choices[0].message.content)

                    except Exception as api_err:
                        st.error(f"DeepSeek API 调用失败：{str(api_err)}")

    except Exception as e:
        st.error(f"程序执行发生错误：{str(e)}")
        st.info("常见原因：Yahoo Finance 临时限制、网络问题、代码格式错误等\n请稍后再试或换个A股代码")
else:
    st.info("请输入国产A股代码开始分析（必须带 .SS / .SZ）～")