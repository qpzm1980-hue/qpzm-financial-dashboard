import datetime
import streamlit as st
import pandas as pd
import numpy as np
import FinanceDataReader as fdr
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 페이지 설정
st.set_page_config(page_title="글로벌 종합 금융 프로 터미널", layout="wide", initial_sidebar_state="expanded")

# ==================== 1. 비공개 접속 비밀번호 인증 ====================
def check_password():
    # 1) 이미 비밀번호를 통과한 세션인지 확인
    if st.session_state.get("authenticated", False):
        return True

    # 2) Secrets에 비밀번호 설정이 있는지 확인
    app_pwd = st.secrets.get("APP_PASSWORD", None)
    
    # Secrets가 설정되지 않았다면 기본값으로 방어 (누구나 접근 방지)
    if not app_pwd:
        st.warning("⚠️ Streamlit Secrets에 APP_PASSWORD가 설정되지 않았습니다. 관리자 설정을 확인하세요.")
        return False

    # 3) 로그인 화면 출력
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

# 인증되지 않은 사용자는 이후 코드 실행 중단
if not check_password():
    st.stop()

# ==================== 2. 본문 대시보드 화면 ====================

import datetime
import streamlit as st
import pandas as pd
import numpy as np
import FinanceDataReader as fdr
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 페이지 설정
st.set_page_config(page_title="글로벌 종합 금융 프로 터미널", layout="wide", initial_sidebar_state="expanded")

# 커스텀 다크 스타일 CSS
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

# 1. 국내주식 시총 상위 100개
@st.cache_data(ttl=3600)
def get_krx_stocks():
    try:
        df = fdr.StockListing('KRX')
        df = df.sort_values(by='Marcap', ascending=False).head(100)
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

# 3. 주요 환율 리스트
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

# 4. 주요 코인 리스트
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

# 티커 직접 입력 모드 지원
input_mode = st.sidebar.radio("🔍 종목 선택 방식", ["목록에서 선택", "티커 직접 입력"], index=0)

if input_mode == "목록에서 선택":
    category = st.sidebar.radio(
        "🌐 자산 카테고리", 
        ["해외주식 (US Custom)", "국내주식 (KRX)", "환율 (Forex)", "암호화폐 (Crypto)"], 
        index=0
    )

    if category == "해외주식 (US Custom)":
        STOCKS = get_us_stocks()
        currency_symbol = "USD"
    elif category == "국내주식 (KRX)":
        STOCKS = get_krx_stocks()
        currency_symbol = "원"
    elif category == "환율 (Forex)":
        STOCKS = get_forex()
        currency_symbol = "원"
    else:
        STOCKS = get_crypto()
        currency_symbol = "USD"

    selected_name = st.sidebar.selectbox("🔎 종목/자산 선택", options=list(STOCKS.keys()), index=0)
    selected_code = STOCKS[selected_name]
else:
    direct_ticker = st.sidebar.text_input("📝 티커 직접 입력 (예: NVDA, 005930, BTC/USD, USD/KRW)", value="NVDA").strip()
    selected_name = f"Custom: {direct_ticker}"
    selected_code = direct_ticker
    category = "직접입력"
    currency_symbol = "원" if (direct_ticker.isdigit() or "KRW" in direct_ticker) else "USD"

timeframe = st.sidebar.radio("📊 차트 주기 (봉 단위)", ["일봉", "주봉", "월봉"], index=0)

period_options = {
    "1달": 30,
    "6개월": 180,
    "1년": 365,
    "3년": 365 * 3,
    "5년": 365 * 5,
    "10년": 365 * 10
}
selected_period = st.sidebar.select_slider("📅 조회 기간", options=list(period_options.keys()), value="1년")

st.sidebar.markdown("---")
st.sidebar.subheader("📐 보조지표 표시")
show_ma = st.sidebar.checkbox("이동평균선 (20/50/100/200)", value=True)
show_bb = st.sidebar.checkbox("볼린저 밴드 (20, 2)", value=False)
show_rsi = st.sidebar.checkbox("RSI (14)", value=True)
show_macd = st.sidebar.checkbox("MACD (12, 26, 9)", value=True)

# 날짜 계산
today = datetime.date.today()
display_start_date = today - datetime.timedelta(days=period_options[selected_period])
fetch_start_date = display_start_date - datetime.timedelta(days=400)

# ==================== 데이터 및 지표 계산 함수 ====================
@st.cache_data(ttl=10)
def load_and_calculate_data(code, start_date, tf):
    df = fdr.DataReader(code, start_date)
    if df is None or df.empty:
        return df
    if 'Volume' not in df.columns:
        df['Volume'] = 0
        
    if tf == "주봉":
        df = df.resample('W').agg({
            'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
        }).dropna()
    elif tf == "월봉":
        df = df.resample('ME').agg({
            'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
        }).dropna()
        
    # 이동평균선
    df['20선'] = df['Close'].rolling(20).mean()
    df['50선'] = df['Close'].rolling(50).mean()
    df['100선'] = df['Close'].rolling(100).mean()
    df['200선'] = df['Close'].rolling(200).mean()

    # 볼린저 밴드
    std20 = df['Close'].rolling(20).std()
    df['BB_Upper'] = df['20선'] + (std20 * 2)
    df['BB_Lower'] = df['20선'] - (std20 * 2)

    # RSI (14)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    # MACD
    exp12 = df['Close'].ewm(span=12, adjust=False).mean()
    exp26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp12 - exp26
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']

    return df

try:
    df = load_and_calculate_data(selected_code, fetch_start_date, timeframe)
    
    if df is None or df.empty:
        st.error(f"티커 '{selected_code}'의 데이터를 가져올 수 없습니다. 올바른 티커인지 확인해 주세요.")
    else:
        display_df = df.loc[df.index >= pd.to_datetime(display_start_date)]
        
        # 최신 가격 및 전일 대비 변동 계산
        latest_close = float(display_df['Close'].iloc[-1])
        prev_close = float(display_df['Close'].iloc[-2]) if len(display_df) > 1 else latest_close
        price_chg = latest_close - prev_close
        price_chg_pct = (price_chg / prev_close) * 100

        # 가격 포맷팅
        if currency_symbol == "USD":
            formatted_close = f"{latest_close:,.2f}" if latest_close >= 1 else f"{latest_close:.4f}"
            delta_str = f"{price_chg:+,.2f} ({price_chg_pct:+.2f}%)"
        else:
            formatted_close = f"{int(latest_close):,}" if category == "국내주식 (KRX)" else f"{latest_close:,.2f}"
            delta_str = f"{int(price_chg):+,} ({price_chg_pct:+.2f}%)" if category == "국내주식 (KRX)" else f"{price_chg:+,.2f} ({price_chg_pct:+.2f}%)"

        # ==================== 상단 대시보드 메트릭 카드 ====================
        st.markdown("### 📌 시장 핵심 요약")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("선택 종목/자산", selected_name.split(' - ')[0])
        m2.metric("현재 시세", f"{formatted_close} {currency_symbol}", delta=delta_str)

        # 52주 고점/저점 및 통계
        one_year_df = df.loc[df.index >= (pd.to_datetime(today) - pd.Timedelta(days=365))]
        if not one_year_df.empty:
            high_52w = one_year_df['High'].max()
            low_52w = one_year_df['Low'].min()
            drop_from_high = ((latest_close - high_52w) / high_52w) * 100
            
            # MDD (최대 낙폭) 계산
            cummax = display_df['Close'].cummax()
            drawdown = (display_df['Close'] - cummax) / cummax
            mdd = drawdown.min() * 100

            m3.metric("52주 최고 / 최저", f"{high_52w:,.0f} / {low_52w:,.0f}" if currency_symbol=="원" else f"{high_52w:,.2f} / {low_52w:,.2f}", f"고점대비 {drop_from_high:+.1f}%")
            m4.metric("기간 내 MDD (최대 낙폭)", f"{mdd:.2f}%", delta_color="inverse")
        else:
            m3.metric("52주 고/저", "-")
            m4.metric("MDD", "-")

        # ==================== 기술적 신호 진단 배지 ====================
        st.markdown("---")
        st.markdown("#### 🚦 기술적 지표 자동 진단 시그널")
        sig_col1, sig_col2, sig_col3, sig_col4 = st.columns(4)

        # 1. 이동평균 배열 (골든/데드)
        latest_ma20 = display_df['20선'].iloc[-1]
        latest_ma50 = display_df['50선'].iloc[-1]
        if pd.notna(latest_ma20) and pd.notna(latest_ma50):
            if latest_ma20 > latest_ma50:
                sig_col1.markdown("이평선 추세: <span class='signal-badge-bull'>골든크로스 구간 (정배열)</span>", unsafe_allow_html=True)
            else:
                sig_col1.markdown("이평선 추세: <span class='signal-badge-bear'>데드크로스 구간 (역배열)</span>", unsafe_allow_html=True)
        else:
            sig_col1.markdown("이평선 추세: <span class='signal-badge-neutral'>데이터 부족</span>", unsafe_allow_html=True)

        # 2. RSI 진단
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

        # 3. 볼린저 밴드 위치
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

        # 4. MACD 히스토그램
        latest_macd_hist = display_df['MACD_Hist'].iloc[-1]
        if pd.notna(latest_macd_hist):
            if latest_macd_hist > 0:
                sig_col4.markdown(f"MACD Hist: <span class='signal-badge-bull'>상승 모멘텀 (+{latest_macd_hist:.2f})</span>", unsafe_allow_html=True)
            else:
                sig_col4.markdown(f"MACD Hist: <span class='signal-badge-bear'>하락 모멘텀 ({latest_macd_hist:.2f})</span>", unsafe_allow_html=True)
        else:
            sig_col4.markdown("MACD Hist: -", unsafe_allow_html=True)

        # ==================== 탭 분기 (메인 차트 / 상대 수익률 비교) ====================
        st.markdown("---")
        tab1, tab2 = st.tabs(["📊 인터랙티브 종합 차트", "📈 벤치마크 상대 수익률(%) 비교"])

        with tab1:
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

            # 캔들스틱 차트
            fig.add_trace(
                go.Candlestick(
                    x=display_df.index,
                    open=display_df['Open'], high=display_df['High'],
                    low=display_df['Low'], close=display_df['Close'],
                    name='시세', increasing_line_color='#26A69A', decreasing_line_color='#EF5350'
                ),
                row=current_row, col=1
            )

            # 이동평균선
            if show_ma:
                ma_colors = {'20선': '#FF9800', '50선': '#AB47BC', '100선': '#29B6F6', '200선': '#B0BEC5'}
                for ma_name, color in ma_colors.items():
                    if ma_name in display_df.columns:
                        fig.add_trace(
                            go.Scatter(x=display_df.index, y=display_df[ma_name], mode='lines', name=ma_name, line=dict(color=color, width=1.2)),
                            row=current_row, col=1
                        )

            # 볼린저 밴드
            if show_bb:
                fig.add_trace(
                    go.Scatter(x=display_df.index, y=display_df['BB_Upper'], mode='lines', name='볼린저 상단', line=dict(color='rgba(200, 200, 200, 0.6)', dash='dot')),
                    row=current_row, col=1
                )
                fig.add_trace(
                    go.Scatter(x=display_df.index, y=display_df['BB_Lower'], mode='lines', name='볼린저 하단', line=dict(color='rgba(200, 200, 200, 0.6)', dash='dot'), fill='tonexty', fillcolor='rgba(255, 255, 255, 0.05)'),
                    row=current_row, col=1
                )

            # 거래량
            if has_vol:
                current_row += 1
                vol_colors = ['#26A69A' if row['Close'] >= row['Open'] else '#EF5350' for _, row in display_df.iterrows()]
                fig.add_trace(
                    go.Bar(x=display_df.index, y=display_df['Volume'], name='거래량', marker_color=vol_colors),
                    row=current_row, col=1
                )

            # MACD 서브플롯
            if show_macd:
                current_row += 1
                fig.add_trace(
                    go.Scatter(x=display_df.index, y=display_df['MACD'], mode='lines', name='MACD', line=dict(color='#29B6F6', width=1.3)),
                    row=current_row, col=1
                )
                fig.add_trace(
                    go.Scatter(x=display_df.index, y=display_df['MACD_Signal'], mode='lines', name='Signal', line=dict(color='#FF7043', width=1.3)),
                    row=current_row, col=1
                )
                hist_colors = ['#26A69A' if v >= 0 else '#EF5350' for v in display_df['MACD_Hist']]
                fig.add_trace(
                    go.Bar(x=display_df.index, y=display_df['MACD_Hist'], name='MACD Hist', marker_color=hist_colors),
                    row=current_row, col=1
                )

            # RSI 서브플롯
            if show_rsi:
                current_row += 1
                fig.add_trace(
                    go.Scatter(x=display_df.index, y=display_df['RSI'], mode='lines', name='RSI(14)', line=dict(color='#AB47BC', width=1.5)),
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
            st.plotly_chart(fig, use_container_width=True)

        with tab2:
            st.markdown("#### 📊 타 자산 및 주요 지수와의 누적 수익률(%) 비교")
            comp_targets = {
                "S&P 500 지수 (미국 대형주)": "US500",
                "나스닥 100 지수 (기술주)": "IXIC",
                "KOSPI 지수 (국내 종합)": "KS11",
                "비트코인 (BTC/USD)": "BTC/USD",
                "원/달러 환율 (USD/KRW)": "USD/KRW",
                "테슬라 (TSLA)": "TSLA",
                "엔비디아 (NVDA)": "NVDA"
            }
            selected_comp = st.selectbox("비교할 대상 자산/지수 선택", options=list(comp_targets.keys()), index=0)
            comp_code = comp_targets[selected_comp]
            
            try:
                comp_df = fdr.DataReader(comp_code, display_start_date)
                if not comp_df.empty:
                    # 수익률(%) 정규화 (시작일 = 0%)
                    base_main = display_df['Close'] / display_df['Close'].iloc[0] * 100 - 100
                    base_comp = comp_df['Close'] / comp_df['Close'].iloc[0] * 100 - 100

                    comp_fig = go.Figure()
                    comp_fig.add_trace(go.Scatter(x=base_main.index, y=base_main, mode='lines', name=f"기준: {selected_name.split(' - ')[0]}", line=dict(color='#29B6F6', width=2)))
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

except Exception as e:
    st.error(f"데이터 조회 중 예기치 않은 오류가 발생했습니다: {e}")
