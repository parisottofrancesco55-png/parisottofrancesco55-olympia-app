import streamlit as st
import pandas as pd
from supabase import create_client, Client
from groq import Groq
from PyPDF2 import PdfReader
import streamlit_authenticator as stauth
import plotly.graph_objects as go
from datetime import datetime, timedelta
import pytz

# --- 1. CONFIGURAZIONE ---
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥", layout="wide")

def init_db():
    try:
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except Exception as e:
        st.error(f"Errore connessione Database: {e}")
        st.stop()

sb = init_db()

def load_users():
    """Carica gli utenti aggiornati dal database di Zurigo"""
    try:
        res = sb.table("profiles").select("*").execute()
        return {"usernames": {u["username"]: {"name": u["name"], "password": u["password"]} for u in res.data}}
    except:
        return {"usernames": {}}

# Inizializzazione stati di navigazione
if "auth_mode" not in st.session_state:
    st.session_state.auth_mode = "login"

# Caricamento utenti dinamico
user_db = load_users()

# --- 2. AUTENTICAZIONE (Versione stabile 0.3.1) ---
auth = stauth.Authenticate(
    user_db,
    "turnosano_cookie",
    "turnosano_key",
    30
)

# --- 3. LOGICA LOGIN / REGISTRAZIONE ---
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
            
            st.info("🛡️ **Privacy:** I tuoi dati sono conservati a Zurigo (CH).")
            privacy = st.checkbox("Accetto la Privacy Policy (GDPR)")
            
            if st.form_submit_button("Crea Account"):
                if not privacy:
                    st.error("Devi accettare la privacy.")
                elif new_p != conf_p:
                    st.error("Le password non coincidono.")
                elif new_u in user_db["usernames"]:
                    st.error("Username già occupato.")
                elif len(new_p) < 6:
                    st.error("Password troppo corta (min 6 car).")
                else:
                    h_pw = stauth.Hasher.hash(new_p)
                    try:
                        sb.table("profiles").insert({"username": new_u, "name": new_n, "password": h_pw}).execute()
                        st.success("✅ Account creato con successo!")
                        st.info("Ora clicca su 'Torna al Login'.")
                    except Exception as e:
                        st.error(f"Errore DB: {e}")
        
        if st.button("Torna al Login"):
            st.session_state.auth_mode = "login"
            st.rerun()

else:
    # --- 4. DASHBOARD (UTENTE LOGGATO) ---
    auth.logout('Esci', 'sidebar')
    
    st.sidebar.title(f"👋 {st.session_state['name']}")
    
    # PULSANTE SPECIALE PER NUOVI ACCOUNT
    if st.sidebar.button("➕ Registra un altro utente"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.session_state.auth_mode = "iscrizione"
        st.rerun()

    # Sezione Privacy e Account
    with st.sidebar.expander("⚖️ Gestione Dati"):
        st.caption("📍 Server: Zurigo, Svizzera")
        if st.button("Elimina i miei dati"):
            sb.table("wellness").delete().eq("user_id", st.session_state['username']).execute()
            st.success("Dati puliti!")

    # Caricamento PDF Turni
    pdf_file = st.sidebar.file_uploader("📅 Carica Turno (PDF)", type="pdf")
    if pdf_file:
        reader = PdfReader(pdf_file)
        st.session_state.pdf_text = "".join([p.extract_text() for p in reader.pages if p.extract_text()])
        st.sidebar.success("Turno analizzato!")

    st.title("📊 Monitoraggio Benessere")

    # --- 5. INSERIMENTO E GRAFICI ---
    c_in, c_graph = st.columns([1, 2])
    
    with c_in:
        st.subheader("📝 Diario")
        with st.form("wellness_data", clear_on_submit=True):
            fatica = st.slider("Fatica (1-10)", 1, 10, 5)
            sonno = st.number_input("Ore sonno", 0.0, 24.0, 7.0, step=0.5)
            if st.form_submit_button("Salva"):
                sb.table("wellness").insert({
                    "user_id": st.session_state['username'], 
                    "fatica": float(fatica), "ore_sonno": float(sonno)
                }).execute()
                st.rerun()

    with c_graph:
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

    # --- 6. COACH IA + COMANDI RAPIDI ---
    st.divider()
    st.subheader("🔬 Coach Scientifico AI")
    
    if "GROQ_API_KEY" in st.secrets:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        
        # Comandi Rapidi
        st.write("💡 **Azioni veloci:**")
        col1, col2, col3 = st.columns(3)
        q_veloce = None
        if col1.button("🌙 Recupero Post-Notte"): q_veloce = "Consigli per recuperare il ritmo dopo una notte."
        if col2.button("🥗 Dieta Turnista"): q_veloce = "Cosa mangiare durante la notte?"
        if col3.button("🗑️ Reset Chat"): 
            st.session_state.msgs = []
            st.rerun()

        if "msgs" not in st.session_state: st.session_state.msgs = []
        
        testo_chat = st.chat_input("Chiedi al coach...")
        query_finale = q_veloce if q_veloce else testo_chat

        if query_finale:
            st.session_state.msgs.append({"role": "user", "content": query_finale})
            sys_msg = "Sei un esperto di cronobiologia. Rispondi in modo scientifico e breve."
            if "pdf_text" in st.session_state:
                sys_msg += f" Turni utente: {st.session_state.pdf_text[:500]}"
            
            res_ai = client.chat.completions.create(
                messages=[{"role": "system", "content": sys_msg}] + st.session_state.msgs,
                model="llama-3.1-8b-instant"
            )
            st.session_state.msgs.append({"role": "assistant", "content": res_ai.choices[0].message.content})

        for m in st.session_state.msgs:
            with st.chat_message(m["role"]): st.write(m["content"])

    st.markdown("---")
    st.caption("📍 Spagna-Italia | 🛡️ Zurigo (CH) | 🏥 TurnoSano AI")
