import datetime
import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import FinanceDataReader as fdr
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import urllib.request
import urllib.parse
import json
import re
import time
import requests
from io import StringIO

# 페이지 설정
st.set_page_config(page_title="글로벌 종합 금융 프로 터미널", layout="wide", initial_sidebar_state="expanded")

# ==================== 0. 정크 종목(거래정지/우선주/스팩/리츠/관리종목) 필터 함수 ====================
def is_valid_normal_stock(name: str, code: str, curr_volume: float, curr_amount: float) -> bool:
    """거래정지, 상장폐지 절차, 스팩, 리츠, 우선주, 관리종목 등을 완벽 필터링"""
    if curr_volume <= 0 or curr_amount <= 0:
        return False
    
    if not (str(code).isdigit() and len(str(code)) == 6):
        return False
        
    name_clean = str(name).strip()
    
    if any(keyword in name_clean for keyword in ["스팩", "기업인수목적", "리츠", "REIT", "인프라", "투융자"]):
        return False
        
    if re.search(r'(우|우B|우C|우\(전환\))$', name_clean):
        return False
        
    if any(keyword in name_clean for keyword in ["(관리)", "(정매)", "(환기)", "정리매매"]):
        return False
        
    return True

# ==================== 텔레그램 메시지 발송 함수 ====================
def send_telegram_message(message: str) -> bool:
    bot_token = st.secrets.get("TELEGRAM_BOT_TOKEN", None)
    chat_id = st.secrets.get("TELEGRAM_CHAT_ID", None)
    
    if not bot_token or not chat_id:
        return False
        
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": str(chat_id).strip(),
            "text": message,
            "parse_mode": "Markdown"
        }
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status == 200
    except Exception:
        return False

# ==================== 세션 상태 초기화 & 콜백 함수 ====================
if "category_radio" not in st.session_state:
    st.session_state["category_radio"] = "국내주식 (KRX)"
if "custom_stock_name" not in st.session_state:
    st.session_state["custom_stock_name"] = None
if "custom_stock_code" not in st.session_state:
    st.session_state["custom_stock_code"] = None
if "tab_selector" not in st.session_state:
    st.session_state["tab_selector"] = "📊 인터랙티브 종합 차트"

# 스캐너 결과 저장용 세션 상태
if "scan_results_df" not in st.session_state:
    st.session_state["scan_results_df"] = None
if "scan_results_date" not in st.session_state:
    st.session_state["scan_results_date"] = None
if "last_scanned_params" not in st.session_state:
    st.session_state["last_scanned_params"] = None

# 초소외주 스캐너 결과 저장용 세션 상태
if "dormant_scan_results" not in st.session_state:
    st.session_state["dormant_scan_results"] = None
if "dormant_scan_date" not in st.session_state:
    st.session_state["dormant_scan_date"] = None
if "dormant_params" not in st.session_state:
    st.session_state["dormant_params"] = None

def select_scanner_stock(name, code):
    st.session_state["category_radio"] = "국내주식 (KRX)"
    st.session_state["custom_stock_name"] = name
    st.session_state["custom_stock_code"] = code
    st.session_state["tab_selector"] = "📊 인터랙티브 종합 차트"

# ==================== 1. 비공개 접속 비밀번호 인증 ====================
def check_password():
    if st.session_state.get("authenticated", False):
        return True

    app_pwd = st.secrets.get("APP_PASSWORD", None)
    if not app_pwd:
        return True

    st.markdown("<h2 style='text-align: center;'>🔒 프라이빗 금융 대시보드</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: gray;'>이 대시보드는 비공개 보안 페이지입니다. 접속 비밀번호를 입력하세요.</p>", unsafe_allow_html=True)
    
    _, col, _ = st.columns([1, 2, 1])
    with col:
        user_input = st.text_input("접속 비밀번호", type="password", placeholder="비밀번호를 입력하세요")
        if st.button("대시보드 접속", use_container_width=True):
            if str(user_input).strip() == str(app_pwd).strip():
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("❌ 비밀번호가 올바르지 않습니다. 다시 입력해 주세요.")
                
    return False

if not check_password():
    st.stop()

# ==================== 2. 본문 대시보드 화면 ====================

st.markdown("""
<style>
    .metric-card {
        background-color: #1E222D;
        border: 1px solid #2A2E39;
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 8px;
    }
    .signal-badge-bull {
        background-color: rgba(38, 166, 154, 0.2);
        color: #26A69A;
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 0.85rem;
    }
    .signal-badge-bear {
        background-color: rgba(239, 83, 80, 0.2);
        color: #EF5350;
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 0.85rem;
    }
    .signal-badge-neutral {
        background-color: rgba(255, 255, 255, 0.1);
        color: #B2B5BE;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 0.85rem;
    }
</style>
""", unsafe_allow_html=True)

st.title("📈 글로벌 종합 금융 인텔리전스 대시보드")

# 1. 국내주식 시총 상위 목록
@st.cache_data(ttl=3600)
def get_krx_stocks():
    try:
        df = fdr.StockListing('KRX')
        df = df.sort_values(by='Marcap', ascending=False).head(150)
        return dict(zip(df['Name'], df['Code']))
    except Exception:
        return {
            "삼성전자": "005930", "SK하이닉스": "000660", "LG에너지솔루션": "373220",
            "삼성바이오로직스": "207940", "현대차": "005380", "셀트리온": "068270"
        }

# 2. 해외/미국 관심 종목 리스트
def get_us_stocks():
    return {
        "META - Meta Platforms": "META",
        "TSLA - Tesla": "TSLA",
        "AAPL - Apple": "AAPL",
        "GOOGL - Alphabet (Google)": "GOOGL",
        "AMZN - Amazon": "AMZN",
        "NVDA - NVIDIA": "NVDA",
        "MSFT - Microsoft": "MSFT",
        "PLTR - Palantir Technologies": "PLTR",
        "AMD - Advanced Micro Devices": "AMD",
        "INTC - Intel": "INTC",
        "NFLX - Netflix": "NFLX",
        "CPNG - Coupang": "CPNG",
        "MSTR - MicroStrategy": "MSTR",
        "LLY - Eli Lilly": "LLY",
        "GE - General Electric": "GE",
        "ASTS - AST SpaceMobile": "ASTS",
        "RKLB - Rocket Lab USA": "RKLB",
        "BABA - Alibaba Group": "BABA"
    }

# 3. 채권(Bonds) 리스트
def get_bonds():
    return {
        "TLT (미국 20년+ 장기국채 ETF)": "TLT",
        "IEF (미국 7-10년 중기국채 ETF)": "IEF",
        "SHY (미국 1-3년 단기국채 ETF)": "SHY",
        "TMF (미국 20년+ 국채 3X 레버리지)": "TMF",
        "^TNX (미국 10년물 국채 수익률 지수)": "^TNX",
        "^TYX (미국 30년물 국채 수익률 지수)": "^TYX",
        "^IRX (미국 13주 단기국채 수익률 지수)": "^IRX",
        "KOSEF 국고채10년 (한국 10년 국채 ETF)": "148070",
        "KBSTAR 국고채3년 (한국 3년 국채 ETF)": "385560",
        "ACE 미국30년국채액티브(H)": "453850",
        "BND (Vanguard 종합채권 ETF)": "BND"
    }

# 4. 원자재(Commodities) 리스트
def get_commodities():
    return {
        "Gold (금 선물)": "GC=F",
        "Silver (은 선물)": "SI=F",
        "Copper (구리 선물)": "HG=F",
        "WTI Crude Oil (WTI 원유)": "CL=F",
        "Brent Oil (브렌트유)": "BZ=F",
        "Natural Gas (천연가스)": "NG=F",
        "Platinum (백금)": "PL=F",
        "Palladium (팔라듐)": "PA=F",
        "Corn (옥수수)": "ZC=F",
        "Soybeans (대두/콩)": "ZS=F",
        "Wheat (밀)": "ZW=F"
    }

# 5. 주요 환율 리스트
def get_forex():
    return {
        "USD/KRW (원/달러)": "USD/KRW",
        "JPY/KRW (원/100엔)": "JPY/KRW",
        "EUR/KRW (원/유로)": "EUR/KRW",
        "CNY/KRW (원/위안)": "CNY/KRW",
        "GBP/KRW (원/파운드)": "GBP/KRW",
        "USD/JPY (달러/엔)": "USD/JPY",
        "EUR/USD (유로/달러)": "EUR/USD"
    }

# 6. 주요 코인 리스트
def get_crypto():
    return {
        "BTC/USD (비트코인)": "BTC/USD",
        "ETH/USD (이더리움)": "ETH/USD",
        "XRP/USD (리플)": "XRP/USD",
        "SOL/USD (솔라나)": "SOL/USD",
        "DOGE/USD (도지코인)": "DOGE/USD",
        "ADA/USD (에이다)": "ADA/USD",
        "BNB/USD (바이낸스코인)": "BNB/USD"
    }

# ==================== 사이드바 구성 ====================
st.sidebar.header("🕹️ 컨트롤 패널")

input_mode = st.sidebar.radio("🔍 종목 선택 방식", ["목록에서 선택", "티커 직접 입력"], index=0)

if input_mode == "목록에서 선택":
    category_list = ["해외주식 (US Custom)", "국내주식 (KRX)", "채권 (Bonds)", "원자재 (Commodity)", "환율 (Forex)", "암호화폐 (Crypto)"]
    
    category = st.sidebar.radio(
        "🌐 자산 카테고리", 
        category_list, 
        key="category_radio"
    )

    if category == "해외주식 (US Custom)":
        STOCKS = get_us_stocks()
        currency_symbol = "USD"
    elif category == "국내주식 (KRX)":
        STOCKS = get_krx_stocks()
        if st.session_state["custom_stock_name"] and st.session_state["custom_stock_code"]:
            c_name = st.session_state["custom_stock_name"]
            c_code = st.session_state["custom_stock_code"]
            if c_name not in STOCKS:
                STOCKS = {c_name: c_code, **STOCKS}
        currency_symbol = "원"
    elif category == "채권 (Bonds)":
        STOCKS = get_bonds()
        currency_symbol = "USD"
    elif category == "원자재 (Commodity)":
        STOCKS = get_commodities()
        currency_symbol = "USD"
    elif category == "환율 (Forex)":
        STOCKS = get_forex()
        currency_symbol = "원"
    else:
        STOCKS = get_crypto()
        currency_symbol = "USD"

    options_list = list(STOCKS.keys())
    default_target = st.session_state.get("custom_stock_name")
    selected_idx = options_list.index(default_target) if (default_target and default_target in options_list) else 0

    selected_name = st.sidebar.selectbox("🔎 종목/자산 선택", options=options_list, index=selected_idx)
    selected_code = STOCKS[selected_name]
else:
    direct_ticker = st.sidebar.text_input("📝 티커 직접 입력 (예: 005930, META, 016800)", value="META").strip()
    selected_name = f"Custom: {direct_ticker}"
    selected_code = direct_ticker
    category = "직접입력"
    currency_symbol = "원" if (direct_ticker.isdigit() or "KRW" in direct_ticker) else "USD"

# 주기 설정 및 매핑
tf_config = {
    "5분봉": {"default": "1일", "options": ["1일", "3일", "5일", "1개월", "2개월"], "interval": "5m"},
    "30분봉": {"default": "5일", "options": ["5일", "1개월", "2개월"], "interval": "30m"},
    "1시간봉": {"default": "1개월", "options": ["5일", "1개월", "2개월", "6개월"], "interval": "60m"},
    "일봉": {"default": "1년", "options": ["1달", "6개월", "1년", "3년", "5년", "10년"], "interval": "1d"},
    "주봉": {"default": "3년", "options": ["6개월", "1년", "3년", "5년", "10년"], "interval": "1wk"},
    "월봉": {"default": "5년", "options": ["1년", "3년", "5년", "10년", "최대(All)"], "interval": "1mo"}
}

st.sidebar.markdown("---")
st.sidebar.subheader("⏱️ 차트 주기 & 기간")
timeframe = st.sidebar.radio("📊 차트 주기", list(tf_config.keys()), index=3)

current_cfg = tf_config[timeframe]
selected_period = st.sidebar.select_slider(
    "📅 조회 기간 (자동 최적화)",
    options=current_cfg["options"],
    value=current_cfg["default"]
)

st.sidebar.markdown("---")
st.sidebar.subheader("📐 보조지표 표시")
show_ma = st.sidebar.checkbox("이동평균선 (20/50/100/200)", value=True)
show_bb = st.sidebar.checkbox("볼린저 밴드 (20, 2)", value=False)
show_rsi = st.sidebar.checkbox("RSI (14)", value=True)
show_macd = st.sidebar.checkbox("MACD (12, 26, 9)", value=True)

# 텔레그램 연동 상태 확인 및 테스트 버튼
st.sidebar.markdown("---")
st.sidebar.subheader("🔔 텔레그램 알림 봇")
if "TELEGRAM_BOT_TOKEN" in st.secrets and "TELEGRAM_CHAT_ID" in st.secrets:
    st.sidebar.success("✅ 텔레그램 연동 완료")
    if st.sidebar.button("📲 테스트 알림 보내기"):
        msg = f"🚀 *[QPZM 터미널 테스트 알림]*\n\n대시보드와 텔레그램 봇 연동이 완벽하게 완료되었습니다!\n확인 시각: `{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`"
        if send_telegram_message(msg):
            st.sidebar.toast("텔레그램으로 테스트 메시지를 발송했습니다!", icon="📱")
        else:
            st.sidebar.error("발송 실패: 봇에게 /start를 보냈는지 확인하세요.")
else:
    st.sidebar.info("💡 Secrets에 TELEGRAM_BOT_TOKEN과 CHAT_ID를 등록하세요.")

st.sidebar.markdown("---")
if st.sidebar.button("🔄 최신 시세 강제 갱신"):
    st.cache_data.clear()
    st.rerun()

if "APP_PASSWORD" in st.secrets:
    if st.sidebar.button("🔒 로그아웃"):
        st.session_state["authenticated"] = False
        st.rerun()

# ==================== 데이터 및 지표 계산 함수 ====================
period_map_yf = {
    "1일": "1d", "3일": "3d", "5일": "5d", "1달": "1mo", "1개월": "1mo", 
    "2개월": "2mo", "6개월": "6mo", "1년": "1y", "3년": "3y", "5년": "5y", "10년": "10y", "최대(All)": "max"
}

@st.cache_data(ttl=60)
def load_and_calculate_data(code, tf, period_str):
    interval = tf_config[tf]["interval"]
    yf_period = period_map_yf.get(period_str, "1y")

    if "m" in interval:
        df = pd.DataFrame()
        if code.isdigit() and len(code) == 6:
            for suffix in [".KS", ".KQ"]:
                try:
                    ticker_obj = yf.Ticker(f"{code}{suffix}")
                    temp_df = ticker_obj.history(period=yf_period, interval=interval)
                    if not temp_df.empty:
                        df = temp_df
                        break
                except Exception:
                    continue
        elif "/" in code:
            c_base, c_quote = code.split("/")
            if c_quote in ["KRW", "USD", "JPY", "EUR", "CNY", "GBP"] and c_base in ["USD", "JPY", "EUR", "CNY", "GBP"]:
                yf_code = f"{c_base}{c_quote}=X"
            else:
                yf_code = code.replace("/", "-")
            try:
                df = yf.Ticker(yf_code).history(period=yf_period, interval=interval)
            except Exception:
                df = pd.DataFrame()
        else:
            try:
                df = yf.Ticker(code).history(period=yf_period, interval=interval)
            except Exception:
                df = pd.DataFrame()
            
        if df.empty:
            return df
        
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
    else:
        today = datetime.date.today()
        days_calc = {"1달": 30, "6개월": 180, "1년": 365, "3년": 365*3, "5년": 365*5, "10년": 365*10, "최대(All)": 365*20}
        needed_days = days_calc.get(period_str, 365) + 300
        start_d = today - datetime.timedelta(days=needed_days)
        
        try:
            df = fdr.DataReader(code, start_d)
        except Exception:
            df = pd.DataFrame()

        if df.empty:
            return df

        if tf == "주봉":
            df = df.resample('W-FRI').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last', 'Volume':'sum'}).dropna()
        elif tf == "월봉":
            df = df.resample('ME').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last', 'Volume':'sum'}).dropna()

    if 'Volume' not in df.columns:
        df['Volume'] = 0

    df['20선'] = df['Close'].rolling(20).mean()
    df['50선'] = df['Close'].rolling(50).mean()
    df['100선'] = df['Close'].rolling(100).mean()
    df['200선'] = df['Close'].rolling(200).mean()

    std20 = df['Close'].rolling(20).std()
    df['BB_Upper'] = df['20선'] + (std20 * 2)
    df['BB_Lower'] = df['20선'] - (std20 * 2)

    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    exp12 = df['Close'].ewm(span=12, adjust=False).mean()
    exp26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp12 - exp26
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']

    if "m" not in interval:
        if period_str != "최대(All)":
            days_disp = days_calc.get(period_str, 365)
            disp_start = today - datetime.timedelta(days=days_disp)
            df = df.loc[df.index >= pd.to_datetime(disp_start)]

    return df

# ==================== 🏢 4~5개년 과거 분기 실적(Pure Quarterly) 다중 크롤러 ====================
@st.cache_data(ttl=3600)
def load_pure_quarterly_financials(code):
    """국내 주식은 네이버 모바일 API/FnGuide/포괄손익계산서 다중 파싱으로 과거 4~5개년 분기 실적 복원"""
    if str(code).isdigit() and len(str(code)) == 6:
        res_dict = {}
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        
        # 1. 네이버 모바일 금융 API (과거 및 최신 분기 데이터 JSON)
        try:
            m_url = f"https://m.stock.naver.com/api/stock/{code}/finance/quarter"
            m_res = requests.get(m_url, headers=headers, timeout=5)
            if m_res.status_code == 200:
                data_json = m_res.json()
                if "financeInfo" in data_json:
                    fin_data = data_json["financeInfo"]
                    # 분기 목록 추출
                    periods = fin_data.get("periods", [])
                    rev_list = fin_data.get("totalRevenue", [])
                    op_list = fin_data.get("operatingIncome", [])
                    net_list = fin_data.get("netIncome", [])
                    
                    for idx, p_str in enumerate(periods):
                        m = re.search(r'(\d{4})\.(\d{2})', str(p_str))
                        if m:
                            y, mo = m.group(1), m.group(2)
                            last_days = {'03': '31', '06': '30', '09': '30', '12': '31'}
                            dt_key = pd.to_datetime(f"{y}-{mo}-{last_days.get(mo, '28')}")
                            
                            r_val = float(rev_list[idx]) if idx < len(rev_list) and rev_list[idx] is not None else np.nan
                            o_val = float(op_list[idx]) if idx < len(op_list) and op_list[idx] is not None else np.nan
                            n_val = float(net_list[idx]) if idx < len(net_list) and net_list[idx] is not None else np.nan
                            
                            if pd.notna(r_val) or pd.notna(n_val):
                                res_dict[dt_key] = {
                                    'Revenue_Eok': r_val,
                                    'OperatingIncome_Eok': o_val,
                                    'NetIncome_Eok': n_val
                                }
        except Exception:
            pass

        # 2. FnGuide 포괄손익계산서 전체 분기 테이블 파싱 (과거 3~5개년 분기 완벽 보완)
        try:
            fn_url = f"http://comp.fnguide.com/SVO2/ASP/SVD_Finance.asp?pGB=1&gicode=A{code}"
            fn_res = requests.get(fn_url, headers=headers, timeout=6)
            if fn_res.status_code == 200:
                tables = pd.read_html(StringIO(fn_res.text))
                for t in tables:
                    if any("매출액" in str(idx) for idx in t.iloc[:, 0]) or any("매출액" in str(c) for c in t.columns):
                        df_t = t.copy()
                        df_t.set_index(df_t.columns[0], inplace=True)
                        date_cols = [c for c in df_t.columns if re.search(r'\d{4}/(03|06|09|12)', str(c)) and '전년' not in str(c)]
                        
                        for d_col in date_cols:
                            m = re.search(r'(\d{4})/(03|06|09|12)', str(d_col))
                            if m:
                                y, mo = m.group(1), m.group(2)
                                last_days = {'03': '31', '06': '30', '09': '30', '12': '31'}
                                dt_key = pd.to_datetime(f"{y}-{mo}-{last_days.get(mo, '28')}")
                                
                                rev_val = np.nan
                                op_val = np.nan
                                net_val = np.nan
                                
                                for r_idx in df_t.index:
                                    r_str = str(r_idx).replace(" ", "")
                                    val_clean = pd.to_numeric(str(df_t.loc[r_idx, d_col]).replace(',', ''), errors='coerce')
                                    
                                    if ("매출액" in r_str or "수익(매출액)" in r_str) and pd.isna(rev_val):
                                        rev_val = val_clean
                                    elif "영업이익" in r_str and pd.isna(op_val):
                                        op_val = val_clean
                                    elif ("당기순이익" in r_str or "순이익" in r_str) and pd.isna(net_val):
                                        net_val = val_clean
                                        
                                if pd.notna(rev_val) or pd.notna(net_val):
                                    if dt_key not in res_dict:
                                        res_dict[dt_key] = {}
                                    if pd.notna(rev_val): res_dict[dt_key]['Revenue_Eok'] = rev_val
                                    if pd.notna(op_val): res_dict[dt_key]['OperatingIncome_Eok'] = op_val
                                    if pd.notna(net_val): res_dict[dt_key]['NetIncome_Eok'] = net_val
        except Exception:
            pass

        # 3. 네이버 증권 PC 메인 표 결합
        try:
            naver_url = f"https://finance.naver.com/item/main.naver?code={code}"
            n_res = requests.get(naver_url, headers=headers, timeout=5)
            if n_res.status_code == 200:
                n_tables = pd.read_html(StringIO(n_res.text))
                for t in n_tables:
                    if any("주요재무정보" in str(col) for col in t.columns) or any("매출액" in str(idx) for idx in t.iloc[:, 0]):
                        df_nt = t.copy()
                        if isinstance(df_nt.columns, pd.MultiIndex):
                            q_cols = [c for c in df_nt.columns if "분기" in str(c[0]) and re.search(r'\d{4}\.\d{2}', str(c[1]))]
                            df_nt.set_index(df_nt.columns[0], inplace=True)
                            
                            for col_tuple in q_cols:
                                m = re.search(r'(\d{4})\.(\d{2})', str(col_tuple[1]))
                                if m:
                                    y, mo = m.group(1), m.group(2)
                                    last_days = {'03': '31', '06': '30', '09': '30', '12': '31'}
                                    dt_key = pd.to_datetime(f"{y}-{mo}-{last_days.get(mo, '28')}")

                                    rev_val = np.nan
                                    op_val = np.nan
                                    net_val = np.nan

                                    for r_idx in df_nt.index:
                                        r_str = str(r_idx)
                                        val_clean = pd.to_numeric(str(df_nt.loc[r_idx, col_tuple]).replace(',', ''), errors='coerce')
                                        if "매출액" in r_str and pd.isna(rev_val):
                                            rev_val = val_clean
                                        elif "영업이익" in r_str and pd.isna(op_val):
                                            op_val = val_clean
                                        elif ("당기순이익" in r_str or "순이익" in r_str) and pd.isna(net_val):
                                            net_val = val_clean

                                    if pd.notna(rev_val) or pd.notna(net_val):
                                        if dt_key not in res_dict:
                                            res_dict[dt_key] = {}
                                        if pd.notna(rev_val): res_dict[dt_key]['Revenue_Eok'] = rev_val
                                        if pd.notna(op_val): res_dict[dt_key]['OperatingIncome_Eok'] = op_val
                                        if pd.notna(net_val): res_dict[dt_key]['NetIncome_Eok'] = net_val
        except Exception:
            pass

        if res_dict:
            fin_df = pd.DataFrame.from_dict(res_dict, orient='index').sort_index()
            if 'Revenue_Eok' in fin_df.columns:
                fin_df['Rev_YoY'] = fin_df['Revenue_Eok'].pct_change(4) * 100
                fin_df['Rev_YoY'] = fin_df['Rev_YoY'].fillna(fin_df['Revenue_Eok'].pct_change(1) * 100)
            if 'NetIncome_Eok' in fin_df.columns:
                fin_df['Net_YoY'] = fin_df['NetIncome_Eok'].pct_change(4) * 100
                fin_df['Net_YoY'] = fin_df['NetIncome_Eok'].fillna(fin_df['NetIncome_Eok'].pct_change(1) * 100)

            if 'Revenue_Eok' in fin_df.columns and 'NetIncome_Eok' in fin_df.columns:
                fin_df['Net_Margin'] = (fin_df['NetIncome_Eok'] / fin_df['Revenue_Eok']) * 100

            return fin_df.dropna(how='all')

    # 해외 주식 (미국 주식 등) -> Yahoo Finance 분기 데이터
    try:
        ticker = yf.Ticker(code)
        q_fin = ticker.quarterly_financials
        if q_fin is None or q_fin.empty:
            return pd.DataFrame()

        q_df = q_fin.T
        q_df.index = pd.to_datetime(q_df.index)
        q_df = q_df.sort_index()

        res = pd.DataFrame(index=q_df.index)
        for rev_col in ['Total Revenue', 'Operating Revenue', 'Revenue']:
            if rev_col in q_df.columns:
                res['Revenue_Eok'] = q_df[rev_col] / 1_000_000_000
                break
                
        for net_col in ['Net Income', 'Net Income Common Stockholders']:
            if net_col in q_df.columns:
                res['NetIncome_Eok'] = q_df[net_col] / 1_000_000_000
                break

        for op_col in ['Operating Income', 'Operating Revenue']:
            if op_col in q_df.columns:
                res['OperatingIncome_Eok'] = q_df[op_col] / 1_000_000_000
                break

        if 'Revenue_Eok' in res.columns and len(res) >= 5:
            res['Rev_YoY'] = res['Revenue_Eok'].pct_change(4) * 100
        else:
            res['Rev_YoY'] = res['Revenue_Eok'].pct_change(1) * 100 if 'Revenue_Eok' in res.columns else np.nan

        if 'NetIncome_Eok' in res.columns and len(res) >= 5:
            res['Net_YoY'] = res['NetIncome_Eok'].pct_change(4) * 100
        else:
            res['Net_YoY'] = res['NetIncome_Eok'].pct_change(1) * 100 if 'NetIncome_Eok' in res.columns else np.nan

        if 'Revenue_Eok' in res.columns and 'NetIncome_Eok' in res.columns:
            res['Net_Margin'] = (res['NetIncome_Eok'] / res['Revenue_Eok']) * 100

        return res.dropna(how='all')
    except Exception:
        return pd.DataFrame()

# ==================== ⚡ 사용자 맞춤 조건 수급 돌파 스캐너 ====================
@st.cache_data(ttl=300)
def scan_custom_volume_surge(lookback_days, threshold_won, min_chg_rate=0.0):
    try:
        today = datetime.date.today()
        sample_hist = fdr.DataReader("005930", today - datetime.timedelta(days=15))
        scan_date = sample_hist.index[-1].strftime('%Y-%m-%d') if (sample_hist is not None and not sample_hist.empty) else str(today)

        df_krx = fdr.StockListing('KRX')
        if df_krx.empty:
            return pd.DataFrame(), scan_date

        amt_col = None
        for col in ['Amount', 'TradeValue', 'amount', 'VolumeValue']:
            if col in df_krx.columns:
                amt_col = col
                break

        if amt_col is None and 'Volume' in df_krx.columns and 'Close' in df_krx.columns:
            df_krx['Estimated_Amount'] = df_krx['Volume'] * df_krx['Close']
            amt_col = 'Estimated_Amount'

        if amt_col is None:
            return pd.DataFrame(), scan_date

        vol_col = 'Volume' if 'Volume' in df_krx.columns else None

        targets = df_krx[df_krx[amt_col] >= threshold_won].copy()

        if targets.empty:
            return pd.DataFrame(), scan_date

        results = []
        calendar_days = int(lookback_days * 1.8) + 25
        start_date = today - datetime.timedelta(days=calendar_days)

        for _, row in targets.iterrows():
            code = str(row['Code']).zfill(6)
            name = row['Name']
            curr_amount = row[amt_col]
            curr_vol = row[vol_col] if vol_col else 1.0
            marcap_val = row.get('Marcap', 0)

            if not is_valid_normal_stock(name, code, curr_vol, curr_amount):
                continue

            try:
                hist = fdr.DataReader(code, start_date)
                if hist is not None and len(hist) >= min(10, lookback_days):
                    if hist['Volume'].iloc[-1] <= 0:
                        continue

                    if 'Amount' in hist.columns and hist['Amount'].iloc[-1] > 0:
                        amounts = hist['Amount']
                    else:
                        amounts = hist['Close'] * hist['Volume']

                    actual_lookback = min(lookback_days, len(amounts) - 1)
                    prev_period_amounts = amounts.iloc[-(actual_lookback + 1):-1]
                    max_period_amt = prev_period_amounts.max()
                    avg_period_amt = prev_period_amounts.mean()
                    yesterday_amt = prev_period_amounts.iloc[-1]

                    if max_period_amt < threshold_won and curr_amount > yesterday_amt:
                        curr_close = hist['Close'].iloc[-1]
                        prev_close = hist['Close'].iloc[-2]
                        real_chg_rate = ((curr_close - prev_close) / prev_close) * 100 if prev_close != 0 else 0.0

                        if real_chg_rate >= min_chg_rate:
                            surge_ratio = (curr_amount / avg_period_amt) * 100 if avg_period_amt > 0 else 999.0
                            results.append({
                                'Code': code,
                                'Name': name,
                                'Close': curr_close,
                                'ChgRate': real_chg_rate,
                                '당일거래대금(억원)': round(curr_amount / 100_000_000, 1),
                                '어제거래대금(억원)': round(yesterday_amt / 100_000_000, 1),
                                f'{lookback_days}일평균(억원)': round(avg_period_amt / 100_000_000, 1),
                                '수급폭증률': round(surge_ratio, 0),
                                '시가총액(억원)': round(marcap_val / 100_000_000, 0),
                                'Market': row.get('Market', 'KRX')
                            })
            except Exception:
                continue

        if not results:
            return pd.DataFrame(), scan_date

        res_df = pd.DataFrame(results).sort_values(by='당일거래대금(억원)', ascending=False)
        return res_df, scan_date

    except Exception:
        return pd.DataFrame(), str(datetime.date.today())

# ==================== 🧊 장기 초소외주 스캐너 ====================
@st.cache_data(ttl=600)
def scan_dormant_stocks(lookback_days, max_cap_won, min_marcap_eok, max_marcap_eok):
    try:
        today = datetime.date.today()
        sample_hist = fdr.DataReader("005930", today - datetime.timedelta(days=15))
        scan_date = sample_hist.index[-1].strftime('%Y-%m-%d') if (sample_hist is not None and not sample_hist.empty) else str(today)

        df_krx = fdr.StockListing('KRX')
        if df_krx.empty:
            return pd.DataFrame(), scan_date

        amt_col = None
        for col in ['Amount', 'TradeValue', 'amount', 'VolumeValue']:
            if col in df_krx.columns:
                amt_col = col
                break

        if amt_col is None and 'Volume' in df_krx.columns and 'Close' in df_krx.columns:
            df_krx['Estimated_Amount'] = df_krx['Volume'] * df_krx['Close']
            amt_col = 'Estimated_Amount'

        vol_col = 'Volume' if 'Volume' in df_krx.columns else None

        min_marcap_won = min_marcap_eok * 100_000_000
        max_marcap_won = max_marcap_eok * 100_000_000
        
        cands = df_krx[
            (df_krx[amt_col] < max_cap_won) & 
            (df_krx['Marcap'] >= min_marcap_won) & 
            (df_krx['Marcap'] <= max_marcap_won)
        ].copy()

        if cands.empty:
            return pd.DataFrame(), scan_date

        results = []
        calendar_days = int(lookback_days * 1.8) + 30
        start_date = today - datetime.timedelta(days=calendar_days)

        sample_cands = cands.sort_values(by='Marcap', ascending=False).head(150)

        for _, row in sample_cands.iterrows():
            code = str(row['Code']).zfill(6)
            name = row['Name']
            marcap_val = row.get('Marcap', 0)
            curr_amt_krx = row[amt_col]
            curr_vol_krx = row[vol_col] if vol_col else 1.0

            if not is_valid_normal_stock(name, code, curr_vol_krx, curr_amt_krx):
                continue

            try:
                hist = fdr.DataReader(code, start_date)
                if hist is not None and len(hist) >= min(60, int(lookback_days * 0.5)):
                    if hist['Volume'].iloc[-1] <= 0:
                        continue

                    if 'Amount' in hist.columns and hist['Amount'].iloc[-1] > 0:
                        amounts = hist['Amount']
                    else:
                        amounts = hist['Close'] * hist['Volume']

                    actual_lookback = min(lookback_days, len(amounts))
                    period_amounts = amounts.iloc[-actual_lookback:]
                    max_amt = period_amounts.max()
                    avg_amt = period_amounts.mean()
                    curr_amt = period_amounts.iloc[-1]

                    if max_amt < max_cap_won:
                        curr_close = hist['Close'].iloc[-1]
                        prev_close = hist['Close'].iloc[-2] if len(hist) > 1 else curr_close
                        real_chg_rate = ((curr_close - prev_close) / prev_close) * 100 if prev_close != 0 else 0.0

                        results.append({
                            'Code': code,
                            'Name': name,
                            'Close': curr_close,
                            'ChgRate': real_chg_rate,
                            f'{lookback_days}일최대거래대금(억원)': round(max_amt / 100_000_000, 1),
                            f'{lookback_days}일평균거래대금(억원)': round(avg_amt / 100_000_000, 2),
                            '당일거래대금(억원)': round(curr_amt / 100_000_000, 2),
                            '시가총액(억원)': round(marcap_val / 100_000_000, 0),
                            'Market': row.get('Market', 'KRX')
                        })
            except Exception:
                continue

        if not results:
            return pd.DataFrame(), scan_date

        res_df = pd.DataFrame(results).sort_values(by=f'{lookback_days}일평균거래대금(억원)', ascending=True)
        return res_df, scan_date

    except Exception:
        return pd.DataFrame(), str(datetime.date.today())

# ==================== 본문 렌더링 ====================
try:
    display_df = load_and_calculate_data(selected_code, timeframe, selected_period)
    
    if display_df is None or display_df.empty:
        st.error(f"티커 '{selected_code}'의 데이터를 가져올 수 없습니다. 주기 및 선택 정보를 확인해 주세요.")
    else:
        latest_close = float(display_df['Close'].iloc[-1])
        prev_close = float(display_df['Close'].iloc[-2]) if len(display_df) > 1 else latest_close
        price_chg = latest_close - prev_close
        price_chg_pct = (price_chg / prev_close) * 100 if prev_close != 0 else 0

        if currency_symbol == "USD":
            formatted_close = f"{latest_close:,.2f}" if latest_close >= 1 else f"{latest_close:.4f}"
            delta_str = f"{price_chg:+,.2f} ({price_chg_pct:+.2f}%)"
        elif "^" in selected_code:
            formatted_close = f"{latest_close:.3f}%"
            delta_str = f"{price_chg:+.3f}%p ({price_chg_pct:+.2f}%)"
        else:
            formatted_close = f"{int(latest_close):,}" if category == "국내주식 (KRX)" else f"{latest_close:,.2f}"
            delta_str = f"{int(price_chg):+,} ({price_chg_pct:+.2f}%)" if category == "국내주식 (KRX)" else f"{price_chg:+,.2f} ({price_chg_pct:+.2f}%)"

        st.markdown("### 📌 시장 핵심 요약")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("선택 종목/자산", selected_name.split(' - ')[0].split(' (')[0])
        m2.metric("현재 시세", f"{formatted_close} {currency_symbol}", delta=delta_str)

        high_val = display_df['High'].max()
        low_val = display_df['Low'].min()
        drop_from_high = ((latest_close - high_val) / high_val) * 100
        
        cummax = display_df['Close'].cummax()
        drawdown = (display_df['Close'] - cummax) / cummax
        mdd = drawdown.min() * 100

        m3.metric("기간 최고 / 최저", f"{high_val:,.0f} / {low_val:,.0f}" if (currency_symbol=="원" and category=="국내주식 (KRX)") else f"{high_val:,.2f} / {low_val:,.2f}", f"고점대비 {drop_from_high:+.1f}%")
        m4.metric("기간 내 MDD (최대 낙폭)", f"{mdd:.2f}%", delta_color="inverse")

        st.markdown("---")
        st.markdown("#### 🚦 기술적 지표 자동 진단 시그널")
        sig_col1, sig_col2, sig_col3, sig_col4 = st.columns(4)

        latest_ma20 = display_df['20선'].iloc[-1]
        latest_ma50 = display_df['50선'].iloc[-1]
        if pd.notna(latest_ma20) and pd.notna(latest_ma50):
            if latest_ma20 > latest_ma50:
                sig_col1.markdown("이평선 추세: <span class='signal-badge-bull'>골든크로스 구간 (정배열)</span>", unsafe_allow_html=True)
            else:
                sig_col1.markdown("이평선 추세: <span class='signal-badge-bear'>데드크로스 구간 (역배열)</span>", unsafe_allow_html=True)
        else:
            sig_col1.markdown("이평선 추세: <span class='signal-badge-neutral'>데이터 계산 중</span>", unsafe_allow_html=True)

        latest_rsi = display_df['RSI'].iloc[-1]
        if pd.notna(latest_rsi):
            if latest_rsi >= 70:
                sig_col2.markdown(f"RSI({latest_rsi:.1f}): <span class='signal-badge-bear'>과열 (매도 주의)</span>", unsafe_allow_html=True)
            elif latest_rsi <= 30:
                sig_col2.markdown(f"RSI({latest_rsi:.1f}): <span class='signal-badge-bull'>침체 (반등 기대)</span>", unsafe_allow_html=True)
            else:
                sig_col2.markdown(f"RSI({latest_rsi:.1f}): <span class='signal-badge-neutral'>중립 구간</span>", unsafe_allow_html=True)
        else:
            sig_col2.markdown("RSI: -", unsafe_allow_html=True)

        latest_bb_up = display_df['BB_Upper'].iloc[-1]
        latest_bb_low = display_df['BB_Lower'].iloc[-1]
        if pd.notna(latest_bb_up) and pd.notna(latest_bb_low):
            if latest_close >= latest_bb_up:
                sig_col3.markdown("볼린저 밴드: <span class='signal-badge-bear'>상단선 돌파 (단기과열)</span>", unsafe_allow_html=True)
            elif latest_close <= latest_bb_low:
                sig_col3.markdown("볼린저 밴드: <span class='signal-badge-bull'>하단선 이탈 (과매도)</span>", unsafe_allow_html=True)
            else:
                sig_col3.markdown("볼린저 밴드: <span class='signal-badge-neutral'>밴드 내부 순항</span>", unsafe_allow_html=True)
        else:
            sig_col3.markdown("볼린저 밴드: -", unsafe_allow_html=True)

        latest_macd_hist = display_df['MACD_Hist'].iloc[-1]
        if pd.notna(latest_macd_hist):
            if latest_macd_hist > 0:
                sig_col4.markdown(f"MACD Hist: <span class='signal-badge-bull'>상승 모멘텀 (+{latest_macd_hist:.2f})</span>", unsafe_allow_html=True)
            else:
                sig_col4.markdown(f"MACD Hist: <span class='signal-badge-bear'>하락 모멘텀 ({latest_macd_hist:.2f})</span>", unsafe_allow_html=True)
        else:
            sig_col4.markdown("MACD Hist: -", unsafe_allow_html=True)

        st.markdown("---")
        
        tab_titles = [
            "📊 인터랙티브 종합 차트", 
            "📈 벤치마크 상대 수익률(%) 비교", 
            "🔥 맞춤 조건 수급 폭발 스캐너",
            "🧊 장기 초소외주 (1년 거래대금 100억 미만) 탐색기",
            "🏢 펀더멘털 & 실적-주가 복합 차트 (TrendSpider)"
        ]
        
        active_tab = st.radio(
            "탭 선택",
            tab_titles,
            horizontal=True,
            label_visibility="collapsed",
            key="tab_selector"
        )

        if active_tab == "📊 인터랙티브 종합 차트":
            is_intraday = "m" in tf_config[timeframe]["interval"]
            if is_intraday:
                x_data = display_df.index.strftime('%Y-%m-%d %H:%M')
            else:
                x_data = display_df.index

            has_vol = bool(display_df['Volume'].sum() > 0)
            rows = 1
            subplot_titles = ["가격 및 이평선 / 볼린저 밴드"]
            row_heights = [0.55]
            
            if has_vol:
                rows += 1
                subplot_titles.append("거래량")
                row_heights.append(0.15)
            if show_macd:
                rows += 1
                subplot_titles.append("MACD (12, 26, 9)")
                row_heights.append(0.15)
            if show_rsi:
                rows += 1
                subplot_titles.append("RSI (14)")
                row_heights.append(0.15)
                
            total_h = sum(row_heights)
            norm_heights = [h / total_h for h in row_heights]

            fig = make_subplots(
                rows=rows, 
                cols=1, 
                shared_xaxes=True, 
                vertical_spacing=0.03,
                row_heights=norm_heights,
                subplot_titles=subplot_titles
            )

            current_row = 1

            fig.add_trace(
                go.Candlestick(
                    x=x_data,
                    open=display_df['Open'], high=display_df['High'],
                    low=display_df['Low'], close=display_df['Close'],
                    name='시세', increasing_line_color='#26A69A', decreasing_line_color='#EF5350'
                ),
                row=current_row, col=1
            )

            if show_ma:
                ma_colors = {'20선': '#FF9800', '50선': '#AB47BC', '100선': '#29B6F6', '200선': '#B0BEC5'}
                for ma_name, color in ma_colors.items():
                    if ma_name in display_df.columns:
                        fig.add_trace(
                            go.Scatter(x=x_data, y=display_df[ma_name], mode='lines', name=ma_name, line=dict(color=color, width=1.2)),
                            row=current_row, col=1
                        )

            if show_bb:
                fig.add_trace(
                    go.Scatter(x=x_data, y=display_df['BB_Upper'], mode='lines', name='볼린저 상단', line=dict(color='rgba(200, 200, 200, 0.6)', dash='dot')),
                    row=current_row, col=1
                )
                fig.add_trace(
                    go.Scatter(x=x_data, y=display_df['BB_Lower'], mode='lines', name='볼린저 하단', line=dict(color='rgba(200, 200, 200, 0.6)', dash='dot'), fill='tonexty', fillcolor='rgba(255, 255, 255, 0.05)'),
                    row=current_row, col=1
                )

            if has_vol:
                current_row += 1
                vol_colors = ['#26A69A' if row['Close'] >= row['Open'] else '#EF5350' for _, row in display_df.iterrows()]
                fig.add_trace(
                    go.Bar(x=x_data, y=display_df['Volume'], name='거래량', marker_color=vol_colors),
                    row=current_row, col=1
                )

            if show_macd:
                current_row += 1
                fig.add_trace(
                    go.Scatter(x=x_data, y=display_df['MACD'], mode='lines', name='MACD', line=dict(color='#29B6F6', width=1.3)),
                    row=current_row, col=1
                )
                fig.add_trace(
                    go.Scatter(x=display_df.index if not is_intraday else x_data, y=display_df['MACD_Signal'], mode='lines', name='Signal', line=dict(color='#FF7043', width=1.3)),
                    row=current_row, col=1
                )
                hist_colors = ['#26A69A' if v >= 0 else '#EF5350' for v in display_df['MACD_Hist']]
                fig.add_trace(
                    go.Bar(x=x_data, y=display_df['MACD_Hist'], name='MACD Hist', marker_color=hist_colors),
                    row=current_row, col=1
                )

            if show_rsi:
                current_row += 1
                fig.add_trace(
                    go.Scatter(x=x_data, y=display_df['RSI'], mode='lines', name='RSI(14)', line=dict(color='#AB47BC', width=1.5)),
                    row=current_row, col=1
                )
                fig.add_hline(y=70, line_dash="dash", line_color="#EF5350", row=current_row, col=1, opacity=0.7)
                fig.add_hline(y=30, line_dash="dash", line_color="#26A69A", row=current_row, col=1, opacity=0.7)

            total_chart_height = 580 + (rows - 1) * 140
            fig.update_layout(
                height=total_chart_height,
                template="plotly_dark",
                paper_bgcolor="#0E1117",
                plot_bgcolor="#0E1117",
                xaxis_rangeslider_visible=False,
                margin=dict(l=10, r=10, t=30, b=10),
                hovermode='x unified'
            )

            if is_intraday:
                fig.update_xaxes(type='category', nticks=10)
            else:
                fig.update_xaxes(type='date')

            st.plotly_chart(fig, use_container_width=True)

        elif active_tab == "📈 벤치마크 상대 수익률(%) 비교":
            st.markdown("#### 📊 타 자산 및 주요 지수와의 누적 수익률(%) 비교")
            comp_targets = {
                "S&P 500 지수 (미국 대형주)": "US500",
                "나스닥 100 지수 (기술주)": "IXIC",
                "KOSPI 지수 (국내 종합)": "KS11",
                "Gold (금 선물)": "GC=F",
                "비트코인 (BTC/USD)": "BTC/USD",
                "원/달러 환율 (USD/KRW)": "USD/KRW",
                "TLT (미국 20년+ 국채 ETF)": "TLT"
            }
            selected_comp = st.selectbox("비교할 대상 자산/지수 선택", options=list(comp_targets.keys()), index=0)
            comp_code = comp_targets[selected_comp]
            
            try:
                comp_df = fdr.DataReader(comp_code, display_df.index[0])
                if not comp_df.empty:
                    base_main = display_df['Close'] / display_df['Close'].iloc[0] * 100 - 100
                    base_comp = comp_df['Close'] / comp_df['Close'].iloc[0] * 100 - 100

                    comp_fig = go.Figure()
                    comp_fig.add_trace(go.Scatter(x=base_main.index, y=base_main, mode='lines', name=f"기준: {selected_name.split(' - ')[0].split(' (')[0]}", line=dict(color='#29B6F6', width=2)))
                    comp_fig.add_trace(go.Scatter(x=base_comp.index, y=base_comp, mode='lines', name=f"비교: {selected_comp.split(' (')[0]}", line=dict(color='#FFB74D', width=2, dash='dot')))
                    
                    comp_fig.add_hline(y=0, line_dash="solid", line_color="gray", opacity=0.5)
                    comp_fig.update_layout(
                        height=500,
                        template="plotly_dark",
                        paper_bgcolor="#0E1117",
                        plot_bgcolor="#0E1117",
                        yaxis_title="누적 수익률 (%)",
                        margin=dict(l=10, r=10, t=30, b=10),
                        hovermode='x unified'
                    )
                    st.plotly_chart(comp_fig, use_container_width=True)
                else:
                    st.warning("비교 대상 데이터를 가져올 수 없습니다.")
            except Exception as e:
                st.error(f"수익률 비교 중 오류: {e}")

        elif active_tab == "🔥 맞춤 조건 수급 폭발 스캐너":
            st.markdown("### 🔥 맞춤 조건 수급 폭발 주도주 실시간 스캐너")
            st.caption("🛡️ 거래정지, 상장폐지, 관리/환기종목, 우선주, 스팩, 리츠는 자동으로 완벽 제외됩니다.")
            
            with st.container():
                st.markdown("##### ⚙️ 검색 조건 직접 입력")
                p_col1, p_col2, p_col3, p_col4 = st.columns([1.2, 1.2, 1.0, 1.0])
                
                with p_col1:
                    input_lookback = st.number_input(
                        "📅 과거 잠복 거래일수",
                        min_value=1,
                        max_value=365,
                        value=20,
                        step=5
                    )
                with p_col2:
                    input_threshold_eok = st.number_input(
                        "💰 돌파 거래대금 (억원 단위)",
                        min_value=10,
                        max_value=10000,
                        value=500,
                        step=50
                    )
                with p_col3:
                    input_min_chg = st.selectbox(
                        "📈 최소 당일 상승률",
                        options=[0.0, 3.0, 5.0, 7.0, 10.0, 15.0],
                        index=0,
                        format_func=lambda x: "전체 (제한없음)" if x == 0.0 else f"+{x:.0f}% 이상 상승"
                    )
                with p_col4:
                    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                    run_search = st.button("🔍 조건 검색 실행", type="primary", use_container_width=True)

            threshold_won_val = input_threshold_eok * 100_000_000
            
            if run_search:
                with st.spinner(f"KRX 전 종목 대상 {input_lookback}일 잠복 / {input_threshold_eok:,}억 돌파 종목 초고속 스캔 중..."):
                    res_df, s_date = scan_custom_volume_surge(input_lookback, threshold_won_val, input_min_chg)
                    st.session_state["scan_results_df"] = res_df
                    st.session_state["scan_results_date"] = s_date
                    st.session_state["last_scanned_params"] = {
                        "lookback": input_lookback,
                        "threshold": input_threshold_eok,
                        "min_chg": input_min_chg
                    }

            if st.session_state["scan_results_df"] is not None:
                surge_data = st.session_state["scan_results_df"]
                scan_date = st.session_state["scan_results_date"]
                p = st.session_state["last_scanned_params"]
                avg_col_name = f'{p["lookback"]}일평균(억원)'

                st.markdown("---")
                
                head_col1, head_col2 = st.columns([4, 1.3])
                with head_col1:
                    if scan_date:
                        st.caption(f"📅 **분석 기준 거래일자:** `{scan_date}` | **적용 조건:** 직전 `{p['lookback']}일`간 `{p['threshold']:,}억` 미만 $\\rightarrow$ 당일 `{p['threshold']:,}억` 첫 돌파")
                with head_col2:
                    if not surge_data.empty:
                        if st.button("📲 텔레그램 전체 전송", key="btn_send_surge_all", use_container_width=True):
                            total_cnt = len(surge_data)
                            chunk_size = 20
                            sent_ok = True
                            
                            for start_idx in range(0, total_cnt, chunk_size):
                                end_idx = min(start_idx + chunk_size, total_cnt)
                                page_no = (start_idx // chunk_size) + 1
                                total_pages = ((total_cnt - 1) // chunk_size) + 1
                                
                                lines = [
                                    f"🚨 *[QPZM 수급 폭발 종목]* ({page_no}/{total_pages})",
                                    f"📅 기준일: `{scan_date}` | 총 {total_cnt}개 중 {start_idx+1}~{end_idx}번째",
                                    f"🎯 조건: {p['lookback']}일 잠복 $\\rightarrow$ {p['threshold']:,}억 첫 돌파\n"
                                ]
                                
                                for rank, (_, r) in enumerate(surge_data.iloc[start_idx:end_idx].iterrows(), start=start_idx+1):
                                    lines.append(f"{rank}. *{r['Name']}* (`{r['Code']}`): {r['Close']:,.0f}원 ({r['ChgRate']:+.2f}%) | 거래대금: *{r['당일거래대금(억원)']}억* (폭증 {r['수급폭증률']:,.0f}%)")
                                
                                if not send_telegram_message("\n".join(lines)):
                                    sent_ok = False
                                time.sleep(0.3)
                                
                            if sent_ok:
                                st.toast(f"텔레그램으로 전체 {total_cnt}개 종목 알림을 전송했습니다!", icon="🚀")
                            else:
                                st.error("일부 메시지 전송 실패")

                if not surge_data.empty:
                    st.success(f"조건을 만족한 주도주 **{len(surge_data)}개**가 포착되었습니다!")
                    
                    st.dataframe(
                        surge_data.style.format({
                            'Close': '{:,.0f}원',
                            'ChgRate': '{:+.2f}%',
                            '당일거래대금(억원)': '{:,.1f} 억',
                            '어제거래대금(억원)': '{:,.1f} 억',
                            avg_col_name: '{:,.1f} 억' if avg_col_name in surge_data.columns else '{:,.1f}',
                            '수급폭증률': '{:,.0f}%',
                            '시가총액(억원)': '{:,.0f} 억'
                        }),
                        use_container_width=True
                    )
                    
                    st.markdown("---")
                    st.markdown("#### 🎯 종목별 상세 보기 및 원클릭 차트 이동")
                    
                    for idx, r in surge_data.iterrows():
                        c_code = r['Code']
                        c_name = r['Name']
                        c_close = r['Close']
                        c_chg = r['ChgRate']
                        c_amt = r['당일거래대금(억원)']
                        c_yest_amt = r['어제거래대금(억원)']
                        c_prev_amt = r[avg_col_name] if avg_col_name in r else 0.0
                        c_surge = r['수급폭증률']
                        c_marcap = r['시가총액(억원)']
                        
                        with st.container():
                            col_info, col_btn = st.columns([5, 1])
                            with col_info:
                                st.markdown(
                                    f"**{c_name}** (`{c_code}`) | **종가:** {c_close:,.0f}원 ({c_chg:+.2f}%) | "
                                    f"**당일 거래대금:** <span style='color:#FF9800; font-weight:bold;'>{c_amt:,.1f} 억원</span> (어제: {c_yest_amt:,.1f}억) | "
                                    f"**{p['lookback']}일 평균:** {c_prev_amt:,.1f} 억원 (폭증률: **{c_surge:,.0f}%**) | **시총:** {c_marcap:,.0f} 억원",
                                    unsafe_allow_html=True
                                )
                            with col_btn:
                                st.button(
                                    "📊 차트 보기", 
                                    key=f"btn_surge_{c_code}", 
                                    on_click=select_scanner_stock, 
                                    args=(c_name, c_code), 
                                    use_container_width=True
                                )
                            st.markdown("---")
                else:
                    st.warning(f"기준일({scan_date})에 조건을 만족하는 종목이 없습니다.")
            else:
                st.info("💡 원하는 조건을 입력한 후 **[🔍 조건 검색 실행]** 버튼을 눌러주세요.")

        elif active_tab == "🧊 장기 초소외주 (1년 거래대금 100억 미만) 탐색기":
            st.markdown("### 🧊 장기 초소외주 / 품절주 전수 탐색기")
            st.caption("🛡️ 거래정지, 상장폐지, 관리/환기종목, 우선주, 스팩, 리츠는 자동으로 완벽 제외됩니다.")
            
            with st.container():
                st.markdown("##### ⚙️ 초소외주 탐색 조건")
                d_col1, d_col2, d_col3, d_col4, d_col5 = st.columns([1.1, 1.1, 1.0, 1.0, 1.0])
                
                with d_col1:
                    d_lookback = st.number_input("📅 추적 기간 (일수)", min_value=30, max_value=500, value=365, step=30)
                with d_col2:
                    d_max_amt = st.number_input("🚫 최대 거래대금 상한선 (억원)", min_value=1, max_value=500, value=100, step=10)
                with d_col3:
                    d_min_marcap = st.number_input("💵 최소 시가총액 (억원)", min_value=50, max_value=5000, value=300, step=50)
                with d_col4:
                    d_max_marcap = st.number_input("💎 최대 시가총액 (억원)", min_value=100, max_value=50000, value=3000, step=500)
                with d_col5:
                    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                    run_dormant_search = st.button("🧊 소외주 전수 스캔", type="primary", use_container_width=True)

            d_threshold_won = d_max_amt * 100_000_000

            if run_dormant_search:
                with st.spinner(f"최근 {d_lookback}일간 거래대금 {d_max_amt}억 미만 유지된 초소외주 분석 중..."):
                    dormant_df, d_date = scan_dormant_stocks(d_lookback, d_threshold_won, d_min_marcap, d_max_marcap)
                    st.session_state["dormant_scan_results"] = dormant_df
                    st.session_state["dormant_scan_date"] = d_date
                    st.session_state["dormant_params"] = {
                        "lookback": d_lookback,
                        "max_amt": d_max_amt,
                        "min_marcap": d_min_marcap,
                        "max_marcap": d_max_marcap
                    }

            if st.session_state["dormant_scan_results"] is not None:
                d_data = st.session_state["dormant_scan_results"]
                d_date = st.session_state["dormant_scan_date"]
                dp = st.session_state["dormant_params"]
                avg_col = f'{dp["lookback"]}일평균거래대금(억원)'
                max_col = f'{dp["lookback"]}일최대거래대금(억원)'

                st.markdown("---")
                
                dhead_col1, dhead_col2 = st.columns([4, 1.3])
                with dhead_col1:
                    if d_date:
                        st.caption(f"📅 **기준일자:** `{d_date}` | **조건:** 최근 `{dp['lookback']}일`간 일간 최대 거래대금 `{dp['max_amt']:,}억 원 미만` & 시총 `{dp['min_marcap']}억 ~ {dp['max_marcap']:,}억 원`")
                with dhead_col2:
                    if not d_data.empty:
                        if st.button("📲 소외주 전체 텔레그램 전송", key="btn_send_dormant_all", use_container_width=True):
                            total_cnt = len(d_data)
                            chunk_size = 20
                            sent_ok = True
                            
                            for start_idx in range(0, total_cnt, chunk_size):
                                end_idx = min(start_idx + chunk_size, total_cnt)
                                page_no = (start_idx // chunk_size) + 1
                                total_pages = ((total_cnt - 1) // chunk_size) + 1
                                
                                lines = [
                                    f"🧊 *[QPZM 장기 초소외주 목록]* ({page_no}/{total_pages})",
                                    f"📅 기준일: `{d_date}` | 총 {total_cnt}개 중 {start_idx+1}~{end_idx}번째",
                                    f"🎯 조건: {dp['lookback']}일간 최대 거래대금 {dp['max_amt']}억 미만\n"
                                ]
                                
                                for rank, (_, r) in enumerate(d_data.iloc[start_idx:end_idx].iterrows(), start=start_idx+1):
                                    lines.append(f"{rank}. *{r['Name']}* (`{r['Code']}`): {r['Close']:,.0f}원 | 일평균: *{r[avg_col]}억* | 시총 {r['시가총액(억원)']:,}억")
                                
                                if not send_telegram_message("\n".join(lines)):
                                    sent_ok = False
                                time.sleep(0.3)
                                
                            if sent_ok:
                                st.toast(f"텔레그램으로 전체 {total_cnt}개 소외주 목록을 전송했습니다!", icon="🚀")
                            else:
                                st.error("일부 메시지 전송 실패")

                if not d_data.empty:
                    st.success(f"최근 {dp['lookback']}일간 거래대금 {dp['max_amt']:,}억을 넘지 않은 초소외주 **{len(d_data)}개**가 발굴되었습니다!")
                    
                    st.dataframe(
                        d_data.style.format({
                            'Close': '{:,.0f}원',
                            'ChgRate': '{:+.2f}%',
                            max_col: '{:,.1f} 억' if max_col in d_data.columns else '{:,.1f}',
                            avg_col: '{:,.2f} 억' if avg_col in d_data.columns else '{:,.2f}',
                            '당일거래대금(억원)': '{:,.2f} 억',
                            '시가총액(억원)': '{:,.0f} 억'
                        }),
                        use_container_width=True
                    )
                    
                    st.markdown("---")
                    st.markdown("#### 🎯 발굴 종목 차트 확인")
                    
                    for idx, r in d_data.iterrows():
                        c_code = r['Code']
                        c_name = r['Name']
                        c_close = r['Close']
                        c_chg = r['ChgRate']
                        c_max = r[max_col] if max_col in r else 0.0
                        c_avg = r[avg_col] if avg_col in r else 0.0
                        c_marcap = r['시가총액(억원)']
                        
                        with st.container():
                            col_info, col_btn = st.columns([5, 1])
                            with col_info:
                                st.markdown(
                                    f"**{c_name}** (`{c_code}`) | **종가:** {c_close:,.0f}원 ({c_chg:+.2f}%) | "
                                    f"**{dp['lookback']}일 일평균 거래대금:** <span style='color:#29B6F6; font-weight:bold;'>{c_avg:,.2f} 억원</span> (최대: {c_max:,.1f}억) | "
                                    f"**시가총액:** {c_marcap:,.0f} 억원",
                                    unsafe_allow_html=True
                                )
                            with col_btn:
                                st.button(
                                    "📊 차트 보기", 
                                    key=f"btn_dormant_{c_code}", 
                                    on_click=select_scanner_stock, 
                                    args=(c_name, c_code), 
                                    use_container_width=True
                                )
                            st.markdown("---")
                else:
                    st.warning("조건에 해당하는 종목이 없습니다.")
            else:
                st.info("💡 조건을 설정한 뒤 **[🧊 소외주 전수 스캔]** 버튼을 눌러주세요.")

        else:
            # ==================== 🏢 5번째 탭: TrendSpider 펀더멘털 & 실적-주가 복합 차트 ====================
            st.markdown(f"### 🏢 {selected_name} - 펀더멘털 & 분기 실적(KPI) 오버레이 차트")
            st.caption(f"사이드바에서 선택하신 **주기({timeframe})**와 **조회 기간({selected_period})**이 그대로 적용되며, 과거 3~5개년 순수 분기 실적 데이터와 1:1로 결합됩니다.")

            is_korean_stock = str(selected_code).isdigit() and len(str(selected_code)) == 6
            data_source_name = "네이버 금융 & FnGuide 분기 데이터" if is_korean_stock else "Yahoo Finance 분기 데이터"
            
            with st.spinner(f"{data_source_name}에서 과거 3~5개년 순수 분기 실적 로드 중..."):
                q_fin_df = load_pure_quarterly_financials(selected_code)

            if q_fin_df.empty:
                st.warning(f"'{selected_name}' 종목의 분기 재무제표 데이터를 가져올 수 없습니다. (지수/환율/원자재/코인이거나 재무제표 미제공 종목일 수 있습니다)")
            else:
                unit_label = "억원" if is_korean_stock else "Billion USD"
                synced_price_df = display_df

                # 1. 상단 TrendSpider 스타일 메인 차트
                st.markdown(f"#### 📈 주가 & 분기 실적 스텝 오버레이 (현재 주기: `{timeframe}` | 기간: `{selected_period}` | 출처: `{data_source_name}`)")
                
                fig_ts = make_subplots(specs=[[{"secondary_y": True}]])
                
                # A. 기본 주가 라인 차트
                fig_ts.add_trace(
                    go.Scatter(
                        x=synced_price_df.index,
                        y=synced_price_df['Close'],
                        mode='lines',
                        name=f'주가 ({timeframe})',
                        line=dict(color='#29B6F6', width=2),
                        fill='tozeroy',
                        fillcolor='rgba(41, 182, 246, 0.04)'
                    ),
                    secondary_y=False
                )

                # B. 계단형 스텝 라인을 위한 분기 시작-종료 시계열 생성
                chart_min_date = synced_price_df.index.min()
                chart_max_date = synced_price_df.index.max()

                step_x = []
                step_rev = []
                step_net = []
                
                for i in range(len(q_fin_df)):
                    curr_dt = q_fin_df.index[i]
                    next_dt = q_fin_df.index[i+1] if (i+1 < len(q_fin_df)) else curr_dt + datetime.timedelta(days=90)
                    
                    if next_dt >= chart_min_date and curr_dt <= chart_max_date + datetime.timedelta(days=90):
                        r_val = q_fin_df['Revenue_Eok'].iloc[i] if 'Revenue_Eok' in q_fin_df.columns else np.nan
                        n_val = q_fin_df['NetIncome_Eok'].iloc[i] if 'NetIncome_Eok' in q_fin_df.columns else np.nan
                        
                        step_x.extend([curr_dt, next_dt])
                        step_rev.extend([r_val, r_val])
                        step_net.extend([n_val, n_val])

                if 'Revenue_Eok' in q_fin_df.columns and len(step_x) > 0:
                    fig_ts.add_trace(
                        go.Scatter(
                            x=step_x,
                            y=step_rev,
                            mode='lines',
                            name=f'분기 매출액 ({unit_label})',
                            line=dict(color='#26A69A', width=2.8),
                        ),
                        secondary_y=True
                    )

                    # TrendSpider 스타일 라벨 배지 생성
                    badge_x = []
                    badge_y = []
                    badge_texts = []
                    badge_colors = []
                    
                    for idx_dt, row_data in q_fin_df.iterrows():
                        mid_dt = idx_dt + datetime.timedelta(days=45)
                        if chart_min_date <= mid_dt <= chart_max_date + datetime.timedelta(days=90):
                            q_num = (idx_dt.month - 1) // 3 + 1
                            q_name = f"Q{q_num}'{str(idx_dt.year)[-2:]}"
                            yoy_val = row_data.get('Rev_YoY', np.nan)
                            
                            badge_x.append(mid_dt)
                            badge_y.append(row_data['Revenue_Eok'])
                            
                            if pd.notna(yoy_val):
                                sign = "+" if yoy_val > 0 else ""
                                badge_texts.append(f"<b>{q_name}</b><br>{sign}{yoy_val:.1f}%")
                                badge_colors.append('#26A69A' if yoy_val >= 0 else '#EF5350')
                            else:
                                badge_texts.append(f"<b>{q_name}</b><br>{row_data['Revenue_Eok']:,.0f}{unit_label[0]}")
                                badge_colors.append('#B2B5BE')

                    if badge_x:
                        fig_ts.add_trace(
                            go.Scatter(
                                x=badge_x,
                                y=badge_y,
                                mode='text',
                                text=badge_texts,
                                textposition="top center",
                                textfont=dict(size=10, color=badge_colors),
                                showlegend=False
                            ),
                            secondary_y=True
                        )

                if 'NetIncome_Eok' in q_fin_df.columns and len(step_x) > 0:
                    fig_ts.add_trace(
                        go.Scatter(
                            x=step_x,
                            y=step_net,
                            mode='lines',
                            name=f'분기 순이익 ({unit_label})',
                            line=dict(color='#FFB74D', width=2, dash='dot'),
                        ),
                        secondary_y=True
                    )

                fig_ts.update_layout(
                    height=580,
                    template="plotly_dark",
                    paper_bgcolor="#0E1117",
                    plot_bgcolor="#0E1117",
                    hovermode='x unified',
                    margin=dict(l=10, r=10, t=30, b=10),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                fig_ts.update_yaxes(title_text=f"주가 ({currency_symbol})", secondary_y=False, showgrid=True, gridcolor="#2A2E39")
                fig_ts.update_yaxes(title_text=f"분기 실적 규모 ({unit_label})", secondary_y=True, showgrid=False)

                st.plotly_chart(fig_ts, use_container_width=True)

                st.markdown("---")

                # 2. 하단 펀더멘털 Segments & KPIs 차트
                st.markdown("#### 📊 과거 3~5개년 분기 실적 세부 지표 & 마진율 (Segments & KPIs)")
                kpi_col1, kpi_col2 = st.columns(2)

                q_labels = [f"{d.year}-Q{(d.month-1)//3 + 1}" for d in q_fin_df.index]

                with kpi_col1:
                    fig_kpi1 = go.Figure()
                    if 'Revenue_Eok' in q_fin_df.columns:
                        fig_kpi1.add_trace(go.Bar(
                            x=q_labels,
                            y=q_fin_df['Revenue_Eok'],
                            name=f'분기 매출액 ({unit_label})',
                            marker_color='#29B6F6'
                        ))
                    if 'OperatingIncome_Eok' in q_fin_df.columns:
                        fig_kpi1.add_trace(go.Bar(
                            x=q_labels,
                            y=q_fin_df['OperatingIncome_Eok'],
                            name=f'분기 영업이익 ({unit_label})',
                            marker_color='#26A69A'
                        ))
                    if 'NetIncome_Eok' in q_fin_df.columns:
                        fig_kpi1.add_trace(go.Bar(
                            x=q_labels,
                            y=q_fin_df['NetIncome_Eok'],
                            name=f'분기 순이익 ({unit_label})',
                            marker_color='#FFB74D'
                        ))
                    fig_kpi1.update_layout(
                        title=f"분기별 매출액, 영업이익, 순이익 추이 ({unit_label})",
                        height=360,
                        barmode='group',
                        template="plotly_dark",
                        paper_bgcolor="#0E1117",
                        plot_bgcolor="#0E1117",
                        margin=dict(l=10, r=10, t=40, b=10),
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                    )
                    st.plotly_chart(fig_kpi1, use_container_width=True)

                with kpi_col2:
                    fig_kpi2 = make_subplots(specs=[[{"secondary_y": True}]])
                    if 'Net_Margin' in q_fin_df.columns:
                        fig_kpi2.add_trace(
                            go.Scatter(
                                x=q_labels,
                                y=q_fin_df['Net_Margin'],
                                mode='lines+markers',
                                name='순이익률 (Net Margin %)',
                                line=dict(color='#AB47BC', width=2.5),
                                marker=dict(size=6)
                            ),
                            secondary_y=False
                        )
                    if 'Rev_YoY' in q_fin_df.columns:
                        yoy_bar_colors = ['#26A69A' if v >= 0 else '#EF5350' for v in q_fin_df['Rev_YoY'].fillna(0)]
                        fig_kpi2.add_trace(
                            go.Bar(
                                x=q_labels,
                                y=q_fin_df['Rev_YoY'],
                                name='매출 YoY 성장률 (%)',
                                marker_color=yoy_bar_colors,
                                opacity=0.4
                            ),
                            secondary_y=True
                        )
                    fig_kpi2.update_layout(
                        title="순이익률 (%) 및 매출 YoY 성장률 (%)",
                        height=360,
                        template="plotly_dark",
                        paper_bgcolor="#0E1117",
                        plot_bgcolor="#0E1117",
                        margin=dict(l=10, r=10, t=40, b=10),
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                    )
                    fig_kpi2.update_yaxes(title_text="순이익률 (%)", secondary_y=False)
                    fig_kpi2.update_yaxes(title_text="매출 YoY (%)", secondary_y=True)
                    st.plotly_chart(fig_kpi2, use_container_width=True)

                # 3. 실적 원본 데이터 테이블
                with st.expander("📋 과거 3~5개년 순수 분기 실적 원본 데이터 테이블 확인"):
                    disp_table = q_fin_df.copy()
                    disp_table.index = [d.strftime('%Y-%m-%d') for d in disp_table.index]
                    
                    rename_dict = {
                        'Revenue_Eok': f'매출액 ({unit_label})',
                        'OperatingIncome_Eok': f'영업이익 ({unit_label})',
                        'NetIncome_Eok': f'당기순이익 ({unit_label})',
                        'Net_Margin': '순이익률 (%)',
                        'Rev_YoY': '매출 YoY 성장률 (%)'
                    }
                    disp_table.rename(columns=rename_dict, inplace=True)
                    
                    show_cols = [c for c in rename_dict.values() if c in disp_table.columns]
                    st.dataframe(
                        disp_table[show_cols].style.format({
                            f'매출액 ({unit_label})': '{:,.1f}',
                            f'영업이익 ({unit_label})': '{:,.1f}',
                            f'당기순이익 ({unit_label})': '{:,.1f}',
                            '순이익률 (%)': '{:.1f}%',
                            '매출 YoY 성장률 (%)': '{:+.1f}%'
                        }),
                        use_container_width=True
                    )

except Exception as e:
    st.error(f"데이터 조회 중 예기치 않은 오류가 발생했습니다: {e}")
