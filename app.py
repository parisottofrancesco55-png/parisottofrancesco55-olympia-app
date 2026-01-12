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

# Recupero utenti centralizzato
def load_users():
    try:
        res = sb.table("profiles").select("*").execute()
        return {u["username"]: {"name": u["name"], "password": u["password"]} for u in res.data}
    except:
        return {}

# Inizializzazione configurazione
if "user_db" not in st.session_state:
    st.session_state.user_db = load_users()

# Stato della pagina (login o iscrizione)
if "auth_mode" not in st.session_state:
    st.session_state.auth_mode = "login"

# --- 2. AUTENTICAZIONE ---
auth = stauth.Authenticate(
    {"credentials": {"usernames": st.session_state.user_db}},
    "turnosano_cookie",
    "signature_key_2026",
    30
)

# --- 3. LOGICA DI NAVIGAZIONE ---
if not st.session_state.get("authentication_status"):
    st.title("🏥 TurnoSano AI")
    
    if st.session_state.auth_mode == "login":
        # SCHERMATA LOGIN
        auth.login(location='main')
        if st.session_state["authentication_status"] is False:
            st.error("Username o password errati.")
        
        st.write("---")
        if st.button("Non hai un account? Iscriviti qui"):
            st.session_state.auth_mode = "iscrizione"
            st.rerun()

    else:
        # SCHERMATA ISCRIZIONE
        st.subheader("📝 Crea il tuo account")
        try:
            res_reg = auth.register_user(location='main', pre_authorization=False)
            if res_reg and res_reg[0]:
                u_name, u_info = res_reg
                sb.table("profiles").insert({
                    "username": str(u_name), 
                    "name": str(u_info['name']), 
                    "password": str(u_info['password'])
                }).execute()
                
                st.success("✅ Registrazione completata con successo!")
                # Aggiorna il database utenti in memoria
                st.session_state.user_db = load_users()
                # FORZA il ritorno al login dopo 2 secondi
                st.info("Reindirizzamento al login in corso...")
                st.session_state.auth_mode = "login"
                st.rerun()
        except Exception as e:
            st.error(f"Errore durante l'iscrizione: {e}")
        
        if st.button("Hai già un account? Accedi"):
            st.session_state.auth_mode = "login"
            st.rerun()

else:
    # --- 4. APP PRINCIPALE (DOPO IL LOGIN) ---
    st.sidebar.title(f"👋 {st.session_state['name']}")
    auth.logout('Esci dall\'app', 'sidebar')
    
    pdf_file = st.sidebar.file_uploader("Carica il tuo Turno (PDF)", type="pdf")
    if pdf_file:
        reader = PdfReader(pdf_file)
        st.session_state.pdf_text = "".join([p.extract_text() for p in reader.pages if p.extract_text()])
        st.sidebar.success("Turno analizzato!")

    st.title("🏥 Dashboard Benessere")

    with st.form("wellness_form", clear_on_submit=True):
        f_val = st.slider("Livello Fatica (1-10)", 1, 10, 5)
        s_val = st.number_input("Ore di sonno effettive", 0.0, 24.0, 7.0, step=0.5)
        if st.form_submit_button("Salva Parametri"):
            try:
                sb.table("wellness").insert({
                    "user_id": str(st.session_state['username']), 
                    "fatica": float(f_val), 
                    "ore_sonno": float(s_val)
                }).execute()
                st.success("Dati salvati!")
                st.rerun()
            except: st.error("Errore nel salvataggio.")

    # Storico
    with st.expander("📂 I tuoi ultimi dati"):
        try:
            res = sb.table("wellness").select("*").filter("user_id", "eq", st.session_state['username']).order("created_at", desc=True).limit(5).execute()
            if res.data:
                st.table(pd.DataFrame(res.data)[["fatica", "ore_sonno"]])
        except: st.info("Nessun dato.")

    # --- 5. COACH SCIENTIFICO ---
    st.divider()
    st.subheader("🔬 Strategie basate su studi scientifici")
    
    if "GROQ_API_KEY" in st.secrets:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        
        c1, c2, c3 = st.columns(3)
        p_rapido = None
        if c1.button("🌙 Post-Notte"): p_rapido = "Strategie scientifiche per il recupero dopo il turno di notte."
        if c2.button("🥗 Alimentazione"): p_rapido = "Consigli cronobiologici sulla nutrizione per turnisti."
        if c3.button("🗑️ Reset"):
            st.session_state.msgs = []
            st.rerun()

        chat_in = st.chat_input("Chiedi un consiglio scientifico...")
        q = chat_in or p_rapido

        if q:
            if "msgs" not in st.session_state: st.session_state.msgs = []
            st.session_state.msgs.append({"role": "user", "content": q})
            
            sys_prompt = (
                "Sei un assistente esperto in cronobiologia. NON sei un medico. "
                "Fornisci consigli comportamentali basati su studi scientifici (es. igiene del sonno, gestione luce)."
            )
            
            res_ai = client.chat.completions.create(
                messages=[{"role": "system", "content": sys_prompt}] + st.session_state.msgs,
                model="llama-3.1-8b-instant"
            )
            st.session_state.msgs.append({"role": "assistant", "content": res_ai.choices[0].message.content})

        if "msgs" in st.session_state:
            for m in st.session_state.msgs:
                with st.chat_message(m["role"]): st.write(m["content"])
