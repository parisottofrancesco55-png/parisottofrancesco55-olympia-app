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
            submit_reg = st.form_submit_button("Crea Account")
            
            if submit_reg:
                if not new_user or not new_pw or not new_name:
                    st.warning("Compila tutti i campi!")
                elif new_pw != confirm_pw:
                    st.error("Le password non coincidono.")
                elif len(new_pw) < 6:
                    st.error("La password deve avere almeno 6 caratteri.")
                elif new_user in st.session_state.user_db:
                    st.error("Username già occupato.")
                else:
                    hashed_pw = stauth.Hasher.hash(new_pw)
                    try:
                        sb.table("profiles").insert({
                            "username": new_user,
                            "name": new_name,
                            "password": hashed_pw
                        }).execute()
                        st.success(f"✅ Utente {new_user} creato! Torna al login.")
                        st.session_state.user_db = load_users()
                    except Exception as e:
                        st.error(f"Errore database: {e}")
        
        if st.button("Torna al Login"):
            st.session_state.auth_mode = "login"
            st.rerun()

else:
    # --- 4. AREA RISERVATA (LOGGED IN) ---
    st.sidebar.title(f"👋 {st.session_state['name']}")
    auth.logout('Esci', 'sidebar')
    
    # Caricamento PDF Turni
    st.sidebar.divider()
    pdf_file = st.sidebar.file_uploader("📅 Carica Turno (PDF)", type="pdf")
    if pdf_file:
        reader = PdfReader(pdf_file)
        st.session_state.pdf_text = "".join([p.extract_text() for p in reader.pages if p.extract_text()])
        st.sidebar.success("Turno analizzato!")

    st.title("🏥 Dashboard Benessere Operatori")

    # --- 5. INSERIMENTO DATI ---
    with st.expander("📝 Diario del Benessere - Inserisci dati oggi", expanded=True):
        with st.form("wellness_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            f_val = c1.slider("Livello Fatica (1=Riposato, 10=Esausto)", 1, 10, 5)
            s_val = c2.number_input("Ore di sonno effettive", 0.0, 24.0, 7.0, step=0.5)
            if st.form_submit_button("Salva Parametri"):
                try:
                    sb.table("wellness").insert({
                        "user_id": st.session_state['username'], 
                        "fatica": float(f_val), 
                        "ore_sonno": float(s_val)
                    }).execute()
                    st.success("Dati salvati!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Errore salvataggio: {e}")

    # --- 6. ANALISI DATI E GRAFICI ---
    st.subheader("📊 I tuoi progressi settimanali")
    try:
        res = sb.table("wellness").select("*").filter("user_id", "eq", st.session_state['username']).execute()
        
        if res.data and len(res.data) > 0:
            df = pd.DataFrame(res.data)
            df['created_at'] = pd.to_datetime(df['created_at'])
            
            # Calcolo KPI con gestione fuso orario (pytz)
            utc = pytz.UTC
            ora_attuale = datetime.now(utc)
            settimana_fa = ora_attuale - timedelta(days=7)
            
            df_week = df[df['created_at'] > settimana_fa]
            
            avg_f = df_week['fatica'].mean() if not df_week.empty else 0
            avg_s = df_week['ore_sonno'].mean() if not df_week.empty else 0

            # Visualizzazione Metriche
            m1, m2, m3 = st.columns(3)
            m1.metric("Media Fatica (7g)", f"{avg_f:.1f}/10", delta_color="inverse")
            m2.metric("Media Sonno (7g)", f"{avg_s:.1f}h")
            m3.metric("Record Totali", len(df))

            # Grafico Plotly
            df_plot = df.sort_values('created_at').tail(14)
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df_plot['created_at'], y=df_plot['fatica'], name="Fatica", line=dict(color='#d63031', width=3), mode='lines+markers'))
            fig.add_trace(go.Scatter(x=df_plot['created_at'], y=df_plot['ore_sonno'], name="Sonno", line=dict(color='#0984e3', width=3), mode='lines+markers'))
            
            fig.update_layout(
                height=350, 
                template="plotly_white", 
                margin=dict(l=0,r=0,t=20,b=0),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("👋 Benvenuto! Inserisci i tuoi primi dati per vedere grafici e medie settimanali.")
    except Exception as e:
        st.error(f"Errore tecnico caricamento grafici: {e}")

    # --- 7. COACH SCIENTIFICO AI ---
    st.divider()
    st.subheader("🔬 Supporto Scientifico Personalizzato")
    
    if "GROQ_API_KEY" in st.secrets:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        col1, col2, col3 = st.columns(3)
        p_rapido = None
        if col1.button("🌙 Recupero Post-Notte"): p_rapido = "Strategie scientifiche cronobiologiche per recuperare dopo il turno di notte."
        if col2.button("🥗 Nutrizione Notturna"): p_rapido = "Consigli scientifici sull'alimentazione ideale per i turnisti di notte."
        if col3.button("🗑️ Reset Chat"):
            st.session_state.msgs = []
            st.rerun()

        chat_in = st.chat_input("Chiedi al coach (es: gestione luce, caffeina)...")
        q = chat_in or p_rapido

        if q:
            if "msgs" not in st.session_state: st.session_state.msgs = []
            st.session_state.msgs.append({"role": "user", "content": q})
            
            sys_msg = "Sei un esperto in cronobiologia e medicina del lavoro. NON sei un medico. Dai consigli basati su studi scientifici."
            if "pdf_text" in st.session_state:
                sys_msg += f" Considera questi turni dell'utente: {st.session_state.pdf_text[:500]}"
            
            res_ai = client.chat.completions.create(
                messages=[{"role": "system", "content": sys_msg}] + st.session_state.msgs,
                model="llama-3.1-8b-instant"
            )
            st.session_state.msgs.append({"role": "assistant", "content": res_ai.choices[0].message.content})

        if "msgs" in st.session_state:
            for m in st.session_state.msgs:
                with st.chat_message(m["role"]): st.write(m["content"])
