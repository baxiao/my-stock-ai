import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
from fpdf import FPDF
import time
from datetime import datetime

# --- 1. 页面基础配置 (回归简洁原生白) ---
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
        st.error("⚠️ 请在 Secrets 中设置 access_password")
    st.stop()

# --- 3. 核心 API 初始化 ---
client = OpenAI(api_key=st.secrets["deepseek_api_key"], base_url="https://api.deepseek.com")

# --- 4. 辅助函数：PDF 导出 ---
def create_pdf(report_content, code):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", size=12)
    pdf.cell(0, 10, f"Stock Report: {code}", 0, 1)
    pdf.cell(0, 10, f"Date: {datetime.now().strftime('%Y-%m-%d')}", 0, 1)
    pdf.ln(5)
    safe_text = report_content.encode('latin-1', 'replace').decode('latin-1')
    pdf.multi_cell(0, 10, safe_text)
    return pdf.output()

# --- 5. 主程序界面 ---
st.title("🚀 文哥哥 A股 AI 极速决策终端")

with st.sidebar:
    st.header("🔍 配置中心")
    # 自动处理代码格式
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

tab1, tab2 = st.tabs(["🎯 主力跟踪雷达", "🧠 DeepSeek 深度决策"])

# --- 功能一：主力查询 (高稳定性版) ---
with tab1:
    if st.button("📡 执行扫描"):
        p_bar = st.progress(0)
        status = st.empty()
        
        try:
            # 1. 获取基础行情 (使用最稳的历史数据接口模拟实时)
            status.text("📡 正在同步行情数据...")
            df_hist = ak.stock_zh_a_hist(symbol=raw_code, period="daily", adjust="qfq").tail(20)
            p_bar.progress(40)
            
            if df_hist.empty:
                st.error("❌ 未找到该股票的历史数据，请确认代码是否正确。")
            else:
                latest = df_hist.iloc[-1]
                prev = df_hist.iloc[-2]
                change_val = latest['收盘'] - prev['收盘']
                change_pct = (change_val / prev['收盘']) * 100
                
                # 2. 获取主力流向 (带异常跳过逻辑)
                status.text("📡 正在截获资金流向...")
                p_bar.progress(70)
                try:
                    mkt = "sh" if raw_code.startswith(('6', '9', '688')) else "sz"
                    df_fund = ak.stock_individual_fund_flow(stock=raw_code, market=mkt)
                    fund_data = df_fund.iloc[0] if not df_fund.empty else None
                except:
                    fund_data = None
                
                p_bar.progress(100)
                status.text("✅ 处理完成")
                
                # 3. 结果展示
                st.subheader(f"📊 股票代码: {raw_code}")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("收盘价", f"¥{latest['收盘']}", f"{change_pct:.2f}%")
                c2.metric("成交量", f"{latest['成交量']}手")
                
                if fund_data is not None:
                    c3.metric("主力净流入", f"{fund_data['主力净流入-净额']}")
                    c4.metric("主力占比", f"{fund_data['主力净流入-净占比']}%")
                else:
                    c3.warning("主力数据暂无")
                    c4.info("可能处于非交易时段")
                
                st.write("---")
                st.write("📈 **近期价格走势图**")
                st.line_chart(df_hist.set_index('日期')['收盘'])
                
        except Exception as e:
            st.error(f"⚠️ 系统繁忙: {e}")
        finally:
            time.sleep(1)
            p_bar.empty()
            status.empty()

# --- 功能二：AI 深度决策 ---
with tab2:
    if st.button("🚀 启动 AI 分析"):
        p_bar = st.progress(0)
        status = st.empty()
        span_days = {"近一周": 5, "近一月": 20, "近三月": 60, "近半年": 120, "近一年": 250}
        
        try:
            status.text("🧠 正在提取历史筹码分布...")
            p_bar.progress(30)
            # 抓取数据
            df_hist = ak.stock_zh_a_hist(symbol=raw_code, period="daily", adjust="qfq").tail(span_days[time_span])
            
            if df_hist.empty:
                st.error("数据提取失败")
            else:
                status.text("🧠 DeepSeek 正在进行深度建模...")
                p_bar.progress(60)
                
                # 构造极简 Prompt 避免 AI 解析失败
                prompt = f"""
                分析A股股票代码 {raw_code}。
                当前价格: {df_hist.iloc[-1]['收盘']}。
                参考跨度: {time_span}。
                请严格按照以下格式回答：
                1. 【建议决策】：明确给出【建议购入】、【建议出手】或【暂时观望】。
                2. 【目标预测】：明确给出未来3个月的目标价格。
                3. 【空间分析】：核心支撑位、压力位。
                4. 【主力评估】：结合近期成交量简述主力状态。
                """
                
                response = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}])
                full_report = response.choices[0].message.content
                
                p_bar.progress(100)
                status.text("✅ 分析报告已生成")
                
                st.markdown("### 📋 DeepSeek 投资决策建议书")
                st.info(full_report)
                
                # PDF 导出
                st.divider()
                pdf_bytes = create_pdf(full_report, raw_code)
                st.download_button(
                    label="📥 导出 PDF 研报",
                    data=pdf_bytes,
                    file_name=f"AI_Report_{raw_code}.pdf",
                    mime="application/pdf"
                )
        except Exception as e:
            st.error(f"AI 模块连接失败: {e}")
        finally:
            time.sleep(1)
            p_bar.empty()
            status.empty()

st.divider()
st.caption("文哥哥 AI 终端 | 提示：若报错请检查代码输入或稍后重试")
