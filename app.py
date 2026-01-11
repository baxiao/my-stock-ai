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
    st.title("🔐 私人终端授权访问")
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
        with st.status("正在执行深度建模...", expanded=True) as status:
            data = get_stock_data_safe(code)
            
            if data["success"]:
                status.write("📡 资金动向与筹码分布对齐中...")
                
                # --- 新增：主力进场/离场逻辑判断 ---
                fund_direction = "数据暂缺"
                if data['fund'] is not None:
                    inflow_val = str(data['fund']['主力净流入-净额'])
                    # 判断正负号来确定进场离场
                    if "-" in inflow_val:
                        fund_direction = f"主力净流出 {inflow_val} (正在【离场】观望)"
                    else:
                        fund_direction = f"主力净流入 {inflow_val} (正在【入场】抢筹)"
                
                # 强化后的 Prompt：加入进场/离场标签，并强制排版
                prompt = f"""
                你是一名专业的资深股票分析师。请严格按照以下【五个部分】分析股票 {code}。
                
                【当前基础面】：
                价格：{data['price']} 元，涨跌幅：{data['pct']}%
                成交额：{data['vol']/1e8:.2f} 亿
                资金面：{fund_direction}

                ### 强制输出格式要求：
                1. 每个标题必须独立成行。
                2. 严禁合并段落。
                3. 分析必须结合上述【资金面】的入场或离场状态。

                ### 必须包含的五个部分：
                1.【建议决策】：明确给出【建议购入】、【建议出手】或【暂时观望】。
                2.【短期预测】：未来一周的目标价格区间。
                3.【中期预测】：未来3个月的目标价格区间。
                4.【空间分析】：最新的核心支撑位和压力位。
                5.【趋势总结】：简述当前强弱状态。

                注意：回答要专业、简练，不要说废话。
                """
                
                try:
                    response = client.chat.completions.create(
                        model="deepseek-chat",
                        messages=[
                            {"role": "system", "content": "你是一个严格执行输出格式、深度理解主力动向的金融专家。"},
                            {"role": "user", "content": prompt}
                        ],
                        max_tokens=600, 
                        temperature=0.2 
                    )
                    ai_res = response.choices[0].message.content
                    st.success(f"**代码: {code}** 最新价: ¥{data['price']}")
                    
                    # 页面直观展示
                    st.markdown(ai_res)
                    st.write("---")
                    st.caption("📖 研报正文 (可直接复制)：")
                    st.code(ai_res) 
                    
                    status.update(label="✅ 分析已根据主力动向更新", state="complete")
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
                    st.warning("⚠️ 实时资金数据未更新。")
                    st.metric("最新价", f"¥{data['price']}", f"{data['pct']}%")
                
                st.write("---")
                st.write("📈 **近期价格趋势**")
                st.line_chart(data['df'].set_index('日期')['收盘'])

st.divider()
st.caption("文哥哥专用 | 主力入场/离场分析增强版 | 稳定运行")
