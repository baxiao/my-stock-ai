import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
import time
from datetime import datetime

# --- 1. 页面配置 ---
st.set_page_config(page_title="文哥哥极速终端", page_icon="🚀", layout="wide")

# --- 2. 初始化持久化记忆 (实现切换TAB不消失) ---
if 'ai_cache' not in st.session_state: st.session_state.ai_cache = None
if 'fund_cache' not in st.session_state: st.session_state.fund_cache = None
if 'last_code' not in st.session_state: st.session_state.last_code = ""

# --- 3. 核心数据取数逻辑 ---
@st.cache_data(ttl=60)
def get_stock_all_data(code):
    try:
        # A. 基础行情与K线
        df_hist = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq").tail(30)
        if df_hist.empty: return {"success": False, "msg": "未找到代码"}
        latest = df_hist.iloc[-1]
        
        # B. 实时新闻
        try:
            news_df = ak.stock_news_em(symbol=code).head(5)
            news_list = news_df['新闻标题'].tolist() if not news_df.empty else ["暂无最新相关新闻"]
        except:
            news_list = ["新闻接口调用受限"]

        # C. 资金流向与占比
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
            "price": latest['收盘'],
            "pct": latest['涨跌幅'],
            "vol": latest['成交额'],
            "news": news_list,
            "fund": fund,
            "df": df_hist
        }
    except Exception as e:
        return {"success": False, "msg": str(e)}

# --- 4. 安全验证 ---
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

client = OpenAI(api_key=st.secrets["deepseek_api_key"], base_url="https://api.deepseek.com")

# --- 5. 侧边栏与代码更换逻辑 ---
with st.sidebar:
    st.title("🚀 控制中心")
    code = st.text_input("股票代码", value="600519").strip()
    
    if code != st.session_state.last_code:
        st.session_state.ai_cache = None
        st.session_state.fund_cache = None
        st.session_state.last_code = code
        
    st.divider()
    if st.button("🔴 退出系统"):
        st.session_state['logged_in'] = False
        st.rerun()

st.title(f"📈 文哥哥 AI 终端: {code}")

tab1, tab2 = st.tabs(["🧠 AI 深度决策", "🎯 资金追踪雷达"])

# --- Tab 1: AI 决策 (集成新闻判断) ---
with tab1:
    if st.button("🚀 启动全维度 AI 建模", use_container_width=True):
        with st.status("正在整合行情、资金、新闻面...", expanded=True) as status:
            data = get_stock_all_data(code)
            if data["success"]:
                fund_direction = "数据暂缺"
                if data['fund'] is not None:
                    inflow_val = str(data['fund']['主力净流入-净额'])
                    fund_direction = f"主力净流入 {inflow_val} (" + ("正在【入场】抢筹" if "-" not in inflow_val else "正在【离场】观望") + ")"
                
                news_text = "\n".join([f"- {n}" for n in data['news']])
                
                prompt = f"""
                你是一名专业的资深股票分析师。请结合行情、资金、新闻分析股票 {code}。
                价格：{data['price']} 元，涨跌幅：{data['pct']}%
                资金面：{fund_direction}
                最新新闻：{news_text}

                ### 强制要求：
                1. 标题必须独立成行，严禁合并。
                2. 必须包含对【新闻面】的利好/利空解读。

                ### 必须输出的五个部分：
                1.【建议决策】：明确给出【建议购入】、【建议出手】或【暂时观望】。
                2.【短期预测】：未来一周的目标价格区间。
                3.【中期预测】：未来3个月的目标价格区间。
                4.【空间分析】：最新的核心支撑位和压力位。
                5.【趋势总结】：结合新闻、主力资金和技术面给出总结。
                """
                
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[{"role": "system", "content": "金融专家"}, {"role": "user", "content": prompt}],
                    max_tokens=800, temperature=0.2 
                )
                st.session_state.ai_cache = {"content": response.choices[0].message.content, "price": data['price']}
                status.update(label="✅ AI 决策已就绪", state="complete")

    if st.session_state.ai_cache:
        c = st.session_state.ai_cache
        st.success(f"**分析基准价**: ¥{c['price']}")
        st.markdown(c['content'])
        st.code(c['content'])
    else:
        st.info("💡 请点击按钮开始 AI 深度决策分析")

# --- Tab 2: 资金雷达 (主力+游资并列分析) ---
with tab2:
    if st.button("📡 扫描实时资金动向", use_container_width=True):
        with st.spinner("拦截筹码中..."):
            data = get_stock_all_data(code)
            if data["success"]:
                st.session_state.fund_cache = data
    
    if st.session_state.fund_cache:
        d = st.session_state.fund_cache
        if d['fund'] is not None:
            f = d['fund']
            
            # --- 1. 主力判断 (超大单+大单) ---
            main_inflow = str(f['主力净流入-净额'])
            main_color = "error" if "-" not in main_inflow else "success"
            main_tag = "🔴 主力强势进场" if "-" not in main_inflow else "🟢 主力获利洗盘"
            
            # --- 2. 游资判断 (中单) ---
            hot_inflow = str(f['中单净流入-净额'])
            hot_tag = "🔥 游资积极参与" if "-" not in hot_inflow else "🌬️ 游资离场观望"
            
            # 视觉展示
            col_a, col_b = st.columns(2)
            with col_a:
                st.subheader(main_tag)
                st.write(f"净流入: **{main_inflow}**")
            with col_b:
                st.subheader(hot_tag)
                st.write(f"净流入: **{hot_inflow}**")
            
            st.divider()
            
            # 四列指标
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("最新价", f"¥{d['price']}", f"{d['pct']}%")
            c2.metric("主力占比", f"{f['主力净流入-净占比']}%")
            c3.metric("游资占比", f"{f['中单净流入-净占比']}%") # 中单通常代表活跃游资
            c4.metric("超大单占比", f"{f['超大单净流入-净占比']}%")
            
            st.write("---")
            st.subheader("📰 相关支撑新闻")
            for n in d['news']:
                st.write(f"· {n}")
        
        st.write("---")
        st.write("📈 **近期价格趋势**")
        st.line_chart(d['df'].set_index('日期')['收盘'])
    else:
        st.info("💡 请点击按钮获取主力与游资占比分析")

st.divider()
st.caption("文哥哥专用 | 主力+游资双线监控 | 记忆化Tab版")
