# ============================================================
# 📁 ai_service.py
# 역할: Gemini AI 와의 통신만 전담하는 파일
#
# 구조:
#   class AIService        ← 틀(설계도)
#     __init__(api_key)    ← 틀 찍을 때 자동 실행, client 세팅
#     get_insight(...)     ← AI 호출 함수
#
# 이 파일은 Flask를 모름. 순수하게 "AI한테 물어보고 답 돌려주기"만 함
# Flask랑 연결은 churn_main.py 에서 함
# ============================================================

from google import genai


class AIService:

    # ──────────────────────────────────────────────────────
    # __init__ : 틀을 찍을 때(객체 생성할 때) 딱 한 번 자동 실행
    #
    # 매개변수:
    #   api_key  → churn_main.py 에서 .env 읽어서 넘겨줌
    #              직접 여기에 키 적지 않아도 됨!
    #
    # ✏️ 모델 바꾸고 싶으면:
    #   self.model_name = "gemini-2.0-flash"  으로 수정
    # ──────────────────────────────────────────────────────
    def __init__(self, api_key):
        # Gemini 클라이언트 생성 → 이후 모든 함수가 self.client 로 공유
        self.client     = genai.Client(api_key=api_key)
        self.model_name = "gemini-2.5-pro"   # ← 모델명 바꿀 때 여기만 수정


    # ──────────────────────────────────────────────────────
    # get_insight : AI 분석 요청 → 답변 반환
    #
    # 매개변수:
    #   graph_data  : Flask가 DB에서 뽑은 6개 가설 데이터 dict
    #                 {"grade":"ALL", "h1":{...}, "h2":{...}, ...}
    #   user_message: 사용자가 채팅창에 입력한 질문 (수동 모드)
    #   auto_mode   : True = 페이지 로드 시 자동 분석
    #                 False = 사용자가 직접 질문
    #
    # 반환값:
    #   {"success": True,  "answer": "AI 답변 텍스트"}
    #   {"success": False, "answer": "에러 메시지"}
    # ──────────────────────────────────────────────────────
    def get_insight(self, graph_data, user_message=None, auto_mode=False):

        # ── Step 1. AI에게 줄 데이터 요약 만들기 ──────────────
        # graph_data 에서 꺼내서 AI가 읽기 좋은 텍스트로 변환
        # .get('키', 기본값) : 키가 없어도 에러 안 남
        grade = graph_data.get('grade', 'ALL')

        context = f"""
당신은 통신사 고객 이탈 분석 전문 AI 어드바이저입니다.
현재 대시보드에 표시된 데이터를 분석하여 기업 임원에게 보고하는 형식으로 답변해주세요.

=== 현재 데이터 요약 ===
선택 위험 등급: {grade}

[가설1] 상담전화건수별 해지건수
- X축(상담건수): {graph_data.get('h1', {}).get('labels', [])}
- Y축(해지건수): {graph_data.get('h1', {}).get('values', [])}

[가설2] 가입일 구간별 해지율(%)
- 구간: {graph_data.get('h2', {}).get('labels', [])}
- 해지율: {graph_data.get('h2', {}).get('values', [])}

[가설3] 총통화시간 구간별 해지율(%)
- 구간: {graph_data.get('h3', {}).get('labels', [])}
- 해지율: {graph_data.get('h3', {}).get('values', [])}

[가설4] 시간대별 통화 비율
- 해지고객: {graph_data.get('h4', {}).get('churn', [])}
- 유지고객: {graph_data.get('h4', {}).get('retain', [])}

[가설5] 상담강도 구간별 해지율(%)
- 구간: {graph_data.get('h5', {}).get('labels', [])}
- 해지율: {graph_data.get('h5', {}).get('values', [])}

[가설6] 시간당요금 구간별 해지율(%)
- 구간: {graph_data.get('h6', {}).get('labels', [])}
- 해지율: {graph_data.get('h6', {}).get('values', [])}
"""

        # ── Step 2. 모드에 따라 프롬프트 다르게 ──────────────
        if auto_mode:
            # 페이지 로드 시 자동 실행 → 전체 요약 리포트
            prompt = f"""{context}

위 데이터를 분석하여 아래 형식으로 기업 임원에게 보고해주세요.
구체적인 수치를 반드시 포함하고, 한국어로 작성해주세요.

🔴 핵심 위험 현황
(가장 심각한 이탈 위험 요인 2가지, 수치 포함)

📊 데이터 인사이트
(각 가설에서 발견된 주요 패턴 3가지)

💡 즉시 실행 가능한 전략
(구체적인 고객 유지 방안 3가지)
"""
        else:
            # 사용자가 직접 질문 → 질문에 맞게 답변
            prompt = f"""{context}

사용자 질문: {user_message}

위 데이터를 바탕으로 전문적이고 구체적으로 답변해주세요.
수치를 근거로 활용하고, 실행 가능한 제안을 포함해주세요.
"""

        # ── Step 3. Gemini API 호출 ──────────────────────────
        try:
            response = self.client.models.generate_content(
                model    = self.model_name,
                contents = prompt
            )
            return {"success": True, "answer": response.text}

        except Exception as e:
            # 에러 종류별 안내
            if "429" in str(e):
                # 429 = API 할당량 초과 (1분 뒤 재시도)
                return {"success": False, "answer": "죄송합니다. 현재 AI 요청이 너무 많습니다. 약 1분 뒤에 다시 시도해 주세요!"}
            return {"success": False, "answer": f"AI 서비스 오류: {str(e)}"}


    # ──────────────────────────────────────────────────────
    # ✏️ 조원 가설 추가 방법:
    #
    # 새 분석 함수가 필요하면 아래처럼 추가:
    #
    # def get_새기능(self, 파라미터):
    #     prompt = f"... {파라미터} ..."
    #     try:
    #         response = self.client.models.generate_content(
    #             model=self.model_name, contents=prompt
    #         )
    #         return {"success": True, "answer": response.text}
    #     except Exception as e:
    #         return {"success": False, "answer": str(e)}
    # ──────────────────────────────────────────────────────
