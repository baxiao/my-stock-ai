import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
import time
from datetime import datetime

# --- 1. 页面配置 ---
st.set_page_config(page_title="文哥哥极速终端", page_icon="🚀", layout="wide")

# --- 2. 初始化持久化记忆 ---
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

        # C. 资金流向
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

# --- 5. 侧边栏 ---
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

# --- Tab 1: AI 决策 ---
with tab1:
    if st.button("🚀 启动全维度 AI 建模", use_container_width=True):
        with st.status("正在进行6大资金板块逻辑建模...", expanded=True) as status:
            data = get_stock_all_data(code)
            if data["success"]:
                f = data['fund']
                # 构造 AI 需要的 6 板块背景
                prompt_fund = f"""
                1.机构投资者(超大): {f['超大单净流入-净额']}
                2.游资(大单): {f['大单净流入-净额']}
                3.大户/牛散(中单): {f['中单净流入-净额']}
                4.散户群体(小单): {f['小单净流入-净额']}
                5.量化/产业参考: 成交额{data['vol']/1e8:.2f}亿，涨跌幅{data['pct']}%
                """
                news_text = "\n".join(data['news'])
                
                prompt = f"""
                分析股票 {code}。价格:{data['price']}, 涨跌:{data['pct']}%。
                资金分布：{prompt_fund}
                最新新闻：{news_text}
                
                请严格按以下5部分分析（每标题一行）：
                1.【建议决策】：建议购入/建议出手
                2.【短期预测】：未来一周目标价格区间
                3.【中期预测】：未来3个月目标价格区间
                4.【空间分析】：核心支撑位/压力位
                5.【趋势总结】：必须结合 机构、游资、牛散、量化、产业、散户 六大维度的博弈结论。
                """
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[{"role": "system", "content": "股票分析专家"}, {"role": "user", "content": prompt}],
                    max_tokens=800, temperature=0.2 
                )
                st.session_state.ai_cache = {"content": response.choices[0].message.content, "price": data['price']}
                status.update(label="✅ 分析已按6板块逻辑生成", state="complete")

    if st.session_state.ai_cache:
        st.success(f"**分析基准价**: ¥{st.session_state.ai_cache['price']}")
        st.markdown(st.session_state.ai_cache['content'])
        st.code(st.session_state.ai_cache['content'])

# --- Tab 2: 资金追踪雷达 (6大板块重定义) ---
with tab2:
    if st.button("📡 扫描六大板块资金博弈", use_container_width=True):
        with st.spinner("正在剥离解析 6 大板块数据..."):
            data = get_stock_all_data(code)
            if data["success"]:
                st.session_state.fund_cache = data
    
    if st.session_state.fund_cache:
        d = st.session_state.fund_cache
        if d['fund'] is not None:
            f = d['fund']
            
            # --- 板块逻辑重定义 ---
            # 1. 机构投资者
            inst_val = str(f['超大单净流入-净额'])
            # 2. 游资
            hot_val = str(f['大单净流入-净额'])
            # 3. 大户/牛散
            big_val = str(f['中单净流入-净额'])
            # 4. 量化资金 (模拟逻辑：高频波动与成交比)
            vol_ratio = (abs(d['pct']) / (d['vol']/1e9)) if d['vol'] > 0 else 0
            quant_tag = "🤖 量化算法活跃" if vol_ratio > 1.5 else "📉 量化参与度低"
            # 5. 产业资金 (关联逻辑：主力占比与成交规模)
            ind_val = str(f['主力净流入-净额'])
            # 6. 散户群体
            retail_val = str(f['小单净流入-净额'])

            # 顶部 6 个指标看板
            c1, c2, c3 = st.columns(3)
            c4, c5, c6 = st.columns(3)
            
            c1.metric("🏢 1.机构投资者", inst_val)
            c2.metric("🔥 2.游资动向", hot_val)
            c3.metric("🐂 3.大户/牛散", big_val)
            c4.metric("🤖 4.量化资金", quant_tag)
            c5.metric("🏭 5.产业资金", ind_val)
            c6.metric("🐣 6.散户群体", retail_val)
            
            st.divider()
            
            # 数据透视表 (用于快速对比)
            st.write("📊 **板块占比全景图**")
            data_df = pd.DataFrame({
                "板块名称": ["机构", "游资", "大户/牛散", "量化/产业", "散户"],
                "流入净占比": [
                    f"{f['超大单净流入-净占比']}%",
                    f"{f['大单净流入-净占比']}%",
                    f"{f['中单净流入-净占比']}%",
                    f"{f['主力净流入-净占比']}%",
                    f"{f['小单净流入-净占比']}%"
                ]
            })
            st.table(data_df)
            
            st.write("---")
            st.subheader("📰 支撑面相关新闻")
            for n in d['news']: st.write(f"· {n}")
        
        st.write("---")
        st.write("📈 **近期价格趋势**")
        st.line_chart(d['df'].set_index('日期')['收盘'])
