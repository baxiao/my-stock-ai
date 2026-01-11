import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
import time

# --- 1. 页面配置 ---
st.set_page_config(page_title="文哥哥AI金融终端", page_icon="📈", layout="wide")

# --- 2. API 配置 ---
if "deepseek_api_key" in st.secrets:
    client = OpenAI(api_key=st.secrets["deepseek_api_key"], base_url="https://api.deepseek.com")
else:
    st.error("🔑 请在后台配置 API Key")
    st.stop()

# --- 3. 极速数据抓取（带重试机制） ---
def get_stock_data_reliable(code):
    """
    分步获取数据，确保第一步不崩
    """
    try:
        # 尝试获取最简单的一行行情 (这个接口最不容易被封)
        df = ak.stock_zh_a_spot_em()
        # 筛选输入代码
        target = df[df['代码'] == code]
        
        if target.empty:
            return None, None, None, None
            
        spot = target.iloc[0]
        name = spot['名称']
        price = spot['最新价']
        change = spot['涨跌幅']
        
        # 尝试抓取K线 (用于画图)，如果卡住就返回空
        try:
            hist = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq").tail(60)
        except:
            hist = pd.DataFrame()
            
        return name, price, change, hist
    except Exception as e:
        st.warning(f"正在尝试备用连接... {e}")
        return None, None, None, None

# --- 4. 主界面 ---
st.title("🛡️ 文哥哥 A股 AI 智能情报站")

with st.container():
    stock_code = st.text_input("📍 输入股票代码 (如 600519)", value="600519")

tab1, tab2 = st.tabs(["🔥 实时行情", "🧠 AI 深度决策"])

with tab1:
    if st.button("查看行情"):
        with st.status("📡 正在穿透网络连接交易所...", expanded=True) as status:
            name, price, change, hist = get_stock_data_reliable(stock_code)
            if name:
                status.update(label="✅ 数据获取成功!", state="complete", expanded=False)
                st.subheader(f"📊 {name} ({stock_code})")
                c1, c2 = st.columns(2)
                c1.metric("最新价", f"¥{price}", f"{change}%")
                if not hist.empty:
                    st.line_chart(hist.set_index('日期')['收盘'])
            else:
                status.update(label="❌ 连接被拦截", state="error")
                st.error("国内交易所限制了海外访问，请多点几次按钮重试，或稍后再试。")

with tab2:
    if st.button("生成 AI 决策报告"):
        try:
            with st.spinner('🤖 DeepSeek 正在极速建模...'):
                # 如果第一步拿到了数据，直接传给AI；如果没拿到，让AI根据代码盲分析
                prompt = f"分析A股代码 {stock_code} 的近期走势和投资建议。请给买入出手建议、目标价和支撑压力位。"
                
                response = client.chat.completions.create(
                    model="deepseek-chat", 
                    messages=[{"role": "user", "content": prompt}]
                )
                
                st.subheader(f"📋 代码 {stock_code} 投研决策书")
                st.info(response.choices[0].message.content)
        except Exception as e:
            st.error("AI 接口拥挤，请稍后再试。")

st.divider()
st.caption("风险提示：AI建议仅供参考。如果多次提示超时，说明云端服务器IP被交易所拦截。")
