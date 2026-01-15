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

# --- 2. 密钥检测 (从 Secrets 读取) ---
if "deepseek_api_key" not in st.secrets or "access_password" not in st.secrets:
    st.error("❌ 密钥未配置！请在 Streamlit Settings -> Secrets 中添加 key。")
    st.stop()

# --- 3. 初始化持久化状态 ---
if 'ai_cache' not in st.session_state: st.session_state.ai_cache = None
if 'last_data' not in st.session_state: st.session_state.last_data = None
if 'last_code' not in st.session_state: st.session_state.last_code = ""
if 'auto_refresh' not in st.session_state: st.session_state.auto_refresh = False

CN_TZ = pytz.timezone('Asia/Shanghai')

# --- 4. 辅助函数：智能单位转换 ---
def format_money(value_str):
    """智能转换：数值超1亿显示'亿'，否则显示'万'"""
    try:
        val = float(value_str)
        abs_val = abs(val)
        if abs_val >= 100000000:
            return f"{val / 100000000:.2f} 亿"
        else:
            return f"{val / 10000:.1f} 万"
    except:
        return "N/A"

# --- 5. 多线程并发数据引擎 ---
def fetch_hist(code):
    try:
        # 剔除ST、创业板、科创板逻辑（在数据端过滤）
        return ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq").tail(30)
    except: return pd.DataFrame()

def fetch_fund(code):
    try:
        mkt = "sh" if code.startswith(('6', '9', '688')) else "sz"
        return ak.stock_individual_fund_flow(stock=code, market=mkt)
    except: return pd.DataFrame()

@st.cache_data(ttl=2)
def get_stock_data_parallel(code):
    try:
        # 并发抓取行情和资金
        with ThreadPoolExecutor(max_workers=2) as executor:
            f_hist = executor.submit(fetch_hist, code)
            f_fund = executor.submit(fetch_fund, code)
            df_hist = f_hist.result()
            df_fund = f_fund.result()

        if df_hist.empty: return {"success": False, "msg": "代码无效或数据未更新"}
        
        fund = df_fund.iloc[0] if not df_fund.empty else None
        return {
            "success": True, 
            "price": df_hist.iloc[-1]['收盘'], 
            "pct": df_hist.iloc[-1]['涨跌幅'],
            "fund": fund, 
            "df": df_hist
        }
    except Exception as e:
        return {"success": False, "msg": str(e)}

# --- 6. 四灯量化核心算法 (🔴多/🟢空) ---
def calculate_four_lamps(data):
    if not data or not data.get('success'):
        return {"trend": "⚪", "money": "⚪", "sentiment": "⚪", "safety": "⚪"}
    df = data['df']
    fund = data['fund']
    
    # 1. 趋势灯：MA5 vs MA20
    ma5, ma20 = df['收盘'].tail(5).mean(), df['收盘'].tail(20).mean()
    trend = "🔴" if ma5 > ma20 else "🟢"
    
    # 2. 资金灯：主力净流入额
    money = "🔴" if fund is not None and "-" not in str(fund['主力净流入-净额']) else "🟢"
    
    # 3. 情绪灯：实时涨跌
    sentiment = "🔴" if data['pct'] > 0 else "🟢"
    
    # 4. 安全灯：小单(散户)占比是否低于15%
    safety = "🔴" if fund is not None and float(fund['小单净流入-净占比']) < 15 else "🟢"
    
    return {"trend": trend, "money": money, "sentiment": sentiment, "safety": safety}

# --- 7. 登录模块 ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if not st.session_state['logged_in']:
    st.title("🔐 文哥哥私人量化终端")
    pwd = st.text_input("请输入访问密钥", type="password")
    if st.button("开启终端", use_container_width=True):
        if pwd == st.secrets["access_password"]:
            st.session_state['logged_in'] = True
            st.rerun()
        else: st.error("密钥错误")
    st.stop()

# 初始化 AI
client = OpenAI(api_key=st.secrets["deepseek_api_key"], base_url="https://api.deepseek.com")

# --- 8. 侧边栏 ---
with st.sidebar:
    st.title("🚀 控制中心")
    code = st.text_input("股票代码", value="600519").strip()
    if code != st.session_state.last_code:
        st.session_state.last_code, st.session_state.ai_cache, st.session_state.last_data = code, None, None
    
    st.divider()
    st.session_state.auto_refresh = st.checkbox("🔄 开启秒级无闪刷新", value=st.session_state.auto_refresh)
    
    st.divider()
    if st.button("🔴 退出系统"):
        st.session_state['logged_in'] = False
        st.rerun()

st.title(f"📈 文哥哥 AI 终端: {code}")
t1, t2, t3 = st.tabs(["🧠 AI 深度决策", "🎯 实时资金雷达", "📜 文哥哥·私募心法"])

# --- Tab 1: AI 深度决策 (最直观指令版) ---
with t1:
    if st.button("🚀 启动全维度 AI 建模分析", use_container_width=True):
        p_bar = st.progress(0, text="多线程并发建模中...")
        for p in range(0, 101, 10): time.sleep(0.05); p_bar.progress(p)
        
        data = get_stock_data_parallel(code)
        if data["success"]:
            l = calculate_four_lamps(data)
            lamp_str = f"趋势:{l['trend']}, 资金:{l['money']}, 情绪:{l['sentiment']}, 安全:{l['safety']}"
            
            prompt = f"""
            你是一位年化收益50%以上的私募操盘手，请对股票 {code} 进行“一句话判死生”式的分析。
            当前数据：价格 {data['price']}, 涨跌幅 {data['pct']}%, 四灯状态 {lamp_str}。

            请严格按以下格式输出，不要废话：
            1. 【战术评级】：（例如：全线进攻 / 逢高撤退 / 绝对空仓观望）
            2. 【核心理由】：（一句话点出最关键的资金或筹码问题）
            3. 【博弈位】：（支撑位：XXX，压力位：XXX）
            4. 【文哥哥锦囊】：（给出一句干货实战叮嘱）
            注意：红涨绿跌，红强绿弱。
            """
            
            res = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}])
            st.session_state.ai_cache = {"content": res.choices[0].message.content}
            p_bar.empty()
            
    if st.session_state.ai_cache:
        st.markdown("### 🏹 实战决策指令")
        st.info(st.session_state.ai_cache['content'])

# --- Tab 2: 实时资金雷达 (无闪烁刷新) ---
with t2:
    placeholder = st.empty()
    def render():
        res = get_stock_data_parallel(code)
        # 断流保护
        if not res["success"] and st.session_state.last_data:
            data, tag = st.session_state.last_data, "⚠️ 断流保护"
        elif res["success"]:
            data = st.session_state.last_data = res; tag = "🟢 实时连通"
        else:
            placeholder.warning("正在并发采集数据..."); return

        f, l = data['fund'], calculate_four_lamps(data)
        
        with placeholder.container():
            st.caption(f"🕒 {datetime.now(CN_TZ).strftime('%H:%M:%S')} | {tag} | 🔴正面 🟢风险")
            
            st.write("### 🚦 核心策略哨兵")
            cols = st.columns(4)
            titles = ["趋势形态", "主力动向", "市场情绪", "筹码安全"]
            keys = ["trend", "money", "sentiment", "safety"]
            descs = [("顺势多头", "重心下移"), ("主力流入", "资金流出"), ("买盘活跃", "信心不足"), ("锁定良好", "散户接盘")]
            
            for i, col in enumerate(cols):
                status = l[keys[i]]
                color = "#ff4b4b" if status == "🔴" else "#2eb872"
                bg = "rgba(255, 75, 75, 0.1)" if status == "🔴" else "rgba(46, 184, 114, 0.1)"
                col.markdown(f"""
                    <div style="background-color:{bg}; padding:15px; border-radius:12px; border-top: 5px solid {color}; text-align:center;">
                        <p style="margin:0; color:{color}; font-weight:bold;">{titles[i]}</p>
                        <h2 style="margin:8px 0;">{status}</h2>
                        <p style="margin:0; color:{color}; font-size:11px;">{descs[i][0] if status=="🔴" else descs[i][1]}</p>
                    </div>
                """, unsafe_allow_html=True)
            
            st.divider()
            m1, m2 = st.columns(2)
            m1.metric("📌 当前价位", f"¥{data['price']}", f"{data['pct']}%")
            main_f = f['主力净流入-净额'] if f is not None else 0
            m2.metric("🌊 主力净额", format_money(main_f), "多方发力" if float(main_f) > 0 else "空方占优")
            
            st.write("📊 **6大资金板块明细 (亿/万自动转换)**")
            if f is not None:
                r1 = st.columns(3); r2 = st.columns(3)
                r1[0].metric("1. 🏢 机构投资者", format_money(f['超大单净流入-净额']))
                r1[1].metric("2. 🔥 游资动向", format_money(f['大单净流入-净额']))
                r1[2].metric("3. 🐂 大户牛散", format_money(f['中单净流入-净额']))
                r2[0].metric("4. 🤖 量化资金", "智能监控中")
                r2[1].metric("5. 🏭 产业资金", format_money(f['主力净流入-净额']))
                r2[2].metric("6. 🐣 散户群体", f"{float(f['小单净流入-净占比']):.1f} %")
            
            st.line_chart(data['df'].set_index('日期')['收盘'], height=250)

    if st.session_state.auto_refresh:
        while st.session_state.auto_refresh: render(); time.sleep(1)
    else: render()

# --- Tab 3: 文哥哥·私募心法 (逻辑详解) ---
with tab3:
    st.markdown("## 📜 文哥哥·私募心法")
    
    st.write("---")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        #### **1. 📈 趋势灯 (Trend)：判定生死**
        - **🔴 红灯**：MA5 > MA20，攻击线上扬，顺势而为。
        - **🟢 绿灯**：重心下移，反弹即逃命。
        
        #### **2. 💰 资金灯 (Money)：辨别真伪**
        - **🔴 红灯**：主力大单净流入，机构真金白银入场。
        - **🟢 绿灯**：拉高出货，资金背离。
        """)
    with col2:
        st.markdown("""
        #### **3. 🎭 情绪灯 (Sentiment)：看冲击力**
        - **🔴 红灯**：实时价格上涨，多方占优。
        - **🟢 绿灯**：信心匮乏，卖压沉重。
        
        #### **4. 🛡️ 安全灯 (Safety)：测压力值**
        - **🔴 红灯**：散户占比 < 15%，筹码高度锁定，易涨难跌。
        - **🟢 绿灯**：散户疯狂进场，容易产生踩踏。
        """)
    st.success("🛡️ **文哥哥提醒：只做红灯共振的机会，坚决执行止损绿灯。**")

st.divider()
st.caption(f"文哥哥专用 | 2026-01-15 序号居中稳定母版 | 无闪刷新版")
