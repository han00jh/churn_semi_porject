# ============================================================
# 📁 churn_insert.py
# 역할: CSV 파일 → Oracle DB 에 한 번만 적재하는 스크립트
#
# ⚠️  이 파일은 Flask 와 무관! 실행하면 바로 DB에 저장됨
#     서버 켜기 전에 딱 한 번만 실행하면 됨
#
# 실행 방법:
#   터미널에서: python churn_insert.py
#
# ✏️ 수정 포인트:
#   - CSV 경로 바꾸려면: CSV_PATH 수정
#   - 테이블명 바꾸려면: name="TRAIN" 수정
#   - 컬럼 타입 추가/수정: dtype={...} 수정
# ============================================================

# < pip 설치 목록>
# pip install pandas
# pip install sqlalchemy
# pip install python-dotenv
# pip install cx_Oracle


from pathlib import Path
from sqlalchemy import create_engine, String, Integer, Numeric
from dotenv import load_dotenv
import pandas as pd
import warnings
import os

# Oracle 대소문자 경고 무시
warnings.filterwarnings('ignore', category=UserWarning)


# ============================================================
# 🔑 .env 에서 DB 접속 정보 읽기
# ✏️ DB 정보 바꾸려면 .env 의 DB_URL 만 수정
# ============================================================
load_dotenv()
DB_URL = os.getenv("DB_URL", "oracle+cx_oracle://it:0000@localhost:1521/xe")


# ============================================================
# 🗄️ DB 엔진 생성
# ============================================================
engine = create_engine(DB_URL)


# ============================================================
# 📂 CSV 파일 경로 설정
# "파일 기준 경로 계산 방식"
# 실행 위치가 아니라 현재 파일(insert.py) 위치를 기준으로
# 프로젝트 루트 폴더를 계산한 뒤,
# 그 기준에서 data/Churn/train.csv 로 내려간다.
#
# → 어디에서 실행해도 (VSCode, PyCharm, 터미널)
# → 다른 PC / 다른 드라이브 / GitHub clone 후에도
# → 프로젝트 폴더 구조만 동일하면 정상 동작
# ======================================


# ✏️ 경로 바꾸려면:
#   BASE_DIR = Path("직접경로")  또는
#   CSV_PATH = Path("C:/내폴더/train.csv")  로 수정
# ============================================================
BASE_DIR = Path(__file__).resolve().parent.parent                      # insert.py 기준으로 => 최상위 프로젝트 폴더ST까지 올라감
#  변수   = 1. 현재 실행 중인 파이썬 파일(insert.py)의 경로 2.절대경로로 확정 3.(insert(raw).py파일 기준으로) 한 단계 위 폴더 4.한단계 위 폴더로  (점 기준으로 나눠보면)
CSV_PATH = BASE_DIR / "data" / "Churn" /"raw"/ "train.csv"                  # 최상위 프로젝트폴더ST에서 다시 csv파일찾으러 내려감 data->churn->train.csv
                                                                                     # csv파일 원본. raw data



df = pd.read_csv(CSV_PATH)

print("=" * 60)
print("✅ CSV 로드 완료!")
print(f"  - 데이터 크기: {df.shape[0]:,}행 × {df.shape[1]}열")
print(f"  - 파일 경로: {CSV_PATH}")
print("=" * 60)
df.info()


# ============================================================
# 💾 Oracle DB 에 저장
# if_exists="replace" : 테이블 있으면 덮어씀   ('기존 테이블을 drop->create->insert'하는 기능이라서 실무에선 주의)
#                       "append" 로 바꾸면 이어붙임  (db에서 마지막행에 이어붙이는 것.따라서 데이터 누적 주의)
#                       "fail"   로 바꾸면 이미 있으면 에러 (db에 기존에 train테이블이 있다면 임부러 fail로 뜨게 하는 것)
#
# ✏️ 컬럼 추가 시: dtype={...} 에 "컬럼명": 타입() 추가
# ============================================================
print("\nOracle DB 저장 중...")

with engine.begin() as conn:        #  트랜잭션 자동 시작
                                    # 성공 시 자동 commit
                                    # 에러 발생 시 자동 rollback
                                    # 사용한 커넥션 자동 반환(닫힘)
    df.to_sql(
        name       = "TRAIN",       # ✏️ 테이블명 바꾸려면 여기
        con        = conn,
        if_exists  = "replace",     # ✏️ replace / append / fail
        index      = False,
        dtype={                     #(모든 데이터를 넣으면서 컬럼명에 맞는 타입을 작업하는 것. 문자와 정수는 자동으로 지정되서 상관없지만 소수는 따로 지정 필요.)
            "ID"          : String(20),
            "가입일"       : Integer(),
            "음성사서함이용": Integer(),
            "주간통화시간" : Numeric(12, 4),          #총 12자리(정수+소수포함) 중 소수 4자리.
            "주간통화요금" : Numeric(12, 4),
            "저녁통화시간" : Numeric(12, 4),
            "저녁통화요금" : Numeric(12, 4),
            "밤통화시간"   : Numeric(12, 4),
            "밤통화요금"   : Numeric(12, 4),
            "주간통화횟수" : Integer(),
            "저녁통화횟수" : Integer(),
            "밤통화횟수"   : Integer(),
            "상담전화건수" : Integer(),
            "전화해지여부" : Integer(),
        }
    )

print("=" * 60)
print("✅ Oracle 저장 완료!")
print(f"  - 테이블명: TRAIN")
print(f"  - 저장된 행: {df.shape[0]:,}개")
print("=" * 60)

engine.dispose()                                # DB 연결 정리 (필수는 아님, 깔끔한 종료용)



######핵심######
# churn_insert.py는 초기 데이터 적재용 스크립트
# 1회 실행 후 DB에 데이터 저장  (따라서 처음에 한 번만 하면 됨.)
# 이후에는 main.py(Flask)에서 DB 데이터를 조회하여
# 표/차트/웹 화면으로 전달함

# 실행 오류 발생 시:
# replace는 내부적으로 DROP → CREATE → INSERT 수행
# 권한 부족, 락(lock), 제약조건 등으로 DROP이 실패할 수 있음
# 이 경우 DB에서 DROP TABLE TRAIN 후 재실행하면 해결되는 경우가 있음


#구조
# ============================================================
# 📌 시스템 전체 흐름 (압축 버전)
# ============================================================

# CSV (원본 데이터)
#  ↓
# churn_insert.py  → DB에 1회 적재
#  ↓
# Oracle DB (데이터 저장소)
#  ↓
# main.py (Flask 서버)
#   ├─ DB 조회
#   ├─ 데이터 가공 (차트/JSON 생성)
#   └─ ai.py 호출 (AI 분석)
#  ↓
# HTML + JS (화면 구성 + 차트 렌더링)
#  ↓
# 브라우저 (사용자 화면)
# ============================================================