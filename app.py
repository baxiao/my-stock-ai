import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
import time
from datetime import datetime

# --- 1. 页面基础配置 ---
st.set_page_config(
    page_title="文哥哥AI金融终端", 
    page_icon="📈", 
    layout="wide",
    initial_sidebar_state="collapsed" 
)

# --- 2. 核心 CSS 注入：自适应美化 ---
st.markdown("""
    <style>
    [data-testid="stMetric"] { background-color: #f8f9fa; padding: 10px; border-radius: 8px; border: 1px solid #e9ecef; }
    @media (max-width: 768px) {
        [data-testid="column"] { width: 100% !important; flex: 1 1 calc(50% - 1rem) !important; min-width: calc(50% - 1rem) !important; }
    }
    .block-container { padding-top: 2rem; padding-left: 1rem; padding-right: 1rem; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. 持久化记忆 (Session State) ---
if 'stock_data' not in st.session_state: st.session_state.stock_data = None
if 'ai_report' not in st.session_state: st.session_state.ai_report = None
if 'last_code' not in st.session_state: st.session_state.last_code = ""

# --- 4. 安全验证 ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.title("🔐 私人终端授权访问")
    if "access_password" in st.secrets:
        pwd_input = st.text_input("请输入访问密钥", type="password")
        if st.button("验证并进入", use_container_width=True):
            if pwd_input == st.secrets["access_password"]:
                st.session_state['logged_in'] = True
                st.rerun()
            else:
                st.error("密钥错误")
    else:
        st.error("⚠️ 缺少 Secrets 配置")
    st.stop()

# --- 5. 核心 API 初始化 ---
client = OpenAI(api_key=st.secrets["deepseek_api_key"], base_url="https://api.deepseek.com")

# --- 6. 辅助工具：获取真正实时的价格 ---
def get_realtime_data(code):
    # 调取东财实时快照接口
    df_spot = ak.stock_zh_a_spot_em()
    target = df_spot[df_spot['代码'] == code]
    if not target.empty:
        return target.iloc[0]
    return None

# --- 7. 主程序界面 ---
st.title("🚀 文哥哥 AI 决策终端")

with st.sidebar:
    st.header("🔍 配置中心")
    raw_code = st.text_input("📍 股票代码", value="600519").strip()
    time_span = st.select_slider("⏳ 分析跨度", options=["近一周", "近一月", "近三月", "近半年", "近一年"], value="近三月")
    
    if raw_code != st.session_state.last_code:
        st.session_state.stock_data = None
        st.session_state.ai_report = None
        st.session_state.last_code = raw_code

    st.divider()
    if st.button("🔴 安全退出", use_container_width=True):
        st.session_state['logged_in'] = False
        st.rerun()

tab1, tab2 = st.tabs(["🧠 DeepSeek 深度决策", "🎯 主力追踪雷达"])

# --- Tab 1: AI 分析 ---
with tab1:
    if st.button("🚀 启动 AI 建模分析", use_container_width=True):
        p_bar = st.progress(0)
        status_text = st.empty()
        try:
            status_text.text("📡 正在截获交易所实时秒级行情...")
            spot_data = get_realtime_data(raw_code)
            p_bar.progress(30)
            
            if spot_data is None:
                st.error("无法获取该股票实时数据，请确认代码是否正确。")
            else:
                status_text.text("🧠 正在同步 K 线走势...")
                # 依然需要历史数据看趋势
                df_hist = ak.stock_zh_a_hist(symbol=raw_code, period="daily", adjust="qfq").tail(60)
                p_bar.progress(60)
                
                status_text.text("🧠 DeepSeek 基于最新价建模中...")
                # 强制把最新实时价塞给AI
                prompt = f"""
                当前时刻：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                股票：{spot_data['名称']} ({raw_code})
                【绝对最新价】：{spot_data['最新价']} 元
                今日涨跌幅：{spot_data['涨跌幅']}%
                今日成交额：{spot_data['成交额']/1e8:.2f} 亿
                
                请结合以上【实时数据】及近期趋势，给出分析：
                1.【建议决策】：明确给出【建议购入】、【建议出手】或【暂时观望】。
                2.【目标预测】：未来3个月的目标价格区间。
                3.【空间分析】：最新的核心支撑位和压力位。
                4.【趋势总结】：简述当前强弱状态。
                """
                
                response = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}])
                st.session_state.ai_report = {
                    "content": response.choices[0].message.content,
                    "date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "price": spot_data['最新价']
                }
                p_bar.progress(100)
                time.sleep(0.5)
                p_bar.empty()
                status_text.empty()
        except Exception as e:
            st.error(f"AI 分析失败: {e}")

    if st.session_state.ai_report:
        rep = st.session_state.ai_report
        st.subheader(f"📋 AI 研报 (实时价: ¥{rep['price']})")
        st.caption(f"分析时间: {rep['date']}")
        st.info(rep['content'])
        st.code(rep['content'], language="markdown")
    else:
        st.info("💡 请点击上方按钮，基于最新价进行 AI 决策")

# --- Tab 2: 主力追踪 ---
with tab2:
    if st.button("📡 执行主力扫描", use_container_width=True):
        p_bar = st.progress(0)
        status_text = st.empty()
        try:
            status_text.text("📡 调取实时快照...")
            spot_data = get_realtime_data(raw_code)
            p_bar.progress(50)
            
            status_text.text("📡 同步资金流向...")
            mkt = "sh" if raw_code.startswith(('6', '9', '688')) else "sz"
            df_fund = ak.stock_individual_fund_flow(stock=raw_code, market=mkt)
            latest_fund = df_fund.iloc[0] if not df_fund.empty else None
            p_bar.progress(90)
            
            st.session_state.stock_data = {
                "name": spot_data['名称'],
                "price": spot_data['最新价'],
                "pct": spot_data['涨跌幅'],
                "amount": spot_data['成交额'],
                "fund": latest_fund,
                "date": datetime.now().strftime('%H:%M:%S')
            }
            p_bar.progress(100)
            time.sleep(0.5)
            p_bar.empty()
            status_text.empty()
        except Exception as e:
            st.error(f"主力扫描失败: {e}")

    if st.session_state.stock_data:
        sd = st.session_state.stock_data
        st.subheader(f"📊 {sd['name']} 实时雷达 ({sd['date']})")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("秒级最新价", f"¥{sd['price']}", f"{sd['pct']}%")
        c2.metric("当前成交额", f"{sd['amount']/1e8:.2f}亿")
        if sd['fund'] is not None:
            c3.metric("主力流入", f"{sd['fund']['主力净流入-净额']}")
            c4.metric("资金净占比", f"{sd['fund']['主力净流入-净占比']}%")
        
        # 补一个简单的走势辅助
        df_hist = ak.stock_zh_a_hist(symbol=raw_code, period="daily", adjust="qfq").tail(20)
        st.line_chart(df_hist.set_index('日期')['收盘'], use_container_width=True)
    else:
        st.info("💡 请点击按钮扫描实时主力资金")

st.divider()
st.caption("文哥哥 AI 终端 | 已接入实时秒级行情接口")
