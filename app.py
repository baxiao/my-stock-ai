import streamlit as st
import streamlit_authenticator as stauth
import akshare as ak
import pandas as pd
from openai import OpenAI

# --- 1. 用户登录配置 ---
# 你可以修改这里的名字、账号和密码
names = ["文哥哥"]
usernames = ["wengege"]
passwords = ["123456"]  # 建议之后修改为更复杂的密码

# 初始化登录模块
authenticator = stauth.Authenticate(
    {"usernames": {usernames[0]: {"name": names[0], "password": passwords[0]}}},
    "stock_app_cookie", 
    "signature_key",    
    cookie_expiry_days=30
)

# 渲染登录界面 (在页面中央)
name, authentication_status, username = authenticator.login('main')

# --- 2. 权限判断 ---
if authentication_status == False:
    st.error('用户名或密码错误，请重新输入')
elif authentication_status == None:
    st.warning('欢迎！请先登录以解锁 AI 股票分析功能')
elif authentication_status:
    # --- 3. 登录成功后的主程序 ---
    
    # 侧边栏：用户信息和退出按钮
    with st.sidebar:
        st.header(f"欢迎，{name}")
        authenticator.logout('退出登录', 'sidebar')
        st.divider()
        stock_code = st.text_input("输入A股代码 (如 600519)", "600519")
        analyze_btn = st.button("🚀 开始深度分析")
        st.caption("提示：60/68开头为沪市，00/30开头为深市")

    st.title("📈 A股全维度 AI 智能分析系统")

    # 配置 DeepSeek API (从 Streamlit Secrets 读取)
    try:
        DEEPSEEK_API_KEY = st.secrets["deepseek_api_key"]
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
    except Exception:
        st.error("未在 Secrets 中配置 API Key，请检查设置。")
        st.stop()

    # --- 4. 数据抓取函数 ---
    def get_ashare_data(code):
        # 实时行情
        df_spot = ak.stock_zh_a_spot_em()
        spot = df_spot[df_spot['代码'] == code].iloc[0]
        
        # 历史日线
        hist = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")
        recent_prices = hist.tail(100) 
        
        # 财务指标 (带容错)
        try:
            df_finance = ak.stock_financial_analysis_indicator_em(symbol=code)
            latest_finance = df_finance.iloc[0]
        except:
            latest_finance = {"净资产收益率(%)": "数据缺失", "净利润同比增长率(%)": "数据缺失"}
        
        return spot, recent_prices, latest_finance

    # --- 5. 执行分析逻辑 ---
    if analyze_btn:
        with st.spinner('正在分析中，请稍候...'):
            try:
                spot_data, hist_data, finance_data = get_ashare_data(stock_code)
                
                # 构造 AI 提示词
                prompt = f"""
                你是一名资深A股策略分析师。请对 {spot_data['名称']} ({stock_code}) 进行专业分析。
                
                【实时行情】
                - 现价：{spot_data['最新价']}，涨跌幅：{spot_data['涨跌幅']}%
                - 换手率：{spot_data['换手率']}%，成交额：{spot_data['成交额']}
                
                【财务指标】
                - ROE：{finance_data['净资产收益率(%)']}%
                - 净利润增长率：{finance_data['净利润同比增长率(%)']}%
                - 市盈率(动)：{spot_data['市盈率-动态']}

                请给出：
                1. 【投资决策摘要】：简述目前多空态势。
                2. 【综合建议】：买入/持有/观望，并给出理由。
                3. 【风险评分】：1-10分。
                4. 【目标价位】：给出未来一个季度的参考区间。
                """

                # 调用 DeepSeek
                response = client.chat.completions.create(
                    model="deepseek-chat", # 或者使用 deepseek-reasoner 性能更强
                    messages=[{"role": "user", "content": prompt}]
                )

                # --- 6. 结果展示 ---
                st.success(f"分析报告生成成功：{spot_data['名称']}")
                
                col1, col2 = st.columns([3, 2])
                with col1:
                    st.subheader("走势观察")
                    st.line_chart(hist_data.set_index('日期')['收盘'])
                
                with col2:
                    st.subheader("核心指标")
                    st.metric("最新价", f"¥{spot_data['最新价']}", f"{spot_data['涨跌幅']}%")
                    st.write(f"**ROE:** {finance_data['净资产收益率(%)']}%")
                    st.write(f"**换手率:** {spot_data['换手率']}%")

                st.divider()
                st.subheader("🤖 AI 深度诊断")
                st.markdown(response.choices[0].message.content)

            except Exception as e:
                st.error(f"分析失败，请确认代码是否正确。错误原因：{e}")
