/* ============================================================
   predict.js — 실시간 이탈 예측 섹션
   · /model_metrics → KPI 바 + 모델 뱃지 갱신
   · 슬라이더/랜덤고객 → /predict · /predict_sample → 게이지·요인
   · /risk_list → Target List 테이블
   ============================================================ */
(function () {
  "use strict";

  // 사용자에게 노출할 핵심 입력 피처 (나머지 30개는 모집단 중앙값으로 자동 채움)
  const SLIDERS = [
    { key: "cs_calls",      label: "상담 전화 횟수", min: 0,   max: 10,   step: 1,    val: 1 },
    { key: "tenure",        label: "가입 기간(개월)", min: 1,   max: 250,  step: 1,    val: 90 },
    { key: "day_minutes",   label: "주간 통화시간",   min: 0,   max: 400,  step: 5,    val: 180 },
    { key: "total_minutes", label: "총 사용량",       min: 100, max: 1200, step: 10,   val: 600 },
    { key: "avg_rate",      label: "평균 요금단가",   min: 0.05,max: 0.35, step: 0.005,val: 0.14 },
  ];

  const $ = (id) => document.getElementById(id);
  const fmt = (v, step) => (step < 1 ? Number(v).toFixed(3) : String(Math.round(v)));

  /* ── 1. KPI 바 + 모델 뱃지 갱신 ── */
  function loadMetrics() {
    fetch("/model_metrics").then(r => r.json()).then(m => {
      if (!m || !m.ready) return;
      const b = m.best || {};
      const set = (id, v) => { const el = $(id); if (el && v != null) el.firstChild ? el.firstChild.nodeValue = v : el.textContent = v; };
      if ($("kpiModel"))  $("kpiModel").textContent  = m.best_model || "—";
      if ($("kpiRoc"))    $("kpiRoc").childNodes[0].nodeValue   = (b.roc_auc ?? 0).toFixed(2);
      if ($("kpiPr"))     $("kpiPr").childNodes[0].nodeValue    = (b.pr_auc ?? 0).toFixed(2);
      if ($("kpiRecall")) $("kpiRecall").childNodes[0].nodeValue = Math.round((b.recall ?? 0) * 100);
      if ($("kpiF1"))     $("kpiF1").childNodes[0].nodeValue     = (b.f1 ?? 0).toFixed(2);
      const badge = $("predModelBadge");
      if (badge) badge.textContent = `${m.best_model} · AUC ${(b.roc_auc ?? 0).toFixed(2)}`;
    }).catch(() => {});
  }

  /* ── 2. 슬라이더 생성 ── */
  function buildSliders() {
    const wrap = $("pcSliders");
    if (!wrap) return;
    wrap.innerHTML = SLIDERS.map(s => `
      <div class="pc-slider-row">
        <div class="pc-slider-label"><span>${s.label}</span><b id="val_${s.key}">${fmt(s.val, s.step)}</b></div>
        <input type="range" id="sld_${s.key}" min="${s.min}" max="${s.max}" step="${s.step}" value="${s.val}">
      </div>`).join("");
    SLIDERS.forEach(s => {
      const el = $(`sld_${s.key}`);
      el && el.addEventListener("input", () => { $(`val_${s.key}`).textContent = fmt(el.value, s.step); });
    });
  }

  function readSliders() {
    const o = {};
    SLIDERS.forEach(s => { const el = $(`sld_${s.key}`); if (el) o[s.key] = parseFloat(el.value); });
    return o;
  }

  function setSliders(values) {
    SLIDERS.forEach(s => {
      if (values[s.key] == null) return;
      let v = Math.max(s.min, Math.min(s.max, Number(values[s.key])));
      const el = $(`sld_${s.key}`); if (el) { el.value = v; $(`val_${s.key}`).textContent = fmt(v, s.step); }
    });
  }

  /* ── 3. 결과 렌더 ── */
  function renderResult(res, opts = {}) {
    if (!res || res.error) {
      $("prVerdict").textContent = "예측 실패 — 모델을 확인하세요";
      return;
    }
    const pct = res.churn_percent;
    const color = res.grade_color || "#6366f1";

    // 게이지 링
    const ring = $("prRing");
    if (ring) ring.style.background = `conic-gradient(${color} 0% ${pct}%, #e7e9f5 ${pct}% 100%)`;
    $("prPercent").innerHTML = `${pct}<span style="font-size:1.1rem">%</span>`;
    $("prPercent").style.color = color;

    const g = $("prGrade");
    g.textContent = `${res.grade} · ${res.grade_name}`;
    g.style.background = color;

    let verdict = res.will_churn
      ? "⚠ 이탈 위험 높음 — 선제 대응 권장"
      : "✓ 유지 가능성 높음";
    if (opts.customerId) verdict = `${opts.customerId} · ` + verdict;
    $("prVerdict").textContent = verdict;

    let meta = `모델 ${res.model_name} · 판정 임계값 ${(res.threshold * 100).toFixed(0)}%`;
    if (opts.actual != null) {
      meta += ` · 실제 ${opts.actual === 1 ? "이탈" : "유지"}`;
    }
    $("prMeta").textContent = meta;

    // 핵심 요인
    const dirTxt = { high: "높음 ▲", low: "낮음 ▼", mid: "보통" };
    const ul = $("prFactors");
    if (res.factors && res.factors.length) {
      ul.innerHTML = res.factors.map((f, i) => `
        <li class="pf-item">
          <span class="pf-rank">${i + 1}</span>
          <span class="pf-label">${f.label}</span>
          <span class="pf-val">${f.value}</span>
          <span class="pf-dir ${f.direction}">${dirTxt[f.direction] || ""}</span>
        </li>`).join("");
    }
  }

  function doPredict() {
    fetch("/predict", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ overrides: readSliders() }),
    }).then(r => r.json()).then(res => renderResult(res)).catch(() => {});
  }

  function doSample() {
    fetch("/predict_sample").then(r => r.json()).then(res => {
      if (res.error) return;
      setSliders(res.inputs || {});
      renderResult(res, { customerId: res.customer_id, actual: res.actual_churn });
    }).catch(() => {});
  }

  /* ── 4. Target List ── */
  function loadTargets(n = 20) {
    const rn = $("riskN"); if (rn) rn.textContent = n;
    fetch(`/risk_list?n=${n}`).then(r => r.json()).then(d => {
      const body = $("targetBody");
      if (!body || !d.items) return;
      body.innerHTML = d.items.map(it => `
        <tr>
          <td class="tt-id">${it.customer_id}</td>
          <td class="tt-prob" style="color:${it.grade_color}">${it.churn_percent}%</td>
          <td><span class="tt-grade" style="background:${it.grade_color}">${it.grade}</span></td>
          <td>${it.cs_calls ?? "-"}</td>
          <td>${it.tenure ?? "-"}</td>
          <td>${it.total_minutes ?? "-"}</td>
          <td>${it.avg_rate ?? "-"}</td>
          <td class="${it.actual_churn === 1 ? "tt-actual-churn" : "tt-actual-stay"}">${it.actual_churn === 1 ? "이탈" : "유지"}</td>
        </tr>`).join("");
    }).catch(() => {});
  }

  /* ── 5. 푸터 API 상태 ── */
  function loadFooterApi() {
    const el = $("footerAPI"); if (!el) return;
    fetch("/ai_usage").then(r => r.json()).then(s => {
      el.textContent = s.demo
        ? "AI: 데모 모드 (LLM 키 미설정)"
        : `AI: ${s.current_label} · 키 ${s.current_index}/${s.total_keys}`;
    }).catch(() => {});
  }

  /* ── init ── */
  document.addEventListener("DOMContentLoaded", () => {
    loadMetrics();
    buildSliders();
    loadTargets(20);
    loadFooterApi();
    $("btnPredict") && $("btnPredict").addEventListener("click", doPredict);
    $("btnSample")  && $("btnSample").addEventListener("click", doSample);
    doPredict();   // 초기 기준선 예측 표시
  });
})();
