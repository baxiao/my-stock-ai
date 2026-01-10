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
    st.divider()
    st.caption("预估耗时：15-25秒")

# --- 3. 辅助函数：模拟进度条 ---
def smooth_progress(progress_bar, status_text, start_val, end_val, speed=0.1):
    """让进度条平滑移动的函数"""
    curr = start_val
    while curr < end_val:
        curr += 1
        progress_bar.progress(curr)
        # 剩余时间简单估算
        remaining = int((end_val - curr) * speed)
        status_text.text(f"正在深度建模中... 预计还需 {remaining + 5} 秒")
        time.sleep(speed)

# --- 4. 数据抓取函数 ---
def get_stock_data_safe(code):
    df_spot = ak.stock_zh_a_spot_em()
    spot = df_spot[df_spot['代码'] == code].iloc[0]
    hist = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")
    
    finance_data = {"净资产收益率(%)": "暂无", "净利润同比增长率(%)": "暂无"}
    try:
        df_finance = ak.stock_financial_analysis_indicator_em(symbol=code)
        if not df_finance.empty:
            finance_data = df_finance.iloc[0]
    except:
        pass
        
    return spot, hist, finance_data

# --- 5. 主逻辑 ---
if analyze_btn:
    # A. 初始化进度条和状态文本
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        # B. 数据准备阶段 (0% -> 30%)
        status_text.text("🔍 正在抓取市场实时行情...")
        spot, hist, finance = get_stock_data_safe(stock_code)
        progress_bar.progress(30)
        
        # C. 展示基本走势
        st.subheader(f"📈 {spot['名称']} ({stock_code}) 走势预览")
        st.line_chart(hist.tail(60).set_index('日期')['收盘'])

        # D. AI 分析阶段 (30% -> 95%)
        # 这个阶段我们开启平滑滚动模拟，直到 95% 停住等 API 返回
        status_text.text("🤖 正在连接 DeepSeek 智算中心...")
        
        prompt = f"""
        你是一名资深A股分析师。请分析 {spot['名称']} ({stock_code})。
        最新价：{spot['最新价']}，换手率：{spot['换手率']}%。
        ROE：{finance.get('净资产收益率(%)', '未知')}%。
        请给出：1.投资摘要 2.操作建议 3.风险评分(1-10) 4.预测区间。
        """

        # 我们预测 API 响应大概需要 15 秒，所以这里让进度条慢慢走
        # 注意：这里我们不在循环里调用 API，而是先发请求，用一个占位符模拟
        with st.spinner('AI 正在思考中...'):
            # 发起真正的 AI 请求
            response = client.chat.completions.create(
                model="deepseek-chat", 
                messages=[{"role": "user", "content": prompt}]
            )

        # E. 完成阶段 (95% -> 100%)
        progress_bar.progress(100)
        status_text.text("✅ 分析报告生成完毕！")
        time.sleep(1)
        status_text.empty() # 清除提示文字
        progress_bar.empty() # 清除进度条

        st.divider()
        st.subheader("🤖 DeepSeek AI 深度分析报告")
        st.markdown(response.choices[0].message.content)
        
    except Exception as e:
        st.error(f"分析发生意外：{e}")
        progress_bar.empty()
        status_text.empty()
