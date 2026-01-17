import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
import time
from datetime import datetime
import pytz
from concurrent.futures import ThreadPoolExecutor

# --- 1. 页面配置 ---
st.set_page_config(page_title="文哥哥极速终端", page_icon="🚀", layout="wide")

# --- 2. 密钥检测 ---
if "deepseek_api_key" not in st.secrets or "access_password" not in st.secrets:
    st.error("❌ 密钥未配置！请在 Streamlit Settings -> Secrets 中添加。")
    st.stop()

# --- 3. 状态初始化 ---
if 'ai_cache' not in st.session_state: st.session_state.ai_cache = None
if 'last_data' not in st.session_state: st.session_state.last_data = None
if 'last_code' not in st.session_state: st.session_state.last_code = ""
if 'auto_refresh' not in st.session_state: st.session_state.auto_refresh = False

CN_TZ = pytz.timezone('Asia/Shanghai')

# --- 4. 辅助函数 ---
def format_money(value_str):
    try:
        val = float(value_str)
        abs_val = abs(val)
        if abs_val >= 100000000:
            return f"{val / 100000000:.2f} 亿"
        else:
            return f"{val / 10000:.1f} 万"
    except:
        return "N/A"

# --- 5. 并发数据引擎 ---
def fetch_hist(code):
    try: return ak.stock_zh_a_hist(symbol=code, period="1", adjust="qfq").tail(30)
    except: return pd.DataFrame()

def fetch_fund(code):
    try:
        mkt = "sh" if code.startswith(('6', '9', '688')) else "sz"
        return ak.stock_individual_fund_flow(stock=code, market=mkt)
    except: return pd.DataFrame()

@st.cache_data(ttl=2)
def get_stock_data_parallel(code):
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            f_hist = executor.submit(fetch_hist, code)
            f_fund = executor.submit(fetch_fund, code)
            df_hist, df_fund = f_hist.result(), f_fund.result()
        if df_hist.empty: return {"success": False, "msg": "无效代码"}
        return {"success": True, "price": df_hist.iloc[-1]['收盘'], "pct": df_hist.iloc[-1]['涨跌幅'], "fund": df_fund.iloc[0] if not df_fund.empty else None, "df": df_hist}
    except Exception as e: return {"success": False, "msg": str(e)}

# --- 6. 四灯逻辑算法 ---
def calculate_four_lamps(data):
    if not data or not data.get('success'): return {"trend": "⚪", "money": "⚪", "sentiment": "⚪", "safety": "⚪"}
    df, fund = data['df'], data['fund']
    ma5, ma20 = df['收盘'].tail(5).mean(), df['收盘'].tail(20).mean()
    l = {
        "trend": "🔴" if ma5 > ma20 else "🟢",
        "money": "🔴" if fund is not None and "-" not in str(fund['主力净流入-净额']) else "🟢",
        "sentiment": "🔴" if data['pct'] > 0 else "🟢",
        "safety": "🔴" if fund is not None and float(fund['小单净流入-净占比']) < 15 else "🟢"
    }
    return l

# --- 7. 登录控制 ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if not st.session_state['logged_in']:
    st.title("🔐 文哥哥私人终端")
    pwd = st.text_input("访问密钥", type="password")
    if st.button("开启终端", use_container_width=True):
        if pwd == st.secrets["access_password"]: st.session_state['logged_in'] = True; st.rerun()
        else: st.error("密钥错误")
    st.stop()

client = OpenAI(api_key=st.secrets["deepseek_api_key"], base_url="https://api.deepseek.com")

# --- 8. 侧边栏 ---
with st.sidebar:
    st.title("🚀 控制中心")
    code = st.text_input("股票代码", value="002510").strip()
    if code != st.session_state.last_code:
        st.session_state.last_code, st.session_state.ai_cache, st.session_state.last_data = code, None, None
    st.divider()
    st.session_state.auto_refresh = st.checkbox("🔄 秒级无闪刷新", value=st.session_state.auto_refresh)
    if st.button("🔴 退出系统"): st.session_state['logged_in'] = False; st.rerun()

st.title(f"📈 文哥哥 AI 终端: {code}")
t1, t2 = st.tabs(["🧠 AI 深度决策", "🎯 实时资金雷达"])

# --- Tab 1: AI 深度决策 ---
with t1:
    if st.button("🚀 启动全维度 AI 建模", use_container_width=True):
        p_bar = st.progress(0, text="深度建模分析中...")
        for p in range(0, 101, 10): time.sleep(0.05); p_bar.progress(p)
        data = get_stock_data_parallel(code)
        if data["success"]:
            l = calculate_four_lamps(data)
            prompt = f"分析股票 {code}。价格 {data['price']}, 四灯 {l}。请以私募总监身份输出：1.战术评级(全线进攻/逢高撤退/空仓)；2.核心理由；3.博弈位(支撑/压力)；4.文哥哥锦囊(一句话干货)。"
            res = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}])
            st.session_state.ai_cache = {"content": res.choices[0].message.content}
            p_bar.empty()
    if st.session_state.ai_cache: 
        st.markdown("### 🏹 实战指令")
        st.info(st.session_state.ai_cache['content'])

# --- Tab 2: 实时资金雷达 (含四灯详细说明) ---
with t2:
    placeholder = st.empty()
    def render():
        res = get_stock_data_parallel(code)
        if not res["success"] and st.session_state.last_data: data, tag = st.session_state.last_data, "⚠️ 断流保护"
        elif res["success"]: data = st.session_state.last_data = res; tag = "🟢 实时连通"
        else: placeholder.warning("连接中..."); return
        
        f, l = data['fund'], calculate_four_lamps(data)
        
        with placeholder.container():
     