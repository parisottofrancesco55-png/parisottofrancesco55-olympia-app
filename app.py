import streamlit as st
import streamlit_authenticator as stauth
from groq import Groq
from PyPDF2 import PdfReader

# 1. Configurazione Pagina
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥", layout="wide")

# 2. Gestione Autenticazione (Versione Aggiornata 2026)
# Creiamo prima il dizionario delle credenziali
credentials = {
    "usernames": {
        "anna2026": {
            "name": "Infermiera Anna",
            "password": "turno123" # Verrà hashata subito dopo
        },
        "francesco2026": {
            "name": "Infermiere Francesco",
            "password": "coach2026" # Verrà hashata subito dopo
        }
    }
}

# Correzione TypeError: Il metodo hash_passwords ora richiede l'intero dizionario credentials
stauth.Hasher.hash_passwords(credentials)

# Inizializzazione Authenticate
authenticator = stauth.Authenticate(
    credentials,
    "turnosano_cookie",
    "auth_key",
    cookie_expiry_days=30
)

# Interfaccia Login
# Nota: La versione 2026 non restituisce più 3 valori ma gestisce lo stato internamente
authenticator.login()

if st.session_state["authentication_status"] == False:
    st.error('Username o Password errati')
elif st.session_state["authentication_status"] == None:
    st.warning('Inserisci le tue credenziali per accedere')
elif st.session_state["authentication_status"]:
    
    # --- AREA RISERVATA ---
    
    # Inizializzazione Session State
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "testo_turno" not in st.session_state:
        st.session_state.testo_turno = ""

    # Sidebar
    with st.sidebar:
        st.write(f"Benvenuto, **{st.session_state['name']}**")
        authenticator.logout('Logout', 'sidebar')
        st.divider()
        file_pdf = st.file_uploader("📂 Carica Turno PDF", type="pdf")
        if file_pdf:
            reader = PdfReader(file_pdf)
            st.session_state.testo_turno = "".join([p.extract_text() or "" for p in reader.pages])
            st.success("Turno analizzato!")

    st.title("🏥 TurnoSano AI")
    
    # --- SEZIONE AZIONI RAPIDE ---
    st.write("### ⚡ Azioni Rapide")
    c1, c2, c3 = st.columns(3)
    
    input_rapido = None
    if c1.button("🌙 SOS Turno Notte"): input_rapido = "Dammi una strategia per la notte."
    if c2.button("🥗 Alimentazione"): input_rapido = "Cosa mangiare in turno?"
    if c3.button("🧘 Stress Relief"): input_rapido = "Esercizio rapido anti-stress."

    # --- LOGICA CHAT ---
    # Assicurati che GROQ_API_KEY sia nei Secrets di Streamlit
    try:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
    except Exception as e:
        st.error("Configura la GROQ_API_KEY nei Secrets!")
        st.stop()

    prompt = st.chat_input("Chiedi al Coach...")
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
            st.error(f"Errore Groq: {e}")

    # Visualizzazione Messaggi
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
