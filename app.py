import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
import time
from datetime import datetime
import pytz
from concurrent.futures import ThreadPoolExecutor

# --- 1. 状态深度初始化 ---
st.set_page_config(page_title="文哥哥极速终端", page_icon="🚀", layout="wide")

# 一行搞定所有 session 状态
for k, v in {
    'ai_cache': None, 'last_data': None, 'last_code': "", 
    'auto_refresh': False, 'logged_in': False, 'executor': ThreadPoolExecutor(max_workers=4)
}.items():
    st.session_state.setdefault(k, v)

CN_TZ = pytz.timezone('Asia/Shanghai')

# --- 2. 权限与密钥逻辑 ---
if not st.session_state.logged_in:
    st.title("🔐 文哥哥私人量化授权")
    pwd = st.text_input("请输入访问密钥", type="password")
    if st.button("开启终端", use_container_width=True):
        if pwd == st.secrets.get("access_password"):
            st.session_state.logged_in = True
            st.rerun()
        else: st.error("密钥无效")
    st.stop()

# 登录成功后实例化，避免重复连接
client = OpenAI(api_key=st.secrets["deepseek_api_key"], base_url="https://api.deepseek.com")

# --- 3. 高效数据引擎 (含列名归一化与缓存) ---
def normalize_columns(df):
    if df.empty: return df
    # 统一 akshare 不同接口的列名差异
    cols = {'开盘': 'open', '收盘': 'close', '最高': 'high', '最低': 'low', '成交量': 'vol', '成交额': 'amount', '涨跌幅': 'pct'}
    return df.rename(columns=lambda x: cols.get(x, x))

@st.cache_data(ttl=8) # 8秒缓存，兼顾实时性与防封IP
def get_clean_data(code):
    try:
        # 并发获取 1 分钟线(秒级感知)与资金流
        f_h = st.session_state.executor.submit(lambda: ak.stock_zh_a_hist(symbol=code, period="1", adjust="qfq").tail(60))
        f_f = st.session_state.executor.submit(lambda: ak.stock_individual_fund_flow(stock=code, market="sh" if code.startswith(('6', '9', '688')) else "sz"))
        
        df_h = normalize_columns(f_h.result())
        df_f = f_f.result()
        
        if df_h.empty: return {"success": False, "msg": "无效代码"}
        return {
            "success": True, "price": df_h.iloc[-1]['close'], "pct": df_h.iloc[-1]['pct'],
            "fund": df_f.iloc[0] if not df_f.empty else None, "df": df_h
        }
    except Exception as e: return {"success": False, "msg": str(e)}

def format_unit(val):
    v = float(val or 0)
    return f"{v/100000000:.2f} 亿" if abs(v) >= 100000000 else f"{v/10000:.1f} 万"

# --- 4. 侧边栏交互 ---
with st.sidebar:
    st.title("🚀 指挥部")
    code = st.text_input("股票代码", value="600519").strip()
    if code != st.session_state.last_code:
        st.session_state.update({'last_code': code, 'ai_cache': None, 'last_data': None})
    
    st.divider()
    stop_p = st.number_input("📉 止损预警价", value=0.0)
    target_p = st.number_input("🎯 目标止盈价", value=0.0)
    
    st.divider()
    st.session_state.auto_refresh = st.checkbox("🔄 开启秒级无闪监控", value=st.session_state.auto_refresh)
    if st.button("🔴 退出系统"):
        st.session_state.logged_in = False
        st.rerun()

# --- 5. 主界面渲染 ---
st.title(f"📈 文哥哥 AI 终端: {code}")
t1, t2 = st.tabs(["🧠 AI 策略建议", "🎯 实时资金雷达"])

with t1:
    if st.button("🚀 启动全维度 AI 建模", use_container_width=True):
        with st.spinner("正在分析多线程量化数据..."):
            data = get_clean_data(code)
            if data["success"]:
                # 强化提示词：引入止损/目标价博弈
                prompt = f"分析股票 {code}。现价 {data['price']}, 止损位 {stop_p}, 目标位 {target_p}。请以私募总监身份输出：战术评级、核心理由、风险盈亏比分析、及实战锦囊。"
                res = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}])
                st.session_state.ai_cache = res.choices[0].message.content
    if st.session_state.ai_cache:
        st.info(st.session_state.ai_cache)

with t2:
    monitor_node = st.empty()
    while True:
        res = get_clean_data(code)
        data = res if res["success"] else st.session_state.last_data
        if not data: st.warning("数据接入中..."); break
        
        df, f = data['df'], data['fund']
        ma5, ma20 = df['close'].tail(5).mean(), df['close'].tail(20).mean()
        
        # 核心：修正后的四灯逻辑
        lamps = {
            "趋势形态": "🔴" if ma5 > ma20 else "🟢",
            "主力动向": "🔴" if f is not None and float(f['主力净流入-净额']) > 0 else "🟢",
            "市场情绪": "🔴" if data['pct'] > 0 else "🟢",
            "安全保障": "🔴" if f is not None and float(f['小单净流入-净占比']) < 15 else "🟢" # 散户少才红/安全
        }
        
        with monitor_node.container():
            st.caption(f"🕒 {datetime.now(CN_TZ).strftime('%H:%M:%S')} | 秒级监控中 | 🔴正面 🟢风险")
            
            # --- 四灯显示 ---
            cols = st.columns(4)
            d_list = [("多头走强", "重心下移"), ("主力净买", "主力撤离"), ("买盘活跃", "信心受阻"), ("机构控盘", "散户接盘")]
            for i, (name, icon) in enumerate(lamps.items()):
                color = "#ff4b4b" if icon == "🔴" else "#2eb872"
                bg = "rgba(255, 75, 75, 0.05)" if icon == "🔴" else "rgba(46, 184, 114, 0.05)"
                cols[i].markdown(f"""<div style="background:{bg}; padding:15px; border-radius:10px; border-top:5px solid {color}; text-align:center;">
                <p style="color:{color}; font-weight:bold; margin:0;">{name}</p><h2>{icon}</h2><p style="font-size:11px; color:{color};">{d_list[i][0] if icon=='🔴' else d_list[i][1]}</p></div>""", unsafe_allow_html=True)
            
            # --- 资金详情 ---
            st.divider()
            m1, m2, m3 = st.columns(3)
            m1.metric("📌 当前价", f"¥{data['price']}", f"{data['pct']}%")
            m2.metric("🌊 主力净额", format_unit(f['主力净流入-净额'] if f is not None else 0))
            m3.metric("🎯 目标余量", f"{(target_p - data['price']):.2f}" if target_p > 0 else "--")
            
            if f is not None:
                r1 = st.columns(3); r2 = st.columns(3)
                r1[0].metric("1. 🏢 机构", format_unit(f['超大单净流入-净额']))
                r1[1].metric("2. 🔥 游资", format_unit(f['大单净流入-净额']))
                r1[2].metric("3. 🐂 大户", format_unit(f['中单净流入-净额']))
                r2[0].metric("4. 🤖 量化", "实时监控中")
                r2[1].metric("5. 🏭 产业", format_unit(f['主力净流入-净额']))
                r2[2].metric("6. 🐣 散户占比", f"{f['小单净流入-净占比']}%")

            # --- 逻辑说明与图表 ---
            with st.expander("🛡️ 终端量化逻辑解析 (可点击展开)"):
                st.markdown("""
                - **趋势**：🔴(MA5>MA20) 代表波段强势；🟢(MA5<MA20) 代表下跌惯性。
                - **资金**：🔴 代表主力大单真金白银买入；🟢 代表主力正在撤离。
                - **安全**：🔴 代表散户接盘少，筹码集中；🟢 代表散户疯抢，易爆跌。
                """)
            
            
            st.line_chart(df.set_index(df.index)['close'], height=200)

        if not st.session_state.auto_refresh: break
        time.sleep(1)

st.divider()
st.caption("文哥哥专用终端 | 2026.01.18 修正母版 | 序号居中")
