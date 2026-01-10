import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
import time

# --- 1. 基础配置 ---
st.set_page_config(page_title="文哥哥AI荐股", layout="wide")

# --- 2. 配置 DeepSeek API ---
if "deepseek_api_key" in st.secrets:
    client = OpenAI(
        api_key=st.secrets["deepseek_api_key"], 
        base_url="https://api.deepseek.com"
    )
else:
    st.error("❌ 未在 Secrets 中检测到 deepseek_api_key")
    st.stop()

st.title("🚀 A股主力雷达 + AI 决策系统")

with st.sidebar:
    st.header("控制台")
    stock_code = st.text_input("输入A股代码", "600519")
    analyze_btn = st.button("📊 开始全维度分析")
    st.divider()
    st.info("将分析：实时行情 + 主力资金 + 财务面 + AI 目标价")

# --- 3. 核心数据抓取函数 ---
def get_comprehensive_data(code):
    # A. 实时行情
    df_spot = ak.stock_zh_a_spot_em()
    spot = df_spot[df_spot['代码'] == code].iloc[0]
    
    # B. 历史K线
    hist = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq").tail(100)
    
    # C. 新增：主力资金流向 (获取当天的个股资金流向)
    try:
        df_fund = ak.stock_individual_fund_flow(stock=code, market="sh" if code.startswith('6') else "sz")
        latest_fund = df_fund.iloc[0] # 获取最新一日资金流向
        fund_status = {
            "主力净流入": latest_fund['主力净流入-净额'],
            "超大单净流入": latest_fund['超大单净流入-净额'],
            "主力净占比": latest_fund['主力净流入-净占比']
        }
    except:
        fund_status = {"主力净流入": "数据接口繁忙", "超大单净流入": "N/A", "主力净占比": "N/A"}

    # D. 财务指标
    try:
        df_finance = ak.stock_financial_analysis_indicator_em(symbol=code)
        finance = df_finance.iloc[0]
    except:
        finance = {"净资产收益率(%)": "暂无", "净利润同比增长率(%)": "暂无"}
        
    return spot, hist, fund_status, finance

# --- 4. 分析逻辑 ---
if analyze_btn:
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        # 1. 抓取阶段
        status_text.text("🔍 正在监控主力轨迹与市场数据...")
        spot, hist, fund, finance = get_comprehensive_data(stock_code)
        progress_bar.progress(40)
        
        # 2. 核心看板展示
        st.subheader(f"💎 {spot['名称']} ({stock_code}) 数据面板")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("最新价", f"¥{spot['最新价']}", f"{spot['涨跌幅']}%")
        c2.metric("主力净买入", f"{fund['主力净流入']}元")
        c3.metric("主力占比", f"{fund['主力净占比']}%")
        c4.metric("动态市盈率", spot['市盈率-动态'])

        # 3. 走势展示
        st.line_chart(hist.set_index('日期')['收盘'])

        # 4. AI 决策阶段
        status_text.text("🤖 DeepSeek 正在进行多维度决策建模...")
        
        # 强化 Prompt
        prompt = f"""
        你是一名顶尖的量化投资总监。请分析 {spot['名称']} ({stock_code})。
        
        【数据】
        - 价格：{spot['最新价']}，涨跌幅：{spot['涨跌幅']}%
        - 主力资金流向：{fund['主力净流入']}元，占比：{fund['主力净占比']}%
        - 财务面：ROE {finance.get('净资产收益率(%)')}%，净利增长 {finance.get('净利润同比增长率(%)')}%
        
        【要求】请严格按以下格式输出，不要含糊其辞：
        1. 【主力动向分析】：判断主力是在撤退还是在潜伏，主力是否在场。
        2. 【核心决策】：明确给出【强烈建议购入】、【建议出手/减持】或【暂时观望】。
        3. 【目标价格】：给出未来3-6个月的预期最高价。
        4. 【理由】：结合资金流向和财务指标给出3点逻辑。
        """

        response = client.chat.completions.create(
            model="deepseek-chat", 
            messages=[{"role": "user", "content": prompt}]
        )
        
        progress_bar.progress(100)
        status_text.text("✅ 分析报告已生成")
        
        # 5. 展示结果
        st.divider()
        st.subheader("🤖 DeepSeek AI 投资决策书")
        # 用高亮色块突出显示建议
        report = response.choices[0].message.content
        st.markdown(report)
        
        # 6. PDF 导出 (延续之前功能)
        st.divider()
        st.download_button(
            label="📥 导出分析报告 (PDF)",
            data=report, # 简化处理，直接导出文本
            file_name=f"{stock_code}_decision.txt",
            mime="text/plain"
        )
        
    except Exception as e:
        st.error(f"分析中断：{e}")
        st.info("提示：若提示资金流向错误，可能是该股今日尚未开盘或接口限流。")
