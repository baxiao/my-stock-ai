import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
from fpdf import FPDF
import time

# --- 1. 页面配置 ---
st.set_page_config(page_title="文哥哥AI金融终端", page_icon="📈", layout="wide")

# --- 2. API 配置 ---
if "deepseek_api_key" in st.secrets:
    client = OpenAI(api_key=st.secrets["deepseek_api_key"], base_url="https://api.deepseek.com")
else:
    st.error("🔑 请在后台配置 API Key")
    st.stop()

# --- 3. 极速数据抓取逻辑 ---
def get_stock_data_fast(code):
    """
    使用更轻量级的接口，避免卡顿
    """
    # 1. 抓取基本面和现价 (只抓个股，不刷全表)
    # 改用这个接口比之前的快得多
    df_info = ak.stock_individual_info_em(symbol=code)
    # 提取关键数值
    name = df_info[df_info['item'] == '股票名称']['value'].values[0]
    price = df_info[df_info['item'] == '最新价']['value'].values[0]
    change_pct = df_info[df_info['item'] == '当日涨跌幅']['value'].values[0]
    
    # 2. 抓取K线 (用于画图)
    hist = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq").tail(60)
    
    return name, price, change_pct, hist

# --- 4. 主界面 ---
st.title("🛡️ 文哥哥 A股 AI 智能情报站")

with st.container():
    col_input, _ = st.columns([1, 2])
    with col_input:
        stock_code = st.text_input("📍 输入股票代码", value="600519")

tab1, tab2 = st.tabs(["🔥 资金 & 走势", "🧠 AI 深度决策"])

# --- 功能一：资金与走势 (极速版) ---
with tab1:
    if st.button("查看行情与资金"):
        progress_bar = st.progress(0)
        try:
            # 第一阶段：快速行情
            st.write("🚀 正在极速连接交易所...")
            name, price, change, hist = get_stock_data_fast(stock_code)
            progress_bar.progress(50)
            
            # 展示核心指标
            st.subheader(f"📊 {name} ({stock_code}) 实时状态")
            c1, c2 = st.columns(2)
            c1.metric("最新股价", f"¥{price}", f"{change}%")
            c2.write("✅ 行情对接成功，请切换至AI分析查看建议")
            
            st.line_chart(hist.set_index('日期')['收盘'])
            progress_bar.progress(100)
            
        except Exception as e:
            st.error(f"⚠️ 交易所响应超时或代码输入有误。建议换个代码试试，或者稍后再试。")
            st.caption(f"错误详情: {e}")

# --- 功能二：深度分析 ---
with tab2:
    if st.button("生成 AI 决策报告"):
        try:
            with st.spinner('🤖 DeepSeek 正在思考中...'):
                # 重新简单取一下现价
                name, price, change, _ = get_stock_data_fast(stock_code)
                
                prompt = f"你是资深操盘手。分析{name}({stock_code})。现价{price}，涨跌{change}%。给出买卖建议和目标价。"
                response = client.chat.completions.create(
                    model="deepseek-chat", 
                    messages=[{"role": "user", "content": prompt}]
                )
                
                st.subheader(f"📋 {name} 投研决策书")
                st.info(response.choices[0].message.content)
        except Exception as e:
            st.error("AI 模块暂时忙碌，请稍后再试。")
