import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
import time
from datetime import datetime
import pytz

# --- 1. 页面配置 ---
st.set_page_config(page_title="文哥哥极速终端", page_icon="🚀", layout="wide")

# --- 2. 初始化持久化状态 ---
if 'ai_cache' not in st.session_state: st.session_state.ai_cache = None
if 'last_code' not in st.session_state: st.session_state.last_code = ""
if 'auto_refresh' not in st.session_state: st.session_state.auto_refresh = False

CN_TZ = pytz.timezone('Asia/Shanghai')

# --- 3. 核心数据引擎 ---
@st.cache_data(ttl=1)
def get_stock_all_data(code):
    try:
        df_hist = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq").tail(30)
        if df_hist.empty: return {"success": False, "msg": "未找到代码"}
        latest = df_hist.iloc[-1]
        
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
    
    trend_lamp = "🔴" if ma5 > ma20 else "🟢"
    money_lamp = "🟢"
    if fund is not None:
        if "-" not in str(fund['主力净流入-净额']): money_lamp = "🔴"
    sentiment_lamp = "🔴" if data['pct'] > 0 else "🟢"
    safety_lamp = "🟢"
    if fund is not None:
        if float(fund['小单净流入-净占比']) < 20: safety_lamp = "🔴"
            
    return {"trend": trend_lamp, "money": money_lamp, "sentiment": sentiment_lamp, "safety": safety_lamp}

# --- 5. 权限验证 ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.title("🔐 私人终端授权访问")
    pwd = st.text_input("请输入访问密钥", type="password")
    if st.button("开启终端", use_container_width=True):
        if "access_password" in st.secrets and pwd == st.secrets["access_password"]:
            st.session_state['logged_in'] = True
            st.rerun()
        else:
            st.error("密钥无效")
    st.stop()

client = OpenAI(api_key=st.secrets["deepseek_api_key"], base_url="https://api.deepseek.com")

# --- 6. 侧边栏 ---
with st.sidebar:
    st.title("🚀 控制中心")
    code = st.text_input("股票代码", value="600519").strip()
    if code != st.session_state.last_code:
        st.session_state.ai_cache = None
        st.session_state.last_code = code
    
    st.divider()
    # 这里的开关改变会触发一次 rerun，是正常的
    st.session_state.auto_refresh = st.checkbox("🔄 开启秒级实时刷新", value=st.session_state.auto_refresh)
    
    st.divider()
    if st.button("🔴 退出系统"):
        st.session_state['logged_in'] = False
        st.rerun()

st.title(f"📈 文哥哥 AI 终端: {code}")
tab1, tab2, tab3 = st.tabs(["🧠 AI 深度决策", "🎯 实时资金雷达", "📜 文哥哥·私募心法"])

# --- Tab 1: AI 决策 (保持原样) ---
with tab1:
    if st.button("🚀 启动全维度 AI 建模", use_container_width=True):
        data = get_stock_all_data(code)
        if data["success"]:
            lamps = calculate_four_lamps(data)
            lamp_str = f"趋势:{lamps['trend']}, 资金:{lamps['money']}, 情绪:{lamps['sentiment']}, 安全:{lamps['safety']}"
            prompt = f"分析股票 {code}。价格:{data['price']}, 四灯:{lamp_str}。请按决策、预测、空间、总结分析。"
            response = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}])
            st.session_state.ai_cache = {"content": response.choices[0].message.content}
    if st.session_state.ai_cache:
        st.markdown(st.session_state.ai_cache['content'])

# --- Tab 2: 实时资金雷达 (无闪烁关键改动) ---
with tab2:
    # 1. 定义一个持久的容器，刷新时只重写这个容器内部
    monitor_placeholder = st.empty()
    
    def render_content():
        data = get_stock_all_data(code)
        if data["success"]:
            f = data['fund']
            lamps = calculate_four_lamps(data)
            bj_time = datetime.now(CN_TZ).strftime('%H:%M:%S')
            
            # 使用 container() 确保内容整体替换，不闪烁
            with monitor_placeholder.container():
                st.caption(f"🕒 北京时间: {bj_time} | 🔴 红色机会 🟢 绿色风险")
                
                # 四灯展示
                st.write("### 🚦 核心策略哨兵")
                l1, l2, l3, l4 = st.columns(4)
                
                def draw_lamp(col, title, status, desc_red, desc_green):
                    color = "#ff4b4b" if status == "🔴" else "#2eb872"
                    bg = "rgba(255, 75, 75, 0.1)" if status == "🔴" else "rgba(46, 184, 114, 0.1)"
                    txt = desc_red if status == "🔴" else desc_green
                    col.markdown(f"""
                        <div style="background-color:{bg}; padding:15px; border-radius:12px; border-top: 4px solid {color}; text-align:center;">
                            <p style="margin:0; color:{color}; font-size:13px; font-weight:bold;">{title}</p>
                            <h2 style="margin:8px 0;">{status}</h2>
                            <p style="margin:0; color:{color}; font-size:11px;">{txt}</p>
                        </div>
                    """, unsafe_allow_html=True)

                draw_lamp(l1, "趋势形态", lamps['trend'], "顺势多头", "重心下移")
                draw_lamp(l2, "主力动向", lamps['money'], "主力流入", "主力撤离")
                draw_lamp(l3, "市场情绪", lamps['sentiment'], "买盘活跃", "信心不足")
                draw_lamp(l4, "筹码安全", lamps['safety'], "高度锁定", "散户接盘")

                st.write("---")
                m1, m2 = st.columns(2)
                m1.metric("📌 当前价位", f"¥{data['price']}", f"{data['pct']}%")
                fund_line = float(f['主力净流入-净占比']) if f is not None else 0
                m2.metric("🌊 核心资金线", f"{fund_line}%", "多方发力" if fund_line > 0 else "空方占优")
                
                st.write("---")
                st.write("📊 **6大资金板块细分**")
                if f is not None:
                    c1, c2, c3 = st.columns(3); c4, c5, c6 = st.columns(3)
                    c1.metric("🏢 1.机构投资者", f['超大单净流入-净额'])
                    c2.metric("🔥 2.游资动向", f['大单净流入-净额'])
                    c3.metric("🐂 3.大户牛散", f['中单净流入-净额'])
                    c4.metric("🤖 4.量化资金", "🤖 智能监控")
                    c5.metric("🏭 5.产业资金", f['主力净流入-净额'])
                    c6.metric("🐣 6.散户群体", f['小单净流入-净额'])
                
                st.line_chart(data['df'].set_index('日期')['收盘'], height=200)

    # --- 自动刷新核心逻辑：使用 While 但不使用 rerun ---
    if st.session_state.auto_refresh:
        # 第一次渲染
        render_content()
        # 进入循环，直到用户手动关闭开关（关闭开关会触发一次 rerun 从而跳出循环）
        while st.session_state.auto_refresh:
            time.sleep(1)  # 间隔一秒
            render_content() # 仅重写 monitor_placeholder，不刷新整个页面
    else:
        render_content()
        if st.button("🔄 手动同步最新数据", use_container_width=True):
            render_content()

# --- Tab 3: 文哥哥·私募心法 (美化版) ---
with tab3:
    st.markdown("## 📜 文哥哥·私募心法")
    st.info("💡 视觉核心：遵循 A 股特色，🔴 红色代表强度与机会，🟢 绿色代表走弱与风险。")
    st.write("---")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        #### **1. 📈 趋势灯 (Trend)**
        - **🔴 红灯 (走强)**：多头排列，顺势而为。
        - **🟢 绿灯 (警惕)**：重心下移，建议防守。
        #### **2. 💰 资金灯 (Money)**
        - **🔴 红灯 (吸筹)**：主力买入，真金白银。
        - **🟢 绿灯 (流出)**：主力派发，筹码松动。
        """)
    with col2:
        st.markdown("""
        #### **3. 🎭 情绪灯 (Sentiment)**
        - **🔴 红灯 (高昂)**：买气充沛，人气聚集。
        - **🟢 绿灯 (低迷)**：信心不足，卖压较大。
        #### **4. 🛡️ 安全灯 (Safety)**
        - **🔴 红灯 (安全)**：筹码锁定，散户极少。
        - **🟢 绿灯 (危险)**：散户涌入，极易踩踏。
        """)
    st.success("🛡️ **文哥哥提醒：只做红灯共振的机会，远离绿灯密集的区域。**")

st.divider()
st.caption(f"文哥哥专用 | 无闪烁静默刷新版 | 北京时间: {datetime.now(CN_TZ).strftime('%H:%M:%S')}")
