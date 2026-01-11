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

# --- 3. 核心取数逻辑 ---
@st.cache_data(ttl=60)
def get_stock_all_data(code):
    try:
        # A. 基础行情
        df_hist = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq").tail(30)
        if df_hist.empty: return {"success": False, "msg": "未找到代码"}
        latest = df_hist.iloc[-1]
        
        # B. 实时新闻
        try:
            news_df = ak.stock_news_em(symbol=code).head(5)
            news_list = news_df['新闻标题'].tolist() if not news_df.empty else ["暂无最新相关新闻"]
        except:
            news_list = ["新闻接口调用受限"]

        # C. 资金流向
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

# --- 4. 四灯算法逻辑内核 ---
def calculate_four_lamps(data):
    if not data or not data.get('success'):
        return {"trend": "⚪", "money": "⚪", "sentiment": "⚪", "safety": "⚪"}
    
    df = data['df']
    fund = data['fund']
    
    # 1. 趋势灯: MA5 vs MA20
    ma5 = df['收盘'].tail(5).mean()
    ma20 = df['收盘'].tail(20).mean()
    trend_lamp = "🟢" if ma5 > ma20 else "🔴"
    
    # 2. 资金灯: 主力流入
    money_lamp = "🔴"
    if fund is not None:
        if "-" not in str(fund['主力净流入-净额']):
            money_lamp = "🟢"
            
    # 3. 情绪灯: 当日涨幅
    sentiment_lamp = "🟢" if data['pct'] > 0 else "🔴"
    
    # 4. 安全灯: 散户占比 (反向)
    safety_lamp = "🔴"
    if fund is not None:
        if float(fund['小单净流入-净占比']) < 20:
            safety_lamp = "🟢"
            
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
        st.session_state.fund_cache = None
        st.session_state.last_code = code
    st.divider()
    if st.button("🔴 退出系统"):
        st.session_state['logged_in'] = False
        st.rerun()

st.title(f"📈 文哥哥 AI 终端: {code}")

tab1, tab2, tab3 = st.tabs(["🧠 AI 深度决策", "🎯 资金追踪雷达", "🕯️ 监控与说明书"])

# --- Tab 1: AI 决策 ---
with tab1:
    if st.button("🚀 启动全维度 AI 建模", use_container_width=True):
        with st.status("建模中...", expanded=True) as status:
            data = get_stock_all_data(code)
            if data["success"]:
                lamps = calculate_four_lamps(data)
                lamp_str = f"趋势:{lamps['trend']}, 资金:{lamps['money']}, 情绪:{lamps['sentiment']}, 安全:{lamps['safety']}"
                prompt = f"分析股票 {code}。价格:{data['price']}, 四灯:{lamp_str}。请按5部分分析(决策、周预测、月预测、空间、总结)。"
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[{"role": "system", "content": "金融专家"}, {"role": "user", "content": prompt}]
                )
                st.session_state.ai_cache = {"content": response.choices[0].message.content, "price": data['price'], "lamps": lamps}
                status.update(label="✅ 分析完成", state="complete")

    if st.session_state.ai_cache:
        st.markdown(st.session_state.ai_cache['content'])

# --- Tab 2: 资金追踪雷达 (6大板块) ---
with tab2:
    if st.button("📡 扫描六大板块资金", use_container_width=True):
        data = get_stock_all_data(code)
        if data["success"]: st.session_state.fund_cache = data
    
    if st.session_state.fund_cache:
        f = st.session_state.fund_cache['fund']
        if f is not None:
            c1, c2, c3 = st.columns(3); c4, c5, c6 = st.columns(3)
            c1.metric("🏢 1.机构投资者", f['超大单净流入-净额'])
            c2.metric("🔥 2.游资动向", f['大单净流入-净额'])
            c3.metric("🐂 3.大户/牛散", f['中单净流入-净额'])
            c4.metric("🤖 4.量化资金", "🤖 模拟监测中")
            c5.metric("🏭 5.产业资金", f['主力净流入-净额'])
            c6.metric("🐣 6.散户群体", f['小单净流入-净额'])

# --- Tab 3: 实时监控 + 说明书 ---
with tab3:
    st.subheader("🛡️ 实时四灯监控哨兵")
    if st.button("🔄 刷新实时监控数据", use_container_width=True):
        # 实时抓取并刷新
        real_data = get_stock_all_data(code)
        if real_data["success"]:
            lamps = calculate_four_lamps(real_data)
            f = real_data['fund']
            
            # 顶部实时三指标
            m1, m2, m3 = st.columns(3)
            m1.metric("📌 当前价位", f"¥{real_data['price']}", f"{real_data['pct']}%")
            # 资金线逻辑：大单及以上净占比合计
            fund_line = float(f['主力净流入-净占比']) if f is not None else 0
            m2.metric("🌊 核心资金线", f"{fund_line}%", "活跃" if fund_line > 0 else "疲软")
            m3.metric("🚦 综合灯效", f"{lamps['trend']}{lamps['money']}{lamps['sentiment']}{lamps['safety']}")
            
            st.write("---")
            # 四灯状态细节
            l1, l2, l3, l4 = st.columns(4)
            l1.info(f"趋势灯: {lamps['trend']}")
            l2.info(f"资金灯: {lamps['money']}")
            l3.info(f"情绪灯: {lamps['sentiment']}")
            l4.info(f"安全灯: {lamps['safety']}")
        else:
            st.error("实时获取失败，请稍后重试")

    st.write("---")
    st.header("📖 四灯算法逻辑说明书")
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("""
        **1. 📈 趋势灯 (Trend)** MA5 > MA20 时亮🟢。判断是否有短期多头动能。  
        **2. 💰 资金灯 (Money)** 主力净流入为正时亮🟢。判断是否有大部队进场。
        """)
    with col_b:
        st.markdown("""
        **3. 🎭 情绪灯 (Sentiment)** 当日价格上涨亮🟢。判断市场对该股的认可度。  
        **4. 🛡️ 安全灯 (Safety)** 散户流入占比 < 20% 亮🟢。判断筹码是否在聪明钱手里。
        """)
    st.warning("文哥哥提示：四灯全绿为‘屠龙区’，四灯全红请‘快闪’。")

st.divider()
st.caption("文哥哥专用 | 实时四灯哨兵版 | 6大板块全透视")
