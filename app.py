import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
import time

# --- 1. 页面配置 ---
st.set_page_config(page_title="文哥哥极速终端", page_icon="🚀", layout="wide")

# --- 2. 核心数据取数逻辑（极致加固，防报错） ---
@st.cache_data(ttl=60)
def get_stock_data_safe(code):
    """
    使用最稳定的历史数据接口，即使非交易时间也能返回最新价格
    """
    try:
        # 1. 抓取最近30天的历史行情（包含今日最新价）
        df_hist = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq").tail(30)
        if df_hist.empty:
            return {"success": False, "msg": "未找到代码，请检查输入"}
        
        # 提取最新一条数据
        latest = df_hist.iloc[-1]
        
        # 2. 抓取资金流向（独立抓取，失败不影响主流程）
        fund = None
        try:
            mkt = "sh" if code.startswith(('6', '9', '688')) else "sz"
            df_fund = ak.stock_individual_fund_flow(stock=code, market=mkt)
            if not df_fund.empty:
                fund = df_fund.iloc[0]
        except:
            pass # 资金抓不到不报错，留给后续逻辑处理
            
        return {
            "success": True,
            "name": code, # 接口限制，历史接口不带名称，直接用代码显示
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
                # 构造 Prompt，即使没资金数据也能分析趋势
                fund_info = f"主力净流入:{data['fund']['主力净流入-净额']}" if data['fund'] is not None else "资金数据暂缺，请基于K线分析"
                
                prompt = f"""
                股票代码:{code}, 现价:{data['price']}, 涨幅:{data['pct']}%。
                {fund_info}。
                请给结论:1.决策(买/卖/观望) 2.支撑压制位 3.核心逻辑。字数100以内。
                """
                
                try:
                    response = client.chat.completions.create(
                        model="deepseek-chat",
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=200
                    )
                    ai_res = response.choices[0].message.content
                    st.success(f"**代码: {code}** 最新价: ¥{data['price']}")
                    st.info(ai_res)
                    st.code(ai_res)
                    status.update(label="✅ 分析完成", state="complete")
                except:
                    st.error("AI 响应超时，请重试")
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
                    c1.metric("最新价", f"¥{data['price']}", f"{data['pct']}%")
                    c2.metric("主力流入", inflow)
                    c3.metric("净占比", f"{f['主力净流入-净占比']}%")
                else:
                    st.warning("⚠️ 当前非交易时段，实时主力数据未更新。")
                    st.metric("最新价", f"¥{data['price']}", f"{data['pct']}%")
                
                st.write("---")
                st.write("📈 **近期价格趋势**")
                st.line_chart(data['df'].set_index('日期')['收盘'])
            else:
                st.error("行情数据获取失败")

st.divider()
st.caption("文哥哥专用 | 已解决 Index Error 崩溃问题 | 稳定白金版")
