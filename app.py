import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
import time
from datetime import datetime
import pytz  # 引入时区库

# --- 1. 页面配置 ---
st.set_page_config(page_title="文哥哥极速终端", page_icon="🚀", layout="wide")

# --- 2. 初始化持久化记忆 ---
if 'ai_cache' not in st.session_state: st.session_state.ai_cache = None
if 'last_code' not in st.session_state: st.session_state.last_code = ""
if 'auto_refresh' not in st.session_state: st.session_state.auto_refresh = False

# 定义中国时区
CN_TZ = pytz.timezone('Asia/Shanghai')

# --- 3. 核心取数逻辑 ---
@st.cache_data(ttl=1)
def get_stock_all_data(code):
    try:
        df_hist = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq").tail(30)
        if df_hist.empty: return {"success": False, "msg": "未找到代码"}
        latest = df_hist.iloc[-1]
        
        try:
            news_df = ak.stock_news_em(symbol=code).head(5)
            news_list = news_df['新闻标题'].tolist() if not news_df.empty else ["暂无最新相关新闻"]
        except:
            news_list = ["新闻接口调用受限"]

        fund = None
        try:
            mkt = "sh" if code.startswith(('6', '9', '688')) else "sz"
            df_fund = ak.stock_individual_fund_flow(stock=code, market=mkt)
            if not df_fund.empty:
                fund = df_fund.iloc[0]
        except:
            pass 
            
        return {
            "success": True,
            "price": latest['收盘'],
            "pct": latest['涨跌幅'],
            "vol": latest['成交额'],
            "news": news_list,
            "fund": fund,
            "df": df_hist
        }
    except Exception as e:
        return {"success": False, "msg": str(e)}

# --- 4. 四灯算法逻辑核心 ---
def calculate_four_lamps(data):
    if not data or not data.get('success'):
        return {"trend": "⚪", "money": "⚪", "sentiment": "⚪", "safety": "⚪"}
    df = data['df']
    fund = data['fund']
    ma5 = df['收盘'].tail(5).mean()
    ma20 = df['收盘'].tail(20).mean()
    trend_lamp = "🟢" if ma5 > ma20 else "🔴"
    money_lamp = "🔴"
    if fund is not None:
        if "-" not in str(fund['主力净流入-净额']): money_lamp = "🟢"
    sentiment_lamp = "🟢" if data['pct'] > 0 else "🔴"
    safety_lamp = "🔴"
    if fund is not None:
        if float(fund['小单净流入-净占比']) < 20: safety_lamp = "🟢"
    return {"trend": trend_lamp, "money": money_lamp, "sentiment": sentiment_lamp, "safety": safety_lamp}

# --- 5. 安全验证 ---
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
    st.session_state.auto_refresh = st.checkbox("🔄 开启实时静默刷新 (1s/次)", value=st.session_state.auto_refresh)
    
    st.divider()
    if st.button("🔴 退出系统"):
        st.session_state['logged_in'] = False
        st.rerun()

st.title(f"📈 文哥哥 AI 终端: {code}")

tab1, tab2, tab3 = st.tabs(["🧠 AI 深度决策", "🎯 实时资金雷达", "📜 文哥哥·私募心法"])

# --- Tab 1: AI 决策 ---
with tab1:
    if st.button("🚀 启动全维度 AI 建模", use_container_width=True):
        data = get_stock_all_data(code)
        if data["success"]:
            lamps = calculate_four_lamps(data)
            lamp_str = f"趋势:{lamps['trend']}, 资金:{lamps['money']}, 情绪:{lamps['sentiment']}, 安全:{lamps['safety']}"
            prompt = f"分析股票 {code}。价格:{data['price']}, 四灯:{lamp_str}。请按5部分分析。"
            response = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}])
            st.session_state.ai_cache = {"content": response.choices[0].message.content}
    if st.session_state.ai_cache:
        st.markdown(st.session_state.ai_cache['content'])

# --- Tab 2: 实时资金雷达 (时区同步版) ---
with tab2:
    main_placeholder = st.empty()
    def draw_ui():
        data = get_stock_all_data(code)
        if data["success"]:
            f = data['fund']
            lamps = calculate_four_lamps(data)
            fund_line = float(f['主力净流入-净占比']) if f is not None else 0
            
            # 获取北京时间
            bj_time = datetime.now(CN_TZ).strftime('%H:%M:%S')
            
            with main_placeholder.container():
                c_time, c_status = st.columns([1, 1])
                c_time.caption(f"🕒 最后更新时间: {bj_time} | 步频: 1s")
                c_status.markdown("🟢 **终端监控已就绪**" if st.session_state.auto_refresh else "🟡 **手动待机模式**")
                m1, m2, m3 = st.columns(3)
                m1.metric("📌 当前价位", f"¥{data['price']}", f"{data['pct']}%")
                m2.metric("🌊 核心资金线", f"{fund_line}%", "活跃" if fund_line > 0 else "疲软")
                m3.metric("🚦 综合灯效", f"{lamps['trend']}{lamps['money']}{lamps['sentiment']}{lamps['safety']}")
                st.write("---")
                l1, l2, l3, l4 = st.columns(4)
                l1.info(f"趋势灯: {lamps['trend']}")
                l2.info(f"资金灯: {lamps['money']}")
                l3.info(f"情绪灯: {lamps['sentiment']}")
                l4.info(f"安全灯: {lamps['safety']}")
                st.write("---")
                st.write("📊 **6大资金板块动态**")
                if f is not None:
                    c1, c2, c3 = st.columns(3); c4, c5, c6 = st.columns(3)
                    c1.metric("🏢 1.机构投资者", f['超大单净流入-净额'])
                    c2.metric("🔥 2.游资动向", f['大单净流入-净额'])
                    c3.metric("🐂 3.大户/牛散", f['中单净流入-净额'])
                    c4.metric("🤖 4.量化资金", "🤖 扫描中")
                    c5.metric("🏭 5.产业资金", f['主力净流入-净额'])
                    c6.metric("🐣 6.散户群体", f['小单净流入-净额'])
                st.write("---")
                st.line_chart(data['df'].set_index('日期')['收盘'], height=200)
    
    if st.session_state.auto_refresh:
        while st.session_state.auto_refresh:
            draw_ui()
            time.sleep(1)
    else:
        draw_ui()
        if st.button("🔄 同步最新实时数据", use_container_width=True):
            draw_ui()

# --- Tab 3: 文哥哥私人·四灯算法说明书 ---
with tab3:
    st.markdown("""
    ## 📜 文哥哥私人·量化四灯算法心法
    > **本系统通过“趋势、资金、情绪、筹码”四大维度构建实时博弈模型，旨在剥离市场噪音，直击资金底牌。**
    """)
    st.write("---")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        ### 🕯️ 信号逻辑解析
        #### **1. 📈 趋势灯 (Trend)**
        * **监控目标**: 价格运行重心。
        * **🟢 绿灯**: 多头排列，处于上升趋势。
        #### **2. 💰 资金灯 (Money)**
        * **监控目标**: 真实真金白银动向。
        * **🟢 绿灯**: 主力净买入，资金在加仓。
        """)
    with col2:
        st.markdown("""
        ### 🕯️ 信号逻辑解析 (续)
        #### **3. 🎭 情绪灯 (Sentiment)**
        * **监控目标**: 市场人气与即时认可度。
        * **🟢 绿灯**: 市场热度上行，买盘积极。
        #### **4. 🛡️ 安全灯 (Safety)**
        * **监控目标**: 筹码集中度与洗盘深度（反向指标）。
        * **🟢 绿灯**: 散户占比 < 20%，筹码已被锁定。
        """)
    st.write("---")
    st.subheader("🎯 六大板块资金博弈模型")
    st.markdown("""
    | 资金板块 | 角色定位 | 操作特性 |
    | :--- | :--- | :--- |
    | **1. 机构投资者** | 定海神针 | 长线筹码，决定趋势高度。 |
    | **2. 游资动向** | 进攻箭头 | 擅长打板，决定短线爆发力。 |
    | **3. 大户/牛散** | 敏锐嗅觉 | 盘感极佳，通常在转折点出现。 |
    | **4. 量化资金** | 绞肉机器 | 高频收割，造成盘中剧烈波动。 |
    | **5. 产业资金** | 底牌玩家 | 决定公司价值底线。 |
    | **6. 散户群体** | 反向指标 | 集体割肉时可布局。 |
    """)
    st.success("🛡️ **四灯全绿：【屠龙模式】。资金、趋势、筹码全共振。**")

st.divider()
st.caption(f"文哥哥专用 | 北京时间同步版 | 当前时区: {CN_TZ}")
