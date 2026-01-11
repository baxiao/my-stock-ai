import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
import time

# --- 1. 页面基础配置 ---
st.set_page_config(
    page_title="文哥哥AI金融终端", 
    page_icon="📈", 
    layout="wide"
)

# 自定义美化样式
st.markdown("""
    <style>
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .report-box { background-color: #ffffff; padding: 25px; border-radius: 15px; border: 1px solid #e0e0e0; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 安全门禁系统 (Session State) ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

# 身份验证逻辑
if not st.session_state['logged_in']:
    st.title("🛡️ 私人金融终端 - 身份验证")
    
    # 从 Secrets 中获取预设密码
    if "access_password" in st.secrets:
        correct_password = st.secrets["access_password"]
        
        col_login, _ = st.columns([1, 1])
        with col_login:
            pwd_input = st.text_input("请输入访问授权码：", type="password")
            if st.button("验证并进入系统"):
                if pwd_input == correct_password:
                    st.session_state['logged_in'] = True
                    st.success("验证成功！欢迎回来，文哥哥。")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("授权码错误，请重新输入。")
    else:
        st.warning("⚠️ 安全提醒：请先在 Streamlit 后台 Secrets 中设置 access_password")
    
    st.stop() # 未通过验证则停止执行后续代码

# --- 3. 核心引擎加载 (验证通过后执行) ---
if "deepseek_api_key" in st.secrets:
    client = OpenAI(
        api_key=st.secrets["deepseek_api_key"], 
        base_url="https://api.deepseek.com"
    )
else:
    st.error("🔑 错误：未在 Secrets 中检测到 deepseek_api_key")
    st.stop()

# --- 4. 主界面布局 ---
st.title("🛡️ 文哥哥 A股 AI 智能情报站")

# 侧边栏
with st.sidebar:
    st.header("系统状态")
    st.success("✅ 授权访问中")
    stock_code = st.text_input("📍 输入股票代码", value="600519", max_chars=6)
    st.divider()
    if st.button("🔴 安全退出系统"):
        st.session_state['logged_in'] = False
        st.rerun()

# 功能标签页
tab1, tab2 = st.tabs(["🔥 资金行情监控", "🧠 AI 深度决策分析"])

# --- 功能一：行情与主力监控 ---
with tab1:
    if st.button("📡 开始扫描实时行情"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            status_text.text("正在调取交易所行情...")
            df_all = ak.stock_zh_a_spot_em()
            target = df_all[df_all['代码'] == stock_code].iloc[0]
            progress_bar.progress(100)
            status_text.text("✅ 数据获取成功")
            
            st.subheader(f"📊 {target['名称']} ({stock_code}) 核心指标")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("最新价", f"¥{target['最新价']}", f"{target['涨跌幅']}%")
            m2.metric("成交额", target['成交额'])
            m3.metric("换手率", f"{target['换手率']}%")
            m4.metric("市盈率(动)", target['市盈率-动态'])
            
            # AI 简评主力
            prompt_fund = f"分析股票{target['名称']}：现价{target['最新价']}，换手率{target['换手率']}%。判断主力是在吸筹还是派发？用一句话总结。"
            res_fund = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt_fund}])
            st.info(f"🤖 **主力意图预判：** {res_fund.choices[0].message.content}")

        except Exception as e:
            st.error(f"行情数据获取超时，请稍后重试。")
        finally:
            time.sleep(1)
            progress_bar.empty()
            status_text.empty()

# --- 功能二：AI 深度决策 ---
with tab2:
    if st.button("🚀 生成 AI 投研决策书"):
        progress_bar = st.progress(0)
        try:
            st.write("正在连接 DeepSeek 智算中心进行多维度建模...")
            # 模拟进度感
            for i in range(1, 100, 20):
                progress_bar.progress(i)
                time.sleep(0.2)
            
            # 调用 AI 深度分析
            prompt_ai = f"""
            你是一名专业的A股首席分析师。请针对代码 {stock_code} 给出决策分析：
            1. 主力目前是否在场？
            2. 明确给出【建议购入】、【建议出手】或【暂时观望】。
            3. 未来3个月的目标价格是多少？
            4. 核心的支撑位和压力位在哪里？
            """
            
            response = client.chat.completions.create(
                model="deepseek-chat", 
                messages=[{"role": "user", "content": prompt_ai}]
            )
            
            progress_bar.progress(100)
            st.divider()
            st.subheader(f"📋 {stock_code} 深度决策报告")
            st.markdown(f'<div class="report-box">{response.choices[0].message.content}</div>', unsafe_allow_html=True)
            
        except Exception as e:
            st.error(f"AI 决策引擎繁忙: {e}")
        finally:
            time.sleep(1)
            progress_bar.empty()

st.divider()
st.caption("风险提示：本程序提供的所有信息仅供 AI 实验参考，不构成任何投资建议。")
