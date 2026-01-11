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
if 'last_data' not in st.session_state: st.session_state.last_data = None
if 'last_code' not in st.session_state: st.session_state.last_code = ""
if 'auto_refresh' not in st.session_state: st.session_state.auto_refresh = False

CN_TZ = pytz.timezone('Asia/Shanghai')

# --- 3. 核心数据引擎 (带断流保护) ---
@st.cache_data(ttl=2)
def get_stock_all_data(code):
    try:
        df_hist = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq").tail(30)
        if df_hist.empty: return {"success": False, "msg": "未找到代码"}
        
        fund = None
        try:
            mkt = "sh" if code.startswith(('6', '9', '688')) else "sz"
            df_fund = ak.stock_individual_fund_flow(stock=code, market=mkt)
            if not df_fund.empty: fund = df_fund.iloc[0]
        except: pass 
            
        return {
            "success": True, 
            "price": df_hist.iloc[-1]['收盘'], 
            "pct": df_hist.iloc[-1]['涨跌幅'],
            "fund": fund, 
            "df": df_hist
        }
    except Exception as e:
        return {"success": False, "msg": "数据源繁忙"}

# --- 4. 四灯算法逻辑 (🔴正面/强, 🟢负面/弱) ---
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
        try:
            if float(fund['小单净流入-净占比']) < 20: safety_lamp = "🔴"
        except: pass
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
        st.session_state.last_code = code
        st.session_state.ai_cache = None
        st.session_state.last_data = None
    
    st.divider()
    st.session_state.auto_refresh = st.checkbox("🔄 开启秒级实时刷新", value=st.session_state.auto_refresh)
    
    st.divider()
    if st.button("🔴 退出系统"):
        st.session_state['logged_in'] = False
        st.rerun()

st.title(f"📈 文哥哥 AI 终端: {code}")
tab1, tab2, tab3 = st.tabs(["🧠 AI 深度决策", "🎯 实时资金雷达", "📜 文哥哥·私募心法"])

# --- Tab 1: AI 决策 (进度条版) ---
with tab1:
    if st.button("🚀 启动全维度 AI 建模", use_container_width=True):
        progress_text = "正在调取深度量化算力分析中..."
        my_bar = st.progress(0, text=progress_text)
        for percent in range(0, 101, 5):
            time.sleep(0.05)
            my_bar.progress(percent, text=progress_text)
        
        data = get_stock_all_data(code)
        if data["success"]:
            lamps = calculate_four_lamps(data)
            lamp_str = f"趋势:{lamps['trend']}, 资金:{lamps['money']}, 情绪:{lamps['sentiment']}, 安全:{lamps['safety']}"
            prompt = f"分析股票 {code}。价格:{data['price']}, 四灯状态:{lamp_str}。请按决策、预测、空间、总结分析。"
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "system", "content": "你资深私募量化师。"}, {"role": "user", "content": prompt}]
            )
            st.session_state.ai_cache = {"content": response.choices[0].message.content}
            my_bar.empty()
    if st.session_state.ai_cache:
        st.markdown(st.session_state.ai_cache['content'])

# --- Tab 2: 实时资金雷达 (两行明细+万元版) ---
with tab2:
    monitor_placeholder = st.empty()
    
    def render_dashboard():
        res = get_stock_all_data(code)
        if not res["success"] and st.session_state.last_data:
            data = st.session_state.last_data
            status_tag = "⚠️ 延迟数据"
        elif res["success"]:
            data = res
            st.session_state.last_data = res
            status_tag = "🟢 实时连通"
        else:
            monitor_placeholder.warning("正在连接卫星数据源...")
            return

        f = data['fund']
        lamps = calculate_four_lamps(data)
        bj_time = datetime.now(CN_TZ).strftime('%H:%M:%S')
        
        with monitor_placeholder.container():
            st.caption(f"🕒 北京时间: {bj_time} | {status_tag} | 🔴正面 🟢风险")
            
            # 四灯显示
            st.write("### 🚦 核心策略哨兵")
            l1, l2, l3, l4 = st.columns(4)
            def draw_lamp(col, title, status, desc_red, desc_green):
                color = "#ff4b4b" if status == "🔴" else "#2eb872"
                bg = "rgba(255, 75, 75, 0.1)" if status == "🔴" else "rgba(46, 184, 114, 0.1)"
                col.markdown(f"""
                    <div style="background-color:{bg}; padding:15px; border-radius:12px; border-top: 5px solid {color}; text-align:center;">
                        <p style="margin:0; color:{color}; font-size:13px; font-weight:bold;">{title}</p>
                        <h2 style="margin:8px 0;">{status}</h2>
                        <p style="margin:0; color:{color}; font-size:11px;">{desc_red if status=='🔴' else desc_green}</p>
                    </div>
                """, unsafe_allow_html=True)

            draw_lamp(l1, "趋势形态", lamps['trend'], "顺势多头", "重心下移")
            draw_lamp(l2, "主力动向", lamps['money'], "主力流入", "主力撤离")
            draw_lamp(l3, "市场情绪", lamps['sentiment'], "买盘活跃", "信心不足")
            draw_lamp(l4, "筹码安全", lamps['safety'], "高度锁定", "散户接盘")

            st.write("---")
            m1, m2 = st.columns(2)
            m1.metric("📌 当前价位", f"¥{data['price']}", f"{data['pct']}%")
            # 资金流转万元
            f_total = float(f['主力净流入-净额']) / 10000 if f is not None else 0
            m2.metric("🌊 主力净额", f"{f_total:.2f} 万", "多方入场" if f_total > 0 else "空方减速")
            
            st.write("---")
            st.write("📊 **6大资金板块明细 (万元)**")
            if f is not None:
                # 分成两行
                r1_c1, r1_c2, r1_c3 = st.columns(3)
                r2_c1, r2_c2, r2_c3 = st.columns(3)
                
                # 第一行
                r1_c1.metric("🏢 机构投资者", f"{float(f['超大单净流入-净额'])/10000:.1f} 万")
                r1_c2.metric("🔥 游资动向", f"{float(f['大单净流入-净额'])/10000:.1f} 万")
                r1_c3.metric("🐂 大户牛散", f"{float(f['中单净流入-净额'])/10000:.1f} 万")
                
                # 第二行
                r2_c1.metric("🤖 量化资金", "实时监控中")
                r2_c2.metric("🏭 产业资金", f"{float(f['主力净流入-净额'])/10000:.1f} 万")
                r2_c3.metric("🐣 散户群体", f"{float(f['小单净流入-净占比']):.1f} %")
            
            st.line_chart(data['df'].set_index('日期')['收盘'], height=200)

    if st.session_state.auto_refresh:
        while st.session_state.auto_refresh:
            render_dashboard()
            time.sleep(1)
    else:
        render_dashboard()
        if st.button("🔄 手动同步最新数据"): render_dashboard()

# --- Tab 3: 文哥哥·私募心法 ---
with tab3:
    st.markdown("## 📜 文哥哥·私募心法")
    
    st.info("💡 视觉核心：遵循 A 股特色，🔴 红色代表强度与机会，🟢 绿色代表走弱与风险。")
    st.write("---")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### **1. 📈 趋势灯**\n- **🔴 红色**：多头，持股。\n- **🟢 绿色**：走弱，防守。")
        st.markdown("#### **2. 💰 资金灯**\n- **🔴 红色**：主力入场。\n- **🟢 绿色**：主力撤离。")
    with col2:
        st.markdown("#### **3. 🎭 情绪灯**\n- **🔴 红色**：买盘积极。\n- **🟢 绿色**：卖压沉重。")
        st.markdown("#### **4. 🛡️ 安全灯**\n- **🔴 红色**：筹码锁定。\n- **🟢 绿色**：散户涌入。")
    st.success("🛡️ **文哥哥提醒：只做红灯共振的机会，坚决远离绿灯密集的区域。**")

st.divider()
st.caption(f"文哥哥专用 | 2026.01.12 | 万元版")
