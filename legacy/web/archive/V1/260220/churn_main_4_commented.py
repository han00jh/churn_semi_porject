print("🔥 churn_main_4_commented.py 실행 중 🔥")

# ============================================================
# 📁 churn_main_4.py  ← 이 파일이 하는 일 한 줄 요약:
#
#   브라우저(HTML) ↔ 파이썬(Flask) ↔ Oracle DB 를 연결하는 "중간 다리"
#
#   브라우저가 "/get_all_data" 로 요청을 보내면
#   → 이 파일이 Oracle DB에서 SQL로 데이터를 꺼내서
#   → JSON 형태로 브라우저에게 돌려준다
#
#
# ★ highlight_map 원리 ★
#   각 가설의 X축 구간에 인덱스(0,1,2,3...) 부여
#   A버튼 → grade="A" → highlight_map["A"] = [해당인덱스]
#   JS가 그 인덱스의 막대만 색변환+확대 처리
# ============================================================


# ============================================================
# 📦 라이브러리 임포트 (수업 lec07, lec08 내용)
# ============================================================

# ─ Flask: 파이썬으로 웹서버를 만드는 도구 (lec08 REST 서버 역할)
#   Flask     : 웹 앱 객체 생성
#   render_template : HTML 파일을 브라우저에 돌려줌 (templates 폴더에서 찾음)
#   request   : 브라우저가 보낸 데이터를 받는 도구 (POST body의 JSON 등)
#   jsonify   : 파이썬 딕셔너리 → JSON 으로 변환해서 반환 (lec08의 "리턴데이터는 JSON")
from flask      import Flask, render_template, request, jsonify

# ─ SQLAlchemy: 파이썬에서 Oracle(DB)에 연결할 때 쓰는 라이브러리 (lec07 핵심)
#   create_engine: DB 연결 엔진 생성 → lec07의 engine = create_engine(...) 과 동일
from sqlalchemy import create_engine

# ─ dotenv: .env 파일에서 비밀번호, API키 등 민감한 정보를 읽어오는 도구
#   .env 파일에 DB_URL, GROQ_API_KEY 를 저장해두면
#   코드에 직접 비밀번호를 쓰지 않아도 됨 → 보안상 매우 중요!
#   (GitHub에 올릴 때 .env는 .gitignore에 추가해서 절대 올리면 안 됨)
from dotenv     import load_dotenv

# ─ ai_service: 같은 폴더에 있는 ai_service.py 를 임포트
#   AI 챗봇(GROQ API)과 통신하는 기능이 여기에 분리되어 있음
from ai_service import AIService

# ─ pandas: 데이터 분석 핵심 라이브러리
#   pd.read_sql() : SQL 실행 결과를 DataFrame으로 바로 받음 (lec07 핵심)
import pandas as pd

# ─ os: 운영체제 기능 (환경변수 읽기 등)
import os


# ============================================================
# ⚙️ 환경변수 로드 & 초기 설정
# ============================================================

# .env 파일을 읽어서 환경변수로 등록
# .env 파일 내용 예시:
#   GROQ_API_KEY=gsk_xxxxxxxxxxxx
#   DB_URL=oracle+cx_oracle://아이디:비밀번호@localhost:1521/xe
load_dotenv()

# os.getenv("키이름") : .env에서 해당 키의 값을 가져옴
GROQ_API_KEY = os.getenv("GROQ_API_KEY")   # AI API 키 (GROQ 서비스)
DB_URL       = os.getenv("DB_URL")          # Oracle DB 접속 URL

# .env 에 키가 없으면 경고 출력 (None이면 AI 기능 안 됨)
if not GROQ_API_KEY:
    print("⚠️  .env 에 GROQ_API_KEY 없음!")


# ============================================================
# 🏗️ 핵심 객체 3개 생성
# ============================================================

# 1. AI 서비스 객체 (ai_service.py 의 AIService 클래스 인스턴스화)
ai = AIService(api_key=GROQ_API_KEY)

# 2. Flask 앱 객체 생성
#    __name__ : 현재 파일 이름을 넘겨서 Flask가 이 파일 기준으로 경로를 잡게 함
#    이 한 줄이 "웹서버"를 만드는 것 (lec08의 REST 서버)
app = Flask(__name__)

# 3. Oracle DB 연결 엔진 생성 (lec07 내용과 완전히 동일!)
#    lec07에서 배운 코드:
#      engine = create_engine("oracle+cx_oracle://it:0000@localhost:1521/xe")
#    여기서는 .env에서 URL을 읽어오는 것만 다름 → 보안을 위해
#
#    DB_URL 형식: oracle+cx_oracle://[아이디]:[비밀번호]@[호스트]:[포트]/[서비스명]
#    예) oracle+cx_oracle://scott:tiger@localhost:1521/xe
engine = create_engine(DB_URL)


# ================================================================
# 📊 DB 조회 함수 6개  (모두 grade 파라미터 추가)
#
# ─ 공통 구조 설명 ─
#   with engine.connect() as conn:          ← lec07: DB 연결 열기
#       df = pd.read_sql("SQL문", conn)     ← lec07: SQL 실행 → DataFrame
#
#   highlight_map = {"ALL":[], "A":[...]}   ← ABCD 버튼별 강조 인덱스 지정
#
#   return { "labels": [...], ... }         ← lec08: JSON으로 반환할 딕셔너리
#                                              jsonify()가 이걸 JSON으로 변환
# ================================================================


# ----------------------------------------------------------------
# 🟦 가설1: 상담전화건수 → 해지건수  [세로 막대그래프]
#
#   "상담전화를 많이 할수록 불만족 → 해지 가능성 높다"
#
#   labels 예: [0,1,2,3,4,5,6,7,8,9,11]  인덱스 0~10
#   A: 상담 많은 쪽(뒤) → [8,9,10]   B: [5,6,7]
#   C: [3,4]            D: 적은 쪽 → [0,1,2]
#
#   ★ grade 파라미터: 버튼(ALL/A/B/C/D)에 따라 어느 막대를 강조할지 결정
# ----------------------------------------------------------------
def get_df1(grade="ALL"):
    # lec07 with 구문: 작업이 끝나면 DB 연결을 자동으로 닫아줌 (안전!)
    # engine.connect() : 읽기 전용 연결 (SELECT 용)
    with engine.connect() as conn:
        df = pd.read_sql("""
            SELECT 상담전화건수,
                   COUNT(CASE WHEN 전화해지여부=1 THEN 1 END) AS 해지건수,
                   COUNT(*) AS 전체건수
            FROM TRAIN
            GROUP BY 상담전화건수
            ORDER BY 상담전화건수
        """, conn)
        # ↑ SQL 해석:
        #   전화해지여부=1 인 건만 카운트 → 상담건수별 "실제 해지 고객 수"
        #   전체건수도 함께 → 나중에 비율 계산 가능
        #   GROUP BY 상담전화건수 : 상담건수가 같은 것끼리 묶어서 집계

    # ─ highlight_map 구조 ─
    # 딕셔너리 키: 버튼명 ("ALL","A","B","C","D")
    # 딕셔너리 값: 강조할 X축 인덱스 리스트
    # JS에서 이 인덱스 번호에 해당하는 막대만 색상/크기를 바꿈
    highlight_map = {
        "ALL": [],          # 전체 버튼: 강조 없음
        "A":  [8, 9, 10],  # A등급: 상담 8~11건 이상 → 고위험
        "B":  [5, 6, 7],   # B등급: 상담 5~7건 → 중위험
        "C":  [3, 4],      # C등급: 상담 3~4건 → 관심 필요
        "D":  [0, 1, 2]    # D등급: 상담 0~2건 → 안전
    }

    # ─ 반환 딕셔너리 ─
    # 이 딕셔너리가 jsonify()를 통해 JSON이 되어 브라우저로 전달됨 (lec08)
    # 브라우저의 JS가 이 데이터를 받아서 Chart.js로 그래프를 그림
    return {
        "labels"   : df["상담전화건수"].tolist(),   # X축 라벨 [0,1,2,3,...]
        "values"   : df["해지건수"].tolist(),        # Y축 값 (해지 건수)
        "totals"   : df["전체건수"].tolist(),        # 툴팁에 표시할 전체 건수
        "y_label"  : "해지 건수",
        "title"    : "가설1: 상담전화건수별 해지 건수",
        "highlight": highlight_map.get(grade, [])   # 현재 선택된 등급의 강조 인덱스
    }


# ----------------------------------------------------------------
# 🟩 가설2: 가입일 구간 → 해지율  [라인차트]
#
#   "가입한 지 얼마 안 된 신규 고객일수록 해지율이 높다"
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
        # ↑ SQL 핵심:
        #   CASE WHEN ~ THEN : 가입일을 4개 구간으로 나눔
        #   해지율 = 해지건수/전체건수*100 → 비율로 비교
        #   ORDER BY 가입구간 : 1. 2. 3. 4. 앞에 붙여서 정렬 (문자열 정렬 트릭)

    # 앞에 붙인 "1." "2." 등의 정렬용 번호를 제거해서 라벨을 깔끔하게 만듦
    # "1.신규(~100일)" → "신규(~100일)"
    df["가입구간_표시"] = df["가입구간"].str[2:]

    highlight_map = {
        "ALL": [],   # 전체: 강조 없음
        "A":  [0],   # A: 신규 구간이 가장 위험
        "B":  [1],   # B: 중간 구간
        "C":  [2],   # C: 오래된 구간
        "D":  [3]    # D: 장기 고객은 안전
    }

    return {
        "labels"   : df["가입구간_표시"].tolist(),  # X축 라벨 (구간명)
        "values"   : df["해지율"].tolist(),          # Y축 값 (해지율 %)
        "counts"   : df["해지건수"].tolist(),        # 툴팁: 실제 해지 건수
        "totals"   : df["전체건수"].tolist(),        # 툴팁: 전체 건수
        "y_label"  : "해지율 (%)",
        "title"    : "가설2: 가입일 구간별 해지율",
        "highlight": highlight_map.get(grade, [])
    }


# ----------------------------------------------------------------
# 🟨 가설3: 총통화시간 구간 → 해지율  [도넛차트]
#
#   "통화를 거의 안 하는 고객 = 서비스 활용도 낮음 → 해지율 높다"
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
        # ↑ SQL 핵심:
        #   주간+저녁+밤 = 총통화시간 (컬럼이 3개라 더해야 함)
        #   4개 구간으로 나눠서 각 구간의 해지율 계산

    df["통화시간구간_표시"] = df["통화시간구간"].str[2:]  # "1." 제거

    highlight_map = {
        "ALL": [], "A": [0], "B": [1], "C": [2], "D": [3]
    }

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
#
#   "해지 고객과 유지 고객은 시간대별 통화 패턴이 다르다"
#   → 주간/저녁/밤 비율을 레이더로 비교 (두 선: 해지 vs 유지)
#
#   레이더는 두 선을 겹쳐서 비교하는 차트
#   → highlight 없음 (인덱스 강조 방식이 아닌 선 색상으로 구분)
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
        # ↑ SQL 핵심:
        #   +0.001 : 분모가 0이 되는 오류 방지 (0으로 나누기 방지 트릭)
        #   AVG(시간/전체*100) : 각 고객의 비율을 구한 뒤 평균냄
        #   GROUP BY 전화해지여부 → 0(유지)과 1(해지) 두 줄만 나옴

    # df에서 유지(0)와 해지(1) 행을 각각 추출
    retain = df[df["전화해지여부"]==0].iloc[0]  # 유지 고객 행
    churn  = df[df["전화해지여부"]==1].iloc[0]  # 해지 고객 행

    return {
        "labels"      : ["주간","저녁","밤"],               # 레이더 꼭짓점 라벨
        "retain"      : [float(retain["주간비율"]),          # 유지 고객 비율 리스트
                         float(retain["저녁비율"]),
                         float(retain["밤비율"])],
        "churn"       : [float(churn["주간비율"]),           # 해지 고객 비율 리스트
                         float(churn["저녁비율"]),
                         float(churn["밤비율"])],
        "retain_count": int(retain["고객수"]),               # 유지 고객 수 (툴팁용)
        "churn_count" : int(churn["고객수"]),                # 해지 고객 수 (툴팁용)
        "y_label"     : "통화 비율 (%)",
        "title"       : "가설4: 시간대별 통화 비율 (해지 vs 유지)",
        "highlight"   : []  # 레이더차트는 강조 인덱스 없음
    }


# ----------------------------------------------------------------
# 🟪 가설5: 상담강도 구간 → 해지율  [수평 막대그래프]
#
#   "상담강도 = 상담건수/가입기간 → 가입한 지 얼마 안 됐는데 상담을 많이 함 = 위험"
#   단순 상담 건수가 아니라 '기간 대비 비율'로 정교하게 분석
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
        # ↑ SQL 핵심:
        #   상담강도 = 상담건수 / (가입일+0.001)  ← 파생 변수를 SQL 안에서 계산
        #   이 값이 클수록 "짧은 기간에 상담을 많이 한 고위험 고객"

    df["상담강도구간_표시"] = df["상담강도구간"].str[2:]  # "1." 제거

    # ★ 주의: 이 가설은 인덱스 순서가 반대!
    #   인덱스 0=낮음(안전), 3=매우높음(위험) 이므로
    #   A(가장 위험) → [3], D(안전) → [0]
    highlight_map = {
        "ALL": [],
        "A":  [3],  # 매우높음 = A등급 위험
        "B":  [2],
        "C":  [1],
        "D":  [0]   # 낮음 = D등급 (안전, 개입 불필요)
    }

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
#   "분당 요금이 비쌀수록 해지율이 높다 (또는 역설적으로 낮다)"
#   → 시간당 요금 = (주간+저녁+밤 요금) / (주간+저녁+밤 시간)
#
#   labels: [저렴(~0.08), 보통(0.08~0.13), 비쌈(0.13~0.18), 매우비쌈(0.18+)]
#   인덱스:      0               1                2                3
#
#   버블차트: X=평균시간당요금, Y=해지율, 버블크기=전체건수
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
        # ↑ SQL 핵심:
        #   시간당요금 = 총요금 / 총시간 → SQL 안에서 직접 계산
        #   평균시간당요금 → 버블의 X축 위치
        #   전체건수 → 버블의 크기 (r 값)

    df["요금구간_표시"] = df["요금구간"].str[2:]

    highlight_map = {
        "ALL": [], "A": [0], "B": [1], "C": [2], "D": [3]
    }

    return {
        "labels"   : df["요금구간_표시"].tolist(),
        "values"   : df["해지율"].tolist(),
        "counts"   : df["해지건수"].tolist(),
        "totals"   : df["전체건수"].tolist(),
        # ─ 버블차트 전용 데이터 ─
        # x: 버블의 X 좌표 (평균 시간당 요금)
        # y: 버블의 Y 좌표 (해지율)
        # r: 버블의 반지름 크기 (전체건수 기반, 최소 5)
        "scatter"  : [
            {
                "x": float(r["평균시간당요금"]),
                "y": float(r["해지율"]),
                "r": max(5, int(r["전체건수"]) // 300)  # 300으로 나눠서 크기 조절
            }
            for _, r in df.iterrows()  # 행마다 딕셔너리 하나씩 생성
        ],
        "y_label"  : "해지율 (%)",
        "title"    : "가설6: 시간당 요금 구간별 해지율",
        "highlight": highlight_map.get(grade, [])
    }


# ================================================================
# 🌐 Flask 라우트 3개  (lec08 REST API)
#
# ─ 라우트(Route)란? ─
#   특정 URL로 요청이 들어왔을 때 어떤 함수를 실행할지 연결하는 것
#   @app.route("/경로", methods=["GET"또는"POST"])
#
# ─ lec08 핵심 개념 연결 ─
#   GET  : 데이터 조회 (URL에 정보 포함, 브라우저 주소창에서 바로 접근 가능)
#   POST : 데이터 전송 (Body에 JSON 담아서 보냄, URL에 안 보임)
# ================================================================

# ─ 라우트 1: 메인 페이지 ─
# GET 방식: 브라우저가 "/" 주소로 접속하면 dashboard_4.html을 돌려줌
# render_template: templates 폴더에서 HTML 파일을 찾아서 브라우저에 전송
@app.route("/")
def index():
    return render_template("dashboard_4-1.html")
    # ↑ 이 HTML 파일 안에 JS 코드가 있고
    #   그 JS가 아래 /get_all_data 로 비동기 요청을 보냄 (lec08 비동기)


# ─ 라우트 2: 차트 데이터 API ─
# POST 방식: JS가 JSON Body에 {"grade": "A"} 담아서 보냄
# 브라우저 → 이 함수 → DB 조회 → JSON 반환 → 브라우저에서 차트 업데이트
# 이것이 lec08의 "REST API + 비동기 통신" 패턴!
@app.route("/get_all_data", methods=["POST"])
def get_all_data():                           # <-----위험도 등급 ABCD관해서 해당 등급 버튼을 클릭시 등급에 맞게 각 그래프를 한 번에 변환.
    # request.json : POST Body에서 JSON 데이터 추출 (lec08 POST 방식)
    # .get("grade", "ALL") : "grade" 키가 없으면 기본값 "ALL"
    grade = request.json.get("grade", "ALL")
    print(f"📡 /get_all_data | grade={grade}")

    # 6개 가설 함수를 모두 호출해서 데이터를 한 번에 묶어 반환
    # jsonify() : 파이썬 딕셔너리 → JSON 형식으로 변환 (lec08 핵심)
    # 브라우저가 이 JSON을 받아서 6개 차트를 모두 업데이트
    return jsonify({
        "h1": get_df1(grade),  # 가설1 데이터
        "h2": get_df2(grade),  # 가설2 데이터
        "h3": get_df3(grade),  # 가설3 데이터
        "h4": get_df4(grade),  # 가설4 데이터
        "h5": get_df5(grade),  # 가설5 데이터
        "h6": get_df6(grade),  # 가설6 데이터
        "grade": grade         # 현재 선택된 등급 (JS에서 UI 표시용)
    })


# ─ 라우트 3: AI 챗봇 API ─
# POST 방식: JS가 {graph_data, message, mode, ...} 담아서 보냄
# ai_service.py의 get_insight() 함수가 GROQ API 호출 → 응답 반환
@app.route("/chat_insight", methods=["POST"])
def chat_insight():
    # request.json.get("키", 기본값) 패턴으로 각 파라미터 추출
    result = ai.get_insight(
        graph_data    = request.json.get("graph_data"),     # 현재 차트 데이터
        user_message  = request.json.get("message"),        # 사용자 질문 텍스트
        auto_mode     = request.json.get("auto_mode", False), # 자동 분석 모드 여부
        mode          = request.json.get("mode"),           # 모드: 종합/가설/자유
        hypothesis_id = request.json.get("hypothesis_id")  # 어떤 가설인지 (h1~h6)
    )
    # ai.get_insight()가 반환한 딕셔너리를 JSON으로 변환해서 브라우저에 전달
    return jsonify(result)


# ─ 라우트 4: AI 연결 상태 확인 ─
# GET 방식: /ai_status 로 접속하면 API 키가 정상인지 확인 결과 반환
# 개발/디버깅 시 "AI가 왜 안 되지?" 확인할 때 브라우저에서 바로 주소 입력해서 확인
@app.route("/ai_status")
def ai_status():
    return ai.check_connection()


# ================================================================
# 🚀 서버 실행
# ================================================================

if __name__ == "__main__":
    # __name__ == "__main__" : 이 파일을 직접 실행할 때만 서버 시작
    # (다른 파일에서 import 할 때는 서버가 자동 시작되면 안 되므로)
    app.run(
        host  = "127.0.0.1",  # 127.0.0.1 = 내 컴퓨터에서만 접속 가능 (로컬)
        port  = 6001,          # 접속 주소: http://127.0.0.1:6001
        debug = True           # 코드 수정 시 서버 자동 재시작 + 에러 상세 표시
    )
    # ↑ 실행 후 브라우저에서 http://127.0.0.1:6001 접속
