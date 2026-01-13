import streamlit as st
import pandas as pd
from supabase import create_client, Client
from groq import Groq
from PyPDF2 import PdfReader
import streamlit_authenticator as stauth
import plotly.graph_objects as go
import stripe
from datetime import datetime, timedelta

# --- 1. CONFIGURAZIONE E CONNESSIONE DB ---
st.set_page_config(page_title="TurnoSano IA", page_icon="🏥", layout="wide")

def init_db():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

sb = init_db()

def load_users():
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
            st.info("🛡️ I tuoi dati sono protetti nei server di Zurigo (CH).")
            privacy = st.checkbox("Accetto la Privacy Policy")
            if st.form_submit_button("Crea Account"):
                if new_p == conf_p and privacy and new_u and new_u not in user_db["usernames"]:
                    hashed_pw = stauth.Hasher([new_p]).generate()[0]
                    sb.table("profiles").insert({
                        "username": new_u, "name": new_n, "password": hashed_pw, "is_premium": False
                    }).execute()
                    st.success("✅ Account creato! Torna al login.")
                    st.session_state.auth_mode = "login"
                    st.rerun()
        if st.button("Torna al Login"):
            st.session_state.auth_mode = "login"
            st.rerun()

else:
    # --- 4. AREA UTENTE LOGGATO ---
    auth.logout('Disconnetti', 'sidebar')
    current_user = st.session_state['username']
    is_premium = user_db["usernames"].get(current_user, {}).get("is_premium", False)

    # Sidebar: Gestione Premium
    st.sidebar.divider()
    st.sidebar.subheader("💎 Il tuo Piano")
    if is_premium:
        st.sidebar.success("Stato: PREMIUM")
    else:
        st.sidebar.warning("Stato: BASE")
        if st.sidebar.button("🚀 Attiva Funzioni Premium"):
            st.sidebar.markdown(f"**[Abbonati con Stripe]({st.secrets['STRIPE_CHECKOUT_URL']})**")
    
    st.sidebar.divider()
    if st.sidebar.button("➕ Registra altro profilo"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.session_state.auth_mode = "iscrizione"
        st.rerun()

    st.title(f"📊 Benvenuto, {st.session_state['name']}")

    # --- 5. TABS PRINCIPALI ---
    tab_d, tab_a, tab_p = st.tabs(["📝 Diario", "📈 Analisi", "🚀 Premium Plus"])
    
    with tab_d:
        col1, col2 = st.columns([1, 1])
        with col1:
            st.subheader("Inserimento Dati")
            with st.form("wellness_data"):
                fatica = st.slider("Livello Fatica (1-10)", 1, 10, 5)
                sonno = st.number_input("Ore Sonno", 0.0, 24.0, 7.0)
                if st.form_submit_button("Salva Parametri"):
                    sb.table("wellness").insert({"user_id": current_user, "fatica": fatica, "ore_sonno": sonno}).execute()
                    st.success("Dati salvati!")
        with col2:
            st.info("📌 **Consiglio:** Inserisci i dati appena ti svegli per una precisione maggiore.")

    with tab_a:
        if is_premium:
            st.subheader("Andamento Settimanale")
            res = sb.table("wellness").select("*").eq("user_id", current_user).execute()
            if res.data:
                df = pd.DataFrame(res.data).sort_values('created_at')
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df['created_at'], y=df['fatica'], name="Fatica", line=dict(color='red', width=3)))
                fig.add_trace(go.Scatter(x=df['created_at'], y=df['ore_sonno'], name="Sonno", line=dict(color='blue', width=3)))
                st.plotly_chart(fig, use_container_width=True)
            else: st.info("Inserisci i dati per vedere il grafico.")
        else:
            st.error("🔒 Grafici storici bloccati. Passa a Premium.")

    with tab_p:
        if is_premium:
            st.subheader("Strumenti Avanzati")
            cp1, cp2 = st.columns(2)
            with cp1:
                if st.button("🍎 Genera Piano Alimentare"):
                    st.session_state.p_query = "Generami un piano alimentare specifico per chi lavora di notte oggi."
            with cp2:
                if st.button("📄 Esporta Report per Medico"):
                    st.download_button("Scarica PDF (Simulazione)", "Dati del report...", "report_medico.txt")
            
            st.divider()
            st.markdown("🔮 **Analisi Predittiva IA:**")
            st.write("In base ai tuoi dati, domani avrai un picco di fatica. Pianifica un riposo extra.")
        else:
            st.warning("🚀 Abbonati per sbloccare l'Analisi Predittiva e i Piani Alimentari.")

    # --- 6. COACH SCIENTIFICO IA ---
    st.divider()
    st.subheader("🔬 Coach Scientifico IA")
    
    if "GROQ_API_KEY" in st.secrets:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        
        # COMANDI RAPIDI
        st.write("💡 **Azioni Rapide:**")
        cq1, cq2, cq3, cq4 = st.columns(4)
        q_fast = None
        if cq1.button("🌙 Recupero Notte"): q_fast = "3 consigli per recuperare dopo la notte."
        if cq2.button("🥗 Cosa Mangio?"): q_fast = "Pasto ideale post-turno pomeridiano."
        if cq3.button("☕ Stop Caffeina"): q_fast = "Quando bere l'ultimo caffè?"
        if cq4.button("🗑️ Reset Chat"): 
            st.session_state.msgs = []
            st.rerun()

        if "msgs" not in st.session_state: st.session_state.msgs = []
        user_in = st.chat_input("Chiedi all'IA...")
        
        # Gestione query (priorità ai bottoni premium o rapidi)
        query = st.session_state.get("p_query") or q_fast or user_in
        if "p_query" in st.session_state: del st.session_state.p_query

        if query:
            st.session_state.msgs.append({"role": "user", "content": query})
            sys_msg = "Sei un esperto di salute per turnisti. Rispondi in italiano."
            if not is_premium: sys_msg += " Rispondi in massimo 2 righe."
            
            res_ia = client.chat.completions.create(
                messages=[{"role": "system", "content": sys_msg}] + st.session_state.msgs,
                model="llama-3.1-8b-instant"
            )
            st.session_state.msgs.append({"role": "assistant", "content": res_ia.choices[0].message.content})

        for m in st.session_state.msgs:
            with st.chat_message(m["role"]): st.write(m["content"])

    st.markdown("---")
    st.caption("🛡️ Dati protetti a Zurigo (CH) | 🏥 TurnoSano IA")
