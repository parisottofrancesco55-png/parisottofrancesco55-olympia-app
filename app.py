import streamlit as st
import pandas as pd
from supabase import create_client, Client
from groq import Groq
from PyPDF2 import PdfReader
import streamlit_authenticator as stauth

# --- 1. CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥", layout="centered")

def init_db():
    try:
        url = st.secrets["SUPABASE_URL"].strip().rstrip('/')
        key = st.secrets["SUPABASE_KEY"].strip()
        return create_client(url, key)
    except Exception as e:
        st.error(f"Errore configurazione Database: {e}")
        st.stop()

sb = init_db()

def load_users():
    try:
        res = sb.table("profiles").select("*").execute()
        if not res.data: return {}
        return {u["username"]: {"name": u["name"], "password": u["password"], "email": u.get("email", "")} for u in res.data}
    except: return {}

# Inizializzazione sessione
if "user_db" not in st.session_state:
    st.session_state.user_db = load_users()

if "auth_mode" not in st.session_state:
    st.session_state.auth_mode = "login"

# --- 2. AUTENTICAZIONE ---
# Passiamo la struttura corretta dei nomi utente
auth = stauth.Authenticate(
    {"usernames": st.session_state.user_db},
    "turnosano_cookie",
    "turnosano_key",
    30
)

# --- 3. LOGICA DI ACCESSO / REGISTRAZIONE ---
if not st.session_state.get("authentication_status"):
    st.title("🏥 TurnoSano AI")
    
    if st.session_state.auth_mode == "login":
        auth.login(location='main')
        if st.session_state["authentication_status"] is False:
            st.error("Username o password errati.")
        
        st.write("---")
        if st.button("Non hai un account? Iscriviti qui"):
            st.session_state.auth_mode = "iscrizione"
            st.rerun()

    else:
        st.subheader("📝 Registrazione")
        # Chiamata pulita per evitare il TypeError e la scomparsa delle caselle
        try:
            # register_user genera automaticamente le caselle di testo e il pulsante
            reg_data = auth.register_user(location='main')
            
            if reg_data:
                email, username, password = reg_data
                if username:
                    sb.table("profiles").insert({
                        "username": str(username), 
                        "name": str(username), 
                        "password": str(password),
                        "email": str(email)
                    }).execute()
                    st.success(f"✅ Registrazione di '{username}' riuscita!")
                    st.session_state.user_db = load_users()
                    st.info("Ora puoi cliccare il tasto sotto per accedere.")
        except Exception as e:
            st.error("Compila tutti i campi sopra e premi 'Register'.")
        
        if st.button("Torna al Login"):
            st.session_state.auth_mode = "login"
            st.rerun()

else:
    # --- 4. DASHBOARD UTENTE (DOPO IL LOGIN) ---
    st.sidebar.title(f"👋 {st.session_state['name']}")
    auth.logout('Esci', 'sidebar')
    
    pdf_file = st.sidebar.file_uploader("Carica Turno (PDF)", type="pdf")
    if pdf_file:
        reader = PdfReader(pdf_file)
        st.session_state.pdf_text = "".join([p.extract_text() for p in reader.pages if p.extract_text()])
        st.sidebar.success("Turno analizzato!")

    st.title("🏥 Dashboard Benessere")

    # Form con pulsante di invio corretto
    with st.form("wellness_form", clear_on_submit=True):
        st.subheader("📝 Diario Giornaliero")
        f_val = st.slider("Fatica percepita (1-10)", 1, 10, 5)
        s_val = st.number_input("Ore di sonno effettive", 0.0, 24.0, 7.0, step=0.5)
        
        # PULSANTE DI INVIO (Risolve l'errore Missing Submit Button)
        submitted = st.form_submit_button("Salva Parametri")
        
        if submitted:
            try:
                sb.table("wellness").insert({
                    "user_id": st.session_state['username'], 
                    "fatica": float(f_val), 
                    "ore_sonno": float(s_val)
                }).execute()
                st.success("Dati salvati!")
                st.rerun()
            except: 
                st.error("Errore nel salvataggio dei dati.")

    # Storico
    with st.expander("📂 I tuoi ultimi inserimenti"):
        try:
            res_w = sb.table("wellness").select("*").filter("user_id", "eq", st.session_state['username']).order("created_at", desc=True).limit(5).execute()
            if res_w.data:
                df = pd.DataFrame(res_w.data)
                df['Data'] = pd.to_datetime(df['created_at']).dt.strftime('%d/%m/%Y %H:%M')
                st.table(df[["Data", "fatica", "ore_sonno"]])
        except:
            st.info("Nessun dato ancora disponibile.")

    # --- 5. ASSISTENTE SCIENTIFICO ---
    st.divider()
    st.subheader("🔬 Strategie Scientifiche per Turnisti")
    
    if "GROQ_API_KEY" in st.secrets:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        
        # DOMANDE RAPIDE
        c1, c2, c3 = st.columns(3)
        p_rapido = None
        if c1.button("🌙 Recupero Notte"): p_rapido = "Quali sono le strategie di cronobiologia per il recupero post-notte?"
        if c2.button("🥗 Nutrizione"): p_rapido = "Consigli sull'alimentazione durante i turni notturni secondo studi scientifici."
        if c3.button("🗑️ Reset Chat"):
            st.session_state.msgs = []
            st.rerun()

        chat_in = st.chat_input("Chiedi un consiglio scientifico...")
        q = chat_in or p_rapido

        if q:
            if "msgs" not in st.session_state: st.session_state.msgs = []
            st.session_state.msgs.append({"role": "user", "content": q})
            
            # PROMPT SCIENTIFICO (NON MEDICO)
            sys_msg = (
                "Sei un assistente esperto in cronobiologia e medicina del lavoro. "
                "NON sei un medico e non devi dare consigli clinici o diagnosi. "
                "Fornisci consigli comportamentali basati su studi scientifici riguardo l'igiene del sonno, "
                "la gestione della luce e l'alimentazione dei turnisti."
            )
            
            res_ai = client.chat.completions.create(
                messages=[{"role": "system", "content": sys_msg}] + st.session_state.msgs,
                model="llama-3.1-8b-instant"
            )
            st.session_state.msgs.append({"role": "assistant", "content": res_ai.choices[0].message.content})

        if "msgs" in st.session_state:
            for m in st.session_state.msgs:
                with st.chat_message(m["role"]): st.write(m["content"])
