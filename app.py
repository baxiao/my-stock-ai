import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI

# --- 1. 基础配置 ---
st.set_page_config(page_title="文哥哥的A股AI分析师", layout="wide")

# --- 2. 配置 DeepSeek API ---
# 确保在 Streamlit 后台 Secrets 配置了 deepseek_api_key
if "deepseek_api_key" in st.secrets:
    client = OpenAI(
        api_key=st.secrets["deepseek_api_key"], 
        base_url="https://api.deepseek.com"
    )
else:
    st.error("❌ 未检测到 API Key！请在 Streamlit 管理后台的 Settings -> Secrets 中添加 deepseek_api_key")
    st.stop()

# --- 3. 界面设计 ---
st.title("🇨🇳 A股全维度 AI 智能分析系统")
st.caption("由 DeepSeek-V3 提供核心分析支持")

with st.sidebar:
    st.header("控制台")
    stock_code = st.text_input("请输入A股代码 (如 600519)", "600519")
    analyze_btn = st.button("🚀 开始深度分析")
    st.divider()
    st.info("💡 提示：输入代码后点击按钮即可。上证代码(60/68开头)，深证代码(00/30开头)")

# --- 4. 数据抓取函数 ---
def get_stock_data(code):
    # 实时行情
    df_spot = ak.stock_zh_a_spot_em()
    spot = df_spot[df_spot['代码'] == code].iloc[0]
    
    # 历史日线数据
    hist = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")
    
    # 财务指标 (带异常处理)
    try:
        df_finance = ak.stock_financial_analysis_indicator_em(symbol=code)
        finance = df_finance.iloc[0]
    except:
        finance = {"净资产收益率(%)": "暂无数据", "净利润同比增长率(%)": "暂无数据"}
        
    return spot, hist, finance

# --- 5. 主程序逻辑 ---
if analyze_btn:
    with st.spinner('AI 正在调取财务数据并多维度建模分析...'):
        try:
            # 抓取数据
            spot, hist, finance = get_stock_data(stock_code)
            
            # 显示基本数据仪表盘
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("最新价", f"¥{spot['最新价']}", f"{spot['涨跌幅']}%")
            col2.metric("成交额", spot['成交额'])
            col3.metric("换手率", f"{spot['换手率']}%")
            col4.metric("动态市盈率", spot['市盈率-动态'])

            # 绘制走势图
            st.subheader(f"📈 {spot['名称']} ({stock_code}) 近期走势")
            st.line_chart(hist.tail(60).set_index('日期')['收盘'])

            # 构造发送给 DeepSeek 的提示词
            prompt = f"""
            你是一名专业的A股首席分析师。请根据以下数据对 {spot['名称']} ({stock_code}) 进行深度投资价值分析。
            
            【实时交易数据】
            - 最新价：{spot['最新价']} (涨跌幅：{spot['涨跌幅']}%)
            - 换手率：{spot['换手率']}%
            - 成交额：{spot['成交额']}
            - 市盈率(动态)：{spot['市盈率-动态']}

            【关键财务指标】
            - 净资产收益率(ROE)：{finance['净资产收益率(%)']}%
            - 净利润同比增长率：{finance['净利润同比增长率(%)']}%

            请按以下模块给出分析报告：
            1. 【投资决策摘要】：总结该股目前的市场地位与强弱。
            2. 【技术指标与价格趋势分析】：结合价格和换手率分析。
            3. 【财务状况评价】：评价其盈利能力与成长性。
            4. 【风险评分】：1-10分 (10分为极高风险)。
            5. 【投资建议与目标价位】：给出操作建议和未来3个月的预测区间。
            """

            # 调用 DeepSeek API
            response = client.chat.completions.create(
                model="deepseek-chat", 
                messages=[{"role": "user", "content": prompt}]
            )

            # 展示 AI 报告
            st.divider()
            st.subheader("🤖 DeepSeek AI 深度分析报告")
            st.markdown(response.choices[0].message.content)

        except Exception as e:
            st.error(f"分析过程中发生错误，请确认代码是否正确。详情：{e}")

else:
    st.write("👈 请在左侧输入股票代码并点击按钮开始。")
