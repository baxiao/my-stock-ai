import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
from fpdf import FPDF
import time
from datetime import datetime

# --- 1. 页面配置与昼夜模式 ---
st.set_page_config(page_title="文哥哥AI智能终端", page_icon="📈", layout="wide")

# 侧边栏：昼夜模式与控制
with st.sidebar:
    st.header("⚙️ 终端设置")
    theme_mode = st.select_slider("显示模式", options=["🌞 浅色", "🌙 深色"])
    st.divider()
    stock_code = st.text_input("📍 股票代码", value="600519")
    time_span = st.select_slider(
        "⏳ 分析时间线",
        options=["近一周", "近一月", "近三月", "近半年", "近一年"],
        value="近三月"
    )
    st.divider()
    if st.button("🔴 安全退出"):
        st.session_state['logged_in'] = False
        st.rerun()

# 动态 CSS 注入：美化与昼夜切换
if theme_mode == "🌙 深色":
    bg_color, text_color, card_bg = "#0e1117", "#ffffff", "#262730"
else:
    bg_color, text_color, card_bg = "#ffffff", "#31333F", "#f0f2f6"

st.markdown(f"""
    <style>
    .stApp {{ background-color: {bg_color}; color: {text_color}; }}
    .metric-card {{ background-color: {card_bg}; padding: 20px; border-radius: 12px; border: 1px solid #444; text-align: center; }}
    .report-box {{ background-color: {card_bg}; padding: 25px; border-radius: 15px; border-left: 6px solid #ff4b4b; line-height: 1.8; color: {text_color}; }}
    </style>
    """, unsafe_allow_html=True)

# --- 2. 访问密钥验证 ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.title("🔐 私人终端访问授权")
    pwd_input = st.text_input("请输入授权密钥", type="password")
    if st.button("验证授权"):
        if pwd_input == st.secrets["access_password"]:
            st.session_state['logged_in'] = True
            st.rerun()
        else:
            st.error("密钥无效")
    st.stop()

# --- 3. 核心引擎加载 ---
client = OpenAI(api_key=st.secrets["deepseek_api_key"], base_url="https://api.deepseek.com")

# --- 4. 辅助功能函数 ---
def get_market(code):
    return "sh" if code.startswith(('6', '9', '688')) else "sz"

class PDF(FPDF):
    def header(self):
        self.set_font('helvetica', 'B', 12)
        self.cell(0, 10, 'Stock Analysis Report - AI Terminal', 0, 1, 'C')

def export_to_pdf(report_text, code, name):
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("helvetica", size=11)
    pdf.cell(0, 10, f"Target: {name} ({code})", 0, 1)
    pdf.cell(0, 10, f"Generated: {datetime.now().strftime('%Y-%m-%d')}", 0, 1)
    pdf.ln(5)
    pdf.multi_cell(0, 10, txt=report_text.encode('latin-1', 'replace').decode('latin-1'))
    return pdf.output()

# --- 5. 主程序逻辑 ---
st.title("🚀 A股主力追踪 & DeepSeek 决策终端")

tab1, tab2 = st.tabs(["🎯 主力查询跟踪", "🤖 深度 AI 分析报告"])

# 功能一：主力查询跟踪
with tab1:
    if st.button("🔍 开启主力信号扫描"):
        with st.status("正在抓取实时主力筹码...", expanded=True) as status:
            try:
                # 获取实时行情
                df_spot = ak.stock_zh_a_spot_em()
                spot = df_spot[df_spot['代码'] == stock_code].iloc[0]
                # 获取主力流向
                df_fund = ak.stock_individual_fund_flow(stock=stock_code, market=get_market(stock_code))
                main_fund = df_fund.iloc[0]
                
                status.update(label="✅ 主力信号截获成功", state="complete")
                
                st.subheader(f"💎 {spot['名称']} ({stock_code}) 主力实时看板")
                c1, c2, c3, c4 = st.columns(4)
                with c1: st.metric("最新价", f"¥{spot['最新价']}", f"{spot['涨跌幅']}%")
                with c2: st.metric("主力净流入", f"{main_fund['主力净流入-净额']}元")
                with c3: st.metric("主力净占比", f"{main_fund['主力净流入-净占比']}%")
                with c4: st.metric("超大单流入", f"{main_fund['超大单净流入-净额']}元")
                
                # 资金可视化
                st.write("---")
                st.write("📈 **近期资金流入走势**")
                st.line_chart(df_fund.head(20).set_index('日期')['主力净流入-净额'])
                
            except Exception as e:
                st.error(f"数据获取失败: {e}")

# 功能二：股票分析 (DeepSeek 驱动)
with tab2:
    if st.button("🧠 启动 DeepSeek 深度建模"):
        span_days = {"近一周": 5, "近一月": 20, "近三月": 60, "近半年": 120, "近一年": 250}
        with st.spinner(f'正在回溯 {time_span} 数据并生成研报...'):
            try:
                # 获取数据
                df_spot = ak.stock_zh_a_spot_em()
                spot = df_spot[df_spot['代码'] == stock_code].iloc[0]
                hist = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq").tail(span_days[time_span])
                
                # AI Prompt 注入
                prompt = f"""
                你是一名资深A股首席分析师。分析股票：{spot['名称']} ({stock_code})。
                时间线：{time_span}。现价：{spot['最新价']}。
                要求必须包含以下模块：
                1. 【建议决策】：明确给出【建议购入】、【建议出手】或【暂时观望】。
                2. 【目标预测】：明确给出未来3个月的目标价格。
                3. 【空间分析】：明确指出核心的支撑位和压力位。
                4. 【主力评估】：结合当前资金面判断主力意图。
                """
                
                response = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}])
                full_report = response.choices[0].message.content
                
                st.subheader(f"📋 DeepSeek 投资决策书 ({time_span})")
                st.markdown(f'<div class="report-box">{full_report}</div>', unsafe_allow_html=True)
                
                # PDF 导出按钮
                st.divider()
                pdf_data = export_to_pdf(full_report, stock_code, spot['名称'])
                st.download_button(
                    label="📥 导出 PDF 研报",
                    data=pdf_data,
                    file_name=f"AI_Report_{stock_code}.pdf",
                    mime="application/pdf"
                )
                
            except Exception as e:
                st.error(f"分析失败: {e}")

st.divider()
st.caption("文哥哥专属 AI 操盘助理 | 股市有风险 入市需谨慎")
