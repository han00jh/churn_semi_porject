/* ============================================================
   app.js — 대시보드 전체 동작 최종본
   Flask 경로: static/js/app.js

   ┌─────────────────────────────────────────────────────────┐
   │  구조                                                    │
   │  1. 공통 유틸 (사이드바 토글, 푸터 시계)                  │
   │  2. 색상·테마 상수                                        │
   │  3. 인사이트 칩 메타데이터 (20개 차트 설명 텍스트)          │
   │  4. 차트 인스턴스 관리                                    │
   │  5. 차트 렌더러 7종                                       │
   │     [1] renderBarLine   막대+평균선+고객수라인 (A-1)       │
   │     [2] renderLine      라인+평균선 (A-2,B-2,C-2,D-4,E-3)│
   │     [3] renderHorizBar  가로막대 (A-3)                    │
   │     [4] renderCompareBar 비교막대2개 (A-4,C-4,D-3,E-2)   │
   │     [5] renderBar       일반막대 (B-1,B-3,C-1,C-3,D-1,E-4)│
   │     [6] renderClustered 클러스터드바 (B-4,E-1)            │
   │     [7] renderMultiLine 멀티라인 (D-2)                   │
   │  6. drawCharts(data) — chart_type 보고 렌더러 자동 선택  │
   │  7. updateCardUI()   — 카드 헤더/칩/뱃지/설명줄 교체     │
   │  8. updateAI(topic, graphData) — AI 3종 분석 + 화면 반영 │
   │  9. 버튼 바인딩 + 초기 실행                               │
   └─────────────────────────────────────────────────────────┘

   [전체 흐름]
     버튼 클릭 (A~E)
       ① setTopicUI(topic)        → 버튼 active, gradeBar 업데이트
       ② fetch /get_all_data      → 차트 데이터 수신
       ③ updateCardUI(topic,data) → 카드 헤더/칩/뱃지 교체
       ④ drawCharts(data)         → Chart.js 렌더링
       ⑤ fetch /ai_topic_insight  → AI 3종 분석 수신
       ⑥ updateAI(result)         → 챗봇 카드 3개 교체
   ============================================================ */


/* ============================================================
   1. 공통 유틸
   ============================================================ */

/** 사이드바 서브메뉴 토글 */
function toggleSub(el) {
  el.classList.toggle('open');
  const s = el.nextElementSibling;
  if (s && s.classList.contains('sub-menu')) s.classList.toggle('open');
}

/** 푸터 시계 */
(function tick() {
  const n = new Date(), p = v => String(v).padStart(2, '0');
  const el = document.getElementById('footerTime');
  if (el) el.textContent =
    `${n.getFullYear()}.${p(n.getMonth()+1)}.${p(n.getDate())}  ${p(n.getHours())}:${p(n.getMinutes())}`;
  setTimeout(tick, 60000);
})();


/* ============================================================
   2. 색상·테마 상수
   ← 이 블록만 수정하면 전체 색상 바뀜
   ============================================================ */

const TOPIC_COLORS = {
  A: '#e63946',   // 불만고객형   빨강
  B: '#0096c7',   // 이용강도형   스카이블루
  C: '#f4a261',   // 시간대별패턴  앰버
  D: '#2a9d8f',   // 장기사용형   에메랄드
  E: '#7b2d8b',   // 행동패턴형   바이올렛
};

const TOPIC_BADGE = {
  A: '🔴 불만고객형',
  B: '🔵 이용강도형',
  C: '🟠 시간대별 패턴',
  D: '🟢 장기사용형',
  E: '🟣 행동패턴형',
};

const TOPIC_DESC = {
  A: '불만고객형 — 핵심: 상담은 임계점 기반 위험 신호',
  B: '이용강도형 — 핵심: 몰입도 ↑ → 이탈 ↓',
  C: '시간대별 패턴 — 핵심: 밤 비중 ↑ / 패턴 불안정 ↑ → 위험',
  D: '장기사용형 — 핵심: 단독 tenure는 약함, 상호작용은 강함',
  E: '행동패턴형 — 핵심: 단조로운 고객이 먼저 떠난다',
};

const GRID_COLOR     = '#eaecf4';
const TICK_COLOR     = '#6b7280';
const AVG_LINE_COLOR = '#f59e0b';       // 평균 기준선 (노란 점선)
const COUNT_COLOR    = 'rgba(79,70,229,'; // 고객수 보조라인 (보라)
const ANIM_MS        = 700;

/** 클러스터드바·멀티라인 팔레트 */
const PAL_BG = [
  'rgba(99,102,241,.7)',
  'rgba(251,146,60,.7)',
  'rgba(52,211,153,.7)',
  'rgba(251,191,36,.7)',
];
const PAL_BD = [
  'rgba(99,102,241,1)',
  'rgba(251,146,60,1)',
  'rgba(52,211,153,1)',
  'rgba(251,191,36,1)',
];

/** Chart.js 전역 툴팁 */
if (window.Chart?.defaults?.plugins?.tooltip) {
  Object.assign(Chart.defaults.plugins.tooltip, {
    backgroundColor: 'rgba(17,24,39,.92)',
    titleColor:      '#fff',
    bodyColor:       '#e5e7eb',
    padding:         12,
    cornerRadius:    10,
  });
}


/* ============================================================
   3. 인사이트 칩 메타데이터
   주제별 4개 차트 각각의 칩 텍스트와 하단 설명줄
   ============================================================ */
const CHIP_META = {
  A: {
    h1: {
      chips: [
        {cls:'chip-warn', text:'⚠ 6회↑ 해지율 55%+ 폭등'},
        {cls:'chip-warn', text:'임계점: 3회부터 급등'},
        {cls:'chip-muted',text:'X: 상담횟수 · Y: 해지율'},
      ],
      note: '점선: 전체 평균 기준선 · 3회부터 급등, 6회 이상 임계점 돌파',
    },
    h2: {
      chips: [
        {cls:'chip-warn', text:'D8 분위부터 해지율 급등'},
        {cls:'chip-info', text:'100분당 상담빈도 위험 지표'},
        {cls:'chip-muted',text:'X: cs_per_100min 분위 · Y: 해지율'},
      ],
      note: '100분당 상담 건수 — 높을수록 이탈 위험 상승 경향',
    },
    h3: {
      chips: [
        {cls:'chip-warn', text:'상담비율 높을수록 이탈 위험'},
        {cls:'chip-info', text:'D8~D10 구간 18%↑'},
        {cls:'chip-muted',text:'X: 해지율 · Y: cs_ratio 분위'},
      ],
      note: '통화 대비 상담 비율 — 높은 분위(오른쪽)일수록 위험',
    },
    h4: {
      chips: [
        {cls:'chip-warn', text:'⚠ 상담 상위 10% 해지율 17.8%'},
        {cls:'chip-info', text:'일반 대비 1.7배'},
        {cls:'chip-muted',text:'X: 고객 그룹 · Y: 해지율'},
      ],
      note: 'cs_per_100min 상위 10% 고객은 임계점 초과 고위험군',
    },
  },
  B: {
    h1: {
      chips: [
        {cls:'chip-info', text:'사용량 ↑ → 이탈 ↓ 경향'},
        {cls:'chip-warn', text:'D6~D8 소폭 반등 주의'},
        {cls:'chip-muted',text:'X: total_minutes 분위 · Y: 해지율'},
      ],
      note: '총 사용량 많을수록 이탈 방어 효과 — 몰입도 핵심 지표',
    },
    h2: {
      chips: [
        {cls:'chip-info', text:'고요금 구간 충성도 높음'},
        {cls:'chip-warn', text:'저요금 D1~D2 해지율 높음'},
        {cls:'chip-muted',text:'X: avg_rate 분위 · Y: 해지율'},
      ],
      note: '평균 요금 상위 분위일수록 해지율 낮아지는 역상관',
    },
    h3: {
      chips: [
        {cls:'chip-warn', text:'요금 변동 클수록 불안정'},
        {cls:'chip-info', text:'D1~D2 변동성 주의'},
        {cls:'chip-muted',text:'X: rate_std 분위 · Y: 해지율'},
      ],
      note: '요금 변동성 높은 그룹 = 요금 패턴 불안정',
    },
    h4: {
      chips: [
        {cls:'chip-info', text:'사용량 × 요금 교차 분석'},
        {cls:'chip-warn', text:'고사용·저요금 조합 위험'},
        {cls:'chip-muted',text:'X: usage_q · 시리즈: avg_rate 분위'},
      ],
      note: '사용량 Q4 × 요금 Q1 조합이 가장 높은 이탈률 기록',
    },
  },
  C: {
    h1: {
      chips: [
        {cls:'chip-info', text:'밤 비중 낮을수록 안정'},
        {cls:'chip-warn', text:'D1~D2 역설적 높음 주의'},
        {cls:'chip-muted',text:'X: night_ratio 분위 · Y: 해지율'},
      ],
      note: '밤 통화 비중 — D1~D2가 오히려 높은 역U형 패턴 확인',
    },
    h2: {
      chips: [
        {cls:'chip-warn', text:'밤-낮 격차 클수록 편중'},
        {cls:'chip-info', text:'D1 13% 주목'},
        {cls:'chip-muted',text:'X: night_day_diff 분위 · Y: 해지율'},
      ],
      note: '밤과 낮의 통화량 차이 — 격차가 클수록 사용 패턴 불안정',
    },
    h3: {
      chips: [
        {cls:'chip-warn', text:'패턴 불안정 고객 이탈 주의'},
        {cls:'chip-info', text:'D5 구간 13.8% 최고점'},
        {cls:'chip-muted',text:'X: time_ratio_std 분위 · Y: 해지율'},
      ],
      note: '시간대 집중도(분산) — D5 구간 이상치 주목',
    },
    h4: {
      chips: [
        {cls:'chip-info', text:'낮 집중 고객 소폭 높음'},
        {cls:'chip-warn', text:'차이 약 1.6%p'},
        {cls:'chip-muted',text:'X: 고객 그룹 · Y: 해지율'},
      ],
      note: 'day_ratio 상위 25% vs 나머지 — 낮 집중 고객이 소폭 위험',
    },
  },
  D: {
    h1: {
      chips: [
        {cls:'chip-info', text:'가입기간 단독 효과 미약'},
        {cls:'chip-warn', text:'D5 13.5% 이상치'},
        {cls:'chip-muted',text:'X: tenure 분위 · Y: 해지율'},
      ],
      note: '가입기간만으로는 뚜렷한 패턴 없음 — 상호작용 변수가 핵심',
    },
    h2: {
      chips: [
        {cls:'chip-warn', text:'고사용+장기 조합 가장 위험'},
        {cls:'chip-info', text:'usage Q4 × tenure Q4 13%+'},
        {cls:'chip-muted',text:'X: usage_q · 시리즈: tenure_q'},
      ],
      note: '사용량과 가입기간 교차 — 고사용 장기고객도 이탈 위험 존재',
    },
    h3: {
      chips: [
        {cls:'chip-warn', text:'고사용+장기 해지율 13%'},
        {cls:'chip-info', text:'일반 대비 1.2배'},
        {cls:'chip-muted',text:'X: 고객 그룹 · Y: 해지율'},
      ],
      note: 'usage_q≥3 AND tenure_q≥3 고객 — 장기 충성 고객도 안심 금물',
    },
    h4: {
      chips: [
        {cls:'chip-info', text:'로그 변환 후 패턴 동일'},
        {cls:'chip-warn', text:'D5 구간 이상 상승 유의'},
        {cls:'chip-muted',text:'X: tenure_log 분위 · Y: 해지율'},
      ],
      note: 'tenure 로그 변환 — 이상치 영향 감소, 선형 결과와 동일',
    },
  },
  E: {
    h1: {
      chips: [
        {cls:'chip-warn', text:'저요금·저변동 = 단조로움'},
        {cls:'chip-info', text:'Q1×Q1 조합 해지율 최고'},
        {cls:'chip-muted',text:'X: avg_rate분위 · 시리즈: rate_std분위'},
      ],
      note: '요금과 변동성 교차 — 단조로운 패턴이 이탈 신호',
    },
    h2: {
      chips: [
        {cls:'chip-info', text:'미사용자 소폭 높음'},
        {cls:'chip-warn', text:'미사용 12.2% vs 사용 10.3%'},
        {cls:'chip-muted',text:'X: 음성사서함 · Y: 해지율'},
      ],
      note: '음성사서함 미사용자가 사용자보다 해지율 약 1.9%p 높음',
    },
    h3: {
      chips: [
        {cls:'chip-warn', text:'미사용(D1) 12.6% 최고'},
        {cls:'chip-info', text:'사용량 증가 시 해지율 급감'},
        {cls:'chip-muted',text:'X: vm_count_log 분위 · Y: 해지율'},
      ],
      note: '음성사서함 횟수 — 사용이 늘수록 충성도 상관관계 확인',
    },
    h4: {
      chips: [
        {cls:'chip-info', text:'D2 12.8% 주목'},
        {cls:'chip-warn', text:'중간 분위 소폭 높음'},
        {cls:'chip-muted',text:'X: total_calls 분위 · Y: 해지율'},
      ],
      note: '총 통화 횟수 — D2~D3 구간에서 소폭 이탈 상승',
    },
  },
};


/* ============================================================
   4. 차트 인스턴스 관리
   ============================================================ */

const chartInstances = {};

/** 차트 마운트: 기존 인스턴스 destroy 후 재생성 */
function mountChart(key, canvasId, config) {
  const el = document.getElementById(canvasId);
  if (!el) return;
  if (chartInstances[key]) chartInstances[key].destroy();
  chartInstances[key] = new Chart(el, config);
}

/** 카드 4개 순차 fade+slideUp 애니메이션 */
function animateCards() {
  ['card1','card2','card3','card4'].forEach((id, i) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.style.opacity   = '0';
    el.style.transform = 'translateY(14px)';
    el.style.transition = 'none';
    setTimeout(() => {
      el.style.transition = `opacity .38s ease ${i*.07}s, transform .38s ease ${i*.07}s`;
      el.style.opacity    = '1';
      el.style.transform  = 'translateY(0)';
    }, 20);
  });
}

/** HEX → rgba 변환 */
function hexRgba(hex, a) {
  const r = parseInt(hex.slice(1,3),16);
  const g = parseInt(hex.slice(3,5),16);
  const b = parseInt(hex.slice(5,7),16);
  return `rgba(${r},${g},${b},${a})`;
}


/* ============================================================
   5. 차트 렌더러 7종
   ============================================================ */

/** [1] 막대 + 평균선 + 고객수 보조라인 */
function renderBarLine(canvasId, data) {
  const c  = TOPIC_COLORS[data.topic] || '#e63946';
  const bg = data.values.map(v =>
    v >= 50 ? hexRgba(c,.9) : v >= 20 ? hexRgba(c,.7) : hexRgba(c,.18)
  );
  const bd = data.values.map(v =>
    v >= 50 ? hexRgba(c,1) : v >= 20 ? hexRgba(c,1) : hexRgba(c,.4)
  );
  mountChart(canvasId, canvasId, {
    data: { labels: data.labels, datasets: [
      { type:'bar',  label:'해지율 (%)',       data:data.values,
        backgroundColor:bg, borderColor:bd, borderWidth:2, borderRadius:6,
        barPercentage:.6, categoryPercentage:.65, yAxisID:'y' },
      { type:'line', label:`평균 ${data.avg}%`,data:new Array(data.labels.length).fill(data.avg),
        borderColor:AVG_LINE_COLOR, borderWidth:2, borderDash:[6,4],
        pointRadius:0, tension:0, yAxisID:'y' },
      { type:'line', label:'고객 수',          data:data.counts,
        borderColor:COUNT_COLOR+'.55)', backgroundColor:COUNT_COLOR+'.05)',
        borderWidth:1.5, pointRadius:3, pointBackgroundColor:COUNT_COLOR+'.7)',
        tension:.3, fill:true, yAxisID:'y2' },
    ]},
    options: {
      responsive:true, maintainAspectRatio:false,
      animation:{duration:ANIM_MS, easing:'easeOutQuart'},
      interaction:{mode:'index', intersect:false},
      plugins:{
        legend:{labels:{color:TICK_COLOR, font:{size:10}}},
        tooltip:{callbacks:{label:(ctx) => {
          if (ctx.dataset.label==='해지율 (%)')  return ` 해지율: ${ctx.parsed.y}%`;
          if (ctx.dataset.label==='고객 수')     return ` 고객수: ${ctx.parsed.y.toLocaleString()}명`;
          return ` 평균: ${ctx.parsed.y}%`;
        }}},
      },
      scales:{
        x: { grid:{color:GRID_COLOR}, ticks:{color:TICK_COLOR},
             title:{display:true, text:data.x_label||'', color:TICK_COLOR, font:{size:10}} },
        y: { position:'left', min:0, max:Math.max(100,...data.values)+5,
             grid:{color:GRID_COLOR}, ticks:{color:TICK_COLOR, callback:v=>v+'%'},
             title:{display:true, text:'해지율 (%)', color:c, font:{size:10,weight:'700'}} },
        y2:{ position:'right', grid:{drawOnChartArea:false},
             ticks:{color:'#a5b4fc', callback:v=>v.toLocaleString()+'명'},
             title:{display:true, text:'고객 수', color:'#818cf8', font:{size:10}} },
      },
    },
  });
}

/** [2] 라인 + 평균선 */
function renderLine(canvasId, data) {
  const c  = TOPIC_COLORS[data.topic] || '#e63946';
  const pt = data.values.map(v => v > data.avg ? hexRgba(c,1) : hexRgba(c,.4));
  mountChart(canvasId, canvasId, {
    type: 'line',
    data: { labels:data.labels, datasets:[
      { label:'해지율 (%)', data:data.values,
        borderColor:hexRgba(c,.9), backgroundColor:hexRgba(c,.08),
        borderWidth:3, tension:.35, fill:true,
        pointRadius:5, pointBackgroundColor:pt, pointBorderColor:pt },
      { label:`평균 ${data.avg}%`, data:new Array(data.labels.length).fill(data.avg),
        borderColor:AVG_LINE_COLOR, borderWidth:1.5, borderDash:[6,4], pointRadius:0, tension:0 },
    ]},
    options:{
      responsive:true, maintainAspectRatio:false,
      animation:{duration:ANIM_MS, easing:'easeOutQuart'},
      plugins:{legend:{labels:{color:TICK_COLOR, font:{size:10}}}},
      scales:{
        x:{ grid:{color:GRID_COLOR}, ticks:{color:TICK_COLOR},
            title:{display:true, text:data.x_label||'', color:TICK_COLOR, font:{size:10}} },
        y:{ grid:{color:GRID_COLOR}, ticks:{color:TICK_COLOR, callback:v=>v+'%'},
            title:{display:true, text:'해지율 (%)', color:c, font:{size:10,weight:'700'}} },
      },
    },
  });
}

/** [3] 가로 막대 */
function renderHorizBar(canvasId, data) {
  const c  = TOPIC_COLORS[data.topic] || '#e63946';
  const bg = data.values.map(v => v > data.avg ? hexRgba(c,.75) : hexRgba(c,.22));
  mountChart(canvasId, canvasId, {
    type: 'bar',
    data: { labels:data.labels, datasets:[
      { label:'해지율 (%)', data:data.values,
        backgroundColor:bg, borderColor:hexRgba(c,.8),
        borderWidth:1.5, borderRadius:4, barPercentage:.6, categoryPercentage:.65 },
      { type:'line', label:`평균 ${data.avg}%`, data:new Array(data.labels.length).fill(data.avg),
        borderColor:AVG_LINE_COLOR, borderWidth:1.5, borderDash:[5,4], pointRadius:0 },
    ]},
    options:{
      indexAxis:'y',
      responsive:true, maintainAspectRatio:false,
      animation:{duration:ANIM_MS, easing:'easeOutQuart'},
      plugins:{legend:{labels:{color:TICK_COLOR, font:{size:10}}}},
      scales:{
        x:{ grid:{color:GRID_COLOR}, ticks:{color:TICK_COLOR, callback:v=>v+'%'},
            title:{display:true, text:'해지율 (%)', color:c, font:{size:10}} },
        y:{ grid:{color:GRID_COLOR}, ticks:{color:TICK_COLOR} },
      },
    },
  });
}

/** [4] 비교 막대 2개 그룹 */
function renderCompareBar(canvasId, data) {
  const c  = TOPIC_COLORS[data.topic] || '#e63946';
  const bg = data.values.map(v => v > data.avg ? hexRgba(c,.8) : hexRgba(c,.22));
  mountChart(canvasId, canvasId, {
    type: 'bar',
    data: { labels:data.labels, datasets:[
      { label:'해지율 (%)', data:data.values,
        backgroundColor:bg, borderColor:hexRgba(c,1),
        borderWidth:2, borderRadius:12, barPercentage:.4, categoryPercentage:.6 },
      { type:'line', label:`평균 ${data.avg}%`, data:new Array(data.labels.length).fill(data.avg),
        borderColor:AVG_LINE_COLOR, borderWidth:2, borderDash:[6,4], pointRadius:0 },
    ]},
    options:{
      responsive:true, maintainAspectRatio:false,
      animation:{duration:ANIM_MS, easing:'easeOutBounce'},
      plugins:{
        legend:{labels:{color:TICK_COLOR, font:{size:10}}},
        tooltip:{callbacks:{afterLabel:(ctx) => {
          const cnt = data.counts?.[ctx.dataIndex];
          return cnt ? ` 고객수: ${cnt.toLocaleString()}명` : '';
        }}},
      },
      scales:{
        x:{ grid:{color:GRID_COLOR}, ticks:{color:TICK_COLOR} },
        y:{ grid:{color:GRID_COLOR}, ticks:{color:TICK_COLOR, callback:v=>v+'%'},
            title:{display:true, text:'해지율 (%)', color:c, font:{size:10,weight:'700'}}, min:0 },
      },
    },
  });
}

/** [5] 일반 막대 */
function renderBar(canvasId, data) {
  const c  = TOPIC_COLORS[data.topic] || '#e63946';
  const bg = data.values.map(v => v > data.avg ? hexRgba(c,.75) : hexRgba(c,.2));
  mountChart(canvasId, canvasId, {
    type: 'bar',
    data: { labels:data.labels, datasets:[
      { label:'해지율 (%)', data:data.values,
        backgroundColor:bg, borderColor:hexRgba(c,.8),
        borderWidth:1.5, borderRadius:5, barPercentage:.65, categoryPercentage:.7 },
      { type:'line', label:`평균 ${data.avg}%`, data:new Array(data.labels.length).fill(data.avg),
        borderColor:AVG_LINE_COLOR, borderWidth:1.5, borderDash:[6,4], pointRadius:0 },
    ]},
    options:{
      responsive:true, maintainAspectRatio:false,
      animation:{duration:ANIM_MS, easing:'easeOutQuart'},
      plugins:{legend:{labels:{color:TICK_COLOR, font:{size:10}}}},
      scales:{
        x:{ grid:{color:GRID_COLOR}, ticks:{color:TICK_COLOR},
            title:{display:true, text:data.x_label||'', color:TICK_COLOR, font:{size:10}} },
        y:{ grid:{color:GRID_COLOR}, ticks:{color:TICK_COLOR, callback:v=>v+'%'},
            title:{display:true, text:'해지율 (%)', color:c, font:{size:10,weight:'700'}} },
      },
    },
  });
}

/** [6] 클러스터드 바 (교차 분석) */
function renderClustered(canvasId, data) {
  const ds = Object.entries(data.series).map(([k,v], i) => ({
    label: k, data: v,
    backgroundColor: PAL_BG[i%4], borderColor: PAL_BD[i%4],
    borderWidth: 1.5, borderRadius: 4,
  }));
  ds.push({
    type:'line', label:`전체 평균 ${data.avg}%`,
    data: new Array(data.labels.length).fill(data.avg),
    borderColor:AVG_LINE_COLOR, borderWidth:1.5, borderDash:[6,4], pointRadius:0,
  });
  mountChart(canvasId, canvasId, {
    type:'bar',
    data:{ labels:data.labels, datasets:ds },
    options:{
      responsive:true, maintainAspectRatio:false,
      animation:{duration:ANIM_MS, easing:'easeOutQuart'},
      plugins:{legend:{labels:{color:TICK_COLOR, font:{size:10}}}},
      scales:{
        x:{ grid:{color:GRID_COLOR}, ticks:{color:TICK_COLOR},
            title:{display:true, text:data.x_label||'', color:TICK_COLOR, font:{size:10}} },
        y:{ grid:{color:GRID_COLOR}, ticks:{color:TICK_COLOR, callback:v=>v+'%'},
            title:{display:true, text:'해지율 (%)', color:TICK_COLOR, font:{size:10}} },
      },
    },
  });
}

/** [7] 멀티 라인 (교차 시리즈) */
function renderMultiLine(canvasId, data) {
  const ds = Object.entries(data.series).map(([k,v], i) => ({
    label: `tenure ${k}`, data: v,
    borderColor: PAL_BD[i%4], backgroundColor: PAL_BG[i%4],
    borderWidth: 2.5, pointRadius: 4, tension: .35, fill: false,
  }));
  ds.push({
    label:'전체 평균', data:new Array(data.labels.length).fill(data.avg),
    borderColor:AVG_LINE_COLOR, borderWidth:1.5, borderDash:[6,4], pointRadius:0, tension:0,
  });
  mountChart(canvasId, canvasId, {
    type:'line',
    data:{ labels:data.labels, datasets:ds },
    options:{
      responsive:true, maintainAspectRatio:false,
      animation:{duration:ANIM_MS, easing:'easeOutQuart'},
      interaction:{mode:'index', intersect:false},
      plugins:{legend:{labels:{color:TICK_COLOR, font:{size:10}}}},
      scales:{
        x:{ grid:{color:GRID_COLOR}, ticks:{color:TICK_COLOR},
            title:{display:true, text:data.x_label||'', color:TICK_COLOR, font:{size:10}} },
        y:{ grid:{color:GRID_COLOR}, ticks:{color:TICK_COLOR, callback:v=>v+'%'},
            title:{display:true, text:'해지율 (%)', color:TICK_COLOR, font:{size:10}} },
      },
    },
  });
}


/* ============================================================
   6. drawCharts(data)
   chart_type → 렌더러 자동 선택
   ============================================================ */

const RENDERER = {
  bar_line      : renderBarLine,
  line          : renderLine,
  horizontal_bar: renderHorizBar,
  compare_bar   : renderCompareBar,
  bar           : renderBar,
  clustered_bar : renderClustered,
  multi_line    : renderMultiLine,
};
const CANVAS = { h1:'chart1', h2:'chart2', h3:'chart3', h4:'chart4' };

function drawCharts(data) {
  animateCards();
  ['h1','h2','h3','h4'].forEach(key => {
    const d  = data[key];
    if (!d) return;
    const fn = RENDERER[d.chart_type];
    if (fn) fn(CANVAS[key], d);
    else    console.warn('알 수 없는 chart_type:', d.chart_type);
  });
}


/* ============================================================
   7. updateCardUI(topic, data)
   카드 헤더(번호/제목/뱃지), 칩, 하단 설명줄 교체
   ============================================================ */

function buildChips(chips) {
  return chips.map(c =>
    `<span class="insight-chip ${c.cls}">${c.text}</span>`
  ).join('');
}

function updateCardUI(topic, data) {
  const badge = TOPIC_BADGE[topic] || '';

  ['h1','h2','h3','h4'].forEach((key, i) => {
    const idx = i + 1;
    const d   = data[key];
    if (!d) return;

    // 번호·제목
    const numEl   = document.getElementById(`num${idx}`);
    const titleEl = document.getElementById(`title${idx}`);
    if (numEl)   numEl.textContent   = String(idx).padStart(2,'0');
    if (titleEl) titleEl.textContent = d.title || '';

    // 주제 뱃지
    const badgeEl = document.getElementById(`badge${idx}`);
    if (badgeEl) {
      badgeEl.textContent    = badge;
      badgeEl.dataset.topic  = topic;
    }

    // 인사이트 칩
    const chipsEl = document.getElementById(`chips${idx}`);
    if (chipsEl) {
      chipsEl.dataset.topic = topic;
      const meta = CHIP_META[topic]?.[key];
      chipsEl.innerHTML = meta?.chips
        ? buildChips(meta.chips)
        : `<span class="insight-chip chip-info">전체 평균 ${d.avg||''}%</span>
           <span class="insight-chip chip-muted">${d.x_label||''}</span>`;
    }

    // 하단 설명줄
    const noteEl = document.getElementById(`noteText${idx}`);
    if (noteEl) {
      const meta = CHIP_META[topic]?.[key];
      noteEl.textContent = meta?.note || `점선: 전체 평균 ${d.avg||''}% 기준선`;
    }
  });
}


/* ============================================================
   8. updateAI(topic, graphData)
   /ai_topic_insight 호출 → 챗봇 카드 3개 교체
   ============================================================ */

/** AI 카드 로딩 상태 ON/OFF */
function setAILoading(on) {
  ['aiCard1','aiCard2','aiCard3'].forEach(id => {
    document.getElementById(id)?.classList.toggle('ai-loading', on);
  });
}


/** 인사이트 카드 한 개 값 업데이트 */
function setCard(numId, labelId, subId, d) {
  if (!d) return;
  const numEl   = document.getElementById(numId);
  const labelEl = document.getElementById(labelId);
  const subEl   = document.getElementById(subId);

  // 부드럽게 fade 교체
  [numEl, labelEl, subEl].forEach(el => {
    if (el) el.style.opacity = '0';
  });
  setTimeout(() => {
    if (numEl)   numEl.textContent   = d.number || '';
    if (labelEl) labelEl.textContent = d.label  || '';
    if (subEl)   subEl.textContent   = d.sub    || '';
    // sub 안에 strong 태그가 있을 경우 innerHTML로
    if (subEl && d.sub && d.sub.includes('<')) subEl.innerHTML = d.sub;
    [numEl, labelEl, subEl].forEach(el => {
      if (el) { el.style.transition = 'opacity .4s'; el.style.opacity = '1'; }
    });
  }, 200);
}

/** AI 분석 실행 */
function updateAI(topic, graphData) {
  setAILoading(true);

  fetch('/ai_topic_insight', {
    method : 'POST',
    headers: {'Content-Type': 'application/json'},
    body   : JSON.stringify({ topic, graph_data: graphData }),
  })
  .then(res => {
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  })
  .then(result => {
    setAILoading(false);


    // 현황 요약
    setCard('sumNumber', 'sumLabel', 'sumSub', result.summary);
    // 핵심 대책
    setCard('strNumber', 'strLabel', 'strSub', result.strategy);
    // 예상 이익
    setCard('fctNumber', 'fctLabel', 'fctSub', result.forecast);

    console.log(`🤖 AI 완료 (topic=${topic}):`, result);
  })
  .catch(err => {
    setAILoading(false);
    console.error('AI fetch 에러:', err);
  });
}


/* ============================================================
   9. 버튼 바인딩 + 초기 실행
   ============================================================ */

/** 버튼 active + gradeBar */
function setTopicUI(topic) {
  const color = TOPIC_COLORS[topic] || '#4f46e5';
  document.querySelectorAll('.grade-btn').forEach(btn =>
    btn.classList.toggle('active', btn.dataset.grade === topic)
  );
  const bar = document.getElementById('gradeBar');
  const dot = document.getElementById('gradeDot');
  const txt = document.getElementById('gradeText');
  if (bar) bar.classList.add('show');
  if (dot) dot.style.background = color;
  if (txt) txt.textContent      = TOPIC_DESC[topic] || '';
}

/** 차트 + AI 전체 로드 */
function loadTopic(topic) {
  // 차트 카드 로딩 표시
  ['card1','card2','card3','card4'].forEach(id =>
    document.getElementById(id)?.classList.add('loading')
  );

  fetch('/get_all_data', {
    method : 'POST',
    headers: {'Content-Type': 'application/json'},
    body   : JSON.stringify({ topic }),
  })
  .then(res => { if (!res.ok) throw new Error(`HTTP ${res.status}`); return res.json(); })
  .then(data => {
    ['card1','card2','card3','card4'].forEach(id =>
      document.getElementById(id)?.classList.remove('loading')
    );
    updateCardUI(topic, data);   // 카드 헤더/칩/뱃지 교체
    drawCharts(data);            // 차트 렌더링

    // ★ 차트 데이터를 그대로 AI에 전달
    updateAI(topic, {
      h1: data.h1,
      h2: data.h2,
      h3: data.h3,
      h4: data.h4,
    });
  })
  .catch(err => {
    ['card1','card2','card3','card4'].forEach(id =>
      document.getElementById(id)?.classList.remove('loading')
    );
    console.error('fetch 에러:', err);
  });
}

/** 초기 실행 */
document.addEventListener('DOMContentLoaded', () => {
  // 버튼 클릭 이벤트
  document.querySelectorAll('.grade-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const topic = btn.dataset.grade;
      if (!topic) return;
      setTopicUI(topic);
      loadTopic(topic);
    });
  });

  // 기본: A (불만고객형)
  setTopicUI('A');
  loadTopic('A');
});
