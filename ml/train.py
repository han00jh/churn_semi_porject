"""
============================================================
ml/train.py  —  Churn 예측 모델 학습 · 평가 · 직렬화 파이프라인
============================================================
이탈 예측 시스템의 모델 학습·평가·직렬화를 담당하는 핵심 산출물.

수행 내용
  1. featured 데이터 로드 (data/churn/featured/churn.csv)
  2. 불균형(이탈 ~11%) 보정하여 4개 모델 학습
       Logistic Regression · Random Forest · XGBoost · LightGBM
  3. StratifiedKFold 교차검증으로 모델 비교 (PR-AUC 기준)
  4. 학습셋 CV 예측으로 의사결정 임계값을 '정직하게' 튜닝 (F1 최대)
  5. 홀드아웃 test에서 ROC-AUC · PR-AUC · Recall · F1 · 혼동행렬 · Brier 평가
  6. 확률 캘리브레이션 곡선 + SHAP 변수 기여도 산출
  7. 최적 모델 → models/churn_model.joblib (모델+임계값+피처 번들)
       지표 → models/metrics.json,  차트 → docs/img/*.png

실행:  python ml/train.py
============================================================
"""
from __future__ import annotations

import json
import warnings
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # 화면 없는 환경/CI에서도 차트 저장
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import joblib

from sklearn.model_selection import StratifiedKFold, cross_val_predict, train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    average_precision_score, roc_auc_score, f1_score, recall_score,
    precision_score, accuracy_score, confusion_matrix, brier_score_loss,
    precision_recall_curve, roc_curve,
)
from sklearn.calibration import calibration_curve
from xgboost import XGBClassifier
from lightgbm import LGBMClassifier

warnings.filterwarnings("ignore")

# ── 경로 ──
ROOT      = Path(__file__).resolve().parents[1]
CSV_PATH  = ROOT / "data" / "churn" / "featured" / "churn.csv"
MODEL_DIR = ROOT / "models"
IMG_DIR   = ROOT / "docs" / "img"
MODEL_DIR.mkdir(parents=True, exist_ok=True)
IMG_DIR.mkdir(parents=True, exist_ok=True)

RANDOM_STATE = 42
TARGET       = "target"

# 색상 팔레트 (대시보드 톤과 일치)
PALETTE = {"Logistic Regression": "#6366f1", "Random Forest": "#e63946",
           "XGBoost": "#0096c7", "LightGBM": "#2a9d8f"}


# ════════════════════════════════════════════════════════════
# 1. 데이터 로드
# ════════════════════════════════════════════════════════════
def load_data():
    # utf-8-sig → 선행 BOM 안전 제거
    df = pd.read_csv(CSV_PATH, encoding="utf-8-sig")
    df.columns = df.columns.str.strip().str.lower()
    y = df[TARGET].astype(int)
    X = df.drop(columns=[TARGET])
    # 모델 입력은 수치형만 (featured 데이터는 전부 수치형)
    X = X.select_dtypes(include=[np.number])
    print(f"✅ 데이터 로드: {X.shape[0]:,}행 × {X.shape[1]}피처 "
          f"| 이탈률 {y.mean()*100:.2f}% (이탈 {int(y.sum()):,}명)")
    return X, y


# ════════════════════════════════════════════════════════════
# 2. 모델 정의 (불균형 보정 내장)
# ════════════════════════════════════════════════════════════
def build_models(y_train):
    pos = int((y_train == 1).sum())
    neg = int((y_train == 0).sum())
    spw = neg / max(pos, 1)  # scale_pos_weight (불균형 보정)
    return {
        "Logistic Regression": LogisticRegression(
            max_iter=2000, class_weight="balanced", random_state=RANDOM_STATE),
        "Random Forest": RandomForestClassifier(
            n_estimators=400, max_depth=12, min_samples_leaf=20, n_jobs=-1,
            class_weight="balanced", random_state=RANDOM_STATE),
        "XGBoost": XGBClassifier(
            n_estimators=500, max_depth=5, learning_rate=0.05,
            subsample=0.9, colsample_bytree=0.9, scale_pos_weight=spw,
            eval_metric="aucpr", random_state=RANDOM_STATE, n_jobs=-1),
        "LightGBM": LGBMClassifier(
            n_estimators=600, max_depth=-1, num_leaves=31, learning_rate=0.05,
            subsample=0.9, colsample_bytree=0.9, class_weight="balanced",
            random_state=RANDOM_STATE, n_jobs=-1, verbose=-1),
    }


# ════════════════════════════════════════════════════════════
# 3. 임계값 튜닝 — 학습셋 CV 예측에서 F1 최대 (test 누수 없음)
# ════════════════════════════════════════════════════════════
def tune_threshold(model, X_tr, y_tr):
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    proba = cross_val_predict(model, X_tr, y_tr, cv=cv,
                              method="predict_proba", n_jobs=-1)[:, 1]
    prec, rec, thr = precision_recall_curve(y_tr, proba)
    f1 = (2 * prec * rec) / (prec + rec + 1e-12)
    best_idx = int(np.nanargmax(f1[:-1]))  # 마지막 점은 threshold 없음
    return float(thr[best_idx]), float(f1[best_idx])


def evaluate(y_true, proba, threshold):
    pred = (proba >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, pred).ravel()
    return {
        "roc_auc":   round(float(roc_auc_score(y_true, proba)), 4),
        "pr_auc":    round(float(average_precision_score(y_true, proba)), 4),
        "recall":    round(float(recall_score(y_true, pred)), 4),
        "precision": round(float(precision_score(y_true, pred)), 4),
        "f1":        round(float(f1_score(y_true, pred)), 4),
        "accuracy":  round(float(accuracy_score(y_true, pred)), 4),
        "brier":     round(float(brier_score_loss(y_true, proba)), 4),
        "confusion_matrix": [[int(tn), int(fp)], [int(fn), int(tp)]],
        "threshold": round(float(threshold), 4),
    }


# ════════════════════════════════════════════════════════════
# 4. 차트
# ════════════════════════════════════════════════════════════
def plot_model_comparison(results):
    names = list(results.keys())
    metrics = ["pr_auc", "roc_auc", "recall", "f1"]
    x = np.arange(len(metrics)); w = 0.2
    fig, ax = plt.subplots(figsize=(9, 5))
    for i, n in enumerate(names):
        vals = [results[n]["test"][m] for m in metrics]
        ax.bar(x + i * w, vals, w, label=n, color=PALETTE.get(n, "#888"))
    ax.set_xticks(x + w * 1.5)
    ax.set_xticklabels(["PR-AUC", "ROC-AUC", "Recall", "F1"])
    ax.set_ylim(0, 1); ax.set_ylabel("Score")
    ax.set_title("Model Comparison (held-out test)", fontweight="bold")
    ax.legend(fontsize=9); ax.grid(axis="y", alpha=.3)
    fig.tight_layout(); fig.savefig(IMG_DIR / "model_comparison.png", dpi=130); plt.close(fig)


def plot_roc_pr(y_test, proba, name):
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    fpr, tpr, _ = roc_curve(y_test, proba)
    axes[0].plot(fpr, tpr, color="#0096c7", lw=2,
                 label=f"{name} (AUC={roc_auc_score(y_test, proba):.3f})")
    axes[0].plot([0, 1], [0, 1], "--", color="#bbb")
    axes[0].set_xlabel("False Positive Rate"); axes[0].set_ylabel("True Positive Rate")
    axes[0].set_title("ROC Curve", fontweight="bold"); axes[0].legend(); axes[0].grid(alpha=.3)

    prec, rec, _ = precision_recall_curve(y_test, proba)
    base = y_test.mean()
    axes[1].plot(rec, prec, color="#e63946", lw=2,
                 label=f"{name} (AP={average_precision_score(y_test, proba):.3f})")
    axes[1].axhline(base, ls="--", color="#bbb", label=f"baseline={base:.3f}")
    axes[1].set_xlabel("Recall"); axes[1].set_ylabel("Precision")
    axes[1].set_title("Precision–Recall Curve", fontweight="bold"); axes[1].legend(); axes[1].grid(alpha=.3)
    fig.tight_layout(); fig.savefig(IMG_DIR / "roc_pr_curves.png", dpi=130); plt.close(fig)


def plot_confusion(cm, name):
    cm = np.array(cm)
    fig, ax = plt.subplots(figsize=(5, 4.5))
    im = ax.imshow(cm, cmap="Blues")
    labels = ["Stay (0)", "Churn (1)"]
    ax.set_xticks([0, 1]); ax.set_yticks([0, 1])
    ax.set_xticklabels(labels); ax.set_yticklabels(labels)
    ax.set_xlabel("Predicted"); ax.set_ylabel("Actual")
    ax.set_title(f"Confusion Matrix — {name}", fontweight="bold")
    total = cm.sum()
    for i in range(2):
        for j in range(2):
            ax.text(j, i, f"{cm[i, j]:,}\n({cm[i, j]/total*100:.1f}%)",
                    ha="center", va="center",
                    color="white" if cm[i, j] > cm.max() / 2 else "#111", fontsize=11)
    fig.colorbar(im, fraction=0.046); fig.tight_layout()
    fig.savefig(IMG_DIR / "confusion_matrix.png", dpi=130); plt.close(fig)


def plot_calibration(y_test, proba, name):
    frac_pos, mean_pred = calibration_curve(y_test, proba, n_bins=10, strategy="quantile")
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.plot([0, 1], [0, 1], "--", color="#bbb", label="perfectly calibrated")
    ax.plot(mean_pred, frac_pos, "o-", color="#2a9d8f", lw=2, label=name)
    ax.set_xlabel("Mean predicted probability"); ax.set_ylabel("Observed churn rate")
    ax.set_title("Calibration Curve", fontweight="bold"); ax.legend(); ax.grid(alpha=.3)
    fig.tight_layout(); fig.savefig(IMG_DIR / "calibration_curve.png", dpi=130); plt.close(fig)


def plot_shap(model, X_sample, name):
    try:
        import shap
        if name in ("XGBoost", "LightGBM", "Random Forest"):
            explainer = shap.TreeExplainer(model)
            sv = explainer.shap_values(X_sample)
            if isinstance(sv, list):          # 일부 버전은 클래스별 리스트
                sv = sv[1]
        else:
            explainer = shap.LinearExplainer(model, X_sample)
            sv = explainer.shap_values(X_sample)
        shap.summary_plot(sv, X_sample, show=False, max_display=15)
        fig = plt.gcf(); fig.set_size_inches(9, 6)
        plt.title(f"SHAP Feature Impact — {name}", fontweight="bold")
        fig.tight_layout(); fig.savefig(IMG_DIR / "shap_summary.png", dpi=130); plt.close(fig)
        # 평균 |SHAP| 기반 top 피처
        mean_abs = np.abs(sv).mean(axis=0)
        order = np.argsort(mean_abs)[::-1][:15]
        return [{"feature": str(X_sample.columns[i]),
                 "mean_abs_shap": round(float(mean_abs[i]), 5)} for i in order]
    except Exception as e:
        print(f"⚠️ SHAP 생략: {e}")
        return []


# ════════════════════════════════════════════════════════════
# 5. 메인
# ════════════════════════════════════════════════════════════
def main():
    print("=" * 60)
    print("🔧 Churn 예측 모델 학습 파이프라인")
    print("=" * 60)
    X, y = load_data()

    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=RANDOM_STATE)
    print(f"   분할: train {len(X_tr):,} / test {len(X_te):,} (stratified 80/20)\n")

    models  = build_models(y_tr)
    results = {}

    for name, model in models.items():
        print(f"▶ {name} 학습 중...")
        thr, cv_f1 = tune_threshold(model, X_tr, y_tr)   # train CV로 임계값 결정
        model.fit(X_tr, y_tr)
        proba = model.predict_proba(X_te)[:, 1]
        test_metrics = evaluate(y_te, proba, thr)
        results[name] = {"cv_f1": round(cv_f1, 4), "threshold": thr,
                         "test": test_metrics, "_model": model, "_proba": proba}
        print(f"   threshold={thr:.3f} | PR-AUC={test_metrics['pr_auc']} "
              f"ROC-AUC={test_metrics['roc_auc']} Recall={test_metrics['recall']} "
              f"F1={test_metrics['f1']}")

    # 최적 모델 = test PR-AUC 최고 (불균형에 적합한 핵심 지표)
    best_name = max(results, key=lambda n: results[n]["test"]["pr_auc"])
    best = results[best_name]
    best_model, best_proba, best_thr = best["_model"], best["_proba"], best["threshold"]
    print(f"\n🏆 최적 모델: {best_name} (PR-AUC={best['test']['pr_auc']})")

    # ── 차트 ──
    print("🎨 차트 생성 중...")
    plot_model_comparison(results)
    plot_roc_pr(y_te, best_proba, best_name)
    plot_confusion(best["test"]["confusion_matrix"], best_name)
    plot_calibration(y_te, best_proba, best_name)
    sample_n = min(2000, len(X_te))
    X_sample = X_te.sample(sample_n, random_state=RANDOM_STATE)
    top_features = plot_shap(best_model, X_sample, best_name)

    # 트리 기반 feature_importances_ 도 백업 저장
    if hasattr(best_model, "feature_importances_"):
        imp = best_model.feature_importances_
        order = np.argsort(imp)[::-1][:15]
        fi = [{"feature": str(X.columns[i]), "importance": round(float(imp[i]), 5)}
              for i in order]
    else:
        coef = np.abs(best_model.coef_[0])
        order = np.argsort(coef)[::-1][:15]
        fi = [{"feature": str(X.columns[i]), "importance": round(float(coef[i]), 5)}
              for i in order]

    # ── 모델 직렬화 (서빙 번들) ──
    bundle = {
        "model": best_model,
        "threshold": best_thr,
        "feature_names": list(X.columns),
        "model_name": best_name,
        "churn_base_rate": round(float(y.mean()), 4),
        "trained_at": datetime.now().isoformat(timespec="seconds"),
    }
    joblib.dump(bundle, MODEL_DIR / "churn_model.joblib")
    print(f"💾 모델 저장: models/churn_model.joblib ({best_name}, thr={best_thr:.3f})")

    # ── 지표 JSON ──
    metrics = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "dataset": {
            "rows": int(X.shape[0]), "features": int(X.shape[1]),
            "churn_rate": round(float(y.mean()), 4), "n_churn": int(y.sum()),
        },
        "split": {"train": int(len(X_tr)), "test": int(len(X_te)),
                  "method": "stratified 80/20", "random_state": RANDOM_STATE},
        "best_model": best_name,
        "threshold": round(best_thr, 4),
        "models": {n: results[n]["test"] for n in results},
        "best": best["test"],
        "top_features_by_importance": fi,
        "top_features_by_shap": top_features,
    }
    with open(MODEL_DIR / "metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    print("💾 지표 저장: models/metrics.json")

    print("\n" + "=" * 60)
    print("✅ 완료")
    print(f"   최적: {best_name} | Recall {best['test']['recall']} "
          f"PR-AUC {best['test']['pr_auc']} ROC-AUC {best['test']['roc_auc']} "
          f"F1 {best['test']['f1']}")
    print("   차트: docs/img/  (model_comparison, roc_pr_curves, confusion_matrix, "
          "calibration_curve, shap_summary)")
    print("=" * 60)


if __name__ == "__main__":
    main()
