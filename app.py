import streamlit as st
import streamlit_authenticator as stauth
from groq import Groq
from PyPDF2 import PdfReader

# 1. Configurazione Pagina
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥", layout="wide")

# 2. Gestione Autenticazione (Versione 2026)
# Definiamo gli utenti
names = ["Infermiera Anna", "Infermiere Francesco"]
usernames = ["anna2026", "francesco2026"]
passwords = ["turno123", "coach2026"]

# Correzione TypeError: Nuovo metodo per hashare le password
hashed_passwords = stauth.Hasher.hash_passwords(passwords)

credentials = {"usernames": {}}
for i in range(len(usernames)):
    credentials["usernames"][usernames[i]] = {
        "name": names[i],
        "password": hashed_passwords[i]
    }

authenticator = stauth.Authenticate(
    credentials,
    "turnosano_cookie",
    "auth_key",
    cookie_expiry_days=30
)

# Interfaccia Login
name, authentication_status, username = authenticator.login('Login', 'main')

if authentication_status == False:
    st.error('Username o Password errati')
elif authentication_status == None:
    st.warning('Inserisci le tue credenziali per accedere al Coach')
elif authentication_status:
    
    # --- INIZIO APP REALE ---
    
    # Inizializzazione Session State
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "testo_turno" not in st.session_state:
        st.session_state.testo_turno = ""

    # Sidebar
    with st.sidebar:
        st.write(f"Benvenuto, **{name}**")
        authenticator.logout('Logout', 'sidebar')
        st.divider()
        st.header("📂 Carica Turno")
        file_pdf = st.file_uploader("Carica PDF", type="pdf")
        if file_pdf:
            reader = PdfReader(file_pdf)
            st.session_state.testo_turno = "".join([p.extract_text() or "" for p in reader.pages])
            st.success("Turno analizzato!")

    st.title("🏥 TurnoSano AI")
    
    # --- SEZIONE AZIONI RAPIDE ---
    st.write("### ⚡ Azioni Rapide")
    c1, c2, c3 = st.columns(3)
    
    input_rapido = None
    if c1.button("🌙 SOS Turno Notte"):
        input_rapido = "Dammi una strategia per gestire la notte di stasera."
    if c2.button("🥗 Alimentazione"):
        input_rapido = "Cosa mangiare per non essere stanchi?"
    if c3.button("🧘 Stress Relief"):
        input_rapido = "Esercizio rapido anti-stress."

    # --- LOGICA CHAT ---
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])

    # Gestione input (da chat o da bottone rapido)
    prompt = st.chat_input("Chiedi al Coach...")
    if input_rapido:
        prompt = input_rapido

    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        prompt_sistema = f"Sei TurnoSano AI, coach per l'infermiere {name}. Rispondi in italiano."
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
