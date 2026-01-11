import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
from fpdf import FPDF
import time

# --- 1. 页面配置与美化 ---
st.set_page_config(page_title="文哥哥AI金融终端", page_icon="📈", layout="wide")

st.markdown("""
    <style>
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .report-box { background-color: #ffffff; padding: 25px; border-radius: 15px; border: 1px solid #e0e0e0; box-shadow: 2px 2px 10px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

# --- 2. API 配置 ---
if "deepseek_api_key" in st.secrets:
    client = OpenAI(api_key=st.secrets["deepseek_api_key"], base_url="https://api.deepseek.com")
else:
    st.error("🔑 请在后台配置 API Key")
    st.stop()

# --- 3. PDF 导出逻辑 ---
class ExportPDF(FPDF):
    def header(self):
        self.set_font('helvetica', 'B', 16)
        self.cell(0, 10, 'Stock Intelligence Analysis Report', 0, 1, 'C')
        self.ln(10)

def generate_pdf_bytes(stock_name, stock_code, content):
    pdf = ExportPDF()
    pdf.add_page()
    pdf.set_font("helvetica", size=12)
    pdf.cell(0, 10, f"Target: {stock_name} ({stock_code})", 0, 1)
    pdf.cell(0, 10, f"Generated: {time.strftime('%Y-%m-%d %H:%M')}", 0, 1)
    pdf.ln(5)
    clean_text = content.replace('#', '').replace('*', '')
    pdf.multi_cell(0, 10, txt=clean_text.encode('latin-1', 'replace').decode('latin-1'))
    return pdf.output()

# --- 4. 辅助函数 ---
def get_market(code):
    return "sh" if code.startswith(('6', '9', '688')) else "sz"

# --- 5. 主界面 ---
st.title("🛡️ 文哥哥 A股 AI 智能情报站")

with st.container():
    col_input, _ = st.columns([1, 2])
    with col_input:
        stock_code = st.text_input("📍 输入股票代码", value="600519")

tab1, tab2 = st.tabs(["🔥 主力监控", "🧠 AI 深度分析"])

# --- 功能一：主力监控（带进度条） ---
with tab1:
    if st.button("开始监控资金流向"):
        # 创建进度条和文字提示
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            status_text.text("📡 正在连接交易所，调取实时成交数据...")
            time.sleep(0.5)
            df_spot = ak.stock_zh_a_spot_em()
            spot = df_spot[df_spot['代码'] == stock_code].iloc[0]
            progress_bar.progress(40)
            
            status_text.text("🔍 正在扫描主力筹码分布与资金流向...")
            time.sleep(0.5)
            df_fund = ak.stock_individual_fund_flow(stock=stock_code, market=get_market(stock_code))
            latest = df_fund.iloc[0]
            progress_bar.progress(70)
            
            status_text.text("🧠 正在通过 AI 进行资金意图判读...")
            prompt = f"分析{spot['名称']}：主力流入{latest['主力净流入-净额']}元。主力进场还是退场？一句话总结。"
            res = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}])
            
            progress_bar.progress(100)
            status_text.text("✅ 数据获取成功！")
            time.sleep(0.5)
            status_text.empty()
            progress_bar.empty()
            
            # 展示结果
            st.subheader(f"📊 {spot['名称']} 筹码分布状态")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("主力净流入", f"{latest['主力净流入-净额']}元")
            m2.metric("主力占比", f"{latest['主力净流入-净占比']}%")
            m3.metric("超大单流入", f"{latest['超大单净流入-净额']}元")
            m4.metric("换手率", f"{spot['换手率']}%")
            st.info(f"🤖 **主力意图：** {res.choices[0].message.content}")
            
        except Exception as e:
            st.error(f"数据获取失败：{e}")
            status_text.empty()
            progress_bar.empty()

# --- 功能二：深度分析（带进度条） ---
with tab2:
    if st.button("生成深度决策报告"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            status_text.text("📉 正在拉取近期 K 线走势数据...")
            df_spot = ak.stock_zh_a_spot_em()
            spot = df_spot[df_spot['代码'] == stock_code].iloc[0]
            hist = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq").tail(100)
            progress_bar.progress(30)
            time.sleep(0.5)
            
            status_text.text("🤖 DeepSeek 正在进行全维度建模与压力位计算...")
            # 模拟 AI 思考的进度感
            for i in range(31, 90, 10):
                progress_bar.progress(i)
                time.sleep(0.3)
            
            prompt = f"你是专业操盘手。分析{spot['名称']}。1.建议买入还是出手？2.目标价？3.支撑压力位？"
            response = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}])
            full_report = response.choices[0].message.content
            
            progress_bar.progress(100)
            status_text.text("✅ 报告生成完毕")
            time.sleep(0.5)
            status_text.empty()
            progress_bar.empty()
            
            # 展示报告
            st.subheader(f"📈 {spot['名称']} 走势与决策")
            st.line_chart(hist.set_index('日期')['收盘'])
            
            st.markdown('<div class="report-box">', unsafe_allow_html=True)
            st.markdown(full_report)
            st.markdown('</div>', unsafe_allow_html=True)
            
            # PDF 导出按钮
            st.divider()
            pdf_bytes = generate_pdf_bytes(spot['名称'], stock_code, full_report)
            st.download_button(
                label="📥 导出分析报告为 PDF",
                data=pdf_bytes,
                file_name=f"Report_{stock_code}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
        except Exception as e:
            st.error(f"分析失败：{e}")
            status_text.empty()
            progress_bar.empty()

st.divider()
st.caption("风险提示：AI建议仅供参考。")
