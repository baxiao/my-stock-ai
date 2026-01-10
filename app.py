import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI

# 页面配置
st.set_page_config(page_title="文哥哥的A股AI分析师", layout="wide")
st.title("🇨🇳 A股全维度 AI 智能分析系统")

# --- 1. 配置 DeepSeek API ---
# 请在此处填入你的 API Key
DEEPSEEK_API_KEY = "sk-3b8d5f4b80ef4e1c9b740b99aff0853d"
client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

# --- 2. 侧边栏设置 ---
with st.sidebar:
    st.header("参数设置")
    stock_code = st.text_input("请输入A股代码 (如 600519)", "600519")
    analyze_btn = st.button("开始深度诊断")
    st.info("提示：支持上证(60/68)、深证(00/30)代码")

# --- 3. 数据抓取函数 ---
def get_ashare_data(code):
    # 获取实时行情
    df_spot = ak.stock_zh_a_spot_em()
    current_info = df_spot[df_spot['代码'] == code].iloc[0]
    
    # 获取历史日线 (近半年)
    df_hist = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")
    recent_prices = df_hist.tail(120) # 约半年数据
    
    # 获取主要财务指标
    df_finance = ak.stock_financial_analysis_indicator_report_em(symbol=code)
    latest_finance = df_finance.iloc[0] # 最新一季财报
    
    return current_info, recent_prices, latest_finance

# --- 4. 主分析逻辑 ---
if analyze_btn:
    with st.spinner('正在调取财报及实时交易数据...'):
        try:
            spot, hist, finance = get_ashare_data(stock_code)
            
            # 计算简单的支撑阻力（最近 20 天的高低点）
            support_level = hist['最低'].tail(20).min()
            resistance_level = hist['最高'].tail(20).max()
            
            # 构造发送给 DeepSeek 的提示词
            prompt = f"""
            你是一名专注A股的资深投资顾问。请针对股票 {spot['名称']} ({stock_code}) 进行深度分析。
            
            【市场行情】
            - 当前价格：{spot['最新价']} (涨跌幅：{spot['涨跌幅']}%)
            - 成交额：{spot['成交额']}
            - 换手率：{spot['换手率']}% (反映投资者情绪)
            - 20日支撑位：{support_level}，20日阻力位：{resistance_level}

            【财务数据】
            - 市盈率(PE)：{spot['市盈率-动态']}
            - 净资产收益率(ROE)：{finance['净资产收益率(%)']}%
            - 净利润增长率：{finance['净利润同比增长率(%)']}%

            请结合以上数据，给出以下格式的报告：
            ### 1. 投资决策摘要
            (分析目前该股在A股市场的地位及走势强弱)
            ### 2. 技术与财务综合建议
            (结合支撑阻力位和ROE给出操作建议：买入/持有/观望)
            ### 3. 风险评分
            (1-10分，并说明理由)
            ### 4. 目标价位
            (给出未来一个季度的预测价格区间)
            """

            # 调用 DeepSeek API
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}]
            )

            # --- 5. 结果展示 ---
            st.success(f"分析完成：{spot['名称']} ({stock_code})")
            
            col1, col2 = st.columns([1, 1])
            with col1:
                st.subheader("📈 近半年K线走势")
                # 简单展示价格曲线
                st.line_chart(hist.set_index('日期')['收盘'])
                st.metric("最新价", spot['最新价'], f"{spot['涨跌幅']}%")
            
            with col2:
                st.subheader("🤖 AI 深度诊断报告")
                st.markdown(response.choices[0].message.content)

        except Exception as e:
            st.error(f"分析出错：可能是代码输入有误或API限流。错误信息：{e}")