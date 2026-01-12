import streamlit as st
import pandas as pd
from supabase import create_client, Client
from groq import Groq
from PyPDF2 import PdfReader
import streamlit_authenticator as stauth

# --- 1. CONFIGURAZIONE INIZIALE ---
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥", layout="centered")

# Inizializzazione Supabase
try:
    sb: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error("Errore di connessione a Supabase. Controlla i Secrets.")
    st.stop()

# --- 2. FUNZIONI DI SUPPORTO ---
def get_auth_config():
    try:
        res = sb.table("profiles").select("*").execute()
        return {"usernames": {u["username"]: {"name": u["name"], "password": u["password"]} for u in res.data}}
    except:
        return {"usernames": {}}

def salva_dati_benessere(username, fatica, sonno):
    try:
        payload = {
            "user_id": str(username),
            "fatica": int(fatica),
            "ore_sonno": float(sonno)
        }
        sb.table("wellness").insert(payload).execute()
        return True
    except Exception as e:
        st.error(f"Errore database: {e}")
        return False

# --- 3. GESTIONE AUTENTICAZIONE ---
if "config" not in st.session_state:
    st.session_state.config = get_auth_config()

# Authenticate con Validator per evitare RegisterError
auth = stauth.Authenticate(
    st.session_state.config,
    "turnosano_cookie",
    "signature_key",
    cookie_expiry_days=30,
    validator={
        "min_length": 6,
        "min_lowercase": 0,
        "min_uppercase": 0,
        "min_digits": 0,
        "min_special": 0
    }
)

if not st.session_state.get("authentication_status"):
    tab_login, tab_reg = st.tabs(["Accedi 🔑", "Iscriviti 📝"])
    
    with tab_reg:
        try:
            # Registrazione nuovo utente
            res_reg = auth.register_user(pre_authorized=None)
            if res_reg and res_reg[0]:
                new_user = {
                    "username": str(res_reg[0]),
                    "name": str(res_reg[1]['name']),
                    "password": str(res_reg[1]['password'])
                }
                sb.table("profiles").insert(new_user).execute()
                st.success("Registrazione completata! Ora puoi accedere dal tab 'Accedi'.")
                st.session_state.config = get_auth_config()
        except Exception as e:
            st.warning("Assicurati che la password sia di almeno 6 caratteri.")

    with tab_login:
        auth.login()

else:
    # --- 4. DASHBOARD UTENTE (LOGGATO) ---
    if "messages" not in st.session_state: st.session_state.messages = []
    if "pdf_text" not in st.session_state: st.session_state.pdf_text = ""

    # Sidebar
    st.sidebar.title("👨‍⚕️ Area Personale")
    st.sidebar.write(f"Benvenuto, **{st.session_state['name']}**")
    auth.logout('Disconnetti', 'sidebar')
    
    st.sidebar.divider()
    pdf_file = st.sidebar.file_uploader("Carica Turno (PDF)", type="pdf")
    if pdf_file:
        reader = PdfReader(pdf_file)
        st.session_state.pdf_text = "".join([p.extract_text() for p in reader.pages if p.extract_text()])
        st.sidebar.success("PDF analizzato!")

    st.title("🏥 TurnoSano AI")
    st.write("Monitora il tuo benessere e chiedi consigli al Coach AI.")

    # Diario Benessere
    with st.form("form_benessere"):
        st.subheader("📝 Diario di Oggi")
        f_val = st.slider("Grado di fatica (1=Riposato, 10=Esausto)", 1, 10, 5)
        s_val = st.number_input("Ore di sonno nell'ultima giornata", 0.0, 24.0, 7.0, step=0.5)
        
        if st.form_submit_button("Salva Parametri"):
            if salva_dati_benessere(st.session_state['username'], f_val, s_val):
                st.success("Dati salvati con successo!")

    # Storico Semplice
    with st.expander("📂 Visualizza Storico Inserimenti"):
        res_wellness = sb.table("wellness").select("*").filter("user_id", "eq", st.session_state['username']).order("created_at", desc=True).limit(5).execute()
        if res_wellness.data:
            st.table(pd.DataFrame(res_wellness.data)[["created_at", "fatica", "ore_sonno"]])
        else:
            st.info("Non ci sono ancora dati registrati.")

    # --- 5. COACH AI (GROQ) ---
    st.divider()
    st.subheader("💬 Coach AI Benessere")

    if "GROQ_API_KEY" in st.secrets:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        
        # Comandi rapidi
        c1, c2, c3 = st.columns(3)
        p_rapido = None
        if c1.button("🌙 SOS Notte"): p_rapido = "Come posso gestire la stanchezza per il turno di notte?"
        if c2.button("🥗 Dieta Turnista"): p_rapido = "Cosa mi consigli di mangiare post-turno?"
        if c3.button("🗑️ Reset Chat"):
            st.session_state.messages = []
            st.rerun()

        prompt_input = st.chat_input("Fai una domanda al Coach...")
        query_finale = prompt_input or p_rapido

        if query_finale:
            st.session_state.messages.append({"role": "user", "content": query_finale})
            
            # Contesto per l'AI
            istruzioni = f"Sei TurnoSano AI, un coach per infermieri. Nome utente: {st.session_state['name']}."
            if st.session_state.pdf_text:
                istruzioni += f" Contesto turno dell'utente: {st.session_state.pdf_text[:400]}"

            try:
                response = client.chat.completions.create(
                    messages=[{"role": "system", "content": istruzioni}] + st.session_state.messages,
                    model="llama-3.1-8b-instant"
                )
                st.session_state.messages.append({"role": "assistant", "content": response.choices[0].message.content})
            except Exception as e:
                st.error("Errore nella risposta dell'AI.")

        # Mostra la Chat
        for m in st.session_state.messages:
            with st.chat_message(m["role"]):
                st.write(m["content"])
    else:
        st.warning("Configura la chiave GROQ_API_KEY per attivare il Coach AI.")
