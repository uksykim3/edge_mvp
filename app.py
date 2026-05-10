import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import json
import os
import random
import re
from collections import Counter
from fpdf import FPDF
import tempfile
import datetime
import textwrap

# --- 0. 텍스트 일반화 함수 (분석용) ---
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

# --- 1. 구글 시트 데이터베이스 연동 ---
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

# --- 2. PDF 리포트 생성 함수 (에러 방지 텍스트 래핑 적용) ---
def create_pdf_report(student_name, w_qs, db_data, node_counts):
    pdf = FPDF()
    pdf.add_page()
    
    try:
        pdf.add_font("NanumGothic", style="", fname="NanumGothic.ttf")
        pdf.set_font("NanumGothic", size=20)
    except Exception as e:
        st.error("폰트 파일을 찾을 수 없습니다. 깃허브 최상단에 NanumGothic.ttf를 업로드해주세요.")
        return None

    # 헤더 섹션
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    pdf.cell(0, 15, f"[EDGE] {student_name} 학생 분석 리포트", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("NanumGothic", size=10)
    pdf.cell(0, 10, f"발행일: {today}", new_x="LMARGIN", new_y="NEXT", align="R")
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)

    # 섹션 1: 취약 단원 분석
    pdf.set_font("NanumGothic", size=14)
    pdf.cell(0, 12, "1. 취약 단원 및 개념 분석", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("NanumGothic", size=11)
    
    for node, n_count in node_counts.most_common():
        pdf.set_text_color(200, 0, 0) # 강조색
        pdf.cell(0, 10, f"📍 {node} (오답 누적: {n_count}회)", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
        
        g_edges = [generalize_edge_text(e) for q in w_qs if node in q['nodes'] for e in q['edges']]
        edge_counts = Counter(g_edges)
        
        for text, count in edge_counts.most_common():
            prefix = f"[중복 {count}회]" if count >= 2 else "[1회]"
            full_text = f"   - {prefix} {text}"
            
            # textwrap을 이용해 가로폭 초과 에러 방지
            wrapped_lines = textwrap.wrap(full_text, width=45)
            for line in wrapped_lines:
                if line != wrapped_lines[0]:
                    line = "      " + line
                pdf.cell(0, 7, line, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)

    # 섹션 2: 추천 기출문제
    pdf.set_font("NanumGothic", size=14)
    pdf.cell(0, 12, "2. 약점 보완용 추천 기출문제", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("NanumGothic", size=11)

    for node, n_count in node_counts.most_common():
        candidate_q = [q['id'].replace('_', ' ') for q in db_data if node in q['nodes'] and not any(wq['id'] == q['id'] for wq in w_qs)]
        if candidate_q:
            random.shuffle(candidate_q)
            rec_text = ", ".join(candidate_q[:3])
            full_rec_text = f"💊 [{node}] 보완 추천: {rec_text}"
            
            wrapped_rec = textwrap.wrap(full_rec_text, width=45)
            for line in wrapped_rec:
                if line != wrapped_rec[0]:
                    line = "      " + line
                pdf.cell(0, 8, line, new_x="LMARGIN", new_y="NEXT")
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        pdf.output(tmp.name)
        with open(tmp.name, "rb") as f:
            pdf_bytes = f.read()
            
    return pdf_bytes

# --- 3. 로그인 및 세션 관리 ---
if 'academy_code' not in st.session_state:
    st.set_page_config(page_title="EDGE MVP1", layout="centered")
    st.title("EDGE 약점 진단 (MVP1)")
    academy_input = st.text_input("학원 코드를 입력하세요", type="password")
    if st.button("시스템 접속"):
        if academy_input.strip():
            st.session_state.academy_code = academy_input.strip()
            st.rerun()
    st.stop()

academy_code = st.session_state.academy_code
full_db = load_full_db_from_sheets()

if academy_code not in full_db:
    full_db[academy_code] = {}
    save_full_db_to_sheets(full_db)

students_db = full_db[academy_code]

# --- 4. 기출문제 원본 DB 로드 ---
@st.cache_data
def load_exam_db():
    with open("edge_db_full_2022.json", "r", encoding="utf-8") as f:
        return json.load(f)

db_data = load_exam_db()
exam_names = sorted(list(set('_'.join(item['id'].split('_')[:-1]) for item in db_data)))

# --- 5. 사이드바: 학생 관리 ---
st.sidebar.title(f"🏢 코드: {academy_code}")
if st.sidebar.button("로그아웃"):
    st.session_state.clear()
    st.rerun()

st.sidebar.markdown("---")
new_student = st.sidebar.text_input("학생 추가")
if st.sidebar.button("추가 완료"):
    if new_student and new_student not in students_db:
        full_db[academy_code][new_student] = {'wrong_questions': [], 'exams': []}
        save_full_db_to_sheets(full_db)
        st.session_state.current_student_name = new_student
        st.rerun()

student_list = list(students_db.keys())
if student_list:
    current_student = st.sidebar.selectbox("학생 선택", student_list, 
                                          index=student_list.index(st.session_state.get('current_student_name', student_list[0])) if st.session_state.get('current_student_name') in student_list else 0)
    st.session_state.current_student_name = current_student
    if st.sidebar.button("🚨 학생 삭제"):
        del full_db[academy_code][current_student]
        save_full_db_to_sheets(full_db)
        st.session_state.current_student_name = None
        st.rerun()
else:
    current_student = None

# --- 6. 메인 로직 ---
st.title("EDGE 약점 진단 시스템")

if current_student:
    tab1, tab2 = st.tabs(["📝 오답 입력", "📊 분석 리포트"])

    with tab1:
        st.subheader(f"{current_student} 오답 기록")
        selected_exam = st.selectbox("시험지 선택", exam_names)
        exam_questions = [q for q in db_data if '_'.join(q['id'].split('_')[:-1]) == selected_exam]
        
        cols = st.columns(5)
        wrong_answers = []
        for i, q in enumerate(exam_questions):
            q_num = q['id'].split('_')[-1]
            if cols[i % 5].checkbox(q_num, key=f"q_{selected_exam}_{q_num}"):
                wrong_answers.append(q)
        
        if st.button("구글 시트에 저장"):
            if wrong_answers:
                full_db[academy_code][current_student]['wrong_questions'].extend(wrong_answers)
                if selected_exam not in full_db[academy_code][current_student]['exams']:
                    full_db[academy_code][current_student]['exams'].append(selected_exam)
                save_full_db_to_sheets(full_db)
                st.success("데이터베이스 저장이 완료되었습니다.")
                st.rerun()

    with tab2:
        s_data = students_db[current_student]
        w_qs = s_data.get('wrong_questions', [])
        if not w_qs:
            st.info("기록된 오답이 없습니다.")
        else:
            all_nodes = [n for q in w_qs for n in q['nodes']]
            node_counts = Counter(all_nodes)
            
            for node, n_count in node_counts.most_common():
                st.error(f"### 📍 {node} ({n_count}회)")
                g_edges = [generalize_edge_text(e) for q in w_qs if node in q['nodes'] for e in q['edges']]
                edge_counts = Counter(g_edges)
                for text, count in edge_counts.most_common():
                    prefix = f"🔥 [중복 {count}회]" if count >= 2 else "[1회]"
                    st.markdown(f"- {prefix} {text}")
                st.markdown("---")

            # PDF 출력 버튼
            if st.button("📄 학부모 상담용 PDF 생성"):
                with st.spinner('구글 시트 데이터 기반 리포트 생성 중...'):
                    pdf_data = create_pdf_report(current_student, w_qs, db_data, node_counts)
                    if pdf_data:
                        st.download_button(
                            label="클릭하여 리포트 다운로드",
                            data=pdf_data,
                            file_name=f"EDGE_리포트_{current_student}.pdf",
                            mime="application/pdf"
                        )