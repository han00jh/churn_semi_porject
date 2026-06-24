print("🔥 churn_main_3.py 실행 중 🔥")

# ============================================================
# 📁 churn_main_3.py
# 역할: Flask 서버 실행 + DB 조회 + AI 연결 허브
#
# 전체 흐름:
#   브라우저 요청
#     └→ @app.route 라우트가 받음
#          └→ DB 조회 함수(get_df1~6) 호출
#               └→ AIService.get_insight() 호출 (AI 필요할 때만)
#                    └→ JSON 으로 브라우저에 반환
#                         └→ JavaScript 가 차트 그림
#
# 포트: 6001  →  브라우저: http://127.0.0.1:6001/
# ============================================================


# ============================================================
# 📦 1. 라이브러리 import
# ============================================================
from flask      import Flask, render_template, request, jsonify
from sqlalchemy import create_engine
from dotenv     import load_dotenv   # .env 파일 읽기용
from ai_service import AIService     # ai_service.py 의 AIService 클래스 가져오기
import pandas as pd
import os                            # 환경변수 읽기용


# ============================================================
# 🔑 2. .env 에서 API 키·DB 정보 읽기
#
# ✏️ 수정할 일 없음.
#    키 바꾸려면 .env 파일만 수정하면 됨
# ============================================================
load_dotenv()   # .env 파일을 자동으로 읽어서 환경변수로 등록

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")   # .env 의 GEMINI_API_KEY= 값
DB_URL         = os.getenv("DB_URL")           # .env 의 DB_URL= 값

# 키가 없으면 바로 알려주기
if not GEMINI_API_KEY:
    print("⚠️  경고: .env 에 GEMINI_API_KEY 가 없습니다! AI 기능이 작동하지 않습니다.")


# ============================================================
# 🤖 3. AIService 객체 생성 (틀 찍기)
#
# AIService 클래스(틀)에 api_key 넣어서 객체(실제 물건) 만들기
# ai_service.py 의 __init__ 이 여기서 실행됨
# ✏️ 모델 바꾸거나 AI 옵션 바꾸려면 → ai_service.py 수정
# ============================================================
ai = AIService(api_key=GEMINI_API_KEY)


# ============================================================
# 🌐 4. Flask 앱 생성
# ============================================================
app = Flask(__name__)


# ============================================================
# 🗄️ 5. Oracle DB 엔진 (전역 1개 → 모든 함수가 재사용)
#
# ✏️ DB 접속 정보 바꾸려면 → .env 의 DB_URL 수정
# ============================================================
engine = create_engine(DB_URL)


# ============================================================
# ================================================================
#  📊 DB 조회 함수 6개 (가설별)
#
#  공통 구조:
#    1️⃣  with engine.connect() as conn:  → DB 연결 (with 끝나면 자동 종료)
#    2️⃣      pd.read_sql(SQL, conn)       → SQL 실행 → DataFrame
#    3️⃣  return { ... }                   → JS Chart.js 가 바로 쓸 수 있는 dict
#
#  반환된 dict 는 get_all_data() 라우트가 jsonify() 로 JSON 변환 후
#  JavaScript 의 fetch() 가 받아서 차트를 그림
# ================================================================
# ============================================================


# ----------------------------------------------------------------
# 🟦 가설1: 상담전화건수 → 해지건수  (세로 막대그래프)
# ✏️ SQL 수정: WHERE 절 추가하면 특정 조건 필터 가능
# ----------------------------------------------------------------
def get_df1():
    with engine.connect() as conn:
        df = pd.read_sql("""
            SELECT
                상담전화건수,
                COUNT(CASE WHEN 전화해지여부 = 1 THEN 1 END) AS 해지건수,
                COUNT(*) AS 전체건수
            FROM TRAIN
            GROUP BY 상담전화건수
            ORDER BY 상담전화건수
        """, conn)

    return {
        "labels"   : df["상담전화건수"].tolist(),   # JS: h1.labels
        "values"   : df["해지건수"].tolist(),        # JS: h1.values
        "totals"   : df["전체건수"].tolist(),
        "y_label"  : "해지 건수",
        "title"    : "가설1: 상담전화건수별 해지 건수",
        "highlight": [7, 8, 9, 10]                  # 강조할 인덱스 번호
    }


# ----------------------------------------------------------------
# 🟩 가설2: 가입일 구간 → 해지율  (라인차트)
# ✏️ 구간 범위 바꾸려면: WHEN 가입일 <= 숫자 부분 수정
# ----------------------------------------------------------------
def get_df2():
    with engine.connect() as conn:
        df = pd.read_sql("""
            SELECT
                CASE
                    WHEN 가입일 <= 100  THEN '1.신규(~100일)'
                    WHEN 가입일 <= 300  THEN '2.중간(101~300일)'
                    WHEN 가입일 <= 500  THEN '3.오래(301~500일)'
                    ELSE                     '4.장기(500일+)'
                END AS 가입구간,
                COUNT(*) AS 전체건수,
                COUNT(CASE WHEN 전화해지여부 = 1 THEN 1 END) AS 해지건수,
                ROUND(
                    COUNT(CASE WHEN 전화해지여부 = 1 THEN 1 END) * 100.0 / COUNT(*), 2
                ) AS 해지율
            FROM TRAIN
            GROUP BY
                CASE
                    WHEN 가입일 <= 100  THEN '1.신규(~100일)'
                    WHEN 가입일 <= 300  THEN '2.중간(101~300일)'
                    WHEN 가입일 <= 500  THEN '3.오래(301~500일)'
                    ELSE                     '4.장기(500일+)'
                END
            ORDER BY 가입구간
        """, conn)

    df["가입구간_표시"] = df["가입구간"].str[2:]   # "1." 앞글자 제거

    return {
        "labels"   : df["가입구간_표시"].tolist(),
        "values"   : df["해지율"].tolist(),
        "counts"   : df["해지건수"].tolist(),
        "totals"   : df["전체건수"].tolist(),
        "y_label"  : "해지율 (%)",
        "title"    : "가설2: 가입일 구간별 해지율",
        "highlight": [0]
    }


# ----------------------------------------------------------------
# 🟨 가설3: 총통화시간 구간 → 해지율  (도넛차트)
# ✏️ 총통화시간 = 주간 + 저녁 + 밤
# ----------------------------------------------------------------
def get_df3():
    with engine.connect() as conn:
        df = pd.read_sql("""
            SELECT
                CASE
                    WHEN (주간통화시간 + 저녁통화시간 + 밤통화시간) <= 530
                        THEN '1.매우낮음(~530분)'
                    WHEN (주간통화시간 + 저녁통화시간 + 밤통화시간) <= 700
                        THEN '2.낮음(531~700분)'
                    WHEN (주간통화시간 + 저녁통화시간 + 밤통화시간) <= 870
                        THEN '3.보통(701~870분)'
                    ELSE '4.높음(871분+)'
                END AS 통화시간구간,
                COUNT(*) AS 전체건수,
                COUNT(CASE WHEN 전화해지여부 = 1 THEN 1 END) AS 해지건수,
                ROUND(
                    COUNT(CASE WHEN 전화해지여부 = 1 THEN 1 END) * 100.0 / COUNT(*), 2
                ) AS 해지율
            FROM TRAIN
            GROUP BY
                CASE
                    WHEN (주간통화시간 + 저녁통화시간 + 밤통화시간) <= 530
                        THEN '1.매우낮음(~530분)'
                    WHEN (주간통화시간 + 저녁통화시간 + 밤통화시간) <= 700
                        THEN '2.낮음(531~700분)'
                    WHEN (주간통화시간 + 저녁통화시간 + 밤통화시간) <= 870
                        THEN '3.보통(701~870분)'
                    ELSE '4.높음(871분+)'
                END
            ORDER BY 통화시간구간
        """, conn)

    df["통화시간구간_표시"] = df["통화시간구간"].str[2:]

    return {
        "labels"   : df["통화시간구간_표시"].tolist(),
        "values"   : df["해지율"].tolist(),
        "counts"   : df["해지건수"].tolist(),
        "totals"   : df["전체건수"].tolist(),
        "y_label"  : "해지율 (%)",
        "title"    : "가설3: 총통화시간 구간별 해지율",
        "highlight": [0]
    }


# ----------------------------------------------------------------
# 🟥 가설4: 시간대별 통화 비율 비교  (레이더차트)
# ✏️ 해지 vs 유지 고객의 주간/저녁/밤 통화 패턴 비교
# ----------------------------------------------------------------
def get_df4():
    with engine.connect() as conn:
        df = pd.read_sql("""
            SELECT
                전화해지여부,
                ROUND(AVG(
                    주간통화시간 / (주간통화시간 + 저녁통화시간 + 밤통화시간 + 0.001) * 100
                ), 2) AS 주간비율,
                ROUND(AVG(
                    저녁통화시간 / (주간통화시간 + 저녁통화시간 + 밤통화시간 + 0.001) * 100
                ), 2) AS 저녁비율,
                ROUND(AVG(
                    밤통화시간 / (주간통화시간 + 저녁통화시간 + 밤통화시간 + 0.001) * 100
                ), 2) AS 밤비율,
                COUNT(*) AS 고객수
            FROM TRAIN
            GROUP BY 전화해지여부
            ORDER BY 전화해지여부
        """, conn)

    retain = df[df["전화해지여부"] == 0].iloc[0]
    churn  = df[df["전화해지여부"] == 1].iloc[0]

    return {
        "labels"      : ["주간", "저녁", "밤"],
        "retain"      : [float(retain["주간비율"]), float(retain["저녁비율"]), float(retain["밤비율"])],
        "churn"       : [float(churn["주간비율"]),  float(churn["저녁비율"]),  float(churn["밤비율"])],
        "retain_count": int(retain["고객수"]),
        "churn_count" : int(churn["고객수"]),
        "y_label"     : "통화 비율 (%)",
        "title"       : "가설4: 시간대별 통화 비율 (해지 vs 유지)"
    }


# ----------------------------------------------------------------
# 🟪 가설5: 상담강도 구간 → 해지율  (수평 막대그래프)
# ✏️ 상담강도 = 상담전화건수 / 가입일
# ----------------------------------------------------------------
def get_df5():
    with engine.connect() as conn:
        df = pd.read_sql("""
            SELECT
                CASE
                    WHEN (상담전화건수 / (가입일 + 0.001)) <= 0.01
                        THEN '1.낮음(~0.01)'
                    WHEN (상담전화건수 / (가입일 + 0.001)) <= 0.03
                        THEN '2.중간(0.01~0.03)'
                    WHEN (상담전화건수 / (가입일 + 0.001)) <= 0.06
                        THEN '3.높음(0.03~0.06)'
                    ELSE '4.매우높음(0.06+)'
                END AS 상담강도구간,
                COUNT(*) AS 전체건수,
                COUNT(CASE WHEN 전화해지여부 = 1 THEN 1 END) AS 해지건수,
                ROUND(
                    COUNT(CASE WHEN 전화해지여부 = 1 THEN 1 END) * 100.0 / COUNT(*), 2
                ) AS 해지율
            FROM TRAIN
            GROUP BY
                CASE
                    WHEN (상담전화건수 / (가입일 + 0.001)) <= 0.01
                        THEN '1.낮음(~0.01)'
                    WHEN (상담전화건수 / (가입일 + 0.001)) <= 0.03
                        THEN '2.중간(0.01~0.03)'
                    WHEN (상담전화건수 / (가입일 + 0.001)) <= 0.06
                        THEN '3.높음(0.03~0.06)'
                    ELSE '4.매우높음(0.06+)'
                END
            ORDER BY 상담강도구간
        """, conn)

    df["상담강도구간_표시"] = df["상담강도구간"].str[2:]

    return {
        "labels"   : df["상담강도구간_표시"].tolist(),
        "values"   : df["해지율"].tolist(),
        "counts"   : df["해지건수"].tolist(),
        "totals"   : df["전체건수"].tolist(),
        "y_label"  : "해지율 (%)",
        "title"    : "가설5: 상담강도 구간별 해지율",
        "highlight": [1, 2, 3]
    }


# ----------------------------------------------------------------
# ⬛ 가설6: 시간당 요금 구간 → 해지율  (버블차트)
# ✏️ 시간당요금 = 총요금 / 총통화시간
# ----------------------------------------------------------------
def get_df6():
    with engine.connect() as conn:
        df = pd.read_sql("""
            SELECT
                CASE
                    WHEN (주간통화요금 + 저녁통화요금 + 밤통화요금)
                       / (주간통화시간 + 저녁통화시간 + 밤통화시간 + 0.001) <= 0.08
                        THEN '1.저렴(~0.08)'
                    WHEN (주간통화요금 + 저녁통화요금 + 밤통화요금)
                       / (주간통화시간 + 저녁통화시간 + 밤통화시간 + 0.001) <= 0.13
                        THEN '2.보통(0.08~0.13)'
                    WHEN (주간통화요금 + 저녁통화요금 + 밤통화요금)
                       / (주간통화시간 + 저녁통화시간 + 밤통화시간 + 0.001) <= 0.18
                        THEN '3.비쌈(0.13~0.18)'
                    ELSE '4.매우비쌈(0.18+)'
                END AS 요금구간,
                COUNT(*) AS 전체건수,
                COUNT(CASE WHEN 전화해지여부 = 1 THEN 1 END) AS 해지건수,
                ROUND(
                    COUNT(CASE WHEN 전화해지여부 = 1 THEN 1 END) * 100.0 / COUNT(*), 2
                ) AS 해지율,
                ROUND(
                    AVG((주간통화요금 + 저녁통화요금 + 밤통화요금)
                      / (주간통화시간 + 저녁통화시간 + 밤통화시간 + 0.001)), 4
                ) AS 평균시간당요금
            FROM TRAIN
            GROUP BY
                CASE
                    WHEN (주간통화요금 + 저녁통화요금 + 밤통화요금)
                       / (주간통화시간 + 저녁통화시간 + 밤통화시간 + 0.001) <= 0.08
                        THEN '1.저렴(~0.08)'
                    WHEN (주간통화요금 + 저녁통화요금 + 밤통화요금)
                       / (주간통화시간 + 저녁통화시간 + 밤통화시간 + 0.001) <= 0.13
                        THEN '2.보통(0.08~0.13)'
                    WHEN (주간통화요금 + 저녁통화요금 + 밤통화요금)
                       / (주간통화시간 + 저녁통화시간 + 밤통화시간 + 0.001) <= 0.18
                        THEN '3.비쌈(0.13~0.18)'
                    ELSE '4.매우비쌈(0.18+)'
                END
            ORDER BY 요금구간
        """, conn)

    df["요금구간_표시"] = df["요금구간"].str[2:]

    return {
        "labels"  : df["요금구간_표시"].tolist(),
        "values"  : df["해지율"].tolist(),
        "counts"  : df["해지건수"].tolist(),
        "totals"  : df["전체건수"].tolist(),
        "scatter" : [
            {
                "x": float(r["평균시간당요금"]),
                "y": float(r["해지율"]),
                "r": max(5, int(r["전체건수"]) // 300)
            }
            for _, r in df.iterrows()
        ],
        "y_label" : "해지율 (%)",
        "title"   : "가설6: 시간당 요금 구간별 해지율",
        "highlight": [0]
    }


# ──────────────────────────────────────────────────────────────
# ✏️ 조원 가설 추가 방법:
#
# 1. 아래 함수 복사해서 get_df7() 로 만들기
# 2. get_all_data() 라우트에 "h7": get_df7() 한 줄 추가
# 3. dashboard_3.html 에 chart7 canvas 추가 + drawChart7() 함수 추가
#
# def get_df7():
#     with engine.connect() as conn:
#         df = pd.read_sql("SELECT ... FROM TRAIN ...", conn)
#     return {
#         "labels": df["컬럼명"].tolist(),
#         "values": df["컬럼명"].tolist(),
#         "title" : "가설7: ..."
#     }
# ──────────────────────────────────────────────────────────────


# ============================================================
# ================================================================
#  🌐 Flask 라우트 3개
#  @app.route("주소", methods=["GET"/"POST"])
#  → 브라우저/JavaScript 가 그 주소로 요청하면 함수 실행
# ================================================================
# ============================================================


# ----------------------------------------------------------------
# 🏠 라우트1: 메인 화면
#   접속: http://127.0.0.1:6001/
#   역할: dashboard_3.html 파일을 브라우저에 보여줌
#   ✏️ html 파일명 바꾸려면: "dashboard_3.html" 부분만 수정
# ----------------------------------------------------------------
@app.route("/")
def index():
    return render_template("dashboard_3-2.html")


# ----------------------------------------------------------------
# 📡 라우트2: 6개 가설 데이터 반환  [POST]
#   요청: JavaScript fetch('/get_all_data', { body: {grade:"A"} })
#   역할: grade 받아서 DB 조회 → JSON 반환 → JS 가 차트 그림
#
#   ✏️ 조원 가설 추가: return jsonify({...}) 안에 "h7": get_df7() 추가
# ----------------------------------------------------------------
@app.route("/get_all_data", methods=["POST"])
def get_all_data():

    # JavaScript 가 fetch() 로 보낸 body 데이터 읽기
    # { "grade": "A" }  →  grade = "A"
    grade = request.json.get("grade", "ALL")
    print(f"📡 /get_all_data 요청 | grade={grade}")

    # 6개 함수 호출 → dict 합쳐서 JSON 으로 반환
    # jsonify(): Python dict → JSON 문자열로 자동 변환
    return jsonify({
        "h1"   : get_df1(),
        "h2"   : get_df2(),
        "h3"   : get_df3(),
        "h4"   : get_df4(),
        "h5"   : get_df5(),
        "h6"   : get_df6(),
        "grade": grade         # JS 에서 현재 등급 확인용
    })


# ----------------------------------------------------------------
# 🤖 라우트3: AI 챗봇  [POST]
#   요청: JavaScript fetch('/chat_insight', { body: {...} })
#   역할: 그래프 데이터 + 질문 → AIService.get_insight() → 답변 반환
#
#   body 에 담기는 것:
#     message    : 사용자 질문 텍스트 (수동 모드)
#     graph_data : 현재 화면의 6개 그래프 데이터 (AI 컨텍스트용)
#     auto_mode  : true = 자동 분석 / false = 사용자 질문
# ----------------------------------------------------------------
@app.route("/chat_insight", methods=["POST"])
def chat_insight():

    auto_mode = request.json.get("auto_mode", False)
    mode = request.json.get("mode")
    hypothesis_id = request.json.get("hypothesis_id")
    user_message = request.json.get("message")
    graph_data = request.json.get("graph_data")  # ✅ 추가

    result = ai.get_insight(
        graph_data=graph_data,
        user_message=user_message,
        auto_mode=auto_mode,
        mode=mode,
        hypothesis_id=hypothesis_id
    )

    return jsonify(result)



# ============================================================
# 🚀 서버 실행
#   포트 바꾸려면: port=6001 숫자만 수정
#   debug=True : 코드 수정 시 서버 자동 재시작 (개발 중에만)
# ============================================================
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=6001, debug=True)
