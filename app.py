# app.py  —— 文哥哥极速终端（第一次优化版）
import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
import pytz, time, os
from concurrent.futures import ThreadPoolExecutor

# -------------------- 0. 页面配置 --------------------
st.set_page_config(page_title="文哥哥极速终端", page_icon="🚀", layout="wide")

# -------------------- 1. 密钥检测 --------------------
for k in ("deepseek_api_key", "access_password"):
    if k not in st.secrets:
        st.error(f"❌ 请在 Secrets 中配置 {k}"); st.stop()

# -------------------- 2. 状态初始化 --------------------
defaults = dict(
    logged_in=False,
    ai_cache="",
    last_data=None,
    last_code="",
    auto_refresh=False,
    stop_loss=0.0,
    take_profit=0.0,
)
for k, v in defaults.items():
    st.session_state.setdefault(k, v)

CN_TZ = pytz.timezone("Asia/Shanghai")
executor = ThreadPoolExecutor(max_workers=2)

# -------------------- 3. 登录控制 --------------------
if not st.session_state.logged_in:
    st.title("🔐 文哥哥私人终端")
    pwd = st.text_input("访问密钥", type="password")
    if st.button("开启终端", use_container_width=True):
        if pwd == st.secrets["access_password"]:
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.error("密钥错误")
    st.stop()

client = OpenAI(api_key=st.secrets["deepseek_api_key"], base_url="https://api.deepseek.com")

# -------------------- 4. 工具函数 --------------------
def format_money(v):
    try:
        v = float(v)
        if abs(v) >= 1e8:
            return f"{v/1e8:.2f} 亿"
        return f"{v/1e4:.1f} 万"
    except: return "N/A"

@st.cache_data(ttl=8)
def get_stock_data(code: str):
    try:
        df = ak.stock_zh_a_hist(symbol=code, period="1", adjust="qfq")
        if df.empty: return None
        df = df.rename(columns=str.lower)
        last = df.iloc[-1]
        mkt = "sh" if code.startswith(("6","9")) else "sz"
        fund = ak.stock_individual_fund_flow(stock=code, market=mkt)
        return dict(price=last["收盘"], pct=last["涨跌幅"], df=df,
                    fund=fund.iloc[0] if not fund.empty else None)
    except Exception as e:
        st.error(f"akshare 异常：{e}")
        return None

def four_lights(data):
    if data is None:
        return {"trend":"⚪","money":"⚪","sentiment":"⚪","safety":"⚪"}
    df, fund = data["df"], data["fund"]
    close = df["收盘"]
    ma5, ma20 = close.tail(5).mean(), close.tail(20).mean()
    trend = "🔴" if ma5 > ma20 else "🟢"
    if abs(ma5 - ma20) / ma20 < 0.01: trend = "⚪"      # 横盘
    money = "🔴" if fund and fund.get("主力净流入-净额", 0) > 0 else "🟢"
    sentiment = "🔴" if data["pct"] > 0 else "🟢"
    small_ratio = float(fund.get("小单净流入-净占比", 0)) if fund else 0
    safety = "🟢" if small_ratio < 15 else "🔴"         # 散户少=安全
    return dict(trend=trend, money=money, sentiment=sentiment, safety=safety)

# -------------------- 5. 侧边栏 --------------------
with st.sidebar:
    st.title("🚀 控制中心")
    code = st.text_input("股票代码", value="600519").strip()
    if code != st.session_state.last_code:
        st.session_state.last_code = code
        st.session_state.ai_cache = ""
        st.session_state.last_data = None
    st.session_state.auto_refresh = st.checkbox("🔄 秒级无闪刷新", value=st.session_state.auto_refresh)
    st.number_input("止损价", value=0.0, step=0.01, key="stop_loss")
    st.number_input("目标价", value=0.0, step=0.01, key="take_profit")
    if st.button("🔴 退出系统"):
        st.session_state.logged_in = False
        st.rerun()

st.title(f"📈 文哥哥 AI 终端 · {code}")
tab1, tab2 = st.tabs(["🧠 AI 深度决策", "🎯 实时资金雷达"])

# -------------------- 6. AI 决策 --------------------
with tab1:
    if st.button("🚀 启动全维度 AI 建模", use_container_width=True):
        with st.spinner("深度建模中..."):
            data = get_stock_data(code)
            lights = four_lights(data)
            prompt = (f"你是私募总监，请用中文给出：1.战术评级(全线进攻/逢高减仓/空仓观望)；"
                      f"2.核心理由；3.关键博弈位(支撑/压力)；4.一句话锦囊。股票={code} "
                      f"价格={data['price']} 四灯={lights} 止损={st.session_state.stop_loss} "
                      f"目标={st.session_state.take_profit}")
            resp = client.chat.completions.create(model="deepseek-chat",
                                                  messages=[{"role":"user","content":prompt}])
            st.session_state.ai_cache = resp.choices[0].message.content
    if st.session_state.ai_cache:
        st.info(st.session_state.ai_cache)

# -------------------- 7. 实时雷达 --------------------
with tab2:
    ph = st.empty()
    def render():
        data = get_stock_data(code) or st.session_state.last_data
        if data is None:
            ph.warning("等待行情...")
            return
        st.session_state.last_data = data
        lights = four_lights(data)
        df_light = pd.DataFrame({
            "维度": ["趋势","资金","情绪","安全"],
            "红灯🔴": ["MA5>MA20 攻击形态","主力净流入","价格上涨","散户<15%"],
            "绿灯🟢": ["MA5<MA20 重心下移","主力净流出","价格下跌","散户>15%"],
            "当前": [lights[k] for k in ("trend","money","sentiment","safety")]
        })
        with ph.container():
            st.subheader("🚦 核心策略哨兵")
            st.dataframe(df_light, use_container_width=True, hide_index=True)
            st.caption("⚪=横盘/无量  🟢=空头信号  🔴=多头信号")
            col1, col2 = st.columns(2)
            col1.metric("当前价", f"¥{data['price']}", f"{data['pct']}%")
            main = data["fund"]["主力净流入-净额"] if data["fund"] else 0
            col2.metric("主力净额", format_money(main), "多方" if main>0 else "空方")
            st.line_chart(data["df"].set_index("日期")["收盘"], height=200)
    if st.session_state.auto_refresh:
        while st.session_state.auto_refresh:
            render()
            time.sleep(1)
    else:
        render()

st.divider()
st.caption("文哥哥专用 | " + dt.now(CN_TZ).strftime("%Y-%m-%d %H:%M"))
