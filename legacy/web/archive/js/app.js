/* ============================================================
   app.js — 대시보드 동작(JS만!)
   Flask: static/js/app.js
   ============================================================ */

/* ── 공통: 사이드바 토글 ── */
function toggleSub(el){
  el.classList.toggle('open');
  const s = el.nextElementSibling;
  if (s && s.classList.contains('sub-menu')) s.classList.toggle('open');
}

/* ── 공통: 푸터 시계 ── */
(function tick(){
  const n = new Date();
  const p = v => String(v).padStart(2,'0');
  const el = document.getElementById('footerTime');
  if (el) el.textContent =
    `${n.getFullYear()}.${p(n.getMonth()+1)}.${p(n.getDate())}  ${p(n.getHours())}:${p(n.getMinutes())}`;
  setTimeout(tick, 60000);
})();

/* ── 등급 색/메시지 ── */
const GC = { ALL:'#4f46e5', A:'#dc2626', B:'#0ea5e9', C:'#7c3aed', D:'#0891b2' };
const GM = { ALL:'전체 고객 데이터', A:'A등급 — 최고위험', B:'B등급 — 고위험', C:'C등급 — 중위험', D:'D등급 — 저위험' };

/* ── 차트 공통 스타일 ── */
const GRID = '#eaecf4';
const TICK = '#6b7280';

/* Chart 인스턴스 보관 */
let charts = {};
let nowGrade = 'ALL';

/* ── Chart.js 전역 툴팁(가독성) ── */
if (window.Chart?.defaults?.plugins?.tooltip) {
  Chart.defaults.plugins.tooltip.backgroundColor = 'rgba(17,24,39,0.92)';
  Chart.defaults.plugins.tooltip.titleColor = '#fff';
  Chart.defaults.plugins.tooltip.bodyColor = '#fff';
  Chart.defaults.plugins.tooltip.padding = 12;
  Chart.defaults.plugins.tooltip.cornerRadius = 10;
}

/* ── 차트 생성/재생성 유틸 ── */
function mountChart(key, canvasId, config){
  const el = document.getElementById(canvasId);
  if (!el) return;

  if (charts[key]) charts[key].destroy();
  charts[key] = new Chart(el, config);
}

/* ============================================================
   (샘플/고정) 데이터 — 네 app.js에 있던 구조를 유지
   ============================================================ */


/* ============================================================
   차트 1~4 렌더링
   ============================================================ */
function drawChart1(d) {

  const bgColors = d.values.map((v, i) => {
    return d.highlight.includes(i)
      ? GC[nowGrade]
      : "rgba(79,70,229,0.12)";
  });

  mountChart('c1', 'chart1', {
    type: 'bar',
    data: {
      labels: d.labels,
      datasets: [{
        label: '해지건수',
        data: d.values,
        borderRadius: 0,
        backgroundColor: bgColors,
        borderColor: GC[nowGrade],
        borderWidth: 2,
        barPercentage: 1.0,
        categoryPercentage: 0.55,

      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: {
        duration: 900,
        easing: 'easeOutQuart'
      },
      plugins: {
        legend: { display: true, labels:{ color: TICK } }
      },
      scales: {
        x: { grid: { color: GRID }, ticks: { color: TICK } },
        y: { grid: { color: GRID }, ticks: { color: TICK } }
      }
    }
  });
}

function drawChart2(d){
    const pointColors = d.values.map((v,i)=>{
  return d.highlight.includes(i)
    ? "rgba(220,38,38,1)"
    : "rgba(79,70,229,0.8)";
});

  mountChart('c2', 'chart2', {
    type: 'line',
    data: {
      labels: d.labels,
      datasets: [{
        label: '해지율(%)',
        data: d.values,
        tension: 0.35,
        borderWidth: 3,
        pointRadius: 4,
        borderColor: "rgba(79,70,229,0.8)",
        backgroundColor: "rgba(79,70,229,0.3)",
        pointBackgroundColor: pointColors,
        pointBorderColor: pointColors
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: true, labels:{ color: TICK } } },
      scales: {
        x: { grid: { color: GRID }, ticks: { color: TICK } },
        y: { grid: { color: GRID }, ticks: { color: TICK } }
      }
    }
  });
}

function drawChart3(d){

  const bgColors = d.values.map((v,i)=>{
    return d.highlight.includes(i)
      ? GC[nowGrade]
      : "rgba(79,70,229,0.12)";
  });

  mountChart('c3', 'chart3', {
    type: 'bar',
    data: {
      labels: d.labels,
      datasets: [{
        label: '구간별 해지율(%)',
        data: d.values,
        borderRadius: 12,
        backgroundColor: bgColors,
        borderWidth: 2,
        barPercentage: 0.5,
        categoryPercentage: 0.6
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      animation: {
        duration: 900,
        easing: 'easeOutQuart'
      },
      plugins: { legend: { display: true, labels:{ color: TICK } } },
      scales: {
        x: { grid: { color: GRID }, ticks: { color: TICK } },
        y: { grid: { color: TICK } }
      }
    }
  });
}

function drawChart4(d){

  mountChart('c4', 'chart4', {
    type: 'radar',
    data: {
      labels: d.labels,
      datasets: [
        {
          label:'해지 고객',
          data:d.churn,
          borderColor:'rgba(220,38,38,1)',
          backgroundColor:'rgba(220,38,38,0.2)'
        },
        {
          label:'유지 고객',
          data:d.retain,
          borderColor:'rgba(34,197,94,1)',
          backgroundColor:'rgba(34,197,94,0.15)'
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { labels:{ color: TICK } } },
      scales: {
        r: {
          grid:{ color: GRID },
          angleLines:{ color: GRID },
          pointLabels:{ color: TICK },
          ticks:{ color: TICK }
        }
      }
    }
  });
}



/* ============================================================
   등급 버튼 + grade bar
   ============================================================ */
function setGradeUI(g){
  // 버튼 active 처리
  nowGrade = g;
  document.querySelectorAll('.grade-btn').forEach(btn=>{
    const on = btn.dataset.grade === g;
    btn.classList.toggle('active', on);
  });

  // 상단 grade bar
  const bar = document.getElementById('gradeBar');
  const dot = document.getElementById('gradeDot');
  const txt = document.getElementById('gradeText');
  if (bar && dot && txt){
    bar.classList.add('show');
    dot.style.background = GC[g];
    txt.textContent = GM[g] || '';
  }
}

function bindGradeButtons(){
  document.querySelectorAll('.grade-btn').forEach(btn=>{
    btn.addEventListener('click', ()=>{
      const g = btn.dataset.grade || 'ALL';
      setGradeUI(g);

      fetch("/get_all_data", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ grade: g })
      })
      .then(res => res.json())
      .then(data => {
        console.log("서버 응답:", data);
        drawChart1(data.h1);
        drawChart2(data.h2);
        drawChart3(data.h3);
        drawChart4(data.h4);
      })
      .catch(err => console.error("fetch 에러:", err));
    });
  });
}


/* ── 초기 실행 ── */
document.addEventListener('DOMContentLoaded', ()=>{
  bindGradeButtons();
  setGradeUI('ALL');

  fetch("/get_all_data", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ grade: "ALL" })
  })
  .then(res => res.json())
  .then(data => {
    console.log("초기 서버 응답:", data);
    drawChart1(data.h1);
    drawChart2(data.h2);
    drawChart3(data.h3);
    drawChart4(data.h4);
  })
  .catch(err => console.error("초기 fetch 에러:", err));
});