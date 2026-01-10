import streamlit as st
import streamlit_authenticator as stauth
import akshare as ak
import pandas as pd
from openai import OpenAI

# --- 1. 用户信息配置 (你可以修改这里的用户名和密码) ---
names = ["文哥哥"]
usernames = ["wengege"]
# 这里的密码是明文，为了演示方便。实际建议用加密后的。
passwords = ["123456"] 

# 创建登录对象
authenticator = stauth.Authenticate(
    {"usernames": {usernames[0]: {"name": names[0], "password": passwords[0]}}},
    "stock_app_cookie", # 随便起个饼干名
    "signature_key",    # 随便起个签名 key
    cookie_expiry_days=30
)

# 渲染登录界面
name, authentication_status, username = authenticator.login('main')

# --- 2. 判断登录状态 ---
if authentication_status == False:
    st.error('用户名或密码错误')
elif authentication_status == None:
    st.warning('请输入用户名和密码')
elif authentication_status:
    # --- 这里放你原来的所有业务代码 ---
    
    with st.sidebar:
        st.write(f"欢迎你，{name}!")
        authenticator.logout('退出登录', 'sidebar')
        
    st.title("🇨🇳 A股全维度 AI 智能分析系统")

    # 配置 API (从 Secrets 读取)
    DEEPSEEK_API_KEY = st.secrets["deepseek_api_key"]
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

    # ... (这里接你之前的侧边栏输入、数据抓取函数和分析逻辑) ...
    # 注意：原本的所有代码都要往后缩进一个 Tab 键，放在 if authentication_status: 之后

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
    
    # 获取主要财务指标 (最新接口去掉了 _report)
def get_ashare_data(code):
    # 1. 获取实时行情 (这个接口最稳)
    df_spot = ak.stock_zh_a_spot_em()
    spot = df_spot[df_spot['代码'] == code].iloc[0]
    
    # 2. 获取历史日线
    hist = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")
    recent_prices = hist.tail(120) 
    
    # 3. 获取财务指标 (增加异常处理)
    try:
        df_finance = ak.stock_financial_analysis_indicator_em(symbol=code)
        latest_finance = df_finance.iloc[0]
    except Exception:
        # 如果财务数据抓不到，就给一个空的字典，防止报错
        latest_finance = {"净资产收益率(%)": "暂无", "净利润同比增长率(%)": "暂无"}
    
    return spot, recent_prices, latest_finance
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



