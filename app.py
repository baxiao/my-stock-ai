import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
import time
from datetime import datetime

# --- 1. 页面配置 ---
st.set_page_config(page_title="文哥哥极速终端", page_icon="🚀", layout="wide")

# --- 2. 持久化记忆 (切换TAB不消失) ---
if 'ai_cache' not in st.session_state: st.session_state.ai_cache = None
if 'fund_cache' not in st.session_state: st.session_state.fund_cache = None
if 'last_code' not in st.session_state: st.session_state.last_code = ""

# --- 3. 核心取数逻辑 ---
@st.cache_data(ttl=60)
def get_stock_all_data(code):
    try:
        # A. 基础行情
        df_hist = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq").tail(30)
        if df_hist.empty: return {"success": False, "msg": "代码错误"}
        latest = df_hist.iloc[-1]
        
        # B. 实时新闻
        try:
            news_df = ak.stock_news_em(symbol=code).head(5)
            news_list = news_df['新闻标题'].tolist() if not news_df.empty else ["暂无最新新闻"]
        except:
            news_list = ["新闻接口延迟"]

        # C. 资金占比与流向
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

# --- 4. 辅助：查询倒计时组件 ---
def processing_timer(duration=10):
    """显示倒计时进度条"""
    p_bar = st.progress(0)
    msg = st.empty()
    for i in range(duration):
        countdown = duration - i
        p_bar.progress((i + 1) * (100 // duration))
        msg.warning(f"⏳ 文哥哥请稍等，深度分析中... 剩余 {countdown} 秒")
        time.sleep(1)
    msg.empty()
    p_bar.empty()

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

tab1, tab2 = st.tabs(["🧠 AI 深度决策", "🎯 主力追踪雷达"])

# --- Tab 1: AI 决策 ---
with tab1:
    if st.button("🚀 启动全维度 AI 建模", use_container_width=True):
        # 启动倒计时
        processing_timer(5)
        
        with st.status("正在注入多源数据...", expanded=True) as status:
            data = get_stock_all_data(code)
            if data["success"]:
                fund_dir = "暂无"
                if data['fund'] is not None:
                    val = str(data['fund']['主力净流入-净额'])
                    fund_dir = f"主力净流入 {val} (" + ("进场" if "-" not in val else "离场") + ")"
                
                news_str = "\n".join(data['news'])
                prompt = f"分析股票 {code}。价格:{data['price']}, 涨幅:{data['pct']}%, 资金:{fund_dir}, 新闻:{news_str}。请按5个部分回复(决策、周预测、月预测、空间、总结)，每个标题一行。"
                
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[{"role": "system", "content": "金融专家"}, {"role": "user", "content": prompt}],
                    max_tokens=800, temperature=0.2 
                )
                st.session_state.ai_cache = {"content": response.choices[0].message.content, "price": data['price']}
                status.update(label="✅ 分析完成", state="complete")

    if st.session_state.ai_cache:
        c = st.session_state.ai_cache
        st.success(f"**基准价**: ¥{c['price']}")
        st.markdown(c['content'])
        st.code(c['content'])

# --- Tab 2: 主力雷达 ---
with tab2:
    if st.button("📡 扫描实时主力动态", use_container_width=True):
        processing_timer(3) # 资金扫描只需3秒
        data = get_stock_all_data(code)
        if data["success"]:
            st.session_state.fund_cache = data
    
    if st.session_state.fund_cache:
        d = st.session_state.fund_cache
        if d['fund'] is not None:
            f = d['fund']
            inflow = str(f['主力净流入-净额'])
            status_msg = f"🔴 主力净流入: {inflow} (强势入场)" if "-" not in inflow else f"🟢 主力净流入: {inflow} (获利离场)"
            st.subheader(status_msg)
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("价格", f"¥{d['price']}", f"{d['pct']}%")
            c2.metric("主力占比", f"{f['主力净流入-净占比']}%")
            c3.metric("超大单占比", f"{f['超大单净流入-净占比']}%")
            c4.metric("中单占比", f"{f['中单净流入-净占比']}%")
            
            st.write("---")
            st.subheader("📰 核心舆情支持")
            for n in d['news']:
                st.write(f"· {n}")
        
        st.write("---")
        st.line_chart(d['df'].set_index('日期')['收盘'])

st.divider()
st.caption("文哥哥专用 | 倒计时安全查询模式 | 稳定运行版")
