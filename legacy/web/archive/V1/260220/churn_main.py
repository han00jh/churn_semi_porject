from soupsieve.css_match import DAYS_IN_WEEK

print("🔥🔥🔥 churn_main 실행 중 🔥🔥🔥")

# ============================================================
# 1️⃣ 기본 설정
# ============================================================
from flask import Flask, render_template, request, redirect, url_for
import pandas as pd
from sqlalchemy import create_engine    , text, Integer, Float, Numeric
from sqlalchemy.dialects.oracle import NUMBER,  FLOAT as ORA_FLOAT
import json
import matplotlib.pyplot as plt
import seaborn as sns
import os



app = Flask(__name__)

# ============================================================
# 2️⃣ 데이터 로드 (CSV)
# ============================================================
engine = create_engine("oracle+cx_oracle://it:0000@localhost:1521/xe")

# ===============================================
# 인덱스
@app.route("/")                         #----웹주소
def index_html():

    # -----------------------------
    # 1️⃣ DB 조회 영역
    # -----------------------------
    with engine.connect() as conn:

        # 기존 예시 차트용 데이터 (필요 컬럼만 조회) day
        df_day = pd.read_sql("""
            SELECT ID, 주간통화시간
            FROM TRAIN
        """, conn)

        df_day.columns = df_day.columns.str.strip()
        df_day.columns = df_day.columns.str.upper()

        print("df_main.columns:", df_day.columns.tolist())
        print("🔥🔥🔥 df_main.columns 확인:", df_day.columns.tolist())

        # 상담전화건수별 해지 건수
        df_call = pd.read_sql("""
            SELECT
                상담전화건수,
                COUNT(CASE WHEN 전화해지여부 = 1 THEN 1 END) AS 해지건수
            FROM TRAIN
            GROUP BY 상담전화건수
            ORDER BY 상담전화건수
        """, conn)

    # -----------------------------
    # 2️⃣ 차트 가공 영역 (Python 영역)
    # -----------------------------



    # 상담전화건수 해지건수 막대그래프
    call_data = {
        "labels": df_call["상담전화건수"].tolist(),
        "values": df_call["해지건수"].tolist()
    }







    # -----------------------------
    # 3️⃣ HTML로 전달
    # -----------------------------
    return render_template(
        "index.html",

        CALL_DATA=call_data,
        MY_KEY_MYLIST = mylist,  # -------------------------------- 전송값
        # MY_KEY_CHART_DATA = chart_data
    )

# ========================================================================================









# ========================================================================================
# ========================================================================================
# ========================================================================================


engine.dispose()
app.run(host='127.0.0.1', port=6001, debug=True)