# churn_ai.py
# pip install groq anthropic

import os
from groq import Groq
import anthropic
from dotenv import load_dotenv

load_dotenv()

# ──────────────────────────────────────────────
# .env 설정:
#   USE_MODE=auto   → 평소 (그록 → 클로드 폴백)
#   USE_MODE=claude → 발표날 (처음부터 클로드)
# ──────────────────────────────────────────────
USE_MODE = os.getenv("USE_MODE", "auto")

GROQ_KEYS = [
    k for k in [
        os.getenv("GROQ_API_KEY_1"),
        os.getenv("GROQ_API_KEY_2"),
        os.getenv("GROQ_API_KEY_3"),
        os.getenv("GROQ_API_KEY_4"),
    ] if k
]

ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")

PRICE_IN  = 0.80 / 1_000_000
PRICE_OUT = 4.00 / 1_000_000
LIMIT_USD = 10.0
WARN_USD  = 9.0


class AIService:
    def __init__(self):
        self._groq_idx        = 0
        self._groq_exhausted  = False
        self._claude_approved = False
        self._use_claude      = (USE_MODE == "claude")

        self._claude_in    = 0
        self._claude_out   = 0
        self._claude_calls = 0

        self._groq_clients  = [Groq(api_key=k) for k in GROQ_KEYS]
        self._claude_client = anthropic.Anthropic(api_key=ANTHROPIC_KEY) if ANTHROPIC_KEY else None

        self._print_status()

    def _print_status(self):
        print("=" * 50)
        if self._use_claude:
            print("🟣 AI MODE : Claude (발표 모드 - 강제 지정)")
            print("   모델    : claude-haiku-4-5")
        else:
            print("🟢 AI MODE : Groq 자동 폴백 모드")
            print(f"   Groq 키 : {len(self._groq_clients)}개 등록")
            print(f"   현재 키 : Groq KEY {self._groq_idx + 1}")
            print(f"   Claude  : {'폴백 준비됨' if self._claude_client else '키 없음 ⚠️'}")
        print("=" * 50)

    def get_api_status(self):
        if self._use_claude or self._claude_approved:
            usage_usd = self._claude_in * PRICE_IN + self._claude_out * PRICE_OUT
            return {
                "mode"     : "claude",
                "label"    : "🟣 Claude API",
                "detail"   : f"사용 ${usage_usd:.3f} / $10.00",
                "warning"  : usage_usd >= WARN_USD,
                "exhausted": usage_usd >= LIMIT_USD,
            }
        else:
            return {
                "mode"     : "groq",
                "label"    : f"🟢 Groq API  KEY {self._groq_idx + 1} / {len(self._groq_clients)}",
                "detail"   : "무료",
                "warning"  : False,
                "exhausted": False,
            }

    def approve_claude(self):
        self._claude_approved = True
        print("✅ Claude 유료 전환 승인됨!")
        print("🟣 Claude 사용 시작 | 한도 $10.00")

    def _call_groq(self, system_msg, prompt):
        while self._groq_idx < len(self._groq_clients):
            client = self._groq_clients[self._groq_idx]
            try:
                res = client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": system_msg},
                        {"role": "user",   "content": prompt}
                    ],
                    model="llama-3.3-70b-versatile",
                    temperature=0.3,
                    max_tokens=300,
                )
                print(f"✅ Groq KEY {self._groq_idx + 1} 호출 성공")
                return {"success": True, "answer": res.choices[0].message.content}
            except Exception as e:
                err = str(e)
                if "rate_limit" in err.lower() or "429" in err or "quota" in err.lower():
                    print(f"⚠️  Groq KEY {self._groq_idx + 1} 한도 소진 → 다음 키 전환")
                    self._groq_idx += 1
                    if self._groq_idx < len(self._groq_clients):
                        print(f"🔄 Groq KEY {self._groq_idx + 1} 사용 시작")
                    else:
                        print("❌ 모든 Groq 키 소진 → Claude 전환 대기 중")
                        self._groq_exhausted = True
                        return {"success": False, "need_claude": True}
                else:
                    print(f"❌ Groq 에러: {e}")
                    return {"success": False, "answer": f"Groq 오류: {e}"}
        self._groq_exhausted = True
        return {"success": False, "need_claude": True}

    def _call_claude(self, system_msg, prompt):
        if not self._claude_client:
            return {"success": False, "answer": "Claude API 키가 없습니다."}
        usage_usd = self._claude_in * PRICE_IN + self._claude_out * PRICE_OUT
        if usage_usd >= LIMIT_USD:
            print("💸 Claude 한도($10) 초과!")
            return {"success": False, "answer": "Claude 한도 초과($10)", "exhausted": True}
        try:
            res = self._claude_client.messages.create(
                model      = "claude-haiku-4-5",
                max_tokens = 300,
                system     = system_msg,
                messages   = [{"role": "user", "content": prompt}],
            )
            self._claude_in    += res.usage.input_tokens
            self._claude_out   += res.usage.output_tokens
            self._claude_calls += 1
            usage_usd = self._claude_in * PRICE_IN + self._claude_out * PRICE_OUT
            print(f"🟣 Claude #{self._claude_calls} | 누적 ${usage_usd:.4f} / $10.00 ({usage_usd/LIMIT_USD*100:.1f}%)")
            return {
                "success"  : True,
                "answer"   : res.content[0].text,
                "warning"  : usage_usd >= WARN_USD,
                "exhausted": usage_usd >= LIMIT_USD,
            }
        except Exception as e:
            print(f"❌ Claude 에러: {e}")
            return {"success": False, "answer": f"Claude 오류: {e}"}

    def _call(self, system_msg, prompt):
        if self._use_claude or self._claude_approved:
            return self._call_claude(system_msg, prompt)
        result = self._call_groq(system_msg, prompt)
        if result.get("need_claude"):
            return {"success": False, "need_claude": True}
        return result

    _SYS = (
        "당신은 대한민국 최고의 통신사 데이터 분석 전문가입니다. "
        "반드시 다음 규칙을 지키세요:\n"
        "1. 모든 답변은 100% 한국어로만 작성하세요.\n"
        "2. 절대로 영어, 한자, 외국 문자를 섞지 마세요.\n"
        "3. 데이터에 없는 내용은 추측하지 마세요."
    )

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

    def get_summary(self, graph_data):
        return self._call(self._SYS,
            self._build_context(graph_data) +
            "\n위 6개 그래프 데이터 전체를 분석해서, 현재 고객 이탈 상황을 "
            "핵심만 뽑아 딱 1문장(30자 이내)으로 요약해줘. "
            "숫자나 등급을 포함해서 임팩트 있게. 문장 외 다른 말은 절대 쓰지 마.")

    def get_strategy(self, graph_data):
        return self._call(self._SYS,
            self._build_context(graph_data) +
            "\n위 6개 그래프 데이터를 직접 분석해서, 고객 이탈을 줄이기 위한 "
            "가장 효과적인 대책을 딱 1문장(30자 이내)으로 써줘. "
            "구체적인 대상(등급/구간)과 행동을 포함해. 문장 외 다른 말은 절대 쓰지 마.")

    def get_forecast(self, graph_data):
        return self._call(self._SYS,
            self._build_context(graph_data) +
            "\n위 6개 그래프 데이터를 분석해서, 이탈 방지 대책을 실행했을 때 "
            "예상되는 효과를 매출 증가율 또는 해지율 감소율 같은 구체적 수치로 "
            "딱 1문장(30자 이내)으로 써줘. "
            "반드시 %나 숫자를 포함해. 문장 외 다른 말은 절대 쓰지 마.")

    def get_topic_insight(self, topic, topic_name, graph_data):
        graph_data["_topic_name"] = topic_name
        graph_data["_topic"]      = topic

        summary  = self.get_summary(graph_data)
        strategy = self.get_strategy(graph_data)
        forecast = self.get_forecast(graph_data)

        need_claude = any([
            summary.get("need_claude"),
            strategy.get("need_claude"),
            forecast.get("need_claude"),
        ])

        def fmt(r, number, label):
            return {"number": number, "label": label, "sub": r.get("answer", "분석 대기 중...")}

        return {
            "summary"    : fmt(summary,  "📊", "현황 요약"),
            "strategy"   : fmt(strategy, "🎯", "핵심 대책"),
            "forecast"   : fmt(forecast, "💹", "기대 효과"),
            "key_index"  : self._groq_idx + 1,
            "need_claude": need_claude,
            "api_status" : self.get_api_status(),
        }

    def get_insight(self, graph_data, user_message=None, auto_mode=False, mode=None, hypothesis_id=None):
        ctx = self._build_context(graph_data)
        if auto_mode:
            prompt = f"{ctx}\n위 데이터를 바탕으로 고객 이탈 방지 전략을 한국어로 요약해줘."
        elif mode == "hypothesis":
            prompt = f"{ctx}\n가설 {hypothesis_id}번에 대해 한국어로 자세히 설명해줘."
        else:
            prompt = f"{ctx}\n질문: {user_message}\n답변은 한국어로만 해줘."
        return self._call(self._SYS, prompt)

    def check_connection(self):
        status = self.get_api_status()
        return {"status": "ok", "model": status["label"], "detail": status["detail"]}
