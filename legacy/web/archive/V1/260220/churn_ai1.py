# ai_service.py

#pip install groq
from groq import Groq



class AIService:
    def __init__(self, api_key):
        self.client = Groq(api_key=api_key)
        self.model_name = "llama-3.3-70b-versatile"

    def check_connection(self):
        try:
            self.client.chat.completions.create(
                messages=[{"role": "user", "content": "ping"}],
                model=self.model_name,
                max_tokens=5,
            )
            return {"status": "ok", "model": self.model_name}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_insight(self, graph_data, user_message=None, auto_mode=False, mode=None, hypothesis_id=None):
        grade = graph_data.get('grade', 'ALL')
        context = f"현재 분석 중인 위험 등급: {grade}\n"

        for i in range(1, 7):
            h_key = f"h{i}"
            h_data = graph_data.get(h_key, {})
            title = h_data.get('title', f'가설{i}')
            values = h_data.get('values', [])

            if isinstance(values, list) and len(values) > 10:
                nums = [v for v in values if isinstance(v, (int, float))]
                if nums:
                    val_str = f"평균:{sum(nums) / len(nums):.2f}, 최대:{max(nums)}, 개수:{len(nums)}"
                else:
                    val_str = f"데이터 {len(values)}개 존재"
            else:
                val_str = str(values)
            context += f"[{h_key}: {title}] 데이터: {val_str}\n"

        # ✨ [강력 수정] AI에게 주는 지침을 매우 구체적으로 바꿨습니다.
        system_msg = (
            "당신은 대한민국 최고의 통신사 데이터 분석 전문가입니다. "
            "반드시 다음 규칙을 지키세요:\n"
            "1. 모든 답변은 100% 한국어로만 작성하세요.\n"
            "2. 절대로 영어(Dramatically 등), 한자(可能性 등), 외국 문자를 섞지 마세요.\n"
            "3. 보고서 형식으로 깔끔하게 정리하세요.\n"
            "4. 데이터에 없는 내용은 추측하지 마세요."
        )

        if auto_mode:
            prompt = f"{context}\n위 데이터를 바탕으로 고객 이탈 방지 전략을 한국어로 요약해줘."
        elif mode == "hypothesis":
            prompt = f"{context}\n가설 {hypothesis_id}번에 대해 한국어로 자세히 설명해줘."
        else:
            prompt = f"{context}\n질문: {user_message}\n답변은 한국어로만 해줘."

        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt}
                ],
                model=self.model_name,
                temperature=0.3,  # ← 0.3으로 낮추면 AI가 헛소리를 덜 하고 얌전해집니다.
            )
            return {"success": True, "answer": chat_completion.choices[0].message.content}
        except Exception as e:
            print(f"❌ AI 에러 발생: {str(e)}")
            return {"success": False, "answer": f"Groq 서비스 오류: {str(e)}"}