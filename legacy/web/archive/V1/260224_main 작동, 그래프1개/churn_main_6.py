



print("🔥 churn_main_8.py 실행 중 🔥")

# ============================================================
# 📁 churn_main_6.py
# ============================================================

# pip install python-dotenv

from flask      import Flask, render_template, request, jsonify
from sqlalchemy import create_engine
from dotenv     import load_dotenv
from churn_ai import AIService
import pandas as pd
import os


load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")     #GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DB_URL         = os.getenv("DB_URL")



if not GROQ_API_KEY:
    print("⚠️  .env 에 GROQ_API_KEY 없음!")

ai     = AIService(api_key=GROQ_API_KEY)
app    = Flask(__name__)
engine = create_engine(DB_URL)


# ================================================================
# 📊 DB 조회 함수 6개  (모두 grade 파라미터 추가)
# ================================================================

# ----------------------------------------------------------------
# 🟦 가설1: 상담전화건수 → 해지건수  [세로 막대그래프]
#
#   labels 예: [0,1,2,3,4,5,6,7,8,9,11]  인덱스 0~10
#   A: 상담 많은 쪽(뒤) → [8,9,10]   B: [5,6,7]
#   C: [3,4]            D: 적은 쪽 → [0,1,2]
# ----------------------------------------------------------------
def get_df1(grade="ALL"):
    with engine.connect() as conn:
        df = pd.read_sql("""
            SELECT 상담전화건수,
                   COUNT(CASE WHEN 전화해지여부=1 THEN 1 END) AS 해지건수,
                   COUNT(*) AS 전체건수
            FROM TRAIN
            GROUP BY 상담전화건수
            ORDER BY 상담전화건수
        """, conn)

    highlight_map = {
        "ALL": [], "A": [8,9,10], "B": [5,6,7], "C": [3,4], "D": [0,1,2]
    }
    return {
        "labels"   : df["상담전화건수"].tolist(),
        "values"   : df["해지건수"].tolist(),
        "totals"   : df["전체건수"].tolist(),
        "y_label"  : "해지 건수",
        "title"    : "가설1: 상담전화건수별 해지 건수",
        "highlight": highlight_map.get(grade, [])
    }


# ----------------------------------------------------------------
# 🟩 가설2: 가입일 구간 → 해지율  [라인차트]
#
#   labels: [신규(~100일), 중간(101~300일), 오래(301~500일), 장기(500일+)]
#   인덱스:       0               1                2                3
#   A: 신규=위험→[0]  B:[1]  C:[2]  D: 장기=안전→[3]
# ----------------------------------------------------------------
def get_df2(grade="ALL"):
    with engine.connect() as conn:
        df = pd.read_sql("""
            SELECT
                CASE
                    WHEN 가입일<=100  THEN '1.신규(~100일)'
                    WHEN 가입일<=300  THEN '2.중간(101~300일)'
                    WHEN 가입일<=500  THEN '3.오래(301~500일)'
                    ELSE                   '4.장기(500일+)'
                END AS 가입구간,
                COUNT(*) AS 전체건수,
                COUNT(CASE WHEN 전화해지여부=1 THEN 1 END) AS 해지건수,
                ROUND(COUNT(CASE WHEN 전화해지여부=1 THEN 1 END)*100.0/COUNT(*),2) AS 해지율
            FROM TRAIN
            GROUP BY
                CASE
                    WHEN 가입일<=100  THEN '1.신규(~100일)'
                    WHEN 가입일<=300  THEN '2.중간(101~300일)'
                    WHEN 가입일<=500  THEN '3.오래(301~500일)'
                    ELSE                   '4.장기(500일+)'
                END
            ORDER BY 가입구간
        """, conn)
    df["가입구간_표시"] = df["가입구간"].str[2:]

    highlight_map = {"ALL":[], "A":[0], "B":[1], "C":[2], "D":[3]}
    return {
        "labels"   : df["가입구간_표시"].tolist(),
        "values"   : df["해지율"].tolist(),
        "counts"   : df["해지건수"].tolist(),
        "totals"   : df["전체건수"].tolist(),
        "y_label"  : "해지율 (%)",
        "title"    : "가설2: 가입일 구간별 해지율",
        "highlight": highlight_map.get(grade, [])
    }


# ----------------------------------------------------------------
# 🟨 가설3: 총통화시간 구간 → 해지율  [도넛차트]
#
#   labels: [매우낮음(~530분), 낮음(531~700분), 보통(701~870분), 높음(871분+)]
#   인덱스:        0                  1                2               3
#   A: 통화 매우낮음=이탈전조→[0]  D: 높음=충성→[3]
# ----------------------------------------------------------------
def get_df3(grade="ALL"):
    with engine.connect() as conn:
        df = pd.read_sql("""
            SELECT
                CASE
                    WHEN (주간통화시간+저녁통화시간+밤통화시간)<=530  THEN '1.매우낮음(~530분)'
                    WHEN (주간통화시간+저녁통화시간+밤통화시간)<=700  THEN '2.낮음(531~700분)'
                    WHEN (주간통화시간+저녁통화시간+밤통화시간)<=870  THEN '3.보통(701~870분)'
                    ELSE '4.높음(871분+)'
                END AS 통화시간구간,
                COUNT(*) AS 전체건수,
                COUNT(CASE WHEN 전화해지여부=1 THEN 1 END) AS 해지건수,
                ROUND(COUNT(CASE WHEN 전화해지여부=1 THEN 1 END)*100.0/COUNT(*),2) AS 해지율
            FROM TRAIN
            GROUP BY
                CASE
                    WHEN (주간통화시간+저녁통화시간+밤통화시간)<=530  THEN '1.매우낮음(~530분)'
                    WHEN (주간통화시간+저녁통화시간+밤통화시간)<=700  THEN '2.낮음(531~700분)'
                    WHEN (주간통화시간+저녁통화시간+밤통화시간)<=870  THEN '3.보통(701~870분)'
                    ELSE '4.높음(871분+)'
                END
            ORDER BY 통화시간구간
        """, conn)
    df["통화시간구간_표시"] = df["통화시간구간"].str[2:]

    highlight_map = {"ALL":[], "A":[0], "B":[1], "C":[2], "D":[3]}
    return {
        "labels"   : df["통화시간구간_표시"].tolist(),
        "values"   : df["해지율"].tolist(),
        "counts"   : df["해지건수"].tolist(),
        "totals"   : df["전체건수"].tolist(),
        "y_label"  : "해지율 (%)",
        "title"    : "가설3: 총통화시간 구간별 해지율",
        "highlight": highlight_map.get(grade, [])
    }


# ----------------------------------------------------------------
# 🟥 가설4: 시간대별 통화 비율  [레이더차트]
#   해지 vs 유지 고객의 주간/저녁/밤 비율 비교
#   레이더는 두 선 비교 → highlight 없음, grade별 해지선 색만 변경
# ----------------------------------------------------------------
def get_df4(grade="ALL"):
    with engine.connect() as conn:
        df = pd.read_sql("""
            SELECT 전화해지여부,
                   ROUND(AVG(주간통화시간/(주간통화시간+저녁통화시간+밤통화시간+0.001)*100),2) AS 주간비율,
                   ROUND(AVG(저녁통화시간/(주간통화시간+저녁통화시간+밤통화시간+0.001)*100),2) AS 저녁비율,
                   ROUND(AVG(밤통화시간/(주간통화시간+저녁통화시간+밤통화시간+0.001)*100),2) AS 밤비율,
                   COUNT(*) AS 고객수
            FROM TRAIN
            GROUP BY 전화해지여부
            ORDER BY 전화해지여부
        """, conn)
    retain = df[df["전화해지여부"]==0].iloc[0]
    churn  = df[df["전화해지여부"]==1].iloc[0]

    return {
        "labels"      : ["주간","저녁","밤"],
        "retain"      : [float(retain["주간비율"]),float(retain["저녁비율"]),float(retain["밤비율"])],
        "churn"       : [float(churn["주간비율"]), float(churn["저녁비율"]), float(churn["밤비율"])],
        "retain_count": int(retain["고객수"]),
        "churn_count" : int(churn["고객수"]),
        "y_label"     : "통화 비율 (%)",
        "title"       : "가설4: 시간대별 통화 비율 (해지 vs 유지)",
        "highlight"   : []
    }


# ----------------------------------------------------------------
# 🟪 가설5: 상담강도 구간 → 해지율  [수평 막대그래프]
#
#   labels: [낮음(~0.01), 중간(0.01~0.03), 높음(0.03~0.06), 매우높음(0.06+)]
#   인덱스:      0               1                2                3
#   A: 매우높음=최고위험→[3]  D: 낮음=안전→[0]
# ----------------------------------------------------------------
def get_df5(grade="ALL"):
    with engine.connect() as conn:
        df = pd.read_sql("""
            SELECT
                CASE
                    WHEN (상담전화건수/(가입일+0.001))<=0.01 THEN '1.낮음(~0.01)'
                    WHEN (상담전화건수/(가입일+0.001))<=0.03 THEN '2.중간(0.01~0.03)'
                    WHEN (상담전화건수/(가입일+0.001))<=0.06 THEN '3.높음(0.03~0.06)'
                    ELSE '4.매우높음(0.06+)'
                END AS 상담강도구간,
                COUNT(*) AS 전체건수,
                COUNT(CASE WHEN 전화해지여부=1 THEN 1 END) AS 해지건수,
                ROUND(COUNT(CASE WHEN 전화해지여부=1 THEN 1 END)*100.0/COUNT(*),2) AS 해지율
            FROM TRAIN
            GROUP BY
                CASE
                    WHEN (상담전화건수/(가입일+0.001))<=0.01 THEN '1.낮음(~0.01)'
                    WHEN (상담전화건수/(가입일+0.001))<=0.03 THEN '2.중간(0.01~0.03)'
                    WHEN (상담전화건수/(가입일+0.001))<=0.06 THEN '3.높음(0.03~0.06)'
                    ELSE '4.매우높음(0.06+)'
                END
            ORDER BY 상담강도구간
        """, conn)
    df["상담강도구간_표시"] = df["상담강도구간"].str[2:]

    highlight_map = {"ALL":[], "A":[3], "B":[2], "C":[1], "D":[0]}
    return {
        "labels"   : df["상담강도구간_표시"].tolist(),
        "values"   : df["해지율"].tolist(),
        "counts"   : df["해지건수"].tolist(),
        "totals"   : df["전체건수"].tolist(),
        "y_label"  : "해지율 (%)",
        "title"    : "가설5: 상담강도 구간별 해지율",
        "highlight": highlight_map.get(grade, [])
    }


# ----------------------------------------------------------------
# ⬛ 가설6: 시간당 요금 구간 → 해지율  [버블차트]
#
#   labels: [저렴(~0.08), 보통(0.08~0.13), 비쌈(0.13~0.18), 매우비쌈(0.18+)]
#   인덱스:      0               1                2                3
#   A: 저렴구간이 의외로 해지율 높음→[0]  D: 매우비쌈=프리미엄→[3]
# ----------------------------------------------------------------
def get_df6(grade="ALL"):
    with engine.connect() as conn:
        df = pd.read_sql("""
            SELECT
                CASE
                    WHEN (주간통화요금+저녁통화요금+밤통화요금)
                       / (주간통화시간+저녁통화시간+밤통화시간+0.001)<=0.08  THEN '1.저렴(~0.08)'
                    WHEN (주간통화요금+저녁통화요금+밤통화요금)
                       / (주간통화시간+저녁통화시간+밤통화시간+0.001)<=0.13  THEN '2.보통(0.08~0.13)'
                    WHEN (주간통화요금+저녁통화요금+밤통화요금)
                       / (주간통화시간+저녁통화시간+밤통화시간+0.001)<=0.18  THEN '3.비쌈(0.13~0.18)'
                    ELSE '4.매우비쌈(0.18+)'
                END AS 요금구간,
                COUNT(*) AS 전체건수,
                COUNT(CASE WHEN 전화해지여부=1 THEN 1 END) AS 해지건수,
                ROUND(COUNT(CASE WHEN 전화해지여부=1 THEN 1 END)*100.0/COUNT(*),2) AS 해지율,
                ROUND(AVG((주간통화요금+저녁통화요금+밤통화요금)
                    /(주간통화시간+저녁통화시간+밤통화시간+0.001)),4) AS 평균시간당요금
            FROM TRAIN
            GROUP BY
                CASE
                    WHEN (주간통화요금+저녁통화요금+밤통화요금)
                       / (주간통화시간+저녁통화시간+밤통화시간+0.001)<=0.08  THEN '1.저렴(~0.08)'
                    WHEN (주간통화요금+저녁통화요금+밤통화요금)
                       / (주간통화시간+저녁통화시간+밤통화시간+0.001)<=0.13  THEN '2.보통(0.08~0.13)'
                    WHEN (주간통화요금+저녁통화요금+밤통화요금)
                       / (주간통화시간+저녁통화시간+밤통화시간+0.001)<=0.18  THEN '3.비쌈(0.13~0.18)'
                    ELSE '4.매우비쌈(0.18+)'
                END
            ORDER BY 요금구간
        """, conn)
    df["요금구간_표시"] = df["요금구간"].str[2:]

    highlight_map = {"ALL":[], "A":[0], "B":[1], "C":[2], "D":[3]}
    return {
        "labels"   : df["요금구간_표시"].tolist(),
        "values"   : df["해지율"].tolist(),
        "counts"   : df["해지건수"].tolist(),
        "totals"   : df["전체건수"].tolist(),
        "scatter"  : [
            {"x":float(r["평균시간당요금"]),"y":float(r["해지율"]),"r":max(5,int(r["전체건수"])//300)}
            for _,r in df.iterrows()
        ],
        "y_label"  : "해지율 (%)",
        "title"    : "가설6: 시간당 요금 구간별 해지율",
        "highlight": highlight_map.get(grade, [])
    }


# ================================================================
# 🌐 Flask 라우트 3개
# ================================================================

@app.route("/")
def index():
    return render_template("dashboard_08.html")


# ★ 핵심: grade를 각 get_df 함수에 전달 → 등급별 highlight 반환 ★
@app.route("/get_all_data", methods=["POST"])
def get_all_data():
    grade = request.json.get("grade", "ALL")
    print(f"📡 /get_all_data | grade={grade}")
    return jsonify({
        "h1": get_df1(grade), "h2": get_df2(grade),
        "h3": get_df3(grade), "h4": get_df4(grade),
        "h5": get_df5(grade), "h6": get_df6(grade),
        "grade": grade
    })


# AI 챗봇: 3가지 모드 (종합분석 / 가설설명 / 자유질문)
@app.route("/chat_insight", methods=["POST"])
def chat_insight():
    result = ai.get_insight(
        graph_data    = request.json.get("graph_data"),
        user_message  = request.json.get("message"),
        auto_mode     = request.json.get("auto_mode", False),
        mode          = request.json.get("mode"),
        hypothesis_id = request.json.get("hypothesis_id")
    )
    return jsonify(result)


# ★ 신규: 챗봇1 — 현황 한 줄 요약
@app.route("/ai_summary", methods=["POST"])
def ai_summary():
    return jsonify(ai.get_summary(request.json.get("graph_data")))

# ★ 신규: 챗봇2 — 대책방안 한 줄
@app.route("/ai_strategy", methods=["POST"])
def ai_strategy():
    return jsonify(ai.get_strategy(request.json.get("graph_data")))

# ★ 신규: 챗봇3 — 예상 이익 수치 한 줄
@app.route("/ai_forecast", methods=["POST"])
def ai_forecast():
    return jsonify(ai.get_forecast(request.json.get("graph_data")))


# ============================================================
# 🔎 AI 상태 상세 확인 API
# ============================================================
@app.route("/ai_status")
def ai_status():
    return jsonify(ai.check_connection())

##=======================================

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=6001, debug=True)




# 구조
# ============================================================
# 📌 한 줄 흐름 요약
# CSV → churn_insert.py → Oracle DB → main.py(+ai.py) → HTML/JS → 브라우저
# ============================================================


# ============================================================
# 📌 전체 시스템 구조 (데이터 흐름)
# ============================================================

# [1] CSV 파일
#  └─ 원본 데이터 파일 (train.csv 등)
#  └─ 아직 DB에 들어가기 전의 상태

#        ↓

# [2] churn_insert.py
#  └─ CSV 파일을 읽어서
#  └─ Oracle DB 테이블(TRAIN)에 저장하는 초기 적재 스크립트
#  └─ 서버 실행 전 1회만 실행
#  └─ Flask와 무관 (웹 기능 없음)

#        ↓

# [3] Oracle DB
#  └─ 데이터가 실제로 저장되는 공간
#  └─ Flask(main.py)가 여기서 데이터를 조회함

#        ↓

# [4] main.py (Flask 서버)
#  ├─ 사용자가 웹에 접속하면 실행됨
#  ├─ Oracle DB에서 데이터 조회
#  ├─ 차트/표에 필요한 데이터 가공
#  ├─ 필요 시 ai.py 호출
#  └─ HTML로 데이터 전달 (JSON 형태)

#        ↓

# [5] ai.py
#  └─ AI API 통신 전담 파일
#  └─ 데이터 분석 요청
#  └─ 인사이트/요약/예측 결과 생성
#  └─ 결과를 main.py로 반환

#        ↓

# [6] HTML + JS
#  ├─ 화면 구조 담당 (HTML)
#  ├─ 차트 렌더링 담당 (JS, Chart.js 등)
#  ├─ main.py가 전달한 데이터를 받아
#  └─ 브라우저에 시각화

#        ↓

# [7] 브라우저 화면
#  └─ 사용자에게 최종적으로 보이는 화면
#  └─ 차트, 표, AI 분석 결과 표시
# ============================================================
