import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import json
import os
import random
import re
from collections import Counter

# --- 0. 텍스트 일반화 함수 ---
def generalize_edge_text(edge_text):
    text = edge_text
    text = re.sub(r'삼각형\s*[a-zA-Z]{3}', '삼각형', text)
    text = re.sub(r'사각형\s*[a-zA-Z]{4}', '사각형', text)
    text = re.sub(r'변\s*[a-zA-Z]{1,3}', '변', text)
    text = re.sub(r'선분\s*[a-zA-Z]{1,3}', '선분', text)
    text = re.sub(r'점\s*[a-zA-Z]', '점', text)
    text = re.sub(r'각\s*[a-zA-Z]{1,3}', '각', text)
    text = re.sub(r'[a-zA-Z]=[0-9]+부터\s*[a-zA-Z]=[0-9]+까지', '특정 구간에서', text)
    text = re.sub(r'함수\s*[a-zA-Z]\([a-zA-Z]\)', '함수', text)
    text = re.sub(r'[a-zA-Z]\([a-zA-Z]\)', '주어진 함수', text) 
    text = re.sub(r'[a-zA-Z]\'(\([a-zA-Z]\))?', '도함수', text) 
    text = re.sub(r'y=[a-zA-Z0-9\(\)]+', '주어진 함수식', text) 
    text = re.sub(r'[a-zA-Z][₀-₉]+', '특정 항', text) 
    text = re.sub(r'[a-zA-Z]_[a-zA-Z0-9]+', '특정 항', text) 
    text = re.sub(r'(자연수|정수|실수|상수|기울기|조건)\s*[a-zA-Z]', r'\1', text) 
    return text

# --- 1. 구글 시트 데이터베이스 연결 (보안 핵심) ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_full_db_from_sheets():
    try:
        df = conn.read(ttl="5s")
        if df.empty: return {}
        db = {}
        for _, row in df.iterrows():
            code = str(row['academy_code'])
            db[code] = json.loads(row['students_data_json'])
        return db
    except:
        return {}

def save_full_db_to_sheets(full_db):
    rows = []
    for code, data in full_db.items():
        rows.append({
            "academy_code": code,
            "students_data_json": json.dumps(data, ensure_ascii=False)
        })
    df_to_save = pd.DataFrame(rows)
    conn.update(data=df_to_save)
    st.cache_data.clear()

# --- 2. 로그인 및 세션 관리 ---
if 'academy_code' not in st.session_state:
    st.set_page_config(page_title="EDGE MVP1 로그인", layout="centered")
    st.title("EDGE 약점 진단 시스템 (MVP1)")
    academy_input = st.text_input("학원 코드를 입력하세요", type="password")
    if st.button("시스템 접속"):
        if academy_input.strip():
            st.session_state.academy_code = academy_input.strip()
            st.rerun()
    st.stop()

academy_code = st.session_state.academy_code
full_db = load_full_db_from_sheets()

# 해당 학원의 데이터만 추출하거나 새로 생성
if academy_code not in full_db:
    full_db[academy_code] = {}
    save_full_db_to_sheets(full_db)

students_db = full_db[academy_code]

# --- 3. 기출문제 원본 DB 로드 ---
@st.cache_data
def load_exam_db():
    with open("edge_db_full_2022.json", "r", encoding="utf-8") as f:
        return json.load(f)

db_data = load_exam_db()
exam_names = sorted(list(set('_'.join(item['id'].split('_')[:-1]) for item in db_data)))

# --- 4. 좌측 사이드바: 학생 관리 ---
st.sidebar.title(f"🏢 학원 코드: {academy_code}")
if st.sidebar.button("로그아웃"):
    st.session_state.clear()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.title("👨‍🎓 학생 DB 관리")

new_student = st.sidebar.text_input("새 학생 이름")
if st.sidebar.button("학생 추가"):
    if new_student and new_student not in students_db:
        full_db[academy_code][new_student] = {'wrong_questions': [], 'exams': []}
        save_full_db_to_sheets(full_db)
        st.session_state.current_student_name = new_student
        st.rerun()

st.sidebar.markdown("---")
student_list = list(students_db.keys())
if student_list:
    current_student = st.sidebar.selectbox("학생 선택", student_list, 
                                          index=student_list.index(st.session_state.get('current_student_name', student_list[0])) if st.session_state.get('current_student_name') in student_list else 0)
    st.session_state.current_student_name = current_student
    
    if st.sidebar.button("🚨 현재 학생 삭제"):
        del full_db[academy_code][current_student]
        save_full_db_to_sheets(full_db)
        st.session_state.current_student_name = None
        st.rerun()
else:
    current_student = None
    st.sidebar.warning("학생을 추가해주세요.")

# --- 5. 메인 화면 ---
st.title("EDGE 약점 진단 시스템 (MVP1)")

if current_student:
    tab1, tab2 = st.tabs([f"📝 {current_student} - 오답 누적", f"📊 {current_student} - 분석"])

    with tab1:
        st.subheader("시험지 오답 입력")
        selected_exam = st.selectbox("시험지 선택", exam_names)
        exam_questions = [q for q in db_data if '_'.join(q['id'].split('_')[:-1]) == selected_exam]
        
        cols = st.columns(5)
        wrong_answers = []
        for i, q in enumerate(exam_questions):
            q_num = q['id'].split('_')[-1]
            if cols[i % 5].checkbox(q_num, key=f"q_{selected_exam}_{q_num}"):
                wrong_answers.append(q)
        
        if st.button("DB에 오답 누적"):
            if wrong_answers:
                full_db[academy_code][current_student]['wrong_questions'].extend(wrong_answers)
                if selected_exam not in full_db[academy_code][current_student]['exams']:
                    full_db[academy_code][current_student]['exams'].append(selected_exam)
                save_full_db_to_sheets(full_db)
                st.success("저장 완료!")
                st.rerun()

    with tab2:
        s_data = students_db[current_student]
        w_qs = s_data.get('wrong_questions', [])
        if not w_qs:
            st.info("오답 데이터가 없습니다.")
        else:
            st.markdown("#### 🚨 계층적 약점 분석")
            all_nodes = [n for q in w_qs for n in q['nodes']]
            node_counts = Counter(all_nodes)
            
            for node, n_count in node_counts.most_common():
                st.error(f"### 📍 {node} ({n_count}회)")
                g_edges = [generalize_edge_text(e) for q in w_qs if node in q['nodes'] for e in q['edges']]
                edge_counts = Counter(g_edges)
                
                for text, count in edge_counts.most_common():
                    prefix = f"🔥 [중복 {count}회]" if count >= 2 else "[1회]"
                    st.markdown(f"- {prefix} {text}")
                
                # 추천 문제 로직
                candidate_q = [q['id'].replace('_', ' ') for q in db_data if node in q['nodes'] and not any(wq['id'] == q['id'] for wq in w_qs)]
                if candidate_q:
                    random.shuffle(candidate_q)
                    st.markdown(f"↳ 💊 **보안 추천:** {', '.join(candidate_q[:3])}")
                st.markdown("---")