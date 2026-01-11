import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
import time
from datetime import datetime

# --- 1. 页面基础配置 ---
st.set_page_config(page_title="文哥哥AI金融终端", page_icon="📈", layout="wide")

# --- 2. 初始化持久化记忆 (Session State) ---
if 'stock_data' not in st.session_state:
    st.session_state.stock_data = None  # 存储主力行情
if 'ai_report' not in st.session_state:
    st.session_state.ai_report = None   # 存储AI报告
if 'last_code' not in st.session_state:
    st.session_state.last_code = ""     # 存储上一次查询的代码

# --- 3. 安全验证 ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.title("🔐 私人终端授权访问")
    if "access_password" in st.secrets:
        pwd_input = st.text_input("请输入访问密钥", type="password")
        if st.button("开启终端"):
            if pwd_input == st.secrets["access_password"]:
                st.session_state['logged_in'] = True
                st.rerun()
            else:
                st.error("密钥无效")
    else:
        st.error("⚠️ 请在后台 Secrets 中设置 access_password")
    st.stop()

# --- 4. 核心 API 初始化 ---
client = OpenAI(api_key=st.secrets["deepseek_api_key"], base_url="https://api.deepseek.com")

# --- 5. 主程序界面 ---
st.title("🚀 文哥哥 A股 AI 极速决策终端")

with st.sidebar:
    st.header("🔍 配置中心")
    raw_code = st.text_input("📍 股票代码", value="600519").strip()
    time_span = st.select_slider(
        "⏳ 分析跨度",
        options=["近一周", "近一月", "近三月", "近半年", "近一年"],
        value="近三月"
    )
    
    # 如果代码变了，清空之前的记忆
    if raw_code != st.session_state.last_code:
        st.session_state.stock_data = None
        st.session_state.ai_report = None
        st.session_state.last_code = raw_code

    st.divider()
    if st.button("🔴 安全退出"):
        st.session_state['logged_in'] = False
        st.rerun()

tab1, tab2 = st.tabs(["🎯 主力追踪雷达", "🧠 DeepSeek 深度决策"])

# --- 功能一：主力查询 ---
with tab1:
    if st.button("📡 执行主力扫描"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            status_text.text("正在建立安全连接...")
            time.sleep(0.3)
            progress_bar.progress(20)
            
            status_text.text(f"正在抓取 {raw_code} 最新行情数据...")
            df_hist = ak.stock_zh_a_hist(symbol=raw_code, period="daily", adjust="qfq")
            df_hist = df_hist.sort_values(by="日期", ascending=False)
            latest_data = df_hist.iloc[0]
            progress_bar.progress(50)
            
            status_text.text("正在拦截主力大单筹码...")
            mkt = "sh" if raw_code.startswith(('6', '9', '688')) else "sz"
            try:
                df_fund = ak.stock_individual_fund_flow(stock=raw_code, market=mkt)
                latest_fund = df_fund.iloc[0] if not df_fund.empty else None
            except:
                latest_fund = None
            progress_bar.progress(80)
            
            status_text.text("正在生成可视化看板...")
            # 将结果存入记忆
            st.session_state.stock_data = {
                "latest": latest_data,
                "fund": latest_fund,
                "hist": df_hist.head(30)
            }
            progress_bar.progress(100)
            time.sleep(0.5)
            status_text.empty()
            progress_bar.empty()
            
        except Exception as e:
            st.error(f"查询失败: {e}")

    # --- 显示主力数据 (从记忆中读取) ---
    if st.session_state.stock_data:
        data = st.session_state.stock_data
        st.subheader(f"📊 实时行情看板 (截至: {data['latest']['日期']})")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("最新价", f"¥{data['latest']['收盘']}", f"{data['latest']['涨跌幅']}%")
        c2.metric("成交额", f"{data['latest']['成交额']/1e8:.2f}亿")
        
        if data['fund'] is not None:
            c3.metric("主力流入", f"{data['fund']['主力净流入-净额']}")
            c4.metric("净占比", f"{data['fund']['主力净流入-净占比']}%")
        
        st.write("---")
        st.write("📈 **近期价格趋势 (30个交易日)**")
        st.line_chart(data['hist'].sort_values(by="日期").set_index('日期')['收盘'])
    else:
        st.info("💡 请点击上方按钮开始扫描主力信号")

# --- 功能二：AI 深度决策 ---
with tab2:
    if st.button("🚀 启动 AI 建模分析"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        span_days = {"近一周": 5, "近一月": 20, "近三月": 60, "近半年": 120, "近一年": 250}
        
        try:
            status_text.text("正在调取历史K线分布...")
            df_hist = ak.stock_zh_a_hist(symbol=raw_code, period="daily", adjust="qfq")
            df_hist = df_hist.sort_values(by="日期", ascending=False).head(span_days[time_span])
            latest_date = df_hist.iloc[0]['日期']
            progress_bar.progress(30)
            
            status_text.text("正在接入 DeepSeek-V3 决策模型...")
            prompt = f"""
            分析A股代码 {raw_code}，截至日期 {latest_date}。
            请根据最近 {time_span} 走势给出决策：
            1.【建议决策】：明确给出【建议购入】、【建议出手】或【暂时观望】。
            2.【目标预测】：未来3个月的目标价格区间。
            3.【空间分析】：最新的核心支撑位和压力位。
            4.【趋势总结】：分析当前强弱状态。
            """
            
            response = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}])
            st.session_state.ai_report = {
                "content": response.choices[0].message.content,
                "date": latest_date
            }
            progress_bar.progress(100)
            time.sleep(0.5)
            status_text.empty()
            progress_bar.empty()
            
        except Exception as e:
            st.error(f"AI 分析失败: {e}")

    # --- 显示 AI 报告 (从记忆中读取) ---
    if st.session_state.ai_report:
        report = st.session_state.ai_report
        st.subheader(f"📋 AI 投资决策研报 (截至: {report['date']})")
        st.info(report['content'])
        
        st.write("📖 **点击下方代码框右上角一键复制报告：**")
        st.code(report['content'], language="markdown")
    else:
        st.info("💡 请点击上方按钮启动 AI 深度建模")

st.divider()
st.caption("文哥哥 AI 终端 | 提示：切换标签页内容已自动保留。")
