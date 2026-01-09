import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client, Client
from groq import Groq
from PyPDF2 import PdfReader
import streamlit_authenticator as stauth

# 1. CONFIGURAZIONE PAGINA (Prima istruzione)
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥", layout="wide")

# 2. DESIGN MOBILE & PWA (Look App Vera)
st.markdown("""
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        .stApp { bottom: 0; }
        .stButton>button { border-radius: 20px; height: 3em; width: 100%; font-weight: bold; }
        .stChatMessage { border-radius: 15px; }
    </style>
""", unsafe_allow_html=True)

# --- 3. CONNESSIONE SUPABASE ---
try:
    URL_DB = st.secrets["SUPABASE_URL"]
    KEY_DB = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(URL_DB, KEY_DB)
except Exception as e:
    st.error("Configura SUPABASE_URL e SUPABASE_KEY nei Secrets!")
    st.stop()

# --- 4. FUNZIONI DATABASE ---
def carica_credenziali():
    try:
        res = supabase.table("profiles").select("*").execute()
        credenziali = {"usernames": {}}
        for u in res.data:
            credenziali["usernames"][u["username"]] = {"name": u["name"], "password": u["password"]}
        return credenziali
    except: return {"usernames": {}}

def salva_nuovo_utente(username, name, password_hash):
    supabase.table("profiles").insert({"username": username, "name": name, "password": password_hash}).execute()

def salva_benessere(username, fatica, sonno):
    supabase.table("wellness").insert({"user_id": username, "fatica": fatica, "ore_sonno": sonno}).execute()

def carica_dati_benessere(username):
    res = supabase.table("wellness").select("*").filter("user_id", "eq", username).order("created_at").execute()
    return pd.DataFrame(res.data)

# --- 5. GESTIONE AUTENTICAZIONE ---
if "config" not in st.session_state:
    st.session_state.config = carica_credenziali()

authenticator = stauth.Authenticate(
    st.session_state.config,
    "turnosano_cookie",
    "auth_key",
    cookie_expiry_days=30
)

if not st.session_state.get("authentication_status"):
    t1, t2 = st.tabs(["Accedi 🔑", "Iscriviti 📝"])
    with t2:
        try:
            new_user = authenticator.register_user(pre_authorized=None)
            if new_user:
                u, info = new_user
                salva_nuovo_utente(u, info['name'], info['password'])
                st.success('Registrato! Ora puoi accedere.')
                st.session_state.config = carica_credenziali()
        except Exception as e: st.error(f"Errore: {e}")
    with t1:
        authenticator.login()
        if st.session_state.get("authentication_status"): st.rerun()

# --- 6. AREA RISERVATA (LOGGATO) ---
else:
    # Setup Memoria
    if "messages" not in st.session_state: st.session_state.messages = []
    if "testo_turno" not in st.session_state: st.session_state.testo_turno = ""

    # Sidebar
    with st.sidebar:
        st.write(f"In servizio: **{st.session_state['name']}** 👋")
        if authenticator.logout('Esci', 'sidebar'): st.rerun()
        st.divider()
        file_pdf = st.file_uploader("📂 Carica Turno PDF", type="pdf")
        if file_pdf:
            reader = PdfReader(file_pdf)
            st.session_state.testo_turno = "".join([p.extract_text() or "" for p in reader.pages])
            st.success("Turno analizzato!")

    st.title("🏥 TurnoSano Dashboard")

    # --- INPUT BENESSERE ---
    with st.expander("📝 Come stai oggi? (Registra dati)"):
        c1, c2 = st.columns(2)
        f_val = c1.slider("Fatica (1-10)", 1, 10, 5)
        s_val = c2.number_input("Ore Sonno", 0.0, 15.0, 7.0)
        if st.button("Salva Dati Giornalieri"):
            salva_benessere(st.session_state['username'], f_val, s_val)
            st.success("Dati salvati!")
            st.rerun()

    # --- GRAFICI ---
    df = carica_dati_benessere(st.session_state['username'])
    if not df.empty:
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            fig_f = px.line(df, x='created_at', y='fatica', title="Andamento Fatica", markers=True)
            st.plotly_chart(fig_f, use_container_width=True)
        with col_g2:
            fig_s = px.bar(df, x='created_at', y='ore_sonno', title="Ore Sonno")
            st.plotly_chart(fig_s, use_container_width=True)
    else:
        st.info("Registra il tuo stato per vedere i grafici.")

    # --- CHAT AI ---
    st.divider()
    st.subheader("💬 Coach TurnoSano AI")
    
    # Tasti Rapidi
    tr1, tr2, tr3 = st.columns(3)
    p_rapido = None
    if tr1.button("🌙 SOS Notte"): p_rapido = "Consigli per turno di notte."
    if tr2.button("🥗 Dieta"): p_rapido = "Cosa mangiare stasera?"
    if tr3.button("🧘 Stress"): p_rapido = "Esercizio relax rapido."

    try:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
    except:
        st.error("Manca GROQ_API_KEY nei Secrets!")
        st.stop()

    prompt = st.chat_input("Chiedi al Coach...")
    if p_rapido: prompt = p_rapido

    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        sys_msg = f"Sei TurnoSano AI, coach per l'infermiere {st.session_state['name']}."
        if st.session_state.testo_turno:
            sys_msg += f"\nTurno attuale: {st.session_state.testo_turno}"
        
        res = client.chat.completions.create(
            messages=[{"role": "system", "content": sys_msg}] + st.session_state.messages,
            model="llama-3.1-8b-instant",
        )
        st.session_state.messages.append({"role": "assistant", "content": res.choices[0].message.content})

    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
