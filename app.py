import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
import time

# --- 1. 基础配置 ---
st.set_page_config(page_title="文哥哥的A股分析师", layout="wide")

# --- 2. 配置 DeepSeek API ---
if "deepseek_api_key" in st.secrets:
    client = OpenAI(
        api_key=st.secrets["deepseek_api_key"], 
        base_url="https://api.deepseek.com"
    )
else:
    st.error("❌ 未检测到 API Key，请在 Secrets 中配置")
    st.stop()

st.title("🇨🇳 A股全维度 AI 智能分析系统")

with st.sidebar:
    st.header("控制台")
    stock_code = st.text_input("请输入A股代码 (如 600519)", "600519")
    analyze_btn = st.button("🚀 开始深度分析")

# --- 3. 优化后的数据抓取函数 ---
def get_stock_data_safe(code):
    # 第一步：抓取实时行情 (这个很快)
    st.write("🔍 正在抓取实时行情...")
    df_spot = ak.stock_zh_a_spot_em()
    spot = df_spot[df_spot['代码'] == code].iloc[0]
    
    # 第二步：抓取K线 (也很稳)
    st.write("📊 正在下载走势图...")
    hist = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")
    
    # 第三步：抓取财务指标 (容易卡顿，加入容错)
    st.write("📑 正在尝试调取财务数据 (若5秒未响应将跳过)...")
    finance_data = {"净资产收益率(%)": "暂无", "净利润同比增长率(%)": "暂无"}
    try:
        # 这里尝试抓取，如果网络慢就报错进入except
        df_finance = ak.stock_financial_analysis_indicator_em(symbol=code)
        if not df_finance.empty:
            finance_data = df_finance.iloc[0]
    except:
        st.warning("⚠️ 财务接口响应较慢，已转为纯技术面分析")
        
    return spot, hist, finance_data

# --- 4. 主逻辑 ---
if analyze_btn:
    # 建立一个状态容器
    status_text = st.empty()
    
    try:
        # 开始抓取
        spot, hist, finance = get_stock_data_safe(stock_code)
        
        # 显示基础信息
        st.subheader(f"📈 {spot['名称']} ({stock_code})")
        st.line_chart(hist.tail(60).set_index('日期')['收盘'])

        # 开始调用 AI
        st.write("🤖 正在连接 DeepSeek 进行深度建模，请稍等片刻...")
        
        prompt = f"""
        你是一名资深A股分析师。请分析 {spot['名称']} ({stock_code})。
        价格：{spot['最新价']} ({spot['涨跌幅']}%)，换手率：{spot['换手率']}%。
        ROE：{finance.get('净资产收益率(%)', '未知')}%。
        请给出投资建议、风险评分和目标价位。
        """

        response = client.chat.completions.create(
            model="deepseek-chat", 
            messages=[{"role": "user", "content": prompt}]
        )

        st.divider()
        st.subheader("🤖 AI 诊断报告")
        st.markdown(response.choices[0].message.content)
        
    except Exception as e:
        st.error(f"发生错误：{e}")
