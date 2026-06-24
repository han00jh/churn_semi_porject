# ============================================================
# 1️⃣ 환경 설정
# ============================================================

# 운영체제(OS)와 상호작용하는 모듈 (파일 경로 등)
import os

# 파일 경로를 쉽게 다루는 모듈 (경로 합치기, 상위 폴더 이동 등)
from pathlib import Path

# 데이터 분석 라이브러리 (엑셀, CSV 읽기/쓰기)
import pandas as pd

# SQLAlchemy: 파이썬에서 DB를 다루는 라이브러리
from sqlalchemy import create_engine, String, text, Integer, Float, Numeric

# Oracle DB 전용 데이터 타입 (현재 미사용)
from sqlalchemy.dialects.oracle import NUMBER, FLOAT as ORA_FLOAT

# sys 모듈: 파이썬 시스템 정보 확인
import sys

# 현재 사용 중인 파이썬 실행 파일 경로 출력
# 예: C:\IT\workspace_python\.venv\Scripts\python.exe
print(sys.executable)

# ============================================================
# 2️⃣ 엔진 열기
# ============================================================

# Oracle DB 연결 엔진 생성
# 형식: "oracle+cx_oracle://사용자명:비밀번호@호스트:포트/SID"
# it: 사용자명
# 0000: 비밀번호
# localhost: DB가 현재 컴퓨터에 있음
# 1521: Oracle 기본 포트
# xe: Oracle Express Edition (무료 버전)
engine = create_engine("oracle+cx_oracle://it:0000@localhost:1521/xe")

# ============================================================
# 3. 경로에 맞게 데이터 로드 (CSV)해서 df에 담기
# ============================================================

# __file__: 현재 실행 중인 파일 (churn_insert.py)의 경로
# .resolve(): 절대 경로로 변환
# .parent: 상위 폴더로 이동
# .parent.parent: 두 단계 위로 이동
#
# 예시:
# 현재 파일: C:\IT\workspace_python\project\oneplus3\web\churn_insert.py
# .parent: C:\IT\workspace_python\project\oneplus3\web
# .parent.parent: C:\IT\workspace_python\project\oneplus3
BASE_DIR = Path(__file__).resolve().parent.parent

# BASE_DIR에서 "data/Churn/train.csv" 경로 합치기
# 결과: C:\IT\workspace_python\project\oneplus3\data\Churn\train.csv
CSV_PATH = BASE_DIR / "data" / "Churn" / "train.csv"

# CSV 파일을 읽어서 pandas DataFrame에 저장
df = pd.read_csv(CSV_PATH)

# 아래는 절대 경로로 직접 읽는 방법 (현재 주석 처리됨)
# df = pd.read_csv(r"C:\IT\workspace_python\project\oneplus3\data\Churn\train.csv")

# 데이터 로드 확인: (행 개수, 열 개수) 출력
# 예: (30200, 14) → 30,200행, 14열
print("CSV 로드 완료:", df.shape)

# 컬럼명 출력
# 예: ['ID', '가입일', '음성사서함이용', ...]
print(df.columns)

# 데이터프레임 상세 정보 출력
# - 각 컬럼의 데이터 타입
# - Null 값 개수
# - 메모리 사용량
df.info()

# ============================================================
# 4. Oracle DB 연결 - with으로 엔진 열고 닫고
# ============================================================

# 아래 코드는 사용 안 함 (주석 처리)
# engine = create_engine("oracle+cx_oracle://it:0000@localhost:1521/xe")
# conn = engine.connect()

# with문: 자동으로 연결 열고 닫기 (안전함)
# engine.begin(): 트랜잭션 시작 (데이터 일괄 처리)
with engine.begin() as conn:
    # DataFrame을 Oracle DB 테이블로 저장
    df.to_sql(
        # 테이블 이름 (Oracle에서는 자동으로 대문자 TRAIN으로 저장됨)
        name="TRAIN",

        # DB 연결 객체
        con=conn,

        # 테이블이 이미 존재하면 삭제 후 새로 생성
        # 옵션: "fail"(에러), "append"(추가), "replace"(교체)
        if_exists="replace",

        # DataFrame의 인덱스(0, 1, 2, ...)를 테이블에 저장하지 않음
        index=False,

        # method="multi": 대량 데이터 빠르게 삽입 (현재 주석)
        # method="multi",

        # 각 컬럼의 Oracle DB 데이터 타입 지정
        dtype={
            # ID: 최대 20자 문자열
            "ID": String(20),

            # 가입일: 정수 (예: 329일)
            "가입일": Integer(),

            # 음성사서함이용: 정수 (0 또는 1)
            "음성사서함이용": Integer(),

            # 주간통화시간: 숫자(12자리, 소수점 4자리)
            # 예: 12345678.1234
            "주간통화시간": Numeric(12, 4),

            "주간통화요금": Numeric(12, 4),
            "저녁통화시간": Numeric(12, 4),
            "저녁통화요금": Numeric(12, 4),
            "밤통화시간": Numeric(12, 4),
            "밤통화요금": Numeric(12, 4),

            # 통화횟수: 정수
            "주간통화횟수": Integer(),
            "저녁통화횟수": Integer(),
            "밤통화횟수": Integer(),

            # 상담전화건수: 정수
            "상담전화건수": Integer(),

            # 전화해지여부: 정수 (0=유지, 1=해지)
            "전화해지여부": Integer(),
        }
    )

# with문이 끝나면 자동으로 commit(저장)되고 연결이 닫힘


# 완료 메시지 출력
print("Oracle 저장 완료! (train 테이블 생성/적재 완료)")

# 주석: 코드 끝 표시
# ---------------------------------------------------------------------------------------------------이상무