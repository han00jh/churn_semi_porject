/* ============================================================
   chart_1_1.js — 주제1 불만고객형 / 1-1 차트 렌더링
   Flask 경로: static/js/chart_1_1.js

   [전체 흐름]
     1. fetch("/api/chart_1_1")      ← Flask에서 JSON 수신
     2. updateChips(data)            ← 인사이트 칩 텍스트 업데이트
     3. buildColors(values)          ← 해지율에 따라 막대 색 결정
     4. renderChart(data)            ← Chart.js로 차트 그리기

   [수정 포인트]
     - API 주소      → fetch() 안의 URL
     - 색 임계값     → buildColors() 안의 숫자 (50, 20)
     - 평균선 색     → AVG_COLOR
     - 고객수 색     → COUNT_COLOR
     - 차트 애니메이션 → animation.duration (밀리초)
   ============================================================ */


/* ── 색상 상수 ─────────────────────────────────────────────
   여기 색만 바꾸면 전체 차트 색이 바뀝니다              */
const COLOR_DANGER  = 'rgba(185, 28,  28,  0.90)';  // 해지율 50%↑ (매우위험)
const COLOR_WARNING = 'rgba(220, 38,  38,  0.75)';  // 해지율 20%↑ (위험)
const COLOR_SAFE    = 'rgba(220, 38,  38,  0.18)';  // 해지율 평균 이하 (안전)

const COLOR_BORDER_DANGER  = 'rgba(185, 28,  28,  1)';
const COLOR_BORDER_WARNING = 'rgba(220, 38,  38,  1)';
const COLOR_BORDER_SAFE    = 'rgba(220, 38,  38,  0.4)';

const AVG_COLOR   = '#f59e0b';              // 평균 기준선 (노란 점선)
const COUNT_COLOR = 'rgba(79, 70, 229, ';  // 고객수 라인 (보라)

const GRID_COLOR  = '#eaecf4';             // 격자선
const TICK_COLOR  = '#6b7280';             // 축 레이블


/* ── Chart.js 전역 툴팁 스타일 ────────────────────────── */
Chart.defaults.plugins.tooltip.backgroundColor = 'rgba(17,24,39,0.92)';
Chart.defaults.plugins.tooltip.titleColor      = '#fff';
Chart.defaults.plugins.tooltip.bodyColor       = '#e5e7eb';
Chart.defaults.plugins.tooltip.padding         = 12;
Chart.defaults.plugins.tooltip.cornerRadius    = 10;


/* ============================================================
   1. 막대 색상 결정 함수
      해지율 값에 따라 3단계 색으로 강조
   ============================================================ */
function buildColors(values) {
  /*
    50% 이상  → 진한 빨강 (매우위험)
    20% 이상  → 중간 빨강 (위험)
    그 외     → 연한 빨강 (평균 이하)

    ← 임계값을 바꾸려면 아래 숫자 수정
  */
  const bg     = [];
  const border = [];

  values.forEach(v => {
    if (v >= 50) {
      bg.push(COLOR_DANGER);
      border.push(COLOR_BORDER_DANGER);
    } else if (v >= 20) {
      bg.push(COLOR_WARNING);
      border.push(COLOR_BORDER_WARNING);
    } else {
      bg.push(COLOR_SAFE);
      border.push(COLOR_BORDER_SAFE);
    }
  });

  return { bg, border };
}


/* ============================================================
   2. 인사이트 칩 & 하단 설명 업데이트 함수
      데이터를 받아 화면 텍스트를 동적으로 채움
   ============================================================ */
function updateChips(data) {
  const { labels, values, avg_churn } = data;

  /* 임계점: 해지율이 처음으로 20% 넘는 상담 횟수 찾기 */
  const thresholdIdx = values.findIndex(v => v >= 20);
  const thresholdLabel = thresholdIdx >= 0
    ? `${labels[thresholdIdx]}회`
    : '없음';

  /* 최고 위험 구간 */
  const maxVal   = Math.max(...values);
  const maxLabel = labels[values.indexOf(maxVal)];

  /* 칩 텍스트 업데이트 */
  document.getElementById('chip-threshold').textContent =
    `⚠ 임계점: 상담 ${thresholdLabel}부터 급등 · 최고 ${maxLabel}회 (${maxVal}%)`;

  document.getElementById('chip-avg').textContent =
    `전체 평균 해지율 ${avg_churn}%`;

  /* 하단 설명 업데이트 */
  document.getElementById('threshold-text').textContent =
    `점선: 전체 평균 해지율 ${avg_churn}% 기준선 `
    + `· ${thresholdLabel} 이상부터 평균 초과 `
    + `· ${maxLabel}회 고객 해지율 ${maxVal}% (최고위험)`;
}


/* ============================================================
   3. Chart.js 차트 렌더링 함수
   ============================================================ */
function renderChart(data) {
  const { labels, values, counts, avg_churn } = data;
  const { bg, border } = buildColors(values);

  /* X축 레이블: 숫자 → "N회" 형태 */
  const xLabels = labels.map(v => `${v}회`);

  new Chart(document.getElementById('chart'), {
    data: {
      labels: xLabels,
      datasets: [

        /* ── 데이터셋 1: 해지율 막대 ── */
        {
          type            : 'bar',
          label           : '해지율 (%)',
          data            : values,
          backgroundColor : bg,
          borderColor     : border,
          borderWidth     : 2,
          borderRadius    : 6,
          barPercentage   : 0.6,
          categoryPercentage: 0.65,
          yAxisID         : 'y',       // 왼쪽 Y축
        },

        /* ── 데이터셋 2: 전체 평균 기준선 ── */
        {
          type        : 'line',
          label       : `전체 평균 ${avg_churn}%`,
          data        : new Array(labels.length).fill(avg_churn),
          borderColor : AVG_COLOR,
          borderWidth : 2,
          borderDash  : [6, 4],        // 점선
          pointRadius : 0,             // 점 없음
          tension     : 0,
          yAxisID     : 'y',
        },

        /* ── 데이터셋 3: 고객 수 보조선 ── */
        {
          type              : 'line',
          label             : '고객 수',
          data              : counts,
          borderColor       : COUNT_COLOR + '0.5)',
          backgroundColor   : COUNT_COLOR + '0.05)',
          borderWidth       : 1.5,
          pointRadius       : 3,
          pointBackgroundColor: COUNT_COLOR + '0.7)',
          tension           : 0.3,
          fill              : true,
          yAxisID           : 'y2',    // 오른쪽 Y축
        }

      ]
    },

    options: {
      responsive        : true,
      maintainAspectRatio: false,

      /* 등장 애니메이션 */
      animation: {
        duration: 1000,              // ← 속도 조절 (밀리초)
        easing  : 'easeOutQuart'
      },

      /* 호버 시 같은 X 인덱스 전체 강조 */
      interaction: {
        mode     : 'index',
        intersect: false,
      },

      plugins: {
        legend: {
          labels: { color: TICK_COLOR, font: { size: 11 } }
        },

        /* 툴팁 커스터마이징 */
        tooltip: {
          callbacks: {
            label: (ctx) => {
              if (ctx.dataset.label === '해지율 (%)') {
                return ` 해지율: ${ctx.parsed.y}%`;
              }
              if (ctx.dataset.label === '고객 수') {
                return ` 고객 수: ${ctx.parsed.y.toLocaleString()}명`;
              }
              return ` 평균: ${ctx.parsed.y}%`;
            }
          }
        }
      },

      scales: {

        /* X축: 상담 횟수 */
        x: {
          grid : { color: GRID_COLOR },
          ticks: { color: TICK_COLOR, font: { size: 12, weight: '600' } },
          title: {
            display: true,
            text   : '상담 전화 횟수',
            color  : TICK_COLOR,
            font   : { size: 11 }
          }
        },

        /* 왼쪽 Y축: 해지율 */
        y: {
          position: 'left',
          grid    : { color: GRID_COLOR },
          ticks   : {
            color   : TICK_COLOR,
            callback: v => v + '%'
          },
          title: {
            display: true,
            text   : '해지율 (%)',
            color  : '#dc2626',
            font   : { size: 11, weight: '700' }
          },
          min: 0,
          max: 100,
        },

        /* 오른쪽 Y축: 고객 수 */
        y2: {
          position: 'right',
          grid    : { drawOnChartArea: false },  // 격자선 중복 방지
          ticks   : {
            color   : '#a5b4fc',
            callback: v => v.toLocaleString() + '명'
          },
          title: {
            display: true,
            text   : '고객 수',
            color  : '#818cf8',
            font   : { size: 11 }
          }
        }

      }
    }
  });
}


/* ============================================================
   4. 메인 실행
      페이지 로드 시 Flask API 호출 → 차트 그리기
   ============================================================ */
document.addEventListener('DOMContentLoaded', () => {

  /* Flask 엔드포인트에서 데이터 가져오기 */
  fetch('/api/chart_1_1')               // ← API 주소 수정 포인트
    .then(res => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    })
    .then(data => {
      console.log('📊 chart_1_1 데이터:', data);
      updateChips(data);   // 인사이트 칩 텍스트 업데이트
      renderChart(data);   // 차트 그리기
    })
    .catch(err => {
      console.error('❌ 데이터 로드 실패:', err);
      document.getElementById('chip-threshold').textContent = '⚠ 데이터 로드 실패';
    });

});
