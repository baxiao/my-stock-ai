import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
import time

# --- 1. 页面配置 ---
st.set_page_config(page_title="文哥哥AI金融终端", page_icon="📈", layout="wide")

st.markdown("""
    <style>
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .report-box { background-color: #ffffff; padding: 25px; border-radius: 15px; border: 1px solid #e0e0e0; border-left: 5px solid #ff4b4b; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 安全门禁系统 (从 Secrets 读取) ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.title("🛡️ 私人金融终端 - 身份验证")
    if "access_password" in st.secrets:
        pwd_input = st.text_input("请输入访问授权码：", type="password")
        if st.button("验证并进入"):
            if pwd_input == st.secrets["access_password"]:
                st.session_state['logged_in'] = True
                st.rerun()
            else:
                st.error("授权码错误")
    else:
        st.warning("⚠️ 请先在 Secrets 中设置 access_password")
    st.stop()

# --- 3. 核心 API 配置 ---
client = OpenAI(api_key=st.secrets["deepseek_api_key"], base_url="https://api.deepseek.com")

# --- 4. 辅助函数 ---
def get_market(code):
    return "sh" if code.startswith(('6', '9', '688')) else "sz"

# --- 5. 主界面布局 ---
st.title("🛡️ 文哥哥 A股主力雷达 & AI 深度分析")

with st.sidebar:
    st.header("🔍 分析配置")
    stock_code = st.text_input("股票代码", value="600519")
    
    # --- 新增：时间线选择 ---
    time_span = st.select_slider(
        "选择分析时间线：",
        options=["近一周", "近一月", "近三月", "近半年", "近一年"],
        value="近三月"
    )
    
    # 映射时间跨度对应的交易天数
    span_map = {"近一周": 5, "近一月": 20, "近三月": 60, "近半年": 120, "近一年": 250}
    lookback_days = span_map[time_span]
    
    st.divider()
    if st.button("🔴 安全退出系统"):
        st.session_state['logged_in'] = False
        st.rerun()

# --- 6. 执行逻辑 ---
if st.button("🚀 启动全维度交叉分析"):
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        # A. 实时行情与主力资金 (保持原有功能)
        status_text.text("📡 正在扫描主力资金雷达...")
        df_spot = ak.stock_zh_a_spot_em()
        spot = df_spot[df_spot['代码'] == stock_code].iloc[0]
        
        market = get_market(stock_code)
        df_fund = ak.stock_individual_fund_flow(stock=stock_code, market=market)
        latest_fund = df_fund.iloc[0]
        progress_bar.progress(30)
        
        # B. 历史趋势获取 (根据选定的时间线)
        status_text.text(f"📊 正在回溯{time_span}的市场表现...")
        hist_data = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq").tail(lookback_days)
        progress_bar.progress(60)
        
        # C. 顶部数据看板
        st.subheader(f"💎 {spot['名称']} ({stock_code}) 核心情报")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("最新价", f"¥{spot['最新价']}", f"{spot['涨跌幅']}%")
        c2.metric("主力净流入", f"{latest_fund['主力净流入-净额']}")
        c3.metric("主力净占比", f"{latest_fund['主力净流入-净占比']}%")
        c4.metric("分析时段", time_span)
        
        # D. 趋势展示
        st.write(f"**{time_span}走势可视化**")
        st.line_chart(hist_data.set_index('日期')['收盘'])
        
        # E. AI 深度决策 (融合主力数据 + 时间线)
        status_text.text("🤖 DeepSeek 正在进行多维度决策分析...")
        
        prompt = f"""
        你是一名资深A股首席分析师。请针对股票 {spot['名称']} ({stock_code}) 进行深度研报编写。
        
        【当前主力状态】
        - 实时主力净流入：{latest_fund['主力净流入-净额']}
        - 资金净占比：{latest_fund['主力净流入-净占比']}%
        
        【分析时间线：{time_span}】
        - 该周期内最高价：{hist_data['最高'].max()}
        - 该周期内最低价：{hist_data['最低'].min()}
        - 周期内波动幅度：{((hist_data['收盘'].iloc[-1] - hist_data['收盘'].iloc[0]) / hist_data['收盘'].iloc[0] * 100):.2f}%
        
        【要求】
        1. 【主力行为定性】：结合今日主力资金和{time_span}的趋势，判断主力是在持续吸筹、阶段性派发还是散户博弈？
        2. 【周期性买卖建议】：针对{time_span}的走势，给出明确的【买入/出手/观望】建议。
        3. 【目标价位】：给出接下来一个周期内的支撑位、压力位及预期目标价。
        4. 【风险评估】：评估目前位置的追高风险或筑底可靠性。
        """
        
        response = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}])
        progress_bar.progress(100)
        status_text.text("✅ 分析完成")
        
        st.divider()
        st.subheader(f"📋 AI 深度投研报告 ({time_span}维度)")
        st.markdown(f'<div class="report-box">{response.choices[0].message.content}</div>', unsafe_allow_html=True)
        
    except Exception as e:
        st.error(f"分析失败，请检查代码或重试: {e}")
    finally:
        time.sleep(2)
        progress_bar.empty()
        status_text.empty()

st.divider()
st.caption("风险提示：AI分析不构成投资建议，股市有风险，入市需谨慎。")
