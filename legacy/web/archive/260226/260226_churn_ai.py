# ai_service.py
# pip install groq

import os
import json
import re
from groq import Groq


class AIService:

    def __init__(self, api_key):
        # ────────────────────────────────────────────────
        # ✏️ API 키 목록 — 팀원 키를 .env 에 추가하면 자동 등록
        #    .env 예시:
        #      GROQ_API_KEY=그록키1값      ← 본인
        #      GROQ_API_KEY_2=그록키2값    ← 팀원1
        #      GROQ_API_KEY_3=그록키3값    ← 팀원2
        # ────────────────────────────────────────────────
        raw_keys = [
            api_key,                           # 키1: 기본 (본인)
            os.getenv("GROQ_API_KEY_2", ""),   # 키2: 팀원1 (없으면 빈 문자열)
            os.getenv("GROQ_API_KEY_3", ""),   # 키3: 팀원2 (없으면 빈 문자열)
        ]
        # 빈 키 제거 → 실제 등록된 키만 남김
        self.api_keys = [k for k in raw_keys if k]
        self.key_index = 0   # 현재 사용 중인 키 인덱스 (0부터 시작)
        self.client = Groq(api_key=self.api_keys[0])
        self.model_name = "llama-3.3-70b-versatile"
        print(f"✅ AIService 초기화 — 등록된 키 {len(self.api_keys)}개")

    # ────────────────────────────────────────────────
    # 키 전환 — 429(토큰 초과) 발생 시 다음 키로 교체
    # [원리] if/elif 처럼 순서대로: 키1 소진 → 키2 → 키3
    # True: 전환 성공 / False: 더 이상 쓸 키 없음
    # ────────────────────────────────────────────────
    def _rotate_key(self):
        next_index = self.key_index + 1
        if next_index >= len(self.api_keys):
            print("⛔ 모든 API 키 소진 — 전환 불가")
            return False
        self.key_index = next_index
        self.client = Groq(api_key=self.api_keys[self.key_index])
        print(f"🔄 API 키 전환 → 키{self.key_index + 1} 사용 중")
        return True

    def get_current_key_index(self):
        """현재 키 번호 반환 (1-based). 프론트 표시용."""
        return self.key_index + 1

    def check_connection(self):
        try:
            self.client.chat.completions.create(
                messages=[{"role": "user", "content": "ping"}],
                model=self.model_name,
                max_tokens=5,
            )
            return {
                "status": "ok",
                "model": self.model_name,
                "key_index": self.get_current_key_index(),
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _build_context(self, graph_data):
        """그래프 원본 데이터를 AI가 읽을 수 있는 텍스트로 변환 (공통 유틸)"""
        grade = graph_data.get('grade', 'ALL')
        context = f"현재 분석 중인 위험 등급: {grade}\n"
        for i in range(1, 7):
            h_key = f"h{i}"
            h_data = graph_data.get(h_key, {})
            title  = h_data.get('title', f'가설{i}')
            labels = h_data.get('labels', [])
            values = h_data.get('values', [])
            if isinstance(values, list) and len(values) > 10:
                nums = [v for v in values if isinstance(v, (int, float))]
                val_str = f"평균:{sum(nums)/len(nums):.2f}, 최대:{max(nums)}, 개수:{len(nums)}" if nums else f"데이터 {len(values)}개"
            else:
                val_str = str(list(zip(labels, values)) if labels else values)
            context += f"[{h_key}: {title}] {val_str}\n"
        return context

    # ────────────────────────────────────────────────
    # 핵심: _call — API 호출 + 429 시 자동 키 전환 재시도
    #
    # [동작 원리 — if/elif 흐름]
    #   키1 호출 → 성공이면 반환
    #             → 429이면 키2로 전환 후 재시도
    #                       → 성공이면 반환 (key_index=2 포함)
    #                       → 429이면 키3으로 전환 후 재시도
    #                                 → 성공/실패 반환
    #
    # [key_index 반환]
    #   프론트에서 key_index >= 2 이면 "다른 키 사용 중" 배지 표시
    # ────────────────────────────────────────────────
    def _call(self, system_msg, prompt):
        for attempt in range(len(self.api_keys)):
            try:
                res = self.client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": system_msg},
                        {"role": "user",   "content": prompt}
                    ],
                    model=self.model_name,
                    temperature=0.3,
                )
                # 성공 — 현재 키 번호도 함께 반환
                return {
                    "success":   True,
                    "answer":    res.choices[0].message.content,
                    "key_index": self.get_current_key_index(),
                }

            except Exception as e:
                err_str = str(e)
                if '429' in err_str:
                    # 토큰 초과 → 다음 키로 전환 후 재시도
                    print(f"⚠️ 키{self.key_index + 1} 토큰 소진 (429)")
                    rotated = self._rotate_key()
                    if not rotated:
                        return {
                            "success":   False,
                            "answer":    "모든 API 키 토큰이 소진되었습니다.",
                            "key_index": self.get_current_key_index(),
                        }
                    continue  # 다음 키로 재시도
                else:
                    # 다른 에러 → 즉시 실패
                    print(f"❌ AI 에러: {e}")
                    return {
                        "success":   False,
                        "answer":    f"Groq 서비스 오류: {e}",
                        "key_index": self.get_current_key_index(),
                    }

        return {
            "success":   False,
            "answer":    "모든 API 키 토큰이 소진되었습니다.",
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

    def get_summary(self, graph_data):
        ctx = self._build_context(graph_data)
        prompt = (
            f"{ctx}\n"
            "위 6개 그래프 데이터 전체를 분석해서, 현재 고객 이탈 상황을 "
            "핵심만 뽑아 딱 1문장(30자 이내)으로 요약해줘. "
            "숫자나 등급을 포함해서 임팩트 있게. 문장 외 다른 말은 절대 쓰지 마."
        )
        return self._call(self._SYS, prompt)

    def get_strategy(self, graph_data):
        ctx = self._build_context(graph_data)
        prompt = (
            f"{ctx}\n"
            "위 6개 그래프 데이터를 직접 분석해서, 고객 이탈을 줄이기 위한 "
            "가장 효과적인 대책을 딱 1문장(30자 이내)으로 써줘. "
            "구체적인 대상(등급/구간)과 행동을 포함해. 문장 외 다른 말은 절대 쓰지 마."
        )
        return self._call(self._SYS, prompt)

    def get_forecast(self, graph_data):
        ctx = self._build_context(graph_data)
        prompt = (
            f"{ctx}\n"
            "위 6개 그래프 데이터를 분석해서, 이탈 방지 대책을 실행했을 때 "
            "예상되는 효과를 매출 증가율 또는 해지율 감소율 같은 구체적 수치로 "
            "딱 1문장(30자 이내)으로 써줘. "
            "반드시 %나 숫자를 포함해. 문장 외 다른 말은 절대 쓰지 마."
        )
        return self._call(self._SYS, prompt)

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
    # 반환값에 key_index 포함 → 프론트에서 키 전환 배지 표시
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
                "key_index": res.get("key_index", 1),  # ← 프론트 배지 표시용
            }
        except Exception as e:
            print(f"⚠️ JSON 파싱 실패: {e}\n원본: {res['answer']}")
            fallback = self._fallback_topic_insight()
            fallback["key_index"] = self.get_current_key_index()
            return fallback

    def _fallback_topic_insight(self):
        """AI 실패 시 기본값 반환"""
        return {
            "summary":  {"number": "−", "label": "분석 중", "kpi1": {"val": "−", "lab": "데이터 확인"}, "kpi2": {"val": "−", "lab": "재시도 필요"}, "sub": "📌 AI 분석을 다시 시도해 주세요"},
            "strategy": {"number": "−", "label": "대책 준비 중", "kpi1": {"val": "−", "lab": "준비 중"}, "kpi2": {"val": "−", "lab": "준비 중"}, "sub": "📌 잠시 후 다시 시도해 주세요"},
            "forecast": {"number": "−", "label": "예측 준비 중", "kpi1": {"val": "−", "lab": "준비 중"}, "kpi2": {"val": "−", "lab": "준비 중"}, "sub": "📌 잠시 후 다시 시도해 주세요"},
        }
