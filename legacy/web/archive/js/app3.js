/* ============================================================
   app.js — 대시보드 전체 동작
   Flask 경로: static/js/app.js

   [구성]
     [A] 전역 상수 (등급색·메시지·고정데이터·강조인덱스)
     [B] Chart.js 전역 툴팁 스타일
     [C] 공통 유틸 (toggleSub, 시계, makeChart)
     [D] 차트 그리기 함수
         drawChart1() — 세로 막대 (상담전화 vs 해지건수)
         drawChart2() — 라인 (가입일 구간별 해지율)
         drawChart3() — 스택 막대-도넛형 (통화시간 구간별)
         drawChart4() — 레이더 (상담강도 해지 vs 유지)
     [E] drawAll(grade) — 4개 차트 일괄 렌더링
     [F] 등급 버튼 이벤트 (클릭 → 강조 + 팝 효과)
     [G] loadData(grade) — 서버 /get_all_data 연동 (Flask용)
     [H] autoInsight / sendChat — AI 챗봇 API 연동 (Flask용)

   [수정 포인트]
     - 등급별 강조 구간 → HIGHLIGHT 객체
     - 고정 차트 데이터  → C1_LABELS/VALS, C2_*, C3_*, C4_*
     - 등급 색상        → GC 객체
     - 서버 API 경로    → loadData() 내 fetch('/get_all_data')
   ============================================================ */

/* ── 공통 ── */
function toggleSub(el){el.classList.toggle('open');const s=el.nextElementSibling;if(s&&s.classList.contains('sub-menu'))s.classList.toggle('open');}
(function tick(){const n=new Date(),p=v=>String(v).padStart(2,'0'),el=document.getElementById('footerTime');if(el)el.textContent=`${n.getFullYear()}.${p(n.getMonth()+1)}.${p(n.getDate())}  ${p(n.getHours())}:${p(n.getMinutes())}`;setTimeout(tick,60000);})();

/* ── 등급별 색상 (실제 app.js와 동일) ── */
const GC = {ALL:'#4f46e5', A:'#dc2626', B:'#0ea5e9', C:'#7c3aed', D:'#0891b2'};
const GM = {ALL:'전체 고객 데이터', A:'A등급 — 최고위험', B:'B등급 — 고위험', C:'C등급 — 중위험', D:'D등급 — 저위험'};

/* ── 차트 축/격자 공통 스타일 ── */
const GRID = '#eaecf4';
const TICK = '#6b7280';

let ch={}, ng='ALL';

/* ── Chart.js 전역 툴팁 스타일 — 크고 읽기 쉽게 ── */
Chart.defaults.plugins.tooltip.backgroundColor = 'rgba(17,24,39,0.92)';
Chart.defaults.plugins.tooltip.titleColor       = '#f9fafb';
Chart.defaults.plugins.tooltip.bodyColor        = '#e5e7eb';
Chart.defaults.plugins.tooltip.borderColor      = 'rgba(255,255,255,.12)';
Chart.defaults.plugins.tooltip.borderWidth      = 1;
Chart.defaults.plugins.tooltip.titleFont        = {size:13, weight:'700', family:'Noto Sans KR'};
Chart.defaults.plugins.tooltip.bodyFont         = {size:13, family:'Noto Sans KR'};
Chart.defaults.plugins.tooltip.padding          = {top:10, bottom:10, left:14, right:14};
Chart.defaults.plugins.tooltip.cornerRadius     = 10;
Chart.defaults.plugins.tooltip.caretSize        = 7;
Chart.defaults.plugins.tooltip.displayColors    = true;
Chart.defaults.plugins.tooltip.boxPadding       = 5;
function mc(id,cfg){if(ch[id])ch[id].destroy();ch[id]=new Chart(document.getElementById(id),cfg);}

/* ────────────────────────────────────────
   01. 세로 막대 — 상담전화건수 vs 해지건수
   배경: 평균 참조선 + 막대 그라디언트
   ────────────────────────────────────────*/
function drawChart1(g,d){
  const b = GC[g];
  const ctx = document.getElementById('chart1').getContext('2d');
  const h = ctx.canvas.clientHeight || 300;

  // 위→아래 그라디언트
  const grad = ctx.createLinearGradient(0,0,0,h);
  grad.addColorStop(0, b+'ee');
  grad.addColorStop(1, b+'22');

  const labels = d.labels;
  const vals   = d.vals;
  const avg    = vals.reduce((a,v)=>a+v,0)/vals.length;

  // 평균선 플러그인
  const avgPlugin = {
    id:'avgLine',
    afterDraw(chart){
      const {ctx,scales:{y,x}}=chart;
      const yp=y.getPixelForValue(avg);
      ctx.save();
      ctx.setLineDash([5,4]);
      ctx.strokeStyle=b+'99';
      ctx.lineWidth=1.5;
      ctx.beginPath();ctx.moveTo(x.left,yp);ctx.lineTo(x.right,yp);ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle=b;
      ctx.font='600 10px Noto Sans KR,sans-serif';
      ctx.textAlign='right';
      ctx.fillText('평균 '+Math.round(avg)+'건',x.right-4,yp-5);
      ctx.restore();
    }
  };

  mc('chart1',{
    type:'bar',
    data:{
      labels,
      datasets:[{
        label:'해지건수',
        data:vals,
        backgroundColor: grad,
        borderColor:'transparent',
        borderWidth:0,
        borderRadius:7,
        borderSkipped:false,
      }]
    },
    options:{
      responsive:true, maintainAspectRatio:false,
      animation:{duration:700,easing:'easeInOutQuart'},
      plugins:{
        legend:{labels:{color:TICK,boxWidth:10,font:{size:11}}},
        tooltip:{callbacks:{label:c=>` 해지건수: ${c.raw}건`}},
      },
      scales:{
        x:{ticks:{color:TICK,font:{size:11}},grid:{color:GRID}},
        y:{ticks:{color:TICK,font:{size:11}},grid:{color:GRID},
           title:{display:true,text:'해지 건수',color:TICK,font:{size:11}},beginAtZero:true},
      }
    },
    plugins:[avgPlugin]
  });
}

/* ────────────────────────────────────────
   02. 라인 — 가입일 구간별 해지율
   면 채우기 + 포인트 강조
   ────────────────────────────────────────*/
function drawChart2(g,d){
  const b = GC[g];
  const ctx = document.getElementById('chart2').getContext('2d');
  const h = ctx.canvas.clientHeight || 300;

  const areaGrad = ctx.createLinearGradient(0,0,0,h);
  areaGrad.addColorStop(0, b+'44');
  areaGrad.addColorStop(1, b+'04');

  mc('chart2',{
    type:'line',
    data:{
      labels:d.labels,
      datasets:[{
        label:'해지율 (%)',
        data:d.vals,
        borderColor:b,
        backgroundColor:areaGrad,
        borderWidth:2.5,
        pointRadius:[5,8,5,5],
        pointBackgroundColor:['#fff','#fff','#fff','#fff'],
        pointBorderColor:b,
        pointBorderWidth:2.5,
        tension:0.4, fill:true,
      }]
    },
    options:{
      responsive:true, maintainAspectRatio:false,
      animation:{duration:700},
      plugins:{legend:{labels:{color:TICK,boxWidth:10,font:{size:11}}}},
      scales:{
        x:{ticks:{color:TICK,font:{size:11}},grid:{color:GRID}},
        y:{ticks:{color:TICK,font:{size:11}},grid:{color:GRID},
           title:{display:true,text:'해지율 (%)',color:TICK,font:{size:11}},beginAtZero:true},
      }
    }
  });
}

/* ────────────────────────────────────────
   03. 도넛형 막대 — 총통화시간 구간별 해지율/유지율
   하나의 100% 스택 막대에 해지/유지 비율을 도넛처럼 분할
   구간별로 행이 나뉘어 도넛의 시각적 분할감을 막대로 표현
   ────────────────────────────────────────*/
function drawChart3(g,d){
  const b = GC[g];
  const labels = d.labels;
  const churn  = d.churn;
  const retain = churn.map(v => 100-v);

  // 해지율 색: 등급색, 유지율 색: 연한 회색
  const churnBg  = b + 'cc';
  const retainBg = '#e2e8f0';

  // 값 라벨 플러그인 (막대 끝에 % 표시)
  const labelPlugin = {
    id:'barLabel3',
    afterDatasetsDraw(chart){
      const {ctx} = chart;
      chart.getDatasetMeta(0).data.forEach((bar, i)=>{
        ctx.save();
        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 11px Noto Sans KR,sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        const cx = (bar.x + chart.scales.x.getPixelForValue(0)) / 2;
        if(churn[i] > 8) ctx.fillText(churn[i]+'%', cx, bar.y);
        ctx.restore();
      });
    }
  };

  mc('chart3',{
    type:'bar',
    data:{
      labels,
      datasets:[
        {
          label:'해지율',
          data:churn,
          backgroundColor: churnBg,
          borderColor:'transparent',
          borderWidth:0,
          borderRadius:{topLeft:5,bottomLeft:5,topRight:0,bottomRight:0},
          borderSkipped:false,
          stack:'s',
        },
        {
          label:'유지율',
          data:retain,
          backgroundColor: retainBg,
          borderColor:'transparent',
          borderWidth:0,
          borderRadius:{topLeft:0,bottomLeft:0,topRight:5,bottomRight:5},
          borderSkipped:false,
          stack:'s',
        }
      ]
    },
    options:{
      indexAxis:'y',
      responsive:true, maintainAspectRatio:false,
      animation:{duration:700,easing:'easeInOutQuart'},
      plugins:{
        legend:{
          labels:{
            color:TICK, font:{size:11}, boxWidth:12,
            usePointStyle:true, pointStyle:'rectRounded',
          }
        },
        tooltip:{
          callbacks:{
            label: c => c.datasetIndex===0
              ? ` 해지율: ${c.raw}%`
              : ` 유지율: ${c.raw}%`
          }
        },
      },
      scales:{
        x:{
          stacked:true,
          ticks:{color:TICK,font:{size:11},callback:v=>v+'%'},
          grid:{color:GRID},
          max:100,
        },
        y:{
          stacked:true,
          ticks:{color:TICK,font:{size:11}},
          grid:{color:'transparent'},
        },
      }
    },
    plugins:[labelPlugin]
  });
}

/* ────────────────────────────────────────
   04. 레이더 — 상담강도 구간별 해지율
   해지 vs 유지, 얇은 선 + 반투명 채우기
   ────────────────────────────────────────*/
function drawChart4(g,d){
  mc('chart4',{
    type:'radar',
    data:{
      labels:['주간','저녁','밤'],
      datasets:[
        {
          label:'해지 고객',
          data:d.churn,
          backgroundColor:'rgba(220,38,38,.1)',
          borderColor:'#dc2626',
          borderWidth:2,
          pointRadius:5,
          pointBackgroundColor:'#fff',
          pointBorderColor:'#dc2626',
          pointBorderWidth:2,
        },
        {
          label:'유지 고객',
          data:d.retain,
          backgroundColor:'rgba(71,85,105,.1)',
          borderColor:'#475569',
          borderWidth:2,
          pointRadius:5,
          pointBackgroundColor:'#fff',
          pointBorderColor:'#475569',
          pointBorderWidth:2,
        }
      ]
    },
    options:{
      responsive:true, maintainAspectRatio:false,
      animation:{duration:700},
      plugins:{
        legend:{
          labels:{
            color:TICK,font:{size:11},
            boxWidth:10,
            usePointStyle:true,  /* 원형 범례 — 외곽선 없음 */
            pointStyle:'circle',
          }
        }
      },
      scales:{
        r:{
          ticks:{color:TICK,backdropColor:'transparent',font:{size:9},stepSize:10},
          grid:{color:GRID},
          angleLines:{color:GRID},
          pointLabels:{color:'#111827',font:{size:12,weight:'600'}},
        }
      }
    }
  });
}

/* ══════════════════════════════════════════════════════
   고정 데이터 (전체 구간 — ALL 기준, 항상 표시)
   등급 선택 시 해당 인덱스만 강조색, 나머지는 연한 회색
   ══════════════════════════════════════════════════════ */

// 01 막대: 상담전화 횟수별 해지건수 (6구간)
const C1_LABELS = ['0회','1~2회','3~4회','5~6회','7~8회','9~11회'];
const C1_VALS   = [520, 640, 1620, 380, 250, 180];

// 02 라인: 가입일 구간별 해지율 (4구간)
const C2_LABELS = ['신규(~100일)','단기(101~300일)','중기(301~500일)','장기(500일+)'];
const C2_VALS   = [28, 31, 18, 10];

// 03 스택막대: 통화시간 구간별 해지율/유지율 (4구간)
const C3_LABELS = ['매우낮음(~530분)','낮음(531~700분)','보통(701~870분)','높음(871분+)'];
const C3_CHURN  = [38, 27, 22, 13];

// 04 레이더: 상담강도(주간/저녁/밤) — 해지 vs 유지
const C4_CHURN  = [35, 20, 30];
const C4_RETAIN = [20, 28, 15];

/* 등급별 강조 인덱스 정의
   각 차트에서 어떤 구간이 해당 등급의 특징인지 매핑 */
const HIGHLIGHT = {
  ALL: { c1:[], c2:[], c3:[], c4:[] },
  A:   { c1:[2,3,4], c2:[0,1], c3:[0,1], c4:[0,2] },   // A: 상담많음·신규·통화짧음·주간/밤
  B:   { c1:[1,2],   c2:[0,1], c3:[1,2], c4:[0,1] },   // B: 중간상담·단기·중간통화
  C:   { c1:[0,1],   c2:[2],   c3:[2],   c4:[1]   },   // C: 상담적음·중기·보통통화·저녁
  D:   { c1:[0],     c2:[3],   c3:[3],   c4:[1,2] },   // D: 상담없음·장기·통화많음
};

const MUTED = '#d1d5db';  // 비강조 구간 색상 (연한 회색)

/* ── 초기 렌더링 ── */
function drawAll(g){
  drawChart1(g);
  drawChart2(g);
  drawChart3(g);
  drawChart4(g);
}

/* ────────────────────────────────────────
   01. 세로 막대 — 상담전화건수 vs 해지건수
   ALL: 전체 그라디언트, 등급 선택: 해당 구간만 등급색·나머지 회색
   ────────────────────────────────────────*/
function drawChart1(g){
  const b   = GC[g];
  const hl  = HIGHLIGHT[g].c1;
  const ctx = document.getElementById('chart1').getContext('2d');
  const h   = ctx.canvas.clientHeight || 300;

  // 전체(ALL)일 때는 그라디언트, 등급 선택 시 강조/비강조 색
  let bgColors;
  if(g === 'ALL'){
    const grad = ctx.createLinearGradient(0,0,0,h);
    grad.addColorStop(0, b+'ee');
    grad.addColorStop(1, b+'33');
    bgColors = C1_VALS.map(()=>grad);
  } else {
    bgColors = C1_VALS.map((_,i)=> hl.includes(i) ? b+'ee' : MUTED);
  }

  const avg = C1_VALS.reduce((a,v)=>a+v,0)/C1_VALS.length;
  const avgPlugin = {
    id:'avgLine1',
    afterDraw(chart){
      const {ctx,scales:{y,x}}=chart;
      const yp=y.getPixelForValue(avg);
      ctx.save();
      ctx.setLineDash([5,4]);
      ctx.strokeStyle=b+'88';
      ctx.lineWidth=1.5;
      ctx.beginPath();ctx.moveTo(x.left,yp);ctx.lineTo(x.right,yp);ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle=b;
      ctx.font='600 10px Noto Sans KR,sans-serif';
      ctx.textAlign='right';
      ctx.fillText('평균 '+Math.round(avg)+'건',x.right-4,yp-5);
      ctx.restore();
    }
  };

  mc('chart1',{
    type:'bar',
    data:{
      labels:C1_LABELS,
      datasets:[{
        label:'해지건수',
        data:C1_VALS,
        backgroundColor:bgColors,
        borderColor:'transparent',
        borderWidth:0,
        borderRadius:7,
        borderSkipped:false,
      }]
    },
    options:{
      responsive:true, maintainAspectRatio:false,
      animation:{duration:600,easing:'easeInOutQuart'},
      plugins:{
        legend:{labels:{color:TICK,boxWidth:10,font:{size:11}}},
        tooltip:{callbacks:{label:c=>` 해지건수: ${c.raw}건`}},
      },
      scales:{
        x:{ticks:{color:TICK,font:{size:11}},grid:{color:GRID}},
        y:{ticks:{color:TICK,font:{size:11}},grid:{color:GRID},
           title:{display:true,text:'해지 건수',color:TICK,font:{size:11}},beginAtZero:true},
      }
    },
    plugins:[avgPlugin]
  });
}

/* ────────────────────────────────────────
   02. 라인 — 가입일 구간별 해지율
   ALL: 전체선+면, 등급: 해당 포인트만 크고 진하게·나머지 회색
   ────────────────────────────────────────*/
function drawChart2(g){
  const b  = GC[g];
  const hl = HIGHLIGHT[g].c2;
  const ctx= document.getElementById('chart2').getContext('2d');
  const h  = ctx.canvas.clientHeight||300;

  const areaGrad = ctx.createLinearGradient(0,0,0,h);
  areaGrad.addColorStop(0, b+'44');
  areaGrad.addColorStop(1, b+'04');

  // 포인트별 색상: 강조=등급색·크게, 비강조=회색·작게
  const ptColor  = C2_VALS.map((_,i)=> (g==='ALL'||hl.includes(i)) ? b : MUTED);
  const ptRadius = C2_VALS.map((_,i)=> (g==='ALL') ? 5 : hl.includes(i) ? 9 : 4);
  const ptBorder = C2_VALS.map((_,i)=> (g==='ALL'||hl.includes(i)) ? 2.5 : 1);

  mc('chart2',{
    type:'line',
    data:{
      labels:C2_LABELS,
      datasets:[{
        label:'해지율 (%)',
        data:C2_VALS,
        borderColor: g==='ALL' ? b : '#d1d5db',
        backgroundColor:areaGrad,
        borderWidth:2.5,
        pointRadius:ptRadius,
        pointBackgroundColor:'#fff',
        pointBorderColor:ptColor,
        pointBorderWidth:ptBorder,
        tension:0.4, fill:true,
      }]
    },
    options:{
      responsive:true, maintainAspectRatio:false,
      animation:{duration:600},
      plugins:{legend:{labels:{color:TICK,boxWidth:10,font:{size:11}}}},
      scales:{
        x:{ticks:{color:TICK,font:{size:11}},grid:{color:GRID}},
        y:{ticks:{color:TICK,font:{size:11}},grid:{color:GRID},
           title:{display:true,text:'해지율 (%)',color:TICK,font:{size:11}},beginAtZero:true},
      }
    }
  });
}

/* ────────────────────────────────────────
   03. 스택 막대(도넛형) — 통화시간 구간별 해지/유지율
   ALL: 전체 등급색, 등급: 해당 구간 막대만 진한 등급색·나머지 회색
   ────────────────────────────────────────*/
function drawChart3(g){
  const b  = GC[g];
  const hl = HIGHLIGHT[g].c3;
  const retain = C3_CHURN.map(v=>100-v);

  // 해지율 막대 색상: 강조=등급색, 비강조=회색
  const churnBg = C3_CHURN.map((_,i)=>
    (g==='ALL'||hl.includes(i)) ? b+'cc' : MUTED+'aa'
  );

  const labelPlugin = {
    id:'barLabel3',
    afterDatasetsDraw(chart){
      const {ctx}=chart;
      chart.getDatasetMeta(0).data.forEach((bar,i)=>{
        const isHl = g==='ALL' || hl.includes(i);
        if(!isHl && g!=='ALL') return;
        ctx.save();
        ctx.fillStyle='#fff';
        ctx.font='bold 11px Noto Sans KR,sans-serif';
        ctx.textAlign='center'; ctx.textBaseline='middle';
        const cx=(bar.x+chart.scales.x.getPixelForValue(0))/2;
        if(C3_CHURN[i]>8) ctx.fillText(C3_CHURN[i]+'%',cx,bar.y);
        ctx.restore();
      });
    }
  };

  mc('chart3',{
    type:'bar',
    data:{
      labels:C3_LABELS,
      datasets:[
        { label:'해지율', data:C3_CHURN, backgroundColor:churnBg,
          borderColor:'transparent', borderWidth:0,
          borderRadius:{topLeft:5,bottomLeft:5,topRight:0,bottomRight:0},
          borderSkipped:false, stack:'s' },
        { label:'유지율', data:retain, backgroundColor:'#e2e8f0',
          borderColor:'transparent', borderWidth:0,
          borderRadius:{topLeft:0,bottomLeft:0,topRight:5,bottomRight:5},
          borderSkipped:false, stack:'s' }
      ]
    },
    options:{
      indexAxis:'y', responsive:true, maintainAspectRatio:false,
      animation:{duration:600,easing:'easeInOutQuart'},
      plugins:{
        legend:{labels:{color:TICK,font:{size:11},boxWidth:12,usePointStyle:true,pointStyle:'rectRounded'}},
        tooltip:{callbacks:{label:c=>c.datasetIndex===0?` 해지율: ${c.raw}%`:` 유지율: ${c.raw}%`}},
      },
      scales:{
        x:{stacked:true,ticks:{color:TICK,font:{size:11},callback:v=>v+'%'},grid:{color:GRID},max:100},
        y:{stacked:true,ticks:{color:TICK,font:{size:11}},grid:{color:'transparent'}},
      }
    },
    plugins:[labelPlugin]
  });
}

/* ────────────────────────────────────────
   04. 레이더 — 상담강도 구간별 해지율
   ALL: 해지(레드)/유지(슬레이트) 고정
   등급: 해당 축(c4 hl 인덱스)만 강조색 포인트·나머지 회색
   ────────────────────────────────────────*/
function drawChart4(g){
  const b  = GC[g];
  const hl = HIGHLIGHT[g].c4;
  const labels = ['주간','저녁','밤'];

  // 강조 포인트: 등급색 크게, 비강조: 회색 작게
  const ptColor  = labels.map((_,i)=>(g==='ALL'||hl.includes(i))? b : MUTED);
  const ptRadius = labels.map((_,i)=>(g==='ALL') ? 5 : hl.includes(i) ? 9 : 4);

  mc('chart4',{
    type:'radar',
    data:{
      labels,
      datasets:[
        { label:'해지 고객', data:C4_CHURN,
          backgroundColor: g==='ALL' ? 'rgba(220,38,38,.1)' : b+'18',
          borderColor: g==='ALL' ? '#dc2626' : b,
          borderWidth:2,
          pointRadius:ptRadius,
          pointBackgroundColor:'#fff',
          pointBorderColor:ptColor,
          pointBorderWidth:2,
        },
        { label:'유지 고객', data:C4_RETAIN,
          backgroundColor:'rgba(71,85,105,.1)',
          borderColor:'#94a3b8',
          borderWidth:1.5,
          pointRadius:4,
          pointBackgroundColor:'#fff',
          pointBorderColor:'#94a3b8',
          pointBorderWidth:1.5,
        }
      ]
    },
    options:{
      responsive:true, maintainAspectRatio:false,
      animation:{duration:600},
      plugins:{legend:{labels:{color:TICK,font:{size:11},boxWidth:10,usePointStyle:true,pointStyle:'circle'}}},
      scales:{r:{
        ticks:{color:TICK,backdropColor:'transparent',font:{size:9},stepSize:10},
        grid:{color:GRID}, angleLines:{color:GRID},
        pointLabels:{color:'#111827',font:{size:12,weight:'600'}},
      }}
    }
  });
}

/* ── 등급 버튼 ── */
.grade-section{margin-bottom:14px;display:flex;align-items:center;gap:10px;}
.section-label{font-size:.52rem;font-weight:700;letter-spacing:2px;color:var(--muted);text-transform:uppercase;white-space:nowrap;}
.grade-btns{display:flex;gap:5px;}
.grade-btn{padding:4px 14px;border-radius:5px;font-family:'Noto Sans KR',sans-serif;font-size:.7rem;font-weight:700;cursor:pointer;transition:all .16s;background:#fff;}
.btn-all{border:1.5px solid rgba(79,70,229,.4);color:var(--all);}
.btn-a{border:1.5px solid rgba(220,38,38,.4);color:var(--a);}
.btn-b{border:1.5px solid rgba(234,88,12,.4);color:var(--b);}
.btn-c{border:1.5px solid rgba(124,58,237,.4);color:var(--c);}
.btn-d{border:1.5px solid rgba(8,145,178,.4);color:var(--d);}
.btn-all.active{border:2px solid var(--all);background:rgba(79,70,229,.05);}
.btn-a.active{border:2px solid var(--a);background:rgba(220,38,38,.04);}
.btn-b.active{border:2px solid var(--b);background:rgba(234,88,12,.04);}
.btn-c.active{border:2px solid var(--c);background:rgba(124,58,237,.04);}
.btn-d.active{border:2px solid var(--d);background:rgba(8,145,178,.04);}
.grade-btn:hover{filter:brightness(.97);transform:translateY(-1px);}
.grade-bar{display:none;align-items:center;gap:8px;padding:5px 13px;margin-bottom:12px;background:var(--surface);border:1px solid var(--border);border-radius:8px;font-size:.72rem;}
.grade-bar.show{display:flex;}
.grade-dot{width:6px;height:6px;border-radius:50%;flex-shrink:0;}

/* ── 콘텐츠 레이아웃 ── */
.content-layout{display:flex;gap:12px;align-items:stretch;}

/* ── 차트 그리드 2×2  — 충분히 크게 ── */
.charts-grid{
  display:grid;
  grid-template-columns:repeat(2,1fr);
  gap:14px;
  flex:1;min-width:0;
}

/* ── 차트 카드 — 완성도 높이기 ── */
.chart-card{
  background:var(--surface);
  border:1px solid var(--border);
  border-radius:14px;
  padding:18px 20px;
  display:flex;flex-direction:column;
  overflow:hidden;
  box-shadow:var(--shadow-sm);
  transition:transform .25s ease,box-shadow .25s ease;
  position:relative;
  /* 높이: 충분히 크게 */
  height:380px;
}
.chart-card::before{
  /* 카드 상단 미묘한 그라디언트 배경 */
  content:'';position:absolute;top:0;left:0;right:0;height:80px;
  background:linear-gradient(180deg,rgba(79,70,229,.03) 0%,transparent 100%);
  border-radius:14px 14px 0 0;
  pointer-events:none;
}
.chart-card:hover{transform:translateY(-4px);box-shadow:var(--shadow-lg);}

.chart-card-head{
  display:flex;align-items:center;gap:10px;
  margin-bottom:14px;padding-bottom:12px;
  border-bottom:1px solid var(--border);
  flex-shrink:0;position:relative;z-index:1;
}
.chart-num{
  font-size:.56rem;font-weight:700;
  color:var(--accent);
  background:rgba(79,70,229,.07);
  border:1px solid rgba(79,70,229,.15);
  padding:2px 7px;border-radius:4px;letter-spacing:1.2px;
}
.chart-title{font-size:.82rem;font-weight:700;color:var(--text);}

.chart-wrap{position:relative;flex:1;min-height:0;}

/* ── AI 챗봇 ── */
.chatbot-sidebar{width:108px;flex-shrink:0;display:flex;flex-direction:column;gap:0;align-self:stretch;}
.chat-arrow{display:flex;align-items:center;justify-content:center;flex-shrink:0;height:26px;position:relative;}
.chat-arrow::before{content:'';position:absolute;left:50%;top:0;bottom:0;width:1px;background:var(--border-dk);transform:translateX(-50%);}
.chat-arrow span{background:var(--bg);padding:0 5px;position:relative;z-index:1;color:#94a3b8;font-size:1.1rem;line-height:1;font-weight:900;}
.chatbot-card{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:11px 10px;flex:1;display:flex;flex-direction:column;min-height:0;overflow:hidden;box-shadow:var(--shadow-sm);}
.chatbot-header{display:flex;align-items:center;gap:5px;margin-bottom:7px;padding-bottom:6px;border-bottom:1px solid var(--border);flex-shrink:0;}
.ai-badge{font-size:.46rem;font-weight:700;padding:1px 5px;border-radius:3px;letter-spacing:.8px;color:#fff;background:#374151;}
.chatbot-title{font-size:.62rem;font-weight:700;color:var(--text);}
.insight-main{flex:1;display:flex;flex-direction:column;justify-content:center;gap:3px;}
.insight-number{font-size:1.35rem;font-weight:900;line-height:1;color:#2563eb;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.insight-label{font-size:.6rem;font-weight:600;color:var(--text2);line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.insight-sub{font-size:.52rem;color:var(--muted);line-height:1.5;border-top:1px solid var(--border);padding-top:5px;margin-top:3px;}
.insight-sub strong{color:var(--text2);}

/* ── 하단 푸터 ── */
.footer-bar{height:32px;background:var(--surface);border-top:1px solid var(--border);display:flex;align-items:center;padding:0 22px;gap:12px;}
.footer-text{font-size:.52rem;color:var(--muted);}
.footer-right{margin-left:auto;font-size:.52rem;color:var(--muted);}
</style>
</head>
<body>

<!-- 사이드바 -->
<nav class="sidebar">
  <div class="sidebar-logo">
    <div class="logo-icon">📡</div>
    <div><div class="logo-text">Oneplus³</div><div class="logo-sub">이탈 예측 시스템</div></div>
  </div>
  <div class="sidebar-nav">
    <div class="nav-section-label">메인 메뉴</div>
    <div class="nav-item active">대시보드 홈</div>
    <div class="nav-item open" onclick="toggleSub(this)">고객 분석<span class="nav-arrow">▶</span></div>
    <div class="sub-menu open">
      <div class="sub-item active">이탈 위험군</div>
      <div class="sub-item">등급별 현황</div>
      <div class="sub-item">충성 고객</div>
    </div>
    <div class="nav-item" onclick="toggleSub(this)">이탈 예측<span class="nav-arrow">▶</span></div>
    <div class="sub-menu">
      <div class="sub-item">예측 모델</div>
      <div class="sub-item">Feature 중요도</div>
      <div class="sub-item">시뮬레이션</div>
    </div>
    <div class="nav-item" onclick="toggleSub(this)">상담 데이터<span class="nav-arrow">▶</span></div>
    <div class="sub-menu">
      <div class="sub-item">통화 기록</div>
      <div class="sub-item">상담 강도 분석</div>
    </div>
    <div class="nav-section-label">리포트</div>
    <div class="nav-item">월간 리포트</div>
    <div class="nav-item">성과 추적</div>
    <div class="nav-section-label">시스템</div>
    <div class="nav-item">설정</div>
    <div class="nav-item">도움말</div>
  </div>
  <div class="sidebar-footer"></div>
</nav>

<!-- 메인 -->
<div class="page">

  <div class="topbar">
    <div>
      <div class="topbar-title">통신 고객 이탈 예측 대시보드</div>
      <div class="topbar-sub">Customer Churn Prediction · 데이터 기반 이탈 예측 시스템</div>
    </div>
    <span class="topbar-badge">✦ GROQ</span>
  </div>

  <div class="kpi-bar">
    <div class="kpi-item pass">
      <div class="kpi-left"><span class="kpi-label">Macro F1 Score</span><span class="kpi-value">0.87</span></div>
      <div class="kpi-right"><span class="kpi-target">목표 ≥ 0.85</span><span class="kpi-badge badge-pass">✔ 목표 달성</span></div>
    </div>
    <div class="kpi-item fail">
      <div class="kpi-left"><span class="kpi-label">해지 고객 Recall</span><span class="kpi-value">0.76</span></div>
      <div class="kpi-right"><span class="kpi-target">목표 ≥ 0.80</span><span class="kpi-badge badge-fail">✘ 미달성</span></div>
    </div>
    <div class="kpi-item pass">
      <div class="kpi-left"><span class="kpi-label">고위험군 상위 20% 해지율</span><span class="kpi-value">38.2<span class="kpi-unit">%</span></span></div>
      <div class="kpi-right"><span class="kpi-target">전체 평균 14.5% 대비</span><span class="kpi-badge badge-pass">✔ 유의미한 상승</span></div>
    </div>
  </div>

  <div class="main-content">

    <div class="grade-section">
      <p class="section-label">▸ Risk Grade</p>
      <div class="grade-btns">
        <button class="grade-btn btn-all active" data-grade="ALL">전체</button>
        <button class="grade-btn btn-a" data-grade="A">A등급</button>
        <button class="grade-btn btn-b" data-grade="B">B등급</button>
        <button class="grade-btn btn-c" data-grade="C">C등급</button>
        <button class="grade-btn btn-d" data-grade="D">D등급</button>
      </div>
    </div>
    <div class="grade-bar" id="gradeBar"><div class="grade-dot" id="gradeDot"></div><span id="gradeText"></span></div>

    <div class="content-layout">

      <section class="charts-grid">

        <!-- 01. 막대: 상담전화건수 vs 해지건수 -->
        <article class="chart-card" id="card1">
          <div class="chart-card-head">
            <span class="chart-num">01</span>
            <span class="chart-title">상담전화건수 vs 해지건수</span>
            
          </div>
          <div class="chart-wrap"><canvas id="chart1"></canvas></div>
        </article>

        <!-- 02. 라인: 가입일 구간별 해지율 -->
        <article class="chart-card" id="card2">
          <div class="chart-card-head">
            <span class="chart-num">02</span>
            <span class="chart-title">가입일 구간별 해지율</span>
            
          </div>
          <div class="chart-wrap"><canvas id="chart2"></canvas></div>
        </article>

        <!-- 03. 가로막대: 총통화시간 구간별 해지율 (도넛 대체) -->
        <article class="chart-card" id="card3">
          <div class="chart-card-head">
            <span class="chart-num">03</span>
            <span class="chart-title">총통화시간 구간별 해지율</span>
            
          </div>
          <div class="chart-wrap"><canvas id="chart3"></canvas></div>
        </article>

        <!-- 04. 레이더: 상담강도 구간별 해지율 -->
        <article class="chart-card" id="card4">
          <div class="chart-card-head">
            <span class="chart-num">04</span>
            <span class="chart-title">상담강도 구간별 해지율</span>
            
          </div>
          <div class="chart-wrap"><canvas id="chart4"></canvas></div>
        </article>

      </section>

      <!-- AI 챗봇 -->
      <aside class="chatbot-sidebar">
        <div class="chatbot-card">
          <div class="chatbot-header"><span class="ai-badge">AI</span><span class="chatbot-title">현황 요약</span></div>
          <div class="insight-main">
            <div class="insight-number">−14.5%</div>
            <div class="insight-label">이탈 위험 고객 감지</div>
            <div class="insight-sub"><strong>상담 4회↑</strong> 이탈률 42%<br><strong>신규 90일↓</strong> 이탈률 31%</div>
          </div>
        </div>
        <div class="chat-arrow"><span>▼</span></div>
        <div class="chatbot-card">
          <div class="chatbot-header"><span class="ai-badge">AI</span><span class="chatbot-title">핵심 대책</span></div>
          <div class="insight-main">
            <div class="insight-number">90일</div>
            <div class="insight-label">신규 집중 케어</div>
            <div class="insight-sub"><strong>전담 상담사</strong> 즉시 배정<br><strong>3개월</strong> 요금 할인</div>
          </div>
        </div>
        <div class="chat-arrow"><span>▼</span></div>
        <div class="chatbot-card">
          <div class="chatbot-header"><span class="ai-badge">AI</span><span class="chatbot-title">예상 이익</span></div>
          <div class="insight-main">
            <div class="insight-number">+10%</div>
            <div class="insight-label">매출 증가 예상</div>
            <div class="insight-sub">이탈 방어 시 <strong>연 +26억</strong><br>ROI <strong>4.2배</strong></div>
          </div>
        </div>
      </aside>

    </div>
  </div>

  <div class="footer-bar">
    <span class="footer-text">Oneplus³ Churn Intelligence Platform</span>
    <span class="footer-right" id="footerTime"></span>
  </div>
</div>

<script>
/* ── 공통 ── */
function toggleSub(el){el.classList.toggle('open');const s=el.nextElementSibling;if(s&&s.classList.contains('sub-menu'))s.classList.toggle('open');}
(function tick(){const n=new Date(),p=v=>String(v).padStart(2,'0'),el=document.getElementById('footerTime');if(el)el.textContent=`${n.getFullYear()}.${p(n.getMonth()+1)}.${p(n.getDate())}  ${p(n.getHours())}:${p(n.getMinutes())}`;setTimeout(tick,60000);})();

/* ── 등급별 색상 (실제 app.js와 동일) ── */
const GC = {ALL:'#4f46e5', A:'#dc2626', B:'#0ea5e9', C:'#7c3aed', D:'#0891b2'};
const GM = {ALL:'전체 고객 데이터', A:'A등급 — 최고위험', B:'B등급 — 고위험', C:'C등급 — 중위험', D:'D등급 — 저위험'};

/* ── 차트 축/격자 공통 스타일 ── */
const GRID = '#eaecf4';
const TICK = '#6b7280';

let ch={}, ng='ALL';

/* ── Chart.js 전역 툴팁 스타일 — 크고 읽기 쉽게 ── */
Chart.defaults.plugins.tooltip.backgroundColor = 'rgba(17,24,39,0.92)';
Chart.defaults.plugins.tooltip.titleColor       = '#f9fafb';
Chart.defaults.plugins.tooltip.bodyColor        = '#e5e7eb';
Chart.defaults.plugins.tooltip.borderColor      = 'rgba(255,255,255,.12)';
Chart.defaults.plugins.tooltip.borderWidth      = 1;
Chart.defaults.plugins.tooltip.titleFont        = {size:13, weight:'700', family:'Noto Sans KR'};
Chart.defaults.plugins.tooltip.bodyFont         = {size:13, family:'Noto Sans KR'};
Chart.defaults.plugins.tooltip.padding          = {top:10, bottom:10, left:14, right:14};
Chart.defaults.plugins.tooltip.cornerRadius     = 10;
Chart.defaults.plugins.tooltip.caretSize        = 7;
Chart.defaults.plugins.tooltip.displayColors    = true;
Chart.defaults.plugins.tooltip.boxPadding       = 5;
function mc(id,cfg){if(ch[id])ch[id].destroy();ch[id]=new Chart(document.getElementById(id),cfg);}

/* ────────────────────────────────────────
   01. 세로 막대 — 상담전화건수 vs 해지건수
   배경: 평균 참조선 + 막대 그라디언트
   ────────────────────────────────────────*/
function drawChart1(g,d){
  const b = GC[g];
  const ctx = document.getElementById('chart1').getContext('2d');
  const h = ctx.canvas.clientHeight || 300;

  // 위→아래 그라디언트
  const grad = ctx.createLinearGradient(0,0,0,h);
  grad.addColorStop(0, b+'ee');
  grad.addColorStop(1, b+'22');

  const labels = d.labels;
  const vals   = d.vals;
  const avg    = vals.reduce((a,v)=>a+v,0)/vals.length;

  // 평균선 플러그인
  const avgPlugin = {
    id:'avgLine',
    afterDraw(chart){
      const {ctx,scales:{y,x}}=chart;
      const yp=y.getPixelForValue(avg);
      ctx.save();
      ctx.setLineDash([5,4]);
      ctx.strokeStyle=b+'99';
      ctx.lineWidth=1.5;
      ctx.beginPath();ctx.moveTo(x.left,yp);ctx.lineTo(x.right,yp);ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle=b;
      ctx.font='600 10px Noto Sans KR,sans-serif';
      ctx.textAlign='right';
      ctx.fillText('평균 '+Math.round(avg)+'건',x.right-4,yp-5);
      ctx.restore();
    }
  };

  mc('chart1',{
    type:'bar',
    data:{
      labels,
      datasets:[{
        label:'해지건수',
        data:vals,
        backgroundColor: grad,
        borderColor:'transparent',
        borderWidth:0,
        borderRadius:7,
        borderSkipped:false,
      }]
    },
    options:{
      responsive:true, maintainAspectRatio:false,
      animation:{duration:700,easing:'easeInOutQuart'},
      plugins:{
        legend:{labels:{color:TICK,boxWidth:10,font:{size:11}}},
        tooltip:{callbacks:{label:c=>` 해지건수: ${c.raw}건`}},
      },
      scales:{
        x:{ticks:{color:TICK,font:{size:11}},grid:{color:GRID}},
        y:{ticks:{color:TICK,font:{size:11}},grid:{color:GRID},
           title:{display:true,text:'해지 건수',color:TICK,font:{size:11}},beginAtZero:true},
      }
    },
    plugins:[avgPlugin]
  });
}

/* ────────────────────────────────────────
   02. 라인 — 가입일 구간별 해지율
   면 채우기 + 포인트 강조
   ────────────────────────────────────────*/
function drawChart2(g,d){
  const b = GC[g];
  const ctx = document.getElementById('chart2').getContext('2d');
  const h = ctx.canvas.clientHeight || 300;

  const areaGrad = ctx.createLinearGradient(0,0,0,h);
  areaGrad.addColorStop(0, b+'44');
  areaGrad.addColorStop(1, b+'04');

  mc('chart2',{
    type:'line',
    data:{
      labels:d.labels,
      datasets:[{
        label:'해지율 (%)',
        data:d.vals,
        borderColor:b,
        backgroundColor:areaGrad,
        borderWidth:2.5,
        pointRadius:[5,8,5,5],
        pointBackgroundColor:['#fff','#fff','#fff','#fff'],
        pointBorderColor:b,
        pointBorderWidth:2.5,
        tension:0.4, fill:true,
      }]
    },
    options:{
      responsive:true, maintainAspectRatio:false,
      animation:{duration:700},
      plugins:{legend:{labels:{color:TICK,boxWidth:10,font:{size:11}}}},
      scales:{
        x:{ticks:{color:TICK,font:{size:11}},grid:{color:GRID}},
        y:{ticks:{color:TICK,font:{size:11}},grid:{color:GRID},
           title:{display:true,text:'해지율 (%)',color:TICK,font:{size:11}},beginAtZero:true},
      }
    }
  });
}

/* ────────────────────────────────────────
   03. 도넛형 막대 — 총통화시간 구간별 해지율/유지율
   하나의 100% 스택 막대에 해지/유지 비율을 도넛처럼 분할
   구간별로 행이 나뉘어 도넛의 시각적 분할감을 막대로 표현
   ────────────────────────────────────────*/
function drawChart3(g,d){
  const b = GC[g];
  const labels = d.labels;
  const churn  = d.churn;
  const retain = churn.map(v => 100-v);

  // 해지율 색: 등급색, 유지율 색: 연한 회색
  const churnBg  = b + 'cc';
  const retainBg = '#e2e8f0';

  // 값 라벨 플러그인 (막대 끝에 % 표시)
  const labelPlugin = {
    id:'barLabel3',
    afterDatasetsDraw(chart){
      const {ctx} = chart;
      chart.getDatasetMeta(0).data.forEach((bar, i)=>{
        ctx.save();
        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 11px Noto Sans KR,sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        const cx = (bar.x + chart.scales.x.getPixelForValue(0)) / 2;
        if(churn[i] > 8) ctx.fillText(churn[i]+'%', cx, bar.y);
        ctx.restore();
      });
    }
  };

  mc('chart3',{
    type:'bar',
    data:{
      labels,
      datasets:[
        {
          label:'해지율',
          data:churn,
          backgroundColor: churnBg,
          borderColor:'transparent',
          borderWidth:0,
          borderRadius:{topLeft:5,bottomLeft:5,topRight:0,bottomRight:0},
          borderSkipped:false,
          stack:'s',
        },
        {
          label:'유지율',
          data:retain,
          backgroundColor: retainBg,
          borderColor:'transparent',
          borderWidth:0,
          borderRadius:{topLeft:0,bottomLeft:0,topRight:5,bottomRight:5},
          borderSkipped:false,
          stack:'s',
        }
      ]
    },
    options:{
      indexAxis:'y',
      responsive:true, maintainAspectRatio:false,
      animation:{duration:700,easing:'easeInOutQuart'},
      plugins:{
        legend:{
          labels:{
            color:TICK, font:{size:11}, boxWidth:12,
            usePointStyle:true, pointStyle:'rectRounded',
          }
        },
        tooltip:{
          callbacks:{
            label: c => c.datasetIndex===0
              ? ` 해지율: ${c.raw}%`
              : ` 유지율: ${c.raw}%`
          }
        },
      },
      scales:{
        x:{
          stacked:true,
          ticks:{color:TICK,font:{size:11},callback:v=>v+'%'},
          grid:{color:GRID},
          max:100,
        },
        y:{
          stacked:true,
          ticks:{color:TICK,font:{size:11}},
          grid:{color:'transparent'},
        },
      }
    },
    plugins:[labelPlugin]
  });
}

/* ────────────────────────────────────────
   04. 레이더 — 상담강도 구간별 해지율
   해지 vs 유지, 얇은 선 + 반투명 채우기
   ────────────────────────────────────────*/
function drawChart4(g,d){
  mc('chart4',{
    type:'radar',
    data:{
      labels:['주간','저녁','밤'],
      datasets:[
        {
          label:'해지 고객',
          data:d.churn,
          backgroundColor:'rgba(220,38,38,.1)',
          borderColor:'#dc2626',
          borderWidth:2,
          pointRadius:5,
          pointBackgroundColor:'#fff',
          pointBorderColor:'#dc2626',
          pointBorderWidth:2,
        },
        {
          label:'유지 고객',
          data:d.retain,
          backgroundColor:'rgba(71,85,105,.1)',
          borderColor:'#475569',
          borderWidth:2,
          pointRadius:5,
          pointBackgroundColor:'#fff',
          pointBorderColor:'#475569',
          pointBorderWidth:2,
        }
      ]
    },
    options:{
      responsive:true, maintainAspectRatio:false,
      animation:{duration:700},
      plugins:{
        legend:{
          labels:{
            color:TICK,font:{size:11},
            boxWidth:10,
            usePointStyle:true,  /* 원형 범례 — 외곽선 없음 */
            pointStyle:'circle',
          }
        }
      },
      scales:{
        r:{
          ticks:{color:TICK,backdropColor:'transparent',font:{size:9},stepSize:10},
          grid:{color:GRID},
          angleLines:{color:GRID},
          pointLabels:{color:'#111827',font:{size:12,weight:'600'}},
        }
      }
    }
  });
}

/* ══════════════════════════════════════════════════
   등급별 데이터 테이블
   ALL: 전체 평균, A: 최고위험, B: 고위험, C: 중위험, D: 저위험
   ══════════════════════════════════════════════════ */
const DATA = {
  ALL: {
    c1: { labels:['0회','1~2회','3~4회','5~6회','7~8회','9~11회'], vals:[520,640,1620,380,250,180] },
    c2: { labels:['신규(~100일)','단기(101~300일)','중기(301~500일)','장기(500일+)'], vals:[28,31,18,10] },
    c3: { labels:['매우낮음(~530분)','낮음(531~700분)','보통(701~870분)','높음(871분+)'], churn:[38,27,22,13] },
    c4: { churn:[35,20,30], retain:[20,28,15] },
  },
  A: {
    // A등급(최고위험): 상담 많을수록 해지 폭발적, 신규에서 매우 높음
    c1: { labels:['0회','1~2회','3~4회','5~6회','7~8회','9~11회'], vals:[80,210,980,1240,890,540] },
    c2: { labels:['신규(~100일)','단기(101~300일)','중기(301~500일)','장기(500일+)'], vals:[52,44,21,8] },
    c3: { labels:['매우낮음(~530분)','낮음(531~700분)','보통(701~870분)','높음(871분+)'], churn:[61,48,30,14] },
    c4: { churn:[55,38,48], retain:[15,20,10] },
  },
  B: {
    // B등급(고위험): 중간 상담 횟수에서 피크, 단기 이탈 높음
    c1: { labels:['0회','1~2회','3~4회','5~6회','7~8회','9~11회'], vals:[310,580,1340,620,190,90] },
    c2: { labels:['신규(~100일)','단기(101~300일)','중기(301~500일)','장기(500일+)'], vals:[38,42,24,12] },
    c3: { labels:['매우낮음(~530분)','낮음(531~700분)','보통(701~870분)','높음(871분+)'], churn:[45,36,25,10] },
    c4: { churn:[42,30,38], retain:[18,25,14] },
  },
  C: {
    // C등급(중위험): 전반적으로 낮고, 중간 가입일에서 약간 높음
    c1: { labels:['0회','1~2회','3~4회','5~6회','7~8회','9~11회'], vals:[480,520,740,280,140,60] },
    c2: { labels:['신규(~100일)','단기(101~300일)','중기(301~500일)','장기(500일+)'], vals:[18,26,20,9] },
    c3: { labels:['매우낮음(~530분)','낮음(531~700분)','보통(701~870분)','높음(871분+)'], churn:[28,22,18,8] },
    c4: { churn:[22,14,18], retain:[25,32,22] },
  },
  D: {
    // D등급(저위험): 상담 거의 없고, 장기 고객 충성도 높음
    c1: { labels:['0회','1~2회','3~4회','5~6회','7~8회','9~11회'], vals:[820,340,180,60,20,10] },
    c2: { labels:['신규(~100일)','단기(101~300일)','중기(301~500일)','장기(500일+)'], vals:[9,12,8,4] },
    c3: { labels:['매우낮음(~530분)','낮음(531~700분)','보통(701~870분)','높음(871분+)'], churn:[14,10,8,5] },
    c4: { churn:[12,8,10], retain:[32,38,28] },
  },
};

/* ── 초기 렌더링 ── */
function drawAll(g){
  const d = DATA[g];
  drawChart1(g, d.c1);
  drawChart2(g, d.c2);
  drawChart3(g, d.c3);
  drawChart4(g, d.c4);
}

/* ── 등급 버튼 ── */
document.querySelectorAll('.grade-btn').forEach(btn=>{
  btn.addEventListener('click',function(){
    document.querySelectorAll('.grade-btn').forEach(b=>b.classList.remove('active'));
    this.classList.add('active'); ng=this.dataset.grade;
    const bar=document.getElementById('gradeBar');
    document.getElementById('gradeDot').style.background=GC[ng];
    document.getElementById('gradeText').textContent=GM[ng];
    ng==='ALL'?bar.classList.remove('show'):bar.classList.add('show');
    drawAll(ng);
    /* 카드 팝 효과 — 테두리/그림자 색상 */
    document.querySelectorAll('.chart-card').forEach((c,i)=>setTimeout(()=>{
      c.style.borderColor = GC[ng];
      c.style.boxShadow = `0 0 0 2px ${GC[ng]}44, 0 8px 28px ${GC[ng]}28`;
      c.classList.add('pop');
      setTimeout(()=>{
        c.classList.remove('pop');
        c.style.borderColor='';
        c.style.boxShadow='';
      }, 900);
    },i*60));
  });
});

window.addEventListener('load',()=>drawAll('ALL'));