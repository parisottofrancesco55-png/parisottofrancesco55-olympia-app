import streamlit as st
import streamlit_authenticator as stauth
from groq import Groq
from PyPDF2 import PdfReader
import yaml
from yaml.loader import SafeLoader

# 1. CONFIGURAZIONE PAGINA
st.set_page_config(page_title="TurnoSano AI - Login", page_icon="🏥")

# 2. DEFINIZIONE UTENTI (Esempio manuale)
# In un'app reale, questi dati andrebbero in un file 'config.yaml' o Database
names = ["Infermiera Anna", "Infermiere Francesco"]
usernames = ["anna2026", "francesco2026"]
# Le password devono essere hashate per sicurezza. 
# Qui usiamo password in chiaro solo per farti testare subito, 
# ma il sistema ti avviserà di usare gli hash.
passwords = ["turno123", "coach2026"]

# Hash delle password (necessario per streamlit-authenticator)
hashed_passwords = stauth.Hasher(passwords).generate()

credentials = {"usernames":{}}
for i in range(len(usernames)):
    credentials["usernames"][usernames[i]] = {
        "name": names[i],
        "password": hashed_passwords[i]
    }

# Creazione dell'oggetto authenticator
authenticator = stauth.Authenticate(
    credentials,
    "turnosano_cookie", # Nome del cookie per restare loggati
    "auth_key",         # Chiave per la firma del cookie
    cookie_expiry_days=30
)

# 3. INTERFACCIA DI LOGIN
name, authentication_status, username = authenticator.login('Login', 'main')

if authentication_status == False:
    st.error('Username o Password errati')
elif authentication_status == None:
    st.warning('Per favore, inserisci username e password')
elif authentication_status:
    # --- SE IL LOGIN È CORRETTO, CARICA L'APP ---
    
    with st.sidebar:
        st.write(f"Benvenuto/a, **{name}**")
        authenticator.logout('Logout', 'sidebar')
        st.divider()
        
        st.header("📂 Carica Turno")
        file_pdf = st.file_uploader("Carica PDF", type="pdf")
        if file_pdf:
            reader = PdfReader(file_pdf)
            st.session_state.testo_turno = "".join([p.extract_text() or "" for p in reader.pages])
            st.success("PDF Caricato!")

    # LOGICA APP TURNOSANO (Precedentemente creata)
    st.title("🏥 TurnoSano AI")
    
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "testo_turno" not in st.session_state:
        st.session_state.testo_turno = ""

    # (Qui inserisci la logica dei bottoni rapidi e della chat con Groq...)
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])

    if prompt := st.chat_input("Chiedi al Coach..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        prompt_sistema = f"Sei TurnoSano AI, coach per l'infermiere {name}."
        if st.session_state.testo_turno:
            prompt_sistema += f"\nTurno attuale: {st.session_state.testo_turno}"
        
        response = client.chat.completions.create(
            messages=[{"role": "system", "content": prompt_sistema}] + st.session_state.messages,
            model="llama-3.1-8b-instant",
        )
        st.session_state.messages.append({"role": "assistant", "content": response.choices[0].message.content})

    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
