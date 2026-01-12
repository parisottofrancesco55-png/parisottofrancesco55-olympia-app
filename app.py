import streamlit as st
import pandas as pd
from supabase import create_client, Client
from groq import Groq
from PyPDF2 import PdfReader
import streamlit_authenticator as stauth

# --- 1. CONFIGURAZIONE ---
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥", layout="centered")

def init_db():
    try:
        url = st.secrets["SUPABASE_URL"].strip().rstrip('/')
        key = st.secrets["SUPABASE_KEY"].strip()
        return create_client(url, key)
    except Exception as e:
        st.error(f"Errore Database: {e}")
        st.stop()

sb = init_db()

def load_users():
    try:
        res = sb.table("profiles").select("*").execute()
        if not res.data:
            return {}
        # Struttura dati richiesta dall'autenticatore
        return {u["username"]: {"name": u["name"], "password": u["password"], "email": u.get("email", "")} for u in res.data}
    except:
        return {}

# Inizializzazione dati
if "user_db" not in st.session_state:
    st.session_state.user_db = load_users()

if "auth_mode" not in st.session_state:
    st.session_state.auth_mode = "login"

# --- 2. AUTENTICAZIONE ---
# Definiamo le credenziali partendo dal DB
credentials = {"usernames": st.session_state.user_db}

auth = stauth.Authenticate(
    credentials,
    "turnosano_cookie",
    "turnosano_key",
    30
)

# --- 3. LOGICA DI NAVIGAZIONE ---
if not st.session_state.get("authentication_status"):
    st.title("🏥 TurnoSano AI")
    
    if st.session_state.auth_mode == "login":
        auth.login(location='main')
        if st.session_state["authentication_status"] is False:
            st.error("Username o password errati.")
        
        st.write("---")
        if st.button("Non hai un account? Iscriviti qui"):
            st.session_state.auth_mode = "iscrizione"
            st.rerun()

    else:
        st.subheader("📝 Registrazione")
        
        # Mostriamo il modulo di registrazione
        # Nota: register_user DEVE essere chiamato fuori da ogni condizione per restare visibile
        result = auth.register_user(location='main', pre_authorization=False)
        
        if result:
            new_email, new_username, new_password = result
            if new_username:
                try:
                    # Salvataggio nel database Supabase
                    sb.table("profiles").insert({
                        "username": str(new_username), 
                        "name": str(new_username), 
                        "password": str(new_password),
                        "email": str(new_email)
                    }).execute()
                    
                    st.success(f"✅ Utente '{new_username}' registrato correttamente!")
                    st.session_state.user_db = load_users() # Aggiorna la lista
                    st.info("Clicca il pulsante sotto per andare al login.")
                except Exception as e:
                    st.error(f"Errore durante il salvataggio: {e}")
        
        st.write("---")
        if st.button("Torna al Login"):
            st.session_state.auth_mode = "login"
            st.rerun()

else:
    # --- 4. APP PRINCIPALE ---
    st.sidebar.title(f"👋 {st.session_state['name']}")
    auth.logout('Esci', 'sidebar')
    
    pdf_file = st.sidebar.file_uploader("Carica Turno (PDF)", type="pdf")
    if pdf_file:
        reader = PdfReader(pdf_file)
        st.session_state.pdf_text = "".join([p.extract_text() for p in reader.pages if p.extract_text()])
        st.sidebar.success("PDF Caricato")

    st.title("🏥 Dashboard Benessere")

    with st.form("wellness_form", clear_on_submit=True):
        f_val = st.slider("Livello Fatica (1-10)", 1, 10, 5)
        s_val = st.number_input("Ore di sonno effettive", 0.0, 24.0, 7.0, step=0.5)
        if st.form_submit_button("Salva Parametri"):
            try:
                sb.table("wellness").insert({
                    "user_id": st.session_state['username'], 
                    "fatica": float(f_val), 
                    "ore_sonno": float(s_val)
                }).execute()
                st.success("Dati salvati!")
                st.rerun()
            except: st.error("Errore salvataggio.")

    # --- 5. COACH SCIENTIFICO ---
    st.divider()
    if "GROQ_API_KEY" in st.secrets:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        
        c1, c2 = st.columns(2)
        q = None
        if c1.button("🌙 Recupero Notte"): q = "Fornisci strategie scientifiche per il post-notte."
        if c2.button("🥗 Dieta Turnisti"): q = "Consigli nutrizionali cronobiologici per turnisti."

        chat_in = st.chat_input("Chiedi un consiglio scientifico...")
        prompt = chat_in or q

        if prompt:
            if "msgs" not in st.session_state: st.session_state.msgs = []
            st.session_state.msgs.append({"role": "user", "content": prompt})
            
            sys_msg = "Sei un esperto in cronobiologia. Fornisci consigli basati su studi scientifici. Non sei un medico."
            res_ai = client.chat.completions.create(
                messages=[{"role": "system", "content": sys_msg}] + st.session_state.msgs,
                model="llama-3.1-8b-instant"
            )
            st.session_state.msgs.append({"role": "assistant", "content": res_ai.choices[0].message.content})

        if "msgs" in st.session_state:
            for m in st.session_state.msgs:
                with st.chat_message(m["role"]): st.write(m["content"])
