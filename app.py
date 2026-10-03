import hmac
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import storage as db
from reporting import LABELS, csv_bytes, summary_rows

st.set_page_config(page_title="Эко-референдум", page_icon="🌿", layout="wide")
st.markdown("""<style>
.stApp { background: #f3f7fb; }
.block-container { max-width: 1080px; padding-top: 2.3rem; }
h1, h2, h3 { color: #153b60; }
[data-testid="stSidebar"] { background: #e7eff7; }
[data-testid="stMetric"] { background: white; padding: 18px; border-radius: 12px;
    border-top: 3px solid #19866b; }
.portal { background: #123958; color: white; border-radius: 14px; padding: 25px 30px;
    border-bottom: 5px solid #29b798; margin-bottom: 24px; }
.portal h1 { color: white; font-size: 2rem; margin: 0; }
.portal p { color: #d4e7f4; margin: 8px 0 0; }
div.stButton > button, div.stFormSubmitButton > button { min-height: 46px; }
</style>
<div class="portal"><h1>ЭКО-РЕФЕРЕНДУМ</h1>
<p>Бүгінгі таңдау — болашақ ұрпақ алдындағы жауапкершілік</p></div>""", unsafe_allow_html=True)
st.caption("Мектепішілік ғылыми жоба • Оқу мақсатындағы қоғамдық талқылау • Мемлекеттік қызмет емес")


def setting(name):
    try:
        return str(st.secrets.get(name, ""))
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        return ""


@st.cache_resource
def connect(url):
    engine = db.open_engine(url)
    db.initialize(engine)
    return engine


def fail_database():
    st.error("Дерекқормен байланыс үзілді. Әрекеттің орындалғанын тексеру үшін бетті жаңартыңыз. "
             "Дауыс жіберген болсаңыз, сол кодпен қайта көріңіз: бір код екі рет есептелмейді.")
    st.stop()


def call(function, *args):
    try:
        return function(*args)
    except (db.VoteError, ValueError) as error:
        st.warning(str(error))
        st.stop()
    except Exception:
        # Connection strings, passwords and SQL parameters must never reach the page.
        fail_database()


url, admin_password = setting("DATABASE_URL"), setting("ADMIN_PASSWORD")
if not url or len(admin_password) < 12:
    st.info("Портал бапталуда. Дауыс беру әзірге ашылған жоқ.")
    st.markdown("**Жоба иесіне:** Streamlit → Manage app → Settings → Secrets бөлімінде "
                "`DATABASE_URL` және кемінде 12 таңбалық `ADMIN_PASSWORD` мәндерін енгізіңіз. "
                "Қадамдар репозиторийдегі **SETUP_KZ.md** файлында берілген.")
    st.stop()
try:
    engine = connect(url)
except Exception:
    st.error("Дерекқорға қосылу мүмкін болмады. Жоба иесі байланыс баптауларын тексеруі қажет.")
    st.stop()

with st.sidebar:
    st.subheader("Навигация")
    page = st.radio("Бөлім", ["Дауыс беру", "Мұғалім кабинеті"], label_visibility="collapsed")
    st.divider()
    st.write("**Анонимді қатысу**")
    st.caption("Аты-жөн, телефон, IP мекенжай қолданбаның дауыс кестесіне жазылмайды. "
               "Бірреттік код таңдалған жауаптан бөлек сақталады.")
    st.caption("Кодты басқаға бермеңіз. Әр оқушыға бір код таратылады.")


def poll_label(poll):
    status = "Ашық" if poll["is_open"] else "Аяқталған"
    return f'{poll["document"]} · {poll["title"][:65]} · {status} · {poll["id"][:6]}'


def display_poll(poll):
    st.caption(poll["document"])
    st.subheader(poll["title"])
    if poll["context"]:
        st.write(poll["context"])


def local_date(value):
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(ZoneInfo("Asia/Almaty")).date()


if page == "Дауыс беру":
    active = call(db.list_polls, engine, True)
    if st.button("Сауалнамалар тізімін жаңарту"):
        st.rerun()
    if not active:
        st.info("Қазір ашық сауалнама жоқ. Мұғалім жаңа мәселені жариялаған соң осы бетті жаңартыңыз.")
        st.stop()
    selected = st.selectbox("Дауыс беретін мәселені таңдаңыз", active, format_func=poll_label)
    display_poll(selected)
    st.info("Мәселені оқып, бүгінгі және болашақ ұрпаққа әсерін салыстырыңыз. "
            "Өз көзқарасыңызды таңдаңыз — дұрыс не бұрыс жауап үшін баға қойылмайды.")
    if st.session_state.get("vote_success") == selected["id"]:
        st.success("Дауысыңыз ортақ дерекқорға сақталды. Қатысқаныңызға рақмет!")
    st.caption("Мұғалімнен алған бірреттік кодты енгізіңіз. Пікірге өзіңіздің не өзгенің аты-жөнін жазбаңыз.")
    with st.form(f'vote_{selected["id"]}', clear_on_submit=True):
        code = st.text_input("Бірреттік код", max_chars=40, placeholder="XXXX-XXXX-XXXX-XXXX")
        choice = st.radio("Сіздің шешіміңіз", ["pro", "con"], format_func=LABELS.get, index=None)
        reason = st.text_area("Неліктен осылай таңдадыңыз? Болашақ ұрпаққа әсері қандай? (міндетті емес)",
                              max_chars=1500)
        submitted = st.form_submit_button("ДАУЫСЫМДЫ ЖІБЕРУ", type="primary")
    if submitted:
        if choice is None:
            st.warning("Алдымен жауап нұсқасын таңдаңыз.")
        else:
            call(db.cast_vote, engine, selected["id"], code, choice, reason)
            st.session_state["vote_success"] = selected["id"]
            st.rerun()
    st.caption("Нәтижелерді мұғалім қорытынды талқылауда көрсетеді. "
               "Сайт атаулы тізім жүргізбейді; хостинг қызметінің техникалық журналдары бөлек болуы мүмкін.")
    st.stop()

# Recheck the password on each run; nothing privileged renders before this gate.
st.header("Мұғалім кабинеті")
st.caption("Дауыс беру нәтижелері мен оқушылардың пікірлері тек осы бөлімде көрсетіледі.")
if st.session_state.get("admin_value") != admin_password:
    with st.form("login", clear_on_submit=True):
        password = st.text_input("Құпия сөз", type="password")
        login = st.form_submit_button("Кіру", type="primary")
    if login:
        now = time.monotonic()
        if now < st.session_state.get("login_after", 0):
            st.warning("Қайталап көру үшін біраз күтіңіз.")
        elif hmac.compare_digest(password.encode(), admin_password.encode()):
            st.session_state["admin_value"] = admin_password
            st.session_state["login_attempts"] = 0
            st.rerun()
        else:
            attempts = st.session_state.get("login_attempts", 0) + 1
            st.session_state["login_attempts"] = attempts
            st.session_state["login_after"] = now + min(60, 2 ** min(attempts, 6))
            st.error("Құпия сөз қате.")
    st.stop()

if st.button("Кабинеттен шығу"):
    for key in ("admin_value", "generated_codes"):
        st.session_state.pop(key, None)
    st.rerun()

with st.expander("＋ Жаңа сауалнама ашу"):
    with st.form("create_poll", clear_on_submit=True):
        document = st.text_input("Сауалнама нөмірі / белгісі", value="ЭКО-2026/01", max_chars=120)
        title = st.text_area("Дауыс беруге ұсынылатын мәселе", max_chars=2000,
            placeholder="Мектеп шараларында бірреттік ыдысты көпреттік ыдысқа ауыстыруды қолдайсыз ба?")
        context = st.text_area("Түсіндірме: баламалар, пайдасы, шығыны және болашаққа әсері", max_chars=5000)
        create = st.form_submit_button("Сауалнаманы жариялау", type="primary")
    if create:
        call(db.create_poll, engine, title, document, context)
        st.session_state["admin_notice"] = "Жаңа сауалнама жарияланды. Оған бірреттік кодтар жасаңыз."
        st.rerun()
if st.session_state.get("admin_notice"):
    st.success(st.session_state.pop("admin_notice"))

all_polls = call(db.list_polls, engine)
if not all_polls:
    st.info("Алдымен жоғарыдағы бөлімнен сауалнама ашыңыз.")
    st.stop()

status = st.selectbox("Күйі бойынша іріктеу", ["Барлығы", "Ашық", "Аяқталған"])
first_date = min(local_date(p["created_at"]) for p in all_polls)
dates = st.date_input("Сауалнама ашылған күндер аралығы", (first_date, datetime.now(ZoneInfo("Asia/Almaty")).date()))
filtered = [p for p in all_polls if status == "Барлығы" or p["is_open"] == (status == "Ашық")]
if isinstance(dates, (tuple, list)) and len(dates) == 2:
    filtered = [p for p in filtered if dates[0] <= local_date(p["created_at"]) <= dates[1]]
if not filtered:
    st.info("Бұл сүзгіге сәйкес сауалнама жоқ.")
    st.stop()
poll = st.selectbox("Сауалнама / архив", filtered, format_func=poll_label)
display_poll(poll)
if st.button("Нәтижелерді жаңарту"):
    st.rerun()
counts = call(db.results, engine, poll["id"])
total = sum(counts.values())
issued, used = call(db.code_counts, engine, poll["id"])
cols = st.columns(3)
cols[0].metric("Қабылданған дауыс", total)
cols[1].metric("Жақтағандар", counts["pro"])
cols[2].metric("Қарсы болғандар", counts["con"])
st.caption(f"Жасалған код: {issued} · Қолданылған код: {used}. Код саны қатысушы санына тең болмауы мүмкін.")
rows = summary_rows(counts)
frame = pd.DataFrame(rows)
st.dataframe(frame, hide_index=True, use_container_width=True)
if total:
    st.bar_chart(frame.set_index("Нұсқа")[["Дауыс саны"]], color="#19866b")
    st.write(f'Сауалнамада {total} дауыс тіркелді. Жақтағандар — {counts["pro"]} '
             f'({rows[0]["Үлес (%)"]}%), қарсы болғандар — {counts["con"]} ({rows[1]["Үлес (%)"]}%).')
else:
    st.info("Әзірге дауыс берілген жоқ. Кодтарды таратып, оқушыларға сайт сілтемесін жіберіңіз.")
st.caption("Қорытынды осы сауалнамаға қатысушылардың пікір бағытын сипаттайды. "
           "Көпшілік таңдауы экологиялық салдарды талдаумен бірге қарастырылады.")
export = [{"Сауалнама": poll["document"], "Мәселе": poll["title"],
           "Күйі": "Ашық" if poll["is_open"] else "Аяқталған", **row} for row in rows]
st.download_button("Нәтижелерді CSV жүктеу (Excel үшін)",
    csv_bytes(export, ["Сауалнама", "Мәселе", "Күйі", "Нұсқа", "Дауыс саны", "Үлес (%)"]),
    file_name=f'eco_results_{poll["id"][:8]}.csv', mime="text/csv")

st.subheader("Таңдауды негіздеу: анонимді пікірлер")
comment_filter = st.selectbox("Пікірлерді іріктеу", ["Барлығы", "Жақтаймын", "Қарсымын"])
choice_filter = next((key for key, label in LABELS.items() if label == comment_filter), None)
notes = call(db.comments, engine, poll["id"], choice_filter)
if notes:
    note_rows = [{"Нұсқа": LABELS[n["choice"]], "Пікір": n["reason"], "Саны": n["count"]} for n in notes]
    st.dataframe(pd.DataFrame(note_rows), hide_index=True, use_container_width=True)
    st.download_button("Іріктелген пікірлерді CSV жүктеу", csv_bytes(note_rows, ["Нұсқа", "Пікір", "Саны"]),
                       file_name=f'eco_comments_{poll["id"][:8]}.csv', mime="text/csv")
else:
    st.caption("Бұл санатта жазбаша пікір жоқ.")

if poll["is_open"]:
    with st.expander("Бірреттік кодтарды дайындау"):
        st.write("Кодтарды қағазға шығарып, араластырып таратыңыз. Кімге қай код түскенін жазбаңыз. "
                 "Әр оқушыға бір код беріңіз. Қосымша код жасағанда бұрынғылары жарамды болып қалады.")
        with st.form("issue_codes"):
            count = st.number_input("Код саны", min_value=1, max_value=500, value=30, step=1)
            generate = st.form_submit_button("Кодтарды жасау")
        if generate:
            codes = call(db.issue_codes, engine, poll["id"], int(count))
            st.session_state["generated_codes"] = (poll["id"], codes)
        generated = st.session_state.get("generated_codes")
        if generated and generated[0] == poll["id"]:
            st.warning("Осы топтаманы қазір жүктеп алыңыз. Бет толық қайта ашылғанда кодтардың ашық мәтіні қалмайды.")
            st.download_button("Кодтарды TXT жүктеу", "Сауалнама: " + poll["document"] + "\n\n" +
                "\n".join(generated[1]), file_name=f'eco_codes_{poll["id"][:8]}.txt', mime="text/plain")
    with st.expander("Сауалнаманы аяқтау"):
        st.write("Жаңа дауыс қабылдау тоқтайды. Барлық нәтижелер архивте сақталады.")
        confirm = st.checkbox("Осы сауалнаманы аяқтауды растаймын", key=f'close_{poll["id"]}')
        if st.button("Дауыс беруді аяқтау", disabled=not confirm):
            call(db.close_poll, engine, poll["id"])
            st.rerun()
