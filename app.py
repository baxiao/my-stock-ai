import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
import time
from datetime import datetime
import pytz

# --- 1. 页面基本配置 ---
st.set_page_config(page_title="文哥哥极速终端", page_icon="🚀", layout="wide")

# --- 2. 初始化持久化状态 ---
if 'ai_cache' not in st.session_state: st.session_state.ai_cache = None
if 'last_code' not in st.session_state: st.session_state.last_code = ""
if 'auto_refresh' not in st.session_state: st.session_state.auto_refresh = False

# 强制中国时区
CN_TZ = pytz.timezone('Asia/Shanghai')

# --- 3. 核心数据引擎 ---
@st.cache_data(ttl=1)
def get_stock_all_data(code):
    try:
        # 基础行情数据
        df_hist = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq").tail(30)
        if df_hist.empty: return {"success": False, "msg": "未找到代码"}
        latest = df_hist.iloc[-1]
        
        # 资金流向数据
        fund = None
        try:
            mkt = "sh" if code.startswith(('6', '9', '688')) else "sz"
            df_fund = ak.stock_individual_fund_flow(stock=code, market=mkt)
            if not df_fund.empty: fund = df_fund.iloc[0]
        except: pass 
            
        return {
            "success": True, "price": latest['收盘'], "pct": latest['涨跌幅'],
            "vol": latest['成交额'], "fund": fund, "df": df_hist
        }
    except Exception as e:
        return {"success": False, "msg": str(e)}

# --- 4. 四灯算法逻辑 (红色正面🔴, 绿色负面🟢) ---
def calculate_four_lamps(data):
    if not data or not data.get('success'):
        return {"trend": "⚪", "money": "⚪", "sentiment": "⚪", "safety": "⚪"}
    df = data['df']
    fund = data['fund']
    ma5 = df['收盘'].tail(5).mean()
    ma20 = df['收盘'].tail(20).mean()
    
    # 趋势灯：MA5 > MA20 为强
    trend_lamp = "🔴" if ma5 > ma20 else "🟢"
    # 资金灯：主力净流入为强
    money_lamp = "🟢"
    if fund is not None:
        if "-" not in str(fund['主力净流入-净额']): money_lamp = "🔴"
    # 情绪灯：当日上涨为强
    sentiment_lamp = "🔴" if data['pct'] > 0 else "🟢"
    # 安全灯：散户占比低（筹码集中）为强
    safety_lamp = "🟢"
    if fund is not None:
        if float(fund['小单净流入-净占比']) < 20: safety_lamp = "🔴"
            
    return {"trend": trend_lamp, "money": money_lamp, "sentiment": sentiment_lamp, "safety": safety_lamp}

# --- 5. 权限安全验证 ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.title("🔐 私人终端授权访问")
    # 此处遵循要求，通过 secrets 管理密码
    pwd = st.text_input("请输入访问密钥", type="password")
    if st.button("开启终端", use_container_width=True):
        if "access_password" in st.secrets and pwd == st.secrets["access_password"]:
            st.session_state['logged_in'] = True
            st.rerun()
        else:
            st.error("密钥无效")
    st.stop()

# DeepSeek 客户端初始化
client = OpenAI(api_key=st.secrets["deepseek_api_key"], base_url="https://api.deepseek.com")

# --- 6. 侧边栏控制面板 ---
with st.sidebar:
    st.title("🚀 控制中心")
    code = st.text_input("股票代码", value="600519").strip()
    if code != st.session_state.last_code:
        st.session_state.ai_cache = None
        st.session_state.last_code = code
    
    st.divider()
    st.session_state.auto_refresh = st.checkbox("🔄 开启秒级实时刷新", value=st.session_state.auto_refresh)
    
    st.divider()
    if st.button("🔴 退出系统"):
        st.session_state['logged_in'] = False
        st.rerun()

st.title(f"📈 文哥哥 AI 终端: {code}")
tab1, tab2, tab3 = st.tabs(["🧠 AI 深度决策", "🎯 实时资金雷达", "📜 文哥哥·私募心法"])

# --- Tab 1: AI 决策 ---
with tab1:
    if st.button("🚀 启动全维度 AI 建模", use_container_width=True):
        with st.status("正在调取深度算力...", expanded=True) as status:
            data = get_stock_all_data(code)
            if data["success"]:
                lamps = calculate_four_lamps(data)
                lamp_str = f"趋势:{lamps['trend']}, 资金:{lamps['money']}, 情绪:{lamps['sentiment']}, 安全:{lamps['safety']}"
                prompt = f"分析股票 {code}。价格:{data['price']}, 四灯状态:{lamp_str}。请按5部分(决策、预测、空间、总结)给出专业分析。"
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[{"role": "system", "content": "你是一个资深私募量化分析师，遵循红涨绿跌的逻辑。"}, {"role": "user", "content": prompt}]
                )
                st.session_state.ai_cache = {"content": response.choices[0].message.content}
                status.update(label="✅ 分析完成", state="complete")
    if st.session_state.ai_cache:
        st.markdown(st.session_state.ai_cache['content'])

# --- Tab 2: 实时资金雷达 (局部静默刷新版) ---
with tab2:
    # 核心占位符
    monitor_placeholder = st.empty()
    
    def render_monitor():
        data = get_stock_all_data(code)
        if data["success"]:
            f = data['fund']
            lamps = calculate_four_lamps(data)
            bj_time = datetime.now(CN_TZ).strftime('%H:%M:%S')
            
            with monitor_placeholder.container():
                st.caption(f"🕒 北京时间: {bj_time} | 🔴 红色代表机会，🟢 绿色代表风险")
                
                # --- 卡片式四灯美化渲染 ---
                st.write("### 🚦 核心策略哨兵")
                l1, l2, l3, l4 = st.columns(4)
                
                def draw_lamp(col, title, status, desc_red, desc_green):
                    color = "#ff4b4b" if status == "🔴" else "#2eb872"
                    bg = "rgba(255, 75, 75, 0.1)" if status == "🔴" else "rgba(46, 184, 114, 0.1)"
                    txt = desc_red if status == "🔴" else desc_green
                    col.markdown(f"""
                        <div style="background-color:{bg}; padding:20px; border-radius:15px; border-top: 5px solid {color}; text-align:center; box-shadow: 2px 2px 5px rgba(0,0,0,0.05);">
                            <p style="margin:0; color:{color}; font-size:14px; font-weight:bold;">{title}</p>
                            <h2 style="margin:10px 0;">{status}</h2>
                            <p style="margin:0; color:{color}; font-size:12px;">{txt}</p>
                        </div>
                    """, unsafe_allow_html=True)

                draw_lamp(l1, "趋势形态", lamps['trend'], "顺势多头", "重心下移")
                draw_lamp(l2, "主力动向", lamps['money'], "主力流入", "主力撤离")
                draw_lamp(l3, "市场情绪", lamps['sentiment'], "买盘活跃", "信心不足")
                draw_lamp(l4, "筹码安全", lamps['safety'], "高度锁定", "散户接盘")

                st.write("---")
                
                # 价格指标
                m1, m2 = st.columns(2)
                m1.metric("📌 当前价位", f"¥{data['price']}", f"{data['pct']}%")
                fund_line = float(f['主力净流入-净占比']) if f is not None else 0
                m2.metric("🌊 核心资金线", f"{fund_line}%", "多方发力" if fund_line > 0 else "空方减速")
                
                # 6大资金板块
                st.write("---")
                st.write("📊 **6大资金板块明细**")
                if f is not None:
                    c1, c2, c3 = st.columns(3); c4, c5, c6 = st.columns(3)
                    c1.metric("🏢 1.机构投资者", f['超大单净流入-净额'])
                    c2.metric("🔥 2.游资动向", f['大单净流入-净额'])
                    c3.metric("🐂 3.大户牛散", f['中单净流入-净额'])
                    c4.metric("🤖 4.量化资金", "🤖 智能监测中")
                    c5.metric("🏭 5.产业资金", f['主力净流入-净额'])
                    c6.metric("🐣 6.散户群体", f['小单净流入-净额'])
                
                st.line_chart(data['df'].set_index('日期')['收盘'], height=200)

    # 自动刷新循环
    if st.session_state.auto_refresh:
        while st.session_state.auto_refresh:
            render_monitor()
            time.sleep(1)
            st.rerun()
    else:
        render_monitor()
        if st.button("🔄 手动同步实时数据", use_container_width=True):
            render_monitor()

# --- Tab 3: 文哥哥·私募心法 (大气美化版) ---
with tab3:
    st.markdown("## 📜 文哥哥·私募心法 (量化博弈指南)")
    
    
    
    st.info("💡 视觉核心：遵循 A 股特色，🔴 红色代表强度与机会，🟢 绿色代表走弱与风险。")
    
    st.write("---")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        #### **1. 📈 趋势灯 (Trend)**
        - **🔴 红灯 (走强)**：多头排列，顺势而为，适合重仓操作。
        - **🟢 绿灯 (警惕)**：均线死叉，重心下移，建议空仓或减磅。
        
        #### **2. 💰 资金灯 (Money)**
        - **🔴 红灯 (吸筹)**：主力资金呈现净买入状态，支撑力度强。
        - **🟢 绿灯 (派发)**：主力大单持续流出，谨防阴跌风险。
        """)
    with col2:
        st.markdown("""
        #### **3. 🎭 情绪灯 (Sentiment)**
        - **🔴 红灯 (高昂)**：日内买气充沛，人气聚集，容易形成合力。
        - **🟢 绿灯 (低迷)**：市场观望情绪重，卖压较大，信心脆弱。
        
        #### **4. 🛡️ 安全灯 (Safety)**
        - **🔴 红灯 (安全)**：散户占比极低，筹码锁定，不易产生踩踏。
        - **🟢 绿灯 (危险)**：散户大幅涌入，筹码松散，极易引发跳水。
        """)

    st.write("---")
    st.subheader("🎯 资金博弈实战口诀")
    st.markdown("""
    | 信号组合 | 逻辑状态 | 操盘策略 |
    | :--- | :--- | :--- |
    | **四灯连红** | **全维度共振** | 核心主升浪，坚定持股，享受红利。 |
    | **灯光闪绿** | **局部背离** | 警惕资金偷跑，观察下方均线支撑。 |
    | **多重绿灯** | **风险扩散** | 执行撤退计划，不盲目抄底，管住手。 |
    """)
    st.success("🛡️ **文哥哥提醒：只做红灯共振的确定性机会，远离绿灯密集的深渊区域。**")

st.divider()
st.caption(f"文哥哥专用 | 北京时间同步稳定版 | 2026 迭代版")
