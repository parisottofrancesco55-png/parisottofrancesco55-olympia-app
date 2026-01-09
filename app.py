import streamlit as st
from supabase import create_client, Client
import streamlit_authenticator as stauth
from groq import Groq
from PyPDF2 import PdfReader

# 1. Inizializzazione Pagina
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥", layout="wide")

# 2. Connessione Database Supabase
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(url, key)
except Exception as e:
    st.error("Configura SUPABASE_URL e SUPABASE_KEY nei Secrets!")
    st.stop()

# 3. Funzioni Database
def carica_utenti():
    res = supabase.table("profiles").select("*").execute()
    credenziali = {"usernames": {}}
    for u in res.data:
        credenziali["usernames"][u["username"]] = {"name": u["name"], "password": u["password"]}
    return credenziali

def salva_utente(username, name, password):
    supabase.table("profiles").insert({"username": username, "name": name, "password": password}).execute()

# 4. Gestione Autenticazione
config = carica_utenti()
authenticator = stauth.Authenticate(config, "turnosano_cookie", "auth_key", cookie_expiry_days=30)

if not st.session_state.get("authentication_status"):
    tab1, tab2 = st.tabs(["Accedi 🔑", "Iscriviti 📝"])
    with tab2:
        try:
            nuovo_utente = authenticator.register_user(pre_authorized=None)
            if nuovo_utente:
                u, info = nuovo_utente
                salva_utente(u, info['name'], info['password'])
                st.success('Registrato! Ora puoi accedere.')
        except Exception as e:
            st.error(f"Errore: {e}")
    with tab1:
        authenticator.login()
        if st.session_state.get("authentication_status"):
            st.rerun()

# --- 5. AREA RISERVATA (Solo se Loggato) ---
else:
    # Setup Memoria
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "testo_turno" not in st.session_state:
        st.session_state.testo_turno = ""

    # Sidebar
    with st.sidebar:
        st.write(f"In servizio: **{st.session_state['name']}**")
        if authenticator.logout('Esci', 'sidebar'):
            st.rerun()
        st.divider()
        file_pdf = st.file_uploader("📂 Carica Turno PDF", type="pdf")
        if file_pdf:
            reader = PdfReader(file_pdf)
            st.session_state.testo_turno = "".join([p.extract_text() or "" for p in reader.pages])
            st.success("Turno analizzato!")

    # --- DASHBOARD PERSONALE ---
    st.title(f"🏥 Dashboard di {st.session_state['name']}")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label="Stato Recupero", value="75%", delta="5%")
    with col2:
        num_c = len([m for m in st.session_state.messages if m["role"] == "assistant"])
        st.metric(label="Consigli Ricevuti", value=num_c)
    with col3:
        stato = "Analizzato ✅" if st.session_state.testo_turno else "Mancante ❌"
        st.write(f"**Turno PDF:** {stato}")

    st.divider()

    # --- CHAT CON GROQ ---
    st.subheader("💬 Parla con il Coach")
    
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])

    if prompt := st.chat_input("Chiedi aiuto per il turno..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        sys_p = f"Sei TurnoSano AI, coach per l'infermiere {st.session_state['name']}."
        if st.session_state.testo_turno:
            sys_p += f"\nContesto turno: {st.session_state.testo_turno}"
        
        res = client.chat.completions.create(
            messages=[{"role": "system", "content": sys_p}] + st.session_state.messages,
            model="llama-3.1-8b-instant",
        )
        st.session_state.messages.append({"role": "assistant", "content": res.choices[0].message.content})

    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
