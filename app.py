import streamlit as st
from supabase import create_client, Client
import streamlit_authenticator as stauth
from groq import Groq
from PyPDF2 import PdfReader

# --- 1. CONNESSIONE SUPABASE ---
# Assicurati di avere queste chiavi nei "Secrets" di Streamlit
try:
    URL_DB = st.secrets["SUPABASE_URL"]
    KEY_DB = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(URL_DB, KEY_DB)
except Exception as e:
    st.error("Errore: Chiavi Supabase non trovate nei Secrets.")
    st.stop()

# --- 2. FUNZIONI DATABASE ---
def carica_credenziali():
    """Recupera gli utenti salvati su Supabase"""
    try:
        res = supabase.table("profiles").select("*").execute()
        db_users = res.data
        credenziali = {"usernames": {}}
        for u in db_users:
            credenziali["usernames"][u["username"]] = {
                "name": u["name"],
                "password": u["password"]
            }
        return credenziali
    except Exception:
        return {"usernames": {}}

def salva_nuovo_utente(username, name, password_hash):
    """Salva i dati dell'iscrizione su Supabase"""
    try:
        supabase.table("profiles").insert({
            "username": username,
            "name": name,
            "password": password_hash
        }).execute()
        return True
    except Exception as e:
        st.error(f"Errore salvataggio DB: {e}")
        return False

# --- 3. CONFIGURAZIONE AUTH ---
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥", layout="wide")

# Carichiamo gli utenti dal database all'avvio
if "config" not in st.session_state:
    st.session_state.config = carica_credenziali()

authenticator = stauth.Authenticate(
    st.session_state.config,
    "turnosano_cookie",
    "auth_key",
    cookie_expiry_days=30
)

# --- 4. INTERFACCIA LOGIN / ISCRIZIONE ---
if not st.session_state.get("authentication_status"):
    tab1, tab2 = st.tabs(["Accedi 🔑", "Iscriviti 📝"])

    with tab2:
        try:
            # Il modulo di registrazione di streamlit-authenticator
            # NOTA: Nelle versioni 2026 i parametri possono variare, questa è la forma stabile
            new_user = authenticator.register_user(pre_authorized=None)
            if new_user:
                username, info = new_user
                if salva_nuovo_utente(username, info['name'], info['password']):
                    st.success('Registrazione completata! Ora puoi accedere.')
                    # Aggiorna la memoria locale dell'app senza riavviare
                    st.session_state.config = carica_credenziali()
        except Exception as e:
            st.error(f"Errore registrazione: {e}")

    with tab1:
        authenticator.login()
        if st.session_state.get("authentication_status"):
            st.rerun() # Entra nell'app dopo il login

# --- 5. AREA RISERVATA (LOGGATO) ---
else:
    # Inizializzazione sessioni AI
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "testo_turno" not in st.session_state:
        st.session_state.testo_turno = ""

    with st.sidebar:
        st.write(f"Benvenuto, **{st.session_state['name']}** 👋")
        if authenticator.logout('Esci', 'sidebar'):
            st.rerun()
        st.divider()
        file_pdf = st.file_uploader("📂 Carica Turno PDF", type="pdf")
        if file_pdf:
            reader = PdfReader(file_pdf)
            st.session_state.testo_turno = "".join([p.extract_text() or "" for p in reader.pages])
            st.success("Turno analizzato!")

    st.title("🏥 TurnoSano AI")
    
    # Integrazione Groq
    try:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
    except:
        st.error("Configura la GROQ_API_KEY!")
        st.stop()

    if prompt := st.chat_input("Chiedi al Coach..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        sys_msg = f"Sei TurnoSano AI, coach per l'infermiere {st.session_state['name']}."
        if st.session_state.testo_turno:
            sys_msg += f"\nContesto turno: {st.session_state.testo_turno}"
        
        res = client.chat.completions.create(
            messages=[{"role": "system", "content": sys_msg}] + st.session_state.messages,
            model="llama-3.1-8b-instant",
        )
        st.session_state.messages.append({"role": "assistant", "content": res.choices[0].message.content})

    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
