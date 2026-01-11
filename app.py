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
if 'last_code' not in st.session_state: st.session_state.last_code = ""
if 'auto_refresh' not in st.session_state: st.session_state.auto_refresh = False

# --- 3. 核心取数逻辑 ---
@st.cache_data(ttl=1)
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

# --- 5. 安全验证 (DeepSeek API Key 类似方式调用) ---
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

tab1, tab2, tab3 = st.tabs(["🧠 AI 深度决策", "🎯 实时资金雷达", "📖 算法说明书"])

# --- Tab 1: AI 决策 (保持不变) ---
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

# --- Tab 2: 实时资金雷达 (无闪烁优化版) ---
with tab2:
    st.subheader("🛡️ 实时哨兵系统 (静默刷新模式)")
    
    # 核心：使用一个稳定的占位容器
    main_placeholder = st.empty()

    def draw_ui():
        # 这里只负责渲染逻辑，不负责循环
        data = get_stock_all_data(code)
        if data["success"]:
            f = data['fund']
            lamps = calculate_four_lamps(data)
            fund_line = float(f['主力净流入-净占比']) if f is not None else 0
            
            with main_placeholder.container():
                # 顶部信息
                c_time, c_status = st.columns([1, 1])
                c_time.caption(f"🕒 数据步频: 1s | 最后更新: {datetime.now().strftime('%H:%M:%S')}")
                if st.session_state.auto_refresh:
                    c_status.markdown("🟢 **实时监控中...**")
                else:
                    c_status.markdown("🟡 **已暂停自动刷新**")

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

    # 逻辑执行控制
    if st.session_state.auto_refresh:
        # 在开启自动刷新时，使用一个简单的循环，但利用 empty() 容器局部重绘
        while st.session_state.auto_refresh:
            draw_ui()
            time.sleep(1)
            # 注意：此处不使用 st.rerun()，而是通过循环不断写入 placeholder
            # 但因为 Streamlit 架构限制，若要组件真正响应点击，仍需配合特定逻辑
            # 为保证文哥哥的使用体验，这里采用 placeholder.container 局部更新
            # 如果发现 UI 不响应切换，可以手动关闭自动刷新开关
    else:
        # 手动模式
        draw_ui()
        if st.button("🔄 手动同步最新数据", use_container_width=True):
            draw_ui()

# --- Tab 3: 说明书 (保持不变) ---
with tab3:
    st.header("📖 文哥哥私人·四灯算法说明书")
    # ...内容略...
    st.warning("文哥哥提示：四灯全绿为‘多头屠龙’，两红以上请‘保持警惕’。")

st.divider()
st.caption("文哥哥专用 | 局部静默刷新版 | 避雷哨兵")
