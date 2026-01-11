import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
from fpdf import FPDF
import time
from datetime import datetime

# --- 1. 页面配置 (固定专业视觉) ---
st.set_page_config(page_title="文哥哥AI金融终端", page_icon="📈", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #ffffff; }
    .stMetric { background-color: #1d2129; padding: 15px; border-radius: 10px; border: 1px solid #444; }
    .report-box { background-color: #1d2129; padding: 25px; border-radius: 15px; border-left: 6px solid #ff4b4b; color: #ffffff; line-height: 1.8; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 安全验证 (Secrets 读取) ---
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
        st.error("⚠️ 请在 Secrets 中设置 access_password")
    st.stop()

# --- 3. 核心 API 初始化 ---
client = OpenAI(api_key=st.secrets["deepseek_api_key"], base_url="https://api.deepseek.com")

# --- 4. 辅助函数：PDF 导出 ---
def create_pdf(report_content, code, name):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", size=12)
    pdf.cell(0, 10, f"Target: {name} ({code})", 0, 1)
    pdf.cell(0, 10, f"Date: {datetime.now().strftime('%Y-%m-%d')}", 0, 1)
    pdf.ln(5)
    safe_text = report_content.encode('latin-1', 'replace').decode('latin-1')
    pdf.multi_cell(0, 10, safe_text)
    return pdf.output()

# --- 5. 主程序界面 ---
st.title("🚀 文哥哥 A股极速追踪系统")

with st.sidebar:
    st.header("🔍 分析配置")
    stock_code = st.text_input("📍 股票代码", value="600519")
    time_span = st.select_slider(
        "⏳ 时间跨度",
        options=["近一周", "近一月", "近三月", "近半年", "近一年"],
        value="近三月"
    )
    st.divider()
    if st.button("🔴 退出系统"):
        st.session_state['logged_in'] = False
        st.rerun()

tab1, tab2 = st.tabs(["🎯 主力追踪雷达", "🤖 DeepSeek 深度决策"])

# --- 功能一：主力查询 (极致提速版) ---
with tab1:
    if st.button("📡 扫描主力信号"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            # 第一阶段：极速获取个股行情
            status_text.text("1/3 正在连接交易所极速通道...")
            progress_bar.progress(30)
            df_info = ak.stock_individual_info_em(symbol=stock_code)
            name = df_info[df_info['item'] == '股票名称']['value'].values[0]
            price = df_info[df_info['item'] == '最新价']['value'].values[0]
            change = df_info[df_info['item'] == '当日涨跌幅']['value'].values[0]
            
            # 第二阶段：主力流向分析
            status_text.text("2/3 正在拦截主力实时大单数据...")
            progress_bar.progress(70)
            market = "sh" if stock_code.startswith(('6', '9', '688')) else "sz"
            df_fund = ak.stock_individual_fund_flow(stock=stock_code, market=market)
            latest_fund = df_fund.iloc[0]
            
            # 第三阶段：完成展示
            progress_bar.progress(100)
            status_text.text("✅ 扫描完成")
            time.sleep(0.5)
            status_text.empty()
            progress_bar.empty()

            st.subheader(f"📊 {name} ({stock_code}) 主力看板")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("最新价", f"¥{price}", f"{change}%")
            c2.metric("主力净额", f"{latest_fund['主力净流入-净额']}")
            c3.metric("主力占比", f"{latest_fund['主力净流入-净占比']}%")
            c4.metric("超大单", f"{latest_fund['超大单净流入-净额']}")
            
            st.write("📈 **近期主力资金活跃度**")
            st.line_chart(df_fund.head(15).set_index('日期')['主力净流入-净额'])
            
        except Exception as e:
            st.error(f"获取失败，请确保代码正确: {e}")

# --- 功能二：深度分析 (AI 提速版) ---
with tab2:
    if st.button("🚀 启动 AI 建模分析"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        span_map = {"近一周": 5, "近一月": 20, "近三月": 60, "近半年": 120, "近一年": 250}
        
        try:
            status_text.text(f"1/3 正在提取 {time_span} 历史筹码...")
            progress_bar.progress(30)
            hist = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq").tail(span_map[time_span])
            
            status_text.text("2/3 DeepSeek 正在极速生成决策报告...")
            progress_bar.progress(70)
            
            # 简化的 Prompt 提升 AI 响应速度
            prompt = f"""
            分析股票代码 {stock_code} ({time_span})。现价约为历史周期末位。
            1.【建议决策】：明确给出【建议购入】、【建议出手】或【暂时观望】。
            2.【目标预测】：未来3个月目标价。
            3.【空间判读】：核心支撑位、压力位。
            4.【主力评估】：结合当前筹码简述意图。
            """
            
            response = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}])
            full_report = response.choices[0].message.content
            
            progress_bar.progress(100)
            status_text.text("✅ 报告已就绪")
            time.sleep(0.5)
            status_text.empty()
            progress_bar.empty()

            st.subheader(f"📋 投资决策建议书 ({time_span})")
            st.markdown(f'<div class="report-box">{full_report}</div>', unsafe_allow_html=True)
            
            # PDF 导出
            pdf_data = create_pdf(full_report, stock_
