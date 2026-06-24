# kpi 관련 전체 흐름 정리(총 2가지)
# =========================================
# # 1. 모델링 파일의 맨 끝에 추가하기.
# =========================================
# import kpi
#
# kpi.save(0.87, 0.76, "RandomForest")
# #        ↑↑↑↑  ↑↑↑↑  ↑↑↑↑↑↑↑↑↑↑↑↑
# #        재료1  재료2  재료3
# #        best_f1 best_recall best_model 로 들어감
# ======================================
# 2. python  # kpi.py. <- 현재 파일에서 저 값을 받아서 플라스크 연결해서 브라우저에 html에 연결해서 띄우기.
# =======================================
#
# def save(best_f1, best_recall, best_model):
#
#
# # best_f1     = 0.87   ← 모델링에서 넘어온 재료
# # best_recall = 0.76   ← 모델링에서 넘어온 재료
# # best_model  = "RandomForest" ← 모델링에서 넘어온 재료
#
# # 이 재료로 DB에 저장
# # 완료 메시지 출력
#





# ============================================================
# 📁 kpi.py
# 역할: 모델링 파일에서 best 모델 성능을 받아 Oracle DB에 저장
#
# 사용법:
#   모델링 파일 맨 마지막 줄에 아래 두 줄 추가
#   import kpi
#   kpi.save(best_f1, best_recall, best_model)
#
# ⚠️ 이 파일은 모델링 파일과 같은 폴더에 있어야 해요!
# ============================================================

from sqlalchemy import create_engine, text
from dotenv    import load_dotenv
from datetime  import datetime
import os

def save(best_f1, best_recall, best_model):
    """
    모델링 파일에서 best 모델 성능을 받아 DB에 저장

    매개변수:
        best_f1     : 제일 높은 f1 값      (예: 0.8745)
        best_recall : 그 모델의 recall 값  (예: 0.7623)
        best_model  : 그 모델 이름         (예: "RandomForestClassifier")
    """

    # ① .env 파일에서 DB_URL 읽기
    load_dotenv()
    DB_URL = os.getenv("DB_URL")

    # ② DB 연결
    engine = create_engine(DB_URL)

    # ③ KPI_RESULT 테이블에 저장
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO KPI_RESULT (모델명, F1_SCORE, RECALL, 실행일자)
            VALUES (:model, :f1, :recall, SYSDATE)
        """), {
            "model"  : best_model,
            "f1"     : round(best_f1,     4),
            "recall" : round(best_recall, 4)
        })

    # ④ 저장 완료 출력
    print("=" * 50)
    print("✅ KPI DB 저장 완료!")
    print(f"   모델명   : {best_model}")
    print(f"   F1 Score : {best_f1:.4f}")
    print(f"   Recall   : {best_recall:.4f}")
    print(f"   저장시각 : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    engine.dispose()
