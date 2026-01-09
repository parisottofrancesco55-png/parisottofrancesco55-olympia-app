import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client, Client
from groq import Groq
from PyPDF2 import PdfReader
import streamlit_authenticator as stauth

# --- 1. CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥", layout="wide")

st.markdown("""
    <style>
        .stButton>button { border-radius: 20px; font-weight: bold; width: 100%; height: 3em; background-color: #007bff; color: white; }
        .stChatMessage { border-radius: 15px; }
        [data-testid="stExpander"] { border-radius: 15px; background-color: #f8f9fa; }
    </style>
""", unsafe_allow_html=True)

# --- 2. CONNESSIONE SUPABASE ---
try:
    URL_DB = st.secrets["SUPABASE_URL"]
    KEY_DB = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(URL_DB, KEY_DB)
except Exception as e:
    st.error("Errore: Credenziali Supabase mancanti nei Secrets!")
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
        supabase.table("profiles").insert({
            "username": str(username), 
            "name": str(name), 
            "password": str(password_hash)
        }).execute()
    except Exception as e: st.error(f"Errore registrazione: {e}")

def salva_benessere(username, fatica, sonno):
    """ RISOLUZIONE ERRORE 405: Converte in tipi nativi Python """
    try:
        payload = {
            "user_id": str(username),
            "fatica": int(fatica),
            "ore_sonno": float(sonno)
        }
        supabase.table("wellness").insert(payload).execute()
        return True
    except Exception as e:
        st.error(f"Errore tecnico: {e}")
        return False

def carica_dati_benessere(username):
    try:
        res = supabase.table("wellness").select("*").filter("user_id", "eq", username).order("created_at").execute()
        return pd.DataFrame(res.data)
    except: return pd.DataFrame()

# --- 4. AUTENTICAZIONE ---
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
            res_reg = authenticator.register_user(pre_authorized=None)
            if res_reg:
                username, user_info = res_reg
                if username:
                    salva_nuovo_utente(username, user_info['name'], user_info['password'])
                    st.success('Registrazione completata! Accedi ora.')
                    st.session_state.config = carica_credenziali()
        except Exception as e: st.error(f"Errore: {e}")
            
    with t1:
        authenticator.login()
        if st.session_state.get("authentication_status"): st.rerun()

else:
    # --- 5. DASHBOARD ---
    if "messages" not in st.session_state: st.session_state.messages = []
    if "testo_turno" not in st.
