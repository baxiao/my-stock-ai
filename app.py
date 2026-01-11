import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
import time
from datetime import datetime  # 必须导入这个，否则会报 NameError

# --- 1. 页面配置 ---
st.set_page_config(page_title="文哥哥极速终端", page_icon="🚀", layout="wide")

# --- 2. 核心数据取数逻辑 ---
@st.cache_data(ttl=60)
def get_stock_data_safe(code):
    """
    使用最稳定的历史数据接口，确保非交易时间也能返回最新价格
    """
    try:
        # 1. 抓取最近30天的历史行情
        df_hist = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq").tail(30)
        if df_hist.empty:
            return {"success": False, "msg": "未找到代码，请检查输入"}
        
        latest = df_hist.iloc[-1]
        
        # 2. 抓取资金流向
        fund = None
        try:
            mkt = "sh" if code.startswith(('6', '9', '688')) else "sz"
            df_fund = ak.stock_individual_fund_flow(stock=code, market=mkt)
            if not df_fund.empty:
                fund = df_fund.iloc[0]
        except:
            pass 
            
        return {
            "success": True,
            "name": code, 
            "price": latest['收盘'],
            "pct": latest['涨跌幅'],
            "high": latest['最高'],
            "low": latest['最低'],
            "vol": latest['成交额'],
            "fund": fund,
            "df": df_hist
        }
    except Exception as e:
        return {"success": False, "msg": f"接口波动: {str(e)}"}

# --- 3. 安全验证 ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.title("🔐 私人终端授权")
    pwd = st.text_input("请输入访问密钥", type="password")
    if st.button("开启终端", use_container_width=True):
        if "access_password" in st.secrets and pwd == st.secrets["access_password"]:
            st.session_state['logged_in'] = True
            st.rerun()
        else:
            st.error("密钥无效")
    st.stop()

# --- 4. API 初始化 ---
client = OpenAI(api_key=st.secrets["deepseek_api_key"], base_url="https://api.deepseek.com")

# --- 5. 主界面布局 ---
st.title("🚀 文哥哥 AI 决策终端")

with st.sidebar:
    st.header("🔍 查询配置")
    code = st.text_input("股票代码", value="600519").strip()
    st.divider()
    if st.button("🔴 退出系统", use_container_width=True):
        st.session_state['logged_in'] = False
        st.rerun()

tab1, tab2 = st.tabs(["🧠 AI 深度决策", "🎯 主力追踪雷达"])

# --- Tab 1: AI 决策 ---
with tab1:
    if st.button("🚀 启动极速建模分析", use_container_width=True):
        with st.status("正在秒杀查询...", expanded=True) as status:
            data = get_stock_data_safe(code)
            
            if data["success"]:
                status.write("📡 历史与实时数据对齐成功...")
                
                # 修正变量名对齐：使用 data 里的值
                fund_info = f"主力净流入:{data['fund']['主力净流入-净额']}" if data['fund'] is not None else "资金数据暂缺"
                
                # 重新整理后的 Prompt
                prompt = f"""
                当前时刻：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                股票代码：{code}
                【最新收盘/实时价】：{data['price']} 元
                今日涨跌幅：{data['pct']}%
                今日成交额：{data['vol']/1e8:.2f} 亿
                {fund_info}
                
                请结合以上数据及近期趋势，给出分析：
                1.【建议决策】：明确给出【建议购入】、【建议出手】或【暂时观望】。
                2.【目标预测】：未来3个月的目标价格区间。
                3.【空间分析】：最新的核心支撑位和压力位。
                4.【趋势总结】：简述当前强弱状态。
                """
                
                try:
                    response = client.chat.completions.create(
                        model="deepseek-chat",
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=300
                    )
                    ai_res = response.choices[0].message.content
                    st.success(f"**代码: {code}** 最新价: ¥{data['price']}")
                    st.info(ai_res)
                    st.code(ai_res) # 方便一键复制
                    status.update(label="✅ 分析完成", state="complete")
                except Exception as e:
                    st.error(f"AI 响应异常: {str(e)}")
            else:
                st.error(data["msg"])

# --- Tab 2: 主力雷达 ---
with tab2:
    if st.button("📡 扫描主力动态", use_container_width=True):
        with st.spinner("正在拦截主力筹码..."):
            data = get_stock_data_safe(code)
            if data["success"]:
                if data['fund'] is not None:
                    f = data['fund']
                    inflow = str(f['主力净流入-净额'])
                    if "-" not in inflow:
                        st.error(f"🔴 主力正在强势进场: {inflow}")
                    else:
                        st.success(f"🟢 主力正在洗盘离场: {inflow}")
                    
                    c1, c2, c3 = st.columns(3)
                    c1.metric("价格", f"¥{data['price']}", f"{data['pct']}%")
                    c2.metric("主力流入", inflow)
                    c3.metric("净占比", f"{f['主力净流入-净占比']}%")
                else:
                    st.warning("⚠️ 当前非交易时段，实时主力数据未更新。")
                    st.metric("最新价", f"¥{data['price']}", f"{data['pct']}%")
                
                st.write("---")
                st.write("📈 **近期价格趋势 (K线图)**")
                st.line_chart(data['df'].set_index('日期')['收盘'])
            else:
                st.error("行情数据获取失败")

st.divider()
st.caption("文哥哥专用 | 已修复 NameError 与变量冲突 | 稳定运行版")
