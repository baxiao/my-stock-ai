import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
from fpdf import FPDF
import time
from datetime import datetime

# --- 1. 页面配置与昼夜模式逻辑 ---
st.set_page_config(page_title="文哥哥AI金融终端", page_icon="📈", layout="wide")

# 侧边栏：控制台
with st.sidebar:
    st.header("⚙️ 终端控制")
    # 昼夜模式切换
    theme_mode = st.select_slider("显示模式", options=["🌞 浅色", "🌙 深色"], value="🌙 深色")
    st.divider()
    stock_code = st.text_input("📍 输入股票代码", value="600519")
    # 深度分析时间线选择
    time_span = st.select_slider(
        "⏳ 分析时间跨度",
        options=["近一周", "近一月", "近三月", "近半年", "近一年"],
        value="近三月"
    )
    st.divider()
    if st.button("🔴 安全退出系统"):
        st.session_state['logged_in'] = False
        st.rerun()

# 动态 UI 美化 CSS
if theme_mode == "🌙 深色":
    bg_color, text_color, card_bg, border_color = "#0e1117", "#ffffff", "#1d2129", "#444"
else:
    bg_color, text_color, card_bg, border_color = "#ffffff", "#31333F", "#f0f2f6", "#ddd"

st.markdown(f"""
    <style>
    .stApp {{ background-color: {bg_color}; color: {text_color}; }}
    .stMetric {{ background-color: {card_bg}; padding: 15px; border-radius: 10px; border: 1px solid {border_color}; }}
    .report-box {{ background-color: {card_bg}; padding: 25px; border-radius: 15px; border-left: 6px solid #ff4b4b; color: {text_color}; line-height: 1.8; }}
    </style>
    """, unsafe_allow_html=True)

# --- 2. 安全门禁（访问密钥） ---
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
                st.error("密钥无效，拒绝访问")
    else:
        st.error("⚠️ 请在 Secrets 中配置 access_password")
    st.stop()

# --- 3. 核心 API 初始化 ---
client = OpenAI(api_key=st.secrets["deepseek_api_key"], base_url="https://api.deepseek.com")

# --- 4. 辅助函数：PDF 导出 ---
class StockPDF(FPDF):
    def header(self):
        self.set_font('helvetica', 'B', 15)
        self.cell(0, 10, 'Stock Analysis Deep Report', 0, 1, 'C')
        self.ln(5)

def create_pdf(report_content, code, name):
    pdf = StockPDF()
    pdf.add_page()
    pdf.set_font("helvetica", size=12)
    pdf.cell(0, 10, f"Target: {name} ({code})", 0, 1)
    pdf.cell(0, 10, f"Date: {datetime.now().strftime('%Y-%m-%d')}", 0, 1)
    pdf.ln(5)
    # 处理编码问题
    safe_text = report_content.encode('latin-1', 'replace').decode('latin-1')
    pdf.multi_cell(0, 10, safe_text)
    return pdf.output()

# --- 5. 主程序界面 ---
st.title("🚀 文哥哥 A股主力追踪 & AI 决策系统")

tab1, tab2 = st.tabs(["🎯 主力查询跟踪", "🤖 DeepSeek 深度分析"])

# --- 功能一：主力查询跟踪 ---
with tab1:
    if st.button("📡 执行主力信号扫描"):
        with st.status("正在截获实时主力筹码流向...", expanded=True) as status:
            try:
                # 1. 抓取行情
                df_spot = ak.stock_zh_a_spot_em()
                target_spot = df_spot[df_spot['代码'] == stock_code].iloc[0]
                # 2. 抓取资金流
                market = "sh" if stock_code.startswith(('6', '9', '688')) else "sz"
                df_fund = ak.stock_individual_fund_flow(stock=stock_code, market=market)
                latest_fund = df_fund.iloc[0]
                
                status.update(label="✅ 主力信号同步完成", state="complete")
                
                st.subheader(f"📊 {target_spot['名称']} ({stock_code}) 实时资金看板")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("最新价", f"¥{target_spot['最新价']}", f"{target_spot['涨跌幅']}%")
                c2.metric("主力净流入", f"{latest_fund['主力净流入-净额']}元")
                c3.metric("主力净占比", f"{latest_fund['主力净流入-净占比']}%")
                c4.metric("超大单流入", f"{latest_fund['超大单净流入-净额']}元")
                
                st.write("📈 **近20日主力资金流入趋势**")
                st.line_chart(df_fund.head(20).set_index('日期')['主力净流入-净额'])
                
            except Exception as e:
                st.error(f"数据扫描失败: {e}")

# --- 功能二：DeepSeek 深度分析 ---
with tab2:
    if st.button("🧠 启动 DeepSeek 深度建模"):
        span_map = {"近一周": 5, "近一月": 20, "近三月": 60, "近半年": 120, "近一年": 250}
        with st.spinner(f'正在基于 {time_span} 维度进行智能研判...'):
            try:
                # 获取数据
                df_spot = ak.stock_zh_a_spot_em()
                target_spot = df_spot[df_spot['代码'] == stock_code].iloc[0]
                hist = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq").tail(span_map[time_span])
                
                # AI 提示词指令
                prompt = f"""
                你是一名顶尖A股策略分析师。请针对股票 {target_spot['名称']} ({stock_code}) 在【{time_span}】的时间跨度下进行深度分析。
                当前价格：{target_spot['最新价']}。
                请务必按以下格式给出结论：
                1. 【核心决策】：明确给出【建议购入】、【建议出手】或【暂时观望】。
                2. 【目标价预测】：明确给出未来3个月的目标价格。
                3. 【空间判读】：给出核心的支撑位和压力位。
                4. 【主力动向】：结合当前筹码状态评估主力意图。
                """
                
                response = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}])
                full_report = response.choices[0].message.content
                
                st.subheader(f"📋 DeepSeek 投资决策建议书 ({time_span})")
                st.markdown(f'<div class="report-box">{full_report}</div>', unsafe_allow_html=True)
                
                # PDF 导出
                st.divider()
                pdf_data = create_pdf(full_report, stock_code, target_spot['名称'])
                st.download_button(
                    label="📥 导出 PDF 深度报告",
                    data=pdf_data,
                    file_name=f"Report_{stock_code}.pdf",
                    mime="application/pdf"
                )
                
            except Exception as e:
                st.error(f"AI 分析中断: {e}")

st.divider()
st.caption("文哥哥专属 AI 操盘助理 | 股市有风险 入市需谨慎")
