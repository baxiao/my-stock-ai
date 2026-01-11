import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
import time

# --- 1. 页面配置 ---
st.set_page_config(page_title="文哥哥极速终端", page_icon="🚀", layout="wide")

# --- 2. 核心数据抓取（带 60 秒缓存，防止进程堆积） ---
@st.cache_data(ttl=60)
def fetch_stock_data(code):
    """单股精准抓取，极速响应"""
    try:
        # 获取基础行情
        info = ak.stock_individual_info_em(symbol=code)
        name = info[info['item'] == '股票名称']['value'].values[0]
        price = info[info['item'] == '最新价']['value'].values[0]
        pct = info[info['item'] == '当日涨跌幅']['value'].values[0]
        
        # 获取资金流向
        mkt = "sh" if code.startswith(('6', '9', '688')) else "sz"
        fund_df = ak.stock_individual_fund_flow(stock=code, market=mkt)
        fund = fund_df.iloc[0] if not fund_df.empty else None
        
        return {"name": name, "price": price, "pct": pct, "fund": fund, "success": True}
    except Exception as e:
        return {"success": False, "msg": str(e)}

# --- 3. 安全验证 ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.title("🔐 私人终端授权")
    pwd = st.text_input("请输入访问密钥", type="password")
    if st.button("开启终端", use_container_width=True):
        if "access_password" in st.secrets and pwd == st.secrets["access_password"]:
            st.session_state['logged_in'] = True
            st.rerun()
        else:
            st.error("密钥无效")
    st.stop()

# --- 4. API 初始化 ---
client = OpenAI(api_key=st.secrets["deepseek_api_key"], base_url="https://api.deepseek.com")

# --- 5. 主界面布局 ---
st.title("🚀 文哥哥 AI 决策终端")

with st.sidebar:
    st.header("🔍 查询配置")
    code = st.text_input("股票代码", value="600519").strip()
    st.divider()
    if st.button("🔴 退出系统", use_container_width=True):
        st.session_state['logged_in'] = False
        st.rerun()

# 定义 Tab
tab1, tab2 = st.tabs(["🧠 DeepSeek 深度决策", "🎯 主力追踪雷达"])

# --- Tab 1: AI 决策 ---
with tab1:
    if st.button("🚀 启动极速建模分析", use_container_width=True):
        with st.status("正在秒杀查询...", expanded=True) as status:
            data = fetch_stock_data(code)
            if data["success"]:
                status.write("📡 行情已锁定，调取 AI 逻辑...")
                # 极简 Prompt 确保 3 秒回传
                prompt = f"股票:{data['name']}, 现价:{data['price']}, 涨幅:{data['pct']}%。请给结论:1.决策(买/卖/观望) 2.压力/支撑位 3.一句话理由。限50字。"
                
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=150
                )
                ai_res = response.choices[0].message.content
                
                st.success(f"**{data['name']}** 当前价: ¥{data['price']}")
                st.info(ai_res)
                st.code(ai_res) # 一键复制
                status.update(label="✅ 分析完成", state="complete")
            else:
                st.error(f"查询失败: {data['msg']}")

# --- Tab 2: 主力雷达 ---
with tab2:
    if st.button("📡 扫描主力动态", use_container_width=True):
        with st.spinner("正在拦截主力筹码..."):
            data = fetch_stock_data(code)
            if data["success"]:
                f = data['fund']
                # 主力状态判断
                inflow_str = str(f['主力净流入-净额'])
                is_in = "-" not in inflow_str
                
                if is_in:
                    st.error(f"🔴 主力正在强势进场: {inflow_str}")
                else:
                    st.success(f"🟢 主力正在洗盘离场: {inflow_str}")
                
                c1, c2, c3 = st.columns(3)
                c1.metric("最新价", f"¥{data['price']}", f"{data['pct']}%")
                c2.metric("主力流入", inflow_str)
                c3.metric("净占比", f"{f['主力净流入-净占比']}%")
                
                # 趋势小图
                df_hist = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq").tail(15)
                st.line_chart(df_hist.set_index('日期')['收盘'])
            else:
                st.error("无法获取资金数据")

st.divider()
st.caption("文哥哥专用 | 缓存保护已开启 | 拒绝卡顿")
