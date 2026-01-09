import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client, Client
from groq import Groq
from PyPDF2 import PdfReader
import streamlit_authenticator as stauth

# --- 1. CONFIGURAZIONE ---
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥", layout="wide")

# --- 2. CONNESSIONE SUPABASE ---
try:
    URL_DB = st.secrets["SUPABASE_URL"]
    KEY_DB = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(URL_DB, KEY_DB)
except Exception as e:
    st.error("Errore: Credenziali Supabase non trovate nei Secrets!")
    st.stop()

# --- 3. FUNZIONI DATABASE ---
def carica_credenziali():
    try:
        res = supabase.table("profiles").select("*").execute()
        credenziali = {"usernames": {}}
        for u in res.data:
            credenziali["usernames"][u["username"]] = {"name": u["name"], "password": u["password"]}
        return credenziali
    except: return {"usernames": {}}

def salva_nuovo_utente(username, name, password_hash):
    try:
        supabase.table("profiles").insert({"username": str(username), "name": str(name), "password": str(password_hash)}).execute()
    except: pass

def salva_benessere(username, fatica, sonno):
    try:
        # PROTEZIONE 405: Trasformiamo in numeri puri Python
        payload = {
            "user_id": str(username),
            "fatica": float(fatica),
            "ore_sonno": float(sonno)
        }
        supabase.table("wellness").insert(payload).execute()
        return True
    except Exception as e:
        st.error(f"Errore salvataggio: {e}")
        return False

def carica_dati_benessere(username):
    try:
        res = supabase.table("wellness").select("*").filter("user_id", "eq", username).order("created_at").execute()
        df = pd.DataFrame(res.data)
        if not df.empty:
            df['fatica'] = pd.to_numeric(df['fatica'])
            df['ore_sonno'] = pd.to_numeric(df['ore_sonno'])
        return df
    except: return pd.DataFrame()

# --- 4. AUTENTICAZIONE ---
if "config" not in st.session_state:
    st.session_state.config = carica_credenziali()

auth = stauth.Authenticate(st.session_state.config, "ts_cookie", "auth_key", 30)

if not st.session_state.get("authentication_status"):
    t1, t2 = st.tabs(["Accedi 🔑", "Iscriviti 📝"])
    with t2:
        res = auth.register_user(pre_authorized=None)
        if res:
            u, info = res
            if u:
                salva_nuovo_utente(u, info['name'], info['password'])
                st.success('Registrato! Accedi ora.')
                st.session_state.config = carica_credenziali()
    with t1:
        auth.login()
else:
    # --- 5. AREA RISERVATA ---
    if "messages" not in st.session_state: st.session_state.messages = []
    if "testo_turno" not in st.session_state: st.session_state.testo_turno = ""

    with st.sidebar:
        st.title("👨‍⚕️ Menù")
        st.write(f"In servizio: **{st.session_state['name']}**")
        auth.logout('Esci', 'sidebar')
        st.divider()
        pdf = st.file_uploader("📂 Carica Turno PDF", type="pdf")
        if pdf:
            reader = PdfReader(pdf)
            st.session_state.testo_turno = "".
