import streamlit as st
import streamlit_authenticator as stauth
from groq import Groq
from PyPDF2 import PdfReader

# 1. Configurazione Pagina
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥", layout="wide")

# 2. Inizializzazione dati (In un'app reale questi dati starebbero su un Database)
if "credentials" not in st.session_state:
    st.session_state.credentials = {"usernames": {}}

# Inizializzazione Authenticator
authenticator = stauth.Authenticate(
    st.session_state.credentials,
    "turnosano_cookie",
    "auth_key",
    cookie_expiry_days=30
)

# 3. INTERFACCIA DI ACCESSO (Login / Registrazione)
tab1, tab2 = st.tabs(["Accedi 🔑", "Iscriviti 📝"])

with tab2:
    # Modulo di Registrazione
    try:
        if authenticator.register_user('Registra nuovo account', pre_authorization=False):
            st.success('Registrazione avvenuta con successo! Ora puoi accedere.')
    except Exception as e:
        st.error(f"Errore durante la registrazione: {e}")

with tab1:
    # Modulo di Login
    authenticator.login()

# 4. LOGICA DELL'APP (Area Riservata)
if st.session_state["authentication_status"]:
    
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
            reader = PdfReader(file_pdf)
            st.session_state.testo_turno = "".join([p.extract_text() or "" for p in reader.pages])
            st.success("Turno analizzato!")

    st.title("🏥 TurnoSano AI")
    st.write("Il tuo Coach AI per la gestione dei turni.")

    # --- AZIONI RAPIDE ---
    st.write("### ⚡ Suggerimenti Rapidi")
    c1, c2, c3 = st.columns(3)
    input_rapido = None
    if c1.button("🌙 SOS Turno Notte"): input_rapido = "Consigli per la notte."
    if c2.button("🥗 Alimentazione"): input_rapido = "Cosa mangiare in turno?"
    if c3.button("🧘 Stress Relief"): input_rapido = "Esercizio relax rapido."

    # --- CHAT CON GROQ ---
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])

    prompt = st.chat_input("Chiedi qualcosa al Coach...")
    if input_rapido: prompt = input_rapido

    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        prompt_sistema = f"Sei TurnoSano AI, coach per l'infermiere {st.session_state['name']}."
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
            st.error(f"Errore tecnico: {e}")

    # Mostra i messaggi
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

elif st.session_state["authentication_status"] == False:
    st.error('Username o Password errati')
elif st.session_state["authentication_status"] == None:
    st.info('Compila i campi per accedere o crea un nuovo account.')
