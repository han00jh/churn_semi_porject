"""
============================================================        => 계속 수정할 예정.
churn_main.py
Flask 경로: churn_app.py (프로젝트 루트)

[데이터 흐름]
  버튼 클릭 (A~E)
  → JS fetch("/get_all_data", {topic:"A"})
  → Flask → get_topic1~5() → CHURN 테이블 (DB실패시 CSV)
  → JSON {h1,h2,h3,h4} 반환 → JS Chart.js 렌더링

  버튼 클릭 후 AI 자동 분석
  → JS fetch("/ai_topic_summary", {topic:"A", graph_data:{...}})
  → Flask → AIService → 현황요약/핵심대책/예상이익 3개 동시 반환

[파일 구조]
  churn_app.py          ← 이 파일
  churn_ai.py           ← AI 서비스 (get_topic_insight 메서드 추가 필요)
  templates/
    dashboard_08.html
  static/
    css/style.css        ← 기존 (사이드바/topbar/kpi/footer 스타일)
    css/chart_topic.css  ← 버튼E + 차트카드 내부 전용
    js/app.js            ← 차트·버튼·AI 전체 동작

[수정 포인트]
  - DB 연결  → .env 의 DB_URL
  - CSV 경로 → get_churn_df() 내 "churn.csv"
  - 포트번호 → 하단 app.run()
============================================================
"""
print("🔥 churn_main.py 실행 중 🔥")

from flask      import Flask, render_template, request, jsonify
from dotenv     import load_dotenv
from pathlib    import Path
import pandas as pd
import os

from churn_ai      import AIService
import model_service as ms

load_dotenv()

# ── 경로 (실행 위치와 무관하게 __file__ 기준) ──
BASE_DIR = Path(__file__).resolve().parent          # web/
ROOT_DIR = BASE_DIR.parent                           # 프로젝트 루트
CSV_PATH = ROOT_DIR / "data" / "churn" / "featured" / "churn.csv"

# ── 환경설정 (전부 선택 — 없어도 데모 모드로 구동) ──
DB_URL = os.getenv("DB_URL") or None
DEBUG  = os.getenv("FLASK_DEBUG", "0").lower() in ("1", "true", "yes")
HOST   = os.getenv("HOST", "127.0.0.1")
PORT   = int(os.getenv("PORT", "6001"))

app = Flask(__name__)

# ── AIService 안전 초기화 (키 없으면 데모 모드, 절대 기동 실패하지 않음) ──
try:
    ai = AIService()
except Exception as e:
    print(f"⚠️ AIService 초기화 실패 → 데모 모드: {e}")
    ai = AIService(demo=True)

# ── DB 엔진은 DB_URL 이 있을 때만 지연 생성 (없으면 CSV 우선) ──
_engine = None
def _get_engine():
    global _engine
    if _engine is None and DB_URL:
        from sqlalchemy import create_engine
        _engine = create_engine(DB_URL)
    return _engine


# ============================================================
# 공통 유틸 — CHURN 데이터 로드 (앱 기동 후 1회 캐시)
#   우선순위: DB_URL 있으면 Oracle → 실패 시 CSV → 그래도 실패면 명확한 에러
# ============================================================
_df_cache = None

def get_churn_df():
    """CHURN 데이터 → pandas DataFrame (DB 우선, CSV fallback)."""
    global _df_cache
    if _df_cache is not None:
        return _df_cache

    engine = _get_engine()
    if engine is not None:
        try:
            with engine.connect() as conn:
                df = pd.read_sql("SELECT * FROM CHURN", conn)
                df.columns = df.columns.str.strip().str.lower()
            print("✅ CHURN 테이블 로드 성공 (DB)")
            _df_cache = df
            return df
        except Exception as e:
            print(f"⚠️ DB 로드 실패 → CSV fallback: {e}")

    # CSV fallback (기본 경로) — utf-8-sig 로 BOM 안전 제거
    df = pd.read_csv(CSV_PATH, encoding="utf-8-sig")
    df.columns = df.columns.str.strip().str.lower()
    print(f"✅ CHURN 데이터 로드 성공 (CSV: {CSV_PATH.name}, {len(df):,}행)")
    _df_cache = df
    return df


def decile_churn(df, col, q=10):
    """
    col 기준 q분위 나누기 → 각 분위 해지율/고객수 계산
    반환: labels(D1~D10), values(%), counts(명), avg(전체평균%)
    """
    d = df.copy()
    d['_q'] = pd.qcut(d[col], q=q, labels=False, duplicates='drop')
    r = (d.groupby('_q')['target']
          .agg(cr=lambda x: round(x.mean() * 100, 2), cnt='count')
          .reset_index())
    return (
        [f"D{int(v)+1}" for v in r['_q']],
        r['cr'].tolist(),
        r['cnt'].tolist(),
        round(df['target'].mean() * 100, 2)
    )


def binary_churn(df, col, label_map):
    """
    0/1 이진 컬럼 → 그룹별 해지율
    label_map 예: {0:"일반 고객", 1:"상담 상위 10%"}
    """
    r = (df.groupby(col)['target']
          .agg(cr=lambda x: round(x.mean() * 100, 2), cnt='count')
          .reset_index())
    return (
        [label_map.get(v, str(v)) for v in r[col]],
        r['cr'].tolist(),
        r['cnt'].tolist(),
        round(df['target'].mean() * 100, 2)
    )


def cross_churn(df, col1, col2, q1=None, q2=None):
    """
    두 컬럼 교차 해지율 (클러스터드바/멀티라인용)
    q1/q2 지정 시 해당 컬럼을 분위로 나눔
    반환: labels, series({Q1:[...], Q2:[...]}), avg
    """
    d = df.copy()
    if q1:
        d[col1] = pd.qcut(d[col1], q=q1, labels=False, duplicates='drop')
    if q2:
        d[col2] = pd.qcut(d[col2], q=q2, labels=False, duplicates='drop')
    pivot = (d.groupby([col1, col2])['target']
              .mean().mul(100).round(2)
              .unstack(col2).fillna(0))
    return (
        [f"Q{int(v)+1}" for v in pivot.index],
        {f"Q{int(c)+1}": pivot[c].tolist() for c in pivot.columns},
        round(df['target'].mean() * 100, 2)
    )


# ============================================================
# 주제형 데이터 함수 5개 — CHURN 테이블
# ============================================================

def get_topic1():
    """
    주제A 불만고객형
    h1: cs_calls 실제값별 해지율        (bar_line)
    h2: cs_per_100min 10분위별 해지율   (line)
    h3: cs_ratio 10분위별 해지율        (horizontal_bar)
    h4: cs_top10_flag 비교              (compare_bar)
    """
    df  = get_churn_df()
    avg = round(df['target'].mean() * 100, 2)

    r1 = (df.groupby('cs_calls')['target']
            .agg(cr=lambda x: round(x.mean()*100, 2), cnt='count')
            .reset_index())
    h1 = {"chart_type":"bar_line", "title":"상담 건수별 해지율",
          "labels":[f"{v}회" for v in r1['cs_calls'].tolist()],
          "values":r1['cr'].tolist(), "counts":r1['cnt'].tolist(),
          "avg":avg, "x_label":"상담 전화 횟수", "topic":"A"}

    lbl,val,cnt,avg2 = decile_churn(df, 'cs_per_100min')
    h2 = {"chart_type":"line", "title":"100분당 상담건수 분위별 해지율",
          "labels":lbl, "values":val, "counts":cnt, "avg":avg2,
          "x_label":"cs_per_100min 분위 (낮음→높음)", "topic":"A"}

    lbl,val,cnt,avg3 = decile_churn(df, 'cs_ratio')
    h3 = {"chart_type":"horizontal_bar", "title":"통화 대비 상담비율 분위별 해지율",
          "labels":lbl, "values":val, "counts":cnt, "avg":avg3,
          "x_label":"해지율 (%)", "topic":"A"}

    lbl,val,cnt,avg4 = binary_churn(df, 'cs_top10_flag',
                                     {0:"일반 고객", 1:"상담 상위 10%"})
    h4 = {"chart_type":"compare_bar", "title":"상담 상위 10% vs 일반 고객 해지율",
          "labels":lbl, "values":val, "counts":cnt, "avg":avg4,
          "x_label":"고객 그룹", "topic":"A"}

    return {"h1":h1, "h2":h2, "h3":h3, "h4":h4}


def get_topic2():
    """
    주제B 이용강도형
    h1: total_minutes 10분위 (bar)
    h2: avg_rate 10분위      (line)
    h3: rate_std 10분위      (bar)
    h4: usage_q × avg_rate_q (clustered_bar)
    """
    df = get_churn_df()
    lbl,val,cnt,avg = decile_churn(df, 'total_minutes')
    h1 = {"chart_type":"bar", "title":"총 사용량 분위별 해지율",
          "labels":lbl, "values":val, "counts":cnt, "avg":avg,
          "x_label":"total_minutes 분위 (낮음→높음)", "topic":"B"}

    lbl,val,cnt,avg = decile_churn(df, 'avg_rate')
    h2 = {"chart_type":"line", "title":"평균 요금 분위별 해지율",
          "labels":lbl, "values":val, "counts":cnt, "avg":avg,
          "x_label":"avg_rate 분위 (낮음→높음)", "topic":"B"}

    lbl,val,cnt,avg = decile_churn(df, 'rate_std')
    h3 = {"chart_type":"bar", "title":"요금 변동성 분위별 해지율",
          "labels":lbl, "values":val, "counts":cnt, "avg":avg,
          "x_label":"rate_std 분위 (낮음→높음)", "topic":"B"}

    lbl,series,avg = cross_churn(df, 'usage_q', 'avg_rate', q2=4)
    h4 = {"chart_type":"clustered_bar", "title":"사용량 × 평균요금 교차 해지율",
          "labels":lbl, "series":series, "avg":avg,
          "x_label":"사용량 분위 (usage_q)", "topic":"B"}

    return {"h1":h1, "h2":h2, "h3":h3, "h4":h4}


def get_topic3():
    """
    주제C 시간대별 패턴
    h1: night_ratio 10분위   (bar)
    h2: night_day_diff 10분위(line)
    h3: time_ratio_std 10분위(bar)
    h4: day_heavy_flag 비교  (compare_bar)
    """
    df = get_churn_df()
    lbl,val,cnt,avg = decile_churn(df, 'night_ratio')
    h1 = {"chart_type":"bar", "title":"밤 통화 비중 분위별 해지율",
          "labels":lbl, "values":val, "counts":cnt, "avg":avg,
          "x_label":"night_ratio 분위 (낮음→높음)", "topic":"C"}

    lbl,val,cnt,avg = decile_churn(df, 'night_day_diff')
    h2 = {"chart_type":"line", "title":"밤-낮 통화 차이 분위별 해지율",
          "labels":lbl, "values":val, "counts":cnt, "avg":avg,
          "x_label":"night_day_diff 분위 (낮음→높음)", "topic":"C"}

    lbl,val,cnt,avg = decile_churn(df, 'time_ratio_std')
    h3 = {"chart_type":"bar", "title":"시간대 집중도 분위별 해지율",
          "labels":lbl, "values":val, "counts":cnt, "avg":avg,
          "x_label":"time_ratio_std 분위 (낮음→높음)", "topic":"C"}

    lbl,val,cnt,avg = binary_churn(df, 'day_heavy_flag',
                                    {0:"일반 사용", 1:"낮 집중 (상위 25%)"})
    h4 = {"chart_type":"compare_bar", "title":"낮 집중 사용 고객 vs 일반 해지율",
          "labels":lbl, "values":val, "counts":cnt, "avg":avg,
          "x_label":"고객 그룹", "topic":"C"}

    return {"h1":h1, "h2":h2, "h3":h3, "h4":h4}


def get_topic4():
    """
    주제D 장기사용형
    h1: tenure 10분위          (bar)
    h2: usage_q × tenure_q 교차(multi_line)
    h3: long_high_usage_flag   (compare_bar)
    h4: tenure_log 10분위      (line)
    """
    df = get_churn_df()
    lbl,val,cnt,avg = decile_churn(df, 'tenure')
    h1 = {"chart_type":"bar", "title":"가입기간 분위별 해지율",
          "labels":lbl, "values":val, "counts":cnt, "avg":avg,
          "x_label":"tenure 분위 (낮음→높음)", "topic":"D"}

    lbl,series,avg = cross_churn(df, 'usage_q', 'tenure_q')
    h2 = {"chart_type":"multi_line", "title":"사용량 × 가입기간 교차 해지율",
          "labels":lbl, "series":series, "avg":avg,
          "x_label":"사용량 분위 (usage_q)", "topic":"D"}

    lbl,val,cnt,avg = binary_churn(df, 'long_high_usage_flag',
                                    {0:"일반 고객", 1:"고사용+장기 고객"})
    h3 = {"chart_type":"compare_bar", "title":"고사용+장기 고객 vs 일반 해지율",
          "labels":lbl, "values":val, "counts":cnt, "avg":avg,
          "x_label":"고객 그룹", "topic":"D"}

    lbl,val,cnt,avg = decile_churn(df, 'tenure_log')
    h4 = {"chart_type":"line", "title":"가입기간(로그) 분위별 해지율",
          "labels":lbl, "values":val, "counts":cnt, "avg":avg,
          "x_label":"tenure_log 분위 (낮음→높음)", "topic":"D"}

    return {"h1":h1, "h2":h2, "h3":h3, "h4":h4}


def get_topic5():
    """
    주제E 행동패턴형
    h1: avg_rate × rate_std 교차(clustered_bar)
    h2: vm_binary 비교          (compare_bar)
    h3: vm_count_log 10분위     (line)
    h4: total_calls 10분위      (bar)
    """
    df = get_churn_df()
    lbl,series,avg = cross_churn(df, 'avg_rate', 'rate_std', q1=4, q2=4)
    h1 = {"chart_type":"clustered_bar", "title":"평균요금 × 요금변동성 교차 해지율",
          "labels":lbl, "series":series, "avg":avg,
          "x_label":"avg_rate 분위", "topic":"E"}

    lbl,val,cnt,avg = binary_churn(df, 'vm_binary', {0:"미사용", 1:"사용"})
    h2 = {"chart_type":"compare_bar", "title":"음성사서함 사용 여부별 해지율",
          "labels":lbl, "values":val, "counts":cnt, "avg":avg,
          "x_label":"음성사서함", "topic":"E"}

    lbl,val,cnt,avg = decile_churn(df, 'vm_count_log')
    h3 = {"chart_type":"line", "title":"음성사서함 횟수(로그) 분위별 해지율",
          "labels":lbl, "values":val, "counts":cnt, "avg":avg,
          "x_label":"vm_count_log 분위 (낮음→높음)", "topic":"E"}

    lbl,val,cnt,avg = decile_churn(df, 'total_calls')
    h4 = {"chart_type":"bar", "title":"총 통화횟수 분위별 해지율",
          "labels":lbl, "values":val, "counts":cnt, "avg":avg,
          "x_label":"total_calls 분위 (낮음→높음)", "topic":"E"}

    return {"h1":h1, "h2":h2, "h3":h3, "h4":h4}


# 주제 → 함수 매핑
TOPIC_MAP = {
    "A": get_topic1,
    "B": get_topic2,
    "C": get_topic3,
    "D": get_topic4,
    "E": get_topic5,
}

# 주제 한글명 (AI 프롬프트용)
TOPIC_NAME = {
    "A": "불만고객형 (상담 임계점 기반 위험 신호)",
    "B": "이용강도형 (몰입도 ↑ → 이탈 ↓)",
    "C": "시간대별 패턴 (밤 비중·패턴 불안정 → 위험)",
    "D": "장기사용형 (tenure 단독 약함, 상호작용 강함)",
    "E": "행동패턴형 (단조로운 고객이 먼저 떠난다)",
}


# ============================================================
# Flask 라우트
# ============================================================

@app.route("/")
def index():
    return render_template("dashboard_09.html")


@app.route("/get_all_data", methods=["POST"])
def get_all_data():
    """
    topic A~E → 해당 주제 차트 데이터 반환
    잘못된 topic 시 A로 fallback
    """
    topic = (request.json or {}).get("topic", "A")
    if topic not in TOPIC_MAP:
        topic = "A"
    print(f"📡 /get_all_data | topic={topic}")
    try:
        data = TOPIC_MAP[topic]()
        data["topic"] = topic
        return jsonify(data)
    except Exception as e:
        print(f"❌ /get_all_data 실패: {e}")
        return jsonify({"error": "데이터 로드 실패", "detail": str(e)}), 500


# ============================================================
# 예측 시스템 라우트 (모델 서빙)
# ============================================================

@app.route("/model_metrics")
def model_metrics():
    """학습된 모델 지표 (KPI 바 · 모델 카드용)."""
    if not ms.is_ready():
        return jsonify({"ready": False,
                        "message": "모델 미학습 — `python ml/train.py` 실행 필요"}), 200
    m = ms.load_metrics()
    m["ready"] = True
    m["meta"]  = ms.model_meta()
    return jsonify(m)


@app.route("/predict", methods=["POST"])
def predict():
    """
    고객 피처 일부(또는 전부)를 받아 이탈 확률·위험등급·핵심요인 반환.
    요청: {overrides: {cs_calls: 6, tenure: 30, ...}}  (부분 입력 허용)
    """
    if not ms.is_ready():
        return jsonify({"error": "model_unavailable",
                        "message": "모델 미학습 — `python ml/train.py` 실행 필요"}), 503
    body = request.json or {}
    overrides = body.get("overrides", body)   # overrides 키 없으면 본문 전체를 입력으로
    try:
        return jsonify(ms.predict(overrides))
    except Exception as e:
        print(f"❌ /predict 실패: {e}")
        return jsonify({"error": "predict_failed", "detail": str(e)}), 500


@app.route("/predict_sample")
def predict_sample():
    """데이터셋의 실제 고객 1명을 뽑아 예측 (입력 없이 '예측 체험')."""
    if not ms.is_ready():
        return jsonify({"error": "model_unavailable"}), 503
    seed = request.args.get("seed", type=int)
    try:
        return jsonify(ms.predict_sample(seed))
    except Exception as e:
        print(f"❌ /predict_sample 실패: {e}")
        return jsonify({"error": "predict_failed", "detail": str(e)}), 500


@app.route("/risk_list")
def risk_list():
    """이탈 확률 상위 N명 (Target List)."""
    if not ms.is_ready():
        return jsonify({"error": "model_unavailable"}), 503
    n = request.args.get("n", default=100, type=int)
    n = max(1, min(n, 500))
    try:
        return jsonify(ms.risk_list(n))
    except Exception as e:
        print(f"❌ /risk_list 실패: {e}")
        return jsonify({"error": "risk_list_failed", "detail": str(e)}), 500


@app.route("/ai_topic_insight", methods=["POST"])
def ai_topic_insight():
    """
    주제 버튼 클릭 시 AI 3종 동시 분석 반환
    요청: {topic:"A", graph_data:{h1:..., h2:..., h3:..., h4:...}}
    응답: {summary:{number,label,sub}, strategy:{...}, forecast:{...}, topic:"A", topic_name:"..."}

    AI가 보고 있는 주제와 차트 정보를 함께 반환해서
    프론트에서 "AI가 X 주제의 Y 차트를 분석 중" 표시 가능
    """
    body       = request.json or {}
    topic      = body.get("topic", "A")
    graph_data = body.get("graph_data", {})

    topic_name = TOPIC_NAME.get(topic, topic)
    print(f"🤖 /ai_topic_insight | topic={topic} ({topic_name})")

    # AIService의 get_topic_insight 호출
    # graph_data에 topic_name을 추가해서 AI가 컨텍스트를 알게 함
    graph_data["_topic_name"] = topic_name
    graph_data["_topic"]      = topic

    result = ai.get_topic_insight(
        topic      = topic,
        topic_name = topic_name,
        graph_data = graph_data,
    )

    result["topic"]      = topic
    result["topic_name"] = topic_name
    return jsonify(result)


# 기존 AI 라우트 유지 (churn_ai.py 호환성) — 본문 None 가드 추가
@app.route("/chat_insight", methods=["POST"])
def chat_insight():
    body = request.json or {}
    return jsonify(ai.get_insight(
        graph_data    = body.get("graph_data"),
        user_message  = body.get("message"),
        auto_mode     = body.get("auto_mode", False),
        mode          = body.get("mode"),
        hypothesis_id = body.get("hypothesis_id"),
    ))

@app.route("/ai_summary",  methods=["POST"])
def ai_summary():
    return jsonify(ai.get_summary((request.json or {}).get("graph_data")))

@app.route("/ai_strategy", methods=["POST"])
def ai_strategy():
    return jsonify(ai.get_strategy((request.json or {}).get("graph_data")))

@app.route("/ai_forecast", methods=["POST"])
def ai_forecast():
    return jsonify(ai.get_forecast((request.json or {}).get("graph_data")))

@app.route("/ai_status")
def ai_status():
    return jsonify(ai.check_connection())

@app.route("/ai_usage")
def ai_usage():
    """현재 API 사용 상태 조회 (푸터용)"""
    return jsonify(ai.get_api_status())

@app.route("/approve_claude", methods=["POST"])
def approve_claude():
    """유저가 Claude 전환 팝업에서 확인 눌렀을 때"""
    ai.approve_claude()
    return jsonify({"success": True})


if __name__ == "__main__":
    print(f"🌐 http://{HOST}:{PORT}  (debug={DEBUG})")
    app.run(host=HOST, port=PORT, debug=DEBUG)
