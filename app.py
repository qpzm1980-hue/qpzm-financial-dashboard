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
import zipfile
import io
import xml.etree.ElementTree as ET
from io import StringIO
from concurrent.futures import ThreadPoolExecutor

# 페이지 설정
st.set_page_config(page_title="글로벌 종합 금융 프로 터미널", layout="wide", initial_sidebar_state="expanded")

# ==================== 0. 정크 종목 필터 ====================
def is_valid_normal_stock(name: str, code: str, curr_volume: float, curr_amount: float) -> bool:
    if curr_volume <= 0 or curr_amount <= 0: return False
    if not (str(code).isdigit() and len(str(code)) == 6): return False
    name_clean = str(name).strip()
    if any(k in name_clean for k in ["스팩", "기업인수목적", "리츠", "REIT", "인프라", "투융자"]): return False
    if re.search(r'(우|우B|우C|우\(전환\))$', name_clean): return False
    if any(k in name_clean for k in ["(관리)", "(정매)", "(환기)", "정리매매"]): return False
    return True

# ==================== 텔레그램 발송 ====================
def send_telegram_message(message: str) -> bool:
    bot_token = st.secrets.get("TELEGRAM_BOT_TOKEN", None)
    chat_id = st.secrets.get("TELEGRAM_CHAT_ID", None)
    if not bot_token or not chat_id: return False
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {"chat_id": str(chat_id).strip(), "text": message, "parse_mode": "Markdown"}
        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status == 200
    except Exception: return False

# ==================== 세션 상태 초기화 ====================
if "category_radio" not in st.session_state: st.session_state["category_radio"] = "해외주식 (US Custom)"
if "custom_stock_name" not in st.session_state: st.session_state["custom_stock_name"] = None
if "custom_stock_code" not in st.session_state: st.session_state["custom_stock_code"] = None
if "tab_selector" not in st.session_state: st.session_state["tab_selector"] = "🏢 펀더멘털 & 실적-주가 복합 차트 (TrendSpider)"
if "scan_results_df" not in st.session_state: st.session_state["scan_results_df"] = None
if "scan_results_date" not in st.session_state: st.session_state["scan_results_date"] = None
if "last_scanned_params" not in st.session_state: st.session_state["last_scanned_params"] = None
if "dormant_scan_results" not in st.session_state: st.session_state["dormant_scan_results"] = None
if "dormant_scan_date" not in st.session_state: st.session_state["dormant_scan_date"] = None
if "dormant_params" not in st.session_state: st.session_state["dormant_params"] = None

def select_scanner_stock(name, code):
    st.session_state["category_radio"] = "국내주식 (KRX)"
    st.session_state["custom_stock_name"] = name
    st.session_state["custom_stock_code"] = code
    st.session_state["tab_selector"] = "📊 인터랙티브 종합 차트"

# ==================== 1. 비공개 인증 ====================
def check_password():
    if st.session_state.get("authenticated", False): return True
    app_pwd = st.secrets.get("APP_PASSWORD", None)
    if not app_pwd: return True
    st.markdown("<h2 style='text-align: center;'>🔒 프라이빗 금융 대시보드</h2>", unsafe_allow_html=True)
    _, col, _ = st.columns([1, 2, 1])
    with col:
        user_input = st.text_input("접속 비밀번호", type="password")
        if st.button("대시보드 접속", use_container_width=True):
            if str(user_input).strip() == str(app_pwd).strip():
                st.session_state["authenticated"] = True
                st.rerun()
            else: st.error("❌ 비밀번호 불일치")
    return False

if not check_password(): st.stop()

# ==================== 2. UI 스타일링 ====================
st.markdown("""
<style>
    .signal-badge-bull { background-color: rgba(38, 166, 154, 0.2); color: #26A69A; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 0.85rem; }
    .signal-badge-bear { background-color: rgba(239, 83, 80, 0.2); color: #EF5350; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 0.85rem; }
    .signal-badge-neutral { background-color: rgba(255, 255, 255, 0.1); color: #B2B5BE; padding: 4px 8px; border-radius: 4px; font-size: 0.85rem; }
</style>
""", unsafe_allow_html=True)

st.title("📈 글로벌 종합 금융 인텔리전스 대시보드")

@st.cache_data(ttl=3600)
def get_krx_stocks():
    try:
        df = fdr.StockListing('KRX')
        df = df.sort_values(by='Marcap', ascending=False).head(150)
        return dict(zip(df['Name'], df['Code']))
    except Exception: return {"삼성전자": "005930", "SK하이닉스": "000660", "LG에너지솔루션": "373220", "현대차": "005380"}

def get_us_stocks():
    return {
        "META - Meta Platforms": "META", "TSLA - Tesla": "TSLA", "AAPL - Apple": "AAPL",
        "GOOGL - Alphabet (Google)": "GOOGL", "AMZN - Amazon": "AMZN", "NVDA - NVIDIA": "NVDA",
        "MSFT - Microsoft": "MSFT", "PLTR - Palantir Technologies": "PLTR", "AMD - Advanced Micro Devices": "AMD",
        "NFLX - Netflix": "NFLX", "INTC - Intel": "INTC", "CPNG - Coupang": "CPNG", "LLY - Eli Lilly": "LLY"
    }

# 사이드바
st.sidebar.header("🕹️ 컨트롤 패널")
input_mode = st.sidebar.radio("🔍 종목 선택 방식", ["목록에서 선택", "티커 직접 입력"], index=0)

if input_mode == "목록에서 선택":
    category = st.sidebar.radio("🌐 자산 카테고리", ["해외주식 (US Custom)", "국내주식 (KRX)", "채권 (Bonds)", "원자재 (Commodity)", "환율 (Forex)", "암호화폐 (Crypto)"], key="category_radio")
    if category == "해외주식 (US Custom)": STOCKS, currency_symbol = get_us_stocks(), "USD"
    elif category == "국내주식 (KRX)":
        STOCKS = get_krx_stocks()
        if st.session_state["custom_stock_name"] and st.session_state["custom_stock_code"]:
            STOCKS = {st.session_state["custom_stock_name"]: st.session_state["custom_stock_code"], **STOCKS}
        currency_symbol = "원"
    elif category == "채권 (Bonds)": STOCKS, currency_symbol = {"TLT": "TLT", "^TNX": "^TNX"}, "USD"
    elif category == "원자재 (Commodity)": STOCKS, currency_symbol = {"Gold": "GC=F", "WTI": "CL=F"}, "USD"
    elif category == "환율 (Forex)": STOCKS, currency_symbol = {"USD/KRW": "USD/KRW", "JPY/KRW": "JPY/KRW"}, "원"
    else: STOCKS, currency_symbol = {"BTC/USD": "BTC/USD", "ETH/USD": "ETH/USD"}, "USD"

    options_list = list(STOCKS.keys())
    default_target = st.session_state.get("custom_stock_name")
    selected_idx = options_list.index(default_target) if (default_target and default_target in options_list) else 0
    selected_name = st.sidebar.selectbox("🔎 종목/자산 선택", options=options_list, index=selected_idx)
    selected_code = STOCKS[selected_name]
else:
    direct_ticker = st.sidebar.text_input("📝 티커 직접 입력 (예: META, AAPL, 005930, 284740)", value="META").strip()
    selected_name = f"Custom: {direct_ticker}"
    selected_code = direct_ticker
    currency_symbol = "원" if (direct_ticker.isdigit() or "KRW" in direct_ticker) else "USD"

tf_config = {
    "5분봉": {"default": "1일", "options": ["1일", "3일", "5일", "1개월", "2개월"], "interval": "5m"},
    "30분봉": {"default": "5일", "options": ["5일", "1개월", "2개월"], "interval": "30m"},
    "1시간봉": {"default": "1개월", "options": ["5일", "1개월", "2개월", "6개월"], "interval": "60m"},
    "일봉": {"default": "1년", "options": ["1달", "6개월", "1년", "3년", "5년", "10년", "최대(All)"], "interval": "1d"},
    "주봉": {"default": "3년", "options": ["6개월", "1년", "3년", "5년", "10년", "최대(All)"], "interval": "1wk"},
    "월봉": {"default": "최대(All)", "options": ["1년", "3년", "5년", "10년", "최대(All)"], "interval": "1mo"}
}

st.sidebar.markdown("---")
st.sidebar.subheader("⏱️ 차트 주기 & 기간")
timeframe = st.sidebar.radio("📊 차트 주기", list(tf_config.keys()), index=5)
current_cfg = tf_config[timeframe]
selected_period = st.sidebar.select_slider("📅 조회 기간", options=current_cfg["options"], value=current_cfg["default"])

st.sidebar.markdown("---")
st.sidebar.subheader("📐 보조지표 표시")
show_ma = st.sidebar.checkbox("이동평균선 (20/50/100/200)", value=True)
show_bb = st.sidebar.checkbox("볼린저 밴드 (20, 2)", value=False)
show_rsi = st.sidebar.checkbox("RSI (14)", value=True)
show_macd = st.sidebar.checkbox("MACD (12, 26, 9)", value=True)

if "DART_API_KEY" in st.secrets:
    st.sidebar.success("🏛️ DART & SEC EDGAR 10년 연동")

if st.sidebar.button("🔄 최신 시세 강제 갱신"):
    st.cache_data.clear()
    st.rerun()

# ==================== 데이터 계산 ====================
period_map_yf = {"1일": "1d", "3일": "3d", "5일": "5d", "1달": "1mo", "1개월": "1mo", "2개월": "2mo", "6개월": "6mo", "1년": "1y", "3년": "3y", "5년": "5y", "10년": "10y", "최대(All)": "max"}

@st.cache_data(ttl=60)
def load_and_calculate_data(code, tf, period_str):
    interval = tf_config[tf]["interval"]
    yf_period = period_map_yf.get(period_str, "max")

    if "m" in interval:
        df = pd.DataFrame()
        if code.isdigit() and len(code) == 6:
            for suffix in [".KS", ".KQ"]:
                try:
                    df = yf.Ticker(f"{code}{suffix}").history(period=yf_period, interval=interval)
                    if not df.empty: break
                except Exception: continue
        elif "/" in code:
            c_base, c_quote = code.split("/")
            yf_code = f"{c_base}{c_quote}=X" if c_quote in ["KRW", "USD", "JPY", "EUR"] else code.replace("/", "-")
            try: df = yf.Ticker(yf_code).history(period=yf_period, interval=interval)
            except Exception: df = pd.DataFrame()
        else:
            try: df = yf.Ticker(code).history(period=yf_period, interval=interval)
            except Exception: df = pd.DataFrame()
        if df.empty: return df
        if df.index.tz is not None: df.index = df.index.tz_localize(None)
    else:
        today = datetime.date.today()
        if period_str == "최대(All)":
            start_d = "1990-01-01"
        else:
            days_calc = {"1달": 30, "6개월": 180, "1년": 365, "3년": 365*3, "5년": 365*5, "10년": 365*10}
            start_d = today - datetime.timedelta(days=days_calc.get(period_str, 365*10) + 400)
            
        try: df = fdr.DataReader(code, start_d)
        except Exception: df = pd.DataFrame()
        if df.empty: return df
        if tf == "주봉": df = df.resample('W-FRI').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last', 'Volume':'sum'}).dropna()
        elif tf == "월봉": df = df.resample('ME').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last', 'Volume':'sum'}).dropna()

    if 'Volume' not in df.columns: df['Volume'] = 0
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
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))
    exp12 = df['Close'].ewm(span=12, adjust=False).mean()
    exp26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp12 - exp26
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']

    if "m" not in interval and period_str != "최대(All)":
        days_disp = days_calc.get(period_str, 365*10)
        disp_start = today - datetime.timedelta(days=days_disp)
        df = df.loc[df.index >= pd.to_datetime(disp_start)]
    return df

# ==================== 🏛️ 국내(DART) & 해외(SEC EDGAR) 10+년 분기 실적 로더 ====================
@st.cache_data(ttl=86400)
def get_dart_corp_code_map(dart_key):
    try:
        url = f"https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key={dart_key}"
        resp = requests.get(url, timeout=12)
        if resp.status_code == 200:
            with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
                xml_data = z.read('CORPCODE.xml')
                tree = ET.fromstring(xml_data)
                code_map = {}
                for item in tree.findall('list'):
                    c_code = item.findtext('corp_code')
                    s_code = item.findtext('stock_code')
                    if s_code and len(s_code.strip()) == 6:
                        code_map[s_code.strip()] = c_code.strip()
                return code_map
    except Exception: pass
    return {}

def fetch_single_dart_report(args):
    dart_key, corp_code, y, r_code, end_day, q_num = args
    try:
        url = f"https://opendart.fss.or.kr/api/fnlttSinglAcnt.json?crtfc_key={dart_key}&corp_code={corp_code}&bsns_year={y}&reprt_code={r_code}"
        resp = requests.get(url, timeout=5).json()
        if resp.get("status") == "000" and "list" in resp:
            items = resp["list"]
            items_cfs = [it for it in items if it.get("fs_div") == "CFS"]
            target_items = items_cfs if items_cfs else items
            
            rev, op, net = np.nan, np.nan, np.nan
            for it in target_items:
                if it.get("sj_div") in ["IS", "CIS"]:
                    acc = it.get("account_nm", "").replace(" ", "")
                    val_str = it.get("thstrm_amount", "0").replace(",", "")
                    val_num = pd.to_numeric(val_str, errors='coerce')
                    if ("매출액" in acc or "수익(매출액)" in acc) and pd.isna(rev): rev = val_num
                    elif "영업이익" in acc and pd.isna(op): op = val_num
                    elif ("당기순이익" in acc or "순이익" in acc) and pd.isna(net): net = val_num

            if pd.notna(rev) or pd.notna(net):
                dt_key = pd.to_datetime(f"{y}-{end_day}")
                return (dt_key, {
                    'Revenue_Eok': rev / 100_000_000,
                    'OperatingIncome_Eok': op / 100_000_000,
                    'NetIncome_Eok': net / 100_000_000,
                    'q_num': q_num,
                    'year': y
                })
    except Exception: pass
    return None

@st.cache_data(ttl=86400)
def get_sec_cik_map():
    """미국 SEC EDGAR 티커 -> CIK 매핑 로더"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'}
        r = requests.get('https://www.sec.gov/files/company_tickers.json', headers=headers, timeout=5)
        if r.status_code == 200:
            data = r.json()
            return {v['ticker'].upper(): str(v['cik_str']) for v in data.values()}
    except Exception: pass
    # 주요 빅테크 기본 매핑
    return {
        "META": "1326801", "AAPL": "320193", "NVDA": "1045810", "TSLA": "1318605",
        "MSFT": "789019", "AMZN": "1018724", "GOOGL": "1652044", "GOOG": "1652044",
        "PLTR": "1321655", "AMD": "2488", "NFLX": "1065280", "INTC": "50863", "CPNG": "1834584", "LLY": "59478"
    }

@st.cache_data(ttl=7200)
def load_sec_edgar_10y_financials(ticker_symbol):
    """SEC EDGAR 공식 XBRL에서 미국 주식의 과거 10년+ 분기 실적(매출/영업이익/순이익) 전수 추출"""
    t_clean = ticker_symbol.upper().strip()
    cik_map = get_sec_cik_map()
    cik = cik_map.get(t_clean)
    
    if cik:
        try:
            url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik.zfill(10)}.json"
            headers = {'User-Agent': 'PersonalDashboardAdmin/2.0 (contact@investortool.com)'}
            resp = requests.get(url, headers=headers, timeout=8)
            
            if resp.status_code == 200:
                cf = resp.json().get('facts', {}).get('us-gaap', {})
                
                # 1. 매출액 태그 탐색
                rev_tags = ['RevenueFromContractWithCustomerExcludingAssessedTax', 'SalesRevenueNet', 'Revenues', 'TotalRevenuesAndOtherIncome']
                rev_data = None
                for tag in rev_tags:
                    if tag in cf and 'USD' in cf[tag].get('units', {}):
                        rev_data = cf[tag]['units']['USD']
                        break
                        
                # 2. 순이익 태그
                net_tags = ['NetIncomeLoss', 'ProfitLoss', 'NetIncomeLossAvailableToCommonStockholdersBasic']
                net_data = None
                for tag in net_tags:
                    if tag in cf and 'USD' in cf[tag].get('units', {}):
                        net_data = cf[tag]['units']['USD']
                        break
                        
                # 3. 영업이익 태그
                op_tags = ['OperatingIncomeLoss']
                op_data = None
                for tag in op_tags:
                    if tag in cf and 'USD' in cf[tag].get('units', {}):
                        op_data = cf[tag]['units']['USD']
                        break
                        
                q_dict = {}
                
                # 분기별 10-Q 및 10-K 파싱
                def parse_series(data_list, val_key):
                    if not data_list: return
                    for item in data_list:
                        form = item.get('form', '')
                        fp = item.get('fp', '')
                        end_dt = item.get('end', '')
                        val = item.get('val', np.nan)
                        
                        # 분기 보고서(10-Q) 또는 10-K
                        if form in ['10-Q', '10-K'] and end_dt:
                            # 3개월 분기 실적 (또는 frame이 분기인 경우)
                            start_dt = item.get('start', '')
                            # 시작일과 종료일 차이가 60~110일 사이인 경우 = 3개월 분기 실적
                            is_pure_quarter = False
                            if start_dt and end_dt:
                                try:
                                    d_diff = (pd.to_datetime(end_dt) - pd.to_datetime(start_dt)).days
                                    if 60 <= d_diff <= 110: is_pure_quarter = True
                                except Exception: pass
                            elif fp in ['Q1', 'Q2', 'Q3', 'Q4']:
                                is_pure_quarter = True
                                
                            if is_pure_quarter and pd.notna(val):
                                dt_idx = pd.to_datetime(end_dt)
                                if dt_idx not in q_dict: q_dict[dt_idx] = {}
                                q_dict[dt_idx][val_key] = val / 1_000_000_000 # Billion USD

                parse_series(rev_data, 'Revenue_Eok')
                parse_series(net_data, 'NetIncome_Eok')
                parse_series(op_data, 'OperatingIncome_Eok')
                
                if q_dict:
                    df_sec = pd.DataFrame.from_dict(q_dict, orient='index').sort_index()
                    # 4분기 이상이면 YoY 및 마진율 계산
                    if 'Revenue_Eok' in df_sec.columns:
                        df_sec['Rev_YoY'] = df_sec['Revenue_Eok'].pct_change(4) * 100
                        df_sec['Rev_YoY'] = df_sec['Rev_YoY'].fillna(df_sec['Revenue_Eok'].pct_change(1) * 100)
                    if 'NetIncome_Eok' in df_sec.columns:
                        df_sec['Net_YoY'] = df_sec['NetIncome_Eok'].pct_change(4) * 100
                        df_sec['Net_YoY'] = df_sec['NetIncome_Eok'].fillna(df_sec['NetIncome_Eok'].pct_change(1) * 100)
                    if 'Revenue_Eok' in df_sec.columns and 'NetIncome_Eok' in df_sec.columns:
                        df_sec['Net_Margin'] = (df_sec['NetIncome_Eok'] / df_sec['Revenue_Eok']) * 100
                    return df_sec.dropna(how='all')
        except Exception: pass

    # 야후 파이낸스 폴백
    try:
        q_fin = yf.Ticker(ticker_symbol).quarterly_financials
        if q_fin is not None and not q_fin.empty:
            q_df = q_fin.T.sort_index()
            q_df.index = pd.to_datetime(q_df.index)
            res = pd.DataFrame(index=q_df.index)
            for c in ['Total Revenue', 'Operating Revenue', 'Revenue']:
                if c in q_df.columns: res['Revenue_Eok'] = q_df[c] / 1_000_000_000; break
            for c in ['Net Income', 'Net Income Common Stockholders']:
                if c in q_df.columns: res['NetIncome_Eok'] = q_df[c] / 1_000_000_000; break
            for c in ['Operating Income', 'Operating Revenue']:
                if c in q_df.columns: res['OperatingIncome_Eok'] = q_df[c] / 1_000_000_000; break
            if 'Revenue_Eok' in res.columns: res['Rev_YoY'] = res['Revenue_Eok'].pct_change(4) * 100
            if 'NetIncome_Eok' in res.columns: res['Net_YoY'] = res['NetIncome_Eok'].pct_change(4) * 100
            if 'Revenue_Eok' in res.columns and 'NetIncome_Eok' in res.columns:
                res['Net_Margin'] = (res['NetIncome_Eok'] / res['Revenue_Eok']) * 100
            return res.dropna(how='all')
    except Exception: pass
    return pd.DataFrame()

@st.cache_data(ttl=7200)
def load_global_full_history_financials(code):
    """국내(DART 2015~현재) 및 해외(SEC EDGAR 10+개년) 전수 실적 통합 분기 로더"""
    is_korean = str(code).isdigit() and len(str(code)) == 6
    if is_korean:
        dart_key = st.secrets.get("DART_API_KEY", "").strip()
        res_dict = {}
        if dart_key:
            corp_map = get_dart_corp_code_map(dart_key)
            corp_code = corp_map.get(str(code).zfill(6))
            if corp_code:
                curr_year = datetime.date.today().year
                years = list(range(2015, curr_year + 1))
                reports = [("11013", "03-31", 1), ("11012", "06-30", 2), ("11014", "09-30", 3), ("11011", "12-31", 4)]
                task_list = [(dart_key, corp_code, y, r_code, end_day, q_num) for y in years for r_code, end_day, q_num in reports]
                with ThreadPoolExecutor(max_workers=10) as executor:
                    results = executor.map(fetch_single_dart_report, task_list)
                for res in results:
                    if res is not None: res_dict[res[0]] = res[1]

        if res_dict:
            raw_df = pd.DataFrame.from_dict(res_dict, orient='index').sort_index()
            pure_dict = {}
            for y_val in raw_df['year'].unique():
                y_df = raw_df[raw_df['year'] == y_val].sort_values(by='q_num')
                q1_row, q2_row, q3_row, q4_row = y_df[y_df['q_num']==1], y_df[y_df['q_num']==2], y_df[y_df['q_num']==3], y_df[y_df['q_num']==4]
                if not q1_row.empty: pure_dict[q1_row.index[0]] = {'Revenue_Eok': q1_row['Revenue_Eok'].iloc[0], 'OperatingIncome_Eok': q1_row['OperatingIncome_Eok'].iloc[0], 'NetIncome_Eok': q1_row['NetIncome_Eok'].iloc[0]}
                if not q2_row.empty:
                    q1_r = q1_row['Revenue_Eok'].iloc[0] if not q1_row.empty else 0
                    pure_dict[q2_row.index[0]] = {'Revenue_Eok': max(0.0, q2_row['Revenue_Eok'].iloc[0]-q1_r) if q2_row['Revenue_Eok'].iloc[0]>q1_r else q2_row['Revenue_Eok'].iloc[0], 'OperatingIncome_Eok': q2_row['OperatingIncome_Eok'].iloc[0]-(q1_row['OperatingIncome_Eok'].iloc[0] if not q1_row.empty else 0), 'NetIncome_Eok': q2_row['NetIncome_Eok'].iloc[0]-(q1_row['NetIncome_Eok'].iloc[0] if not q1_row.empty else 0)}
                if not q3_row.empty:
                    q2_cum_r = q2_row['Revenue_Eok'].iloc[0] if not q2_row.empty else 0
                    pure_dict[q3_row.index[0]] = {'Revenue_Eok': max(0.0, q3_row['Revenue_Eok'].iloc[0]-q2_cum_r) if q3_row['Revenue_Eok'].iloc[0]>q2_cum_r else q3_row['Revenue_Eok'].iloc[0], 'OperatingIncome_Eok': q3_row['OperatingIncome_Eok'].iloc[0]-(q2_row['OperatingIncome_Eok'].iloc[0] if not q2_row.empty else 0), 'NetIncome_Eok': q3_row['NetIncome_Eok'].iloc[0]-(q2_row['NetIncome_Eok'].iloc[0] if not q2_row.empty else 0)}
                if not q4_row.empty:
                    q3_cum_r = q3_row['Revenue_Eok'].iloc[0] if not q3_row.empty else (q2_row['Revenue_Eok'].iloc[0] if not q2_row.empty else 0)
                    pure_r = q4_row['Revenue_Eok'].iloc[0] - q3_cum_r if (q4_row['Revenue_Eok'].iloc[0] > q3_cum_r and q3_cum_r > 0) else q4_row['Revenue_Eok'].iloc[0] / 4
                    pure_dict[q4_row.index[0]] = {'Revenue_Eok': max(0.0, pure_r), 'OperatingIncome_Eok': q4_row['OperatingIncome_Eok'].iloc[0]-(q3_row['OperatingIncome_Eok'].iloc[0] if not q3_row.empty else 0), 'NetIncome_Eok': q4_row['NetIncome_Eok'].iloc[0]-(q3_row['NetIncome_Eok'].iloc[0] if not q3_row.empty else 0)}

            final_df = pd.DataFrame.from_dict(pure_dict, orient='index').sort_index()
            if 'Revenue_Eok' in final_df.columns:
                final_df['Rev_YoY'] = final_df['Revenue_Eok'].pct_change(4) * 100
                final_df['Rev_YoY'] = final_df['Rev_YoY'].fillna(final_df['Revenue_Eok'].pct_change(1) * 100)
            if 'NetIncome_Eok' in final_df.columns:
                final_df['Net_YoY'] = final_df['NetIncome_Eok'].pct_change(4) * 100
                final_df['Net_YoY'] = final_df['NetIncome_Eok'].fillna(final_df['NetIncome_Eok'].pct_change(1) * 100)
            if 'Revenue_Eok' in final_df.columns and 'NetIncome_Eok' in final_df.columns:
                final_df['Net_Margin'] = (final_df['NetIncome_Eok'] / final_df['Revenue_Eok']) * 100
            return final_df.dropna(how='all')
    else:
        # 해외 주식 (미국 주식) -> SEC EDGAR 10+년 호출
        return load_sec_edgar_10y_financials(code)

    return pd.DataFrame()

# ==================== 본문 렌더링 ====================
try:
    display_df = load_and_calculate_data(selected_code, timeframe, selected_period)
    
    if display_df is None or display_df.empty:
        st.error(f"티커 '{selected_code}'의 데이터를 가져올 수 없습니다.")
    else:
        latest_close = float(display_df['Close'].iloc[-1])
        prev_close = float(display_df['Close'].iloc[-2]) if len(display_df) > 1 else latest_close
        price_chg = latest_close - prev_close
        price_chg_pct = (price_chg / prev_close) * 100 if prev_close != 0 else 0

        formatted_close = f"{latest_close:,.2f}" if currency_symbol == "USD" else f"{int(latest_close):,}"
        delta_str = f"{price_chg:+,.2f} ({price_chg_pct:+.2f}%)" if currency_symbol == "USD" else f"{int(price_chg):+,} ({price_chg_pct:+.2f}%)"

        st.markdown("### 📌 시장 핵심 요약")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("선택 종목/자산", selected_name.split(' - ')[0].split(' (')[0])
        m2.metric("현재 시세", f"{formatted_close} {currency_symbol}", delta=delta_str)

        high_val, low_val = display_df['High'].max(), display_df['Low'].min()
        drop_from_high = ((latest_close - high_val) / high_val) * 100
        cummax = display_df['Close'].cummax()
        mdd = ((display_df['Close'] - cummax) / cummax).min() * 100

        m3.metric("기간 최고 / 최저", f"{int(high_val):,} / {int(low_val):,}" if currency_symbol=="원" else f"{high_val:,.2f} / {low_val:,.2f}", f"고점대비 {drop_from_high:+.1f}%")
        m4.metric("기간 내 MDD (최대 낙폭)", f"{mdd:.2f}%", delta_color="inverse")

        st.markdown("---")
        tab_titles = ["📊 인터랙티브 종합 차트", "📈 벤치마크 상대 수익률(%) 비교", "🏢 펀더멘털 & 실적-주가 복합 차트 (TrendSpider)"]
        active_tab = st.radio("탭 선택", tab_titles, horizontal=True, label_visibility="collapsed", key="tab_selector")

        if active_tab == "📊 인터랙티브 종합 차트":
            x_data = display_df.index.strftime('%Y-%m-%d %H:%M') if "m" in tf_config[timeframe]["interval"] else display_df.index
            fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.6, 0.2, 0.2], subplot_titles=["가격 및 이평선", "거래량", "MACD"])
            fig.add_trace(go.Candlestick(x=x_data, open=display_df['Open'], high=display_df['High'], low=display_df['Low'], close=display_df['Close'], name='시세', increasing_line_color='#26A69A', decreasing_line_color='#EF5350'), row=1, col=1)
            if show_ma:
                for ma_name, color in {'20선': '#FF9800', '50선': '#AB47BC', '100선': '#29B6F6', '200선': '#B0BEC5'}.items():
                    if ma_name in display_df.columns: fig.add_trace(go.Scatter(x=x_data, y=display_df[ma_name], mode='lines', name=ma_name, line=dict(color=color, width=1.2)), row=1, col=1)
            vol_colors = ['#26A69A' if r['Close'] >= r['Open'] else '#EF5350' for _, r in display_df.iterrows()]
            fig.add_trace(go.Bar(x=x_data, y=display_df['Volume'], name='거래량', marker_color=vol_colors), row=2, col=1)
            fig.add_trace(go.Scatter(x=x_data, y=display_df['MACD'], mode='lines', name='MACD', line=dict(color='#29B6F6', width=1.3)), row=3, col=1)
            fig.add_trace(go.Scatter(x=x_data, y=display_df['MACD_Signal'], mode='lines', name='Signal', line=dict(color='#FF7043', width=1.3)), row=3, col=1)
            fig.update_layout(height=720, template="plotly_dark", paper_bgcolor="#0E1117", plot_bgcolor="#0E1117", xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=30, b=10), hovermode='x unified')
            st.plotly_chart(fig, use_container_width=True)

        elif active_tab == "📈 벤치마크 상대 수익률(%) 비교":
            comp_targets = {"S&P 500 지수": "US500", "나스닥 100 지수": "IXIC", "KOSPI 지수": "KS11", "Gold": "GC=F", "비트코인": "BTC/USD"}
            sel_comp = st.selectbox("비교 대상 선택", list(comp_targets.keys()))
            comp_df = fdr.DataReader(comp_targets[sel_comp], display_df.index[0])
            if not comp_df.empty:
                b_main = display_df['Close'] / display_df['Close'].iloc[0] * 100 - 100
                b_comp = comp_df['Close'] / comp_df['Close'].iloc[0] * 100 - 100
                c_fig = go.Figure()
                c_fig.add_trace(go.Scatter(x=b_main.index, y=b_main, mode='lines', name=f"기준 종목", line=dict(color='#29B6F6', width=2)))
                c_fig.add_trace(go.Scatter(x=b_comp.index, y=b_comp, mode='lines', name=sel_comp, line=dict(color='#FFB74D', width=2, dash='dot')))
                c_fig.update_layout(height=480, template="plotly_dark", paper_bgcolor="#0E1117", plot_bgcolor="#0E1117", yaxis_title="수익률(%)", hovermode='x unified')
                st.plotly_chart(c_fig, use_container_width=True)

        else:
            # ==================== 🏢 5번째 탭: TrendSpider 펀더멘털 & 10+개년 분기 실적 복합 차트 ====================
            is_korean = str(selected_code).isdigit() and len(str(selected_code)) == 6
            source_lbl = "금융감독원 Open DART 전자공시" if is_korean else "미국 증권거래위원회 SEC EDGAR 공식 XBRL"
            unit_label = "억원" if is_korean else "Billion USD"

            st.markdown(f"### 🏢 {selected_name} - 펀더멘털 & 전 기간(10+년) 분기 실적(KPI) 오버레이 차트")
            st.caption(f"사이드바 주기: **`{timeframe}`** | 기간: **`{selected_period}`** | 출처: **`{source_lbl}`** (10+개년 100% 순수 분기 실적)")

            with st.spinner(f"{source_lbl}에서 10+년 치 분기 실적 전수 수집 및 4분기 순수 실적 보정 중..."):
                q_fin_df = load_global_full_history_financials(selected_code)

            if q_fin_df.empty:
                st.warning(f"'{selected_name}'의 분기 실적 데이터를 가져올 수 없습니다. 종목 티커를 확인하세요.")
            else:
                synced_price_df = display_df

                st.markdown(f"#### 📈 주가 & 10+년 분기 실적 스텝 오버레이 (출처: `{source_lbl}`)")
                fig_ts = make_subplots(specs=[[{"secondary_y": True}]])
                fig_ts.add_trace(go.Scatter(x=synced_price_df.index, y=synced_price_df['Close'], mode='lines', name=f'주가 ({timeframe})', line=dict(color='#29B6F6', width=2), fill='tozeroy', fillcolor='rgba(41, 182, 246, 0.04)'), secondary_y=False)

                c_min, c_max = synced_price_df.index.min(), synced_price_df.index.max()
                step_x, step_rev, step_net = [], [], []

                for i in range(len(q_fin_df)):
                    curr_dt = q_fin_df.index[i]
                    next_dt = q_fin_df.index[i+1] if (i+1 < len(q_fin_df)) else curr_dt + datetime.timedelta(days=90)
                    if next_dt >= c_min and curr_dt <= c_max + datetime.timedelta(days=90):
                        r_val = q_fin_df['Revenue_Eok'].iloc[i] if 'Revenue_Eok' in q_fin_df.columns else np.nan
                        n_val = q_fin_df['NetIncome_Eok'].iloc[i] if 'NetIncome_Eok' in q_fin_df.columns else np.nan
                        step_x.extend([curr_dt, next_dt])
                        step_rev.extend([r_val, r_val])
                        step_net.extend([n_val, n_val])

                if 'Revenue_Eok' in q_fin_df.columns and len(step_x) > 0:
                    fig_ts.add_trace(go.Scatter(x=step_x, y=step_rev, mode='lines', name=f'분기 매출액 ({unit_label})', line=dict(color='#26A69A', width=2.8)), secondary_y=True)
                    
                    # 배지 라벨
                    b_x, b_y, b_txt, b_col = [], [], [], []
                    for idx_dt, row_data in q_fin_df.iterrows():
                        mid_dt = idx_dt + datetime.timedelta(days=45)
                        if c_min <= mid_dt <= c_max + datetime.timedelta(days=90):
                            q_name = f"Q{(idx_dt.month-1)//3+1}'{str(idx_dt.year)[-2:]}"
                            yoy_val = row_data.get('Rev_YoY', np.nan)
                            b_x.append(mid_dt)
                            b_y.append(row_data['Revenue_Eok'])
                            sign = "+" if yoy_val > 0 else ""
                            b_txt.append(f"<b>{q_name}</b><br>{sign}{yoy_val:.1f}%" if pd.notna(yoy_val) else f"<b>{q_name}</b><br>{row_data['Revenue_Eok']:,.1f}")
                            b_col.append('#26A69A' if (pd.notna(yoy_val) and yoy_val >= 0) else '#EF5350')

                    if b_x:
                        fig_ts.add_trace(go.Scatter(x=b_x, y=b_y, mode='text', text=b_txt, textposition="top center", textfont=dict(size=10, color=b_col), showlegend=False), secondary_y=True)

                if 'NetIncome_Eok' in q_fin_df.columns and len(step_x) > 0:
                    fig_ts.add_trace(go.Scatter(x=step_x, y=step_net, mode='lines', name=f'분기 순이익 ({unit_label})', line=dict(color='#FFB74D', width=2, dash='dot')), secondary_y=True)

                fig_ts.update_layout(height=580, template="plotly_dark", paper_bgcolor="#0E1117", plot_bgcolor="#0E1117", hovermode='x unified', margin=dict(l=10, r=10, t=30, b=10), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                fig_ts.update_yaxes(title_text=f"주가 ({currency_symbol})", secondary_y=False, showgrid=True, gridcolor="#2A2E39")
                fig_ts.update_yaxes(title_text=f"실적 ({unit_label})", secondary_y=True, showgrid=False)
                st.plotly_chart(fig_ts, use_container_width=True)

                st.markdown("---")
                st.markdown("#### 📊 과거 10+년 분기 실적 세부 지표 & 마진율 (Segments & KPIs)")
                kpi1, kpi2 = st.columns(2)
                q_labels = [f"{d.year}-Q{(d.month-1)//3+1}" for d in q_fin_df.index]

                with kpi1:
                    fig_k1 = go.Figure()
                    if 'Revenue_Eok' in q_fin_df.columns: fig_k1.add_trace(go.Bar(x=q_labels, y=q_fin_df['Revenue_Eok'], name=f'매출액', marker_color='#29B6F6'))
                    if 'OperatingIncome_Eok' in q_fin_df.columns: fig_k1.add_trace(go.Bar(x=q_labels, y=q_fin_df['OperatingIncome_Eok'], name=f'영업이익', marker_color='#26A69A'))
                    if 'NetIncome_Eok' in q_fin_df.columns: fig_k1.add_trace(go.Bar(x=q_labels, y=q_fin_df['NetIncome_Eok'], name=f'순이익', marker_color='#FFB74D'))
                    fig_k1.update_layout(title=f"10+년 분기별 매출/영업이익/순이익 ({unit_label})", height=360, barmode='group', template="plotly_dark", paper_bgcolor="#0E1117", plot_bgcolor="#0E1117", margin=dict(l=10, r=10, t=40, b=10))
                    st.plotly_chart(fig_k1, use_container_width=True)

                with kpi2:
                    fig_k2 = make_subplots(specs=[[{"secondary_y": True}]])
                    if 'Net_Margin' in q_fin_df.columns: fig_k2.add_trace(go.Scatter(x=q_labels, y=q_fin_df['Net_Margin'], mode='lines+markers', name='순이익률(%)', line=dict(color='#AB47BC', width=2.5)), secondary_y=False)
                    if 'Rev_YoY' in q_fin_df.columns:
                        yoy_cols = ['#26A69A' if v >= 0 else '#EF5350' for v in q_fin_df['Rev_YoY'].fillna(0)]
                        fig_k2.add_trace(go.Bar(x=q_labels, y=q_fin_df['Rev_YoY'], name='매출 YoY 성장률(%)', marker_color=yoy_cols, opacity=0.4), secondary_y=True)
                    fig_k2.update_layout(title="순이익률(%) 및 매출 YoY 성장률(%)", height=360, template="plotly_dark", paper_bgcolor="#0E1117", plot_bgcolor="#0E1117", margin=dict(l=10, r=10, t=40, b=10))
                    st.plotly_chart(fig_k2, use_container_width=True)

                with st.expander("📋 10+년 분기 실적 원본 데이터 확인"):
                    disp_t = q_fin_df.copy()
                    disp_t.index = [d.strftime('%Y-%m-%d') for d in disp_t.index]
                    st.dataframe(disp_t.style.format({'Revenue_Eok': '{:,.2f}', 'OperatingIncome_Eok': '{:,.2f}', 'NetIncome_Eok': '{:,.2f}', 'Net_Margin': '{:.1f}%', 'Rev_YoY': '{:+.1f}%'}), use_container_width=True)

except Exception as e:
    st.error(f"오류가 발생했습니다: {e}")
