# 통신 고객 이탈 예측 및 고객 유지 전략 대시보드

> **Telecom Customer Churn Prediction — Portfolio Project**

---

## 프로젝트 개요

통신사 고객 데이터(3만 건)를 분석해 이탈 위험 고객을 **A~D 4등급**으로 분류하고, AI 기반 맞춤형 대응 전략을 제공하는 대시보드를 구축한 팀 프로젝트입니다.

| 항목 | 내용 |
|------|------|
| 기간 | 2026년 2월 |
| 인원 | 4인 팀 |
| 데이터 | 통신사 고객 데이터 30,200건 (train 24,000 / test 6,200) |
| 주요 성과 | Macro F1 **0.80** \| Recall **81%** \| ROI **1.67배** \| 손실 절감 **약 2억 원** |

---

## 팀 구성 및 역할

| 이름 | 역할 |
|------|------|
| 어창선 (팀장) | 머신러닝 모델링 (분류 모델 학습 및 등급 산출) |
| **한정현 (본인)** | **EDA · 파생 피처 엔지니어링 · 전처리 파이프라인 · Oracle DB 구축** |
| 김나연 | 데이터 시각화 (Chart.js 대시보드) |
| 김효중 | 기획 · 발표 |

---

## 담당 파트 상세 — 한정현

### 1. 1차 EDA 및 6대 비즈니스 가설 수립

클래스 불균형 확인(이탈률 14.5%), 결측치 탐색, 분포 분석을 수행한 후 비즈니스 맥락을 반영한 6개 가설을 직접 수립하고 통계적으로 검증했습니다.

| 가설 | 내용 | 검증 결과 |
|------|------|-----------|
| 가설 1 | 상담 전화 건수가 많을수록 이탈 확률이 높다 (불만 고객) | **지지** — 상담 多 그룹 이탈률 14.56% vs 少 그룹 9.99% |
| 가설 2 | 가입 기간이 짧은 고객이 더 이탈할 것이다 (초기 이탈) | **기각** — 오히려 장기 고객의 이탈 증가 (피로도·경쟁사 이동) |
| 가설 3 | 사용량이 낮은 고객이 이탈할 것이다 | **반전** — 고사용 + 장기 고객 그룹이 가장 위험 |
| 가설 4 | 시간대별 통화 패턴이 이탈과 연관된다 | **지지** — 야간 통화 집중 고객 특이 패턴 확인 |
| 가설 5 | 상담 비율(통화 대비 상담 빈도)이 높을수록 이탈 가능성이 높다 | **지지** — cs_per_100min, cs_per_call 유의 |
| 가설 6 | 시간당 요금(단가)이 높은 고객은 이탈 가능성이 높다 | **지지** — avg_rate, rate_std 이탈 그룹 유의미하게 높음 |

### 2. 행동 기반 파생 피처 17개 생성

단순 원본 피처의 한계를 넘어, **고객 행동 패턴을 수치화**하는 파생 피처를 직접 설계했습니다.

```
파생 피처 목록 (17개)

[통화량 종합]  total_calls
[시간대 비율]  day_ratio, eve_ratio, night_ratio
[시간대 편중]  night_day_diff, time_ratio_std
[상담 집중도]  cs_ratio, cs_per_100min, cs_per_call
[시간당 요금]  day_rate, eve_rate, night_rate, avg_rate, rate_std
[서비스 이용]  vm_binary, vm_count_log
[가입 안정성]  tenure_log
```

### 3. 전처리 파이프라인 자동화

| 단계 | 처리 내용 |
|------|-----------|
| 결측치 처리 | 수치형 중앙값, 범주형 최빈값으로 대체 |
| 인코딩 | Label Encoding (이진 범주형) |
| 이상치 대응 | IQR 분석으로 이상치 비율 파악 → 삭제 대신 **파생 피처로 흡수** |
| 스케일링 | **RobustScaler** — 이상치 영향 최소화 |

> 이상치를 단순 삭제하지 않고 파생 피처 설계로 흡수한 것이 Recall 81% 달성에 기여

### 4. Oracle DB 구축 및 학습 데이터셋 최적화

- 원본 CSV → Oracle DB 적재 (`churn_insert.py`)
- 파생 피처 포함 전처리 완료 데이터를 `NEW` 테이블로 별도 관리
- Flask 서버가 DB에서 실시간으로 데이터를 조회하는 구조 설계

---

## 주요 성과

```
Macro F1 Score :  0.80
Recall (이탈 탐지율) :  81%
ROI :  1.67배
예상 손실 절감 :  약 2억 원
```

---

## 기술 스택

| 구분 | 도구 |
|------|------|
| 데이터 분석 | Python, Pandas, NumPy, SciPy |
| 머신러닝 | Scikit-learn (RobustScaler, Label Encoding) |
| 시각화 (EDA) | Matplotlib, Seaborn |
| 웹 서버 | Python Flask |
| 프론트엔드 | HTML5, CSS3, JavaScript, Chart.js v4.4.0 |
| 데이터베이스 | Oracle DB (Express Edition), SQLAlchemy, cx_Oracle |
| AI 인사이트 | Groq API (Llama-3.3-70b-versatile) |
| 환경 관리 | python-dotenv |

---

## 폴더 구조

```
ST/
├── README.md                       # 현재 보고 계신 문서
├── .gitignore
│
├── data/                           # 데이터
│   └── churn/
│       ├── raw/                    # 원본 CSV (train.csv, test.csv, sample_submission.csv)
│       └── featured/               # 전처리 완료 데이터 (churn.csv)
│
├── notebooks/                      # EDA & 전처리 (담당: 한정현)
│   └── jh_EDA_FINAL.ipynb          # ★ 6대 가설 검증 + 파생 피처 17개 + 전처리 파이프라인
│
├── web/                            # Flask 대시보드 애플리케이션
│   ├── churn_main.py               # Flask 메인 서버 (라우팅, 데이터 조회)
│   ├── churn_ai.py                 # Groq AI 서비스 (자동 분석·자유 질의)
│   ├── churn_insert.py             # Oracle DB 초기 데이터 적재 (1회 실행)
│   ├── kpi.py                      # KPI 계산 로직
│   ├── requirements.txt            # 의존성 목록
│   ├── templates/
│   │   └── dashboard_09.html       # 대시보드 UI
│   └── static/
│       ├── css/                    # 스타일시트
│       └── js/                     # Chart.js 차트·버튼·AI 동작 스크립트
│
└── doc/                            # 기획서·스토리보드 등 문서
```

---

## 실행 방법

### 1. 의존성 설치

```bash
pip install flask pandas sqlalchemy cx_Oracle python-dotenv groq scikit-learn matplotlib seaborn
```

### 2. 환경 변수 설정

`web/.env` 파일을 생성하고 아래 내용을 입력하세요.

```env
GROQ_API_KEY=your_groq_api_key_here
DB_URL=oracle+cx_oracle://it:0000@localhost:1521/xe
```

### 3. Oracle DB에 데이터 적재 (최초 1회)

```bash
cd web
python churn_insert.py
```

### 4. 대시보드 서버 실행

```bash
cd web
python churn_main.py
```

접속 주소: `http://127.0.0.1:6001`

---

## 대시보드 주요 기능

- **등급별 필터링** — A(최고위험) ~ D(저위험) 버튼 클릭 시 전체 차트 즉시 반영
- **6대 가설 시각화** — 상담 건수, 가입 기간, 요금 등 핵심 지표 그래프
- **AI 자동 분석** — 등급 변경 시 Groq Llama-3.3이 한국어 리포트 자동 생성
- **자유 질의** — 분석 데이터 기반 고객 관리 전략 AI 상담
- **Target List** — 즉각 관리가 필요한 고위험 고객 상위 100명 목록
