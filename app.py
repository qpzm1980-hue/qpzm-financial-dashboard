import datetime
import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import FinanceDataReader as fdr
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 페이지 설정
st.set_page_config(page_title="글로벌 종합 금융 프로 터미널", layout="wide", initial_sidebar_state="expanded")

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
        "TSLA - Tesla": "TSLA",
        "AAPL - Apple": "AAPL",
        "GOOGL - Alphabet (Google)": "GOOGL",
        "AMZN - Amazon": "AMZN",
        "META - Meta Platforms": "META",
        "ORCL - Oracle": "ORCL",
        "PLTR - Palantir Technologies": "PLTR",
        "AMD - Advanced Micro Devices": "AMD",
        "INTC - Intel": "INTC",
        "DIS - Walt Disney": "DIS",
        "NFLX - Netflix": "NFLX",
        "CPNG - Coupang": "CPNG",
        "MSTR - MicroStrategy": "MSTR",
        "LLY - Eli Lilly": "LLY",
        "NVO - Novo Nordisk": "NVO",
        "UNH - UnitedHealth Group": "UNH",
        "GE - General Electric": "GE",
        "GEV - GE Vernova": "GEV",
        "LMT - Lockheed Martin": "LMT",
        "OXY - Occidental Petroleum": "OXY",
        "NOW - ServiceNow": "NOW",
        "SNOW - Snowflake": "SNOW",
        "ETN - Eaton Corporation": "ETN",
        "PWR - Quanta Services": "PWR",
        "HUBB - Hubbell Incorporated": "HUBB",
        "CRDO - Credo Technology": "CRDO",
        "ASTS - AST SpaceMobile": "ASTS",
        "RKLB - Rocket Lab USA": "RKLB",
        "RDW - Redwire": "RDW",
        "LUNR - Intuitive Machines": "LUNR",
        "JOBY - Joby Aviation": "JOBY",
        "IREN - Iris Energy": "IREN",
        "MP - MP Materials": "MP",
        "BABA - Alibaba Group": "BABA",
        "NIO - NIO Inc.": "NIO",
        "BMNR - Biomea Fusion": "BMNR",
        "CBRS - Centerspace": "CBRS",
        "SNDK - Western Digital": "WDC",
        "USAR - US Gold Corp": "USAU"
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

# 세션 상태 기본값 처리
if "selected_category" not in st.session_state:
    st.session_state["selected_category"] = "국내주식 (KRX)"

if input_mode == "목록에서 선택":
    category_list = ["해외주식 (US Custom)", "국내주식 (KRX)", "채권 (Bonds)", "원자재 (Commodity)", "환율 (Forex)", "암호화폐 (Crypto)"]
    cat_idx = category_list.index(st.session_state.get("selected_category", "국내주식 (KRX)")) if st.session_state.get("selected_category") in category_list else 1
    
    category = st.sidebar.radio(
        "🌐 자산 카테고리", 
        category_list, 
        index=cat_idx,
        key="selected_category"
    )

    if category == "해외주식 (US Custom)":
        STOCKS = get_us_stocks()
        currency_symbol = "USD"
    elif category == "국내주식 (KRX)":
        STOCKS = get_krx_stocks()
        # 스캐너에서 선택된 종목이 기존 상위 목록에 없으면 동적 추가
        if "custom_stock_name" in st.session_state and "custom_stock_code" in st.session_state:
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

    # 스캐너에서 선택된 종목이 있는 경우 기본 선택값으로 동기화
    options_list = list(STOCKS.keys())
    default_name = st.session_state.get("custom_stock_name", options_list[0])
    selected_idx = options_list.index(default_name) if default_name in options_list else 0

    selected_name = st.sidebar.selectbox("🔎 종목/자산 선택", options=options_list, index=selected_idx)
    selected_code = STOCKS[selected_name]
else:
    direct_ticker = st.sidebar.text_input("📝 티커 직접 입력 (예: 005930, NVDA, USD/KRW, GC=F)", value="005930").strip()
    selected_name = f"Custom: {direct_ticker}"
    selected_code = direct_ticker
    category = "직접입력"
    currency_symbol = "원" if (direct_ticker.isdigit() or "KRW" in direct_ticker) else "USD"

# 주기 설정 및 매핑
tf_config = {
    "5분봉": {"default": "1일", "options": ["1일", "3일", "5일", "1개월", "2개월"], "interval": "5m"},
    "30분봉": {"default": "5일", "options": ["5일", "1개월", "2개월"], "interval": "30m"},
    "1시간봉": {"default": "1개월", "options": ["5일", "1개월", "2개월", "6개월"], "interval": "60m"},
    "일봉": {"default": "6개월", "options": ["1달", "6개월", "1년", "3년", "5년", "10년"], "interval": "1d"},
    "주봉": {"default": "1년", "options": ["6개월", "1년", "3년", "5년", "10년"], "interval": "1wk"},
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

# 수동 새로고침 및 로그아웃
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

    # 1) 분봉 조회
    if "m" in interval:
        yf_code = code
        if code.isdigit() and len(code) == 6:
            yf_code = f"{code}.KS"
        elif "/" in code:
            c_base, c_quote = code.split("/")
            if c_quote in ["KRW", "USD", "JPY", "EUR", "CNY", "GBP"] and c_base in ["USD", "JPY", "EUR", "CNY", "GBP"]:
                yf_code = f"{c_base}{c_quote}=X"
            else:
                yf_code = code.replace("/", "-")
            
        try:
            ticker_obj = yf.Ticker(yf_code)
            df = ticker_obj.history(period=yf_period, interval=interval)
            if not df.empty:
                df.index = df.index.tz_localize(None)
        except Exception:
            df = pd.DataFrame()
            
        if df.empty:
            return df
    else:
        # 2) 일봉 / 주봉 / 월봉 조회
        today = datetime.date.today()
        if tf == "월봉":
            start_d = today - datetime.timedelta(days=365 * 25)
        elif tf == "주봉":
            start_d = today - datetime.timedelta(days=365 * 10)
        else:
            days_calc = {"1달": 30, "6개월": 180, "1년": 365, "3년": 365*3, "5년": 365*5, "10년": 365*10, "최대(All)": 365*20}
            start_d = today - datetime.timedelta(days=days_calc.get(period_str, 365) + 400)
        
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
            days_calc = {"1달": 30, "6개월": 180, "1년": 365, "3년": 365*3, "5년": 365*5, "10년": 365*10}
            disp_start = today - datetime.timedelta(days=days_calc.get(period_str, 365*5))
            df = df.loc[df.index >= pd.to_datetime(disp_start)]

    return df

# ==================== ⚡ 초고속 수급 폭발 스캐너 ====================
@st.cache_data(ttl=300)
def scan_volume_surge_stocks_fast():
    try:
        today = datetime.date.today()
        sample_hist = fdr.DataReader("005930", today - datetime.timedelta(days=15))
        if sample_hist is None or sample_hist.empty:
            scan_date = today.strftime('%Y-%m-%d')
        else:
            scan_date = sample_hist.index[-1].strftime('%Y-%m-%d')

        df_krx = fdr.StockListing('KRX')
        if df_krx.empty:
            return pd.DataFrame(), scan_date

        chg_col = None
        for col in ['ChgRate', 'ChangesRatio', 'Change', 'chg_rate']:
            if col in df_krx.columns:
                chg_col = col
                break

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

        # 당일 거래대금 2,000억 이상
        targets = df_krx[df_krx[amt_col] >= 200_000_000_000].copy()

        if targets.empty:
            return pd.DataFrame(), scan_date

        results = []
        start_date = today - datetime.timedelta(days=35)

        for _, row in targets.iterrows():
            code = str(row['Code']).zfill(6)
            name = row['Name']
            curr_amount = row[amt_col]
            chg_rate = row[chg_col] if chg_col else 0.0
            close_val = row['Close']
            marcap_val = row.get('Marcap', 0)

            try:
                hist = fdr.DataReader(code, start_date)
                if hist is not None and len(hist) >= 6:
                    if 'Amount' in hist.columns and hist['Amount'].iloc[-1] > 0:
                        amounts = hist['Amount']
                    else:
                        amounts = hist['Close'] * hist['Volume']

                    prev_5days = amounts.iloc[-6:-1]
                    avg_5d = prev_5days.mean()

                    if avg_5d < 200_000_000_000:
                        surge_ratio = (curr_amount / avg_5d) * 100 if avg_5d > 0 else 999.0
                        results.append({
                            '기준일자': scan_date,
                            'Code': code,
                            'Name': name,
                            'Close': close_val,
                            'ChgRate': chg_rate,
                            '당일거래대금(억원)': round(curr_amount / 100_000_000, 1),
                            '직전5일평균(억원)': round(avg_5d / 100_000_000, 1),
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
        tab1, tab2, tab3 = st.tabs(["📊 인터랙티브 종합 차트", "📈 벤치마크 상대 수익률(%) 비교", "🔥 2천억 이상 수급 폭발주 (평소 2천억 미만)"])

        with tab1:
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

        with tab2:
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

        # ==================== TAB 3. 2천억 첫 수급 폭발 스캐너 (클릭 즉시 차트 연동) ====================
        with tab3:
            st.markdown("### 🔥 평소 2천억 미만 $\\rightarrow$ 당일 2천억 이상 메가 수급 폭발주")
            st.info("💡 **원클릭 차트 이동:** 아래 포착된 종목의 **`[📊 차트 보기]`** 버튼을 클릭하면 사이드바 목록에 자동 추가되며 해당 종목의 캔들 차트로 즉시 전환됩니다.")
            
            with st.spinner("KRX 수급 급증 종목 초고속 스캔 중..."):
                surge_data, scan_date = scan_volume_surge_stocks_fast()
                
            if scan_date:
                st.caption(f"📅 **분석 기준 거래일자:** `{scan_date}`")

            if not surge_data.empty:
                st.success(f"기준일({scan_date})에 평소 대비 2,000억 이상 수급이 터진 종목 **{len(surge_data)}개**가 포착되었습니다!")
                
                # 인터랙티브 버튼 카드 목록 렌더링
                for idx, r in surge_data.iterrows():
                    c_code = r['Code']
                    c_name = r['Name']
                    c_close = r['Close']
                    c_chg = r['ChgRate']
                    c_amt = r['당일거래대금(억원)']
                    c_prev_amt = r['직전5일평균(억원)']
                    c_surge = r['수급폭증률']
                    c_marcap = r['시가총액(억원)']
                    
                    with st.container():
                        col_info, col_btn = st.columns([5, 1])
                        with col_info:
                            st.markdown(
                                f"**{c_name}** (`{c_code}`) | **종가:** {c_close:,.0f}원 ({c_chg:+.2f}%) | "
                                f"**당일 거래대금:** <span style='color:#FF9800; font-weight:bold;'>{c_amt:,.1f} 억원</span> | "
                                f"**직전5일평균:** {c_prev_amt:,.1f} 억원 (폭증률: **{c_surge:,.0f}%**) | **시총:** {c_marcap:,.0f} 억원",
                                unsafe_allow_html=True
                            )
                        with col_btn:
                            if st.button("📊 차트 보기", key=f"btn_{c_code}", use_container_width=True):
                                st.session_state["selected_category"] = "국내주식 (KRX)"
                                st.session_state["custom_stock_name"] = c_name
                                st.session_state["custom_stock_code"] = c_code
                                st.rerun()
                        st.markdown("---")

                # 전체 데이터프레임 뷰
                st.dataframe(
                    surge_data.style.format({
                        'Close': '{:,.0f}원',
                        'ChgRate': '{:+.2f}%',
                        '당일거래대금(억원)': '{:,.1f} 억',
                        '직전5일평균(억원)': '{:,.1f} 억',
                        '수급폭증률': '{:,.0f}%',
                        '시가총액(억원)': '{:,.0f} 억'
                    }),
                    use_container_width=True,
                    height=250
                )
            else:
                st.warning(f"기준일({scan_date})에 '평소 2천억 미만 $\\rightarrow$ 2천억 돌파' 조건을 만족하는 종목이 없습니다.")

except Exception as e:
    st.error(f"데이터 조회 중 예기치 않은 오류가 발생했습니다: {e}")
