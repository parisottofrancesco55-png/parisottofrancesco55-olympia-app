import streamlit as st
import pandas as pd
from supabase import create_client, Client
from groq import Groq
from PyPDF2 import PdfReader
import streamlit_authenticator as stauth
import plotly.graph_objects as go
from datetime import datetime, timedelta
import pytz

# --- 1. CONFIGURAZIONE E DATABASE ---
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥", layout="wide")

def init_db():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

sb = init_db()

def load_users():
    """Carica utenti dal DB di Zurigo con la struttura per Authenticator 0.3.x"""
    try:
        res = sb.table("profiles").select("*").execute()
        return {"usernames": {u["username"]: {"name": u["name"], "password": u["password"]} for u in res.data}}
    except:
        return {"usernames": {}}

# Inizializzazione stati
if "auth_mode" not in st.session_state:
    st.session_state.auth_mode = "login"

user_db = load_users()

# --- 2. AUTENTICAZIONE ---
auth = stauth.Authenticate(
    user_db,
    "turnosano_cookie",
    "turnosano_key",
    30
)

# --- 3. LOGICA DI ACCESSO / REGISTRAZIONE ---
if not st.session_state.get("authentication_status"):
    
    if st.session_state.auth_mode == "login":
        st.title("🏥 TurnoSano AI - Accedi")
        auth.login(location='main')
        
        if st.session_state["authentication_status"] is False:
            st.error("Username o password errati.")
        
        st.write("---")
        if st.button("Non hai un account? Registrati qui"):
            st.session_state.auth_mode = "iscrizione"
            st.rerun()

    else:
        st.title("📝 Registrazione Nuovo Profilo")
        with st.form("reg_form"):
            new_u = st.text_input("Username").lower().strip()
            new_n = st.text_input("Nome Visualizzato")
            new_p = st.text_input("Password", type="password")
            conf_p = st.text_input("Conferma Password", type="password")
            
            st.info("🛡️ **Privacy:** I tuoi dati sono protetti a Zurigo (CH) secondo GDPR.")
            privacy = st.checkbox("Accetto il trattamento dei dati personali")
            
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
                    # FIX RIGA 81: Nuovo metodo hashing per stauth 0.3.x
                    hashed_pw = stauth.Hasher([new_p]).generate()[0]
                    try:
                        sb.table("profiles").insert({
                            "username": new_u, "name": new_n, "password": hashed_pw
                        }).execute()
                        st.success("✅ Account creato! Ora puoi fare il login.")
                        st.session_state.auth_mode = "login"
                        st.rerun()
                    except Exception as e:
                        st.error(f"Errore database: {e}")
        
        if st.button("Torna al Login"):
            st.session_state.auth_mode = "login"
            st.rerun()

else:
    # --- 4. AREA RISERVATA ---
    auth.logout('Disconnetti', 'sidebar')
    st.sidebar.title(f"👋 Ciao {st.session_state['name']}")
    
    # Reset sessione per nuovo account
    if st.sidebar.button("➕ Registra un altro account"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.session_state.auth_mode = "iscrizione"
        st.rerun()

    # Sidebar PDF e Privacy
    with st.sidebar.expander("⚖️ Gestione Account"):
        st.caption("Server: Zurigo (CH)")
        if st.button("Elimina i miei dati"):
            sb.table("wellness").delete().eq("user_id", st.session_state['username']).execute()
            st.success("Dati eliminati.")

    pdf_file = st.sidebar.file_uploader("📅 Carica Turno (PDF)", type="pdf")
    if pdf_file:
        reader = PdfReader(pdf_file)
        st.session_state.pdf_text = "".join([p.extract_text() for p in reader.pages if p.extract_text()])
        st.sidebar.success("Turno analizzato!")

    st.title("📊 La tua Dashboard")

    # --- 5. INPUT E GRAFICI ---
    c1, c2 = st.columns([1, 2])
    
    with c1:
        st.subheader("📝 Inserisci dati")
        with st.form("wellness_form", clear_on_submit=True):
            f_val = st.slider("Fatica (1-10)", 1, 10, 5)
            s_val = st.number_input("Ore Sonno", 0.0, 24.0, 7.0, step=0.5)
            if st.form_submit_button("Salva"):
                sb.table("wellness").insert({
                    "user_id": st.session_state['username'], 
                    "fatica": float(f_val), "ore_sonno": float(s_val)
                }).execute()
                st.rerun()

    with c2:
        st.subheader("📈 Andamento")
        try:
            res = sb.table("wellness").select("*").eq("user_id", st.session_state['username']).execute()
            if res.data:
                df = pd.DataFrame(res.data).sort_values('created_at')
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df['created_at'], y=df['fatica'], name="Fatica", line=dict(color='red')))
                fig.add_trace(go.Scatter(x=df['created_at'], y=df['ore_sonno'], name="Sonno", line=dict(color='blue')))
                fig.update_layout(height=300, margin=dict(l=0,r=0,t=0,b=0), template="plotly_white")
                st.plotly_chart(fig, use_container_width=True)
        except: st.info("Inserisci i primi dati per vedere il grafico.")

    # --- 6. COACH IA E COMANDI RAPIDI ---
    st.divider()
    st.subheader("🔬 Coach Scientifico")
    
    if "GROQ_API_KEY" in st.secrets:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        
        # COMANDI RAPIDI
        st.write("💡 **Azioni Rapide:**")
        col1, col2, col3 = st.columns(3)
        fast_query = None
        if col1.button("🌙 Recupero Post-Notte"): fast_query = "Consigli scientifici per il recupero post-notte."
        if col2.button("🥗 Dieta Turnista"): fast_query = "Cosa mangiare durante il turno di notte?"
        if col3.button("🗑️ Reset Chat"): 
            st.session_state.messages = []
            st.rerun()

        if "messages" not in st.session_state: st.session_state.messages = []
        
        chat_input = st.chat_input("Chiedi al coach...")
        query = fast_query if fast_query else chat_input

        if query:
            st.session_state.messages.append({"role": "user", "content": query})
            sys_msg = "Sei un esperto di cronobiologia. Rispondi in modo breve."
            if "pdf_text" in st.session_state:
                sys_msg += f" Turni: {st.session_state.pdf_text[:500]}"
            
            res_ai = client.chat.completions.create(
                messages=[{"role": "system", "content": sys_msg}] + st.session_state.messages,
                model="llama-3.1-8b-instant"
            )
            st.session_state.messages.append({"role": "assistant", "content": res_ai.choices[0].message.content})

        for m in st.session_state.messages:
            with st.chat_message(m["role"]): st.write(m["content"])

    st.caption("🛡️ Sviluppato per la salute dei turnisti | Dati a Zurigo (CH)")
