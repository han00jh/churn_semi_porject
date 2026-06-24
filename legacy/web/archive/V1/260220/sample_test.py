from flask import Flask, render_template, request, redirect, url_for
import pandas as pd
from sqlalchemy import create_engine    , text, Integer, Float, Numeric
from sqlalchemy.dialects.oracle import NUMBER,  FLOAT as ORA_FLOAT
import json
import matplotlib.pyplot as plt
import seaborn as sns
import os

app = Flask(__name__)

@app.route("/")   #--------------------------------------------------------------------------------- 웹주소
def index_html():
    engine = create_engine("oracle+cx_oracle://it:0000@localhost:1521/xe")
    conn = engine.connect()
    df = pd.read_sql("SELECT * FROM emp", conn)
    df_news = pd.read_sql("SELECT * FROM ytn_news", conn)
    conn.close()
    engine.dispose()


    chart_data = { "label1" : df['ename'].tolist()
                    ,"value1": df['sal'].tolist()
                    ,"label2": ["aa", "bb", "cc", "dd"]
                    ,"value2": [110, 220, 330, 440]
                 }
    # news_data = { "label3" : df_news.columns.to_list()
    #             , "value3":  df_news.values
    #               }

    #--------------------------------------------------------------------------------
    news_list_dict = df_news.to_dict(orient="records") #   [  {}, {}, {}  ]
    # --------------------------------------------------------------------------------

    mylist = [10,20,30,40]
    return render_template('index.html'   #----------------------------------------- .html파일
                           ,MY_KEY_MYLIST = mylist         #-------------------------------- 전송값
                           ,MY_KEY_CHART_DATA = chart_data
                            #,MY_KEY_NEWS_DATA=news_data
                           ,MY_KEY_NEWS_LIST_DICT=news_list_dict
                           )


@app.route("/login_html")
def login_html():
    return render_template('login.html')


@app.route("/charts_html")
def charts_html():
    return render_template('charts.html')




@app.route("/register_html")                       #----------------------- 웹주소
def register_html():
    return render_template('register.html')        #----------------------- .html파일


#------------------------------------------------
# 회원가입 처리부
#------------------------------------------------
@app.route("/register", methods=["POST"])                       #----------------------- 웹주소
def register():
    user_name   = request.form.get("user_name")
    user_id     = request.form.get("user_id")
    user_mobile = request.form.get("user_mobile")
    user_pw     = request.form.get("user_pw")
    print(user_name, user_id, user_mobile, user_pw)

    # ---------------DB입력---------------
    engine = create_engine("oracle+cx_oracle://it:0000@localhost:1521/xe")

    with engine.begin() as conn:
        conn.execute(text("insert into users2 values(users_sequence.nextval, :aa,  :bb, :cc, :dd, 'u',null)"),
                     {"aa": user_id, "bb": user_name, "cc": user_pw, "dd":user_mobile }
                     )
    return render_template('login.html')


"""
drop sequence users_sequence;
create sequence users_sequence start with 1 increment by 1 nocache;

CREATE TABLE "USERS2" (	
    "USER_SEQ" NUMBER PRIMARY KEY , 
	"USER_ID" VARCHAR2(20 BYTE), 
	"USER_NAME" VARCHAR2(20 BYTE), 
	"USER_PW" VARCHAR2(20 BYTE), 
	"USER_MOBILE" VARCHAR2(15 BYTE), 
	"USER_GUBUN" CHAR(1 BYTE), 
	"MGR_SEQ" NUMBER
);

insert into users2 values(users_sequence.nextval,'lee','이씨','111','01058589696','u',null);
insert into users2 values(users_sequence.nextval,'kim','김씨','222','01023654787','u',1);
insert into users2 values(users_sequence.nextval,'park','박씨','333','01052528989','u',1);
insert into users2 values(users_sequence.nextval,'hong','홍씨','555','0108889999','u',3);
insert into users2 values(users_sequence.nextval,'admin','이관리','444','0101234567','a',null);

commit;
"""




#------------------------------------------------
# 로그인 처리부
#------------------------------------------------
@app.route("/login", methods=["POST"])
def login():
    user_id = request.form.get("user_id")
    user_pw = request.form.get("user_pw")
    print(user_id, user_pw)

    #---------------DB조회---------------
    engine = create_engine("oracle+cx_oracle://it:0000@localhost:1521/xe")

    find_user_name = ""
    with engine.connect() as conn:
        rows = conn.execute(text("select user_name, user_gubun from users2 where user_id=:aa and user_pw=:bb"),
                            {"aa": user_id, "bb": user_pw}
                            )
        for r in rows:
            print(r.user_name, r.user_gubun)
            find_user_name = r.user_name

    if(find_user_name != "") :
        return render_template('rest_test_result.html',
                               KEY_MY_NAME=find_user_name)
    else :
        #return render_template('index.html')
        #return redirect(url_for("index_html"))  #-----index.html로 가는 함수이름
        return redirect("/")                     #-----index.html로 가는 주소



@app.route("/rest_get", methods=["GET"])
def rest_get():
    # res = {"res":"get-ok"}
    # return res
    uid = request.args.get("uid")
    upw = request.args.get("upw")
    print(uid, upw)

    return render_template('rest_test_result.html',
                           KEY_MY_NAME=uid)

#-----------------------------------------------
@app.route("/rest_test_html") #  , methods=["GET", "POST"])
def rest_test_html():
    return render_template('rest_test.html')

#----------------------------------------------
# rest_test.html :: 부서별 사원 검색
#----------------------------------------------
@app.route("/form_search", methods=["POST"])
def form_search():
    deptno   = request.form.get("deptno")
    print(deptno)

    # ---------------DB조회---------------
    engine = create_engine("oracle+cx_oracle://it:0000@localhost:1521/xe")

    emp_list = []
    with engine.connect() as conn:
        rows = conn.execute(text("select empno, ename, deptno from emp where deptno=:aa "),
                            {"aa": deptno}
                            )
        for r in rows:
            #print(r.empno, r.ename, r.deptno)
            emp_list.append( [r.empno, r.ename, r.deptno]  )

    return render_template('rest_test.html',
                           KEY_MY_EMP_LIST=emp_list)




#----------------------------------------------
# index.html :: 부서별 급여 바차트
#----------------------------------------------
@app.route("/rest_chart", methods=["POST"])
def rest_chart():
    deptno   = request.form.get("deptno")
    print(deptno)
    # ---------------DB조회---------------
    engine = create_engine("oracle+cx_oracle://it:0000@localhost:1521/xe")
    ename_list = []
    sal_list = []
    with engine.connect() as conn:
        rows = conn.execute(text("select ename,sal from emp where deptno=:aa"),
                            {"aa": deptno}
                            )
        for r in rows:
            ename_list.append( r.ename)
            sal_list.append(r.sal)

    chart_data = {  "label1": ename_list
                  , "value1":sal_list
                 }

    return chart_data



#----------------------------------------------
# rest_test.html :: 부서별 사원 검색
#----------------------------------------------
@app.route("/rest_search", methods=["POST"])
def rest_search():
    deptno   = request.form.get("deptno")
    print(deptno)

    # ---------------DB조회---------------
    engine = create_engine("oracle+cx_oracle://it:0000@localhost:1521/xe")

    emp_list = []
    with engine.connect() as conn:
        rows = conn.execute(text("select empno, ename, deptno from emp where deptno=:aa "),
                            {"aa": deptno}
                            )
        for r in rows:
            #print(r.empno, r.ename, r.deptno)
            emp_list.append( [r.empno, r.ename, r.deptno]  )

    return emp_list



#----------------------------------------------
# rest_test.html :: 사원명 검색
#----------------------------------------------
@app.route("/rest_search2", methods=["POST"])
def rest_search2():
    ename = request.form.get("ename")
    print(ename)

    # ---------------DB조회---------------
    engine = create_engine("oracle+cx_oracle://it:0000@localhost:1521/xe")

    emp_list = []
    with engine.connect() as conn:
        rows = conn.execute(text("select empno, ename, deptno from emp where ename like upper(:aa) "),
                                 {"aa": f"%{ename}%"}
                            )
        for r in rows:
            # print(r.empno, r.ename, r.deptno)
            emp_list.append([r.empno, r.ename, r.deptno])

    return emp_list



@app.route("/rest_post", methods=["POST"])
def rest_post():
    uid   = request.form.get("uid")
    upw   = request.form.get("upw")
    habit = request.form.getlist("habit")
    gen   = request.form.get("gen")
    sec   = request.form.get("sec")
    addr  = request.form.get("addr")
    memo  = request.form.get("memo")

    print(uid, upw, habit, gen, sec, addr, memo)

    # ---------- 들어온 데이터 처리부 ---------------
    # res = {"res": "post-ok"}
    # return res
    return render_template('rest_test_result.html',
                           KEY_MY_NAME = uid)





app.run(host='127.0.0.1', port=7777, debug=True)