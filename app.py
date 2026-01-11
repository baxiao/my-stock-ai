import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
import time

# --- 1. 极速页面配置 ---
st.set_page_config(page_title="文哥哥极速终端", page_icon="🚀", layout="wide")

# 强制清理 CSS 冗余
st.markdown("<style>.block-container {padding-top: 1rem;}</style>", unsafe_allow_html=True)

# --- 2. 状态持久化 ---
if 'res' not in st.session_state: st.session_state.res = None
if 'ai' not in st.session_state: st.session_state.ai = None

# --- 3. 安全验证 ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    pwd = st.text_input("密钥", type="password")
    if st.button("进入"):
        if pwd == st.secrets["access_password"]:
            st.session_state['logged_in'] = True
            st.rerun()
    st.stop()

# --- 4. API 初始化 ---
client = OpenAI(api_key=st.secrets["deepseek_api_key"], base_url="https://api.deepseek.com")

# --- 5. 极速取数逻辑 (单股精准抓取) ---
def get_data_fast(code):
    # 只取单股信息，不抓全量表，防止进程堆积
    info = ak.stock_individual_info_em(symbol=code)
    # 提取关键值
    name = info[info['item'] == '股票名称']['value'].values[0]
    price = info[info['item'] == '最新价']['value'].values[0]
    pct = info[info['item'] == '当日涨跌幅']['value'].values[0]
    
    # 单股资金流
    mkt = "sh" if code.startswith(('6', '9', '688')) else "sz"
    fund = ak.stock_individual_fund_flow(stock=code, market=mkt).iloc[0]
    return {"name": name, "price": price, "pct": pct, "fund": fund}

# --- 6. 界面 ---
st.title("🚀 文哥哥极速终端")

code = st.sidebar.text_input("代码", value="600519").strip()

tab1, tab2 = st.tabs(["🧠 AI 决策", "🎯 主力"])

# --- Tab 1: AI 决策 (极致压缩速度) ---
with tab1:
    if st.button("🚀 极速分析", use_container_width=True):
        with st.status("秒杀查询中...", expanded=True) as s:
            try:
                data = get_data_fast(code)
                s.write("📡 数据已就绪，调取 AI...")
                
                # 极致压缩 Prompt 缩短 AI 思考时间
                p = f"{data['name']}({code})现价:{data['price']},涨幅:{data['pct']}%。1.结论(买/卖/停) 2.压力位 3.核心理由。50字内。"
                
                resp = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[{"role": "user", "content": p}],
                    max_tokens=150,
                    temperature=0.5 # 降低随机性，提高生成速度
                )
                st.session_state.ai = resp.choices[0].message.content
                st.session_state.res = data
                s.update(label="✅ 完成", state="complete")
            except Exception as e:
                st.error(f"失败: {e}")

    if st.session_state.ai:
        st.success(f"**{st.session_state.res['name']}** 最新价: {st.session_state.res['price']}")
        st.write(st.session_state.ai)
        st.code(st.session_state.ai)

# --- Tab 2: 主力进场 (一眼辨别) ---
with tab2:
    if st.button("📡 扫描主力", use_container_width=True):
        with st.spinner("秒抓资金..."):
            st.session_state.res = get_data_fast(code)
    
    if st.session_state.res:
        r = st.session_state.res
        f = r['fund']
        inflow = float(str(f['主力净流入-净额']).replace('万','')) if f is not None else 0
        
        # 极简状态灯
        if inflow > 0:
            st.error(f"🔴 主力净流入: {f['主力净流入-净额']} (正在抢筹)")
        else:
            st.success(f"🟢 主力净流入: {f['主力净流入-净额']} (正在洗盘/离场)")
            
        c1, c2 = st.columns(2)
        c1.metric("价格", f"¥{r['price']}", f"{r['pct']}%")
        c2.metric("主力占比", f"{f['主力净流入-净占比']}%")
    else:
        st.info("点按钮抓取实时主力")

st.divider()
st.caption("文哥哥专用 | 已优化单进程精准模式")
