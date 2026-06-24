"""
============================================================
model_service.py  —  학습된 이탈 예측 모델 서빙 레이어
============================================================
ml/train.py 가 만든 번들(models/churn_model.joblib)을 로드해
Flask 라우트(/predict · /predict_sample · /risk_list · /model_metrics)에
필요한 예측·리스크 스코어링·설명 기능을 제공한다.

런타임 의존: joblib + scikit-learn(+lightgbm) + pandas  (SHAP 불필요)
설명(factors)은 학습 시 저장한 글로벌 중요 피처 + 고객값 vs 모집단 중앙값
비교로 생성하므로 요청 시 추가 의존성이 없다.
============================================================
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import joblib

ROOT       = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "models" / "churn_model.joblib"
METRICS_PATH = ROOT / "models" / "metrics.json"
CSV_PATH   = ROOT / "data" / "churn" / "featured" / "churn.csv"

# 위험 등급 밴드 (이탈 확률 기준) — 대시보드 A~D 등급과 일치
GRADE_BANDS = [
    ("A", 0.50, "최고위험", "#e63946"),
    ("B", 0.30, "고위험",   "#f4a261"),
    ("C", 0.15, "주의",     "#0096c7"),
    ("D", 0.00, "안정",     "#2a9d8f"),
]

# 고객에게 보여줄 핵심 피처의 한글 라벨
FEATURE_LABEL = {
    "cs_calls": "상담 전화 횟수", "tenure": "가입 기간", "day_minutes": "주간 통화시간",
    "day_charge": "주간 통화요금", "eve_charge": "저녁 통화요금", "night_charge": "밤 통화요금",
    "avg_rate": "평균 요금단가", "rate_std": "요금 변동성", "total_minutes": "총 사용량",
    "total_calls": "총 통화횟수", "vm_count": "음성사서함 횟수", "day_rate": "주간 요금단가",
    "eve_rate": "저녁 요금단가", "night_rate": "밤 요금단가", "cs_ratio": "통화대비 상담비율",
    "night_ratio": "밤 통화 비중", "day_calls": "주간 통화횟수", "eve_calls": "저녁 통화횟수",
    "night_calls": "밤 통화횟수", "cs_per_100min": "100분당 상담건수",
}


class ModelUnavailable(RuntimeError):
    """모델 번들이 없을 때 (ml/train.py 미실행)."""


@lru_cache(maxsize=1)
def _bundle():
    if not MODEL_PATH.exists():
        raise ModelUnavailable(
            f"모델이 없습니다: {MODEL_PATH}. 먼저 `python ml/train.py` 를 실행하세요.")
    return joblib.load(MODEL_PATH)


@lru_cache(maxsize=1)
def _frame() -> pd.DataFrame:
    df = pd.read_csv(CSV_PATH, encoding="utf-8-sig")
    df.columns = df.columns.str.strip().str.lower()
    return df


@lru_cache(maxsize=1)
def _defaults() -> dict:
    """피처별 모집단 중앙값 — 부분 입력 시 빈 칸을 채우는 '평균 고객' 기준선."""
    df = _frame()
    feats = _bundle()["feature_names"]
    return {f: float(df[f].median()) for f in feats}


def is_ready() -> bool:
    try:
        _bundle(); return True
    except Exception:
        return False


def model_meta() -> dict:
    b = _bundle()
    return {"model_name": b["model_name"], "threshold": round(float(b["threshold"]), 4),
            "n_features": len(b["feature_names"]), "trained_at": b.get("trained_at")}


def grade_for(prob: float) -> dict:
    for letter, lo, name, color in GRADE_BANDS:
        if prob >= lo:
            return {"grade": letter, "name": name, "color": color}
    return {"grade": "D", "name": "안정", "color": "#2a9d8f"}


def _top_factors(row: dict, k: int = 5) -> list[dict]:
    """글로벌 중요 피처 중 상위 k개에 대해 고객값 vs 모집단 중앙값 비교."""
    metrics  = load_metrics()
    feats    = [f["feature"] for f in metrics.get("top_features_by_shap", [])][:k] \
               or [f["feature"] for f in metrics.get("top_features_by_importance", [])][:k]
    defaults = _defaults()
    out = []
    for f in feats:
        val = float(row.get(f, defaults.get(f, 0.0)))
        med = defaults.get(f, 0.0)
        direction = "high" if val > med * 1.05 else ("low" if val < med * 0.95 else "mid")
        out.append({
            "feature": f, "label": FEATURE_LABEL.get(f, f),
            "value": round(val, 2), "population_median": round(med, 2),
            "direction": direction,
        })
    return out


def predict(overrides: dict | None = None) -> dict:
    """
    overrides: 일부 피처 값 dict (없으면 '평균 고객' 기준선).
    반환: 이탈 확률 · 위험 등급 · 임계값 · 핵심 요인.
    """
    b = _bundle()
    feats   = b["feature_names"]
    base    = _defaults().copy()
    if overrides:
        for k, v in overrides.items():
            kk = str(k).strip().lower()
            if kk in base:
                try: base[kk] = float(v)
                except (TypeError, ValueError): pass
    X = pd.DataFrame([[base[f] for f in feats]], columns=feats)
    prob = float(b["model"].predict_proba(X)[:, 1][0])
    g = grade_for(prob)
    return {
        "churn_probability": round(prob, 4),
        "churn_percent": round(prob * 100, 1),
        "threshold": round(float(b["threshold"]), 4),
        "will_churn": bool(prob >= b["threshold"]),
        "grade": g["grade"], "grade_name": g["name"], "grade_color": g["color"],
        "model_name": b["model_name"],
        "factors": _top_factors(base),
        "inputs": {f: round(float(base[f]), 4) for f in feats},
    }


def predict_sample(seed: int | None = None) -> dict:
    """데이터셋에서 실제 고객 1명을 뽑아 예측 (입력 없이 '예측 체험')."""
    df = _frame()
    row = df.sample(1, random_state=seed) if seed is not None else df.sample(1)
    idx = int(row.index[0])
    feats = _bundle()["feature_names"]
    overrides = {f: float(row.iloc[0][f]) for f in feats}
    res = predict(overrides)
    res["customer_id"] = f"CUST-{idx:05d}"
    res["actual_churn"] = int(row.iloc[0]["target"]) if "target" in row.columns else None
    return res


@lru_cache(maxsize=1)
def _scored() -> pd.DataFrame:
    """전체 고객 이탈 확률 스코어링 (캐시)."""
    df = _frame().copy()
    b = _bundle()
    feats = b["feature_names"]
    df["_prob"] = b["model"].predict_proba(df[feats])[:, 1]
    return df


def risk_list(n: int = 100) -> dict:
    """이탈 확률 상위 n명 (Target List)."""
    df = _scored().sort_values("_prob", ascending=False).head(n)
    feats_show = ["cs_calls", "tenure", "total_minutes", "avg_rate"]
    items = []
    for idx, r in df.iterrows():
        prob = float(r["_prob"]); g = grade_for(prob)
        items.append({
            "customer_id": f"CUST-{int(idx):05d}",
            "churn_percent": round(prob * 100, 1),
            "grade": g["grade"], "grade_color": g["color"],
            **{f: round(float(r[f]), 2) for f in feats_show if f in r},
            "actual_churn": int(r["target"]) if "target" in r else None,
        })
    return {"count": len(items), "items": items}


@lru_cache(maxsize=1)
def load_metrics() -> dict:
    if not METRICS_PATH.exists():
        return {}
    with open(METRICS_PATH, encoding="utf-8") as f:
        return json.load(f)
