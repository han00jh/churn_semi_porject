# ============================================================
# 1️⃣ 환경 설정
# ============================================================
import os
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine,  String   , text, Integer, Float, Numeric
# from sqlalchemy.dialects.oracle import NUMBER,  FLOAT as ORA_FLOAT
# import sys
# print(sys.executable)



# ============================================================
# 2️⃣ 엔진 열기
# ============================================================
engine = create_engine("oracle+cx_oracle://it:0000@localhost:1521/xe")



# ============================================================
# 3. 경로에 맞게 데이터 로드 (CSV)해서 df에 담기
# ============================================================
BASE_DIR = Path(__file__).resolve().parent.parent      # file = churn_insert.py를 말함. 그 파일에서 최상위 폴더인 oneplus3까지 가야함.parent가 상위폴더로 가는 것. web -> oneplus3
CSV_PATH = BASE_DIR / "data" / "Churn" / "train.csv"   # oneplus3/data/Churn/train.csv
df = pd.read_csv(CSV_PATH)

# df = pd.read_csv(r"C:\IT\workspace_python\project\oneplus3\data\Churn\train.csv")

print("CSV 로드 완료:", df.shape)
print(df.columns)
df.info()



# ============================================================
# 4. Oracle DB 연결 - with으로 엔진 열고 닫고
# ============================================================
# engine = create_engine("oracle+cx_oracle://it:0000@localhost:1521/xe")
# conn = engine.connect()
with engine.begin() as conn:
    df.to_sql(
        name="TRAIN",      #### 테이블 명.
        con=conn,             # con=engine?D
        if_exists="replace",
        index=False,
        # method="multi",
        dtype={
            "ID": String(20),
            "가입일": Integer(),
            "음성사서함이용": Integer(),
            # float64 컬럼들: NUMBER(12, 4) 같은 방식으로 안전하게 저장
            "주간통화시간": Numeric(12,4),
            "주간통화요금": Numeric(12,4),
            "저녁통화시간": Numeric(12,4),
            "저녁통화요금": Numeric(12,4),                                  #NUMBER(12, 4)
            "밤통화시간": Numeric(12,4),
            "밤통화요금": Numeric(12,4),
            "주간통화횟수": Integer(),
            "저녁통화횟수": Integer(),
            "밤통화횟수": Integer(),
            "상담전화건수": Integer(),
            "전화해지여부": Integer(),
        }
    )




print("Oracle 저장 완료! (train 테이블 생성/적재 완료)")
#---------------------------------------------------------------------------------------------------이상무
