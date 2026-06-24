"""
============================================================
ml/train.py  —  Churn 예측 모델 학습·평가·직렬화 (엄밀 검증 파이프라인)
============================================================
이탈 예측 시스템의 모델링 핵심. "점수를 높이는" 것보다 "점수가 타당한가"를
먼저 검증하는 분석 전문가 워크플로우를 그대로 코드화한다.

엄밀성 설계
  0. 누수 진단      — 중복행 / 타깃 상관 / 동일피처-다른타깃 검사 후 기록
  1. 누수 안전 피처  — 전수 데이터로 산출된 전도적(transductive) 분위·플래그 피처와
                       완전중복(r=1.0) 피처를 제외 (test 정보 누출 차단 + 잡음 제거)
  2. 견고한 검증     — RepeatedStratifiedKFold(5×2)로 PR-AUC/ROC mean±std (단일분할 의존 X)
  3. 불균형 보정     — class_weight / scale_pos_weight
  4. 확률 보정       — isotonic CalibratedClassifierCV → 신뢰 가능한 '이탈 확률'
  5. 임계값 선택     — dev OOF(교차예측)에서 F1 최대 (test 누수 없이)
  6. 정직한 보고     — 과적합 갭·CV 분산·보정 전후 Brier 까지 metrics.json 기록

실행:  python ml/train.py
============================================================
"""
from __future__ import annotations

import json
import warnings
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import joblib

from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import (
    StratifiedKFold, RepeatedStratifiedKFold, cross_val_score,
    cross_val_predict, train_test_split,
)
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.metrics import (
    average_precision_score, roc_auc_score, f1_score, recall_score,
    precision_score, accuracy_score, confusion_matrix, brier_score_loss,
    precision_recall_curve, roc_curve,
)
from xgboost import XGBClassifier
from lightgbm import LGBMClassifier

warnings.filterwarnings("ignore")

ROOT      = Path(__file__).resolve().parents[1]
CSV_PATH  = ROOT / "data" / "churn" / "featured" / "churn.csv"
MODEL_DIR = ROOT / "models"
IMG_DIR   = ROOT / "docs" / "img"
MODEL_DIR.mkdir(parents=True, exist_ok=True)
IMG_DIR.mkdir(parents=True, exist_ok=True)

RANDOM_STATE = 42
TARGET       = "target"
PALETTE = {"Logistic Regression": "#6366f1", "Random Forest": "#e63946",
           "XGBoost": "#0096c7", "LightGBM": "#2a9d8f"}

# 누수 안전성: 전수 데이터 분위/플래그(전도적) + 완전중복 피처 제외
#  · 분위·플래그는 transform 시 test 분포 정보를 사용 → 전도적 누수 + 실험상 잡음
#  · cs_ratio 는 cs_per_100min 과 r=1.000 (완전중복)
DROP_TRANSDUCTIVE = ["usage_q", "tenure_q", "cs_top10_flag",
                     "day_heavy_flag", "long_high_usage_flag"]
DROP_REDUNDANT    = ["cs_ratio"]


# ════════════════════════════════════════════════════════════
# 0. 데이터 로드 + 누수 진단
# ════════════════════════════════════════════════════════════
def load_and_audit():
    df = pd.read_csv(CSV_PATH, encoding="utf-8-sig")
    df.columns = df.columns.str.strip().str.lower()
    y = df[TARGET].astype(int)
    X_all = df.drop(columns=[TARGET]).select_dtypes(include=[np.number])

    # 누수 진단
    dup_rows = int(df.duplicated().sum())
    dup_feat = int(X_all.duplicated().sum())
    max_corr = float(X_all.apply(lambda c: abs(np.corrcoef(c, y)[0, 1]) if c.std() > 0 else 0).max())
    audit = {
        "duplicate_rows": dup_rows,
        "duplicate_feature_rows": dup_feat,
        "max_abs_target_corr": round(max_corr, 4),
        "verdict": ("중복행/타깃누수 없음 — 점수는 다수 약신호의 상호작용에서 유래"
                    if dup_rows == 0 and max_corr < 0.3 else "검토 필요"),
    }
    print("="*60)
    print("0) 누수 진단")
    print(f"   완전중복행 {dup_rows} · 피처중복행 {dup_feat} · 최대|타깃상관| {max_corr:.3f}")
    print(f"   → {audit['verdict']}")

    # 누수 안전 + 비중복 피처셋
    drop = [c for c in DROP_TRANSDUCTIVE + DROP_REDUNDANT if c in X_all.columns]
    X = X_all.drop(columns=drop)
    print(f"   제외 피처({len(drop)}): {drop}")
    print(f"✅ 데이터 {X.shape[0]:,}행 × {X.shape[1]}피처 | 이탈률 {y.mean()*100:.2f}% (이탈 {int(y.sum()):,})")
    return X, y, audit, drop


# ════════════════════════════════════════════════════════════
# 1. 모델 정의 (LogReg 는 스케일링 파이프라인)
# ════════════════════════════════════════════════════════════
def build_models(y_train):
    spw = (y_train == 0).sum() / max((y_train == 1).sum(), 1)
    return {
        "Logistic Regression": Pipeline([
            ("scale", StandardScaler()),
            ("clf", LogisticRegression(max_iter=5000, class_weight="balanced",
                                       random_state=RANDOM_STATE)),
        ]),
        "Random Forest": RandomForestClassifier(
            n_estimators=400, max_depth=12, min_samples_leaf=20, n_jobs=-1,
            class_weight="balanced", random_state=RANDOM_STATE),
        "XGBoost": XGBClassifier(
            n_estimators=500, max_depth=5, learning_rate=0.05,
            subsample=0.9, colsample_bytree=0.9, scale_pos_weight=spw,
            eval_metric="aucpr", random_state=RANDOM_STATE, n_jobs=-1),
        "LightGBM": LGBMClassifier(
            n_estimators=600, learning_rate=0.05, num_leaves=31,
            subsample=0.9, colsample_bytree=0.9, class_weight="balanced",
            random_state=RANDOM_STATE, n_jobs=-1, verbose=-1),
    }


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
# 차트
# ════════════════════════════════════════════════════════════
def plot_model_comparison(cv_results):
    names = list(cv_results.keys())
    fig, ax = plt.subplots(figsize=(9, 5))
    x = np.arange(2); w = 0.2
    for i, n in enumerate(names):
        means = [cv_results[n]["pr_auc_mean"], cv_results[n]["roc_auc_mean"]]
        errs  = [cv_results[n]["pr_auc_std"],  cv_results[n]["roc_auc_std"]]
        ax.bar(x + i*w, means, w, yerr=errs, capsize=4, label=n, color=PALETTE.get(n, "#888"))
    ax.set_xticks(x + w*1.5); ax.set_xticklabels(["PR-AUC", "ROC-AUC"])
    ax.set_ylim(0, 1); ax.set_ylabel("CV score (mean ± std)")
    ax.set_title("Model Comparison — RepeatedStratifiedKFold (5×2)", fontweight="bold")
    ax.legend(fontsize=9); ax.grid(axis="y", alpha=.3)
    fig.tight_layout(); fig.savefig(IMG_DIR / "model_comparison.png", dpi=130); plt.close(fig)


def plot_roc_pr(y, proba, name):
    fig, ax = plt.subplots(1, 2, figsize=(12, 5))
    fpr, tpr, _ = roc_curve(y, proba)
    ax[0].plot(fpr, tpr, color="#0096c7", lw=2, label=f"{name} (AUC={roc_auc_score(y,proba):.3f})")
    ax[0].plot([0,1],[0,1],"--",color="#bbb"); ax[0].set_title("ROC Curve", fontweight="bold")
    ax[0].set_xlabel("False Positive Rate"); ax[0].set_ylabel("True Positive Rate"); ax[0].legend(); ax[0].grid(alpha=.3)
    prec, rec, _ = precision_recall_curve(y, proba)
    ax[1].plot(rec, prec, color="#e63946", lw=2, label=f"{name} (AP={average_precision_score(y,proba):.3f})")
    ax[1].axhline(y.mean(), ls="--", color="#bbb", label=f"baseline={y.mean():.3f}")
    ax[1].set_title("Precision–Recall Curve", fontweight="bold")
    ax[1].set_xlabel("Recall"); ax[1].set_ylabel("Precision"); ax[1].legend(); ax[1].grid(alpha=.3)
    fig.tight_layout(); fig.savefig(IMG_DIR / "roc_pr_curves.png", dpi=130); plt.close(fig)


def plot_confusion(cm, name):
    cm = np.array(cm); fig, ax = plt.subplots(figsize=(5, 4.5))
    im = ax.imshow(cm, cmap="Blues"); lab = ["Stay (0)", "Churn (1)"]
    ax.set_xticks([0,1]); ax.set_yticks([0,1]); ax.set_xticklabels(lab); ax.set_yticklabels(lab)
    ax.set_xlabel("Predicted"); ax.set_ylabel("Actual"); ax.set_title(f"Confusion Matrix — {name}", fontweight="bold")
    tot = cm.sum()
    for i in range(2):
        for j in range(2):
            ax.text(j, i, f"{cm[i,j]:,}\n({cm[i,j]/tot*100:.1f}%)", ha="center", va="center",
                    color="white" if cm[i,j] > cm.max()/2 else "#111", fontsize=11)
    fig.colorbar(im, fraction=0.046); fig.tight_layout()
    fig.savefig(IMG_DIR / "confusion_matrix.png", dpi=130); plt.close(fig)


def plot_calibration(y, raw, cal, name):
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.plot([0,1],[0,1],"--",color="#bbb",label="perfectly calibrated")
    for p, c, lb in [(raw, "#f4a261", f"raw (Brier {brier_score_loss(y,raw):.3f})"),
                      (cal, "#2a9d8f", f"calibrated (Brier {brier_score_loss(y,cal):.3f})")]:
        fp, mp = calibration_curve(y, p, n_bins=10, strategy="quantile")
        ax.plot(mp, fp, "o-", color=c, lw=2, label=lb)
    ax.set_xlabel("Mean predicted probability"); ax.set_ylabel("Observed churn rate")
    ax.set_title(f"Calibration — {name} (isotonic)", fontweight="bold"); ax.legend(); ax.grid(alpha=.3)
    fig.tight_layout(); fig.savefig(IMG_DIR / "calibration_curve.png", dpi=130); plt.close(fig)


def plot_shap(model, X_sample, name):
    try:
        import shap
        sv = shap.TreeExplainer(model).shap_values(X_sample)
        if isinstance(sv, list): sv = sv[1]
        shap.summary_plot(sv, X_sample, show=False, max_display=15)
        fig = plt.gcf(); fig.set_size_inches(9, 6)
        plt.title(f"SHAP Feature Impact — {name}", fontweight="bold")
        fig.tight_layout(); fig.savefig(IMG_DIR / "shap_summary.png", dpi=130); plt.close(fig)
        ma = np.abs(sv).mean(axis=0); order = np.argsort(ma)[::-1][:15]
        return [{"feature": str(X_sample.columns[i]), "mean_abs_shap": round(float(ma[i]), 5)} for i in order]
    except Exception as e:
        print(f"⚠️ SHAP 생략: {e}"); return []


# ════════════════════════════════════════════════════════════
# 메인
# ════════════════════════════════════════════════════════════
def main():
    print("="*60); print("🔧 Churn 예측 — 엄밀 검증 파이프라인"); print("="*60)
    X, y, audit, dropped = load_and_audit()

    # 홀드아웃 test 분리 (최종 평가 전용, 모델 선택·보정·임계값에 미사용)
    X_dev, X_te, y_dev, y_te = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=RANDOM_STATE)
    print(f"   분할: dev {len(X_dev):,} / test {len(X_te):,} (stratified 80/20)\n")

    # 1) 견고한 CV 비교 (RepeatedStratifiedKFold 5×2)
    print("1) RepeatedStratifiedKFold(5×2) 모델 비교 (mean ± std)")
    rcv = RepeatedStratifiedKFold(n_splits=5, n_repeats=2, random_state=RANDOM_STATE)
    cv_results = {}
    for name, model in build_models(y_dev).items():
        pr = cross_val_score(model, X_dev, y_dev, cv=rcv, scoring="average_precision", n_jobs=-1)
        rc = cross_val_score(model, X_dev, y_dev, cv=rcv, scoring="roc_auc", n_jobs=-1)
        cv_results[name] = {
            "pr_auc_mean": round(float(pr.mean()), 4), "pr_auc_std": round(float(pr.std()), 4),
            "roc_auc_mean": round(float(rc.mean()), 4), "roc_auc_std": round(float(rc.std()), 4),
        }
        print(f"   {name:20s} PR-AUC {pr.mean():.4f}±{pr.std():.4f} | ROC {rc.mean():.4f}±{rc.std():.4f}")

    best_name = max(cv_results, key=lambda n: cv_results[n]["pr_auc_mean"])
    print(f"\n🏆 최적(CV PR-AUC): {best_name}")

    # 2) 확률 보정 모델 (isotonic) — 서빙용
    base = build_models(y_dev)[best_name]
    calibrated = CalibratedClassifierCV(base, method="isotonic", cv=5)

    # 3) 임계값: dev OOF(교차예측, 보정 확률)에서 F2 최대 — test 누수 없음
    #    이탈 방지는 미탐(FN, 놓친 이탈자) 비용이 오탐보다 크므로 recall 가중(F2) 운영점 채택
    BETA = 2.0
    print(f"\n2) 임계값 튜닝 (dev OOF F{int(BETA)} 최대, recall 가중) + 확률 보정")
    oof = cross_val_predict(calibrated, X_dev, y_dev, cv=5, method="predict_proba", n_jobs=-1)[:, 1]
    prec, rec, thr = precision_recall_curve(y_dev, oof)
    fbeta = (1+BETA**2)*prec*rec / (BETA**2*prec + rec + 1e-12)
    best_thr = float(thr[int(np.nanargmax(fbeta[:-1]))])
    print(f"   선택 임계값 {best_thr:.3f} (dev OOF F{int(BETA)} {np.nanmax(fbeta[:-1]):.3f})")

    # 4) 최종 학습 + test 평가
    calibrated.fit(X_dev, y_dev)
    base_fit = build_models(y_dev)[best_name]; base_fit.fit(X_dev, y_dev)  # SHAP/중요도용
    proba_cal = calibrated.predict_proba(X_te)[:, 1]
    proba_raw = base_fit.predict_proba(X_te)[:, 1]
    test_metrics = evaluate(y_te, proba_cal, best_thr)

    overfit_gap = round(float(roc_auc_score(y_dev, base_fit.predict_proba(X_dev)[:, 1])
                              - roc_auc_score(y_te, proba_raw)), 4)
    print(f"\n3) 홀드아웃 test 평가 (보정 확률)")
    print(f"   ROC {test_metrics['roc_auc']} · PR-AUC {test_metrics['pr_auc']} · "
          f"Recall {test_metrics['recall']} · F1 {test_metrics['f1']} · Brier {test_metrics['brier']}")
    print(f"   과적합 갭(ROC, raw) {overfit_gap} · Brier raw {brier_score_loss(y_te,proba_raw):.4f}→보정 {test_metrics['brier']}")

    # 5) 차트
    print("\n4) 차트 생성")
    plot_model_comparison(cv_results)
    plot_roc_pr(y_te, proba_cal, best_name)
    plot_confusion(test_metrics["confusion_matrix"], best_name)
    plot_calibration(y_te, proba_raw, proba_cal, best_name)
    Xs = X_te.sample(min(2000, len(X_te)), random_state=RANDOM_STATE)
    top_shap = plot_shap(base_fit if not isinstance(base_fit, Pipeline) else base_fit, Xs, best_name) \
        if best_name in ("LightGBM", "XGBoost", "Random Forest") else []

    # 피처 중요도
    est = base_fit
    if hasattr(est, "feature_importances_"):
        imp = est.feature_importances_; order = np.argsort(imp)[::-1][:15]
        fi = [{"feature": str(X.columns[i]), "importance": round(float(imp[i]), 5)} for i in order]
    else:
        fi = []

    # 6) 직렬화 (보정 모델 = 서빙)
    bundle = {
        "model": calibrated, "threshold": best_thr, "feature_names": list(X.columns),
        "model_name": best_name, "churn_base_rate": round(float(y.mean()), 4),
        "calibrated": True, "trained_at": datetime.now().isoformat(timespec="seconds"),
    }
    joblib.dump(bundle, MODEL_DIR / "churn_model.joblib")
    print(f"\n💾 모델 저장: churn_model.joblib ({best_name}, isotonic 보정, thr {best_thr:.3f})")

    metrics = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "dataset": {"rows": int(X.shape[0]), "features": int(X.shape[1]),
                    "features_dropped": dropped, "churn_rate": round(float(y.mean()), 4),
                    "n_churn": int(y.sum())},
        "split": {"dev": int(len(X_dev)), "test": int(len(X_te)),
                  "method": "stratified 80/20", "random_state": RANDOM_STATE},
        "leakage_audit": audit,
        "cv": {"scheme": "RepeatedStratifiedKFold(5x2)", "models": cv_results},
        "calibration": {"method": "isotonic",
                        "brier_raw": round(float(brier_score_loss(y_te, proba_raw)), 4),
                        "brier_calibrated": test_metrics["brier"]},
        "overfit_gap_roc": overfit_gap,
        "best_model": best_name, "threshold": round(best_thr, 4),
        "threshold_criterion": "F2 (recall-weighted, dev OOF)",
        "models": {n: cv_results[n] for n in cv_results},
        "best": test_metrics,
        "top_features_by_importance": fi,
        "top_features_by_shap": top_shap,
    }
    with open(MODEL_DIR / "metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    print("💾 지표 저장: metrics.json")
    print("\n" + "="*60)
    print(f"✅ 완료 — {best_name} | Recall {test_metrics['recall']} "
          f"PR-AUC {test_metrics['pr_auc']} ROC {test_metrics['roc_auc']} (확률 보정·누수 검증)")
    print("="*60)


if __name__ == "__main__":
    main()
