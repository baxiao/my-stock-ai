import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
import time
from datetime import datetime
import pytz
from concurrent.futures import ThreadPoolExecutor

# --- 1. 基础配置与状态初始化 ---
st.set_page_config(page_title="文哥哥极速终端", page_icon="🚀", layout="wide")

# 一行代码完成所有状态初始化
for k, v in {"ai_cache": None, "last_data": None, "last_code": "", "auto_refresh": False, "logged_in": False}.items():
    st.session_state.setdefault(k, v)

CN_TZ = pytz.timezone('Asia/Shanghai')
# 线程池复用
if "executor" not in st.session_state:
    st.session_state.executor = ThreadPoolExecutor(max_workers=4)

# --- 2. 权限校验 ---
if not st.session_state.logged_in:
    st.title("🔐 文哥哥私人量化授权")
    col_p1, col_p2 = st.columns([3, 1])
    pwd = col_p1.text_input("请输入访问密钥", type="password")
    if col_p2.button("进入系统", use_container_width=True) or (pwd and pwd == st.secrets.get("access_password")):
        if pwd == st.secrets.get("access_password"):
            st.session_state.logged_in = True
            st.rerun()
        else: st.error("密钥无效")
    st.stop()

# 登录后实例化客户端
client = OpenAI(api_key=st.secrets["deepseek_api_key"], base_url="https://api.deepseek.com")

# --- 3. 核心数据处理引擎 ---
def normalize_df(df):
    """列名归一化处理，防止 akshare 列名变动导致报错"""
    if df.empty: return df
    mapping = {'开盘': 'open', '收盘': 'close', '最高': 'high', '最低': 'low', '成交量': 'vol', '成交额': 'amount', '涨跌幅': 'pct'}
    return df.rename(columns=lambda x: mapping.get(x, x))

@st.cache_data(ttl=8) # 缓存8秒，防止高频刷新封IP
def get_realtime_data(code):
    try:
        def fetch_m1(): # 1分钟线实现秒级感知
            return ak.stock_zh_a_hist(symbol=code, period="1", adjust="qfq").tail(60)
        def fetch_fund():
            mkt = "sh" if code.startswith(('6', '9', '688')) else "sz"
            return ak.stock_individual_fund_flow(stock=code, market=mkt)

        f1 = st.session_state.executor.submit(fetch_m1)
        f2 = st.session_state.executor.submit(fetch_fund)
        
        df_h, df_f = normalize_df(f1.result()), f2.result()
        if df_h.empty: return {"success": False, "msg": "空数据"}
        
        return {
            "success": True, "price": df_h.iloc[-1]['close'], "pct": df_h.iloc[-1]['pct'],
            "fund": df_f.iloc[0] if not df_f.empty else None, "df": df_h
        }
    except Exception as e:
        return {"success": False, "msg": str(e)}

def format_unit(val):
    v = float(val)
    return f"{v/100000000:.2f} 亿" if abs(v) >= 100000000 else f"{v/10000:.1f} 万"

# --- 4. 侧边栏控制 ---
with st.sidebar:
    st.title("🚀 指挥部")
    code = st.text_input("股票代码", value="600519").strip()
    if code != st.session_state.last_code:
        st.session_state.update({"last_code": code, "ai_cache": None, "last_data": None})
    
    st.divider()
    stop_p = st.number_input("📉 我的止损价", value=0.0, step=0.01)
    target_p = st.number_input("🎯 我的目标价", value=0.0, step=0.01)
    
    st.divider()
    st.session_state.auto_refresh = st.checkbox("🔄 开启秒级无闪监控", value=st.session_state.auto_refresh)
    if st.button("🔴 安全退出"):
        st.session_state.logged_in = False
        st.rerun()

# --- 5. 主界面布局 ---
t1, t2 = st.tabs(["🧠 AI 策略闭环", "🎯 实时资金雷达"])

with t1:
    if st.button("🚀 启动私募级 AI 建模", use_container_width=True):
        with st.spinner("正在调取多线程算力..."):
            data = get_realtime_data(code)
            if data["success"]:
                prompt = f"""分析股票 {code}。现价 {data['price']}, 止损位 {stop_p}, 目标位 {target_p}。
                请以此给出战术评级、空间分析及操作指令，重点针对止损/目标价给出风险盈亏比建议。"""
                res = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}])
                st.session_state.ai_cache = res.choices[0].message.content
    if st.session_state.ai_cache:
        st.info(st.session_state.ai_cache)

with t2:
    placeholder = st.empty() # 关键：占位符复用防止闪屏
    while True:
        res = get_realtime_data(code)
        data = res if res["success"] else st.session_state.last_data
        if not data: st.warning("等待数据接入..."); break
        
        df, f = data['df'], data['fund']
        ma5, ma20 = df['close'].tail(5).mean(), df['close'].tail(20).mean()
        
        # 修正后的四灯逻辑
        l = {
            "趋势": "🔴" if ma5 > ma20 else "🟢",
            "资金": "🔴" if f is not None and float(f['主力净流入-净额']) > 0 else "🟢",
            "情绪": "🔴" if data['pct'] > 0 else "🟢",
            "安全": "🟢" if f is not None and float(f['小单净流入-净占比']) > 15 else "🔴" # 散户接盘多则危险
        }
        
        with placeholder.container():
            st.caption(f"🕒 {datetime.now(CN_TZ).strftime('%H:%M:%S')} | 秒级分时连通 | 🔴正面 🟢风险")
            c1, c2, c3, c4 = st.columns(4)
            for i, (name, icon) in enumerate(l.items()):
                color = "#ff4b4b" if icon == "🔴" else "#2eb872"
                [c1, c2, c3, c4][i].markdown(f"""<div style="background:rgba({(255,75,75,0.1) if icon=='🔴' else (46,184,114,0.1)}); padding:15px; border-radius:10px; border-top:5px solid {color}; text-align:center;">
                <p style="color:{color}; font-weight:bold; margin:0;">{name}</p><h2>{icon}</h2></div>""", unsafe_allow_html=True)
            
            # 说明表导出
            exp_df = pd.DataFrame({
                "维度": ["趋势", "资金", "情绪", "安全"],
                "红色逻辑": ["多头(MA5>MA20)", "主力大单流入", "股价上涨", "散户离场(安全)"],
                "状态": list(l.values())
            })
            with st.expander("📖 策略说明 & 数据导出"):
                st.dataframe(exp_df, use_container_width=True)
                st.download_button("📥 导出决策快照", exp_df.to_csv().encode('utf-8'), "signal.csv")

            st.divider()
            v1, v2, v3 = st.columns(3)
            v1.metric("📌 当前价", f"¥{data['price']}", f"{data['pct']}%")
            v2.metric("🌊 主力净额", format_unit(f['主力净流入-净额'] if f is not None else 0))
            v3.metric("🎯 目标距离", f"{(target_p - data['price']):.2f}" if target_p > 0 else "--")

            st.write("📊 **6大板块细分 (实时分钟级)**")
            if f is not None:
                r1, r2 = st.columns(3), st.columns(3)
                r1[0].metric("1. 🏢 机构", format_unit(f['超大单净流入-净额']))
                r1[1].metric("2. 🔥 游资", format_unit(f['大单净流入-净额']))
                r1[2].metric("3. 🐂 大户", format_unit(f['中单净流入-净额']))
                r2[0].metric("4. 🤖 量化", "智能监控")
                r2[1].metric("5. 🏭 产业", format_unit(f['主力净流入-净额']))
                r2[2].metric("6. 🐣 散户", f"{f['小单净流入-净占比']}%")
            
            st.line_chart(df.set_index(df.index)['close'], height=200)

        if not st.session_state.auto_refresh: break
        time.sleep(1)

st.divider()
st.caption("文哥哥专用 | 2026-01-18 | 秒级分时实战版")
