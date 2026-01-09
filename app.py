import streamlit as st
import streamlit_authenticator as stauth
from groq import Groq
from PyPDF2 import PdfReader

# 1. Configurazione Pagina
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥", layout="wide")

# 2. Inizializzazione dati (Session State)
# La libreria modifica questo dizionario direttamente
if "config" not in st.session_state:
    st.session_state.config = {
        "usernames": {}
    }

# Inizializzazione Authenticator
authenticator = stauth.Authenticate(
    st.session_state.config,  # Passiamo il dizionario da Session State
    "turnosano_cookie",
    "auth_key",
    cookie_expiry_days=30
)

# 3. INTERFACCIA DI ACCESSO
tab1, tab2 = st.tabs(["Accedi 🔑", "Iscriviti 📝"])

with tab2:
    # Modulo di Registrazione - Versione 2026
    try:
        # Nota: Non passiamo label/form_name se causano errori nelle versioni recenti
        # Il metodo restituisce True se la registrazione va a buon fine
        if authenticator.register_user(pre_authorized=None):
            st.success('Registrazione avvenuta! Ora puoi andare sulla scheda "Accedi".')
            # I dati in st.session_state.config sono già stati aggiornati dall'authenticator
    except Exception as e:
        st.error(f"Errore durante la registrazione: {e}")

with tab1:
    # Modulo di Login (Sintassi 2026)
    authenticator.login()

# 4. LOGICA DELL'APP (Area Riservata)
if st.session_state.get("authentication_status"):
    
    # Inizializzazione memoria AI
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "testo_turno" not in st.session_state:
        st.session_state.testo_turno = ""

    # Sidebar con Logout
    with st.sidebar:
        st.write(f"Ciao, **{st.session_state['name']}** 👋")
        authenticator.logout('Esci', 'sidebar')
        st.divider()
        file_pdf = st.file_uploader("📂 Carica Turno PDF", type="pdf")
        if file_pdf:
            try:
                reader = PdfReader(file_pdf)
                testo_estratto = "".join([page.extract_text() or "" for page in reader.pages])
                st.session_state.testo_turno = testo_estratto
                st.success("Turno analizzato!")
            except Exception as e:
                st.error(f"Errore lettura PDF: {e}")

    st.title("🏥 TurnoSano AI")
    
    # --- CHAT CON GROQ ---
    try:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
    except Exception:
        st.error("Configura GROQ_API_KEY nei Secrets!")
        st.stop()

    if prompt := st.chat_input("Chiedi al Coach..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        prompt_sistema = f"Sei TurnoSano AI, coach per l'infermiere {st.session_state['name']}. Rispondi in italiano."
        if st.session_state.testo_turno:
            prompt_sistema += f"\nContesto turno: {st.session_state.testo_turno}"
        
        try:
            response = client.chat.completions.create(
                messages=[{"role": "system", "content": prompt_sistema}] + st.session_state.messages,
                model="llama-3.1-8b-instant",
            )
            # Accesso corretto al contenuto (SDK Groq)
            risposta = response.choices[0].message.content
            st.session_state.messages.append({"role": "assistant", "content": risposta})
        except Exception as e:
            st.error(f"Errore AI: {e}")

    # Visualizzazione messaggi
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

elif st.session_state.get("authentication_status") is False:
    st.error('Username o Password errati')
elif st.session_state.get("authentication_status") is None:
    st.info('Registrati o effettua l\'accesso per continuare.')
