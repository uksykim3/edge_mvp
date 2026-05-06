import streamlit as st
import json
import os
import random
import re
from collections import Counter

# --- 0. 텍스트 일반화 함수 (Semi-Micro 전용) ---
def generalize_edge_text(edge_text):
    text = edge_text
    
    # 도형 및 기하 일반화
    text = re.sub(r'삼각형\s*[a-zA-Z]{3}', '삼각형', text)
    text = re.sub(r'사각형\s*[a-zA-Z]{4}', '사각형', text)
    text = re.sub(r'변\s*[a-zA-Z]{1,3}', '변', text)
    text = re.sub(r'선분\s*[a-zA-Z]{1,3}', '선분', text)
    text = re.sub(r'점\s*[a-zA-Z]', '점', text)
    text = re.sub(r'각\s*[a-zA-Z]{1,3}', '각', text)
    
    # 함수 및 구간 일반화
    text = re.sub(r'[a-zA-Z]=[0-9]+부터\s*[a-zA-Z]=[0-9]+까지', '특정 구간에서', text)
    text = re.sub(r'함수\s*[a-zA-Z]\([a-zA-Z]\)', '함수', text)
    text = re.sub(r'[a-zA-Z]\([a-zA-Z]\)', '주어진 함수', text) 
    text = re.sub(r'[a-zA-Z]\'(\([a-zA-Z]\))?', '도함수', text) 
    text = re.sub(r'y=[a-zA-Z0-9\(\)]+', '주어진 함수식', text) 
    
    # 수열 및 변수 일반화
    text = re.sub(r'[a-zA-Z][₀-₉]+', '특정 항', text) 
    text = re.sub(r'[a-zA-Z]_[a-zA-Z0-9]+', '특정 항', text) 
    text = re.sub(r'(자연수|정수|실수|상수|기울기|조건)\s*[a-zA-Z]', r'\1', text) 

    return text

# --- 1. 학원 로그인 (DB 분리) 시스템 ---
if 'academy_code' not in st.session_state:
    st.set_page_config(page_title="EDGE 시스템 로그인", layout="centered")
    st.title("EDGE 약점 진단 시스템")
    st.subheader("원장님 전용 로그인")
    
    academy_input = st.text_input("부여받은 학원 코드를 입력하세요 (예: A101)", type="password")
    
    if st.button("시스템 접속"):
        if academy_input.strip() == "":
            st.error("학원 코드를 입력해주세요.")
        else:
            st.session_state.academy_code = academy_input.strip()
            st.rerun()
    st.stop()

academy_code = st.session_state.academy_code

# --- 2. 기출문제 원본 DB 로드 ---
@st.cache_data
def load_exam_db():
    with open("edge_db_full_2022.json", "r", encoding="utf-8") as f:
        return json.load(f)

db_data = load_exam_db()

exam_names = set()
for item in db_data:
    exam_name = '_'.join(item['id'].split('_')[:-1])
    exam_names.add(exam_name)
exam_names = sorted(list(exam_names))

# --- 3. 영구 저장을 위한 학원별 학생 DB 세팅 ---
STUDENT_DB_FILE = f"students_db_{academy_code}.json"

def load_student_db():
    if os.path.exists(STUDENT_DB_FILE):
        with open(STUDENT_DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_student_db(data):
    with open(STUDENT_DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

students_db = load_student_db()

if 'current_student_name' not in st.session_state:
    st.session_state.current_student_name = None

# --- 4. 좌측 사이드바: 학생 관리 및 설정 ---
st.sidebar.title(f"🏢 학원 코드: {academy_code}")
if st.sidebar.button("로그아웃"):
    st.session_state.clear()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.title("👨‍🎓 학원생 DB 관리")

new_student = st.sidebar.text_input("새로운 학생 이름 입력")
if st.sidebar.button("학생 추가하기"):
    if new_student:
        if new_student not in students_db:
            students_db[new_student] = {'wrong_questions': [], 'exams': []}
            save_student_db(students_db)
            st.session_state.current_student_name = new_student 
            st.sidebar.success(f"'{new_student}' 학생이 추가되었습니다.")
            st.rerun()
        else:
            st.sidebar.error("이미 존재하는 학생입니다.")

st.sidebar.markdown("---")

current_student = None
if students_db:
    student_list = list(students_db.keys())
    if st.session_state.current_student_name in student_list:
        default_idx = student_list.index(st.session_state.current_student_name)
    else:
        default_idx = 0
        
    current_student = st.sidebar.selectbox("📂 현재 분석할 학생 선택", student_list, index=default_idx)
    st.session_state.current_student_name = current_student
    st.sidebar.info(f"현재 선택됨: **{current_student}**")
else:
    st.sidebar.warning("위에서 학생을 먼저 추가해주세요.")

# --- 데이터 관리 (초기화 및 삭제) ---
st.sidebar.markdown("---")
if current_student:
    if st.sidebar.button("⚠️ 현재 학생 데이터 전체 초기화"):
        students_db[current_student] = {'wrong_questions': [], 'exams': []}
        save_student_db(students_db)
        st.sidebar.success("데이터가 초기화되었습니다.")
        st.rerun()
        
    # --- [신규 추가] 학생 삭제 기능 ---
    if st.sidebar.button("🚨 현재 학생 삭제"):
        del students_db[current_student]
        save_student_db(students_db)
        st.session_state.current_student_name = None # 선택된 학생 상태 초기화
        st.sidebar.success(f"'{current_student}' 학생이 DB에서 완전히 삭제되었습니다.")
        st.rerun()

# --- 5. 메인 화면: 진단 및 분석/처방 ---
st.title("EDGE 약점 진단 시스템")

if not current_student:
    st.info("👈 좌측 메뉴에서 학생을 먼저 추가하거나 선택해주세요.")
else:
    tab1, tab2 = st.tabs([f"📝 {current_student} - 오답 누적", f"📊 {current_student} - 분석 및 처방"])

    with tab1:
        st.subheader("새로운 시험지 오답 입력")
        selected_exam = st.selectbox("진단할 시험지를 선택하세요", exam_names)
        
        exam_questions = [item for item in db_data if '_'.join(item['id'].split('_')[:-1]) == selected_exam]
        
        cols = st.columns(5)
        wrong_answers = []
        
        for i, q in enumerate(exam_questions):
            q_num = q['id'].split('_')[-1]
            if cols[i % 5].checkbox(q_num, key=f"chk_{academy_code}_{current_student}_{selected_exam}_{q_num}_{i}"):
                wrong_answers.append(q)
        
        st.markdown("---")
        if st.button(f"{current_student} 학생 DB에 오답 누적하기"):
            if not wrong_answers:
                st.warning("틀린 문항을 1개 이상 선택해주세요.")
            else:
                if 'wrong_questions' not in students_db[current_student]:
                    students_db[current_student]['wrong_questions'] = []

                students_db[current_student]['wrong_questions'].extend(wrong_answers)
                if selected_exam not in students_db[current_student]['exams']:
                    students_db[current_student]['exams'].append(selected_exam)
                
                save_student_db(students_db)
                st.success("데이터 누적 완료!")
                st.rerun() 

    with tab2:
        student_data = students_db.get(current_student, {})
        wrong_questions = student_data.get('wrong_questions', [])
        
        st.subheader(f"🧑‍🎓 {current_student} 학생 종합 리포트 및 처방")
        
        if not wrong_questions:
            st.info("아직 누적된 오답 데이터가 없습니다.")
        else:
            st.markdown("#### 📚 누적된 시험 응시 이력")
            for exam in student_data.get('exams', []):
                st.markdown(f"- {exam}")
                
            st.markdown("---")
            st.markdown("#### 🚨 계층적 약점 분석 및 💊 문제 처방")
            
            all_nodes = []
            for q in wrong_questions:
                all_nodes.extend(q['nodes'])
            
            node_counts = Counter(all_nodes)
            
            for node, n_count in node_counts.most_common():
                st.error(f"### 📍 취약 단원: {node} (오답 누적: {n_count}문항)")
                
                generalized_edges = []
                for q in wrong_questions:
                    if node in q['nodes']:
                        for edge in q['edges']:
                            generalized_edges.append(generalize_edge_text(edge))
                
                edge_counts = Counter(generalized_edges)
                
                multiple_weakness = []
                single_weakness = []
                
                for text, count in edge_counts.most_common():
                    if count >= 2:
                        multiple_weakness.append(f"- **[중복 약점 {count}회]** 🔥 {text}")
                    else:
                        single_weakness.append(f"- [약점 1회] {text}")
                
                for mw in multiple_weakness:
                    st.markdown(mw)
                
                if single_weakness:
                    with st.expander("🔍 1회 약점 내역 보기"):
                        for sw in single_weakness:
                            st.markdown(f"<span style='color:gray;'>{sw}</span>", unsafe_allow_html=True)
                
                candidate_q = []
                for q_db in db_data:
                    if node in q_db['nodes']:
                        is_wrong = any(wq['id'] == q_db['id'] for wq in wrong_questions)
                        if not is_wrong:
                            clean_id = q_db['id'].replace('_', ' ')
                            candidate_q.append(clean_id)
                
                if candidate_q:
                    random.shuffle(candidate_q)
                    rec_display = ", ".join(candidate_q[:3])
                    st.markdown(f"<br>&nbsp;&nbsp;&nbsp;&nbsp;↳ 💊 **[{node}] 단원 보완을 위한 추천 기출:** {rec_display}", unsafe_allow_html=True)
                else:
                    st.markdown(f"<br>&nbsp;&nbsp;&nbsp;&nbsp;↳ 💊 **추천 기출문제:** DB 내 추가 문항 없음", unsafe_allow_html=True)
                    
                st.markdown("---")