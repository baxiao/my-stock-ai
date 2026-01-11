import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
import time
from datetime import datetime

# --- 1. 页面配置 ---
st.set_page_config(page_title="文哥哥AI金融终端", page_icon="📈", layout="wide")

# --- 2. 持久化记忆 ---
if 'stock_data' not in st.session_state: st.session_state.stock_data = None
if 'ai_report' not in st.session_state: st.session_state.ai_report = None
if 'last_code' not in st.session_state: st.session_state.last_code = ""

# --- 3. 安全验证 ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.title("🔐 私人终端授权访问")
    if "access_password" in st.secrets:
        pwd_input = st.text_input("请输入密钥", type="password")
        if st.button("验证进入", use_container_width=True):
            if pwd_input == st.secrets["access_password"]:
                st.session_state['logged_in'] = True
                st.rerun()
            else:
                st.error("密钥错误")
    st.stop()

# --- 4. API 初始化 ---
client = OpenAI(api_key=st.secrets["deepseek_api_key"], base_url="https://api.deepseek.com")

# --- 5. 核心：获取秒级实时行情与主力 ---
def get_latest_all(code):
    # 实时快照
    df_spot = ak.stock_zh_a_spot_em()
    spot = df_spot[df_spot['代码'] == code].iloc[0]
    
    # 主力流向
    mkt = "sh" if code.startswith(('6', '9', '688')) else "sz"
    df_fund = ak.stock_individual_fund_flow(stock=code, market=mkt)
    fund = df_fund.iloc[0] if not df_fund.empty else None
    
    return spot, fund

# --- 6. 主界面 ---
st.title("🚀 文哥哥 AI 决策终端")

with st.sidebar:
    st.header("🔍 配置")
    raw_code = st.text_input("股票代码", value="600519").strip()
    if raw_code != st.session_state.last_code:
        st.session_state.stock_data = None
        st.session_state.ai_report = None
        st.session_state.last_code = raw_code
    if st.button("🔴 退出"):
        st.session_state['logged_in'] = False
        st.rerun()

tab1, tab2 = st.tabs(["🧠 AI 极速决策", "🎯 主力实时雷达"])

# --- Tab 1: AI 极速决策 ---
with tab1:
    if st.button("🚀 开启极速建模", use_container_width=True):
        # 使用 status 容器，进度条更稳固
        with st.status("正在执行 AI 深度分析...", expanded=True) as status:
            try:
                st.write("📡 采集秒级实时行情...")
                spot, _ = get_latest_all(raw_code)
                
                st.write("🧠 接入 DeepSeek 极速通道...")
                # 精简后的 Prompt，要求 AI 快速输出
                prompt = f"股票:{spot['名称']}，现价:{spot['最新价']}。简要分析：1.决策(买/卖/观望) 2.支撑/压力位 3.核心逻辑。字数150以内。"
                
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=300, # 限制长度，加快速度
                    temperature=0.7
                )
                
                st.session_state.ai_report = {
                    "content": response.choices[0].message.content,
                    "price": spot['最新价'],
                    "time": datetime.now().strftime('%H:%M:%S')
                }
                status.update(label="✅ 分析完成", state="complete", expanded=False)
            except Exception as e:
                st.error(f"分析失败: {e}")

    if st.session_state.ai_report:
        rep = st.session_state.ai_report
        st.success(f"**实时价格: ¥{rep['price']}** (更新于 {rep['time']})")
        st.markdown(rep['content'])
        st.code(rep['content']) # 一键复制

# --- Tab 2: 主力实时雷达 ---
with tab2:
    if st.button("📡 扫描实时资金", use_container_width=True):
        with st.status("数据拦截中...", expanded=True) as status:
            try:
                spot, fund = get_latest_all(raw_code)
                st.session_state.stock_data = {"spot": spot, "fund": fund}
                status.update(label="✅ 同步成功", state="complete", expanded=False)
            except Exception as e:
                st.error(f"同步失败: {e}")

    if st.session_state.stock_data:
        sd = st.session_state.stock_data
        spot = sd['spot']
        fund = sd['fund']
        
        # 主力进场显示
        inflow = float(str(fund['主力净流入-净额']).replace('万','')) if fund is not None else 0
        status_color = "🔴 主力正在疯狂买入" if inflow > 0 else "🟢 主力正在离场观望"
        st.subheader(status_color)
        
        c1, c2, c3 = st.columns(3)
        c1.metric("最新价", f"¥{spot['最新价']}", f"{spot['涨跌幅']}%")
        c2.metric("主力流入", f"{fund['主力净流入-净额']}" if fund is not None else "N/A")
        c3.metric("资金净占比", f"{fund['主力净流入-净占比']}%" if fund is not None else "N/A")
        
        # 简单走势图
        df_hist = ak.stock_zh_a_hist(symbol=raw_code, period="daily", adjust="qfq").tail(20)
        st.line_chart(df_hist.set_index('日期')['收盘'])
    else:
        st.info("💡 点击按钮获取秒级主力动态")

st.divider()
st.caption("文哥哥专属版 | 极速响应 | 杜绝乱码")
