import streamlit as st
import pandas as pd
from supabase import create_client, Client
from groq import Groq
from PyPDF2 import PdfReader
import streamlit_authenticator as stauth
import plotly.graph_objects as go
import stripe # Assicurati di averlo nel requirements.txt
from datetime import datetime

# --- 1. CONFIGURAZIONE E CONNESSIONE DB ---
st.set_page_config(page_title="TurnoSano IA", page_icon="🏥", layout="wide")

def init_db():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

sb = init_db()

def load_users():
    """Carica utenti e stato abbonamento dal database di Zurigo"""
    try:
        res = sb.table("profiles").select("*").execute()
        return {"usernames": {u["username"]: {
            "name": u["name"], 
            "password": u["password"],
            "is_premium": u.get("is_premium", False)
        } for u in res.data}}
    except:
        return {"usernames": {}}

if "auth_mode" not in st.session_state:
    st.session_state.auth_mode = "login"

user_db = load_users()

# --- 2. AUTENTICAZIONE ---
auth = stauth.Authenticate(user_db, "turnosano_cookie", "turnosano_key", 0)

# --- 3. LOGICA DI ACCESSO / REGISTRAZIONE ---
if not st.session_state.get("authentication_status"):
    if st.session_state.auth_mode == "login":
        st.title("🏥 TurnoSano IA - Accedi")
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
                    # Fix Hashing per la registrazione
                    hashed_pw = stauth.Hasher([new_p]).generate()[0]
                    try:
                        sb.table("profiles").insert({
                            "username": new_u, "name": new_n, "password": hashed_pw, "is_premium": False
                        }).execute()
                        st.success("✅ Account creato! Torna al login.")
                        st.session_state.auth_mode = "login"
                        st.rerun()
                    except Exception as e:
                        st.error(f"Errore DB: {e}")
                else:
                    st.error("Dati non validi o username già esistente.")
        if st.button("Torna al Login"):
            st.session_state.auth_mode = "login"
            st.rerun()

else:
    # --- 4. AREA UTENTE LOGGATO ---
    auth.logout('Disconnetti', 'sidebar')
    
    current_user = st.session_state['username']
    is_premium = user_db["usernames"].get(current_user, {}).get("is_premium", False)

    # Sidebar: Piano Abbonamento
    st.sidebar.divider()
    st.sidebar.subheader("💎 Il tuo Piano")
    if is_premium:
        st.sidebar.success("Stato: PREMIUM")
    else:
        st.sidebar.warning("Stato: BASE")
        if st.sidebar.button("🚀 Passa a Premium"):
            if "STRIPE_CHECKOUT_URL" in st.secrets:
                st.sidebar.markdown(f"**[Abbonati con Stripe]({st.secrets['STRIPE_CHECKOUT_URL']})**")
            else:
                st.sidebar.error("Link Stripe non configurato.")
    
    st.sidebar.divider()
    if st.sidebar.button("➕ Registra un altro profilo"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.session_state.auth_mode = "iscrizione"
        st.rerun()

    st.title("📊 Dashboard Wellness")

    # --- 5. INPUT E ANALISI ---
    tab_d, tab_a = st.tabs(["📝 Diario Giornaliero", "📊 Analisi Avanzata"])
    
    with tab_d:
        with st.form("input_wellness"):
            f = st.slider("Livello Fatica (1-10)", 1, 10, 5)
            s = st.number_input("Ore Sonno", 0.0, 24.0, 7.0)
            if st.form_submit_button("Salva Parametri"):
                sb.table("wellness").insert({"user_id": current_user, "fatica": f, "ore_sonno": s}).execute()
                st.rerun()

    with tab_a:
        if is_premium:
            st.subheader("📈 Storico Benessere (Premium)")
            res = sb.table("wellness").select("*").eq("user_id", current_user).execute()
            if res.data:
                df = pd.DataFrame(res.data).sort_values('created_at')
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df['created_at'], y=df['fatica'], name="Fatica", line=dict(color='red', width=3)))
                fig.add_trace(go.Scatter(x=df['created_at'], y=df['ore_sonno'], name="Sonno", line=dict(color='blue', width=3)))
                fig.update_layout(template="plotly_white", height=400)
                st.plotly_chart(fig, use_container_width=True)
            else: st.info("Nessun dato registrato.")
        else:
            st.error("🔒 I grafici sono riservati agli utenti Premium.")
            st.info("Abbonati per monitorare i tuoi progressi nel tempo.")

    # --- 6. COACH SCIENTIFICO IA E COMANDI RAPIDI ---
    st.divider()
    st.subheader("🔬 Coach Scientifico IA")
    
    if "GROQ_API_KEY" in st.secrets:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        
        # --- COMANDI RAPIDI ---
        st.write("💡 **Azioni Rapide:**")
        c1, c2, c3, c4 = st.columns(4)
        q_fast = None
        
        if c1.button("🌙 Recupero Notturno"): q_fast = "Consigli scientifici per recuperare dopo la notte."
        if c2.button("🥗 Alimentazione"): q_fast = "Cosa mangiare durante il turno di notte?"
        if c3.button("☕ Gestione Caffeina"): q_fast = "Quando bere l'ultimo caffè prima di dormire?"
        if c4.button("🗑️ Svuota Chat"): 
            st.session_state.msgs = []
            st.rerun()

        if "msgs" not in st.session_state: st.session_state.msgs = []
        user_q = st.chat_input("Chiedi al Coach IA...")
        query = q_fast if q_fast else user_q

        if query:
            st.session_state.msgs.append({"role": "user", "content": query})
            sys_prompt = "Sei un esperto di cronobiologia e salute dei turnisti. Rispondi in italiano in modo breve."
            if not is_premium: sys_prompt += " Fornisci solo consigli generali (utente base)."
            
            res_ia = client.chat.completions.create(
                messages=[{"role": "system", "content": sys_prompt}] + st.session_state.msgs,
                model="llama-3.1-8b-instant"
            )
            st.session_state.msgs.append({"role": "assistant", "content": res_ia.choices[0].message.content})

        for m in st.session_state.msgs:
            with st.chat_message(m["role"]): st.write(m["content"])

    st.markdown("---")
    st.caption("🛡️ Dati a Zurigo (CH) | 💳 Pagamenti Stripe | 🏥 TurnoSano IA")
