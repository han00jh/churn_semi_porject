from flask import Flask, render_template, request, jsonify
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
import json

app = Flask(__name__)

# ============================================================
# Oracle DB 연결 설정
# ============================================================
def get_db_connection():
    engine = create_engine("oracle+cx_oracle://it:0000@localhost:1521/xe")
    return engine

# ============================================================
# 위험도 등급 계산 함수 (예측 확률 기반)
# ============================================================
def calculate_risk_grade(df):
    """
    고객별 위험도 등급을 A, B, C, D로 분류
    실제로는 ML 모델의 예측 확률을 사용해야 하지만,
    여기서는 상담전화건수와 가입일을 기반으로 임시 점수 계산
    """
    # 위험 점수 계산 (0~100)
    df['위험점수'] = (
        (df['상담전화건수'] / df['상담전화건수'].max() * 40) +  # 상담전화 40%
        ((df['가입일'].max() - df['가입일']) / df['가입일'].max() * 30) +  # 가입일 짧을수록 30%
        ((df['주간통화시간'] + df['저녁통화시간'] + df['밤통화시간']).min() / 
         (df['주간통화시간'] + df['저녁통화시간'] + df['밤통화시간']) * 30)  # 통화시간 적을수록 30%
    ) * 100
    
    # 등급 분류
    df['RISK_GRADE'] = pd.cut(df['위험점수'], 
                               bins=[0, 25, 50, 75, 100],
                               labels=['D', 'C', 'B', 'A'],
                               include_lowest=True)
    
    return df

# ============================================================
# 가설별 데이터 계산 함수들
# ============================================================
def calculate_hypothesis1(df):
    """가설1: 상담전화건수와 해지율 관계"""
    # 상담전화건수 구간화
    df['상담구간'] = pd.cut(df['상담전화건수'], bins=[0, 2, 4, 6, 10], labels=['0-2', '3-4', '5-6', '7+'])
    result = df.groupby('상담구간')['전화해지여부'].agg(['mean', 'count']).reset_index()
    result.columns = ['구간', '해지율', '고객수']
    return {
        'labels': result['구간'].tolist(),
        'churn_rate': (result['해지율'] * 100).round(2).tolist(),
        'customer_count': result['고객수'].tolist()
    }

def calculate_hypothesis2(df):
    """가설2: 가입일과 해지율 관계"""
    # 가입일 구간화 (분위수 기준)
    df['가입구간'] = pd.qcut(df['가입일'], q=4, labels=['신규', '중간', '오래', '최장기'])
    result = df.groupby('가입구간')['전화해지여부'].agg(['mean', 'count']).reset_index()
    result.columns = ['구간', '해지율', '고객수']
    return {
        'labels': result['구간'].tolist(),
        'churn_rate': (result['해지율'] * 100).round(2).tolist(),
        'customer_count': result['고객수'].tolist()
    }

def calculate_hypothesis3(df):
    """가설3: 총통화시간과 해지율 관계"""
    df['총통화시간'] = df['주간통화시간'] + df['저녁통화시간'] + df['밤통화시간']
    df['통화구간'] = pd.qcut(df['총통화시간'], q=4, labels=['매우낮음', '낮음', '보통', '높음'])
    result = df.groupby('통화구간')['전화해지여부'].agg(['mean', 'count']).reset_index()
    result.columns = ['구간', '해지율', '고객수']
    return {
        'labels': result['구간'].tolist(),
        'churn_rate': (result['해지율'] * 100).round(2).tolist(),
        'customer_count': result['고객수'].tolist()
    }

def calculate_hypothesis4(df):
    """가설4: 시간대별 통화 비율과 해지율"""
    df['총통화시간'] = df['주간통화시간'] + df['저녁통화시간'] + df['밤통화시간']
    df['주간비율'] = (df['주간통화시간'] / df['총통화시간'] * 100).fillna(0)
    df['저녁비율'] = (df['저녁통화시간'] / df['총통화시간'] * 100).fillna(0)
    df['밤비율'] = (df['밤통화시간'] / df['총통화시간'] * 100).fillna(0)
    
    # 해지/비해지 그룹별 평균
    churn_group = df[df['전화해지여부'] == 1]
    retain_group = df[df['전화해지여부'] == 0]
    
    return {
        'labels': ['주간', '저녁', '밤'],
        'churn_avg': [
            churn_group['주간비율'].mean(),
            churn_group['저녁비율'].mean(),
            churn_group['밤비율'].mean()
        ],
        'retain_avg': [
            retain_group['주간비율'].mean(),
            retain_group['저녁비율'].mean(),
            retain_group['밤비율'].mean()
        ]
    }

def calculate_hypothesis5(df):
    """가설5: 총통화시간 대비 상담전화건수 비율"""
    df['총통화시간'] = df['주간통화시간'] + df['저녁통화시간'] + df['밤통화시간']
    df['상담강도'] = (df['상담전화건수'] / (df['총통화시간'] + 1) * 100).fillna(0)
    df['상담강도구간'] = pd.qcut(df['상담강도'].clip(upper=df['상담강도'].quantile(0.95)), 
                               q=4, labels=['낮음', '중간', '높음', '매우높음'], duplicates='drop')
    result = df.groupby('상담강도구간')['전화해지여부'].agg(['mean', 'count']).reset_index()
    result.columns = ['구간', '해지율', '고객수']
    return {
        'labels': result['구간'].tolist(),
        'churn_rate': (result['해지율'] * 100).round(2).tolist(),
        'customer_count': result['고객수'].tolist()
    }

def calculate_hypothesis6(df):
    """가설6: 시간당 요금과 해지율"""
    df['총통화시간'] = df['주간통화시간'] + df['저녁통화시간'] + df['밤통화시간']
    df['총요금'] = df['주간통화요금'] + df['저녁통화요금'] + df['밤통화요금']
    df['시간당요금'] = (df['총요금'] / (df['총통화시간'] + 1)).fillna(0)
    df['요금구간'] = pd.qcut(df['시간당요금'], q=4, labels=['저렴', '보통', '비쌈', '매우비쌈'], duplicates='drop')
    result = df.groupby('요금구간')['전화해지여부'].agg(['mean', 'count']).reset_index()
    result.columns = ['구간', '해지율', '고객수']
    return {
        'labels': result['구간'].tolist(),
        'churn_rate': (result['해지율'] * 100).round(2).tolist(),
        'customer_count': result['고객수'].tolist()
    }

# ============================================================
# 메인 대시보드 페이지
# ============================================================
@app.route("/")
def dashboard():
    return render_template('dashboard.html')

# ============================================================
# 등급별 데이터 제공 (AJAX)
# ============================================================
@app.route("/get_risk_data", methods=["POST"])
def get_risk_data():
    risk_grade = request.json.get("risk_grade", "ALL")
    
    engine = get_db_connection()
    with engine.connect() as conn:
        df = pd.read_sql("SELECT * FROM TRAIN", conn)
    engine.dispose()
    
    # 위험도 등급 계산
    df = calculate_risk_grade(df)
    
    # 등급별 필터링
    if risk_grade != "ALL":
        df_filtered = df[df['RISK_GRADE'] == risk_grade].copy()
    else:
        df_filtered = df.copy()
    
    # 6개 가설 데이터 계산
    chart_data = {
        'hypothesis1': calculate_hypothesis1(df_filtered),
        'hypothesis2': calculate_hypothesis2(df_filtered),
        'hypothesis3': calculate_hypothesis3(df_filtered),
        'hypothesis4': calculate_hypothesis4(df_filtered),
        'hypothesis5': calculate_hypothesis5(df_filtered),
        'hypothesis6': calculate_hypothesis6(df_filtered),
        'total_customers': len(df_filtered),
        'churn_rate': (df_filtered['전화해지여부'].mean() * 100).round(2),
        'selected_grade': risk_grade
    }
    
    return jsonify(chart_data)

# ============================================================
# 고위험 고객 테이블 데이터
# ============================================================
@app.route("/high_risk_customers", methods=["POST"])
def high_risk_customers():
    engine = get_db_connection()
    with engine.connect() as conn:
        df = pd.read_sql("SELECT * FROM TRAIN", conn)
    engine.dispose()
    
    # 위험도 계산
    df = calculate_risk_grade(df)
    
    # 상위 100명 추출
    df_top = df.nlargest(100, '위험점수')[['ID', '위험점수', 'RISK_GRADE', '상담전화건수', '가입일', '전화해지여부']]
    df_top['순위'] = range(1, len(df_top) + 1)
    df_top['위험점수'] = df_top['위험점수'].round(2)
    
    return jsonify(df_top.to_dict(orient='records'))

# ============================================================
# Claude API 챗봇 (그래프 데이터 기반 인사이트)
# ============================================================
@app.route("/chat_insight", methods=["POST"])
def chat_insight():
    user_message = request.json.get("message", "")
    graph_data = request.json.get("graph_data", {})
    auto_mode = request.json.get("auto_mode", False)
    
    try:
        # Claude API 호출
        import anthropic
        
        # API 키는 환경변수에서 가져오는 것이 안전하지만, 여기서는 직접 전달받습니다
        # 실제 사용시에는 환경변수로 관리하세요
        
        # 그래프 데이터를 텍스트로 변환
        context = f"""
현재 대시보드에 표시된 데이터:
- 총 고객 수: {graph_data.get('total_customers', 'N/A')}
- 전체 해지율: {graph_data.get('churn_rate', 'N/A')}%
- 선택된 위험 등급: {graph_data.get('selected_grade', 'ALL')}

가설1 (상담전화건수와 해지율):
{json.dumps(graph_data.get('hypothesis1', {}), ensure_ascii=False, indent=2)}

가설2 (가입일과 해지율):
{json.dumps(graph_data.get('hypothesis2', {}), ensure_ascii=False, indent=2)}

가설3 (총통화시간과 해지율):
{json.dumps(graph_data.get('hypothesis3', {}), ensure_ascii=False, indent=2)}

가설4 (시간대별 통화 비율):
{json.dumps(graph_data.get('hypothesis4', {}), ensure_ascii=False, indent=2)}

가설5 (상담강도와 해지율):
{json.dumps(graph_data.get('hypothesis5', {}), ensure_ascii=False, indent=2)}

가설6 (시간당 요금과 해지율):
{json.dumps(graph_data.get('hypothesis6', {}), ensure_ascii=False, indent=2)}
"""
        
        if auto_mode:
            # 자동 인사이트 모드
            prompt = f"""
위 데이터를 분석하여 3가지 핵심 인사이트를 간단명료하게 제시해주세요.
각 인사이트는 이모지와 함께 1-2문장으로 작성하고, 구체적인 수치를 포함해주세요.

형식:
🎯 [인사이트1]
📊 [인사이트2]  
⚠️ [인사이트3]
"""
        else:
            # 사용자 질문 모드
            prompt = f"{context}\n\n사용자 질문: {user_message}\n\n위 데이터를 바탕으로 답변해주세요."
        
        # Claude API 직접 호출 (API 키 필요)
        # 실제 환경에서는 이 부분을 활성화하세요
        """
        client = anthropic.Anthropic(api_key="YOUR_API_KEY")
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        response_text = message.content[0].text
        """
        
        # 개발용 Mock 응답 (실제로는 위 Claude API 호출 사용)
        if auto_mode:
            response_text = f"""
🎯 **위험 등급 {graph_data.get('selected_grade', 'ALL')} 고객 분석**
총 {graph_data.get('total_customers', 'N/A')}명 중 해지율은 {graph_data.get('churn_rate', 'N/A')}%입니다.

📊 **상담전화 패턴 주목**
상담전화가 많은 고객군에서 해지율이 {graph_data.get('hypothesis1', {}).get('churn_rate', [0])[-1] if graph_data.get('hypothesis1') else 0}%로 가장 높습니다. 불만족 고객 관리가 시급합니다.

⚠️ **신규 가입자 이탈 위험**
가입일이 짧은 고객의 해지율이 {graph_data.get('hypothesis2', {}).get('churn_rate', [0])[0] if graph_data.get('hypothesis2') else 0}%로 높습니다. 초기 온보딩 강화가 필요합니다.

💡 **추천 액션 플랜**
A등급 고객 대상 전담 상담팀 배정 및 가입 3개월 이내 고객에게 혜택 제공을 권장합니다.
"""
        else:
            response_text = f"""
질문: "{user_message}"

현재 표시된 {graph_data.get('selected_grade', 'ALL')} 등급 고객 데이터를 분석하면:

- 총 {graph_data.get('total_customers', 'N/A')}명의 고객이 있으며, 해지율은 {graph_data.get('churn_rate', 'N/A')}%입니다.
- 6개 가설 중 상담전화건수와 가입일이 해지에 가장 큰 영향을 미치는 것으로 보입니다.

더 자세한 분석이 필요하시면 구체적인 질문을 해주세요!
"""
        
        return jsonify({
            "success": True,
            "answer": response_text
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "answer": f"⚠️ 챗봇 오류가 발생했습니다: {str(e)}"
        })

if __name__ == "__main__":
    app.run(host='127.0.0.1', port=6001, debug=True)
