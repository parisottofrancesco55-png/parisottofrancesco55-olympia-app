import streamlit as st
import pandas as pd
from supabase import create_client, Client
from groq import Groq
from PyPDF2 import PdfReader
import streamlit_authenticator as stauth
import plotly.graph_objects as go
import stripe

# --- 1. CONFIGURAZIONE E CONNESSIONE DB ---
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥", layout="wide")

def init_db():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

sb = init_db()

def load_users():
    """Carica gli utenti e lo stato abbonamento dal DB di Zurigo"""
    try:
        res = sb.table("profiles").select("*").execute()
        return {"usernames": {u["username"]: {
            "name": u["name"], 
            "password": u["password"],
            "is_premium": u.get("is_premium", False)
        } for u in res.data}}
    except:
        return {"usernames": {}}

# Stato navigazione
if "auth_mode" not in st.session_state:
    st.session_state.auth_mode = "login"

user_db = load_users()

# --- 2. AUTENTICAZIONE (Cookie expiry a 0 per evitare blocchi) ---
auth = stauth.Authenticate(user_db, "turnosano_cookie", "turnosano_key", 0)

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
            new_u = st.text_input("Username").lower().strip()
            new_n = st.text_input("Nome")
            new_p = st.text_input("Password", type="password")
            conf_p = st.text_input("Conferma Password", type="password")
            st.info("🛡️ Dati protetti a Zurigo (CH) - GDPR compliant.")
            privacy = st.checkbox("Accetto la Privacy Policy")
            if st.form_submit_button("Crea Account"):
                if new_p == conf_p and privacy and new_u and new_u not in user_db["usernames"]:
                    # Fix Hashing per v0.3.x
                    hashed_pw = stauth.Hasher([new_p]).generate()[0]
                    sb.table("profiles").insert({
                        "username": new_u, "name": new_n, "password": hashed_pw, "is_premium": False
                    }).execute()
                    st.success("✅ Account creato! Torna al login.")
                    st.session_state.auth_mode = "login"
                    st.rerun()
                else:
                    st.error("Dati non validi o username già esistente.")
        if st.button("Torna al Login"):
            st.session_state.auth_mode = "login"
            st.rerun()

else:
    # --- 4. AREA UTENTE LOGGATO ---
    auth.logout('Disconnetti', 'sidebar')
    
    current_user = st.session_state['username']
    is_premium = user_db["usernames"][current_user].get("is_premium", False)

    # Sidebar: Gestione Premium
    st.sidebar.divider()
    st.sidebar.subheader("💎 Piano Abbonamento")
    if is_premium:
        st.sidebar.success("Stato: PREMIUM")
    else:
        st.sidebar.warning("Stato: BASE")
        if st.sidebar.button("🚀 Attiva Premium"):
            st.sidebar.markdown(f"**[Paga ora con Stripe]({st.secrets['STRIPE_CHECKOUT_URL']})**")
    
    st.sidebar.divider()
    if st.sidebar.button("➕ Registra un altro profilo"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.session_state.auth_mode = "iscrizione"
        st.rerun()

    st.title("📊 La tua Dashboard Wellness")

    # --- 5. INPUT E ANALISI ---
    tab_d, tab_a = st.tabs(["📝 Diario", "📊 Analisi Avanzata"])
    
    with tab_d:
        with st.form("input_wellness"):
            f = st.slider("Livello Fatica", 1, 10, 5)
            s = st.number_input("Ore Sonno", 0.0, 24.0, 7.0)
            if st.form_submit_button("Salva Dati"):
                sb.table("wellness").insert({"user_id": current_user, "fatica": f, "ore_sonno": s}).execute()
                st.rerun()

    with tab_a:
        if is_premium:
            res = sb.table("wellness").select("*").eq("user_id", current_user).execute()
            if res.data:
                df = pd.DataFrame(res.data).sort_values('created_at')
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df['created_at'], y=df['fatica'], name="Fatica", line=dict(color='red')))
                fig.add_trace(go.Scatter(x=df['created_at'], y=df['ore_sonno'], name="Sonno", line=dict(color='blue')))
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.error("🔒 I grafici storici sono riservati agli utenti Premium.")

    # --- 6. COACH IA + COMANDI RAPIDI ---
    st.divider()
    st.subheader("🔬 Coach Scientifico AI")
    
    if "GROQ_API_KEY" in st.secrets:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        
        # --- SEZIONE COMANDI RAPIDI ---
        st.write("💡 **Azioni Rapide:**")
        c1, c2, c3, c4 = st.columns(4)
        fast_cmd = None
        
        if c1.button("🌙 Recupero Post-Notte"): 
            fast_cmd = "Dammi 3 consigli scientifici per recuperare il ritmo dopo un turno di notte."
        if c2.button("🥗 Dieta Turnista"): 
            fast_cmd = "Cosa dovrei mangiare durante il turno di notte per evitare picchi glicemici?"
        if c3.button("☕ Gestione Caffeina"): 
            fast_cmd = "Qual è l'orario migliore per l'ultimo caffè prima di finire il turno?"
        if c4.button("🗑️ Reset Chat"): 
            st.session_state.chat_history = []
            st.rerun()

        # Gestione Chat
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []

        chat_input = st.chat_input("Fai una domanda al Coach...")
        
        # Se è stato premuto un comando rapido, usalo come query
        query = fast_cmd if fast_cmd else chat_input

        if query:
            st.session_state.chat_history.append({"role": "user", "content": query})
            
            # Personalizzazione risposta in base al piano
            sys_prompt = "Sei un esperto di cronobiologia."
            if not is_premium:
                sys_prompt += " Rispondi in modo molto breve e generale (utente base)."
            
            completion = client.chat.completions.create(
                messages=[{"role": "system", "content": sys_prompt}] + st.session_state.chat_history,
                model="llama-3.1-8b-instant"
            )
            
            st.session_state.chat_history.append({"role": "assistant", "content": completion.choices[0].message.content})

        # Visualizzazione Chat
        for m in st.session_state.chat_history:
            with st.chat_message(m["role"]):
                st.write(m["content"])

    st.markdown("---")
    st.caption("🛡️ Dati protetti a Zurigo (CH) | 💳 Pagamenti via Stripe")
