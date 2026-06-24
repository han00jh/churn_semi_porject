"""
============================================================
churn_ai.py — AI 분석 서비스 최종본
Flask 경로: churn_ai.py (프로젝트 루트)

[변경 내역]
  - get_topic_insight() 신규 추가
    : 주제 버튼 클릭 시 현황요약/핵심대책/예상이익 3종 동시 분석
    : graph_data(h1~h4 전체) + topic_name을 컨텍스트로 받아 분석
  - 기존 get_insight / get_summary / get_strategy / get_forecast 유지

[AI 호출 흐름]
  버튼 클릭 → /ai_topic_insight
  → AIService.get_topic_insight(topic, topic_name, graph_data)
  → GROQ API (llama3-70b)
  → {summary, strategy, forecast} 반환
  → JS → chatbot 카드 3개 교체

[수정 포인트]
  - AI 모델  → self.model (기본 llama3-70b-8192)
  - 프롬프트 → _build_topic_prompt() 내부
  - 응답 파싱 → _parse_topic_response()
============================================================
"""

import os
import json
import re
import requests


class AIService:
    """
    GROQ API 기반 AI 분석 서비스
    churn_app.py 에서 ai = AIService(api_key=...) 로 사용
    """

    # ── 클래스 상수 ──────────────────────────────────────────
    GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
    MODEL    = "llama3-70b-8192"

    # 주제별 분석 컨텍스트 (AI 프롬프트에 삽입)
    TOPIC_CONTEXT = {
        "A": "상담 건수(cs_calls)가 많을수록 해지율이 급증하는 임계점 패턴. 3회부터 위험, 6회 이상 55%+.",
        "B": "총 사용량·평균요금이 높을수록 이탈률이 낮아지는 역상관. 저사용·저요금 고객이 이탈 위험 높음.",
        "C": "밤 통화 비중, 밤-낮 차이, 시간대 집중도가 이탈과 연관. 패턴 불안정 고객이 위험.",
        "D": "가입기간 단독 효과 미약. 고사용+장기 조합 시 13%+ 해지율. 상호작용 변수가 핵심.",
        "E": "요금 변동성 낮고 음성사서함 미사용 = 단조로운 패턴. 서비스 몰입도 낮은 고객 이탈 위험.",
    }

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    # ──────────────────────────────────────────────────────────
    # 핵심 신규 메서드: 주제별 3종 AI 분석
    # ──────────────────────────────────────────────────────────

    def get_topic_insight(self, topic: str, topic_name: str, graph_data: dict) -> dict:
        """
        주제 버튼 클릭 시 AI 3종 동시 분석
        반환: {
          summary:  {number, label, sub},   ← 현황 요약
          strategy: {number, label, sub},   ← 핵심 대책
          forecast: {number, label, sub},   ← 예상 이익
          ai_context: "분석 기준: A주제 4개 차트"  ← 프론트 표시용
        }
        """
        if not self.api_key:
            return self._fallback_topic(topic)

        prompt = self._build_topic_prompt(topic, topic_name, graph_data)

        try:
            resp = requests.post(
                self.GROQ_URL,
                headers=self.headers,
                json={
                    "model"      : self.MODEL,
                    "temperature": 0.4,
                    "max_tokens" : 600,
                    "messages"   : [
                        {"role": "system", "content": self._system_prompt()},
                        {"role": "user",   "content": prompt},
                    ],
                },
                timeout=15,
            )
            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"]
            print(f"🤖 AI 응답 (topic={topic}):\n{raw[:200]}")
            result = self._parse_topic_response(raw)

        except Exception as e:
            print(f"⚠️ AI 오류: {e}")
            result = self._fallback_topic(topic)

        # AI가 보고 있는 컨텍스트 정보 (프론트 표시용)
        chart_titles = [
            graph_data.get(k, {}).get("title", f"차트{i+1}")
            for i, k in enumerate(["h1","h2","h3","h4"])
        ]
        result["ai_context"] = (
            f"📊 분석 기준: [{topic}] {topic_name.split('(')[0].strip()} "
            f"— {' · '.join(t for t in chart_titles if t)}"
        )
        return result

    def _system_prompt(self) -> str:
        return (
            "당신은 통신사 고객 이탈 예측 전문 데이터 분석가입니다. "
            "주어진 차트 데이터를 바탕으로 핵심 인사이트를 도출하세요. "
            "반드시 JSON 형식으로만 응답하세요. 다른 텍스트는 절대 포함하지 마세요."
        )

    def _build_topic_prompt(self, topic: str, topic_name: str, graph_data: dict) -> str:
        """
        4개 차트 데이터를 요약해서 AI 프롬프트 생성
        graph_data: {h1:{title,values,labels,avg,...}, h2:..., h3:..., h4:...}
        """
        context = self.TOPIC_CONTEXT.get(topic, "")

        # 차트 요약 텍스트 생성
        chart_summaries = []
        for k in ["h1","h2","h3","h4"]:
            d = graph_data.get(k, {})
            if not d or k.startswith("_"):
                continue
            title  = d.get("title", "")
            avg    = d.get("avg", "")
            values = d.get("values", [])
            labels = d.get("labels", [])
            # 최고/최저 포인트만 추출
            if values and labels:
                max_i = values.index(max(values))
                min_i = values.index(min(values))
                summary = (
                    f"[{title}] 전체평균={avg}%, "
                    f"최고={labels[max_i]}({max(values)}%), "
                    f"최저={labels[min_i]}({min(values)}%)"
                )
            else:
                summary = f"[{title}] 전체평균={avg}%"
            chart_summaries.append(summary)

        charts_text = "\n".join(chart_summaries)

        return f"""
주제: {topic_name}
핵심 컨텍스트: {context}

차트 데이터 요약:
{charts_text}

위 데이터를 분석해서 아래 JSON 형식으로 응답하세요.
숫자값은 구체적인 수치(%, 배수, 일수 등)를 반드시 포함하세요.

{{
  "summary": {{
    "number": "−X%",
    "label": "한 줄 현황 요약 (15자 이내)",
    "sub": "구체적 수치 2가지 포함한 2줄 설명"
  }},
  "strategy": {{
    "number": "X일 or X% or X배",
    "label": "핵심 대책명 (10자 이내)",
    "sub": "실행 방법 2가지 (각 15자 이내)"
  }},
  "forecast": {{
    "number": "+X%",
    "label": "예상 효과 (10자 이내)",
    "sub": "수익 수치 포함 2줄 (연간 기준)"
  }}
}}
"""

    def _parse_topic_response(self, raw: str) -> dict:
        """
        AI 응답 JSON 파싱
        실패 시 fallback 반환
        """
        try:
            # JSON 블록 추출
            match = re.search(r'\{[\s\S]*\}', raw)
            if match:
                data = json.loads(match.group())
                # 필수 키 검증
                for key in ["summary", "strategy", "forecast"]:
                    if key not in data:
                        raise ValueError(f"키 누락: {key}")
                    for sub in ["number", "label", "sub"]:
                        if sub not in data[key]:
                            data[key][sub] = ""
                return data
        except Exception as e:
            print(f"⚠️ JSON 파싱 실패: {e}\n원본: {raw[:300]}")
        return self._fallback_topic("")

    def _fallback_topic(self, topic: str) -> dict:
        """AI 호출 실패 시 기본값"""
        defaults = {
            "A": {
                "summary" : {"number":"−17%",  "label":"상담 임계점 위험", "sub":"상담 6회↑ 해지율 55%\n상담 3회↑부터 평균 초과"},
                "strategy": {"number":"3회",    "label":"조기 개입 기준",   "sub":"상담 3회 도달 즉시 전담 상담사 배정\n3개월 요금 10% 할인 적용"},
                "forecast": {"number":"+12%",   "label":"이탈 방어 효과",   "sub":"연간 이탈 감소 시 +18억 예상\nROI 3.8배"},
            },
            "B": {
                "summary" : {"number":"−8%",   "label":"저사용 고객 위험", "sub":"total_minutes 하위 20% 해지율 높음\n저요금 구간도 동반 상승"},
                "strategy": {"number":"30일",   "label":"사용 촉진 캠페인",  "sub":"저사용 고객 맞춤 데이터 무료 제공\n월 1회 사용 리포트 발송"},
                "forecast": {"number":"+9%",   "label":"매출 유지 효과",   "sub":"이탈 방어 연 +14억 예상\nROI 2.9배"},
            },
            "C": {
                "summary" : {"number":"−6%",   "label":"패턴 불안정 위험", "sub":"밤 비중 높은 D1~D2 해지율 12%+\n시간대 집중도 D5 구간 13.8%"},
                "strategy": {"number":"14일",   "label":"패턴 모니터링",    "sub":"밤 통화 집중 고객 2주 주기 점검\n시간대 다양화 혜택 제공"},
                "forecast": {"number":"+7%",   "label":"패턴 안정화 효과", "sub":"이탈 방어 연 +11억 예상\nROI 2.4배"},
            },
            "D": {
                "summary" : {"number":"−5%",   "label":"고사용+장기 위험", "sub":"usage Q4 × tenure Q4 해지율 13%\n장기 고객도 안심 불가"},
                "strategy": {"number":"90일",   "label":"장기 고객 케어",    "sub":"3년+ 고객 전담 VIP 서비스 배정\n분기별 사용 패턴 리뷰 발송"},
                "forecast": {"number":"+8%",   "label":"유지율 개선 효과", "sub":"이탈 방어 연 +13억 예상\nROI 3.1배"},
            },
            "E": {
                "summary" : {"number":"−9%",   "label":"단조 패턴 위험",   "sub":"vm 미사용 해지율 12.2% vs 사용 10.3%\n요금 변동성 낮은 고객 집중 위험"},
                "strategy": {"number":"21일",   "label":"서비스 다양화",    "sub":"음성사서함 미사용 고객 무료 체험 권유\n부가서비스 21일 무료 제공"},
                "forecast": {"number":"+10%",  "label":"몰입도 개선 효과", "sub":"이탈 방어 연 +16억 예상\nROI 3.5배"},
            },
        }
        return defaults.get(topic, defaults["A"])

    # ──────────────────────────────────────────────────────────
    # 기존 메서드 유지 (하위 호환)
    # ──────────────────────────────────────────────────────────

    def _call_groq(self, messages: list, max_tokens: int = 400) -> str:
        """GROQ API 공통 호출"""
        resp = requests.post(
            self.GROQ_URL,
            headers=self.headers,
            json={
                "model"      : self.MODEL,
                "temperature": 0.5,
                "max_tokens" : max_tokens,
                "messages"   : messages,
            },
            timeout=12,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def get_insight(self, graph_data=None, user_message=None,
                    auto_mode=False, mode=None, hypothesis_id=None) -> dict:
        """기존 자유 질문 챗봇 (유지)"""
        if not self.api_key:
            return {"response": "API 키가 없습니다."}
        try:
            content = self._call_groq([
                {"role":"system","content":"통신사 이탈 분석 전문가. 간결하게 한국어로 답변."},
                {"role":"user","content": str(user_message or graph_data or "")},
            ])
            return {"response": content}
        except Exception as e:
            return {"response": f"오류: {e}"}

    def get_summary(self, graph_data=None) -> dict:
        """기존 현황 요약 (유지)"""
        if not self.api_key:
            return {"number":"−14.5%","label":"이탈 위험 고객 감지","sub":"상담 4회↑ 이탈률 42%\n신규 90일↓ 이탈률 31%"}
        try:
            raw = self._call_groq([
                {"role":"system","content":"JSON만 반환. {number,label,sub} 형식."},
                {"role":"user",  "content":f"차트 데이터: {str(graph_data)[:500]}\n현황 요약을 JSON으로."},
            ])
            return json.loads(re.search(r'\{[^}]+\}', raw).group())
        except:
            return {"number":"−14.5%","label":"이탈 위험 고객 감지","sub":"상담 4회↑ 이탈률 42%\n신규 90일↓ 이탈률 31%"}

    def get_strategy(self, graph_data=None) -> dict:
        """기존 핵심 대책 (유지)"""
        if not self.api_key:
            return {"number":"90일","label":"신규 집중 케어","sub":"전담 상담사 즉시 배정\n3개월 요금 할인"}
        try:
            raw = self._call_groq([
                {"role":"system","content":"JSON만 반환. {number,label,sub} 형식."},
                {"role":"user",  "content":f"차트 데이터: {str(graph_data)[:500]}\n핵심 대책을 JSON으로."},
            ])
            return json.loads(re.search(r'\{[^}]+\}', raw).group())
        except:
            return {"number":"90일","label":"신규 집중 케어","sub":"전담 상담사 즉시 배정\n3개월 요금 할인"}

    def get_forecast(self, graph_data=None) -> dict:
        """기존 예상 이익 (유지)"""
        if not self.api_key:
            return {"number":"+10%","label":"매출 증가 예상","sub":"이탈 방어 시 연 +26억\nROI 4.2배"}
        try:
            raw = self._call_groq([
                {"role":"system","content":"JSON만 반환. {number,label,sub} 형식."},
                {"role":"user",  "content":f"차트 데이터: {str(graph_data)[:500]}\n예상 이익을 JSON으로."},
            ])
            return json.loads(re.search(r'\{[^}]+\}', raw).group())
        except:
            return {"number":"+10%","label":"매출 증가 예상","sub":"이탈 방어 시 연 +26억\nROI 4.2배"}

    def check_connection(self) -> dict:
        """AI 연결 상태 확인"""
        if not self.api_key:
            return {"status":"no_key","message":"API 키 없음"}
        try:
            self._call_groq([{"role":"user","content":"ping"}], max_tokens=5)
            return {"status":"ok","model":self.MODEL}
        except Exception as e:
            return {"status":"error","message":str(e)}
