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

# --- 2. 初始化持久化状态 ---
if 'ai_cache' not in st.session_state: st.session_state.ai_cache = None
if 'last_data' not in st.session_state: st.session_state.last_data = None
if 'last_code' not in st.session_state: st.session_state.last_code = ""
if 'auto_refresh' not in st.session_state: st.session_state.auto_refresh = False

CN_TZ = pytz.timezone('Asia/Shanghai')

# --- 3. 核心工具函数 ---
def format_money(value_str):
    """智能单位转换：亿/万自动切换"""
    try:
        val = float(value_str)
        abs_val = abs(val)
        if abs_val >= 100000000:
            return f"{val / 100000000:.2f} 亿"
        else:
            return f"{val / 10000:.1f} 万"
    except:
        return "N/A"

# --- 4. 多线程数据引擎 ---
def fetch_hist_data(code):
    return ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq").tail(30)

def fetch_fund_flow(code):
    mkt = "sh" if code.startswith(('6', '9', '688')) else "sz"
    return ak.stock_individual_fund_flow(stock=code, market=mkt)

@st.cache_data(ttl=2)
def get_stock_complete_data(code):
    """使用线程池并发抓取数据，提升响应速度"""
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_hist = executor.submit(fetch_hist_data, code)
            future_fund = executor.submit(fetch_fund_flow, code)
            
            df_hist = future_hist.result()
            df_fund = future_fund.result()

        if df_hist.empty:
            return {"success": False, "msg": "未找到代码"}
        
        fund = df_fund.iloc[0] if not df_fund.empty else None
        
        return {
            "success": True, 
            "price": df_hist.iloc[-1]['收盘'], 
            "pct": df_hist.iloc[-1]['涨跌幅'],
            "vol": df_hist.iloc[-1]['成交额'],
            "fund": fund, 
            "df": df_hist
        }
    except Exception as e:
        return {"success": False, "msg": f"接口繁忙: {str(e)}"}

# --- 5. 四灯量化算法 ---
def calculate_four_lamps(data):
    if not data or not data.get('success'):
        return {"trend": "⚪", "money": "⚪", "sentiment": "⚪", "safety": "⚪"}
    df = data['df']
    fund = data['fund']
    ma5 = df['收盘'].tail(5).mean()
    ma20 = df['收盘'].tail(20).mean()
    
    # 🔴正面/强势  🟢负面/风险
    trend_lamp = "🔴" if ma5 > ma20 else "🟢"
    money_lamp = "🟢"
    if fund is not None:
        if "-" not in str(fund['主力净流入-净额']): money_lamp = "🔴"
    sentiment_lamp = "🔴" if data['pct'] > 0 else "🟢"
    safety_lamp = "🟢"
    if fund is not None:
        try:
            # 散户流出（负值）或占比极低为🔴安全
            if float(fund['小单净流入-净占比']) < 15: safety_lamp = "🔴"
        except: pass
    return {"trend": trend_lamp, "money": money_lamp, "sentiment": sentiment_lamp, "safety": safety_lamp}

# --- 6. 权限验证 (API Key模式) ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.title("🔐 私人量化终端授权")
    pwd = st.text_input("请输入访问密钥", type="password")
    if st.button("开启终端", use_container_width=True):
        if "access_password" in st.secrets and pwd == st.secrets["access_password"]:
            st.session_state['logged_in'] = True
            st.rerun()
        else:
            st.error("密钥无效")
    st.stop()

client = OpenAI(api_key=st.secrets["deepseek_api_key"], base_url="https://api.deepseek.com")

# --- 7. 侧边栏 ---
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

# --- Tab 1: AI 深度决策 (线程保护+专业模型) ---
with tab1:
    if st.button("🚀 启动全维度 AI 建模分析", use_container_width=True):
        progress_text = "多线程算力调取中..."
        my_bar = st.progress(0, text=progress_text)
        
        for p in range(0, 101, 10):
            time.sleep(0.05)
            my_bar.progress(p, text=progress_text)
        
        data = get_stock_complete_data(code)
        if data["success"]:
            lamps = calculate_four_lamps(data)
            lamp_str = f"趋势:{lamps['trend']}, 资金:{lamps['money']}, 情绪:{lamps['sentiment']}, 安全:{lamps['safety']}"
            
            # 增强型 Prompt：引入私募博弈视角
            prompt = f"""
            你是一位年化收益50%以上的私募操盘手，请对股票 {code} 进行深度复盘。
            当前数据：价格 {data['price']}, 涨跌幅 {data['pct']}%, 四灯状态 {lamp_str}。
            请结合以下维度给出结论：
            1. 筹码博弈：主力是否在进行“黄金坑”洗盘或高位“倒车接人”？
            2. 信号强度：如果四灯中出现红绿交替，是背离还是修复？
            3. 实战指令：给出明确的【买点/持股/卖点】参考位。
            4. 风险警示：当前最可能导致绿灯亮的突发因素。
            注意：严格遵循红涨绿跌、红强绿弱的逻辑。
            """
            
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "system", "content": "你是文哥哥的首席私募量化分析师。"}, {"role": "user", "content": prompt}]
            )
            st.session_state.ai_cache = {"content": response.choices[0].message.content}
            my_bar.empty()
            st.success("决策建议已更新")
            
    if st.session_state.ai_cache:
        st.markdown(st.session_state.ai_cache['content'])

# --- Tab 2: 实时资金雷达 (无闪烁+智能单位) ---
with tab2:
    monitor_placeholder = st.empty()
    
    def render_dashboard():
        res = get_stock_complete_data(code)
        if not res["success"] and st.session_state.last_data:
            data = st.session_state.last_data
            status_tag = "⚠️ 断流保护"
        elif res["success"]:
            data = res
            st.session_state.last_data = res
            status_tag = "🟢 线程连通"
        else:
            monitor_placeholder.warning("正在并发采集数据...")
            return

        f = data['fund']
        lamps = calculate_four_lamps(data)
        bj_time = datetime.now(CN_TZ).strftime('%H:%M:%S')
        
        with monitor_placeholder.container():
            st.caption(f"🕒 北京时间: {bj_time} | {status_tag} | 🔴正面 🟢风险")
            
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
            draw_lamp(l2, "主力动向", lamps['money'], "主力流入", "资金流出")
            draw_lamp(l3, "市场情绪", lamps['sentiment'], "买盘活跃", "信心不足")
            draw_lamp(l4, "筹码安全", lamps['safety'], "锁定良好", "散户接盘")

            st.write("---")
            m1, m2 = st.columns(2)
            m1.metric("📌 当前价位", f"¥{data['price']}", f"{data['pct']}%")
            main_f = data['fund']['主力净流入-净额'] if data['fund'] is not None else 0
            m2.metric("🌊 主力净额", format_money(main_f), "多方发力" if float(main_f) > 0 else "空方减速")
            
            st.write("---")
            st.write("📊 **6大资金板块明细 (亿/万自动转换)**")
            if f is not None:
                r1_c1, r1_c2, r1_c3 = st.columns(3)
                r2_c1, r2_c2, r2_c3 = st.columns(3)
                r1_c1.metric("🏢 机构投资者", format_money(f['超大单净流入-净额']))
                r1_c2.metric("🔥 游资动向", format_money(f['大单净流入-净额']))
                r1_c3.metric("🐂 大户牛散", format_money(f['中单净流入-净额']))
                r2_c1.metric("🤖 量化资金", "智能监控中")
                r2_c2.metric("🏭 产业资金", format_money(f['主力净流入-净额']))
                r2_c3.metric("🐣 散户群体", f"{float(f['小单净流入-净占比']):.1f} %")
            
            st.line_chart(data['df'].set_index('日期')['收盘'], height=200)

    if st.session_state.auto_refresh:
        while st.session_state.auto_refresh:
            render_dashboard()
            time.sleep(1)
    else:
        render_dashboard()

# --- Tab 3: 文哥哥·私募心法 (逻辑解析) ---
with tab3:
    st.markdown("## 📜 文哥哥·私募心法")
    
    st.info("💡 视觉核心：遵循 A 股特色，🔴 红色代表强度与机会，🟢 绿色代表走弱与风险。")
    st.write("---")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### **📈 趋势灯**：判死生。红灯是波段护城河。")
        st.markdown("#### **💰 资金灯**：辨真伪。红灯代表真金白银。")
    with col2:
        st.markdown("#### **🎭 情绪灯**：看人气。红灯是进场冲锋号。")
        st.markdown("#### **🛡️ 安全灯**：测底盘。红灯意味着筹码锁定。")
    st.success("🛡️ **文哥哥提醒：只做四灯红共振，坚决执行止损绿。**")

st.divider()
st.caption(f"文哥哥专用 | 2026.01.12 | 多线程并发决策版")
