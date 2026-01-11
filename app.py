import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
import time

# --- 1. 页面配置 ---
st.set_page_config(page_title="文哥哥AI金融终端", page_icon="📈", layout="wide")

# 自定义样式
st.markdown("""
    <style>
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .report-box { background-color: #ffffff; padding: 25px; border-radius: 15px; border: 1px solid #e0e0e0; line-height: 1.6; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 安全门禁系统 ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.title("🛡️ 私人金融终端 - 身份验证")
    if "access_password" in st.secrets:
        correct_password = st.secrets["access_password"]
        col_login, _ = st.columns([1, 1])
        with col_login:
            pwd_input = st.text_input("请输入访问授权码：", type="password")
            if st.button("验证并进入系统"):
                if pwd_input == correct_password:
                    st.session_state['logged_in'] = True
                    st.rerun()
                else:
                    st.error("授权码错误")
    else:
        st.warning("⚠️ 请先在 Secrets 中设置 access_password")
    st.stop()

# --- 3. 核心引擎加载 ---
client = OpenAI(api_key=st.secrets["deepseek_api_key"], base_url="https://api.deepseek.com")

# --- 4. 主界面布局 ---
st.title("🛡️ 文哥哥 A股 AI 智能情报站")

with st.sidebar:
    st.header("系统设置")
    stock_code = st.text_input("📍 输入股票代码", value="600519")
    # 增加分析跨度选项
    analysis_span = st.selectbox("分析时间跨度", ["近1年 (趋势版)", "近1个月 (短线版)"])
    st.divider()
    if st.button("🔴 安全退出系统"):
        st.session_state['logged_in'] = False
        st.rerun()

tab1, tab2 = st.tabs(["🔥 资金行情监控", "🧠 多维度 AI 决策"])

# --- 功能一：行情与趋势 ---
with tab1:
    if st.button("📡 扫描实时行情"):
        try:
            with st.spinner('正在调取深度行情数据...'):
                # 抓取实时行情
                df_all = ak.stock_zh_a_spot_em()
                target = df_all[df_all['代码'] == stock_code].iloc[0]
                
                # 抓取长达 250 天的历史数据（约 1 年）
                hist = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq").tail(250)
                
                st.subheader(f"📊 {target['名称']} ({stock_code}) 趋势看板")
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("最新价", f"¥{target['最新价']}", f"{target['涨跌幅']}%")
                m2.metric("成交额", target['成交额'])
                m3.metric("换手率", f"{target['换手率']}%")
                m4.metric("一年内高位", f"¥{hist['最高'].max()}")

                st.write("**过去一年走势图**")
                st.line_chart(hist.set_index('日期')['收盘'])
        except Exception as e:
            st.error(f"行情获取超时: {e}")

# --- 功能二：深度 AI 决策 (增加时间维度) ---
with tab2:
    if st.button("🚀 生成年度/季度深度投研书"):
        progress_bar = st.progress(0)
        try:
            st.write("正在结合历史一年的波动数据进行 AI 建模...")
            hist_data = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq").tail(250)
            
            # 计算一些简单的历史特征给 AI 参考
            avg_price = hist_data['收盘'].mean()
            max_price = hist_data['收盘'].max()
            min_price = hist_data['收盘'].min()
            
            prompt_ai = f"""
            你是一名深耕A股20年的资深首席分析师。请针对代码 {stock_code} 给出多维度的深度决策：
            
            【历史参考数据】
            - 过去250个交易日均价：{avg_price:.2f}
            - 年度最高位：{max_price:.2f}
            - 年度最低位：{min_price:.2f}

            【要求】请严格按以下模块输出，重点增加“时间周期”的分析：
            1. 【历史位置评估】：当前价格处于全年的高位、中位还是低位？
            2. 【分时周期策略】：
               - 短线建议（1-5天）：
               - 中线建议（1-3个月）：
               - 长线建议（1年以上）：
            3. 【买卖建议】：明确给出结论（如：强烈建议购入、逢高减持、或持筹观望）。
            4. 【目标价预判】：给出未来一个季度和一年的预期目标价格。
            """
            
            progress_bar.progress(50)
            response = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt_ai}])
            progress_bar.progress(100)
            
            st.divider()
            st.subheader(f"📋 {stock_code} 全周期投研报告")
            st.markdown(f'<div class="report-box">{response.choices[0].message.content}</div>', unsafe_allow_html=True)
            
        except Exception as e:
            st.error(f"AI 决策引擎繁忙: {e}")
        finally:
            progress_bar.empty()

st.divider()
st.caption("风险提示：本程序提供的所有信息仅供 AI 实验参考，不构成任何投资建议。")
