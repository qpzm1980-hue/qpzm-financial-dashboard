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
if "category_radio" not in st.session_state: st.session_state["category_radio"] = "국내주식 (KRX)"
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
    except Exception: return {"SK하이닉스": "000660", "삼성전자": "005930", "LG에너지솔루션": "373220", "현대차": "005380"}

def get_us_stocks():
    return {
        "TSLA - Tesla": "TSLA", "META - Meta Platforms": "META", "AAPL - Apple": "AAPL",
        "GOOGL - Alphabet (Google)": "GOOGL", "AMZN - Amazon": "AMZN", "NVDA - NVIDIA": "NVDA",
        "MSFT - Microsoft": "MSFT", "PLTR - Palantir Technologies": "PLTR", "AMD - Advanced Micro Devices": "AMD",
        "NFLX - Netflix": "NFLX", "INTC - Intel": "INTC", "CPNG - Coupang": "CPNG", "LLY - Eli Lilly": "LLY"
    }

# 사이드바
st.sidebar.header("🕹️ 컨트롤 패널")
input_mode = st.sidebar.radio("🔍 종목 선택 방식", ["목록에서 선택", "티커 직접 입력"], index=0)

if input_mode == "목록에서 선택":
    category = st.sidebar.radio("🌐 자산 카테고리", ["국내주식 (KRX)", "해외주식 (US Custom)", "채권 (Bonds)", "원자재 (Commodity)", "환율 (Forex)", "암호화폐 (Crypto)"], key="category_radio")
    if category == "국내주식 (KRX)":
        STOCKS = get_krx_stocks()
        if st.session_state["custom_stock_name"] and st.session_state["custom_stock_code"]:
            STOCKS = {st.session_state["custom_stock_name"]: st.session_state["custom_stock_code"], **STOCKS}
        currency_symbol = "원"
    elif category == "해외주식 (US Custom)": STOCKS, currency_symbol = get_us_stocks(), "USD"
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
    direct_ticker = st.sidebar.text_input("📝 티커 직접 입력 (예: 000660, 005930, TSLA, META)", value="000660").strip()
    selected_name = f"Custom: {direct_ticker}"
    selected_code = direct_ticker
    currency_symbol = "원" if (direct_ticker.isdigit() or "KRW" in direct_ticker) else "USD"

# ⏱️ 일봉: 1년, 주봉: 3년, 월봉: 5년 기본
tf_config = {
    "일봉": {"default": "1년", "options": ["1달", "6개월", "1년", "3년", "5년", "10년", "최대(All)"], "interval": "1d"},
    "주봉": {"default": "3년", "options": ["6개월", "1년", "3년", "5년", "10년", "최대(All)"], "interval": "1wk"},
    "월봉": {"default": "5년", "options": ["1년", "3년", "5년", "10년", "최대(All)"], "interval": "1mo"}
}

st.sidebar.markdown("---")
st.sidebar.subheader("⏱️ 차트 주기 & 기간")
timeframe = st.sidebar.radio("📊 차트 주기", list(tf_config.keys()), index=0)
current_cfg = tf_config[timeframe]

selected_period = st.sidebar.select_slider(
    "📅 조회 기간", 
    options=current_cfg["options"], 
    value=current_cfg["default"],
    key=f"slider_period_{timeframe}"
)

st.sidebar.markdown("---")
st.sidebar.subheader("📐 보조지표 표시")
show_ma = st.sidebar.checkbox("이동평균선 (20/50/100/200)", value=True)
show_bb = st.sidebar.checkbox("볼린저 밴드 (20, 2)", value=False)
show_rsi = st.sidebar.checkbox("RSI (14)", value=True)
show_macd = st.sidebar.checkbox("MACD (12, 26, 9)", value=True)

if "DART_API_KEY" in st.secrets:
    st.sidebar.success("🏛️ DART & SEC EDGAR 연동 활성화")

if st.sidebar.button("🔄 최신 시세 강제 갱신"):
    st.cache_data.clear()
    st.rerun()

# ==================== 데이터 계산 ====================
days_calc = {"1달": 30, "6개월": 180, "1년": 365, "3년": 365*3, "5년": 365*5, "10년": 365*10}

@st.cache_data(ttl=60)
def load_and_calculate_data(code, tf, period_str):
    today = datetime.date.today()
    if period_str == "최대(All)":
        start_d = "1990-01-01"
    else:
        start_d = today - datetime.timedelta(days=days_calc.get(period_str, 365) + 400)
        
    try: df = fdr.DataReader(code, start_d)
    except Exception: df = pd.DataFrame()
    if df.empty: return df
    if tf == "주봉": df = df.resample('W-FRI').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last', 'Volume':'sum'}).dropna()
    elif tf == "월봉": 
        try:
            df = df.resample('ME').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last', 'Volume':'sum'}).dropna()
        except Exception:
            df = df.resample('M').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last', 'Volume':'sum'}).dropna()

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

    if period_str != "최대(All)":
        days_disp = days_calc.get(period_str, 365)
        disp_start = today - datetime.timedelta(days=days_disp)
        df = df.loc[df.index >= pd.to_datetime(disp_start)]
    return df

# ==================== 🏛️ 국내 DART 2015~현재 전 기간 전수 수집 및 4분기 솟구침 보정 엔진 ====================
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
    # fnlttSinglAcntAll(전체계정) -> fnlttSinglAcnt(주요계정)
    for api_type in ["fnlttSinglAcntAll", "fnlttSinglAcnt"]:
        for fs_div in ["CFS", "OFS"]:
            try:
                url = f"https://opendart.fss.or.kr/api/{api_type}.json?crtfc_key={dart_key}&corp_code={corp_code}&bsns_year={y}&reprt_code={r_code}&fs_div={fs_div}"
                resp = requests.get(url, timeout=4).json()
                
                if resp.get("status") == "000" and "list" in resp:
                    items = resp["list"]
                    rev, op, net = np.nan, np.nan, np.nan
                    
                    for it in items:
                        acc_nm = str(it.get("account_nm", "")).replace(" ", "").strip()
                        val_str = str(it.get("thstrm_amount", "0")).replace(",", "")
                        val_num = pd.to_numeric(val_str, errors='coerce')
                        
                        # 분기 순수 금액(3개월치) 필드가 존재하면 우선 활용
                        if "thstrm_q_amount" in it and pd.notna(it.get("thstrm_q_amount")):
                            q_str = str(it.get("thstrm_q_amount", "")).replace(",", "")
                            q_num_val = pd.to_numeric(q_str, errors='coerce')
                            if pd.notna(q_num_val): val_num = q_num_val

                        # 1. 매출액 계정 (SK하이닉스, 삼성전자, 금융, 지주, 바이오 등 전수 매칭)
                        if pd.isna(rev):
                            if any(acc_nm == k for k in ["수익(매출액)", "매출액", "영업수익", "수익", "매출", "보험수익", "이자수익", "순영업수익"]):
                                rev = val_num
                            elif re.search(r'^(수익\(매출액\)|매출액|영업수익|매출|수익)$', acc_nm):
                                rev = val_num

                        # 2. 영업이익 계정
                        if pd.isna(op):
                            if any(acc_nm == k for k in ["영업이익", "영업이익(손실)", "영업손익"]):
                                op = val_num
                            elif "영업이익" in acc_nm or "영업손익" in acc_nm:
                                op = val_num

                        # 3. 당기순이익 계정
                        if pd.isna(net):
                            if any(acc_nm == k for k in ["당기순이익", "당기순이익(손실)", "분기순이익", "분기순이익(손실)", "반기순이익", "반기순이익(손실)", "연결당기순이익", "지배기업소유주지분순이익", "지배기업의소유주지분순이익"]):
                                net = val_num
                            elif "당기순이익" in acc_nm or "분기순이익" in acc_nm:
                                net = val_num

                    if pd.notna(rev) or pd.notna(net):
                        dt_key = pd.to_datetime(f"{y}-{end_day}")
                        return (dt_key, {
                            'Revenue_Eok': rev / 100_000_000 if pd.notna(rev) else np.nan,
                            'OperatingIncome_Eok': op / 100_000_000 if pd.notna(op) else np.nan,
                            'NetIncome_Eok': net / 100_000_000 if pd.notna(net) else np.nan,
                            'q_num': q_num,
                            'year': y
                        })
            except Exception:
                continue
    return None

@st.cache_data(ttl=3600)
def load_korean_backup_financials(code):
    res_dict = {}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}
    try:
        url = f"https://finance.naver.com/item/main.naver?code={code}"
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code == 200:
            tables = pd.read_html(StringIO(r.text))
            for t in tables:
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
                                rev_val = pd.to_numeric(str(df_nt.loc[df_nt.index[0], col_tuple]).replace(',', ''), errors='coerce')
                                op_val = pd.to_numeric(str(df_nt.loc[df_nt.index[1], col_tuple]).replace(',', ''), errors='coerce') if len(df_nt)>1 else np.nan
                                net_val = pd.to_numeric(str(df_nt.loc[df_nt.index[2], col_tuple]).replace(',', ''), errors='coerce') if len(df_nt)>2 else np.nan
                                if pd.notna(rev_val) or pd.notna(net_val):
                                    q_num_val = (int(mo) - 1) // 3 + 1
                                    res_dict[dt_key] = {'Revenue_Eok': rev_val, 'OperatingIncome_Eok': op_val, 'NetIncome_Eok': net_val, 'year': int(y), 'q_num': q_num_val}
    except Exception: pass
    return res_dict

@st.cache_data(ttl=86400)
def get_sec_cik_map():
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'}
        r = requests.get('https://www.sec.gov/files/company_tickers.json', headers=headers, timeout=5)
        if r.status_code == 200:
            data = r.json()
            return {v['ticker'].upper(): str(v['cik_str']) for v in data.values()}
    except Exception: pass
    return {
        "TSLA": "1318605", "META": "1326801", "AAPL": "320193", "NVDA": "1045810",
        "MSFT": "789019", "AMZN": "1018724", "GOOGL": "1652044", "GOOG": "1652044",
        "PLTR": "1321655", "AMD": "2488", "NFLX": "1065280", "INTC": "50863", "CPNG": "1834584", "LLY": "59478"
    }

@st.cache_data(ttl=7200)
def load_sec_edgar_10y_financials(ticker_symbol):
    t_clean = ticker_symbol.upper().strip()
    cik_map = get_sec_cik_map()
    cik = cik_map.get(t_clean)
    
    if cik:
        try:
            url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik.zfill(10)}.json"
            headers = {'User-Agent': 'PersonalFinanceTerminal/2.1 (admin@globalinvest.org)'}
            resp = requests.get(url, headers=headers, timeout=8)
            
            if resp.status_code == 200:
                cf = resp.json().get('facts', {}).get('us-gaap', {})
                q_dict = {}

                rev_tags = [
                    'RevenueFromContractWithCustomerExcludingAssessedTax',
                    'SalesRevenueNet',
                    'Revenues',
                    'TotalRevenuesAndOtherIncome',
                    'SalesRevenueGoodsNet',
                    'AutomotiveRevenues'
                ]
                net_tags = [
                    'NetIncomeLoss',
                    'ProfitLoss',
                    'NetIncomeLossAvailableToCommonStockholdersBasic'
                ]
                op_tags = ['OperatingIncomeLoss']

                def parse_multi_tags(tag_list, val_key):
                    for tag in tag_list:
                        if tag in cf and 'USD' in cf[tag].get('units', {}):
                            items = cf[tag]['units']['USD']
                            for item in items:
                                form = item.get('form', '')
                                fp = item.get('fp', '')
                                end_dt = item.get('end', '')
                                val = item.get('val', np.nan)
                                start_dt = item.get('start', '')
                                
                                if form in ['10-Q', '10-K'] and end_dt and pd.notna(val):
                                    is_quarter = False
                                    if start_dt:
                                        try:
                                            diff_d = (pd.to_datetime(end_dt) - pd.to_datetime(start_dt)).days
                                            if 60 <= diff_d <= 115:
                                                is_quarter = True
                                        except Exception: pass
                                    elif fp in ['Q1', 'Q2', 'Q3', 'Q4']:
                                        is_quarter = True
                                        
                                    if is_quarter:
                                        dt_idx = pd.to_datetime(end_dt)
                                        if dt_idx not in q_dict:
                                            q_dict[dt_idx] = {}
                                        if val_key not in q_dict[dt_idx] or pd.isna(q_dict[dt_idx][val_key]):
                                            q_dict[dt_idx][val_key] = val / 1_000_000_000

                parse_multi_tags(rev_tags, 'Revenue_Eok')
                parse_multi_tags(net_tags, 'NetIncome_Eok')
                parse_multi_tags(op_tags, 'OperatingIncome_Eok')
                
                if q_dict:
                    df_sec = pd.DataFrame.from_dict(q_dict, orient='index').sort_index()
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
                
                with ThreadPoolExecutor(max_workers=6) as executor:
                    results = executor.map(fetch_single_dart_report, task_list)
                for res in results:
                    if res is not None: res_dict[res[0]] = res[1]

        # 백업망 보완
        backup_data = load_korean_backup_financials(code)
        for k, v in backup_data.items():
            if k not in res_dict:
                res_dict[k] = v

        if res_dict:
            raw_df = pd.DataFrame.from_dict(res_dict, orient='index').sort_index()
            pure_dict = {}
            
            # 🎯 [핵심] 4분기 솟구침 완벽 제거 및 3개월 순수 분기 실적 정규화
            for y_val in raw_df['year'].dropna().unique():
                y_df = raw_df[raw_df['year'] == y_val].sort_values(by='q_num')
                q1_row = y_df[y_df['q_num'] == 1]
                q2_row = y_df[y_df['q_num'] == 2]
                q3_row = y_df[y_df['q_num'] == 3]
                q4_row = y_df[y_df['q_num'] == 4]
                
                # Q1
                if not q1_row.empty:
                    pure_dict[q1_row.index[0]] = {
                        'Revenue_Eok': q1_row['Revenue_Eok'].iloc[0],
                        'OperatingIncome_Eok': q1_row['OperatingIncome_Eok'].iloc[0],
                        'NetIncome_Eok': q1_row['NetIncome_Eok'].iloc[0]
                    }
                # Q2 (반기 누적인 경우 1분기 차감)
                if not q2_row.empty:
                    q1_r = q1_row['Revenue_Eok'].iloc[0] if (not q1_row.empty and pd.notna(q1_row['Revenue_Eok'].iloc[0])) else 0
                    q2_r = q2_row['Revenue_Eok'].iloc[0]
                    pure_r = (q2_r - q1_r) if (pd.notna(q2_r) and q2_r > q1_r and q1_r > 0) else q2_r
                    pure_dict[q2_row.index[0]] = {
                        'Revenue_Eok': max(0.0, pure_r) if pd.notna(pure_r) else np.nan,
                        'OperatingIncome_Eok': q2_row['OperatingIncome_Eok'].iloc[0] - (q1_row['OperatingIncome_Eok'].iloc[0] if not q1_row.empty else 0),
                        'NetIncome_Eok': q2_row['NetIncome_Eok'].iloc[0] - (q1_row['NetIncome_Eok'].iloc[0] if not q1_row.empty else 0)
                    }
                # Q3 (3분기 누적인 경우 반기 누적 차감)
                if not q3_row.empty:
                    q2_cum_r = q2_row['Revenue_Eok'].iloc[0] if (not q2_row.empty and pd.notna(q2_row['Revenue_Eok'].iloc[0])) else 0
                    q3_r = q3_row['Revenue_Eok'].iloc[0]
                    pure_r = (q3_r - q2_cum_r) if (pd.notna(q3_r) and q3_r > q2_cum_r and q2_cum_r > 0) else q3_r
                    pure_dict[q3_row.index[0]] = {
                        'Revenue_Eok': max(0.0, pure_r) if pd.notna(pure_r) else np.nan,
                        'OperatingIncome_Eok': q3_row['OperatingIncome_Eok'].iloc[0] - (q2_row['OperatingIncome_Eok'].iloc[0] if not q2_row.empty else 0),
                        'NetIncome_Eok': q3_row['NetIncome_Eok'].iloc[0] - (q2_row['NetIncome_Eok'].iloc[0] if not q2_row.empty else 0)
                    }
                # Q4 (사업보고서 연간 누적에서 3분기 누적 차감 -> 솟구침 완벽 제거)
                if not q4_row.empty:
                    q3_cum_r = q3_row['Revenue_Eok'].iloc[0] if not q3_row.empty else (q2_row['Revenue_Eok'].iloc[0] if not q2_row.empty else 0)
                    q4_r = q4_row['Revenue_Eok'].iloc[0]
                    
                    if pd.notna(q4_r) and pd.notna(q3_cum_r) and q4_r > q3_cum_r and q3_cum_r > 0:
                        pure_r = q4_r - q3_cum_r
                    elif pd.notna(q4_r) and q4_r > 50000: # 대형주 연간 누적으로 남아있는 경우 4등분 추정
                        pure_r = q4_r / 4.0
                    else:
                        pure_r = q4_r
                        
                    pure_dict[q4_row.index[0]] = {
                        'Revenue_Eok': max(0.0, pure_r) if pd.notna(pure_r) else np.nan,
                        'OperatingIncome_Eok': q4_row['OperatingIncome_Eok'].iloc[0] - (q3_row['OperatingIncome_Eok'].iloc[0] if not q3_row.empty else 0),
                        'NetIncome_Eok': q4_row['NetIncome_Eok'].iloc[0] - (q3_row['NetIncome_Eok'].iloc[0] if not q3_row.empty else 0)
                    }

            final_df = pd.DataFrame.from_dict(pure_dict if pure_dict else res_dict, orient='index').sort_index()
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
        return load_sec_edgar_10y_financials(code)

    return pd.DataFrame()

# ==================== ⚡ 사용자 맞춤 조건 수급 돌파 스캐너 ====================
@st.cache_data(ttl=300)
def scan_custom_volume_surge(lookback_days, threshold_won, min_chg_rate=0.0):
    try:
        today = datetime.date.today()
        sample_hist = fdr.DataReader("005930", today - datetime.timedelta(days=15))
        scan_date = sample_hist.index[-1].strftime('%Y-%m-%d') if (sample_hist is not None and not sample_hist.empty) else str(today)
        df_krx = fdr.StockListing('KRX')
        if df_krx.empty: return pd.DataFrame(), scan_date

        amt_col = next((c for c in ['Amount', 'TradeValue', 'amount', 'VolumeValue'] if c in df_krx.columns), None)
        if amt_col is None and 'Volume' in df_krx.columns and 'Close' in df_krx.columns:
            df_krx['Estimated_Amount'] = df_krx['Volume'] * df_krx['Close']
            amt_col = 'Estimated_Amount'
        if amt_col is None: return pd.DataFrame(), scan_date

        vol_col = 'Volume' if 'Volume' in df_krx.columns else None
        targets = df_krx[df_krx[amt_col] >= threshold_won].copy()
        if targets.empty: return pd.DataFrame(), scan_date

        results = []
        start_date = today - datetime.timedelta(days=int(lookback_days * 1.8) + 25)

        for _, row in targets.iterrows():
            code = str(row['Code']).zfill(6)
            name = row['Name']
            curr_amount = row[amt_col]
            curr_vol = row[vol_col] if vol_col else 1.0
            marcap_val = row.get('Marcap', 0)
            if not is_valid_normal_stock(name, code, curr_vol, curr_amount): continue

            try:
                hist = fdr.DataReader(code, start_date)
                if hist is not None and len(hist) >= min(10, lookback_days) and hist['Volume'].iloc[-1] > 0:
                    amounts = hist['Amount'] if 'Amount' in hist.columns and hist['Amount'].iloc[-1] > 0 else hist['Close'] * hist['Volume']
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
                                'Code': code, 'Name': name, 'Close': curr_close, 'ChgRate': real_chg_rate,
                                '당일거래대금(억원)': round(curr_amount / 100_000_000, 1),
                                '어제거래대금(억원)': round(yesterday_amt / 100_000_000, 1),
                                f'{lookback_days}일평균(억원)': round(avg_period_amt / 100_000_000, 1),
                                '수급폭증률': round(surge_ratio, 0), '시가총액(억원)': round(marcap_val / 100_000_000, 0),
                                'Market': row.get('Market', 'KRX')
                            })
            except Exception: continue

        if not results: return pd.DataFrame(), scan_date
        return pd.DataFrame(results).sort_values(by='당일거래대금(억원)', ascending=False), scan_date
    except Exception: return pd.DataFrame(), str(datetime.date.today())

# ==================== 🧊 장기 초소외주 스캐너 ====================
@st.cache_data(ttl=600)
def scan_dormant_stocks(lookback_days, max_cap_won, min_marcap_eok, max_marcap_eok):
    try:
        today = datetime.date.today()
        sample_hist = fdr.DataReader("005930", today - datetime.timedelta(days=15))
        scan_date = sample_hist.index[-1].strftime('%Y-%m-%d') if (sample_hist is not None and not sample_hist.empty) else str(today)
        df_krx = fdr.StockListing('KRX')
        if df_krx.empty: return pd.DataFrame(), scan_date

        amt_col = next((c for c in ['Amount', 'TradeValue', 'amount', 'VolumeValue'] if c in df_krx.columns), None)
        if amt_col is None and 'Volume' in df_krx.columns and 'Close' in df_krx.columns:
            df_krx['Estimated_Amount'] = df_krx['Volume'] * df_krx['Close']
            amt_col = 'Estimated_Amount'

        vol_col = 'Volume' if 'Volume' in df_krx.columns else None
        min_marcap_won = min_marcap_eok * 100_000_000
        max_marcap_won = max_marcap_eok * 100_000_000
        cands = df_krx[(df_krx[amt_col] < max_cap_won) & (df_krx['Marcap'] >= min_marcap_won) & (df_krx['Marcap'] <= max_marcap_won)].copy()
        if cands.empty: return pd.DataFrame(), scan_date

        results = []
        start_date = today - datetime.timedelta(days=int(lookback_days * 1.8) + 30)
        sample_cands = cands.sort_values(by='Marcap', ascending=False).head(150)

        for _, row in sample_cands.iterrows():
            code = str(row['Code']).zfill(6)
            name = row['Name']
            marcap_val = row.get('Marcap', 0)
            curr_amt_krx = row[amt_col]
            curr_vol_krx = row[vol_col] if vol_col else 1.0
            if not is_valid_normal_stock(name, code, curr_vol_krx, curr_amt_krx): continue

            try:
                hist = fdr.DataReader(code, start_date)
                if hist is not None and len(hist) >= min(60, int(lookback_days * 0.5)) and hist['Volume'].iloc[-1] > 0:
                    amounts = hist['Amount'] if 'Amount' in hist.columns and hist['Amount'].iloc[-1] > 0 else hist['Close'] * hist['Volume']
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
                            'Code': code, 'Name': name, 'Close': curr_close, 'ChgRate': real_chg_rate,
                            f'{lookback_days}일최대거래대금(억원)': round(max_amt / 100_000_000, 1),
                            f'{lookback_days}일평균거래대금(억원)': round(avg_amt / 100_000_000, 2),
                            '당일거래대금(억원)': round(curr_amt / 100_000_000, 2),
                            '시가총액(억원)': round(marcap_val / 100_000_000, 0),
                            'Market': row.get('Market', 'KRX')
                        })
            except Exception: continue

        if not results: return pd.DataFrame(), scan_date
        return pd.DataFrame(results).sort_values(by=f'{lookback_days}일평균거래대금(억원)', ascending=True), scan_date
    except Exception: return pd.DataFrame(), str(datetime.date.today())

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
        tab_titles = [
            "📊 인터랙티브 종합 차트", 
            "📈 벤치마크 상대 수익률(%) 비교", 
            "🔥 맞춤 조건 수급 폭발 스캐너",
            "🧊 장기 초소외주 (1년 거래대금 100억 미만) 탐색기",
            "🏢 펀더멘털 & 실적-주가 복합 차트 (TrendSpider)"
        ]
        active_tab = st.radio("탭 선택", tab_titles, horizontal=True, label_visibility="collapsed", key="tab_selector")

        if active_tab == "📊 인터랙티브 종합 차트":
            x_data = display_df.index
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

        elif active_tab == "🔥 맞춤 조건 수급 폭발 스캐너":
            st.markdown("### 🔥 맞춤 조건 수급 폭발 주도주 실시간 스캐너")
            c1, c2, c3, c4 = st.columns([1.2, 1.2, 1.0, 1.0])
            i_lookback = c1.number_input("📅 잠복 거래일수", 1, 365, 20, 5)
            i_threshold = c2.number_input("💰 돌파 거래대금 (억원)", 10, 10000, 500, 50)
            i_min_chg = c3.selectbox("📈 최소 당일 상승률", [0.0, 3.0, 5.0, 7.0, 10.0, 15.0], 0, format_func=lambda x: "전체" if x == 0.0 else f"+{x:.0f}% 이상")
            c4.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            if c4.button("🔍 조건 검색 실행", type="primary", use_container_width=True):
                with st.spinner("KRX 전 종목 스캔 중..."):
                    st.session_state["scan_results_df"], st.session_state["scan_results_date"] = scan_custom_volume_surge(i_lookback, i_threshold * 100_000_000, i_min_chg)
                    st.session_state["last_scanned_params"] = {"lookback": i_lookback, "threshold": i_threshold}

            if st.session_state["scan_results_df"] is not None:
                s_df, s_date = st.session_state["scan_results_df"], st.session_state["scan_results_date"]
                if not s_df.empty:
                    st.success(f"포착 종목 **{len(s_df)}개**")
                    if st.button("📲 텔레그램 전체 전송"):
                        for idx_s in range(0, len(s_df), 20):
                            chunk = s_df.iloc[idx_s:idx_s+20]
                            lines = [f"🚨 *[수급 폭발 종목]* ({idx_s+1}~{min(idx_s+20, len(s_df))})"]
                            for _, r in chunk.iterrows(): lines.append(f"• *{r['Name']}* (`{r['Code']}`): {r['Close']:,.0f}원 ({r['ChgRate']:+.2f}%) | {r['당일거래대금(억원)']}억")
                            send_telegram_message("\n".join(lines)); time.sleep(0.3)
                        st.toast("텔레그램 전송 완료!", icon="🚀")
                    st.dataframe(s_df.style.format({'Close': '{:,.0f}원', 'ChgRate': '{:+.2f}%', '당일거래대금(억원)': '{:,.1f} 억'}), use_container_width=True)

        elif active_tab == "🧊 장기 초소외주 (1년 거래대금 100억 미만) 탐색기":
            st.markdown("### 🧊 장기 초소외주 / 품절주 전수 탐색기")
            d1, d2, d3, d4, d5 = st.columns([1.1, 1.1, 1.0, 1.0, 1.0])
            dl = d1.number_input("📅 추적 기간 (일수)", 30, 500, 365, 30)
            dm = d2.number_input("🚫 최대 거래대금 상한선 (억원)", 1, 500, 100, 10)
            dmin = d3.number_input("💵 최소 시총 (억원)", 50, 5000, 300, 50)
            dmax = d4.number_input("💎 최대 시총 (억원)", 100, 50000, 3000, 500)
            d5.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            if d5.button("🧊 소외주 전수 스캔", type="primary", use_container_width=True):
                with st.spinner("초소외주 분석 중..."):
                    st.session_state["dormant_scan_results"], st.session_state["dormant_scan_date"] = scan_dormant_stocks(dl, dm * 100_000_000, dmin, dmax)
                    st.session_state["dormant_params"] = {"lookback": dl, "max_amt": dm}

            if st.session_state["dormant_scan_results"] is not None:
                dd_df = st.session_state["dormant_scan_results"]
                if not dd_df.empty:
                    st.success(f"발굴 종목 **{len(dd_df)}개**")
                    if st.button("📲 소외주 전체 텔레그램 전송"):
                        for idx_d in range(0, len(dd_df), 20):
                            chunk = dd_df.iloc[idx_d:idx_d+20]
                            lines = [f"🧊 *[초소외주 목록]* ({idx_d+1}~{min(idx_d+20, len(dd_df))})"]
                            for _, r in chunk.iterrows(): lines.append(f"• *{r['Name']}* (`{r['Code']}`): {r['Close']:,.0f}원 | 일평균: {r.get(f'{dl}일평균거래대금(억원)', 0)}억")
                            send_telegram_message("\n".join(lines)); time.sleep(0.3)
                        st.toast("텔레그램 전송 완료!", icon="🚀")
                    st.dataframe(dd_df, use_container_width=True)

        else:
            # ==================== 🏢 5번째 탭: TrendSpider 펀더멘털 복합 차트 (조회 기간 100% 동기화) ====================
            is_korean = str(selected_code).isdigit() and len(str(selected_code)) == 6
            source_lbl = "금융감독원 Open DART 전자공시" if is_korean else "미국 증권거래위원회 SEC EDGAR 공식 XBRL"
            unit_label = "억원" if is_korean else "Billion USD"

            st.markdown(f"### 🏢 {selected_name} - 펀더멘털 & 분기 실적(KPI) 오버레이 차트")
            st.caption(f"사이드바 주기: **`{timeframe}`** | 선택 기간: **`{selected_period}`** | 출처: **`{source_lbl}`** (2015~현재 전 기간 연동)")

            with st.spinner(f"{source_lbl}에서 분기 실적 수집 및 기간 동기화 중..."):
                raw_fin_df = load_global_full_history_financials(selected_code)

            if raw_fin_df.empty:
                st.warning(f"'{selected_name}'의 분기 실적 데이터를 가져올 수 없습니다. 종목 티커를 확인하세요.")
            else:
                synced_price_df = display_df
                c_min, c_max = synced_price_df.index.min(), synced_price_df.index.max()

                # 🎯 조회 기간 범위 내로 실적 데이터 완벽 필터링
                q_fin_df = raw_fin_df.loc[(raw_fin_df.index >= (c_min - datetime.timedelta(days=45))) & (raw_fin_df.index <= (c_max + datetime.timedelta(days=90)))].copy()
                if q_fin_df.empty:
                    q_fin_df = raw_fin_df.copy()

                st.markdown(f"#### 📈 주가 & 분기 실적 스텝 오버레이 (현재 기간: `{selected_period}` | 출처: `{source_lbl}`)")
                fig_ts = make_subplots(specs=[[{"secondary_y": True}]])
                fig_ts.add_trace(go.Scatter(x=synced_price_df.index, y=synced_price_df['Close'], mode='lines', name=f'주가 ({timeframe})', line=dict(color='#29B6F6', width=2), fill='tozeroy', fillcolor='rgba(41, 182, 246, 0.04)'), secondary_y=False)

                step_x, step_rev, step_net = [], [], []

                for i in range(len(q_fin_df)):
                    curr_dt = q_fin_df.index[i]
                    next_dt = q_fin_df.index[i+1] if (i+1 < len(q_fin_df)) else curr_dt + datetime.timedelta(days=90)
                    
                    eff_start = max(curr_dt, c_min)
                    eff_end = min(next_dt, c_max)
                    
                    if eff_end >= eff_start:
                        r_val = q_fin_df['Revenue_Eok'].iloc[i] if 'Revenue_Eok' in q_fin_df.columns else np.nan
                        n_val = q_fin_df['NetIncome_Eok'].iloc[i] if 'NetIncome_Eok' in q_fin_df.columns else np.nan
                        step_x.extend([eff_start, eff_end])
                        step_rev.extend([r_val, r_val])
                        step_net.extend([n_val, n_val])

                if 'Revenue_Eok' in q_fin_df.columns and len(step_x) > 0:
                    fig_ts.add_trace(go.Scatter(x=step_x, y=step_rev, mode='lines', name=f'분기 매출액 ({unit_label})', line=dict(color='#26A69A', width=2.8)), secondary_y=True)
                    
                    # 배지 라벨 (HTML 기반 안전 렌더링)
                    b_x, b_y, b_txt = [], [], []
                    for idx_dt, row_data in q_fin_df.iterrows():
                        mid_dt = idx_dt + datetime.timedelta(days=45)
                        if c_min <= mid_dt <= (c_max + datetime.timedelta(days=45)):
                            q_name = f"Q{(idx_dt.month-1)//3+1}'{str(idx_dt.year)[-2:]}"
                            yoy_val = row_data.get('Rev_YoY', np.nan)
                            b_x.append(mid_dt)
                            b_y.append(row_data['Revenue_Eok'])
                            sign = "+" if yoy_val > 0 else ""
                            color_tag = "#26A69A" if (pd.notna(yoy_val) and yoy_val >= 0) else "#EF5350"
                            
                            if pd.notna(yoy_val):
                                b_txt.append(f"<span style='color:{color_tag}; font-weight:bold;'>{q_name}</span><br><span style='color:{color_tag};'>{sign}{yoy_val:.1f}%</span>")
                            else:
                                b_txt.append(f"<b>{q_name}</b><br>{row_data['Revenue_Eok']:,.1f}")

                    if b_x:
                        fig_ts.add_trace(go.Scatter(x=b_x, y=b_y, mode='text', text=b_txt, textposition="top center", showlegend=False), secondary_y=True)

                if 'NetIncome_Eok' in q_fin_df.columns and len(step_x) > 0:
                    fig_ts.add_trace(go.Scatter(x=step_x, y=step_net, mode='lines', name=f'분기 순이익 ({unit_label})', line=dict(color='#FFB74D', width=2, dash='dot')), secondary_y=True)

                fig_ts.update_layout(height=580, template="plotly_dark", paper_bgcolor="#0E1117", plot_bgcolor="#0E1117", hovermode='x unified', margin=dict(l=10, r=10, t=30, b=10), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                fig_ts.update_yaxes(title_text=f"주가 ({currency_symbol})", secondary_y=False, showgrid=True, gridcolor="#2A2E39")
                fig_ts.update_yaxes(title_text=f"실적 ({unit_label})", secondary_y=True, showgrid=False)
                st.plotly_chart(fig_ts, use_container_width=True)

                st.markdown("---")
                
                # 하단 차트
                st.markdown(f"#### 📊 선택 기간({selected_period}) 분기 실적 세부 지표 & 마진율 (Segments & KPIs)")
                kpi1, kpi2 = st.columns(2)
                q_labels = [f"{d.year}-Q{(d.month-1)//3+1}" for d in q_fin_df.index]

                with kpi1:
                    fig_k1 = go.Figure()
                    if 'Revenue_Eok' in q_fin_df.columns: fig_k1.add_trace(go.Bar(x=q_labels, y=q_fin_df['Revenue_Eok'], name=f'매출액', marker_color='#29B6F6'))
                    if 'OperatingIncome_Eok' in q_fin_df.columns: fig_k1.add_trace(go.Bar(x=q_labels, y=q_fin_df['OperatingIncome_Eok'], name=f'영업이익', marker_color='#26A69A'))
                    if 'NetIncome_Eok' in q_fin_df.columns: fig_k1.add_trace(go.Bar(x=q_labels, y=q_fin_df['NetIncome_Eok'], name=f'순이익', marker_color='#FFB74D'))
                    fig_k1.update_layout(title=f"선택 기간({selected_period}) 분기별 매출/영업이익/순이익 ({unit_label})", height=360, barmode='group', template="plotly_dark", paper_bgcolor="#0E1117", plot_bgcolor="#0E1117", margin=dict(l=10, r=10, t=40, b=10))
                    st.plotly_chart(fig_k1, use_container_width=True)

                with kpi2:
                    fig_k2 = make_subplots(specs=[[{"secondary_y": True}]])
                    if 'Net_Margin' in q_fin_df.columns: fig_k2.add_trace(go.Scatter(x=q_labels, y=q_fin_df['Net_Margin'], mode='lines+markers', name='순이익률(%)', line=dict(color='#AB47BC', width=2.5)), secondary_y=False)
                    if 'Rev_YoY' in q_fin_df.columns:
                        yoy_cols = ['#26A69A' if v >= 0 else '#EF5350' for v in q_fin_df['Rev_YoY'].fillna(0)]
                        fig_k2.add_trace(go.Bar(x=q_labels, y=q_fin_df['Rev_YoY'], name='매출 YoY 성장률(%)', marker_color=yoy_cols, opacity=0.4), secondary_y=True)
                    fig_k2.update_layout(title=f"선택 기간({selected_period}) 순이익률(%) 및 매출 YoY 성장률(%)", height=360, template="plotly_dark", paper_bgcolor="#0E1117", plot_bgcolor="#0E1117", margin=dict(l=10, r=10, t=40, b=10))
                    st.plotly_chart(fig_k2, use_container_width=True)

                with st.expander(f"📋 선택 기간({selected_period}) 분기 실적 원본 데이터 확인"):
                    disp_t = q_fin_df.copy()
                    disp_t.index = [d.strftime('%Y-%m-%d') for d in disp_t.index]
                    for c_name in disp_t.columns:
                        if c_name in ['Revenue_Eok', 'OperatingIncome_Eok', 'NetIncome_Eok']:
                            disp_t[c_name] = disp_t[c_name].apply(lambda x: f"{x:,.2f}" if pd.notna(x) else "-")
                        elif c_name in ['Net_Margin', 'Rev_YoY', 'Net_YoY']:
                            disp_t[c_name] = disp_t[c_name].apply(lambda x: f"{x:+.1f}%" if pd.notna(x) else "-")
                    st.dataframe(disp_t, use_container_width=True)

except Exception as e:
    st.error(f"오류가 발생했습니다: {e}")
