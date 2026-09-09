import streamlit as st
import pandas as pd
import requests

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# ----------------------------------------
# 1. 페이지 기본 설정
# ----------------------------------------

st.set_page_config(
    page_title="어제의 박스오피스",
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
# 3. 한국 시간 기준으로 '어제' 계산
# ----------------------------------------
# 배포 서버의 시간이 한국 시간이 아닐 수 있기 때문에
# 반드시 Asia/Seoul 시간대를 사용한다.

korea_time = datetime.now(ZoneInfo("Asia/Seoul"))
yesterday = korea_time.date() - timedelta(days=1)

# KOBIS API가 요구하는 YYYYMMDD 형식으로 변환
target_date = yesterday.strftime("%Y%m%d")

# 화면에 보여 줄 날짜
display_date = yesterday.strftime("%Y년 %m월 %d일")


# ----------------------------------------
# 4. KOBIS API에서 데이터 가져오기
# ----------------------------------------
# 같은 날짜의 데이터를 1시간 동안 저장한다.
# 따라서 새로고침을 해도 1시간 동안 API를 다시 호출하지 않는다.

@st.cache_data(ttl=3600)
def get_boxoffice(target_dt, api_key):
    """KOBIS에서 해당 날짜의 일일 박스오피스 데이터를 가져온다."""

    params = {
        "key": api_key,
        "targetDt": target_dt
    }

    # API 요청
    response = requests.get(
        API_URL,
        params=params,
        timeout=10
    )

    # HTTP 오류가 발생하면 예외 발생
    response.raise_for_status()

    # JSON 형태로 변환
    data = response.json()

    return data


# ----------------------------------------
# 5. API 인증키 확인
# ----------------------------------------
# Streamlit Cloud의 Secrets에
# KOBIS_KEY = "발급받은 인증키"
# 형태로 저장해야 한다.

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

st.title("🎬 어제의 박스오피스")

st.write(
    f"한국 시간 기준 **{display_date}**의 일일 박스오피스입니다."
)


# ----------------------------------------
# 7. API 요청 및 오류 처리
# ----------------------------------------

try:
    data = get_boxoffice(target_date, api_key)

except requests.exceptions.Timeout:
    st.error("⏱️ KOBIS API 요청 시간이 초과되었습니다.")

    st.info(
        "잠시 후 다시 시도하거나 인터넷 연결 상태를 확인해 주세요."
    )

    st.stop()

except requests.exceptions.RequestException as e:
    st.error("🌐 KOBIS API 요청에 실패했습니다.")

    st.info(
        "인터넷 연결, KOBIS API 주소, API 서버 상태 등을 확인해 주세요."
    )

    st.code(str(e))

    st.stop()

except Exception as e:
    st.error("⚠️ 데이터를 불러오는 중 오류가 발생했습니다.")

    st.info(
        "KOBIS API 인증키와 요청 날짜, API 서버 상태를 확인해 주세요."
    )

    st.code(str(e))

    st.stop()


# ----------------------------------------
# 8. KOBIS의 faultInfo 확인
# ----------------------------------------
# KOBIS는 인증키가 잘못되어도 HTTP 상태코드가 200일 수 있다.
# 따라서 faultInfo가 있는지 직접 확인해야 한다.

if "faultInfo" in data:

    fault_info = data["faultInfo"]

    st.error("🚨 KOBIS API에서 오류를 반환했습니다.")

    # 오류 내용을 화면에 표시
    if isinstance(fault_info, dict):

        if "message" in fault_info:
            st.write(f"오류 내용: {fault_info['message']}")

        elif "errorMessage" in fault_info:
            st.write(f"오류 내용: {fault_info['errorMessage']}")

        else:
            st.write(fault_info)

    else:
        st.write(fault_info)

    st.info(
        "KOBIS_KEY가 정확한지, KOBIS Open API에서 발급받은 "
        "인증키인지 확인해 주세요."
    )

    st.stop()


# ----------------------------------------
# 9. 박스오피스 결과 확인
# ----------------------------------------

boxoffice_result = data.get("boxOfficeResult")

if not boxoffice_result:
    st.error("📭 박스오피스 결과가 없습니다.")

    st.info(
        "KOBIS API 응답에 boxOfficeResult가 있는지 확인하고, "
        "조회 날짜와 API 서버 상태를 확인해 주세요."
    )

    st.stop()


# 영화 목록 가져오기
movie_list = boxoffice_result.get("dailyBoxOfficeList", [])


# 영화 목록이 비어 있는 경우
if not movie_list:
    st.warning("🎬 해당 날짜의 영화 목록이 없습니다.")

    st.info(
        "조회 날짜에 대한 박스오피스 집계가 있는지 확인해 주세요. "
        "KOBIS API 서버 상태도 함께 확인해 주세요."
    )

    st.stop()


# ----------------------------------------
# 10. API 데이터를 데이터프레임으로 변환
# ----------------------------------------

df = pd.DataFrame(movie_list)


# ----------------------------------------
# 11. 숫자로 와야 하는 값들을 숫자형으로 변환
# ----------------------------------------
# KOBIS API에서는 숫자도 문자열로 전달되기 때문에
# 정렬과 그래프를 제대로 사용하려면 숫자로 바꿔야 한다.

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
# 12. 1위 영화 찾기
# ----------------------------------------

df = df.sort_values("rank")

first_movie = df.iloc[0]


# ----------------------------------------
# 13. 1위 영화 정보 크게 보여주기
# ----------------------------------------

st.subheader("🏆 오늘의 박스오피스 1위")

st.markdown(
    f"## 🥇 {first_movie['movieNm']}"
)


# 지표 카드 세 장
col1, col2, col3 = st.columns(3)


with col1:
    st.metric(
        "어제 관객수",
        f"{int(first_movie['audiCnt']):,}명"
    )


with col2:
    st.metric(
        "누적 관객수",
        f"{int(first_movie['audiAcc']):,}명"
    )


with col3:
    st.metric(
        "스크린수",
        f"{int(first_movie['scrnCnt']):,}개"
    )


# ----------------------------------------
# 14. 전체 박스오피스 표
# ----------------------------------------

st.subheader("📋 어제의 박스오피스")

# 화면에 보여 줄 열과 한글 이름
display_columns = [
    "rank",
    "movieNm",
    "openDt",
    "audiCnt",
    "audiAcc",
    "scrnCnt"
]

display_df = df[display_columns].copy()

display_df.columns = [
    "순위",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수"
]

# 숫자를 보기 편하게 표시
display_df["관객수"] = display_df["관객수"].apply(
    lambda x: f"{int(x):,}" if pd.notna(x) else "-"
)

display_df["누적관객"] = display_df["누적관객"].apply(
    lambda x: f"{int(x):,}" if pd.notna(x) else "-"
)

display_df["스크린수"] = display_df["스크린수"].apply(
    lambda x: f"{int(x):,}" if pd.notna(x) else "-"
)

st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True
)


# ----------------------------------------
# 15. 관객수 상위 5편 막대그래프
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

# 그래프에 사용할 데이터
chart_data = top5[
    ["movieNm", "audiCnt"]
].copy()

# 영화명을 인덱스로 설정
chart_data = chart_data.set_index("movieNm")

# 막대그래프 표시
st.bar_chart(
    chart_data,
    x_label="영화명",
    y_label="관객수"
)


# ----------------------------------------
# 16. 데이터 출처 안내
# ----------------------------------------

st.caption(
    "데이터 출처: 영화관입장권통합전산망(KOBIS) 일일 박스오피스 Open API"
)
