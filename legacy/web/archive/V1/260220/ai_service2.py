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


#설치
# pip install groq
# pip install google-genai



import os

from groq import Groq
from google import genai

PROVIDER = "groq"
# PROVIDER = "gemini"



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
    def __init__(self, api_key=None):

        if PROVIDER == "gemini":
            self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
            self.model_name = "gemini-2.5-flash"

        elif PROVIDER == "groq":
            self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
            self.model_name = "llama3-8b-8192"

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
    def get_insight(self, graph_data,
                    user_message=None,
                    auto_mode=False,
                    mode=None,
                    hypothesis_id=None):

        graph_data = graph_data or {}
        grade = graph_data.get("grade", "ALL")

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

        # ── Step 2. 분석 모드 분기 ───────────────────────

        # 🔴 1️⃣ 종합 분석 버튼 클릭 시
        if auto_mode:

            prompt = f"""
        {context}

        개별 가설을 나열하지 말고, 전체를 통합하여 분석하세요.

        🔴 1. 가장 영향력 높은 이탈 요인 TOP 2 (수치 근거 포함)
        🟠 2. 요인 간 상호작용 구조
        🟡 3. 고객 유형 2~3개 분류
        🟢 4. 실행 전략 3가지

        전문 보고서 형식으로 작성하세요.
        """

        # 🟡 2️⃣ 특정 가설 설명 버튼 클릭 시
        elif mode == "hypothesis" and hypothesis_id:

            prompt = f"""
        {context}

        현재 사용자는 가설{hypothesis_id}번 그래프 설명을 요청했습니다.

        해당 가설이 무엇을 의미하는지,
        왜 중요한지,
        실무에서 어떻게 해석하는지 설명하세요.
        수치를 근거로 작성하세요.
        """

        # 🟢 3️⃣ 일반 질문 모드
        else:

            prompt = f"""
        {context}

        사용자 질문:
        {user_message}

        데이터 근거로 수치를 인용하여 답변하세요.
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
