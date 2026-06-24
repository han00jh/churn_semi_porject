# churn_ai.py
# pip install groq google-generativeai anthropic

import os
import json
import re
from groq import Groq


# ════════════════════════════════════════════════════════════
# AIService — 멀티 API 키 관리 + Groq/Gemini 자동 구분
#
# [.env 설정 예시]
#   GROQ_API_KEY_1=gsk_xxxx   ← Groq 키1 (필수)
#   GROQ_API_KEY_2=gsk_xxxx   ← Groq 키2
#   GROQ_API_KEY_3=gsk_xxxx   ← Groq 키3
#   GROQ_API_KEY_4=gsk_xxxx   ← Groq 키4
#   CLAUDE_API_KEY_5=sk-ant-xx ← Claude 키5 (선택)
#   GEMINI_API_KEY_6=AIza_xx  ← Gemini 키6 (선택)
#
# [키 슬롯 구조]
#   슬롯1~4 : Groq   (provider='groq')
#   슬롯5   : Claude (provider='claude') ← 비어있으면 자동 스킵
#   슬롯6   : Gemini (provider='gemini') ← 비어있으면 자동 스킵
#
# [동작 원리]
#   429(토큰 소진) 발생 시 다음 슬롯으로 자동 전환
#   터미널 출력 예시:
#     ✅ Groq_1 사용 중 (1번째 호출)
#     ⚠️ Groq_1 토큰 소진 (429) — 3번 사용됨
#     🔄 Groq_1 소진 → Groq_2 전환
#     ✅ Groq_2 사용 중 (1번째 호출)
# ════════════════════════════════════════════════════════════

class AIService:

    def __init__(self, api_key=None):
        # ────────────────────────────────────────────────
        # 키 슬롯 5개 정의
        # 비어있는 슬롯은 자동으로 제외됨
        # ────────────────────────────────────────────────
        raw_slots = [
            # 슬롯 1~4: Groq
            {'key': os.getenv('GROQ_API_KEY_1', api_key or ''), 'provider': 'groq',   'label': 'Groq_1'},
            {'key': os.getenv('GROQ_API_KEY_2', ''),             'provider': 'groq',   'label': 'Groq_2'},
            {'key': os.getenv('GROQ_API_KEY_3', ''),             'provider': 'groq',   'label': 'Groq_3'},
            {'key': os.getenv('GROQ_API_KEY_4', ''),             'provider': 'groq',   'label': 'Groq_4'},
            # 슬롯 5: Claude (비어있으면 자동 스킵)
            {'key': os.getenv('CLAUDE_API_KEY_5', ''),           'provider': 'claude', 'label': 'Claude_5'},
            # 슬롯 6: Gemini (비어있으면 자동 스킵)
            {'key': os.getenv('GEMINI_API_KEY_6', ''),           'provider': 'gemini', 'label': 'Gemini_6'},
        ]

        # 키가 있는 슬롯만 등록
        self.slots = [s for s in raw_slots if s['key']]

        # USE_ONLY 설정 시 해당 키만 사용 (평소엔 .env에서 주석처리)
        only = os.getenv('USE_ONLY', '')
        if only:
            filtered = [s for s in self.slots if s['label'].lower() == only.lower()]
            if filtered:
                self.slots = filtered
                print(f"🎯 단독 모드: {only} 만 사용")
            else:
                print(f"⚠️ '{only}' 못 찾음 — 전체 키 사용")

        if not self.slots:
            raise ValueError("❌ 사용 가능한 API 키가 없습니다. .env를 확인하세요.")

        if not self.slots:
            raise ValueError("❌ 사용 가능한 API 키가 없습니다. .env를 확인하세요.")

        self.key_index  = 0   # 현재 슬롯 인덱스
        self.call_count = 0   # 현재 키로 성공한 호출 횟수 (토큰 간접 추적용)
        self.model_name        = "llama-3.3-70b-versatile"
        self.gemini_model_name = "gemini-pro"
        self.claude_model_name = "claude-3-5-haiku-20241022"  # Claude 무료 티어 모델

        self._init_client()

        print(f"✅ AIService 초기화 완료")
        print(f"   등록된 키: {[s['label'] for s in self.slots]}")
        print(f"   현재 사용: {self.current_label()}")

    # ────────────────────────────────────────────────
    # 현재 슬롯 정보 반환
    # ────────────────────────────────────────────────
    def current_label(self):
        """현재 키 라벨 (예: 'Groq_1', 'Gemini_5')"""
        return self.slots[self.key_index]['label']

    def current_provider(self):
        """현재 키 종류 ('groq' or 'gemini')"""
        return self.slots[self.key_index]['provider']

    def get_current_key_index(self):
        """1-based 인덱스 (프론트 표시용)"""
        return self.key_index + 1

    # ────────────────────────────────────────────────
    # 클라이언트 초기화 — 슬롯 전환 시마다 호출
    # ────────────────────────────────────────────────
    def _init_client(self):
        slot = self.slots[self.key_index]
        if slot['provider'] == 'groq':
            self.client = Groq(api_key=slot['key'])
        elif slot['provider'] == 'claude':
            try:
                import anthropic
                self.client = anthropic.Anthropic(api_key=slot['key'])
            except ImportError:
                print("⚠️ anthropic 미설치 — pip install anthropic")
                self.client = None
        elif slot['provider'] == 'gemini':
            try:
                import google.generativeai as genai
                genai.configure(api_key=slot['key'])
                self.client = genai.GenerativeModel(self.gemini_model_name)
            except ImportError:
                print("⚠️ google-generativeai 미설치 — pip install google-generativeai")
                self.client = None
        self.call_count = 0  # 새 키 전환 시 카운트 리셋

    # ────────────────────────────────────────────────
    # 키 전환 — 429 발생 시 다음 슬롯으로
    # ────────────────────────────────────────────────
    def _rotate_key(self):
        current    = self.current_label()
        next_index = self.key_index + 1
        if next_index >= len(self.slots):
            print(f"⛔ 모든 키 소진 — 더 이상 전환 불가 ({current} 이후 없음)")
            return False
        self.key_index = next_index
        self._init_client()
        print(f"🔄 {current} 소진 → {self.current_label()} 전환")
        return True

    # ────────────────────────────────────────────────
    # 연결 확인
    # ────────────────────────────────────────────────
    def check_connection(self):
        try:
            if self.current_provider() == 'groq':
                self.client.chat.completions.create(
                    messages=[{"role": "user", "content": "ping"}],
                    model=self.model_name,
                    max_tokens=5,
                )
            elif self.current_provider() == 'claude' and self.client:
                self.client.messages.create(
                    model=self.claude_model_name,
                    max_tokens=5,
                    messages=[{"role": "user", "content": "ping"}],
                )
            elif self.current_provider() == 'gemini' and self.client:
                self.client.generate_content("ping")
            return {
                "status":    "ok",
                "model":     self.model_name,
                "key_label": self.current_label(),
                "key_index": self.get_current_key_index(),
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ────────────────────────────────────────────────
    # 컨텍스트 빌더 (공통)
    # ────────────────────────────────────────────────
    def _build_context(self, graph_data):
        grade   = graph_data.get('grade', 'ALL')
        context = f"현재 분석 중인 위험 등급: {grade}\n"
        for i in range(1, 7):
            h_key  = f"h{i}"
            h_data = graph_data.get(h_key, {})
            title  = h_data.get('title', f'가설{i}')
            labels = h_data.get('labels', [])
            values = h_data.get('values', [])
            if isinstance(values, list) and len(values) > 10:
                nums    = [v for v in values if isinstance(v, (int, float))]
                val_str = f"평균:{sum(nums)/len(nums):.2f}, 최대:{max(nums)}, 개수:{len(nums)}" if nums else f"데이터 {len(values)}개"
            else:
                val_str = str(list(zip(labels, values)) if labels else values)
            context += f"[{h_key}: {title}] {val_str}\n"
        return context

    # ────────────────────────────────────────────────
    # _call — API 호출 + 429 시 자동 키 전환 재시도
    #
    # [동작 흐름]
    #   현재 키 호출
    #   → 성공: 반환 (key_label 포함)
    #   → 429:  다음 키로 전환 후 재시도
    #   → 기타 오류: 즉시 실패 반환
    # ────────────────────────────────────────────────
    def _call(self, system_msg, prompt):
        for attempt in range(len(self.slots)):
            try:
                if self.current_provider() == 'groq':
                    res = self.client.chat.completions.create(
                        messages=[
                            {"role": "system", "content": system_msg},
                            {"role": "user",   "content": prompt}
                        ],
                        model=self.model_name,
                        temperature=0.3,
                    )
                    answer = res.choices[0].message.content

                elif self.current_provider() == 'claude':
                    if self.client is None:
                        raise Exception("Claude 클라이언트 초기화 실패")
                    res = self.client.messages.create(
                        model=self.claude_model_name,
                        max_tokens=1024,
                        system=system_msg,
                        messages=[{"role": "user", "content": prompt}],
                    )
                    answer = res.content[0].text

                elif self.current_provider() == 'gemini':
                    if self.client is None:
                        raise Exception("Gemini 클라이언트 초기화 실패")
                    res    = self.client.generate_content(f"{system_msg}\n\n{prompt}")
                    answer = res.text

                self.call_count += 1
                label = self.current_label()
                print(f"✅ {label} 호출 성공 (이 키로 {self.call_count}번째)")
                return {
                    "success":   True,
                    "answer":    answer,
                    "key_label": label,
                    "key_index": self.get_current_key_index(),
                }

            except Exception as e:
                err_str = str(e)
                if '429' in err_str:
                    print(f"⚠️ {self.current_label()} 토큰 소진 (429) — {self.call_count}번 사용됨")
                    rotated = self._rotate_key()
                    if not rotated:
                        return {
                            "success":   False,
                            "answer":    "모든 API 키 토큰이 소진되었습니다.",
                            "key_label": self.current_label(),
                            "key_index": self.get_current_key_index(),
                        }
                    continue
                else:
                    print(f"❌ {self.current_label()} 오류: {e}")
                    return {
                        "success":   False,
                        "answer":    f"API 오류 ({self.current_label()}): {e}",
                        "key_label": self.current_label(),
                        "key_index": self.get_current_key_index(),
                    }

        return {
            "success":   False,
            "answer":    "모든 API 키 토큰이 소진되었습니다.",
            "key_label": self.current_label(),
            "key_index": self.get_current_key_index(),
        }

    # ────────────────────────────────────────────────
    # 공통 시스템 메시지
    # ────────────────────────────────────────────────
    _SYS = (
        "당신은 대한민국 최고의 통신사 데이터 분석 전문가입니다. "
        "반드시 다음 규칙을 지키세요:\n"
        "1. 모든 답변은 100% 한국어로만 작성하세요.\n"
        "2. 절대로 영어, 한자, 외국 문자를 섞지 마세요.\n"
        "3. 데이터에 없는 내용은 추측하지 마세요."
    )

    # ────────────────────────────────────────────────
    # 챗봇 1: 현황 한 줄 요약
    # ────────────────────────────────────────────────
    def get_summary(self, graph_data):
        ctx    = self._build_context(graph_data)
        prompt = (
            f"{ctx}\n"
            "위 6개 그래프 데이터 전체를 분석해서, 현재 고객 이탈 상황을 "
            "핵심만 뽑아 딱 1문장(30자 이내)으로 요약해줘. "
            "숫자나 등급을 포함해서 임팩트 있게. 문장 외 다른 말은 절대 쓰지 마."
        )
        return self._call(self._SYS, prompt)

    # ────────────────────────────────────────────────
    # 챗봇 2: 대책방안 한 줄
    # ────────────────────────────────────────────────
    def get_strategy(self, graph_data):
        ctx    = self._build_context(graph_data)
        prompt = (
            f"{ctx}\n"
            "위 6개 그래프 데이터를 직접 분석해서, 고객 이탈을 줄이기 위한 "
            "가장 효과적인 대책을 딱 1문장(30자 이내)으로 써줘. "
            "구체적인 대상(등급/구간)과 행동을 포함해. 문장 외 다른 말은 절대 쓰지 마."
        )
        return self._call(self._SYS, prompt)

    # ────────────────────────────────────────────────
    # 챗봇 3: 예상 이익 수치
    # ────────────────────────────────────────────────
    def get_forecast(self, graph_data):
        ctx    = self._build_context(graph_data)
        prompt = (
            f"{ctx}\n"
            "위 6개 그래프 데이터를 분석해서, 이탈 방지 대책을 실행했을 때 "
            "예상되는 효과를 매출 증가율 또는 해지율 감소율 같은 구체적 수치로 "
            "딱 1문장(30자 이내)으로 써줘. "
            "반드시 %나 숫자를 포함해. 문장 외 다른 말은 절대 쓰지 마."
        )
        return self._call(self._SYS, prompt)

    # ────────────────────────────────────────────────
    # 기존 get_insight (자유 질문 / 가설 설명 — 유지)
    # ────────────────────────────────────────────────
    def get_insight(self, graph_data, user_message=None, auto_mode=False, mode=None, hypothesis_id=None):
        ctx = self._build_context(graph_data)
        if auto_mode:
            prompt = f"{ctx}\n위 데이터를 바탕으로 고객 이탈 방지 전략을 한국어로 요약해줘."
        elif mode == "hypothesis":
            prompt = f"{ctx}\n가설 {hypothesis_id}번에 대해 한국어로 자세히 설명해줘."
        else:
            prompt = f"{ctx}\n질문: {user_message}\n답변은 한국어로만 해줘."
        return self._call(self._SYS, prompt)

    # ────────────────────────────────────────────────
    # get_topic_insight — 주제 버튼 클릭 시 AI 3종 분석
    # ────────────────────────────────────────────────
    def get_topic_insight(self, topic, topic_name, graph_data):
        ctx = self._build_context(graph_data)

        SYS_JSON = (
            "당신은 대한민국 최고의 통신사 데이터 분석 전문가입니다. "
            "반드시 다음 규칙을 지키세요:\n"
            "1. 모든 답변은 100% 한국어로만 작성하세요.\n"
            "2. 절대로 영어, 한자, 외국 문자를 섞지 마세요.\n"
            "3. 데이터에 없는 내용은 추측하지 마세요.\n"
            "4. 반드시 순수 JSON만 출력하세요. 마크다운, 설명, 코드블록 절대 금지."
        )

        prompt = f"""
{ctx}

위 데이터를 분석해서 아래 JSON 형식으로만 답해줘. 다른 말은 절대 쓰지 마.

{{
  "summary": {{
    "number": "핵심 수치 (예: -17%, 55%, 3회 등)",
    "label": "한 줄 현황 설명 (10자 이내)",
    "kpi1": {{"val": "수치1", "lab": "수치1 설명 (8자 이내)"}},
    "kpi2": {{"val": "수치2", "lab": "수치2 설명 (8자 이내)"}},
    "sub": "📌 핵심 인사이트 한 문장 (25자 이내)"
  }},
  "strategy": {{
    "number": "대책 핵심 수치 또는 키워드",
    "label": "대책 제목 (10자 이내)",
    "kpi1": {{"val": "행동1 키워드", "lab": "행동1 설명 (8자 이내)"}},
    "kpi2": {{"val": "수치 또는 기간", "lab": "행동2 설명 (8자 이내)"}},
    "sub": "📌 실행 방안 한 문장 (25자 이내)"
  }},
  "forecast": {{
    "number": "예상 효과 수치 (예: +12%, +18억)",
    "label": "효과 제목 (10자 이내)",
    "kpi1": {{"val": "수치1", "lab": "효과1 설명 (8자 이내)"}},
    "kpi2": {{"val": "수치2", "lab": "효과2 설명 (8자 이내)"}},
    "sub": "📌 기대 효과 한 문장 (25자 이내)"
  }}
}}
"""
        res = self._call(SYS_JSON, prompt)

        if not res.get("success"):
            fallback = self._fallback_topic_insight()
            fallback["key_label"] = self.current_label()
            fallback["key_index"] = self.get_current_key_index()
            return fallback

        try:
            text = res["answer"].strip()
            text = re.sub(r"```json|```", "", text).strip()
            data = json.loads(text)
            return {
                "summary":   data.get("summary",  {}),
                "strategy":  data.get("strategy", {}),
                "forecast":  data.get("forecast", {}),
                "key_label": res.get("key_label", self.current_label()),
                "key_index": res.get("key_index", 1),
            }
        except Exception as e:
            print(f"⚠️ JSON 파싱 실패: {e}\n원본: {res['answer']}")
            fallback = self._fallback_topic_insight()
            fallback["key_label"] = self.current_label()
            fallback["key_index"] = self.get_current_key_index()
            return fallback

    def _fallback_topic_insight(self):
        """AI 실패 시 기본값 반환"""
        return {
            "summary":  {"number": "−", "label": "분석 중", "kpi1": {"val": "−", "lab": "데이터 확인"}, "kpi2": {"val": "−", "lab": "재시도 필요"}, "sub": "📌 AI 분석을 다시 시도해 주세요"},
            "strategy": {"number": "−", "label": "대책 준비 중", "kpi1": {"val": "−", "lab": "준비 중"}, "kpi2": {"val": "−", "lab": "준비 중"}, "sub": "📌 잠시 후 다시 시도해 주세요"},
            "forecast": {"number": "−", "label": "예측 준비 중", "kpi1": {"val": "−", "lab": "준비 중"}, "kpi2": {"val": "−", "lab": "준비 중"}, "sub": "📌 잠시 후 다시 시도해 주세요"},
        }
