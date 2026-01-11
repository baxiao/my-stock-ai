import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
from fpdf import FPDF
import time
from datetime import datetime

# --- 1. 页面配置 ---
st.set_page_config(page_title="文哥哥AI金融终端", page_icon="📈", layout="wide")

# --- 2. 安全验证 ---
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

# --- 3. API 初始化 ---
client = OpenAI(api_key=st.secrets["deepseek_api_key"], base_url="https://api.deepseek.com")

# --- 4. 辅助函数：PDF 修复 (处理编码) ---
def create_pdf(report_content, code):
    pdf = FPDF()
    pdf.add_page()
    # FPDF原生不支持中文，这里我们尽量清理并提示
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, txt=f"Stock Analysis Report: {code}", ln=True, align='C')
    pdf.cell(0, 10, txt=f"Date: {datetime.now().strftime('%Y-%m-%d')}", ln=True, align='C')
    pdf.ln(10)
    
    # 强制将中文转为拼音或英文说明，防止全是问号 (这是由于FPDF限制)
    # 更好的办法是建议文哥哥直接复制网页内容
    clean_text = "AI Report Content (Raw Text Support): \n" + report_content.replace('*', '')
    # 尝试使用 latin-1 兼容模式
    pdf.multi_cell(0, 10, txt=clean_text.encode('latin-1', 'replace').decode('latin-1'))
    
    return bytes(pdf.output())

# --- 5. 主界面 ---
st.title("🚀 文哥哥 A股 AI 极速决策终端")

with st.sidebar:
    st.header("🔍 配置中心")
    raw_code = st.text_input("📍 股票代码", value="600519").strip()
    time_span = st.select_slider(
        "⏳ 分析跨度",
        options=["近一周", "近一月", "近三月", "近半年", "近一年"],
        value="近三月"
    )
    if st.button("🔴 安全退出"):
        st.session_state['logged_in'] = False
        st.rerun()

tab1, tab2 = st.tabs(["🎯 主力追踪雷达", "🧠 DeepSeek 深度决策"])

# --- 功能一：主力查询 ---
with tab1:
    if st.button("📡 扫描主力信号"):
        with st.status("数据同步中...", expanded=True):
            try:
                df_hist = ak.stock_zh_a_hist(symbol=raw_code, period="daily", adjust="qfq").tail(30)
                if df_hist.empty:
                    st.error("未找到数据")
                else:
                    latest = df_hist.iloc[-1]
                    st.subheader(f"📊 实时看板: {raw_code}")
                    c1, c2 = st.columns(2)
                    c1.metric("收盘价", f"¥{latest['收盘']}")
                    c2.metric("成交额", f"{latest['成交额']/1e8:.2f}亿")
                    st.line_chart(df_hist.set_index('日期')['收盘'])
            except Exception as e:
                st.error(f"查询失败: {e}")

# --- 功能二：AI 分析 (增强显示) ---
with tab2:
    if st.button("🚀 启动 AI 深度建模"):
        with st.spinner('🤖 DeepSeek 正在极速生成研报...'):
            try:
                span_days = {"近一周": 5, "近一月": 20, "近三月": 60, "近半年": 120, "近一年": 250}
                df_hist = ak.stock_zh_a_hist(symbol=raw_code, period="daily", adjust="qfq").tail(span_days[time_span])
                
                prompt = f"分析A股代码 {raw_code}，时间跨度 {time_span}。请给出：1.【建议决策】(购入/出手/观望) 2.目标价 3.支撑压力位。"
                response = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}])
                full_report = response.choices[0].message.content
                
                # 页面美化显示
                st.subheader("📋 投资决策建议书")
                st.success("分析已完成！")
                st.markdown(f"""
                ---
                {full_report}
                ---
                """, unsafe_allow_html=True)
                
                # 方案：因为PDF中文支持极差，我们提供“一键复制文本”
                st.text_area("📄 报告文本（可直接复制）", value=full_report, height=300)
                
                # 备选PDF按钮
                pdf_output = create_pdf(full_report, raw_code)
                st.download_button(
                    label="📥 导出 PDF (注：中文可能受限)",
                    data=pdf_output,
                    file_name=f"Report_{raw_code}.pdf",
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(f"AI 模块异常: {e}")

st.divider()
st.caption("文哥哥 AI 终端 | 提示：PDF 库对中文支持较弱，建议直接复制上方文本框内容。")
