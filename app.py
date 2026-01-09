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
    st.error("Errore Secrets Supabase!")
    st.stop()

# --- 3. FUNZIONI DB ---
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
        payload = {"user_id": str(username), "fatica": int(fatica), "ore_sonno": float(sonno)}
        supabase.table("wellness").insert(payload).execute()
        return True
    except Exception as e:
        st.error(f"Errore DB: {e}")
        return False

def carica_dati_benessere(username):
    try:
        res = supabase.table("wellness").select("*").filter("user_id", "eq", username).order("created_at").execute()
        return pd.DataFrame(res.data)
    except: return pd.DataFrame()

# --- 4. AUTENTICAZIONE ---
if "config" not in st.session_state:
    st.session_state.config = carica_credenziali()

authenticator = stauth.Authenticate(st.session_state.config, "turnosano_cookie", "auth_key", cookie_expiry_days=30)

if not st.session_state.get("authentication_status"):
    t1, t2 = st.tabs(["Accedi", "Iscriviti"])
    with t2:
        res_reg = authenticator.register_user(pre_authorized=None)
        if res_reg:
            u, info = res_reg
            if u:
                salva_nuovo_utente(u, info['name'], info['password'])
                st.success('Registrato! Accedi ora.')
                st.session_state.config = carica_credenziali()
