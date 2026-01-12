import streamlit as st
import pandas as pd
from supabase import create_client, Client
from groq import Groq
from PyPDF2 import PdfReader
import streamlit_authenticator as stauth
import plotly.graph_objects as go
from datetime import datetime, timedelta
import pytz

# --- 1. CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥", layout="wide")

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
        return {u["username"]: {"name": u["name"], "password": u["password"]} for u in res.data}
    except:
        return {}

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
        st.subheader("📝 Registrazione Nuovo Utente")
        with st.form("registration_form"):
            new_user = st.text_input("Username (per il login)")
            new_name = st.text_input("Nome Visualizzato")
            new_pw = st.text_input("Password", type="password")
            confirm_pw = st.text_input("Conferma Password", type="password")
            
            st.markdown("---")
            st.info("**Informativa Privacy:** I tuoi dati sono protetti a Zurigo (CH). Cliccando accetti il trattamento dei dati sanitari (GDPR).")
            privacy_check = st.checkbox("Accetto la Privacy Policy")

            submit_reg = st.form_submit_button("Crea Account")
            
            if submit_reg:
                if not privacy_check:
                    st.error("Devi accettare la privacy.")
                elif not new_user or not new_pw:
                    st.warning("Compila i campi.")
                elif new_pw != confirm_pw:
                    st.error("Password non coincidenti.")
                else:
                    hashed_pw = stauth.Hasher.hash(new_pw)
                    try:
                        sb.table("profiles").insert({"username": new_user, "name": new_name, "password": hashed_pw}).execute()
                        st.success("Account creato! Fai il login.")
                        st.session_state.user_db = load_users()
                        st.session_state.auth_mode = "login"
                        st.rerun()
                    except Exception as e:
                        st.error(f"Errore: {e}")
        
        if st.button("Torna al Login"):
            st.session_state.auth_mode = "login"
            st.rerun()

else:
    # --- 4. AREA RISERVATA ---
    st.sidebar.title(f"👋 {st.session_state['name']}")
    
    with st.sidebar.expander("⚖️ Privacy e Account"):
        st.caption("Server: Zurigo (CH) | Sviluppo: Spagna")
        if st.checkbox("Voglio eliminare i miei dati"):
            if st.button("Elimina Account Definitivamente"):
                sb.table("wellness").delete().eq("user_id", st.session_state['username']).execute()
                sb.table("profiles").delete().eq("username", st.session_state['username']).execute()
                st.rerun()

    auth.logout('Esci', 'sidebar')
    
    st.sidebar.divider()
    pdf_file = st.sidebar.file_uploader("📅 Carica Turno (PDF)", type="pdf")
    if pdf_file:
        reader = PdfReader(pdf_file)
        st.session_state.pdf_text = "".join([p.extract_text() for p in reader.pages if p.extract_text()])
        st.sidebar.success("Turno analizzato!")

    st.title("📊 Dashboard Benessere")

    # --- 5. INSERIMENTO DATI ---
    with st.expander("📝 Inserisci dati oggi", expanded=True):
        with st.form("wellness_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            f_val = c1.slider("Fatica (1-10)", 1, 10, 5)
            s_val = c2.number_input("Ore Sonno", 0.0, 24.0, 7.0, step=0.5)
            if st.form_submit_button("Salva Parametri"):
                sb.table("wellness").insert({"user_id": st.session_state['username'], "fatica": float(f_val), "ore_sonno": float(s_val)}).execute()
                st.success("Dati salvati!")
                st.rerun()

    # --- 6. GRAFICI ---
    try:
        res = sb.table("wellness").select("*").filter("user_id", "eq", st.session_state['username']).execute()
        if res.data:
            df = pd.DataFrame(res.data)
            df['created_at'] = pd.to_datetime(df['created_at'])
            df_plot = df.sort_values('created_at').tail(10)
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df_plot['created_at'], y=df_plot['fatica'], name="Fatica", line=dict(color='red')))
            fig.add_trace(go.Scatter(x=df_plot['created_at'], y=df_plot['ore_sonno'], name="Sonno", line=dict(color='blue')))
            fig.update_layout(height=300, margin=dict(l=0,r=0,t=0,b=0))
            st.plotly_chart(fig, use_container_width=True)
    except:
        st.info("Inserisci dati per vedere i grafici.")

    # --- 7. COACH IA E COMANDI RAPIDI ---
    st.divider()
    st.subheader("🔬 Coach Scientifico")
    
    if "GROQ_API_KEY" in st.secrets:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        
        # --- BLOCCO COMANDI RAPIDI ---
        st.write("💡 **Azioni Rapide:**")
        col1, col2, col3 = st.columns(3)
        prompt_rapido = None
        
        if col1.button("🌙 Recupero Post-Notte"):
            prompt_rapido = "Dammi consigli scientifici per recuperare il ritmo circadiano dopo un turno di notte."
        if col2.button("🥗 Dieta Turnista"):
            prompt_rapido = "Cosa dovrei mangiare durante un turno di notte per evitare picchi di stanchezza?"
        if col3.button("🗑️ Reset Chat"):
            st.session_state.msgs = []
            st.rerun()
        # -----------------------------

        chat_in = st.chat_input("Chiedi al coach...")
        
        # Se viene premuto un comando rapido, usiamo quello, altrimenti l'input manuale
        query = prompt_rapido if prompt_rapido else chat_in

        if query:
            if "msgs" not in st.session_state: st.session_state.msgs = []
            st.session_state.msgs.append({"role": "user", "content": query})
            
            sys_msg = "Sei un esperto in cronobiologia. Aiuta i turnisti."
            if "pdf_text" in st.session_state:
                sys_msg += f" Analizza i turni dell'utente: {st.session_state.pdf_text[:500]}"
            
            response = client.chat.completions.create(
                messages=[{"role": "system", "content": sys_msg}] + st.session_state.msgs,
                model="llama-3.1-8b-instant"
            )
            st.session_state.msgs.append({"role": "assistant", "content": response.choices[0].message.content})

        if "msgs" in st.session_state:
            for m in st.session_state.msgs:
                with st.chat_message(m["role"]): st.write(m["content"])

    st.markdown("---")
    st.caption("📍 Spagna | 🛡️ Zurigo (CH) | 🏥 TurnoSano AI")
    st.caption("📍 Sviluppato in Spagna | 🛡️ Dati protetti a Zurigo (CH) | 🏥 TurnoSano AI v1.1")
