import streamlit as st
import streamlit_authenticator as stauth
import akshare as ak
import pandas as pd
from openai import OpenAI

# --- 1. 基础配置 ---
st.set_page_config(page_title="文哥哥的A股AI分析师", layout="wide")

# --- 2. 用户登录系统配置 ---
# 这里定义用户信息
credentials = {
    "usernames": {
        "wengege": {
            "name": "文哥哥",
            "password": "123456"  # 登录账号: wengege, 密码: 123456
        }
    }
}

# 初始化登录模块
authenticator = stauth.Authenticate(
    credentials,
    "stock_dashboard_cookie",  # Cookie名称
    "auth_key_12345",          # 签名密钥
    cookie_expiry_days=30
)

# --- 3. 渲染登录界面 ---
# 使用 try-except 包裹以防止前端渲染报错
try:
    name, authentication_status, username = authenticator.login(location='main')
except Exception as e:
    st.error("界面加载异常，请尝试刷新页面")
    st.stop()

# --- 4. 逻辑判断 ---
if authentication_status == False:
    st.error('用户名或密码错误')
elif authentication_status == None:
    st.warning('🔒 请输入账号密码登录系统')
    st.info("默认账号：wengege | 密码：123456")
elif authentication_status:
    # --- 登录成功后的主程序 ---
    
    # 侧边栏配置
    with st.sidebar:
        st.success(f"欢迎，{name}!")
        authenticator.logout('退出登录', 'sidebar')
        st.divider()
        stock_code = st.text_input("请输入A股代码 (如 600519)", "600519")
        analyze_btn = st.button("🚀 开始 AI 深度分析")
        st.caption("注：支持上证(60/68)、深证(00/30)")

    st.title("🇨🇳 A股全维度 AI 智能分析系统")

    # 配置 DeepSeek API (务必确保在 Streamlit Secrets 中配置了 key)
    if "deepseek_api_key" in st.secrets:
        client = OpenAI(
            api_key=st.secrets["deepseek_api_key"], 
            base_url="https://api.deepseek.com"
        )
    else:
        st.error("未检测到 API Key，请在 Streamlit 后台 Secrets 配置 deepseek_api_key")
        st.stop()

    # --- 数据抓取函数 (带容错) ---
    def get_stock_data(code):
        # 实时数据
        df_spot = ak.stock_zh_a_spot_em()
        spot = df_spot[df_spot['代码'] == code].iloc[0]
        
        # 历史数据 (K线)
        hist = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")
        
        # 财务指标
        try:
            df_finance = ak.stock_financial_analysis_indicator_em(symbol=code)
            finance = df_finance.iloc[0]
        except:
            finance = {"净资产收益率(%)": "暂无", "净利润同比增长率(%)": "暂无"}
            
        return spot, hist, finance

    # --- 点击按钮后的执行逻辑 ---
    if analyze_btn:
        with st.spinner('AI 正在调取财务数据并分析市场情绪...'):
            try:
                spot, hist, finance = get_stock_data(stock_code)
                
                # 计算简单技术面指标
                last_price = spot['最新价']
                change_pct = spot['涨跌幅']
                
                # 构造给 DeepSeek 的报告需求
                prompt = f"""
                你是一名专业的A股投资顾问。请分析股票：{spot['名称']} ({stock_code})。
                
                【数据概况】
                - 价格：{last_price} ({change_pct}%)
                - 换手率：{spot['换手率']}%，市盈率(动)：{spot['市盈率-动态']}
                - 财务ROE：{finance['净资产收益率(%)']}%，利润同比：{finance['净利润同比增长率(%)']}%

                请严格按以下格式输出分析报告：
                ### 1. 投资决策摘要
                ### 2. 技术指标与趋势分析
                ### 3. 财务与估值评价
                ### 4. 风险评分 (1-10分)
                ### 5. 目标价位 (未来3个月预测)
                """

                # 调用 DeepSeek
                response = client.chat.completions.create(
                    model="deepseek-chat", 
                    messages=[{"role": "user", "content": prompt}]
                )

                # --- 结果显示 ---
                st.success(f"分析完成：{spot['名称']}")
                
                c1, c2 = st.columns([2, 1])
                with c1:
                    st.subheader("近期走势图")
                    st.line_chart(hist.tail(60).set_index('日期')['收盘'])
                with c2:
                    st.subheader("核心指标")
                    st.metric("最新价", f"￥{last_price}", f"{change_pct}%")
                    st.write(f"**成交额:** {spot['成交额']}")
                    st.write(f"**换手率:** {spot['换手率']}%")

                st.divider()
                st.subheader("🤖 DeepSeek AI 分析报告")
                st.markdown(response.choices[0].message.content)

            except Exception as e:
                st.error(f"分析出错：{e}")

