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
    try: return ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq").tail(30)
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

# --- 6. 四灯逻辑 ---
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

# --- 7. 登录 ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if not st.session_state['logged_in']:
    st.title("🔐 文哥哥私人终端")
    pwd = st.text_input("访问密钥", type="password")
    if st.button("开启", use_container_width=True):
        if pwd == st.secrets["access_password"]: st.session_state['logged_in'] = True; st.rerun()
        else: st.error("密钥错误")
    st.stop()

client = OpenAI(api_key=st.secrets["deepseek_api_key"], base_url="https://api.deepseek.com")

# --- 8. 界面逻辑 ---
with st.sidebar:
    st.title("🚀 控制中心")
    code = st.text_input("代码", value="600519").strip()
    if code != st.session_state.last_code:
        st.session_state.last_code, st.session_state.ai_cache, st.session_state.last_data = code, None, None
    st.session_state.auto_refresh = st.checkbox("🔄 秒级无闪刷新", value=st.session_state.auto_refresh)
    if st.button("🔴 退出系统"): st.session_state['logged_in'] = False; st.rerun()

st.title(f"📈 文哥哥 AI 终端: {code}")
t1, t2, t3 = st.tabs(["🧠 AI 深度决策", "🎯 实时资金雷达", "📜 文哥哥·私募心法"])

with t1:
    if st.button("🚀 启动全维度 AI 建模", use_container_width=True):
        p_bar = st.progress(0, text="多线程并发建模中...")
        for p in range(0, 101, 10): time.sleep(0.05); p_bar.progress(p)
        data = get_stock_data_parallel(code)
        if data["success"]:
            l = calculate_four_lamps(data)
            prompt = f"分析股票 {code}。价格 {data['price']}, 四灯 {l}。请以私募总监身份输出：1.战术评级(全线进攻/逢高撤退/空仓)；2.核心理由；3.博弈位(支撑/压力)；4.文哥哥锦囊(一句话干货)。"
            res = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}])
            st.session_state.ai_cache = {"content": res.choices[0].message.content}
            p_bar.empty()
    if st.session_state.ai_cache: st.info(st.session_state.ai_cache['content'])

with t2:
    placeholder = st.empty()
    def render():
        res = get_stock_data_parallel(code)
        if not res["success"] and st.session_state.last_data: data, tag = st.session_state.last_data, "⚠️ 延迟"
        elif res["success"]: data = st.session_state.last_data = res; tag = "🟢 实时"
        else: placeholder.warning("连接中..."); return
        f, l = data['fund'], calculate_four_lamps(data)
        with placeholder.container():
            st.caption(f"🕒 {datetime.now(CN_TZ).strftime('%H:%M:%S')} | {tag} | 🔴正面 🟢风险")
            st.write("### 🚦 核心策略哨兵")
            cols = st.columns(4)
            t_list = ["趋势形态", "主力动向", "市场情绪", "筹码安全"]
            k_list = ["trend", "money", "sentiment", "safety"]
            d_list = [("顺势多头", "重心下移"), ("主力流入", "资金流出"), ("买盘活跃", "信心不足"), ("锁定良好", "散户接盘")]
            for i, col in enumerate(cols):
                status = l[k_list[i]]
                color = "#ff4b4b" if status == "🔴" else "#2eb872"
                bg = "rgba(255, 75, 75, 0.1)" if status == "🔴" else "rgba(46, 184, 114, 0.1)"
                col.markdown(f'<div style="background-color:{bg}; padding:15px; border-radius:12px; border-top: 5px solid {color}; text-align:center;"><p style="margin:0; color:{color}; font-weight:bold;">{t_list[i]}</p><h2 style="margin:8px 0;">{status}</h2><p style="margin:0; color:{color}; font-size:11px;">{d_list[i][0] if status=="🔴" else d_list[i][1]}</p></div>', unsafe_allow_html=True)
            st.divider()
            m1, m2 = st.columns(2)
            m1.metric("📌 当前价位", f"¥{data['price']}", f"{data['pct']}%")
            main_f = f['主力净流入-净额'] if f is not None else 0
            m2.metric("🌊 主力净额", format_money(main_f), "流入" if float(main_f) > 0 else "流出")
            if f is not None:
                r1, r2 = st.columns(3), st.columns(3)
                r1[0].metric("1. 🏢 机构", format_money(f['超大单净流入-净额']))
                r1[1].metric("2. 🔥 游资", format_money(f['大单净流入-净额']))
                r1[2].metric("3. 🐂 大户", format_money(f['中单净流入-净额']))
                r2[0].metric("4. 🤖 量化", "智能监控")
                r2[1].metric("5. 🏭 产业", format_money(f['主力净流入-净额']))
                r2[2].metric("6. 🐣 散户", f"{float(f['小单净流入-净占比']):.1f} %")
            st.line_chart(data['df'].set_index('日期')['收盘'], height=200)

    if st.session_state.auto_refresh:
        while st.session_state.auto_refresh: render(); time.sleep(1)
    else: render()

with t3:
    st.markdown("## 📜 文哥哥·私募心法")
    
    st.info("💡 视觉核心：遵循 A 股特色，🔴 红色代表强度与机会，🟢 绿色代表走弱与风险。")
    st.success("🛡️ **文哥哥提醒：只做红灯共振的机会，坚决执行止损绿灯。**")
