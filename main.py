import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# --------------------------------------------------
# 페이지 기본 설정
# --------------------------------------------------

st.set_page_config(
    page_title="KOBIS 박스오피스",
    page_icon="🎬",
    layout="wide"
)


# --------------------------------------------------
# KOBIS API 주소
# --------------------------------------------------

API_URL = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
    "boxoffice/searchDailyBoxOfficeList.json"
)


# --------------------------------------------------
# 한국 시간 기준 날짜 설정
# --------------------------------------------------

korea_time = datetime.now(ZoneInfo("Asia/Seoul"))

today = korea_time.date()
yesterday = today - timedelta(days=1)


# --------------------------------------------------
# 제목
# --------------------------------------------------

st.title("🎬 KOBIS 일일 박스오피스")
st.write("영화진흥위원회 KOBIS 데이터를 이용한 일일 박스오피스 조회")


# --------------------------------------------------
# KOBIS API 인증키 가져오기
# --------------------------------------------------

try:
    api_key = st.secrets["KOBIS_KEY"]

except KeyError:
    st.error("🔑 KOBIS 인증키를 찾을 수 없습니다.")
    st.info(
        "Streamlit Cloud의 Secrets에 "
        "`KOBIS_KEY`라는 이름으로 인증키를 등록했는지 확인해 주세요."
    )
    st.stop()


# --------------------------------------------------
# 날짜 선택
# 오늘은 아직 집계가 끝나지 않았으므로
# 어제까지만 선택할 수 있도록 설정
# --------------------------------------------------

selected_date = st.date_input(
    "📅 조회 날짜를 선택하세요",
    value=yesterday,
    max_value=yesterday
)

# KOBIS API에 사용할 날짜 형식
target_date = selected_date.strftime("%Y%m%d")

# 화면에 표시할 날짜 형식
display_date = selected_date.strftime("%Y년 %m월 %d일")


# --------------------------------------------------
# API 데이터 가져오기
# 같은 날짜의 데이터는 1시간 동안 캐시
# --------------------------------------------------

@st.cache_data(ttl=3600)
def get_boxoffice(target_date, api_key):

    params = {
        "key": api_key,
        "targetDt": target_date
    }

    response = requests.get(
        API_URL,
        params=params,
        timeout=10
    )

    # HTTP 오류가 발생하면 예외 발생
    response.raise_for_status()

    return response.json()


# --------------------------------------------------
# API 호출
# --------------------------------------------------

try:

    data = get_boxoffice(
        target_date,
        api_key
    )

except requests.exceptions.Timeout:

    st.error("⏰ KOBIS 서버 응답 시간이 초과되었습니다.")
    st.info("잠시 후 다시 시도해 주세요.")
    st.stop()

except requests.exceptions.RequestException:

    st.error("❌ KOBIS API 요청에 실패했습니다.")
    st.info("인터넷 연결이나 KOBIS API 상태를 확인해 주세요.")
    st.stop()

except Exception:

    st.error("❌ 데이터를 불러오는 중 오류가 발생했습니다.")
    st.info("잠시 후 다시 시도해 주세요.")
    st.stop()


# --------------------------------------------------
# KOBIS API에서 오류 정보가 반환되었는지 확인
# --------------------------------------------------

if "faultInfo" in data:

    fault_info = data["faultInfo"]

    st.error("❌ KOBIS API에서 오류가 발생했습니다.")

    if isinstance(fault_info, dict):

        error_message = fault_info.get(
            "message",
            "알 수 없는 오류입니다."
        )

        st.info(f"오류 내용: {error_message}")

    else:

        st.info("KOBIS API 인증키나 요청 날짜를 확인해 주세요.")

    st.stop()


# --------------------------------------------------
# 박스오피스 결과 확인
# --------------------------------------------------

boxoffice_result = data.get("boxOfficeResult")

if not boxoffice_result:

    st.error("❌ 박스오피스 데이터를 찾을 수 없습니다.")
    st.info("선택한 날짜의 데이터를 확인해 주세요.")
    st.stop()


# --------------------------------------------------
# 영화 목록 가져오기
# --------------------------------------------------

movie_list = boxoffice_result.get(
    "dailyBoxOfficeList",
    []
)


# --------------------------------------------------
# 영화 데이터가 없는 경우
# --------------------------------------------------

if not movie_list:

    st.warning("📭 그날은 아직 집계 전입니다.")
    st.info(
        "다른 날짜를 선택해 주세요. "
        "오늘 날짜는 아직 박스오피스가 집계되지 않아 선택할 수 없습니다."
    )
    st.stop()


# --------------------------------------------------
# DataFrame으로 변환
# --------------------------------------------------

df = pd.DataFrame(movie_list)


# --------------------------------------------------
# 숫자로 변환할 컬럼
# API에서는 숫자가 문자열로 들어오기 때문에
# 그래프와 정렬을 위해 숫자형으로 변환
# --------------------------------------------------

numeric_columns = [
    "rank",
    "rankInten",
    "audiCnt",
    "audiAcc",
    "scrnCnt",
    "showCnt"
]

for column in numeric_columns:

    if column in df.columns:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )


# --------------------------------------------------
# 순위 기준으로 정렬
# --------------------------------------------------

df = df.sort_values(
    "rank"
).reset_index(drop=True)


# --------------------------------------------------
# 누적 관객수가 100만 명을 넘은 영화에는
# 트로피 이모지를 붙임
# --------------------------------------------------

df["영화명표시"] = df.apply(

    lambda row:
        f"{row['movieNm']} 🏆"
        if row["audiAcc"] > 1_000_000
        else row["movieNm"],

    axis=1
)


# --------------------------------------------------
# 순위 변동 표시
#
# 양수 → 순위 상승 → 빨간색 위쪽 화살표
# 음수 → 순위 하락 → 파란색 아래쪽 화살표
# 0 → 변동 없음
# --------------------------------------------------

def make_rank_change(value):

    if pd.isna(value):
        return "-"

    value = int(value)

    if value > 0:
        return f"⬆ {value}"

    elif value < 0:
        return f"⬇ {abs(value)}"

    else:
        return "—"


df["순위변동"] = df["rankInten"].apply(
    make_rank_change
)


# --------------------------------------------------
# 선택한 날짜 제목
# --------------------------------------------------

st.header(f"📊 {display_date} 박스오피스")


# --------------------------------------------------
# 1위 영화 정보
# --------------------------------------------------

first_movie = df.iloc[0]


st.markdown(
    f"## 🥇 {first_movie['영화명표시']}"
)


# --------------------------------------------------
# 1위 영화 주요 정보 3개 카드
# --------------------------------------------------

col1, col2, col3 = st.columns(3)


with col1:

    st.metric(
        "관객수",
        f"{int(first_movie['audiCnt']):,}명"
    )


with col2:

    st.metric(
        "누적관객",
        f"{int(first_movie['audiAcc']):,}명"
    )


with col3:

    st.metric(
        "스크린수",
        f"{int(first_movie['scrnCnt']):,}개"
    )


# --------------------------------------------------
# 전체 박스오피스 표
# --------------------------------------------------

st.subheader("🎞️ 전체 순위")


table_df = df[
    [
        "rank",
        "순위변동",
        "영화명표시",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt"
    ]
].copy()


# --------------------------------------------------
# 컬럼 이름 변경
# --------------------------------------------------

table_df.columns = [
    "순위",
    "순위 변동",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수"
]


# --------------------------------------------------
# 숫자에 천 단위 콤마와 단위 표시
# --------------------------------------------------

table_df["관객수"] = table_df["관객수"].apply(
    lambda x: f"{int(x):,}명"
)

table_df["누적관객"] = table_df["누적관객"].apply(
    lambda x: f"{int(x):,}명"
)

table_df["스크린수"] = table_df["스크린수"].apply(
    lambda x: f"{int(x):,}개"
)


# --------------------------------------------------
# 순위 변동 색상 설정
# 상승 → 빨간색
# 하락 → 파란색
# --------------------------------------------------

def color_rank_change(value):

    if str(value).startswith("⬆"):

        return "color: red; font-weight: bold"

    elif str(value).startswith("⬇"):

        return "color: blue; font-weight: bold"

    else:

        return ""


styled_table = table_df.style.map(
    color_rank_change,
    subset=["순위 변동"]
)


# --------------------------------------------------
# 표 출력
# --------------------------------------------------

st.dataframe(
    styled_table,
    use_container_width=True,
    hide_index=True
)


# --------------------------------------------------
# 관객수 기준 TOP 5
# --------------------------------------------------

st.subheader("📈 관객수 TOP 5")


top5 = (
    df
    .sort_values(
        "audiCnt",
        ascending=False
    )
    .head(5)
    .copy()
)


# --------------------------------------------------
# 그래프용 데이터 생성
# --------------------------------------------------

chart_data = top5[
    [
        "영화명표시",
        "audiCnt"
    ]
].copy()


chart_data = chart_data.set_index(
    "영화명표시"
)


# --------------------------------------------------
# 막대그래프 출력
# --------------------------------------------------

st.bar_chart(
    chart_data,
    x_label="영화명",
    y_label="관객수"
)


# --------------------------------------------------
# 하단 안내
# --------------------------------------------------

st.caption(
    "※ 데이터 출처: 영화진흥위원회 KOBIS"
)
