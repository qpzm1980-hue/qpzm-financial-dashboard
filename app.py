import datetime
import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="글로벌 종합 금융 차트 대시보드", layout="wide")

st.title("📊 글로벌 종합 금융 차트 대시보드")

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
        "SNDK - Sandisk / Western Digital": "WDC",
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

# 사이드바 설정
category = st.sidebar.radio(
    "🌐 자산 카테고리 선택", 
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

selected_name = st.sidebar.selectbox("🔎 종목/자산 선택 (검색 가능)", options=list(STOCKS.keys()), index=0)
selected_code = STOCKS[selected_name]

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

today = datetime.date.today()
display_start_date = today - datetime.timedelta(days=period_options[selected_period])
fetch_start_date = display_start_date - datetime.timedelta(days=350)

@st.cache_data
def load_data(code, start_date, tf):
    df = fdr.DataReader(code, start_date)
    if df.empty:
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
        
    df['20선'] = df['Close'].rolling(20).mean()
    df['50선'] = df['Close'].rolling(50).mean()
    df['100선'] = df['Close'].rolling(100).mean()
    df['200선'] = df['Close'].rolling(200).mean()
    return df

try:
    df = load_data(selected_code, fetch_start_date, timeframe)
    display_df = df.loc[df.index >= pd.to_datetime(display_start_date)]
    
    if display_df.empty:
        st.warning("선택한 기간의 데이터가 존재하지 않습니다.")
    else:
        latest_close = float(display_df['Close'].iloc[-1])
        if currency_symbol == "USD":
            formatted_close = f"{latest_close:,.2f}" if latest_close >= 1 else f"{latest_close:.4f}"
        else:
            formatted_close = f"{int(latest_close):,}" if category == "국내주식 (KRX)" else f"{latest_close:,.2f}"

        col1, col2 = st.columns(2)
        col1.metric("선택 자산", f"{selected_name}")
        col2.metric("최신 시세", f"{formatted_close} {currency_symbol}")

        st.subheader(f"[{selected_name}] 최근 {selected_period} ({timeframe}) 차트")

        has_vol = bool(display_df['Volume'].sum() > 0)
        if has_vol:
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.75, 0.25])
        else:
            fig = make_subplots(rows=1, cols=1)

        fig.add_trace(
            go.Candlestick(
                x=display_df.index,
                open=display_df['Open'], high=display_df['High'],
                low=display_df['Low'], close=display_df['Close'],
                name='시세', increasing_line_color='red', decreasing_line_color='blue'
            ),
            row=1, col=1
        )

        ma_colors = {'20선': 'orange', '50선': 'purple', '100선': 'green', '200선': 'gray'}
        for ma_name, color in ma_colors.items():
            if ma_name in display_df.columns:
                fig.add_trace(
                    go.Scatter(x=display_df.index, y=display_df[ma_name], mode='lines', name=ma_name, line=dict(color=color, width=1.2)),
                    row=1, col=1
                )

        if has_vol:
            colors = ['red' if row['Close'] >= row['Open'] else 'blue' for _, row in display_df.iterrows()]
            fig.add_trace(
                go.Bar(x=display_df.index, y=display_df['Volume'], name='거래량', marker_color=colors),
                row=2, col=1
            )

        fig.update_layout(height=650, xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=10, b=10), hovermode='x unified')
        st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error(f"데이터 조회 중 오류: {e}")
