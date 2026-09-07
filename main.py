import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# ------------------------------
# 기본 설정
# ------------------------------
st.set_page_config(page_title="학교 중식 메뉴 분석", layout="wide")

# Streamlit Cloud Secrets에서 API 키 불러오기
try:
    API_KEY = st.secrets["NEIS_API_KEY"]
except Exception:
    st.error("⚠️ API 키가 설정되지 않았습니다. Streamlit Cloud의 Secrets 또는 로컬 .streamlit/secrets.toml 파일을 확인해주세요.")
    st.stop()

BASE_URL = "https://open.neis.go.kr/hub/mealServiceDietInfo"

# 학교 정보 (지역코드, 학교코드, 학교명)
SCHOOL_LIST = {
    "당곡고등학교": {"ATPT_OFCDC_SC_CODE": "B10", "SD_SCHUL_CODE": "7010073"},
    "구암고등학교": {"ATPT_OFCDC_SC_CODE": "B10", "SD_SCHUL_CODE": "7011111"},
    "서울공업고등학교": {"ATPT_OFCDC_SC_CODE": "B10", "SD_SCHUL_CODE": "7010278"},
    "성보고등학교": {"ATPT_OFCDC_SC_CODE": "B10", "SD_SCHUL_CODE": "7010194"},
}

# 연도별 유행 메뉴 키워드 (직접 조사해서 업데이트하는 부분)
TREND_KEYWORDS_BY_YEAR = {
    2023: ["마라탕", "탕후루", "흑당", "요아정", "크로플", "마라샹궈"],
    2024: ["두바이초콜릿", "요아정", "마라탕후루", "약과", "탕후루", "말차"],
    2025: ["요아정", "두바이초콜릿", "마라탕", "흑당", "탕후루"],
}
ALL_TREND_KEYWORDS = sorted(set(sum(TREND_KEYWORDS_BY_YEAR.values(), [])))

ECO_KEYWORDS = ["친환경", "유기농", "무항생제", "동물복지", "저탄소"]
VEGAN_KEYWORDS = ["채식", "비건", "샐러드바", "두부스테이크", "콩고기", "베지"]


# ------------------------------
# 급식 데이터 가져오기 함수 (중식만 필터링)
# ------------------------------
@st.cache_data(show_spinner=True)
def get_lunch_data(office_code, school_code, start_date, end_date):
    params = {
        "KEY": API_KEY,
        "Type": "json",
        "ATPT_OFCDC_SC_CODE": office_code,
        "SD_SCHUL_CODE": school_code,
        "MLSV_FROM_YMD": start_date,
        "MLSV_TO_YMD": end_date,
        "pSize": 1000,
    }
    try:
        res = requests.get(BASE_URL, params=params, timeout=10)
        data = res.json()

        first_key = data.get("mealServiceDietInfo", [{}])[0]
        if "RESULT" in first_key:
            return pd.DataFrame(), first_key["RESULT"].get("MESSAGE", "데이터 없음")

        if "mealServiceDietInfo" not in data:
            return pd.DataFrame(), "예상치 못한 응답 형식"

        rows = data["mealServiceDietInfo"][1]["row"]
        df = pd.DataFrame(rows)

        if "MMEAL_SC_CODE" in df.columns:
            df = df[df["MMEAL_SC_CODE"] == "2"]  # 중식만

        if df.empty:
            return pd.DataFrame(), "중식 데이터 없음"

        df = df[["MLSV_YMD", "DDISH_NM"]]
        df.columns = ["날짜", "메뉴"]

        df["메뉴"] = df["메뉴"].str.replace("<br/>", " ", regex=False)
        df["메뉴"] = df["메뉴"].str.replace(r"\d+\.", "", regex=True)
        df["메뉴"] = df["메뉴"].str.replace(r"\([^)]*\)", "", regex=True)
        return df.reset_index(drop=True), None
    except Exception as e:
        return pd.DataFrame(), f"오류 발생: {e}"


def count_keyword_hits(df, keywords):
    """중식 메뉴 중 키워드가 등장한 날짜 수 계산"""
    if df.empty:
        return 0, []
    hit_dates = []
    for _, row in df.iterrows():
        for kw in keywords:
            if kw in row["메뉴"]:
                hit_dates.append(row["날짜"])
                break
    return len(hit_dates), hit_dates


# ==============================================================
# 섹션 1: 오늘(당일) 중식 메뉴 비교 - 앱 접속 시 가장 먼저 표시
# ==============================================================
st.title("🍱 학교 중식 메뉴 분석 대시보드")

st.header("📅 오늘의 중식 메뉴 비교")

today_str = datetime.today().strftime("%Y%m%d")
today_display = datetime.today().strftime("%Y년 %m월 %d일")
st.caption(f"기준 날짜: {today_display}")

today_schools = st.multiselect(
    "오늘 급식을 비교할 학교를 선택하세요 (3개 이상 권장)",
    options=list(SCHOOL_LIST.keys()),
    default=["당곡고등학교", "구암고등학교", "서울공업고등학교"],
    key="today_select"
)

if today_schools:
    cols = st.columns(len(today_schools))
    for idx, school in enumerate(today_schools):
        info = SCHOOL_LIST[school]
        df_today, msg = get_lunch_data(
            info["ATPT_OFCDC_SC_CODE"], info["SD_SCHUL_CODE"], today_str, today_str
        )
        with cols[idx]:
            st.subheader(school)
            if df_today.empty:
                st.info(f"오늘은 급식 정보가 없습니다.\n({msg})")
            else:
                menu_text = df_today.iloc[0]["메뉴"]
                menu_items = [m.strip() for m in menu_text.split(" ") if m.strip()]
                for item in menu_items:
                    st.write(f"- {item}")

                is_trend = any(kw in menu_text for kw in ALL_TREND_KEYWORDS)
                is_eco = any(kw in menu_text for kw in ECO_KEYWORDS)
                is_vegan = any(kw in menu_text for kw in VEGAN_KEYWORDS)

                badges = []
                if is_trend:
                    badges.append("🔥 유행메뉴")
                if is_eco:
                    badges.append("🌿 친환경")
                if is_vegan:
                    badges.append("🥦 채식")

                if badges:
                    st.success(" / ".join(badges))
else:
    st.info("비교할 학교를 선택해주세요.")

st.markdown("---")


# ==============================================================
# 섹션 2: 기간 선택 후 종합 분석 (유행/친환경/채식 비율 비교)
# ==============================================================
st.header("📊 기간별 종합 분석")
st.markdown("""
선택한 기간 동안의 **중식 데이터**를 기준으로
1) **유행 메뉴 반영 정도**
2) **친환경 식재료 및 채식 선택권 보장 정도**  
를 비교 분석합니다.
""")

with st.expander("🔧 분석 조건 설정 (펼쳐서 확인)", expanded=True):
    period_schools = st.multiselect(
        "비교할 학교를 선택하세요 (3개 이상 권장)",
        options=list(SCHOOL_LIST.keys()),
        default=["당곡고등학교", "구암고등학교", "서울공업고등학교"],
        key="period_select"
    )

    if len(period_schools) < 3:
        st.warning("3개 이상의 학교를 선택해주세요.")

    col_a, col_b = st.columns(2)
    with col_a:
        start_date = st.date_input("시작 날짜", datetime.today() - timedelta(days=90))
    with col_b:
        end_date = st.date_input("종료 날짜", datetime.today())

    st.subheader("🔥 유행 키워드 직접 수정하기")
    st.caption("SNS·뉴스에서 최근 유행하는 음식을 찾아 아래에 추가해보세요!")
    custom_keywords_input = st.text_area(
        "쉼표(,)로 구분해서 입력",
        value=", ".join(ALL_TREND_KEYWORDS)
    )
    custom_keywords = [kw.strip() for kw in custom_keywords_input.split(",") if kw.strip()]

start_str = start_date.strftime("%Y%m%d")
end_str = end_date.strftime("%Y%m%d")

if period_schools:
    result_rows = []
    all_meal_data = {}

    with st.spinner("중식 급식 데이터를 불러오는 중입니다..."):
        for school in period_schools:
            info = SCHOOL_LIST[school]
            df, msg = get_lunch_data(info["ATPT_OFCDC_SC_CODE"], info["SD_SCHUL_CODE"], start_str, end_str)
            all_meal_data[school] = df

            total_days = len(df)
            trend_count, _ = count_keyword_hits(df, custom_keywords)
            eco_count, _ = count_keyword_hits(df, ECO_KEYWORDS)
            vegan_count, _ = count_keyword_hits(df, VEGAN_KEYWORDS)

            result_rows.append({
                "학교명": school,
                "전체 중식일수": total_days,
                "유행메뉴 등장일수": trend_count,
                "유행메뉴 비율(%)": round(trend_count / total_days * 100, 1) if total_days else 0,
                "친환경 식재료 등장일수": eco_count,
                "친환경 비율(%)": round(eco_count / total_days * 100, 1) if total_days else 0,
                "채식메뉴 등장일수": vegan_count,
                "채식메뉴 비율(%)": round(vegan_count / total_days * 100, 1) if total_days else 0,
            })

    result_df = pd.DataFrame(result_rows)

    if result_df.empty or result_df["전체 중식일수"].sum() == 0:
        st.warning("해당 기간에 중식 데이터가 없습니다. 날짜 범위를 조정하거나 API 키를 확인해주세요.")
    else:
        st.subheader("📋 학교별 중식 요약 데이터")
        st.dataframe(result_df, use_container_width=True)

        st.subheader("🔥 유행 메뉴 반영 비율 비교 (중식 기준)")
        fig1 = px.bar(
            result_df, x="학교명", y="유행메뉴 비율(%)", color="학교명",
            text="유행메뉴 비율(%)", title="학교별 중식 유행 메뉴 등장 비율 (%)"
        )
        fig1.update_traces(texttemplate='%{text}%', textposition='outside')
        st.plotly_chart(fig1, use_container_width=True)

        st.subheader("🌱 친환경 식재료 및 채식 선택권 비교 (중식 기준)")
        eco_vegan_df = result_df.melt(
            id_vars="학교명",
            value_vars=["친환경 비율(%)", "채식메뉴 비율(%)"],
            var_name="구분", value_name="비율(%)"
        )
        fig2 = px.bar(
            eco_vegan_df, x="학교명", y="비율(%)", color="구분",
            barmode="group", text="비율(%)",
            title="학교별 중식 친환경 및 채식 메뉴 제공 비율"
        )
        fig2.update_traces(texttemplate='%{text}%', textposition='outside')
        st.plotly_chart(fig2, use_container_width=True)

        st.subheader("🕸️ 종합 비교 (레이더 차트)")
        categories = ["유행메뉴 비율(%)", "친환경 비율(%)", "채식메뉴 비율(%)"]
        fig3 = go.Figure()
        for _, row in result_df.iterrows():
            fig3.add_trace(go.Scatterpolar(
                r=[row[c] for c in categories], theta=categories,
                fill='toself', name=row["학교명"]
            ))
        fig3.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, max(result_df[categories].max()) + 5])),
            showlegend=True, title="학교별 종합 비교 레이더 차트 (중식 기준)"
        )
        st.plotly_chart(fig3, use_container_width=True)

        st.subheader("🔍 학교별 상세 중식 메뉴 확인")
        check_school = st.selectbox("확인할 학교를 선택하세요", period_schools, key="detail_select")
        if not all_meal_data[check_school].empty:
            st.dataframe(all_meal_data[check_school], use_container_width=True, height=400)
        else:
            st.info("해당 학교의 데이터가 없습니다.")
else:
    st.info("비교할 학교를 3개 이상 선택해주세요.")


# ------------------------------
# 하단 안내
# ------------------------------
st.markdown("---")
st.caption("""
📌 **분석 기준 안내**  
- 분석 대상: **중식(점심)** 메뉴만 사용  
- 유행 메뉴 키워드: 직접 수정 가능 (SNS/뉴스 검색 후 업데이트 권장)  
- 친환경 키워드: 친환경, 유기농, 무항생제, 동물복지 등  
- 채식 키워드: 채식, 비건, 샐러드바, 두부스테이크 등  
- 본 분석은 급식 식단표에 표기된 텍스트만을 기준으로 합니다.
""")
