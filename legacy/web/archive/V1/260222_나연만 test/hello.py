print("(= > ⩊ < =) hello 나연world 실행 중 (= > ⩊ < =)")

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

@app.route("/hello")
def hello():
    print("good morning!")
    return render_template('hello.html')









































# ===============================================
# ===============================================
engine.dispose()
app.run(host='127.0.0.1', port=6001, debug=True)