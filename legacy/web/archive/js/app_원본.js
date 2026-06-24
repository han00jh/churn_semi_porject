/* =====================================================
  app.js — 대시보드 전체 동작 담당

  구조:
  [A] 전역 변수/상수       ← 색상/텍스트 수정은 여기
  [B] 페이지 로드 초기화
  [C] 버튼 이벤트 등록
  [D] API 통신 함수
    D-1. loadData()          서버에서 차트 데이터 가져오기
    D-2. autoInsight()       AI 종합 분석 요청
    D-3. explainHypothesis() 개별 가설 분석 요청
    D-4. sendChat()          사용자 질문 전송
  [E] 차트 그리기 함수
    E-0. 공통 유틸 (makeChart, xyScale, makeBarHighlightPlugin)
    E-1. drawChart1()  가설1: 세로 막대
    E-2. drawChart2()  가설2: 꺾은선
    E-3. drawChart3()  가설3: 도넛
    E-4. drawChart4()  가설4: 레이더
    E-5. drawChart5()  가설5: 수평 막대
    E-6. drawChart6()  가설6: 버블
  [F] UI 애니메이션
    popCards()         등급 변경 시 카드 팝 효과
===================================================== */


/* =====================================================
  [A] 전역 변수 / 상수
  ★ 등급 색상 바꾸려면 GRADE_COLOR 수정
  ★ 등급 설명 바꾸려면 GRADE_MSG 수정
===================================================== */

let charts   = {};     // 생성된 Chart 인스턴스 보관
let lastData = null;   // 마지막으로 서버에서 받은 데이터 (AI 분석에 재사용)
let nowGrade = 'ALL';  // 현재 선택된 등급

// 등급별 포인트 색상
const GRADE_COLOR = {
  ALL: '#6366f1',
  A:   '#ef4444',
  B:   '#f97316',
  C:   '#eab308',
  D:   '#22c55e',
};

// 등급 바 설명 텍스트
const GRADE_MSG = {
  ALL: '전체 고객 데이터를 표시합니다.',
  A:   '🔴 A등급(최고위험): 상담전화 多·신규가입·낮은통화량 구간이 강조됩니다.',
  B:   '🟠 B등급(고위험): 고위험 특성 구간이 강조됩니다.',
  C:   '🟡 C등급(중위험): 중위험 구간이 강조됩니다.',
  D:   '🟢 D등급(저위험): 저위험·충성고객 구간이 강조됩니다.',
};

// 차트 공통 색상 (다크 테마용)
const DARK = {
  color: '#4e627a',  // 제목 색
  grid:  '#1a2035',  // 격자선 색
  tick:  '#7a92aa',  // 축 라벨 색
};


/* =====================================================
  [B] 페이지 로드 초기화
  페이지 열리면 전체(ALL) 데이터 자동 로드
===================================================== */
window.addEventListener('load', () => {
  loadData('ALL');
});


/* =====================================================
  [C] 버튼 이벤트 등록
  - 등급 버튼: 클릭 시 등급 바 업데이트 + 데이터 새로 로드
  - 종합 분석 버튼: AI 분석 요청
===================================================== */

// 등급 버튼 (전체/A/B/C/D)
document.querySelectorAll('.grade-btn').forEach(btn => {
  btn.addEventListener('click', function() {

    // 모든 버튼에서 active 제거 → 클릭한 버튼에만 active 추가
    document.querySelectorAll('.grade-btn').forEach(b => b.classList.remove('active'));
    this.classList.add('active');

    nowGrade = this.dataset.grade; // data-grade 속성값 읽기

    // 등급 설명 바 업데이트
    const bar = document.getElementById('gradeBar');
    document.getElementById('gradeDot').style.background = GRADE_COLOR[nowGrade];
    document.getElementById('gradeText').textContent = GRADE_MSG[nowGrade];

    // ALL이면 설명 바 숨기기, 아니면 보이기
    nowGrade === 'ALL' ? bar.classList.remove('show') : bar.classList.add('show');

    // 새 등급으로 데이터 다시 로드
    loadData(nowGrade);
  });
});

// 종합 분석 버튼
document.getElementById('analyzeBtn').addEventListener('click', () => {
  if (lastData) autoInsight(lastData);
});


/* =====================================================
  [D-1] loadData(grade)
  역할: 서버 /get_all_data 에 등급 전송 → 차트 데이터 수신 → 차트 그리기
  ★ API 엔드포인트 바꾸려면 fetch('/get_all_data') URL 수정
  ★ 서버 응답 구조: { h1, h2, h3, h4, h5, h6 }
===================================================== */
async function loadData(grade) {
  try {
    const res = await fetch('/get_all_data', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ grade }),
    });
    const data = await res.json();
    lastData = data;

    // 받은 데이터로 차트 6개 그리기
    drawChart1(data.h1);
    drawChart2(data.h2);
    drawChart3(data.h3);
    drawChart4(data.h4);
    drawChart5(data.h5);
    drawChart6(data.h6);

    // 카드 팝 애니메이션
    popCards(grade);

    // 전체 보기일 때만 자동으로 AI 종합 분석 실행
    if (grade === 'ALL') autoInsight(data);

  } catch (e) {
    console.error('loadData 오류:', e);
  }
}


/* =====================================================
  [D-2] autoInsight(data)
  역할: 서버 /chat_insight 에 전체 데이터 전송 → AI 종합 분석 결과 수신
===================================================== */
async function autoInsight(data) {
  const box = document.getElementById('chatMessages');
  box.innerHTML = '<span class="msg-loading">🤖 AI 종합 분석 중... (수 초 소요)</span>';

  try {
    const res = await fetch('/chat_insight', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ auto_mode: true, graph_data: data }),
    });
    const r = await res.json();

    box.innerHTML = r.success
      ? `<span class="msg-auto">${r.answer}</span>`
      : `<span style="color:#ef4444">⚠ ${r.answer}</span>`;

  } catch (e) {
    box.innerHTML = '<span style="color:#ef4444">⚠ AI 서비스 오류</span>';
  }
}


/* =====================================================
  [D-3] explainHypothesis(id)
  역할: 특정 가설 번호(1~6)에 대한 AI 분석 요청
  ★ 가설 버튼 클릭 시 호출됨 (HTML onclick="explainHypothesis(숫자)")
===================================================== */
async function explainHypothesis(id) {
  if (!lastData) { alert('데이터 로딩 중'); return; }

  const box = document.getElementById('chatMessages');
  box.innerHTML = `<span class="msg-loading">🤖 가설${id} 분석 중...</span>`;

  try {
    const res = await fetch('/chat_insight', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: 'hypothesis', hypothesis_id: id, graph_data: lastData }),
    });
    const r = await res.json();

    box.innerHTML = r.success
      ? `<span class="msg-auto">${r.answer}</span>`
      : `<span style="color:#ef4444">⚠ ${r.answer}</span>`;

  } catch (e) {
    box.innerHTML = '<span style="color:#ef4444">⚠ 오류</span>';
  }

  box.scrollTop = box.scrollHeight; // 스크롤 맨 아래로
}


/* =====================================================
  [D-4] sendChat()
  역할: 사용자가 입력한 질문을 서버에 전송 → AI 답변 수신
  호출 조건: 전송 버튼 클릭 or Enter 키
===================================================== */
async function sendChat() {
  const input = document.getElementById('chatInput');
  const msg = input.value.trim();
  if (!msg) return; // 빈 입력 무시

  const box = document.getElementById('chatMessages');

  // 사용자 메시지 표시
  box.innerHTML += `<div class="msg-user">👤 ${msg}</div>`;
  box.innerHTML += `<div class="msg-loading" id="loadMsg">🤖 답변 생성 중...</div>`;
  box.scrollTop = box.scrollHeight;
  input.value = '';

  try {
    const res = await fetch('/chat_insight', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: msg, graph_data: lastData, auto_mode: false }),
    });
    const r = await res.json();

    // 로딩 메시지 제거 후 AI 답변 추가
    const el = document.getElementById('loadMsg');
    if (el) el.remove();
    box.innerHTML += `<div class="msg-bot">🤖 ${r.answer}</div>`;

  } catch (e) {
    box.innerHTML += '<div style="color:#ef4444">⚠ 오류</div>';
  }

  box.scrollTop = box.scrollHeight;
}

// 전송 버튼 클릭
document.getElementById('chatSendBtn').addEventListener('click', sendChat);
// Enter 키로도 전송
document.getElementById('chatInput').addEventListener('keypress', e => {
  if (e.key === 'Enter') sendChat();
});


/* =====================================================
  [E-0] 차트 공통 유틸 함수
===================================================== */

/**
 * makeChart(id, config)
 * 기존 차트가 있으면 destroy() 후 새로 생성
 * ★ Chart.js 설정 전체 구조: https://www.chartjs.org/docs/
 */
function makeChart(id, config) {
  if (charts[id]) charts[id].destroy(); // 기존 차트 제거 (메모리 누수 방지)
  charts[id] = new Chart(document.getElementById(id), config);
}

/**
 * xyScale(yLabel)
 * x/y 축 공통 스타일 반환 (다크 테마)
 * ★ 축 스타일 바꾸려면 여기 수정
 */
function xyScale(yLabel) {
  return {
    x: {
      ticks: { color: DARK.tick },
      grid:  { color: DARK.grid },
    },
    y: {
      ticks: { color: DARK.tick },
      grid:  { color: DARK.grid },
      title: { display: true, text: yLabel, color: DARK.color },
      beginAtZero: true,
    },
  };
}

/**
 * makeBarHighlightPlugin(idxArr, gradeColor, suffix)
 * 등급 필터 시 특정 막대를 강조하는 플러그인
 * Chart.js afterDatasetsDraw 훅: 막대 그린 후 강조 사각형 덮어 그림
 * @param idxArr     강조할 막대 인덱스 배열 (서버 응답의 highlight)
 * @param gradeColor 강조 색상
 * @param suffix     숫자 뒤에 붙는 단위 (예: '건', '%')
 */
function makeBarHighlightPlugin(idxArr, gradeColor, suffix) {
  return {
    id: 'hl_' + Math.random(),
    afterDatasetsDraw(chart) {
      if (!idxArr || !idxArr.length || nowGrade === 'ALL') return;

      const { ctx, data } = chart;

      chart.getDatasetMeta(0).data.forEach((bar, i) => {
        if (!idxArr.includes(i)) return;

        const x      = bar.x;
        const y      = bar.y;
        const w      = bar.width;
        const bottom = chart.scales.y.getPixelForValue(0);
        const GROW   = 9;   // 좌우로 더 넓게
        const LIFT   = 16;  // 위로 더 솟게

        ctx.save();

        // 강조 사각형
        ctx.fillStyle = gradeColor;
        ctx.beginPath();
        ctx.roundRect(x - w/2 - GROW, y - LIFT, w + GROW*2, bottom - y + LIFT, 8);
        ctx.fill();

        // 흰 테두리
        ctx.strokeStyle = 'rgba(255,255,255,0.9)';
        ctx.lineWidth = 2.5;
        ctx.stroke();

        // 값 라벨
        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 12px Noto Sans KR, sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'bottom';
        ctx.fillText(data.datasets[0].data[i] + (suffix || ''), x, y - LIFT - 5);

        ctx.restore();
      });
    },
  };
}


/* =====================================================
  [E-1] drawChart1(h) — 가설1: 세로 막대 (bar)
  데이터: h.labels(X축), h.values(막대 높이), h.highlight(강조 인덱스)
  ★ 이 차트만 수정하려면 여기서만 건드리면 됨
===================================================== */
function drawChart1(h) {
  const base = GRADE_COLOR[nowGrade];
  const isGrade = nowGrade !== 'ALL';

  const bgColors = h.labels.map((_, i) =>
    (isGrade && h.highlight?.includes(i)) ? base + '55' : base + (isGrade ? '1a' : '99')
  );

  makeChart('chart1', {
    type: 'bar',
    data: {
      labels: h.labels,
      datasets: [{
        label: '해지건수',
        data: h.values,
        backgroundColor: bgColors,
        borderColor: 'transparent',
        borderWidth: 0,
        borderRadius: 7,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 800, easing: 'easeInOutQuart' },
      plugins: {
        legend: { labels: { color: DARK.tick } },
        tooltip: { callbacks: { label: c => `해지건수: ${c.raw}건` } },
      },
      scales: xyScale(h.y_label),
    },
    plugins: [makeBarHighlightPlugin(h.highlight, base, '건')],
  });
}


/* =====================================================
  [E-2] drawChart2(h) — 가설2: 꺾은선 (line)
  강조 포인트: 크기 키우고 흰색으로 표시
===================================================== */
function drawChart2(h) {
  const base = GRADE_COLOR[nowGrade];
  const isGrade = nowGrade !== 'ALL';

  makeChart('chart2', {
    type: 'line',
    data: {
      labels: h.labels,
      datasets: [{
        label: '해지율 (%)',
        data: h.values,
        borderColor: base,
        backgroundColor: base + '20',
        borderWidth: 2.5,
        pointRadius:          h.labels.map((_, i) => (isGrade && h.highlight?.includes(i)) ? 13 : 5),
        pointBackgroundColor: h.labels.map((_, i) => (isGrade && h.highlight?.includes(i)) ? '#fff' : base),
        pointBorderColor: base,
        pointBorderWidth:     h.labels.map((_, i) => (isGrade && h.highlight?.includes(i)) ? 3 : 1),
        tension: 0.4,
        fill: true,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 700 },
      plugins: { legend: { labels: { color: DARK.tick } } },
      scales: xyScale(h.y_label),
    },
  });
}


/* =====================================================
  [E-3] drawChart3(h) — 가설3: 도넛 (doughnut)
  강조 조각: 불투명하게, 나머지: 반투명
===================================================== */
function drawChart3(h) {
  const isGrade = nowGrade !== 'ALL';
  const palette = ['#ef4444', '#f97316', '#eab308', '#22c55e'];

  makeChart('chart3', {
    type: 'doughnut',
    data: {
      labels: h.labels,
      datasets: [{
        label: '해지율 (%)',
        data: h.values,
        backgroundColor: palette.map((c, i) =>
          (isGrade && h.highlight?.includes(i)) ? c : c + (isGrade ? '44' : 'bb')
        ),
        borderColor: '#06080f',
        borderWidth: 4,
        hoverOffset: 18,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 700 },
      plugins: {
        legend: { position: 'bottom', labels: { color: DARK.tick, padding: 16 } },
      },
    },
  });
}


/* =====================================================
  [E-4] drawChart4(h) — 가설4: 레이더 (radar)
  해지 고객(빨강) vs 유지 고객(초록) 비교
===================================================== */
function drawChart4(h) {
  makeChart('chart4', {
    type: 'radar',
    data: {
      labels: h.labels,
      datasets: [
        {
          label: '해지 고객',
          data: h.churn,
          backgroundColor: 'rgba(239,68,68,.18)',
          borderColor: '#ef4444',
          borderWidth: 2.5,
          pointRadius: 6,
          pointBackgroundColor: '#ef4444',
        },
        {
          label: '유지 고객',
          data: h.retain,
          backgroundColor: 'rgba(34,197,94,.18)',
          borderColor: '#22c55e',
          borderWidth: 2.5,
          pointRadius: 6,
          pointBackgroundColor: '#22c55e',
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 700 },
      plugins: { legend: { labels: { color: DARK.tick } } },
      scales: {
        r: {
          ticks:       { color: DARK.tick, backdropColor: 'transparent' },
          grid:        { color: DARK.grid },
          angleLines:  { color: DARK.grid },
          pointLabels: { color: DARK.tick, font: { size: 13 } },
          beginAtZero: true,
        },
      },
    },
  });
}


/* =====================================================
  [E-5] drawChart5(h) — 가설5: 수평 막대 (bar, indexAxis:'y')
  강조 막대: 불투명 + 흰 테두리
===================================================== */
function drawChart5(h) {
  const base = GRADE_COLOR[nowGrade];
  const isGrade = nowGrade !== 'ALL';

  const bgColors     = h.labels.map((_, i) => (isGrade && h.highlight?.includes(i)) ? base       : base + (isGrade ? '22' : '99'));
  const borderColors = h.labels.map((_, i) => (isGrade && h.highlight?.includes(i)) ? '#fff'     : 'transparent');
  const borderWidths = h.labels.map((_, i) => (isGrade && h.highlight?.includes(i)) ? 2          : 0);

  makeChart('chart5', {
    type: 'bar',
    data: {
      labels: h.labels,
      datasets: [{
        label: '해지율 (%)',
        data: h.values,
        backgroundColor: bgColors,
        borderColor: borderColors,
        borderWidth: borderWidths,
        borderRadius: 7,
      }],
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 700 },
      plugins: {
        legend: { labels: { color: DARK.tick } },
        tooltip: { callbacks: { label: c => `해지율: ${c.raw}%` } },
      },
      scales: {
        x: { ticks: { color: DARK.tick }, grid: { color: DARK.grid }, title: { display: true, text: h.y_label, color: DARK.color }, beginAtZero: true },
        y: { ticks: { color: DARK.tick }, grid: { color: DARK.grid } },
      },
    },
  });
}


/* =====================================================
  [E-6] drawChart6(h) — 가설6: 버블 (bubble)
  x=시간당요금, y=해지율, r=고객수(버블 크기)
  강조 버블: 선명한 색 + 흰 테두리 + 구간명 라벨
===================================================== */
function drawChart6(h) {
  const base = GRADE_COLOR[nowGrade];
  const isGrade = nowGrade !== 'ALL';

  const bgColors     = h.scatter.map((_, i) => (isGrade && h.highlight?.includes(i)) ? base + 'cc' : base + (isGrade ? '33' : '88'));
  const borderColors = h.scatter.map((_, i) => (isGrade && h.highlight?.includes(i)) ? '#ffffff'   : base + '66');
  const borderWidths = h.scatter.map((_, i) => (isGrade && h.highlight?.includes(i)) ? 3           : 1);

  makeChart('chart6', {
    type: 'bubble',
    data: {
      datasets: [{
        label: '요금구간별 해지율',
        data: h.scatter,
        backgroundColor: bgColors,
        borderColor: borderColors,
        borderWidth: borderWidths,
        hoverBackgroundColor: base,
        hoverBorderColor: '#ffffff',
        hoverBorderWidth: 3,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 700 },
      plugins: {
        legend: { labels: { color: DARK.tick } },
        tooltip: {
          callbacks: {
            label: ctx => {
              const d   = ctx.raw;
              const lbl = h.labels ? h.labels[ctx.dataIndex] : '';
              return [
                `구간: ${lbl}`,
                `시간당요금: ${d.x.toFixed(4)}`,
                `해지율: ${d.y}%`,
                `고객수: ~${d.r * 300}명`,
              ];
            },
          },
        },
      },
      scales: {
        x: { ticks: { color: DARK.tick }, grid: { color: DARK.grid }, title: { display: true, text: '평균 시간당 요금', color: DARK.color } },
        y: { ticks: { color: DARK.tick }, grid: { color: DARK.grid }, title: { display: true, text: '해지율 (%)',       color: DARK.color }, beginAtZero: true },
      },
    },
    // 강조 버블 위에 구간명 텍스트 라벨 추가
    plugins: [{
      id: 'bubbleLbl',
      afterDatasetsDraw(chart) {
        if (!h.highlight || !h.highlight.length || nowGrade === 'ALL') return;
        const { ctx } = chart;
        chart.getDatasetMeta(0).data.forEach((pt, i) => {
          if (!h.highlight.includes(i)) return;
          ctx.save();
          ctx.fillStyle    = '#ffffff';
          ctx.font         = 'bold 11px Noto Sans KR, sans-serif';
          ctx.textAlign    = 'center';
          ctx.textBaseline = 'bottom';
          ctx.fillText(h.labels ? h.labels[i] : '', pt.x, pt.y - pt.options.radius - 6);
          ctx.restore();
        });
      },
    }],
  });
}


/* =====================================================
  [F] popCards(grade) — 카드 팝 애니메이션
  역할: 등급 변경 시 카드들이 순서대로 팝업 효과
  ★ 타이밍 바꾸려면 i*80 (80ms 간격) 수정
===================================================== */
function popCards(grade) {
  const color = GRADE_COLOR[grade];

  document.querySelectorAll('.chart-card').forEach((card, i) => {
    setTimeout(() => {
      card.style.borderColor = color;
      card.style.boxShadow   = `0 0 32px ${color}60, 0 10px 30px rgba(0,0,0,.4)`;
      card.classList.add('pop');

      // 1초 후 원래대로 복원
      setTimeout(() => {
        card.classList.remove('pop');
        card.style.borderColor = '';
        card.style.boxShadow   = '';
      }, 1000);

    }, i * 80); // 카드마다 80ms씩 딜레이
  });
}
