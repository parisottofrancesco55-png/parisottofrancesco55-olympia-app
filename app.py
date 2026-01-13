import streamlit as st
import pandas as pd
from supabase import create_client, Client
from groq import Groq
from PyPDF2 import PdfReader
import streamlit_authenticator as stauth
import plotly.graph_objects as go
from datetime import datetime, timedelta
import pytz

# --- 1. CONFIGURAZIONE E CONNESSIONE DB ---
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥", layout="wide")

def init_db():
    """Inizializza la connessione a Supabase"""
    try:
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except Exception as e:
        st.error(f"Errore connessione Database: {e}")
        st.stop()

sb = init_db()

def load_users():
    """Carica gli utenti aggiornati dal DB di Zurigo"""
    try:
        res = sb.table("profiles").select("*").execute()
        return {"usernames": {u["username"]: {"name": u["name"], "password": u["password"]} for u in res.data}}
    except:
        return {"usernames": {}}

# Inizializzazione stati di navigazione
if "auth_mode" not in st.session_state:
    st.session_state.auth_mode = "login"

user_db = load_users()

# --- 2. AUTENTICAZIONE (Fix sessione persistente) ---
auth = stauth.Authenticate(
    user_db,
    "turnosano_cookie",
    "turnosano_key",
    cookie_expiry_days=0  # La sessione scade alla chiusura del browser
)

# --- 3. LOGICA DI ACCESSO / REGISTRAZIONE ---
if not st.session_state.get("authentication_status"):
    
    if st.session_state.auth_mode == "login":
        st.title("🏥 TurnoSano AI - Accedi")
        auth.login(location='main')
        
        if st.session_state["authentication_status"] is False:
            st.error("Username o password errati.")
        
        st.write("---")
        if st.button("Non hai un account? Registrati ora"):
            st.session_state.auth_mode = "iscrizione"
            st.rerun()

    else:
        st.title("📝 Registrazione Nuovo Operatore")
        with st.form("reg_form"):
            new_u = st.text_input("Username (per il login)").lower().strip()
            new_n = st.text_input("Nome Visualizzato")
            new_p = st.text_input("Password", type="password")
            conf_p = st.text_input("Conferma Password", type="password")
            
            st.info("🛡️ **Privacy:** I tuoi dati sono conservati a Zurigo (CH) secondo GDPR.")
            privacy = st.checkbox("Accetto la Privacy Policy")
            
            if st.form_submit_button("Crea Account"):
                if not privacy:
                    st.error("Devi accettare la privacy.")
                elif new_p != conf_p:
                    st.error("Le password non coincidono.")
                elif new_u in user_db["usernames"]:
                    st.error("Username già occupato.")
                elif not new_u or not new_p:
                    st.warning("Compila tutti i campi.")
                else:
                    # FIX HASHING RIGA 81
                    hashed_pw = stauth.Hasher([new_p]).generate()[0]
                    try:
                        sb.table("profiles").insert({
                            "username": new_u, "name": new_n, "password": hashed_pw
                        }).execute()
                        st.success("✅ Account creato! Torna al login.")
                        st.session_state.auth_mode = "login"
                        st.rerun()
                    except Exception as e:
                        st.error(f"Errore DB: {e}")
        
        if st.button("Torna al Login"):
            st.session_state.auth_mode = "login"
            st.rerun()

else:
    # --- 4. DASHBOARD (UTENTE LOGGATO) ---
    auth.logout('Esci dall\'account', 'sidebar')
    
    st.sidebar.title(f"👋 Ciao {st.session_state['name']}")
    
    # Pulsante per forzare la creazione di un altro account (Reset sessione)
    if st.sidebar.button("➕ Registra un altro profilo"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.session_state.auth_mode = "iscrizione"
        st.rerun()

    # Sidebar Privacy e PDF
    with st.sidebar.expander("⚖️ Gestione Dati"):
        st.caption("📍 Server: Zurigo, Svizzera")
        if st.button("Elimina i miei parametri"):
            sb.table("wellness").delete().eq("user_id", st.session_state['username']).execute()
            st.success("Dati puliti!")

    pdf_file = st.sidebar.file_uploader("📅 Carica Turno (PDF)", type="pdf")
    if pdf_file:
        reader = PdfReader(pdf_file)
        st.session_state.pdf_text = "".join([p.extract_text() for p in reader.pages if p.extract_text()])
        st.sidebar.success("Turno analizzato!")

    st.title("📊 Monitoraggio Benessere Operatori")

    # --- 5. INSERIMENTO E GRAFICI ---
    col_in, col_graph = st.columns([1, 2])
    
    with col_in:
        st.subheader("📝 Diario")
        with st.form("wellness_data", clear_on_submit=True):
            fatica = st.slider("Fatica (1-10)", 1, 10, 5)
            sonno = st.number_input("Ore sonno", 0.0, 24.0, 7.0, step=0.5)
            if st.form_submit_button("Salva Parametri"):
                sb.table("wellness").insert({
                    "user_id": st.session_state['username'], 
                    "fatica": float(fatica), "ore_sonno": float(sonno)
                }).execute()
                st.rerun()

    with col_graph:
        st.subheader("📈 Andamento")
        try:
            res = sb.table("wellness").select("*").eq("user_id", st.session_state['username']).execute()
            if res.data:
                df = pd.DataFrame(res.data).sort_values('created_at')
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df['created_at'], y=df['fatica'], name="Fatica", line=dict(color='red', width=3)))
                fig.add_trace(go.Scatter(x=df['created_at'], y=df['ore_sonno'], name="Sonno", line=dict(color='blue', width=3)))
                fig.update_layout(height=300, margin=dict(l=0,r=0,t=0,b=0), template="plotly_white")
                st.plotly_chart(fig, use_container_width=True)
        except: st.info("Inserisci i dati per vedere il grafico.")

    # --- 6. COACH IA E COMANDI RAPIDI ---
    st.divider()
    st.subheader("🔬 Coach Scientifico AI")
    
    if "GROQ_API_KEY" in st.secrets:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        
        st.write("💡 **Azioni veloci:**")
        c1, c2, c3 = st.columns(3)
        q_fast = None
        if c1.button("🌙 Recupero Post-Notte"): q_fast = "Consigli per il post-notte."
        if c2.button("🥗 Dieta Turnista"): q_fast = "Cosa mangiare durante il turno di notte?"
        if c3.button("🗑️ Reset Chat"): 
            st.session_state.msgs = []
            st.rerun()

        if "msgs" not in st.session_state: st.session_state.msgs = []
        
        user_in = st.chat_input("Chiedi al coach...")
        query = q_fast if q_fast else user_in

        if query:
            st.session_state.msgs.append({"role": "user", "content": query})
            sys_msg = "Sei un esperto di cronobiologia. Rispondi in modo scientifico e breve."
            if "pdf_text" in st.session_state:
                sys_msg += f" Turni: {st.session_state.pdf_text[:500]}"
            
            res_ai = client.chat.completions.create(
                messages=[{"role": "system", "content": sys_msg}] + st.session_state.msgs,
                model="llama-3.1-8b-instant"
            )
            st.session_state.msgs.append({"role": "assistant", "content": res_ai.choices[0].message.content})

        for m in st.session_state.msgs:
            with st.chat_message(m["role"]): st.write(m["content"])

    st.markdown("---")
    st.caption("📍 Spagna-Italia | 🛡️ Zurigo (CH) | 🏥 TurnoSano AI")
