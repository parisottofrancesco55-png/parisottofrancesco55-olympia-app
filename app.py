import streamlit as st
import pandas as pd
from supabase import create_client, Client
from groq import Groq
from PyPDF2 import PdfReader
import streamlit_authenticator as stauth

# --- 1. CONFIGURAZIONE ---
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥", layout="centered")

def init_db():
    try:
        url = st.secrets["SUPABASE_URL"].strip().rstrip('/')
        key = st.secrets["SUPABASE_KEY"].strip()
        return create_client(url, key)
    except Exception as e:
        st.error(f"Errore Database: {e}")
        st.stop()

sb = init_db()

def load_users():
    try:
        res = sb.table("profiles").select("*").execute()
        if not res.data: return {}
        return {u["username"]: {"name": u["name"], "password": u["password"], "email": u.get("email", "")} for u in res.data}
    except: return {}

# Inizializzazione dati
if "user_db" not in st.session_state:
    st.session_state.user_db = load_users()

if "auth_mode" not in st.session_state:
    st.session_state.auth_mode = "login"

# --- 2. AUTENTICAZIONE ---
auth = stauth.Authenticate(
    {"usernames": st.session_state.user_db},
    "turnosano_cookie",
    "turnosano_key",
    30
)

# --- 3. LOGICA DI NAVIGAZIONE ---
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
        try:
            # Chiamata compatibile con le versioni 0.3.x
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
                    st.info("Torna al Login per entrare.")
        except Exception as e:
            st.error(f"Errore: {e}. Assicurati di compilare tutti i campi.")
        
        if st.button("Torna al Login"):
            st.session_state.auth_mode = "login"
            st.rerun()

else:
    # --- 4. APP PRINCIPALE ---
    st.sidebar.title(f"👋 {st.session_state['name']}")
    auth.logout('Esci', 'sidebar')
    
    pdf_file = st.sidebar.file_uploader("Carica Turno (PDF)", type="pdf")
    if pdf_file:
        reader = PdfReader(pdf_file)
        st.session_state.pdf_text = "".join([p.extract_text() for p in reader.pages if p.extract_text()])
        st.sidebar.success("PDF Caricato")

    st.title("🏥 Dashboard Benessere")

    # Diario
    with st.form("wellness_form", clear_on_submit=True):
        st.subheader("📝 Diario")
        f_val = st.slider("Fatica (1-10)", 1, 10, 5)
        s_val = st.number_input("Ore sonno effettive", 0.0, 24.0, 7.0, step=0.5)
        if st.form_submit_button("Salva Parametri"):
            try:
                sb.table("wellness").insert({
                    "user_id": st.session_state['username'], 
                    "fatica": float(f_val), "ore_sonno": float(s_val)
                }).execute()
                st.success("Dati salvati!")
                st.rerun()
            except: st.error("Errore salvataggio.")

    # Storico (Tabella)
    with st.expander("📂 I tuoi ultimi dati"):
        try:
            res_w = sb.table("wellness").select("*").filter("user_id", "eq", st.session_state['username']).order("created_at", desc=True).limit(5).execute()
            if res_w.data:
                df = pd.DataFrame(res_w.data)
                df['Data'] = pd.to_datetime(df['created_at']).dt.strftime('%d/%m/%Y %H:%M')
                st.table(df[["Data", "fatica", "ore_sonno"]])
            else:
                st.info("Ancora nessun dato.")
        except: st.info("Caricamento...")

    # --- 5. ASSISTENTE SCIENTIFICO ---
    st.divider()
    st.subheader("🔬 Supporto Scientifico per Turnisti")
    
    if "GROQ_API_KEY" in st.secrets:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        
        # DOMANDE RAPIDE
        c1, c2, c3 = st.columns(3)
        p_rapido = None
        if c1.button("🌙 Recupero Notte"): p_rapido = "Strategie scientifiche (cronobiologia) per recuperare dopo il turno di notte."
        if c2.button("🥗 Nutrizione"): p_rapido = "Cosa dice la scienza sull'alimentazione ideale per i turnisti notturni?"
        if c3.button("🗑️ Reset Chat"):
            st.session_state.msgs = []
            st.rerun()

        chat_in = st.chat_input("Chiedi un consiglio scientifico...")
        q = chat_in or p_rapido

        if q:
            if "msgs" not in st.session_state: st.session_state.msgs = []
            st.session_state.msgs.append({"role": "user", "content": q})
            
            sys_msg = (
                "Sei un assistente scientifico esperto in cronobiologia. "
                "NON sei un medico e non dai pareri clinici. Fornisci consigli basati su studi "
                "scientifici riguardo l'igiene del sonno e la gestione dei ritmi circadiani."
            )
            if "pdf_text" in st.session_state:
                sys_msg += f" Considera questi turni: {st.session_state.pdf_text[:300]}"

            res_ai = client.chat.completions.create(
                messages=[{"role": "system", "content": sys_msg}] + st.session_state.msgs,
                model="llama-3.1-8b-instant"
            )
            st.session_state.msgs.append({"role": "assistant", "content": res_ai.choices[0].message.content})

        if "msgs" in st.session_state:
            for m in st.session_state.msgs:
                with st.chat_message(m["role"]): st.write(m["content"])
