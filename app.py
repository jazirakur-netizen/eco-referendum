import streamlit as st
import pandas as pd
import time
import random

# Беттің дизайнын орнату
st.set_page_config(page_title="Қоғамдық талқылау", page_icon="⚖️", layout="centered")

# CSS арқылы әдемі дизайн қосу
st.markdown("""
<style>
    .admin-box {
        background-color: #fce4ec;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #e91e63;
        margin-bottom: 20px;
    }
    .question-box {
        background-color: #ebf5fb;
        padding: 30px;
        border-radius: 10px;
        border-top: 5px solid #3498db;
        text-align: center;
        margin-bottom: 30px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .question-text {
        font-family: 'Times New Roman', Times, serif;
        font-size: 24px;
        color: #1e293b;
        margin-bottom: 10px;
    }
    .doc-id {
        color: #3498db;
        font-weight: bold;
        font-size: 14px;
        margin-bottom: 15px;
    }
    div.stButton > button:first-child {
        width: 100%;
        height: 60px;
        font-size: 20px;
        font-weight: bold;
        border-radius: 10px;
    }
    /* Жақтаймын батырмасы (Көк) */
    div[data-testid="column"]:nth-of-type(1) div.stButton > button:first-child {
        background-color: #1e293b;
        color: white;
    }
    /* Қарсымын батырмасы (Қызыл) */
    div[data-testid="column"]:nth-of-type(2) div.stButton > button:first-child {
        background-color: white;
        color: #b91c1c;
        border: 2px solid #b91c1c;
    }
</style>
""", unsafe_allow_html=True)


# --- ДЕРЕКТЕРДІ САҚТАУ (Session State) ---
if 'current_question' not in st.session_state:
    st.session_state['current_question'] = "«Болашақ ұрпақ мүддесін қорғау мақсатында ауыл аумағындағы барлық сауда нүктелерінде полиэтилен пакеттерді қолдануға толықтай тыйым салу туралы»"
if 'doc_number' not in st.session_state:
    st.session_state['doc_number'] = "Қаулы жобасы №2026/10-ЭК"
if 'votes_pro' not in st.session_state:
    st.session_state['votes_pro'] = 0
if 'votes_con' not in st.session_state:
    st.session_state['votes_con'] = 0
if 'has_voted' not in st.session_state:
    st.session_state['has_voted'] = False


# --- БҮЙІРЛІК ТАҚТА (АДМИН ПАНЕЛЬ) - ҚҰПИЯ СӨЗБЕН ҚОРҒАЛҒАН ---
with st.sidebar:
    st.markdown("### ⚙️ Мұғалім (Админ) панелі")
    
    # ҚҰПИЯ СӨЗ СҰРАЙТЫН ЖЕР
    password = st.text_input("Басқару үшін құпия сөзді енгізіңіз:", type="password")
    
    # Егер пароль дұрыс болса (қазір пароль: 2026)
    if password == "2026":
        st.success("Рұқсат етілді!")
        st.write("Осы жерден талқылауға шығарылатын жаңа мәселені енгізіңіз:")
        
        new_doc_num = st.text_input("Қаулы нөмірі:", st.session_state['doc_number'])
        new_question = st.text_area("Жаңа экологиялық мәселе (сұрақ):", st.session_state['current_question'], height=150)
        
        if st.button("🔄 Жаңа сауалнаманы бастау"):
            st.session_state['current_question'] = new_question
            st.session_state['doc_number'] = new_doc_num
            # Сауалнаманы нөлдеу
            st.session_state['votes_pro'] = 0
            st.session_state['votes_con'] = 0
            st.session_state['has_voted'] = False
            st.success("Жаңа мәселе сәтті жарияланды!")
            time.sleep(1)
            st.rerun()
            
    # Егер пароль қате болса
    elif password != "":
        st.error("Құпия сөз қате!")
    # Басында бос тұрғанда
    else:
        st.info("Бұл бөлім тек басқарушыға (мұғалімге) арналған.")


# --- НЕГІЗГІ ЭКРАН (ОҚУШЫЛАРҒА КӨРІНЕТІН БӨЛІГІ) ---
st.markdown("<h2 style='text-align: center;'>ЭЛЕКТРОНДЫ ДАУЫС БЕРУ ЖҮЙЕСІ ⚖️</h2>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: gray;'>Жастардың қоғамдық талқылау порталы</p>", unsafe_allow_html=True)

# Сұрақты көрсету
st.markdown(f"""
<div class="question-box">
    <div class="doc-id">{st.session_state['doc_number']}</div>
    <div class="question-text">{st.session_state['current_question']}</div>
</div>
""", unsafe_allow_html=True)


# Дауыс беру пульті
if not st.session_state['has_voted']:
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("ЖАҚТАЙМЫН 👍"):
            with st.spinner("Серверге тіркелуде..."):
                time.sleep(1.5)
            st.session_state['votes_pro'] += 1
            st.session_state['has_voted'] = True
            st.rerun()
            
    with col2:
        if st.button("ҚАРСЫМЫН 👎"):
            with st.spinner("Серверге тіркелуде..."):
                time.sleep(1.5)
            st.session_state['votes_con'] += 1
            st.session_state['has_voted'] = True
            st.rerun()

# Дауыс беріп қойғаннан кейін статистиканы көрсету
else:
    st.success("✅ Дауысыңыз қабылданды! Мөр басылды.")
    
    st.markdown("### Дауыс беру қорытындысы:")
    
    total_votes = st.session_state['votes_pro'] + st.session_state['votes_con']
    
    if total_votes > 0:
        pro_percent = round((st.session_state['votes_pro'] / total_votes) * 100)
        con_percent = 100 - pro_percent
        
        st.write(f"**Жақтағандар:** {st.session_state['votes_pro']} адам ({pro_percent}%)")
        st.progress(pro_percent / 100)
        
        st.write(f"**Қарсы болғандар:** {st.session_state['votes_con']} адам ({con_percent}%)")
        st.progress(con_percent / 100)
        
        st.info(f"Жалпы қатысқандар: {total_votes} адам. Идентификатор: KZ-{random.randint(10000, 99999)}")
