import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
import time
from datetime import datetime
import pytz

# --- 1. 页面配置 ---
st.set_page_config(page_title="文哥哥极速终端", page_icon="🚀", layout="wide")

# --- 2. 初始化持久化记忆 ---
if 'ai_cache' not in st.session_state: st.session_state.ai_cache = None
if 'last_code' not in st.session_state: st.session_state.last_code = ""
if 'auto_refresh' not in st.session_state: st.session_state.auto_refresh = False

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
            "success": True, "price": latest['收盘'], "pct": latest['涨跌幅'],
            "vol": latest['成交额'], "news": news_list, "fund": fund, "df": df_hist
        }
    except Exception as e:
        return {"success": False, "msg": str(e)}

# --- 4. 四灯算法逻辑 (红色正面🔴，绿色负面🟢) ---
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

with tab1:
    if st.button("🚀 启动全维度 AI 建模", use_container_width=True):
        data = get_stock_all_data(code)
        if data["success"]:
            lamps = calculate_four_lamps(data)
            lamp_str = f"趋势:{lamps['trend']}, 资金:{lamps['money']}, 情绪:{lamps['sentiment']}, 安全:{lamps['safety']}"
            prompt = f"分析股票 {code}。价格:{data['price']}, 四灯:{lamp_str}。请结合红利绿空的中国特色给出决策分析。"
            response = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}])
            st.session_state.ai_cache = {"content": response.choices[0].message.content}
    if st.session_state.ai_cache:
        st.markdown(st.session_state.ai_cache['content'])

# --- Tab 2: 实时资金雷达 (修复渲染错误) ---
with tab2:
    placeholder = st.empty()
    
    def render_content():
        data = get_stock_all_data(code)
        if data["success"]:
            f = data['fund']
            lamps = calculate_four_lamps(data)
            fund_line = float(f['主力净流入-净占比']) if f is not None else 0
            bj_time = datetime.now(CN_TZ).strftime('%H:%M:%S')
            
            with placeholder.container():
                st.caption(f"🕒 中国标准时间: {bj_time} | 🔴正面信号 🟢风险警告")
                m1, m2, m3 = st.columns(3)
                m1.metric("📌 当前价位", f"¥{data['price']}", f"{data['pct']}%")
                m2.metric("🌊 核心资金线", f"{fund_line}%", "多方占优" if fund_line > 0 else "空方占优")
                m3.metric("🚦 综合灯效", f"{lamps['trend']}{lamps['money']}{lamps['sentiment']}{lamps['safety']}")
                
                st.write("---")
                l1, l2, l3, l4 = st.columns(4)
                # 使用 error 表示红色(正面警告色在UI中需语义化处理，这里统一用颜色块)
                with l1: st.markdown(f"**趋势**\n# {'🔴' if lamps['trend']=='🔴' else '🟢'}")
                with l2: st.markdown(f"**资金**\n# {'🔴' if lamps['money']=='🔴' else '🟢'}")
                with l3: st.markdown(f"**情绪**\n# {'🔴' if lamps['sentiment']=='🔴' else '🟢'}")
                with l4: st.markdown(f"**安全**\n# {'🔴' if lamps['safety']=='🔴' else '🟢'}")
                
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
                st.line_chart(data['df'].set_index('日期')['收盘'], height=200)

    # 自动刷新逻辑，避免 DeltaGenerator 错误
    if st.session_state.auto_refresh:
        while st.session_state.auto_refresh:
            render_content()
            time.sleep(1)
    else:
        render_content()
        if st.button("🔄 同步实时数据"): render_content()

# --- Tab 3: 文哥哥·私募心法 (增强版) ---
with tab3:
    st.markdown("## 📜 文哥哥·私募心法")
    st.info("💡 视觉核心：遵循 A 股特色，🔴 红色代表强度与机会，🟢 绿色代表走弱与风险。")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        #### **1. 📈 趋势灯 (Trend)**
        - **🔴 红灯 (走强)**：多头排列，顺势而为。
        - **🟢 绿灯 (风险)**：趋势破位，建议止损。
        
        #### **2. 💰 资金灯 (Money)**
        - **🔴 红灯 (吸筹)**：主力买入，真金白银护盘。
        - **🟢 绿灯 (流出)**：主力派发，筹码搬家散户。
        """)
    with col2:
        st.markdown("""
        #### **3. 🎭 情绪灯 (Sentiment)**
        - **🔴 红灯 (高昂)**：人气聚集，买盘积极。
        - **🟢 绿灯 (低迷)**：信心不足，卖盘占优。
        
        #### **4. 🛡️ 安全灯 (Safety)**
        - **🔴 红灯 (安全)**：筹码高度集中，散户占比低。
        - **🟢 绿灯 (危险)**：散户涌入接盘，易生踩踏。
        """)

    st.write("---")
    st.subheader("🎯 资金博弈模型说明")
    
    # 插入示意图帮助理解资金博弈
    

    st.markdown("""
    | 信号组合 | 操盘建议 |
    | :--- | :--- |
    | **四灯连红** | **【龙抬头】**。重仓持股，享受主升浪。 |
    | **灯光闪绿** | **【变盘点】**。警惕资金偷跑，观察支撑。 |
    | **多重绿灯** | **【撤退令】**。执行止损，君子不立危墙。 |
    """)

st.divider()
st.caption(f"文哥哥专用 | 北京时间: {datetime.now(CN_TZ).strftime('%Y-%m-%d %H:%M')}")
