import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
import time

# --- 1. 基础页面设置 ---
st.set_page_config(page_title="文哥哥AI分析师", layout="wide", initial_sidebar_state="expanded")

# --- 2. 核心：DeepSeek API 安全接入 ---
if "deepseek_api_key" in st.secrets:
    client = OpenAI(
        api_key=st.secrets["deepseek_api_key"], 
        base_url="https://api.deepseek.com"
    )
else:
    st.error("❌ 请在 Streamlit 后台 Secrets 配置 deepseek_api_key")
    st.stop()

# --- 3. 辅助函数：判断沪深市场 ---
def get_market(code):
    if code.startswith(('6', '9', '688')):
        return "sh"
    else:
        return "sz"

# --- 4. 主界面设计 ---
st.title("📈 A股主力监控 + AI 智能决策系统")
st.markdown("---")

with st.sidebar:
    st.header("🔍 股票查询")
    stock_code = st.text_input("代码 (如: 600519)", value="600519", max_chars=6)
    analyze_btn = st.button("🚀 开启全维度深度分析")
    st.divider()
    st.caption("提示：包含实时行情、主力资金、AI 买卖建议")

# --- 5. 核心逻辑执行 ---
if analyze_btn:
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        # 第一阶段：抓取实时与历史行情
        status_text.text("正在同步实时交易数据...")
        df_spot = ak.stock_zh_a_spot_em()
        spot = df_spot[df_spot['代码'] == stock_code].iloc[0]
        
        hist = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq").tail(60)
        progress_bar.progress(30)
        
        # 第二阶段：监控主力资金 (关键修改点)
        status_text.text("正在扫描主力筹码动向...")
        market = get_market(stock_code)
        try:
            # 抓取个股资金流向
            df_fund = ak.stock_individual_fund_flow(stock=stock_code, market=market)
            latest_fund = df_fund.iloc[0]
            main_inflow = latest_fund['主力净流入-净额']
            main_pct = latest_fund['主力净流入-净占比']
        except:
            main_inflow = "数据维护中"
            main_pct = "N/A"
        progress_bar.progress(60)

        # 第三阶段：展示仪表盘
        st.subheader(f"💎 {spot['名称']} ({stock_code}) 核心情报")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("最新价", f"¥{spot['最新价']}", f"{spot['涨跌幅']}%")
        c2.metric("主力净买入", f"{main_inflow}")
        c3.metric("主力占比", f"{main_pct}%")
        c4.metric("换手率", f"{spot['换手率']}%")
        
        st.line_chart(hist.set_index('日期')['收盘'])
        
        # 第四阶段：AI 决策
        status_text.text("🤖 DeepSeek 正根据主力动向制定投资决策...")
        
        prompt = f"""
        你是一名A股顶级操盘手。请针对 {spot['名称']} ({stock_code}) 给出实战分析：
        - 现价：{spot['最新价']} ({spot['涨跌幅']}%)
        - 主力资金状态：净流入 {main_inflow}，占比 {main_pct}%
        - 市场数据：市盈率 {spot['市盈率-动态']}，换手率 {spot['换手率']}%
        
        请严格按以下要求输出：
        1. 【主力是否存在】：根据资金占比判断主力是在吸筹、派发还是观望。
        2. 【买卖动作建议】：必须从【强烈买入、分批买入、持股观望、逢高减持、一键清仓】中选一个。
        3. 【目标价格】：给出未来一个月的短线压力位和长线目标位。
        4. 【风险警示】：给出当前最核心的一个风险点。
        """

        response = client.chat.completions.create(
            model="deepseek-chat", 
            messages=[{"role": "user", "content": prompt}]
        )
        
        progress_bar.progress(100)
        status_text.text("✅ 分析完成")
        
        st.divider()
        st.subheader("🤖 DeepSeek AI 投资决策建议")
        st.info(response.choices[0].message.content)

    except Exception as e:
        st.error(f"分析出错：请确保代码正确且股市已开盘。详情：{e}")
