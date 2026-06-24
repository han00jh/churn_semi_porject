print("🔥 churn_main_final.py 실행 중 🔥")

# ============================================================
# 📦 1. 라이브러리 import
# ============================================================
#pip install google-genai
from ai_service import AIService
from flask import Flask, render_template, request, jsonify
import pandas as pd
from sqlalchemy import create_engine
from google import genai  # Gemini API 라이브러리
import json

app = Flask(__name__)

# ============================================================
# 🔑 2. Gemini API 키 설정
#       ↓↓↓ 여기에 새로 발급받은 API 키 붙여넣기 ↓↓↓
# ============================================================
import os
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")  # 하드코딩 키 제거: 환경변수 사용
client = genai.Client(api_key=GEMINI_API_KEY)


# ============================================================
# 🗄️ 3. Oracle DB 엔진 (전역 1개만 만들어서 재사용)
# ============================================================
engine = create_engine("oracle+cx_oracle://it:0000@localhost:1521/xe")


# ============================================================
# ================================================================
#  📊 가설별 데이터 함수 6개
#  구조: 1️⃣ DB 조회(with)  →  2️⃣ 가공  →  3️⃣ dict 반환
#  반환된 dict는 jsonify() → JavaScript → 차트 그리기에 사용됨
# ================================================================
# ============================================================


# ----------------------------------------------------------------
# 🟦 가설1: 상담전화건수 → 해지건수   (막대그래프)
#   Y축: 해지건수 (율 아님!)
# ----------------------------------------------------------------
def get_df1():

    # 1️⃣ DB 조회  ← with 끝나면 conn 자동 닫힘
    with engine.connect() as conn:
        df_1 = pd.read_sql("""
            SELECT
                상담전화건수,
                COUNT(CASE WHEN 전화해지여부 = 1 THEN 1 END) AS 해지건수,
                COUNT(*) AS 전체건수
            FROM TRAIN
            GROUP BY 상담전화건수
            ORDER BY 상담전화건수
        """, conn)

    # 2️⃣ 가공 → JavaScript Chart.js 가 바로 쓸 수 있는 형태로
    return {
        "labels": df_1["상담전화건수"].tolist(),   # X축 라벨
        "values": df_1["해지건수"].tolist(),        # Y축 값
        "totals": df_1["전체건수"].tolist(),
        "y_label": "해지 건수",
        "title": "가설1: 상담전화건수별 해지 건수",
        # A등급 강조 인덱스: 상담건수 많은 쪽 (뒤쪽) 강조
        "highlight": [7, 8, 9, 10]
    }


# ----------------------------------------------------------------
# 🟩 가설2: 가입일 구간 → 해지율   (라인차트)
# ----------------------------------------------------------------
def get_df2():

    with engine.connect() as conn:
        df_2 = pd.read_sql("""
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

    df_2["가입구간_표시"] = df_2["가입구간"].str[2:]  # "1." 제거

    return {
        "labels": df_2["가입구간_표시"].tolist(),
        "values": df_2["해지율"].tolist(),
        "counts": df_2["해지건수"].tolist(),
        "totals": df_2["전체건수"].tolist(),
        "y_label": "해지율 (%)",
        "title": "가설2: 가입일 구간별 해지율",
        "highlight": [0]   # 신규 구간 강조
    }


# ----------------------------------------------------------------
# 🟨 가설3: 총통화시간 구간 → 해지율   (도넛/영역 차트)
#   총통화시간 = 주간 + 저녁 + 밤
# ----------------------------------------------------------------
def get_df3():

    with engine.connect() as conn:
        df_3 = pd.read_sql("""
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

    df_3["통화시간구간_표시"] = df_3["통화시간구간"].str[2:]

    return {
        "labels": df_3["통화시간구간_표시"].tolist(),
        "values": df_3["해지율"].tolist(),
        "counts": df_3["해지건수"].tolist(),
        "totals": df_3["전체건수"].tolist(),
        "y_label": "해지율 (%)",
        "title": "가설3: 총통화시간 구간별 해지율",
        "highlight": [0]   # 매우낮음 강조
    }


# ----------------------------------------------------------------
# 🟥 가설4: 시간대별 통화 비율   (레이더차트)
#   해지고객 vs 유지고객의 주간/저녁/밤 평균 비율 비교
# ----------------------------------------------------------------
def get_df4():

    with engine.connect() as conn:
        df_4 = pd.read_sql("""
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

    retain = df_4[df_4["전화해지여부"] == 0].iloc[0]
    churn  = df_4[df_4["전화해지여부"] == 1].iloc[0]

    return {
        "labels":       ["주간", "저녁", "밤"],
        "retain":       [float(retain["주간비율"]), float(retain["저녁비율"]), float(retain["밤비율"])],
        "churn":        [float(churn["주간비율"]),  float(churn["저녁비율"]),  float(churn["밤비율"])],
        "retain_count": int(retain["고객수"]),
        "churn_count":  int(churn["고객수"]),
        "y_label": "통화 비율 (%)",
        "title": "가설4: 시간대별 통화 비율 (해지 vs 유지)"
    }


# ----------------------------------------------------------------
# 🟪 가설5: 상담강도 구간 → 해지율   (수평 막대그래프)
#   상담강도 = 상담전화건수 / 가입일
# ----------------------------------------------------------------
def get_df5():

    with engine.connect() as conn:
        df_5 = pd.read_sql("""
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

    df_5["상담강도구간_표시"] = df_5["상담강도구간"].str[2:]

    return {
        "labels": df_5["상담강도구간_표시"].tolist(),
        "values": df_5["해지율"].tolist(),
        "counts": df_5["해지건수"].tolist(),
        "totals": df_5["전체건수"].tolist(),
        "y_label": "해지율 (%)",
        "title": "가설5: 상담강도 구간별 해지율",
        "highlight": [1, 2, 3]   # 중간~매우높음 강조
    }


# ----------------------------------------------------------------
# ⬛ 가설6: 시간당 요금 구간 → 해지율   (버블/산점도 차트)
#   시간당요금 = 총요금 / 총통화시간
# ----------------------------------------------------------------
def get_df6():

    with engine.connect() as conn:
        df_6 = pd.read_sql("""
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

    df_6["요금구간_표시"] = df_6["요금구간"].str[2:]

    return {
        "labels":  df_6["요금구간_표시"].tolist(),
        "values":  df_6["해지율"].tolist(),
        "counts":  df_6["해지건수"].tolist(),
        "totals":  df_6["전체건수"].tolist(),
        "scatter": [           # 산점도용: x=평균시간당요금, y=해지율, r=고객수
            {"x": float(r["평균시간당요금"]),
             "y": float(r["해지율"]),
             "r": max(5, int(r["전체건수"]) // 300)}
            for _, r in df_6.iterrows()
        ],
        "y_label": "해지율 (%)",
        "title": "가설6: 시간당 요금 구간별 해지율",
        "highlight": [0]   # 저렴 구간이 의외로 해지율 높음
    }


# ============================================================
# ================================================================
#  🌐 Flask 라우트 (URL 주소 → 함수 연결)
#  @app.route("/주소")  →  def 함수():  →  return 결과
# ================================================================
# ============================================================
##############################################################################3
#############################################################################
# ----------------------------------------------------------------
# 🏠 메인 화면  →  dashboard_1.html 렌더링
#   브라우저: http://127.0.0.1:6001/
# ----------------------------------------------------------------
@app.route("/")
def index_html():
    # render_template: templates 폴더에서 html 파일 찾아서 보여줌
    return render_template("dashboard_3.html")


# ----------------------------------------------------------------
# 📡 [비동기] 6개 가설 데이터 전체 반환
#   JavaScript fetch("/get_all_data") → 이 함수 실행 → JSON 반환
#   methods=["POST"]: JavaScript에서 POST 방식으로 요청해야 함
# ----------------------------------------------------------------
@app.route("/get_all_data", methods=["POST"])
def get_all_data():

    # request.json: JavaScript가 보낸 데이터 읽기
    # grade: "ALL" / "A" / "B" / "C" / "D"
    grade = request.json.get("grade", "ALL")
    print(f"📡 /get_all_data 요청 수신 | grade={grade}")

    # 6개 함수 호출 → dict로 합쳐서 JSON 반환
    # jsonify(): Python dict → JavaScript가 읽을 수 있는 JSON 변환
    return jsonify({
        "h1": get_df1(),
        "h2": get_df2(),
        "h3": get_df3(),
        "h4": get_df4(),
        "h5": get_df5(),
        "h6": get_df6(),
        "grade": grade    # JavaScript에서 어느 등급인지 확인용
    })


# ----------------------------------------------------------------
# 🤖 [비동기] Gemini 챗봇
#   자동 모드: 페이지 로드/버튼 클릭 시 그래프 데이터 자동 분석
#   수동 모드: 사용자가 질문 입력 시 답변
# ----------------------------------------------------------------
@app.route("/chat_insight", methods=["POST"])
def chat_insight():

    user_message = request.json.get("message", "")
    graph_data   = request.json.get("graph_data", {})
    auto_mode    = request.json.get("auto_mode", False)

    try:
        # ── 그래프 데이터를 텍스트로 요약 (Gemini에게 전달할 컨텍스트)
        context = f"""
당신은 통신사 고객 이탈 분석 전문 AI 어드바이저입니다.
현재 대시보드에 표시된 데이터를 분석하여 기업 임원에게 보고하는 형식으로 답변해주세요.

=== 현재 데이터 요약 ===
선택 위험 등급: {graph_data.get('grade', 'ALL')}

[가설1] 상담전화건수별 해지건수
- X축(상담건수): {graph_data.get('h1', {}).get('labels', [])}
- Y축(해지건수): {graph_data.get('h1', {}).get('values', [])}

[가설2] 가입일 구간별 해지율(%)
- 구간: {graph_data.get('h2', {}).get('labels', [])}
- 해지율: {graph_data.get('h2', {}).get('values', [])}

[가설3] 총통화시간 구간별 해지율(%)
- 구간: {graph_data.get('h3', {}).get('labels', [])}
- 해지율: {graph_data.get('h3', {}).get('values', [])}

[가설4] 시간대별 통화 비율
- 해지고객: {graph_data.get('h4', {}).get('churn', [])}
- 유지고객: {graph_data.get('h4', {}).get('retain', [])}

[가설5] 상담강도 구간별 해지율(%)
- 구간: {graph_data.get('h5', {}).get('labels', [])}
- 해지율: {graph_data.get('h5', {}).get('values', [])}

[가설6] 시간당요금 구간별 해지율(%)
- 구간: {graph_data.get('h6', {}).get('labels', [])}
- 해지율: {graph_data.get('h6', {}).get('values', [])}
"""

        if auto_mode:
            # ── 자동 분석 프롬프트 (페이지 로드/버튼 클릭 시)
            prompt = f"""{context}

위 데이터를 분석하여 아래 형식으로 기업 임원에게 보고해주세요.
구체적인 수치를 반드시 포함하고, 한국어로 작성해주세요.

🔴 핵심 위험 현황
(가장 심각한 이탈 위험 요인 2가지, 수치 포함)

📊 데이터 인사이트
(각 가설에서 발견된 주요 패턴 3가지)

💡 즉시 실행 가능한 전략
(구체적인 고객 유지 방안 3가지)
"""
        else:
            # ── 사용자 질문 응답 프롬프트
            prompt = f"""{context}

사용자 질문: {user_message}

위 데이터를 바탕으로 전문적이고 구체적으로 답변해주세요.
수치를 근거로 활용하고, 실행 가능한 제안을 포함해주세요.
"""

        # ── Gemini API 호출
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt
        )
        answer   = response.text

        return jsonify({"success": True, "answer": answer})

    except Exception as e:
        print(f"❌ Gemini 오류: {e}")
        return jsonify({"success": False, "answer": f"챗봇 오류: {str(e)}"})


# ============================================================
# 🚀 서버 실행
# ============================================================
engine.dispose()
app.run(host="127.0.0.1", port=6001, debug=True)
