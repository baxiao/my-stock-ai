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
    df = data['df']
    fund = data['fund']
    
    # 1. 趋势灯 (MA5 vs MA20)
    ma5 = df['收盘'].tail(5).mean()
    ma20 = df['收盘'].tail(20).mean()
    trend_lamp = "🟢" if ma5 > ma20 else "🔴"
    
    # 2. 资金灯 (主力流入是否为正)
    money_lamp = "🔴"
    if fund is not None:
        if "-" not in str(fund['主力净流入-净额']):
            money_lamp = "🟢"
            
    # 3. 情绪灯 (当日涨幅 > 0)
    sentiment_lamp = "🟢" if data['pct'] > 0 else "🔴"
    
    # 4. 安全灯 (散户占比是否 < 20%)
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

tab1, tab2, tab3 = st.tabs(["🧠 AI 深度决策", "🎯 资金追踪雷达", "🕯️ 四灯算法说明"])

# --- Tab 1: AI 决策 ---
with tab1:
    if st.button("🚀 启动全维度 AI 建模", use_container_width=True):
        with st.status("正在进行全维度建模与四灯扫描...", expanded=True) as status:
            data = get_stock_all_data(code)
            if data["success"]:
                lamps = calculate_four_lamps(data)
                lamp_str = f"趋势:{lamps['trend']}, 资金:{lamps['money']}, 情绪:{lamps['sentiment']}, 安全:{lamps['safety']}"
                
                news_text = "\n".join(data['news'])
                prompt = f"分析股票 {code}。价格:{data['price']}, 涨跌:{data['pct']}%。四灯状态:{lamp_str}。新闻:{news_text}。请按5部分分析(决策、周预测、月预测、空间、总结)，总结需结合四灯表现。"
                
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[{"role": "system", "content": "金融专家"}, {"role": "user", "content": prompt}],
                    max_tokens=800, temperature=0.2 
                )
                st.session_state.ai_cache = {"content": response.choices[0].message.content, "price": data['price'], "lamps": lamps}
                status.update(label="✅ 分析完成", state="complete")

    if st.session_state.ai_cache:
        c = st.session_state.ai_cache
        l = c['lamps']
        st.subheader(f"🚦 实时四灯状态：趋势{l['trend']} | 资金{l['money']} | 情绪{l['sentiment']} | 安全{l['safety']}")
        st.markdown(c['content'])
        st.code(c['content'])

# --- Tab 2: 资金追踪雷达 ---
with tab2:
    if st.button("📡 扫描六大板块资金博弈", use_container_width=True):
        data = get_stock_all_data(code)
        if data["success"]: st.session_state.fund_cache = data
    
    if st.session_state.fund_cache:
        d = st.session_state.fund_cache
        f = d['fund']
        if f is not None:
            c1, c2, c3 = st.columns(3)
            c4, c5, c6 = st.columns(3)
            c1.metric("🏢 1.机构投资者", f['超大单净流入-净额'])
            c2.metric("🔥 2.游资动向", f['大单净流入-净额'])
            c3.metric("🐂 3.大户/牛散", f['中单净流入-净额'])
            c4.metric("🤖 4.量化资金", "🤖 算法扫描中")
            c5.metric("🏭 5.产业资金", f['主力净流入-净额'])
            c6.metric("🐣 6.散户群体", f['小单净流入-净额'])
            st.divider()
            st.table(pd.DataFrame({"板块": ["机构", "游资", "牛散", "散户"], "流入占比": [f"{f['超大单净流入-净占比']}%", f"{f['大单净流入-净占比']}%", f"{f['中单净流入-净占比']}%", f"{f['小单净流入-净占比']}%"]}))
            st.line_chart(d['df'].set_index('日期')['收盘'])

# --- Tab 3: 四灯算法说明书 ---
with tab3:
    st.header("📖 文哥哥私人·四灯算法说明书")
    st.info("四灯算法是基于‘趋势、资金、情绪、筹码’四个维度设计的极简决策模型。")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        ### 1. 📈 趋势灯 (Trend)
        - **核心逻辑**：基于 MA5（短期趋势）与 MA20（中期支撑）的关系。
        - **🟢 绿灯**：MA5 > MA20，处于上升通道或多头排列。
        - **🔴 红灯**：MA5 < MA20，趋势走弱或处于调整阶段。
        
        ### 2. 💰 资金灯 (Money)
        - **核心逻辑**：监测主力（超大+大单）真实净流入。
        - **🟢 绿灯**：主力资金净流入为正，大资金正在买入。
        - **🔴 红灯**：主力资金净流出，资金撤离中。
        """)
    with col2:
        st.markdown("""
        ### 3. 🎭 情绪灯 (Sentiment)
        - **核心逻辑**：盘面即时反馈与涨跌幅表现。
        - **🟢 绿灯**：价格正增长，市场人气活跃。
        - **🔴 红灯**：价格下跌，恐慌或冷清。
        
        ### 4. 🛡️ 安全灯 (Safety)
        - **核心逻辑**：散户参与度（反向指标）。
        - **🟢 绿灯**：散户流入占比 < 20%，筹码集中在专业资金手中。
        - **🔴 红灯**：散户大量接盘，筹码松散，风险加大。
        """)
    st.warning("⚠️ 决策建议：三灯以上转绿为【强攻区】，两灯以下建议【观望】或【减仓】。")

st.divider()
st.caption("文哥哥专用 | 四灯算法增强版 | 6大资金板块透视")
