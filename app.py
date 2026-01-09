import streamlit as st
import pandas as pd
from supabase import create_client, Client
from groq import Groq
from PyPDF2 import PdfReader
import streamlit_authenticator as stauth

# 1. SETUP
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥")

try:
    sb = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except:
    st.error("Errore Secrets!")
    st.stop()

# 2. FUNZIONI
def get_auth():
    try:
        r = sb.table("profiles").select("*").execute()
        return {"usernames": {u["username"]: {"name": u["name"], "password": u["password"]} for u in r.data}}
    except: return {"usernames": {}}

def save_data(u, f, s):
    try:
        sb.table("wellness").insert({"user_id": str(u), "fatica": int(f), "ore_sonno": float(s)}).execute()
        return True
    except Exception as e:
        st.error(f"Errore: {e}")
        return False

# 3. AUTH
if "config" not in st.session_state: st.session_state.config = get_auth()
auth = stauth.Authenticate(st.session_state.config, "ts_cookie", "key", 30)

if not st.session_state.get("authentication_status"):
    t1, t2 = st.tabs(["Accedi", "Iscriviti"])
    with t2:
        res = auth.register_user(pre_authorized=None)
        if res and res[0]:
            sb.table("profiles").insert({"username": str(res[0]), "name": str(res[1]['name']), "password": str(res[1]['password'])}).execute()
            st.success("Registrato!")
    with t1: auth.login()
else:
    # 4. DASHBOARD
    if "msgs" not in st.session_state: st.session_state.msgs = []
    if "txt" not in st.session_state: st.session_state.txt = ""

    st.sidebar.title("👨‍⚕️ Menù")
    st.sidebar.write(f"Utente: {st.session_state['name']}")
    auth.logout('Esci', 'sidebar')
    
    pdf = st.sidebar.file_uploader("Carica Turno (PDF)", type="pdf")
    if pdf:
        r = PdfReader(pdf)
        st.session_state.txt = "".join([p.extract_text() for p in r.pages if p.extract_text()])
        st.sidebar.success("PDF caricato")

    st.title("🏥 TurnoSano AI")

    with st.form("diario"):
        st.subheader("📝 Diario Giornaliero")
        f = st.slider("Fatica (1-10)", 1, 10, 5)
        s = st.number_input("Ore Sonno", 0.0, 20.0, 7.0)
        if st.form_submit_button("Salva Parametri"):
            if save_data(st.session_state['username'], f, s):
                st.success("Dati salvati!")

    with st.expander("📂 Storico Inserimenti"):
        res = sb.table("wellness").select("*").filter("user_id", "eq", st.session_state['username']).order("created_at", desc=True).limit(10).execute()
        if res.data: st.table(res.data)

    # 5. COACH AI
    st.divider()
    st.subheader("💬 Coach AI")
    if "GROQ_API_KEY" in st.secrets:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        
        c1, c2, c3 = st.columns(3)
        p_rapido = None
        if c1.button("🌙 SOS Notte"): p_rapido = "Consigli per la notte"
        if c2.button("🥗 Dieta"): p_rapido = "Cosa mangiare in turno?"
        if c3.button("🗑️ Reset"):
            st.session_state.msgs = []
            st.rerun()

        prompt = st.chat_input("Scrivi qui...") or p_rapido
        if prompt:
            st.session_state.msgs.append({"role": "user", "content": prompt})
            ctx = f"Sei un coach per infermieri. Utente: {st.session_state['name']}. Turno: {st.session_state.txt[:300]}"
            chat = client.chat.completions.create(
                messages=[{"role": "system", "content": ctx}] + st.session_state.msgs,
                model="llama-3.1-8b-instant"
            )
            st.session_state.msgs.append({"role": "assistant", "content": chat.choices[0].message.content})

        for m in st.session_state.msgs:
            with st.chat_message(m["role"]): st.write(m["content"])
    else:
        st.warning("Configura GROQ_API_KEY")
