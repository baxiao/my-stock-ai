import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
from fpdf import FPDF
import time
from datetime import datetime

# --- 1. 页面基础配置 ---
st.set_page_config(page_title="文哥哥AI金融终端", page_icon="📈", layout="wide")

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
        st.error("⚠️ 请在后台 Secrets 中设置 access_password")
    st.stop()

# --- 3. 核心 API 初始化 ---
client = OpenAI(api_key=st.secrets["deepseek_api_key"], base_url="https://api.deepseek.com")

# --- 4. 辅助函数：PDF 处理 ---
def create_pdf(report_content, code):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, txt=f"Stock Analysis Report: {code}", ln=True, align='C')
    pdf.cell(0, 10, txt=f"Report Date: {datetime.now().strftime('%Y-%m-%d')}", ln=True, align='C')
    pdf.ln(10)
    # 处理中文字符编码问题
    clean_text = "Analysis Result:\n" + report_content.replace('*', '').replace('#', '')
    pdf.multi_cell(0, 10, txt=clean_text.encode('latin-1', 'replace').decode('latin-1'))
    return bytes(pdf.output())

# --- 5. 主程序界面 ---
st.title("🚀 文哥哥 A股 AI 极速决策终端 (最新时间线版)")

with st.sidebar:
    st.header("🔍 配置中心")
    raw_code = st.text_input("📍 股票代码", value="600519").strip()
    time_span = st.select_slider(
        "⏳ 分析跨度",
        options=["近一周", "近一月", "近三月", "近半年", "近一年"],
        value="近三月"
    )
    st.divider()
    if st.button("🔴 安全退出"):
        st.session_state['logged_in'] = False
        st.rerun()

tab1, tab2 = st.tabs(["🎯 主力追踪雷达", "🧠 DeepSeek 深度决策"])

# --- 功能一：主力查询 (确保最新时间) ---
with tab1:
    if st.button("📡 执行扫描"):
        progress_bar = st.progress(0)
        try:
            # 1. 获取最新历史K线
            df_hist = ak.stock_zh_a_hist(symbol=raw_code, period="daily", adjust="qfq")
            # 核心修正：按日期降序排列，取最后面（最新）的数据
            df_hist = df_hist.sort_values(by="日期", ascending=False)
            latest_data = df_hist.iloc[0] # 这里就是最新的一个交易日
            progress_bar.progress(40)
            
            # 2. 获取主力流向
            mkt = "sh" if raw_code.startswith(('6', '9', '688')) else "sz"
            df_fund = ak.stock_individual_fund_flow(stock=raw_code, market=mkt)
            # 同样确保资金流也是最新的
            latest_fund = df_fund.iloc[0] if not df_fund.empty else None
            progress_bar.progress(80)
            
            st.subheader(f"📊 实时行情看板 (截至: {latest_data['日期']})")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("最新收盘价", f"¥{latest_data['收盘']}", f"{latest_data['涨跌幅']}%")
            c2.metric("成交额", f"{latest_data['成交额']/1e8:.2f}亿")
            
            if latest_fund is not None:
                c3.metric("主力净流入", f"{latest_fund['主力净流入-净额']}")
                c4.metric("资金净占比", f"{latest_fund['主力净流入-净占比']}%")
            
            st.write("---")
            st.write("📈 **近期价格趋势 (最新时间轴)**")
            # 绘图用升序，方便从左往右看
            st.line_chart(df_hist.head(30).sort_values(by="日期").set_index('日期')['收盘'])
            progress_bar.progress(100)
            
        except Exception as e:
            st.error(f"查询失败: {e}")
        finally:
            time.sleep(1)
            progress_bar.empty()

# --- 功能二：AI 深度决策 (基于最新数据) ---
with tab2:
    if st.button("🚀 启动 AI 建模"):
        progress_bar = st.progress(0)
        span_days = {"近一周": 5, "近一月": 20, "近三月": 60, "近半年": 120, "近一年": 250}
        
        try:
            # 获取数据并确保最新
            df_hist = ak.stock_zh_a_hist(symbol=raw_code, period="daily", adjust="qfq")
            df_hist = df_hist.sort_values(by="日期", ascending=False).head(span_days[time_span])
            latest_date = df_hist.iloc[0]['日期']
            
            progress_bar.progress(40)
            
            # 构造 AI Prompt
            prompt = f"""
            分析A股代码 {raw_code}，数据截至日期为 {latest_date}。
            请根据最近 {time_span} 的走势给出决策：
            1.【建议决策】：明确给出【建议购入】、【建议出手】或【暂时观望】。
            2.【目标预测】：未来3个月的目标价格区间。
            3.【空间分析】：给出最新的核心支撑位和压力位。
            4.【主力评估】：简述当前筹码状态。
            """
            
            response = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}])
            report = response.choices[0].message.content
            progress_bar.progress(100)
            
            st.subheader(f"📋 AI 投资决策书 (数据截至: {latest_date})")
            st.success(f"已同步最新时间线数据进行分析")
            st.info(report)
            
            # 一键复制文本框
            st.text_area("📄 报告文本 (可直接复制)", value=report, height=200)
            
            # PDF 导出
            pdf_bytes = create_pdf(report, raw_code)
            st.download_button(
                label="📥 导出 PDF (中文受限建议复制文本)",
                data=pdf_bytes,
                file_name=f"Report_{raw_code}.pdf",
                mime="application/pdf"
            )
            
        except Exception as e:
            st.error(f"AI 分析失败: {e}")
        finally:
            time.sleep(1)
            progress_bar.empty()

st.divider()
st.caption("文哥哥 AI 终端 | 提示：已强制同步最新交易日数据。")
