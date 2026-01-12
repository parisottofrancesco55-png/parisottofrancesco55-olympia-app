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
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except Exception as e:
        st.error(f"Errore connessione Database: {e}")
        st.stop()

sb = init_db()

def load_users():
    try:
        res = sb.table("profiles").select("*").execute()
        return {u["username"]: {"name": u["name"], "password": u["password"]} for u in res.data}
    except:
        return {}

# Inizializzazione Session State
if "user_db" not in st.session_state:
    st.session_state.user_db = load_users()
if "auth_mode" not in st.session_state:
    st.session_state.auth_mode = "login"

# --- 2. AUTENTICAZIONE ---
auth = stauth.Authenticate(
    {"usernames": st.session_state.user_db},
    "turnosano_cookie", "turnosano_key", 30
)

# --- 3. LOGICA DI ACCESSO / REGISTRAZIONE ---
if not st.session_state.get("authentication_status"):
    placeholder = st.empty()
    
    if st.session_state.auth_mode == "login":
        with placeholder.container():
            st.title("🏥 Accedi a TurnoSano AI")
            auth.login(location='main')
            if st.session_state["authentication_status"] is False:
                st.error("Username o password errati.")
            
            st.write("---")
            if st.button("Non hai un account? Registrati qui"):
                st.session_state.auth_mode = "iscrizione"
                st.rerun()

    else:
        with placeholder.container():
            st.title("📝 Crea il tuo Account")
            with st.form("reg_form"):
                new_u = st.text_input("Username (per il login)").lower().strip()
                new_n = st.text_input("Nome Visualizzato")
                new_p = st.text_input("Password", type="password")
                conf_p = st.text_input("Conferma Password", type="password")
                
                st.info("🛡️ I tuoi dati saranno protetti nei server di Zurigo (CH).")
                privacy = st.checkbox("Accetto la Privacy Policy (GDPR)")
                
                if st.form_submit_button("Completa Registrazione"):
                    if not privacy:
                        st.error("Devi accettare la privacy.")
                    elif new_p != conf_p:
                        st.error("Le password non coincidono.")
                    elif new_u in st.session_state.user_db:
                        st.error("Username già occupato.")
                    elif len(new_p) < 6:
                        st.error("Password troppo corta (min 6 car).")
                    else:
                        hashed_pw = stauth.Hasher.hash(new_p)
                        try:
                            sb.table("profiles").insert({
                                "username": new_u, "name": new_n, "password": hashed_pw
                            }).execute()
                            st.session_state.user_db = load_users() # Aggiorna lista utenti
                            st.success("✅ Account creato! Torna al login.")
                        except Exception as e:
                            st.error(f"Errore DB: {e}")
            
            if st.button("Torna al Login"):
                st.session_state.auth_mode = "login"
                st.rerun()

else:
    # --- 4. DASHBOARD (UTENTE LOGGATO) ---
    st.sidebar.title(f"👋 Ciao {st.session_state['name']}")
    
    with st.sidebar.expander("⚖️ Privacy e Account"):
        st.caption("Server: Zurigo (CH) | Sviluppo: Spagna")
        if st.checkbox("Elimina tutti i miei dati"):
            if st.button("Conferma Eliminazione"):
                sb.table("wellness").delete().eq("user_id", st.session_state['username']).execute()
                sb.table("profiles").delete().eq("username", st.session_state['username']).execute()
                for key in list(st.session_state.keys()): del st.session_state[key]
                st.rerun()

    auth.logout('Esci', 'sidebar')
    
    st.sidebar.divider()
    pdf_file = st.sidebar.file_uploader("📅 Carica Turno (PDF)", type="pdf")
    if pdf_file:
        reader = PdfReader(pdf_file)
        st.session_state.pdf_text = "".join([p.extract_text() for p in reader.pages if p.extract_text()])
        st.sidebar.success("Turno analizzato!")

    st.title("🏥 Dashboard Benessere Operatori")

    # --- 5. INSERIMENTO DATI ---
    with st.expander("📝 Diario di oggi", expanded=True):
        with st.form("wellness_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            f_val = c1.slider("Fatica (1=Riposato, 10=Esausto)", 1, 10, 5)
            s_val = c2.number_input("Ore sonno effettive", 0.0, 24.0, 7.0, step=0.5)
            if st.form_submit_button("Salva Parametri"):
                sb.table("wellness").insert({
                    "user_id": st.session_state['username'], 
                    "fatica": float(f_val), "ore_sonno": float(s_val)
                }).execute()
                st.success("Dati salvati!")
                st.rerun()

    # --- 6. GRAFICI ---
    st.subheader("📊 I tuoi progressi")
    try:
        res = sb.table("wellness").select("*").filter("user_id", "eq", st.session_state['username']).execute()
        if res.data:
            df = pd.DataFrame(res.data)
            df['created_at'] = pd.to_datetime(df['created_at'])
            
            # Calcolo medie (7 giorni)
            utc = pytz.UTC
            limite = datetime.now(utc) - timedelta(days=7)
            df_week = df[df['created_at'] > limite]
            
            m1, m2 = st.columns(2)
            m1.metric("Media Fatica (7g)", f"{df_week['fatica'].mean():.1f}/10")
            m2.metric("Media Sonno (7g)", f"{df_week['ore_sonno'].mean():.1f}h")

            # Grafico Linee
            fig = go.Figure()
            df_plot = df.sort_values('created_at').tail(14)
            fig.add_trace(go.Scatter(x=df_plot['created_at'], y=df_plot['fatica'], name="Fatica", line=dict(color='red', width=3)))
            fig.add_trace(go.Scatter(x=df_plot['created_at'], y=df_plot['ore_sonno'], name="Sonno", line=dict(color='blue', width=3)))
            fig.update_layout(height=350, template="plotly_white", margin=dict(l=0,r=0,t=10,b=0))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Inserisci i tuoi primi dati per vedere l'andamento.")
    except Exception as e:
        st.error(f"Errore caricamento grafici: {e}")

    # --- 7. COACH IA E COMANDI RAPIDI ---
    st.divider()
    st.subheader("🔬 Supporto Scientifico AI")
    
    if "GROQ_API_KEY" in st.secrets:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        
        st.write("💡 **Comandi Rapidi:**")
        col1, col2, col3 = st.columns(3)
        p_rapido = None
        if col1.button("🌙 Recupero Post-Notte"): p_rapido = "Strategie per recuperare dopo la notte."
        if col2.button("🥗 Dieta Turnista"): p_rapido = "Cosa mangiare durante il turno di notte?"
        if col3.button("🗑️ Reset Chat"): 
            st.session_state.msgs = []
            st.rerun()

        chat_in = st.chat_input("Fai una domanda al coach...")
        q = p_rapido if p_rapido else chat_in

        if q:
            if "msgs" not in st.session_state: st.session_state.msgs = []
            st.session_state.msgs.append({"role": "user", "content": q})
            
            sys_msg = "Sei un esperto in cronobiologia e medicina del lavoro. NON sei un medico. Dai consigli scientifici."
            if "pdf_text" in st.session_state:
                sys_msg += f" Considera questi turni lavorativi: {st.session_state.pdf_text[:500]}"
            
            res_ai = client.chat.completions.create(
                messages=[{"role": "system", "content": sys_msg}] + st.session_state.msgs,
                model="llama-3.1-8b-instant"
            )
            st.session_state.msgs.append({"role": "assistant", "content": res_ai.choices[0].message.content})

        if "msgs" in st.session_state:
            for m in st.session_state.msgs:
                with st.chat_message(m["role"]): st.write(m["content"])

    st.markdown("---")
    st.caption("📍 Sviluppato in Spagna | 🛡️ Dati a Zurigo (CH) | 🏥 TurnoSano AI v1.2")
