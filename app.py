import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
import time
from datetime import datetime

# --- 1. 页面配置 ---
st.set_page_config(page_title="文哥哥极速终端", page_icon="🚀", layout="wide")

# --- 2. 核心数据取数逻辑 ---
@st.cache_data(ttl=60)
def get_stock_data_safe(code):
    try:
        # 抓取历史行情
        df_hist = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq").tail(30)
        if df_hist.empty:
            return {"success": False, "msg": "未找到代码，请检查输入"}
        
        latest = df_hist.iloc[-1]
        
        # 抓取资金流向
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
                status.write("📡 数据对齐成功，AI 正在强制生成四项分析...")
                
                fund_info = f"主力净流入:{data['fund']['主力净流入-净额']}" if data['fund'] is not None else "资金数据暂缺"
                
                # 强化后的 Prompt，强制四项输出
                prompt = f"""
                你是一名专业的资深股票分析师。请严格按照以下【四个部分】分析股票 {code}。
                当前价格：{data['price']} 元，涨跌幅：{data['pct']}%，成交额：{data['vol']/1e8:.2f} 亿。
                {fund_info}。

                必须且只能包含以下四个标题，不得省略任何一项：
                1.【建议决策】：明确给出【建议购入】、【建议出手】或【暂时观望】。
                2.【目标预测】：未来3个月的目标价格区间。
                3.【空间分析】：最新的核心支撑位和压力位。
                4.【趋势总结】：简述当前强弱状态。

                注意：回答要专业、简练，不要说废话。
                """
                
                try:
                    response = client.chat.completions.create(
                        model="deepseek-chat",
                        messages=[
                            {"role": "system", "content": "你是一个严格执行输出格式的金融专家。"},
                            {"role": "user", "content": prompt}
                        ],
                        max_tokens=500, # 增加字数限制，防止被截断
                        temperature=0.3  # 降低随机性，让格式更稳
                    )
                    ai_res = response.choices[0].message.content
                    st.success(f"**代码: {code}** 最新价: ¥{data['price']}")
                    st.markdown(ai_res)  # 使用 markdown 渲染，显示更清晰
                    st.code(ai_res) 
                    status.update(label="✅ 四项核心指标已生成", state="complete")
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
                    st.warning("⚠️ 实时资金接口暂未同步。")
                    st.metric("最新价", f"¥{data['price']}", f"{data['pct']}%")
                
                st.write("---")
                st.write("📈 **近期价格趋势**")
                st.line_chart(data['df'].set_index('日期')['收盘'])

st.divider()
st.caption("文哥哥专用 | 格式强制执行版 | 稳定运行")
