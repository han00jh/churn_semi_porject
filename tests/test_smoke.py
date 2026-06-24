"""
스모크 테스트 — 데이터 로드 · 차트 라우트 · 모델 서빙 · AI 데모 모드.
키/DB 없이(데모 모드) 전부 통과해야 한다.

실행:  pytest -q
"""
import pandas as pd
import pytest


# ── 데이터 로드 ──
def test_data_loads():
    import churn_main
    df = churn_main.get_churn_df()
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 30000
    assert "target" in df.columns
    assert "tenure" in df.columns           # BOM 회귀 방지 (첫 컬럼)


# ── 차트 데이터 함수 5개 ──
@pytest.mark.parametrize("fn", ["get_topic1", "get_topic2", "get_topic3", "get_topic4", "get_topic5"])
def test_topic_functions(fn):
    import churn_main
    data = getattr(churn_main, fn)()
    assert set(["h1", "h2", "h3", "h4"]).issubset(data)
    for h in ["h1", "h2", "h3", "h4"]:
        assert "chart_type" in data[h]


# ── 차트 라우트 ──
@pytest.mark.parametrize("topic", ["A", "B", "C", "D", "E"])
def test_get_all_data(client, topic):
    r = client.post("/get_all_data", json={"topic": topic})
    assert r.status_code == 200
    j = r.get_json()
    assert all(k in j for k in ("h1", "h2", "h3", "h4"))


def test_index(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "predictSection" in r.get_data(as_text=True)


# ── 모델 서빙 ──
def test_model_metrics(client):
    r = client.get("/model_metrics")
    assert r.status_code == 200
    j = r.get_json()
    assert j.get("ready") is True
    assert j["best"]["roc_auc"] > 0.8           # 학습 모델 품질 회귀 방지


def test_predict(client):
    r = client.post("/predict", json={"overrides": {"cs_calls": 8, "tenure": 10}})
    assert r.status_code == 200
    j = r.get_json()
    assert 0.0 <= j["churn_probability"] <= 1.0
    assert j["grade"] in ("A", "B", "C", "D")
    assert len(j["factors"]) >= 1


def test_predict_sample(client):
    r = client.get("/predict_sample?seed=1")
    assert r.status_code == 200
    j = r.get_json()
    assert j["customer_id"].startswith("CUST-")
    assert "churn_percent" in j


def test_risk_list(client):
    r = client.get("/risk_list?n=10")
    assert r.status_code == 200
    j = r.get_json()
    assert j["count"] == 10
    # 가장 위험한 고객이 평균(11%)보다 훨씬 높아야 한다
    assert j["items"][0]["churn_percent"] > 50


# ── AI 데모 모드 ──
def test_ai_demo_mode(client):
    chart = client.post("/get_all_data", json={"topic": "A"}).get_json()
    r = client.post("/ai_topic_insight", json={"topic": "A", "graph_data": chart})
    assert r.status_code == 200
    j = r.get_json()
    for k in ("summary", "strategy", "forecast"):
        assert k in j and "number" in j[k]


def test_ai_usage_demo(client):
    j = client.get("/ai_usage").get_json()
    assert j["demo"] is True            # 키 없는 환경에서 데모 모드여야 함
