
import streamlit as st
import pandas as pd
import requests

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# ----------------------------------------
# 1. 페이지 설정
# ----------------------------------------

st.set_page_config(
    page_title="KOBIS 박스오피스",
    page_icon="🎬",
    layout="wide"
)


# ----------------------------------------
# 2. KOBIS API 주소
# ----------------------------------------

API_URL = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
    "boxoffice/searchDailyBoxOfficeList.json"
)


# ----------------------------------------
# 3. 한국 시간 기준 날짜 계산
# ----------------------------------------
# 서버가 한국 시간이 아닐 수 있으므로
# 반드시 한국 시간(Asia/Seoul)을 사용한다.

korea_time = datetime.now(ZoneInfo("Asia/Seoul"))

today = korea_time.date()
yesterday = today - timedelta(days=1)


# ----------------------------------------
# 4. KOBIS API 호출 함수
# ----------------------------------------
# 선택한 날짜별로 결과를 1시간 동안 캐시한다.
# 따라서 같은 날짜를 다시 선택해도
# 1시간 이내에는 API를 다시 호출하지 않는다.

@st.cache_data(ttl=3600)
def get_boxoffice(target_date, api_key):
    """선택한 날짜의 KOBIS 일일 박스오피스 데이터를 가져온다."""

    params = {
        "key": api_key,
        "targetDt": target_date
    }

    response = requests.get(
        API_URL,
        params=params,
        timeout=10
    )

    # HTTP 오류가 있으면 오류 발생
    response.raise_for_status()

    # JSON 데이터로 변환
    return response.json()


# ----------------------------------------
# 5. Secrets에서 인증키 가져오기
# ----------------------------------------

try:
    api_key = st.secrets["KOBIS_KEY"]

except KeyError:
    st.error("🔑 KOBIS 인증키를 찾을 수 없습니다.")

    st.info(
        "Streamlit Cloud의 Secrets에 "
        "KOBIS_KEY라는 이름으로 인증키를 등록했는지 확인해 주세요."
    )

    st.stop()


# ----------------------------------------
# 6. 제목
# ----------------------------------------

st.title("🎬 KOBIS 일일 박스오피스")

st.write(
    "조회할 날짜를 선택하면 해당 날짜의 박스오피스를 확인할 수 있습니다."
)


# ----------------------------------------
# 7. 날짜 선택
# ----------------------------------------
# 오늘은 아직 집계 전이므로
# 선택 가능한 가장 늦은 날짜를 어제로 설정한다.

selected_date = st.date_input(
    "📅 조회 날짜",
    value=yesterday,
    min_value=None,
    max_value=yesterday
)


# ----------------------------------------
# 8. 선택한 날짜를 KOBIS 형식으로 변환
# ----------------------------------------

target_date = selected_date.strftime("%Y%m%d")

display_date = selected_date.strftime(
    "%Y년 %m월 %d일"
)


# ----------------------------------------
# 9. API 요청
# ----------------------------------------

try:
    data = get_boxoffice(
        target_date,
        api_key
    )

except requests.exceptions.Timeout:
    st.error("⏱️ KOBIS API 요청 시간이 초과되었습니다.")

    st.info(
        "잠시 후 다시 시도하거나 인터넷 연결 상태와 "
        "KOBIS API 서버 상태를 확인해 주세요."
    )

    st.stop()

except requests.exceptions.RequestException as e:
    st.error("🌐 KOBIS API 요청에 실패했습니다.")

    st.info(
        "인터넷 연결, KOBIS API 주소, 인증키, "
        "KOBIS API 서버 상태를 확인해 주세요."
    )

    st.code(str(e))

    st.stop()

except Exception as e:
    st.error("⚠️ 데이터를 불러오는 중 오류가 발생했습니다.")

    st.info(
        "KOBIS 인증키와 선택한 날짜, "
        "KOBIS API 서버 상태를 확인해 주세요."
    )

    st.code(str(e))

    st.stop()


# ----------------------------------------
# 10. KOBIS faultInfo 확인
# ----------------------------------------
# 인증키가 잘못되어도 HTTP 상태코드는 200일 수 있다.
# 따라서 faultInfo가 있는지 반드시 확인한다.

if "faultInfo" in data:

    fault_info = data["faultInfo"]

    st.error("🚨 KOBIS API에서 오류를 반환했습니다.")

    if isinstance(fault_info, dict):

        if "message" in fault_info:
            st.write(
                f"오류 내용: {fault_info['message']}"
            )

        elif "errorMessage" in fault_info:
            st.write(
                f"오류 내용: {fault_info['errorMessage']}"
            )

        else:
            st.write(fault_info)

    else:
        st.write(fault_info)

    st.info(
        "KOBIS_KEY가 정확한지, KOBIS Open API에서 "
        "발급받은 인증키인지 확인해 주세요."
    )

    st.stop()


# ----------------------------------------
# 11. 박스오피스 결과 확인
# ----------------------------------------

boxoffice_result = data.get(
    "boxOfficeResult"
)

if not boxoffice_result:

    st.warning(
        "📭 박스오피스 결과가 없습니다."
    )

    st.info(
        "선택한 날짜에 대한 박스오피스 집계가 있는지 "
        "확인해 주세요."
    )

    st.stop()


# 영화 목록 가져오기
movie_list = boxoffice_result.get(
    "dailyBoxOfficeList",
    []
)


# ----------------------------------------
# 12. 영화 목록이 비어 있는 경우
# ----------------------------------------

if not movie_list:

    st.warning(
        "📭 그날은 아직 집계 전입니다."
    )

    st.info(
        "다른 날짜를 선택해 주세요. "
        "오늘 날짜는 아직 박스오피스가 집계되지 않았기 때문에 "
        "선택할 수 없습니다."
    )

    st.stop()


# ----------------------------------------
# 13. 데이터프레임으로 변환
# ----------------------------------------

df = pd.DataFrame(movie_list)


# ----------------------------------------
# 14. 숫자 데이터 숫자형으로 변환
# ----------------------------------------
# KOBIS API에서는 숫자도 문자열로 전달되므로
# 정렬과 그래프에 사용할 수 있도록 숫자로 변환한다.

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


# ----------------------------------------
# 15. 순위순으로 정렬
# ----------------------------------------

df = df.sort_values(
    "rank"
).reset_index(drop=True)


# ----------------------------------------
# 16. 영화명에 트로피 붙이기
# ----------------------------------------
# 누적관객이 100만 명을 넘으면
# 영화명 뒤에 🏆를 붙인다.

df["영화명표시"] = df.apply(
    lambda row:
        f"{row['movieNm']} 🏆"
        if row["audiAcc"] > 1_000_000
        else row["movieNm"],
    axis=1
)


# ----------------------------------------
# 17. 순위 증감 화살표 만들기
# ----------------------------------------
# rankInten이 양수 → 빨간 위 화살표
# rankInten이 음수 → 파란 아래 화살표
# 0 → 변화 없음
#
# HTML을 사용해 색상을 지정한다.

def make_rank_change(value):

    if pd.isna(value):
        return "-"

    value = int(value)

    if value > 0:
        return f":red[⬆ {value}]"

    elif value < 0:
        return f":blue[⬇ {abs(value)}]"

    else:
        return "—"


df["순위변동"] = df["rankInten"].apply(
    make_rank_change
)


# ----------------------------------------
# 18. 선택한 날짜 표시
# ----------------------------------------

st.subheader(
    f"📅 {display_date} 박스오피스"
)


# ----------------------------------------
# 19. 1위 영화 정보
# ----------------------------------------

first_movie = df.iloc[0]

st.markdown(
    f"## 🥇 {first_movie['영화명표시']}"
)


# ----------------------------------------
# 20. 1위 영화 지표 카드 3개
# ----------------------------------------

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


# ----------------------------------------
# 21. 전체 박스오피스 표
# ----------------------------------------

st.subheader("📋 전체 박스오피스")


display_df = df[
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


# 열 이름을 한글로 변경
display_df.columns = [
    "순위",
    "순위 변동",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수"
]


# 숫자를 보기 편하게 쉼표로 표시
display_df["관객수"] = display_df[
    "관객수"
].apply(
    lambda x:
        f"{int(x):,}" if pd.notna(x) else "-"
)


display_df["누적관객"] = display_df[
    "누적관객"
].apply(
    lambda x:
        f"{int(x):,}" if pd.notna(x) else "-"
)


display_df["스크린수"] = display_df[
    "스크린수"
].apply(
    lambda x:
        f"{int(x):,}" if pd.notna(x) else "-"
)


# 표 표시
st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True
)


# ----------------------------------------
# 22. 관객수 상위 5편 그래프
# ----------------------------------------

st.subheader("📊 관객수 상위 5편")


# 관객수가 많은 순서로 정렬
top5 = (
    df.sort_values(
        "audiCnt",
        ascending=False
    )
    .head(5)
    .copy()
)


# 그래프용 데이터
chart_data = top5[
    ["영화명표시", "audiCnt"]
].copy()


chart_data = chart_data.set_index(
    "영화명표시"
)


# 막대그래프
st.bar_chart(
    chart_data,
    x_label="영화명",
    y_label="관객수"
)


# ----------------------------------------
# 23. 데이터 출처
# ----------------------------------------

st.caption(
    "데이터 출처: 영화관입장권통합전산망(KOBIS) "
    "일일 박스오피스 Open API"
)
