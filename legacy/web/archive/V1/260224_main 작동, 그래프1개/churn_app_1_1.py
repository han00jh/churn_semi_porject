"""
============================================================
churn_app_1_1.py — 주제1 불만고객형 / 1-1 차트 Flask 라우트
============================================================

[역할]
  기존 churn_app.py 에 이 함수와 라우트를 추가하면 됩니다.

[연결 흐름]
  Oracle DB(CHURN 테이블)
    → get_chart_1_1()     ← 데이터 계산 함수
    → /chart_1_1          ← Flask 라우트 (JSON 반환)
    → chart_1_1.html      ← 화면 렌더링
    → chart_1_1.js        ← Chart.js 차트 그리기

[계산 원리]
  해지율(churn_rate) = AVG(TARGET) * 100
  = 해당 그룹의 해지고객수 / 전체고객수 * 100
  TARGET = 1(해지), 0(유지)

[수정 포인트]
  - DB 연결  → engine (기존 churn_app.py 것 그대로 사용)
  - 테이블명 → "CHURN" (필요 시 변경)
  - 포트번호 → app.run() 하단 (기본 6001)
============================================================
"""

from flask import Flask, render_template, jsonify
from sqlalchemy import create_engine
from dotenv import load_dotenv
import pandas as pd
import os

# ── 기존 churn_app.py 에 합칠 경우 아래 4줄은 삭제 ──
load_dotenv()
DB_URL = os.getenv("DB_URL")
engine = create_engine(DB_URL)
app    = Flask(__name__)
# ─────────────────────────────────────────────────────


# ============================================================
# 데이터 계산 함수
# ============================================================

def get_chart_1_1():
    """
    주제1 불만고객형 — 1-1
    상담 건수(cs_calls)별 해지율 계산

    [계산 원리]
      cs_calls 값 기준으로 그룹화
      → 각 그룹의 AVG(TARGET) * 100 = 해지율

    [반환 형태] 딕셔너리
      {
        "labels"    : [0, 1, 2, ...],       ← X축: 상담 횟수
        "values"    : [9.63, 9.59, ...],    ← Y축: 해지율(%)
        "counts"    : [6303, 834, ...],     ← 보조: 고객 수
        "avg_churn" : 10.99                 ← 전체 평균 해지율
      }
    """

    # ── Fallback: DB 실패 시 CSV로 대체 ──────────────────
    try:
        with engine.connect() as conn:
            df = pd.read_sql("""
                SELECT
                    CS_CALLS,
                    ROUND(AVG(TARGET) * 100, 2) AS CHURN_RATE,
                    COUNT(*)                    AS CNT
                FROM CHURN
                GROUP BY CS_CALLS
                ORDER BY CS_CALLS
            """, conn)
            df.columns = df.columns.str.lower()
        print("✅ DB 조회 성공")

    except Exception as e:
        print(f"⚠️ DB 실패 → CSV fallback: {e}")
        df_raw = pd.read_csv("churn.csv")
        df_raw.columns = df_raw.columns.str.strip().str.lower()

        # CSV에서 직접 계산
        # groupby cs_calls → target 평균 * 100 = 해지율
        df = (
            df_raw.groupby("cs_calls")["target"]
            .agg(
                churn_rate=lambda x: round(x.mean() * 100, 2),
                cnt="count"
            )
            .reset_index()
        )

    # 전체 평균 해지율 계산 (기준선용)
    total_avg = round(
        df["churn_rate"].mul(df["cnt"]).sum() / df["cnt"].sum(), 2
    )

    return {
        "labels"    : df["cs_calls"].tolist(),   # X축
        "values"    : df["churn_rate"].tolist(),  # Y축: 해지율
        "counts"    : df["cnt"].tolist(),          # 보조: 고객 수
        "avg_churn" : total_avg                    # 전체 평균선
    }


# ============================================================
# Flask 라우트
# ============================================================

@app.route("/topic1/chart1")
def page_chart_1_1():
    """차트 1-1 HTML 페이지 렌더링"""
    return render_template("chart_1_1.html")


@app.route("/api/chart_1_1")
def api_chart_1_1():
    """
    차트 1-1 데이터 API
    JS에서 fetch("/api/chart_1_1") 로 호출
    → JSON 반환
    """
    data = get_chart_1_1()
    print(f"📡 /api/chart_1_1 | 데이터 {len(data['labels'])}건")
    return jsonify(data)


# ── 단독 실행용 (기존 churn_app.py에 합칠 경우 삭제) ──
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=6001, debug=True)
