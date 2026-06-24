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
@app.route("/")   # ----------------------------- 웹주소
def index_html():



    # 🔥 with 사용해서 연결 자동 close
    with engine.connect() as conn:
        df = pd.read_sql("SELECT * FROM TRAIN", conn)

    # ⚠️ TRAIN 테이블에는 ename, sal 없음
    # 실제 존재하는 컬럼으로 변경
    chart_data = {
        "label1": df["ID"].head(10).tolist(),
        "value1": df["주간통화시간"].head(10).tolist(),
        "label2": ["aa", "bb", "cc", "dd"],
        "value2": [110, 220, 330, 440]
    }

    mylist = [10, 20, 30, 40]

    return render_template(
        "index.html",
        MY_KEY_MYLIST=mylist,
        MY_KEY_CHART_DATA=chart_data
    )

    # ============================================================
    # 그래프_ 상담전화건수에 따른 해지율
    # ============================================================






# ========================================================================================



























# ========================================================================================
# ========================================================================================
# ========================================================================================


engine.dispose()
app.run(host='127.0.0.1', port=7777, debug=True)