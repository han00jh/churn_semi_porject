# ai_service.py
from groq import Groq
import json
import time

class AIService:
    def __init__(self, api_key):
        # Groq 클라이언트 설정
        self.client = Groq(api_key=api_key)
        # 추천 모델
        self.model_name = "llama-3.3-70b-versatile"

    def check_connection(self):
        status = {
            "provider": "Groq",
            "model_name": self.model_name,
            "api_key_loaded": False,
            "connection": "NOT_TESTED",
            "response_sample": None,
            "response_time_ms": None
        }

        try:
            if not self.client:
                status["connection"] = "CLIENT_NOT_INITIALIZED"
                return status

            status["api_key_loaded"] = True
            start = time.time()

            # ✨ Groq 방식으로 수정됨!
            response = self.client.chat.completions.create(
                messages=[{"role": "user", "content": "Say OK"}],
                model=self.model_name,
            )

            end = time.time()
            status["connection"] = "SUCCESS"
            status["response_sample"] = response.choices[0].message.content.strip()
            status["response_time_ms"] = round((end - start) * 1000, 2)
            return status

        except Exception as e:
            status["connection"] = "FAILED"
            status["error"] = str(e)
            return status

    def get_insight(self, graph_data, user_message=None, auto_mode=False):
        grade = graph_data.get('grade', 'ALL')
        context = f"현재 분석 중인 위험 등급: {grade}\n"
        for i in range(1, 7):
            h_key = f"h{i}"
            h_data = graph_data.get(h_key, {})
            context += f"[{h_key} 가설 데이터]\n- 제목: {h_data.get('title')}\n- 값: {h_data.get('values')}\n"

        system_msg = "당신은 통신사 고객 이탈 방지 전문가입니다. 데이터 기반으로 한국어로 답변하세요."

        if auto_mode:
            prompt = f"{context}\n위 데이터를 분석하여 핵심 위험 요인과 대응 전략을 요약 보고하세요."
        else:
            prompt = f"{context}\n사용자 질문: {user_message}"

        try:
            # ✨ Groq 방식 호출
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_msg},              ## 시스템 설정
                    {"role": "user", "content": prompt}                     ## 실제 질문
                ],
                model=self.model_name,
            )
            return {"success": True, "answer": chat_completion.choices[0].message.content}
        except Exception as e:
            return {"success": False, "answer": f"Groq 서비스 오류: {str(e)}"}