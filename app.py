import streamlit as st
import streamlit_authenticator as stauth
from groq import Groq
from PyPDF2 import PdfReader

# 1. Configurazione Pagina
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥", layout="wide")

# 2. Inizializzazione Dati Utenti
if "config" not in st.session_state:
    st.session_state.config = {"usernames": {}}

authenticator = stauth.Authenticate(
    st.session_state.config,
    "turnosano_cookie",
    "auth_key",
    cookie_expiry_days=30
)

# --- LOGICA DI VISUALIZZAZIONE ---
# Se l'utente NON è autenticato, mostriamo i Tab di accesso
if not st.session_state.get("authentication_status"):
    tab1, tab2 = st.tabs(["Accedi 🔑", "Iscriviti 📝"])

    with tab2:
        try:
            if authenticator.register_user(pre_authorized=None):
                st.success('Registrazione avvenuta! Ora puoi accedere.')
        except Exception as e:
            st.error(f"Errore registrazione: {e}")

    with tab1:
        # Il login aggiorna st.session_state["authentication_status"]
        authenticator.login()
        if st.session_state.get("authentication_status") is False:
            st.error('Username o Password errati')
        elif st.session_state.get("authentication_status") is None:
            st.info('Inserisci le tue credenziali')
        
        # Forza il refresh appena lo stato cambia in True
        if st.session_state.get("authentication_status"):
            st.rerun()

# Se l'utente È autenticato, mostriamo l'App reale
else:
    # --- AREA RISERVATA (Solo se Loggato) ---
    
    # Inizializzazione Memoria AI
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "testo_turno" not in st.session_state:
        st.session_state.testo_turno = ""

    # Sidebar con Logout
    with st.sidebar:
        st.write(f"Ciao, **{st.session_state.get('name', 'Infermiere')}** 👋")
        # Il pulsante logout resetta lo stato e noi forziamo il rerun
        if authenticator.logout('Esci', 'sidebar'):
            st.rerun()
            
        st.divider()
        file_pdf = st.file_uploader("📂 Carica Turno PDF", type="pdf")
        if file_pdf:
            try:
                reader = PdfReader(file_pdf)
                st.session_state.testo_turno = "".join([p.extract_text() or "" for p in reader.pages])
                st.success("Turno analizzato!")
            except Exception as e:
                st.error(f"Errore PDF: {e}")

    st.title("🏥 TurnoSano AI")
    st.write("Benvenuto nel tuo spazio di lavoro.")

    # --- CHAT CON GROQ ---
    try:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
    except:
        st.error("Configura la API Key nei Secrets!")
        st.stop()

    if prompt := st.chat_input("Chiedi al Coach..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        sys_prompt = f"Sei TurnoSano AI, coach per l'infermiere {st.session_state.get('name')}."
        if st.session_state.testo_turno:
            sys_prompt += f"\nContesto turno: {st.session_state.testo_turno}"
        
        try:
            response = client.chat.completions.create(
                messages=[{"role": "system", "content": sys_prompt}] + st.session_state.messages,
                model="llama-3.1-8b-instant",
            )
            st.session_state.messages.append({"role": "assistant", "content": response.choices[0].message.content})
        except Exception as e:
            st.error(f"Errore AI: {e}")

    # Display messaggi
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
