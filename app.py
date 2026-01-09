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
        .stButton>button { border-radius: 20px; font-weight: bold; width: 100%; height: 3em; }
        .stChatMessage { border-radius: 15px; border: 1px solid #f0f2f6; }
        [data-testid="stExpander"] { border-radius: 15px; background-color: #f8f9fa; }
    </style>
""", unsafe_allow_html=True)

# --- 2. CONNESSIONE SUPABASE ---
try:
    URL_DB = st.secrets["SUPABASE_URL"]
    KEY_DB = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(URL_DB, KEY_DB)
except Exception as e:
    st.error("Errore: Credenziali Supabase mancanti!")
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
    try:
        payload = {
            "user_id": str(username),
            "fatica": int(fatica),
            "ore_sonno": float(sonno)
        }
        supabase.table("wellness").insert(payload).execute()
        return True
    except Exception as e:
        st.error(f"Errore database: {e}")
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
    # --- 5. DASHBOARD (LOGGATO) ---
    if "messages" not in st.session_state: st.session_state.messages = []
    if "testo_turno" not in st.session_state: st.session_state.testo_turno = ""

    with st.sidebar:
        st.title("👨‍⚕️ Menù")
        st.write(f"In servizio: **{st.session_state['name']}**")
        if authenticator.logout('Esci', 'sidebar'): 
            st.session_state.messages = []
            st.rerun()
        st.divider()
        file_pdf = st.file_uploader("📂 Carica Turno PDF", type="pdf")
        if file_pdf:
            reader = PdfReader(file_pdf)
            st.session_state.testo_turno = "".join([p.extract_text() or "" for p in reader.pages])
            st.success("Turno analizzato!")

    st.title("🏥 TurnoSano AI")

    # REGISTRAZIONE DATI
    with st.expander("📝 Diario del Benessere"):
        c1, c2 = st.columns(2)
        f_val = c1.slider("Livello Fatica (1-10)", 1, 10, 5)
        s_val = c2.number_input("Ore di Sonno", 0.0, 20.0, 7.0, step=0.5)
        if st.button("💾 Salva Dati"):
            if salva_benessere(st.session_state['username'], f_val, s_val):
                st.success("Dati salvati!")
                st.rerun()

    # GRAFICI
    df = carica_dati_benessere(st.session_state['username'])
    if not df.empty:
        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(px.line(df, x='created_at', y='fatica', title="Andamento Fatica", markers=True), use_container_width=True)
        with col2:
            st.plotly_chart(px.bar(df, x='created_at', y='ore_sonno', title="Ore Sonno"), use_container_width=True)
    else:
        st.info("Nessun dato presente. Inizia a registrare!")

    # --- 6. COACH AI (GROQ) ---
    st.divider()
    st.subheader("💬 Coach AI")
    
    if "GROQ_API_KEY" in st.secrets:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        
        def chiedi_ai(prompt):
            st.session_state.messages.append({"role": "user", "content": prompt})
            ctx = f"Sei TurnoSano AI, coach per infermieri. Utente: {st.session_state['name']}."
            if st.session_state.testo_turno:
                ctx += f" Contesto turno: {st.session_state.testo_turno[:500]}"
            
            try:
                res = client.chat.completions.create(
                    messages=[{"role": "system", "content": ctx}] + st.session_state.messages,
                    model="llama-3.1-8b-instant",
                )
                st.session_state.messages.append({"role": "assistant", "content": res.choices[0].message.content})
            except Exception as e: st.error(f"Errore AI: {e}")

        # TASTI RAPIDI
        tr1, tr2, tr3 = st.columns(3)
        prompt_rapido = None
        if tr1.button("🌙 SOS Notte"): 
            prompt_rapido = "Consigli per affrontare il turno di notte."
        if tr2.button("🥗 Dieta Turnista"): 
            prompt_rapido = "Cosa mangiare per avere energia in turno?"
        if tr3.button("🗑️ Reset Chat"): 
            st.session_state.messages = []
            st.rerun()

        chat_in = st.chat_input("Chiedi al Coach...")
        final_query = chat_in or prompt_rapido
        
        if final_query:
            chiedi_ai(final_query)

        for m in st.session_state.messages:
            with st.chat_message(m["role"]):
                st.markdown(m["content
