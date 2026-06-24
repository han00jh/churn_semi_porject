import pandas as pd
from sqlalchemy import create_engine

engine = create_engine("oracle+cx_oracle://it:0000@localhost:1521/xe")

df = pd.read_csv(r"C:\IT\workspace_python\_Project\etc\data\Churn\train.csv")

with engine.begin() as conn:
    df.to_sql("TRAIN", conn, if_exists="append", index=False)

print("완료")