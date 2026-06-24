# ============================================================
# 통신 고객 이탈 데이터 Oracle DB 적재 스크립트
# ============================================================
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine, String, Integer, Numeric
import warnings

# UserWarning 무시 (테이블명 대소문자 경고)
warnings.filterwarnings('ignore', category=UserWarning)

# ============================================================
# 1. Oracle DB 연결 엔진 생성
# ============================================================
engine = create_engine("oracle+cx_oracle://it:0000@localhost:1521/xe")

# ============================================================
# 2. CSV 파일 로드
# ============================================================
# 현재 파일 위치에서 상위 폴더로 이동하여 data/Churn/train.csv 찾기
BASE_DIR = Path(__file__).resolve().parent.parent
CSV_PATH = BASE_DIR / "data" / "Churn" / "train.csv"

# CSV 읽기
df = pd.read_csv(CSV_PATH)

# 로드 확인
print("="*60)
print("CSV 로드 완료!")
print(f"  - 데이터 크기: {df.shape[0]:,}행 × {df.shape[1]}열")
print(f"  - 파일 경로: {CSV_PATH}")
print("="*60)
print("\n[컬럼 정보]")
df.info()
print()

# ============================================================
# 3. Oracle DB에 저장
# ============================================================
print("Oracle DB 저장 중...")

with engine.begin() as conn:
    df.to_sql(
        name="TRAIN",           # 테이블명
        con=conn,                # DB 연결
        if_exists="replace",     # 기존 테이블 교체
        index=False,             # 인덱스 제외
        dtype={
            "ID": String(20),
            "가입일": Integer(),
            "음성사서함이용": Integer(),
            "주간통화시간": Numeric(12, 4),
            "주간통화요금": Numeric(12, 4),
            "저녁통화시간": Numeric(12, 4),
            "저녁통화요금": Numeric(12, 4),
            "밤통화시간": Numeric(12, 4),
            "밤통화요금": Numeric(12, 4),
            "주간통화횟수": Integer(),
            "저녁통화횟수": Integer(),
            "밤통화횟수": Integer(),
            "상담전화건수": Integer(),
            "전화해지여부": Integer(),
        }
    )

print("="*60)
print("✅ Oracle 저장 완료!")
print(f"  - 테이블명: TRAIN")
print(f"  - 저장된 행: {df.shape[0]:,}개")
print("="*60)

# 연결 종료
engine.dispose()
