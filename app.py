import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
import time
from datetime import datetime

# --- 1. 页面配置 ---
st.set_page_config(page_title="文哥哥极速终端", page_icon="🚀", layout="wide")

# --- 2. 初始化持久化记忆 ---
if 'ai_cache' not in st.session_state: st.session_state.ai_cache = None
if 'fund_cache' not in st.session_state: st.session_state.fund_cache = None
if 'last_code' not in st.session_state: st.session_state.last_code = ""
if 'auto_refresh' not in st.session_state: st.session_state.auto_refresh = False

# --- 3. 核心取数逻辑 ---
@st.cache_data(ttl=1) # 实时数据缓存设为1秒
def get_stock_realtime(code):
    try:
        # 实时快照
        df_hist = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq").tail(30)
        latest = df_hist.iloc[-1]
        
        # 资金流向
        mkt = "sh" if code.startswith(('6', '9', '688')) else "sz"
        df_fund = ak.stock_individual_fund_flow(stock=code, market=mkt)
        fund = df_fund.iloc[0] if not df_fund.empty else None
        
        return {"success": True, "price": latest['收盘'], "pct": latest['涨跌幅'], "fund": fund, "df": df_hist}
    except:
        return {"success": False}

# --- 4. 四灯算法逻辑 ---
def calculate_four_lamps(data):
    if not data or not data.get('success'):
        return {"trend": "⚪", "money": "⚪", "sentiment": "⚪", "safety": "⚪"}
    df, fund = data['df'], data['fund']
    ma5, ma20 = df['收盘'].tail(5).mean(), df['收盘'].tail(20).mean()
    
    trend = "🟢" if ma5 > ma20 else "🔴"
    money = "🟢" if fund is not None and "-" not in str(fund['主力净流入-净额']) else "🔴"
    sentiment = "🟢" if data['pct'] > 0 else "🔴"
    safety = "🟢" if fund is not None and float(fund['小单净流入-净占比']) < 20 else "🔴"
    
    return {"trend": trend, "money": money, "sentiment": sentiment, "safety": safety}

# --- 5. 安全验证 ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if not st.session_state['logged_in']:
    st.title("🔐 私人终端授权访问")
    pwd = st.text_input("请输入访问密钥", type="password")
    if st.button("开启终端", use_container_width=True):
        if "access_password" in st.secrets and pwd == st.secrets["access_password"]:
            st.session_state['logged_in'] = True
            st.rerun()
    st.stop()

client = OpenAI(api_key=st.secrets["deepseek_api_key"], base_url="https://api.deepseek.com")

# --- 6. 侧边栏 ---
with st.sidebar:
    st.title("🚀 控制中心")
    code = st.text_input("股票代码", value="600519").strip()
    if code != st.session_state.last_code:
        st.session_state.ai_cache = None
        st.session_state.fund_cache = None
        st.session_state.last_code = code
    
    st.divider()
    st.session_state.auto_refresh = st.toggle("⏱️ 开启每秒自动监控", value=st.session_state.auto_refresh)
    if st.button("🔴 退出系统"):
        st.session_state['logged_in'] = False
        st.rerun()

st.title(f"📈 文哥哥 AI 终端: {code}")
tab1, tab2, tab3 = st.tabs(["🧠 AI 深度决策", "🎯 资金追踪雷达", "🕯️ 实时哨兵说明"])

# --- Tab 1 & Tab 2 逻辑保持不变 ---
with tab1:
    if st.button("🚀 启动全维度 AI 建模", use_container_width=True):
        data = get_stock_realtime(code)
        if data["success"]:
            lamps = calculate_four_lamps(data)
            prompt = f"分析股票 {code}。价格:{data['price']}, 四灯:{lamps}。请按5部分分析。"
            response = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}])
            st.session_state.ai_cache = {"content": response.choices[0].message.content, "price": data['price'], "lamps": lamps}
    if st.session_state.ai_cache: st.markdown(st.session_state.ai_cache['content'])

with tab2:
    if st.button("📡 扫描六大板块资金", use_container_width=True):
        st.session_state.fund_cache = get_stock_realtime(code)
    if st.session_state.fund_cache:
        f = st.session_state.fund_cache['fund']
        if f is not None:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("🏢 机构", f['超大单净流入-净额']); c2.metric("🔥 游资", f['大单净流入-净额'])
            c3.metric("🏭 产业", f['主力净流入-净额']); c4.metric("🐣 散户", f['小单净流入-净额'])

# --- Tab 3: 实时监控 (重点更新：自动刷新) ---
with tab3:
    st.subheader("🛡️ 实时四灯监控哨兵")
    
    # 局部刷新容器
    placeholder = st.empty()
    
    # 自动刷新逻辑
    count = 0
    while st.session_state.auto_refresh:
        with placeholder.container():
            real_data = get_stock_realtime(code)
            if real_data["success"]:
                lamps = calculate_four_lamps(real_data)
                f = real_data['fund']
                
                m1, m2, m3 = st.columns(3)
                m1.metric("📌 当前价位", f"¥{real_data['price']}", f"{real_data['pct']}%")
                fund_line = float(f['主力净流入-净占比']) if f is not None else 0
                m2.metric("🌊 核心资金线", f"{fund_line}%", "流入" if fund_line > 0 else "流出")
                m3.metric("🚦 综合灯效", f"{lamps['trend']}{lamps['money']}{lamps['sentiment']}{lamps['safety']}")
                
                l1, l2, l3, l4 = st.columns(4)
                l1.info(f"趋势: {lamps['trend']}"); l2.info(f"资金: {lamps['money']}")
                l3.info(f"情绪: {lamps['sentiment']}"); l4.info(f"安全: {lamps['safety']}")
                
                st.caption(f"🕒 最后更新时间: {datetime.now().strftime('%H:%M:%S')} (自动刷新中)")
            
        time.sleep(1) # 暂停1秒
        if not st.session_state.auto_refresh: break
    
    if not st.session_state.auto_refresh:
        st.warning("⏱️ 自动刷新已关闭。请在侧边栏开启以进行实时监控。")
        if st.button("手动刷新一次"):
            st.rerun()

    st.write("---")
    st.header("📖 四灯算法逻辑说明书")
    st.markdown("1. **趋势灯**: MA5 > MA20 | 2. **资金灯**: 主力净流入 > 0 | 3. **情绪灯**: 价格上涨 | 4. **安全灯**: 散户占比 < 20%")

st.divider()
st.caption("文哥哥专用 | 实时秒级刷新版 | 四灯算法哨兵")
