import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI

# --- 1. 基础页面设置 ---
st.set_page_config(page_title="文哥哥AI分析师", layout="wide")

# --- 2. DeepSeek API 配置 ---
if "deepseek_api_key" in st.secrets:
    client = OpenAI(
        api_key=st.secrets["deepseek_api_key"], 
        base_url="https://api.deepseek.com"
    )
else:
    st.error("❌ 请在 Secrets 中配置 deepseek_api_key")
    st.stop()

# --- 3. 辅助函数 ---
def get_market(code):
    return "sh" if code.startswith(('6', '9', '688')) else "sz"

def get_base_data(code):
    """获取基础行情数据"""
    df_spot = ak.stock_zh_a_spot_em()
    spot = df_spot[df_spot['代码'] == code].iloc[0]
    return spot

# --- 4. 侧边栏：功能切换 ---
with st.sidebar:
    st.header("功能菜单")
    mode = st.radio(
        "选择操作模式：",
        ("主力进场/退场监控", "个股深度AI分析")
    )
    st.divider()
    stock_code = st.text_input("请输入股票代码 (如 600519)", "600519")
    run_btn = st.button("🚀 执行查询")
    st.divider()
    if mode == "主力进场/退场监控":
        st.caption("🔍 模式说明：专门监控大单资金流向，判断主力是否在场。")
    else:
        st.caption("🤖 模式说明：全维度基本面+技术面分析，并给出买卖建议。")

# --- 5. 功能逻辑实现 ---

# --- 功能 A：主力进场/退场监控 ---
if run_btn and mode == "主力进场/退场监控":
    with st.spinner('正在扫描主力筹码...'):
        try:
            spot = get_base_data(stock_code)
            market = get_market(stock_code)
            # 获取个股资金流向
            df_fund = ak.stock_individual_fund_flow(stock=stock_code, market=market)
            latest = df_fund.iloc[0] # 获取最新一天
            
            st.subheader(f"📊 主力动向监控：{spot['名称']} ({stock_code})")
            
            c1, c2, c3 = st.columns(3)
            # 根据流入流出显示颜色
            main_inflow = latest['主力净流入-净额']
            color = "normal" if "-" not in str(main_inflow) else "inverse"
            
            c1.metric("主力净流入(元)", f"{main_inflow}", delta=None)
            c2.metric("超大单流入(元)", f"{latest['超大单净流入-净额']}")
            c3.metric("主力净占比", f"{latest['主力净流入-净占比']}%")

            # 调用 AI 快速定性
            prompt = f"""
            分析股票 {spot['名称']} 今日资金数据：
            主力净流入：{main_inflow}元，占比：{latest['主力净流入-净占比']}%。
            请简短判断：1.主力是在进场还是退场？2.属于吸筹、出货还是洗盘？3.散户跟风情况。
            """
            response = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}])
            
            st.info(f"🤖 **AI 资金定性判读：**\n\n{response.choices[0].message.content}")
            
        except Exception as e:
            st.error(f"数据抓取失败，可能由于非交易日或代码错误：{e}")

# --- 功能 B：个股深度AI分析 ---
if run_btn and mode == "个股深度AI分析":
    with st.spinner('AI 正在全维度建模分析...'):
        try:
            spot = get_base_data(stock_code)
            hist = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq").tail(60)
            
            st.subheader(f"🤖 深度决策报告：{spot['名称']} ({stock_code})")
            
            col1, col2 = st.columns([2, 1])
            with col1:
                st.line_chart(hist.set_index('日期')['收盘'])
            with col2:
                st.write(f"**最新价:** ¥{spot['最新价']}")
                st.write(f"**涨跌幅:** {spot['涨跌幅']}%")
                st.write(f"**市盈率:** {spot['市盈率-动态']}")
                st.write(f"**换手率:** {spot['换手率']}%")

            # 调用 AI 进行深度分析
            prompt = f"""
            你是一名专业的A股分析师。针对 {spot['名称']} ({stock_code}) 给出深度报告：
            1. 建议购入还是出手？（明确给出一个：强烈买入、观望、或出手）
            2. 目标价格是多少？（给出未来1-3个月的预测）
            3. 该股目前的支撑位和压力位在哪里？
            """
            response = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}])
            
            st.divider()
            st.markdown("### 📋 AI 实战策略建议")
            st.success(response.choices[0].message.content)
            
        except Exception as e:
            st.error(f"分析失败：{e}")
