import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
from fpdf import FPDF
import time
from datetime import datetime

# --- 1. 页面配置 (简洁白金版) ---
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
        st.error("⚠️ 请在 Secrets 中设置 access_password")
    st.stop()

# --- 3. 核心 API 初始化 ---
client = OpenAI(api_key=st.secrets["deepseek_api_key"], base_url="https://api.deepseek.com")

# --- 4. 辅助函数：修复后的 PDF 导出 ---
def create_pdf(report_content, code):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, txt=f"Stock Analysis Report: {code}", ln=True, align='C')
    pdf.cell(0, 10, txt=f"Date: {datetime.now().strftime('%Y-%m-%d')}", ln=True, align='C')
    pdf.ln(10)
    
    # 清理特殊字符，防止编码错误
    clean_text = report_content.replace('**', '').replace('#', '').encode('latin-1', 'replace').decode('latin-1')
    pdf.multi_cell(0, 10, txt=clean_text)
    
    # 核心修复：返回 bytes 格式
    return bytes(pdf.output())

# --- 5. 主界面布局 ---
st.title("🚀 文哥哥 A股 AI 极速决策终端")

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

# --- 功能一：主力查询 ---
with tab1:
    if st.button("📡 扫描主力信号"):
        p_bar = st.progress(0)
        status_msg = st.empty()
        
        try:
            status_msg.text("📡 正在同步行情...")
            df_hist = ak.stock_zh_a_hist(symbol=raw_code, period="daily", adjust="qfq").tail(30)
            p_bar.progress(50)
            
            if df_hist.empty:
                st.error("❌ 未找到该股票数据")
            else:
                latest = df_hist.iloc[-1]
                # 尝试获取主力流向
                try:
                    mkt = "sh" if raw_code.startswith(('6', '9', '688')) else "sz"
                    df_fund = ak.stock_individual_fund_flow(stock=raw_code, market=mkt)
                    fund_data = df_fund.iloc[0] if not df_fund.empty else None
                except:
                    fund_data = None
                
                p_bar.progress(100)
                status_msg.text("✅ 扫描完成")
                
                st.subheader(f"📊 实时看板: {raw_code}")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("最新价", f"¥{latest['收盘']}")
                c2.metric("成交额", f"{latest['成交额'] / 100000000:.2f}亿")
                
                if fund_data is not None:
                    c3.metric("主力流入", f"{fund_data['主力净流入-净额']}")
                    c4.metric("净占比", f"{fund_data['主力净流入-净占比']}%")
                else:
                    st.info("💡 当前非交易时段，仅展示基础行情。")
                
                st.line_chart(df_hist.set_index('日期')['收盘'])
        except Exception as e:
            st.error(f"查询失败: {e}")
        finally:
            time.sleep(1)
            p_bar.empty()
            status_msg.empty()

# --- 功能二：AI 分析 ---
with tab2:
    if st.button("🚀 启动 AI 深度建模"):
        p_bar = st.progress(0)
        status_msg = st.empty()
        span_days = {"近一周": 5, "近一月": 20, "近三月": 60, "近半年": 120, "近一年": 250}
        
        try:
            status_msg.text("🧠 正在提取筹码分布...")
            df_hist = ak.stock_zh_a_hist(symbol=raw_code, period="daily", adjust="qfq").tail(span_days[time_span])
            p_bar.progress(40)
            
            if df_hist.empty:
                st.error("数据提取失败")
            else:
                status_msg.text("🧠 DeepSeek 正在极速生成报告...")
                prompt = f"""
                分析A股代码 {raw_code}，时间跨度 {time_span}。
                1.【建议决策】：明确给出【建议购入】、【建议出手】或【暂时观望】。
                2.【目标预测】：未来3个月目标价格。
                3.【空间分析】：核心支撑位、压力位。
                4.【趋势总结】：分析当前强弱。
                """
                
                response = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}])
                full_report = response.choices[0].message.content
                p_bar.progress(100)
                
                st.markdown("### 📋 AI 投资决策建议书")
                st.info(full_report)
                
                # 导出 PDF (核心修复点)
                st.divider()
                try:
                    pdf_output = create_pdf(full_report, raw_code)
                    st.download_button(
                        label="📥 导出 PDF 研报",
                        data=pdf_output,
                        file_name=f"Report_{raw_code}.pdf",
                        mime="application/pdf"
                    )
                except Exception as pdf_err:
                    st.warning(f"PDF 导出功能异常: {pdf_err}")
                    
        except Exception as e:
            st.error(f"AI 模块连接失败: {e}")
        finally:
            time.sleep(1)
            p_bar.empty()
            status_msg.empty()

st.divider()
st.caption("文哥哥 AI 终端 | 股市有风险 入市需谨慎")
