import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
import time
from datetime import datetime
import pytz
from concurrent.futures import ThreadPoolExecutor
import re  # 新增：用于股票代码校验

# ===================== 全局配置与常量定义 =====================
st.set_page_config(page_title="文哥哥极速终端", page_icon="🚀", layout="wide")
CN_TZ = pytz.timezone('Asia/Shanghai')
# 四灯配置常量（提升可读性）
FOUR_LAMPS_CONFIG = {
    "trend": {"name": "趋势形态", "red_desc": "多头占优", "green_desc": "重心下移"},
    "money": {"name": "主力动向", "red_desc": "主力流入", "green_desc": "主力撤离"},
    "sentiment": {"name": "市场情绪", "red_desc": "买盘活跃", "green_desc": "信心不足"},
    "safety": {"name": "筹码安全", "red_desc": "锁仓良好", "green_desc": "散户接盘"}
}
# 资金字段映射（提升可读性）
FUND_FIELDS = {
    "main_net": "主力净流入-净额",
    "small_net_ratio": "小单净流入-净占比",
    "super_large_net": "超大单净流入-净额",
    "large_net": "大单净流入-净额",
    "medium_net": "中单净流入-净额"
}

# ===================== 状态初始化（集中管理） =====================
def init_session_state():
    default_states = {
        "ai_cache": None,
        "last_data": None,
        "last_code": "",
        "auto_refresh": False,
        "logged_in": False,
        "refresh_count": 0  # 新增：用于自动刷新计数
    }
    for key, value in default_states.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# ===================== 密钥校验（提前拦截） =====================
def check_secrets():
    required_secrets = ["deepseek_api_key", "access_password"]
    missing = [key for key in required_secrets if key not in st.secrets]
    if missing:
        st.error(f"❌ 缺少配置密钥：{', '.join(missing)}！请在 Streamlit Settings -> Secrets 中添加。")
        st.stop()

check_secrets()

# ===================== 工具函数（优化） =====================
def format_money(value):
    """
    格式化资金数值为亿/万单位
    :param value: 数值/字符串类型的资金额
    :return: 格式化后的字符串，异常返回"N/A"
    """
    try:
        val = float(value)
        abs_val = abs(val)
        if abs_val >= 1e8:  # 1亿
            return f"{val / 1e8:.2f} 亿"
        elif abs_val >= 1e4:  # 1万
            return f"{val / 1e4:.1f} 万"
        else:
            return f"{val:.2f}"
    except (ValueError, TypeError):
        return "N/A"

def validate_stock_code(code):
    """校验A股代码格式"""
    if not code or len(code) != 6:
        return False, "代码必须为6位数字"
    # A股代码开头校验
    valid_prefixes = ['0', '3', '6', '8', '9']
    if code[0] not in valid_prefixes:
        return False, "代码开头应为0/3/6/8/9（A股）"
    return True, ""

# ===================== 数据获取函数（优化） =====================
def fetch_hist_data(code):
    """获取股票历史数据（带具体异常捕获）"""
    try:
        df = ak.stock_zh_a_hist(
            symbol=code,
            period="daily",
            adjust="qfq"
        ).tail(30)
        return df if not df.empty else pd.DataFrame()
    except ak.exceptions.DataNotFoundError:
        return pd.DataFrame()
    except Exception as e:
        st.warning(f"获取历史数据失败：{str(e)}")
        return pd.DataFrame()

def fetch_fund_flow(code):
    """获取资金流数据（优化市场判断）"""
    try:
        market = "sh" if code.startswith(('6', '9')) else "sz"
        df = ak.stock_individual_fund_flow(stock=code, market=market)
        return df if not df.empty else pd.DataFrame()
    except Exception as e:
        st.warning(f"获取资金流数据失败：{str(e)}")
        return pd.DataFrame()

@st.cache_data(ttl=5, show_spinner="获取股票数据中...")  # 优化缓存时间
def get_stock_data(code):
    """并行获取股票数据（优化异常处理和返回结构）"""
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            fut_hist = executor.submit(fetch_hist_data, code)
            fut_fund = executor.submit(fetch_fund_flow, code)
            df_hist = fut_hist.result()
            df_fund = fut_fund.result()

        if df_hist.empty:
            return {"success": False, "msg": "未获取到股票历史数据"}
        
        # 核心数据提取（带索引校验）
        last_row = df_hist.iloc[-1] if len(df_hist) > 0 else None
        if last_row is None:
            return {"success": False, "msg": "历史数据无有效行"}
        
        fund_data = df_fund.iloc[0] if not df_fund.empty else None
        
        return {
            "success": True,
            "price": last_row.get('收盘', 0),
            "pct": last_row.get('涨跌幅', 0),
            "fund": fund_data,
            "df": df_hist
        }
    except Exception as e:
        return {"success": False, "msg": f"数据获取异常：{str(e)}"}

# ===================== 四灯逻辑（优化） =====================
def calculate_four_lamps(stock_data):
    """计算四灯状态（优化判断逻辑，提升鲁棒性）"""
    default_lamps = {
        "trend": "⚪", "money": "⚪", 
        "sentiment": "⚪", "safety": "⚪"
    }
    
    if not stock_data or not stock_data.get('success'):
        return default_lamps
    
    df_hist = stock_data['df']
    fund_data = stock_data['fund']
    price_pct = stock_data['pct']
    
    # 1. 趋势灯（MA5 vs MA20）
    if len(df_hist) >= 20:
        ma5 = df_hist['收盘'].tail(5).mean()
        ma20 = df_hist['收盘'].tail(20).mean()
        trend_lamp = "🔴" if ma5 > ma20 else "🟢"
    else:
        trend_lamp = "⚪"
    
    # 2. 资金灯（主力净流入）
    money_lamp = "⚪"
    if fund_data is not None:
        main_net = fund_data.get(FUND_FIELDS['main_net'], 0)
        try:
            money_lamp = "🔴" if float(main_net) > 0 else "🟢"
        except (ValueError, TypeError):
            money_lamp = "⚪"
    
    # 3. 情绪灯（涨跌幅）
    try:
        sentiment_lamp = "🔴" if float(price_pct) > 0 else "🟢"
    except (ValueError, TypeError):
        sentiment_lamp = "⚪"
    
    # 4. 安全灯（小单占比）
    safety_lamp = "⚪"
    if fund_data is not None:
        small_ratio = fund_data.get(FUND_FIELDS['small_net_ratio'], 0)
        try:
            safety_lamp = "🔴" if float(small_ratio) < 15 else "🟢"
        except (ValueError, TypeError):
            safety_lamp = "⚪"
    
    return {
        "trend": trend_lamp,
        "money": money_lamp,
        "sentiment": sentiment_lamp,
        "safety": safety_lamp
    }

# ===================== 登录逻辑 =====================
def login_section():
    """独立登录模块"""
    st.title("🔐 文哥哥私人终端")
    pwd = st.text_input("访问密钥", type="password", key="login_pwd")
    if st.button("开启终端", use_container_width=True):
        if pwd == st.secrets["access_password"]:
            st.session_state['logged_in'] = True
            st.rerun()
        else:
            st.error("密钥错误，请重新输入")
    st.stop()

# 登录拦截
if not st.session_state['logged_in']:
    login_section()

# ===================== OpenAI客户端初始化 =====================
client = OpenAI(
    api_key=st.secrets["deepseek_api_key"],
    base_url="https://api.deepseek.com"
)

# ===================== 侧边栏 =====================
with st.sidebar:
    st.title("🚀 控制中心")
    
    # 股票代码输入（带校验）
    code = st.text_input(
        "股票代码", 
        value="600519", 
        key="stock_code",
        placeholder="输入6位A股代码，如600519"
    ).strip()
    
    # 代码校验提示
    is_valid, err_msg = validate_stock_code(code)
    if code and not is_valid:
        st.warning(f"⚠️ {err_msg}")
    
    # 重置状态（仅当代码有效且变化时）
    if code != st.session_state.last_code and is_valid:
        st.session_state.last_code = code
        st.session_state.ai_cache = None
        st.session_state.last_data = None
    
    st.divider()
    
    # 自动刷新（改用Streamlit官方autorefresh）
    st.session_state.auto_refresh = st.checkbox(
        "🔄 自动刷新（5秒/次）", 
        value=st.session_state.auto_refresh,
        key="auto_refresh_checkbox"
    )
    if st.session_state.auto_refresh:
        # 官方推荐的自动刷新方式，不会阻塞主线程
        st.autorefresh(interval=5000, key="auto_refresh_timer")
        st.session_state.refresh_count += 1  # 刷新计数
    
    if st.button("🔴 退出系统", use_container_width=True):
        st.session_state['logged_in'] = False
        st.rerun()

# ===================== 主页面 =====================
st.title(f"📈 文哥哥 AI 终端: {code if code else '未输入有效代码'}")

# 仅当代码有效时显示标签页
if is_valid:
    t1, t2 = st.tabs(["🧠 AI 深度决策", "🎯 实时资金雷达"])

    # --- Tab 1: AI 深度决策 ---
    with t1:
        if st.button("🚀 启动全维度 AI 建模", use_container_width=True):
            with st.spinner("正在获取数据并生成分析报告..."):
                # 真实进度反馈（按步骤）
                progress_steps = ["获取股票数据", "计算四灯指标", "生成AI分析"]
                p_bar = st.progress(0, text=f"正在{progress_steps[0]}...")
                
                # 步骤1：获取数据
                stock_data = get_stock_data(code)
                p_bar.progress(33, text=f"正在{progress_steps[1]}...")
                
                if not stock_data["success"]:
                    st.error(f"数据获取失败：{stock_data['msg']}")
                    p_bar.empty()
                else:
                    # 步骤2：计算四灯
                    four_lamps = calculate_four_lamps(stock_data)
                    p_bar.progress(66, text=f"正在{progress_steps[2]}...")
                    
                    # 优化Prompt（结构化输出）
                    prompt = f"""
                    你是资深私募投资总监，现分析A股股票 {code}，具体信息如下：
                    1. 当前价格：{stock_data['price']} 元
                    2. 涨跌幅：{stock_data['pct']}%
                    3. 四灯指标：{four_lamps}
                       - 趋势灯：🔴=多头占优 🟢=重心下移
                       - 资金灯：🔴=主力流入 🟢=主力撤离
                       - 情绪灯：🔴=买盘活跃 🟢=信心不足
                       - 安全灯：🔴=锁仓良好 🟢=散户接盘

                    请严格按照以下格式输出分析结果：
                    ### 1. 战术评级
                    [全线进攻/逢高撤退/空仓观望]
                    
                    ### 2. 核心理由
                    [基于四灯指标和价格数据的3-5条核心分析]
                    
                    ### 3. 博弈位
                    支撑位：[根据近期价格判断的支撑价位]
                    压力位：[根据近期价格判断的压力价位]
                    
                    ### 4. 文哥哥锦囊
                    [一句简洁、实战性强的操作建议]
                    """
                    
                    # 调用OpenAI API
                    try:
                        response = client.chat.completions.create(
                            model="deepseek-chat",
                            messages=[{"role": "user", "content": prompt}],
                            temperature=0.1  # 降低随机性，提升分析稳定性
                        )
                        st.session_state.ai_cache = {
                            "content": response.choices[0].message.content,
                            "timestamp": datetime.now(CN_TZ).strftime("%Y-%m-%d %H:%M:%S")
                        }
                        p_bar.progress(100, text="分析完成！")
                        time.sleep(0.5)
                        p_bar.empty()
                    except Exception as e:
                        st.error(f"AI分析失败：{str(e)}")
                        p_bar.empty()
            
            # 显示AI分析结果
            if st.session_state.ai_cache:
                st.markdown("### 🏹 实战指令")
                st.info(f"""
                **分析时间**：{st.session_state.ai_cache['timestamp']}
                \n{st.session_state.ai_cache['content']}
                """)

    # --- Tab 2: 实时资金雷达 ---
    with t2:
        def render_fund_radar():
            """渲染资金雷达页面（独立函数，便于复用）"""
            stock_data = get_stock_data(code)
            placeholder = st.empty()
            
            with placeholder.container():
                # 状态标签
                if not stock_data["success"]:
                    if st.session_state.last_data:
                        display_data = st.session_state.last_data
                        status_tag = "⚠️ 断流保护（使用缓存数据）"
                    else:
                        st.warning(f"❌ 数据加载失败：{stock_data['msg']}")
                        return
                else:
                    display_data = stock_data
                    st.session_state.last_data = stock_data
                    status_tag = "🟢 实时连通"
                
                # 时间戳
                current_time = datetime.now(CN_TZ).strftime("%H:%M:%S")
                st.caption(f"🕒 {current_time} | {status_tag} | 🔴正面 🟢风险")
                
                # 四灯渲染（优化样式）
                st.write("### 🚦 核心策略哨兵")
                cols = st.columns(4)
                for idx, (key, config) in enumerate(FOUR_LAMPS_CONFIG.items()):
                    lamp_status = calculate_four_lamps(display_data)[key]
                    color = "#ff4b4b" if lamp_status == "🔴" else "#2eb872" if lamp_status == "🟢" else "#cccccc"
                    bg_color = f"rgba({255 if lamp_status == '🔴' else 46 if lamp_status == '🟢' else 204}, {75 if lamp_status == '🔴' else 184 if lamp_status == '🟢' else 204}, {75 if lamp_status == '🔴' else 114 if lamp_status == '🟢' else 204}, 0.1)"
                    
                    cols[idx].markdown(f"""
                    <div style="
                        background-color: {bg_color};
                        padding: 15px;
                        border-radius: 12px;
                        border-top: 5px solid {color};
                        text-align: center;
                    ">
                        <p style="margin:0; color:{color}; font-weight:bold; font-size:14px;">{config['name']}</p>
                        <h2 style="margin:8px 0; color:{color};">{lamp_status}</h2>
                        <p style="margin:0; color:{color}; font-size:11px;">
                            {config['red_desc'] if lamp_status == '🔴' else config['green_desc'] if lamp_status == '🟢' else '数据不足'}
                        </p>
                    </div>
                    """, unsafe_allow_html=True)
                
                # 四灯说明（优化表格）
                with st.expander("📖 四灯量化逻辑说明", expanded=True):
                    st.markdown("""
                    | 维度 | 🔴 红色 (正面/多头) | 🟢 绿色 (负面/空头) |
                    | :--- | :--- | :--- |
                    | **趋势** | MA5 > MA20，攻击线有效支撑，顺势持股 | MA5 < MA20，股价重心下移，反弹即逃命 |
                    | **资金** | 主力净流入>0，机构真金白银吸筹 | 主力净流入≤0，机构持续派发筹码 |
                    | **情绪** | 实时涨跌幅>0，场外资金抢筹意愿强 | 实时涨跌幅≤0，市场信心匮乏，卖压重 |
                    | **安全** | 小单占比<15%，筹码高度锁定 | 小单占比≥15%，散户接盘，易踩踏 |
                    """)
                    st.caption("🛡️ 文哥哥提醒：只做红灯共振的机会，坚决执行止损绿灯")
                
                st.divider()
                
                # 核心指标
                col1, col2 = st.columns(2)
                with col1:
                    price = display_data['price']
                    pct = display_data['pct']
                    pct_color = "green" if float(pct) > 0 else "red" if float(pct) < 0 else "gray"
                    st.metric(
                        "📌 当前价位",
                        f"¥{price:.2f}",
                        f"{pct:.2f}%",
                        delta_color=pct_color
                    )
                with col2:
                    fund_data = display_data['fund']
                    main_net = fund_data[FUND_FIELDS['main_net']] if fund_data is not None else 0
                    main_net_formatted = format_money(main_net)
                    main_net_desc = "多方发力" if float(main_net) > 0 else "空方减速" if float(main_net) < 0 else "资金持平"
                    st.metric("🌊 主力净额", main_net_formatted, main_net_desc)
                
                # 6大资金板块
                st.write("📊 **6大资金板块明细**")
                if fund_data is not None:
                    row1 = st.columns(3)
                    row2 = st.columns(3)
                    
                    # 机构（超大单）
                    super_large = fund_data.get(FUND_FIELDS['super_large_net'], 0)
                    row1[0].metric("1. 🏢 机构", format_money(super_large))
                    
                    # 游资（大单）
                    large = fund_data.get(FUND_FIELDS['large_net'], 0)
                    row1[1].metric("2. 🔥 游资", format_money(large))
                    
                    # 大户（中单）
                    medium = fund_data.get(FUND_FIELDS['medium_net'], 0)
                    row1[2].metric("3. 🐂 大户", format_money(medium))
                    
                    # 量化（占位）
                    row2[0].metric("4. 🤖 量化", "智能监控")
                    
                    # 产业（主力）
                    main = fund_data.get(FUND_FIELDS['main_net'], 0)
                    row2[1].metric("5. 🏭 产业", format_money(main))
                    
                    # 散户（小单占比）
                    small_ratio = fund_data.get(FUND_FIELDS['small_net_ratio'], 0)
                    row2[2].metric("6. 🐣 散户", f"{float(small_ratio):.1f} %")
                
                # 价格走势图
                st.write("### 📉 近30日价格走势")
                df_plot = display_data['df'].set_index('日期')['收盘']
                st.line_chart(df_plot, height=200, use_container_width=True)
        
        # 渲染资金雷达
        render_fund_radar()

else:
    st.warning("请输入有效的6位A股股票代码（如600519）")

# 页脚
st.divider()
st.caption(f"文哥哥专用 | {datetime.now(CN_TZ).strftime('%Y-%m-%d')} | 战术集成优化版")
