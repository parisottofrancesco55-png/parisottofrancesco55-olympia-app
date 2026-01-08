import streamlit as st
import streamlit_authenticator as stauth
from groq import Groq
from PyPDF2 import PdfReader

# 1. Configurazione Pagina
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥", layout="wide")

# 2. Inizializzazione dati in Session State
if "credentials" not in st.session_state:
    st.session_state.credentials = {"usernames": {}}

# Inizializzazione Authenticate (Versione 2026)
authenticator = stauth.Authenticate(
    st.session_state.credentials,
    "turnosano_cookie",
    "auth_key",
    cookie_expiry_days=30
)

# 3. INTERFACCIA DI ACCESSO
tab1, tab2 = st.tabs(["Accedi 🔑", "Iscriviti 📝"])

with tab2:
    # Modulo di Registrazione - CORREZIONE PARAMETRI 2026
    try:
        # In questa versione il parametro è spesso 'label' o semplicemente il primo argomento
        if authenticator.register_user(label='Registra nuovo account', pre_authorized=None):
            st.success('Registrazione avvenuta con successo! Clicca sulla scheda "Accedi" per entrare.')
    except Exception as e:
        st.error(f"Errore durante la registrazione: {e}")

with tab1:
    # Modulo di Login
    authenticator.login()

# 4. LOGICA DELL'APP (Area Riservata)
if st.session_state.get("authentication_status"):
    
    # Inizializzazione Session State per l'AI
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "testo_turno" not in st.session_state:
        st.session_state.testo_turno = ""

    # Sidebar con Logout e Caricamento PDF
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
    
    # --- AZIONI RAPIDE ---
    st.write("### ⚡ Suggerimenti Rapidi")
    c1, c2, c3 = st.columns(3)
    input_rapido = None
    if c1.button("🌙 SOS Turno Notte"): input_rapido = "Dammi una strategia pratica per gestire il turno di notte di stasera."
    if c2.button("🥗 Alimentazione"): input_rapido = "Cosa mi consigli di mangiare durante il turno per non avere cali di energia?"
    if c3.button("🧘 Stress Relief"): input_rapido = "Consigliami un esercizio rapido per scaricare la tensione durante il lavoro."

    # --- CHAT CON GROQ ---
    try:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
    except Exception:
        st.error("Errore: Chiave API Groq non configurata nei Secrets.")
        st.stop()

    prompt = st.chat_input("Chiedi qualcosa al Coach...")
    if input_rapido: prompt = input_rapido

    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        prompt_sistema = f"Sei TurnoSano AI, coach per l'infermiere {st.session_state['name']}. Rispondi in italiano."
        if st.session_state.testo_turno:
            prompt_sistema += f"\nContesto turno: {st.session_state.testo_turno}"
        
        try:
            response = client.chat.completions.create(
                messages=[{"role": "system", "content": prompt_sistema}] + st.session_state.messages,
                model="llama-3.1-8b-instant",
            )
            risposta = response.choices[0].message.content
            st.session_state.messages.append({"role": "assistant", "content": risposta})
        except Exception as e:
            st.error(f"Errore tecnico AI: {e}")

    # Mostra i messaggi
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

elif st.session_state.get("authentication_status") is False:
    st.error('Username o Password errati')
elif st.session_state.get("authentication_status") is None:
    st.info('Effettua il login o registrati per iniziare.')
