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
        # Restituisce un dizionario formattato per l'authenticator
        return {u["username"]: {"name": u["name"], "password": u["password"]} for u in res.data}
    except:
        return {}

# Inizializzazione Session State
if "user_db" not in st.session_state:
    st.session_state.user_db = load_users()

if "auth_mode" not in st.session_state:
    st.session_state.auth_mode = "login"

# --- 2. CONFIGURAZIONE AUTENTICATORE ---
auth = stauth.Authenticate(
    {"usernames": st.session_state.user_db},
    "turnosano_cookie",
    "turnosano_key",
    30
)

# --- 3. LOGICA DI ACCESSO / REGISTRAZIONE ---
if not st.session_state.get("authentication_status"):
    st.title("🏥 TurnoSano AI")
    
    # Placeholder per gestire il passaggio pulito tra Login e Registrazione
    login_placeholder = st.empty()

    if st.session_state.auth_mode == "login":
        with login_placeholder.container():
            # Il widget di login di streamlit-authenticator
            auth.login(location='main')
            
            if st.session_state["authentication_status"] is False:
                st.error("Username o password errati.")
            
            st.write("---")
            if st.button("Non hai un account? Iscriviti qui"):
                st.session_state.auth_mode = "iscrizione"
                st.rerun()

    elif st.session_state.auth_mode == "iscrizione":
        with login_placeholder.container():
            st.subheader("📝 Registrazione Nuovo Utente")
            with st.form("registration_form"):
                new_user = st.text_input("Username (per il login)")
                new_name = st.text_input("Nome Visualizzato (es. Mario)")
                new_pw = st.text_input("Password", type="password")
                confirm_pw = st.text_input("Conferma Password", type="password")
                
                st.markdown("---")
                st.info("🛡️ **Privacy:** I tuoi dati sono protetti a Zurigo (CH).")
                privacy_check = st.checkbox("Accetto la Privacy Policy e il trattamento dei dati personali.")

                submit_reg = st.form_submit_button("Crea Account")
                
                if submit_reg:
                    if not privacy_check:
                        st.error("Devi accettare la privacy per procedere.")
                    elif not new_user or not new_pw or not new_name:
                        st.warning("Compila tutti i campi obbligatori.")
                    elif new_pw != confirm_pw:
                        st.error("Le password non coincidono.")
                    elif len(new_pw) < 6:
                        st.error("La password deve avere almeno 6 caratteri.")
                    elif new_user in st.session_state.user_db:
                        st.error("Questo Username è già occupato.")
                    else:
                        hashed_pw = stauth.Hasher.hash(new_pw)
                        try:
                            sb.table("profiles").insert({
                                "username": new_user,
                                "name": new_name,
                                "password": hashed_pw
                            }).execute()
                            st.success("✅ Account creato con successo!")
                            st.session_state.user_db = load_users() # Ricarica il DB utenti
                            st.info("Ora clicca su 'Torna al Login' per entrare.")
                        except Exception as e:
                            st.error(f"Errore database: {e}")
            
            if st.button("Torna al Login"):
                st.session_state.auth_mode = "login"
                st.rerun()

else:
    # --- 4. AREA RISERVATA (UTENTE LOGGATO) ---
    st.sidebar.title(f"👋 {st.session_state['name']}")
    
    # Sezione Privacy e Diritto all'oblio
    with st.sidebar.expander("⚖️ Note Legali e Account"):
        st.caption("Server: Zurigo (CH) | Sviluppo: Spagna")
        st.write("App protetta da crittografia e RLS.")
        if st.checkbox("Voglio eliminare i miei dati"):
            if st.button("Elimina definitivamente"):
                try:
                    sb.table("wellness").delete().eq("user_id", st.session_state['username']).execute()
                    sb.table("profiles").delete().eq("username", st.session_state['username']).execute()
                    st.success("Dati eliminati.")
                    for key in list(st.session_state.keys()): del st.session_state[key]
                    st.rerun()
                except Exception as e: st.error(f"Errore: {e}")

    auth.logout('Esci', 'sidebar')
    
    # PDF Turni
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
            f_val = c1.slider("Livello Fatica (1-10)", 1, 10, 5)
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
                except Exception as e: st.error(f"Errore: {e}")

    # --- 6. GRAFICI ---
    st.subheader("📊 Andamento Settimanale")
    try:
        res = sb.table("wellness").select("*").filter("user_id", "eq", st.session_state['username']).execute()
        if res.data:
            df = pd.DataFrame(res.data)
            df['created_at'] = pd.to_datetime(df['created_at'])
            
            # Fix Fuso Orario per filtro 7 giorni
            utc = pytz.UTC
            limite = datetime.now(utc) - timedelta(days=7)
            df_week = df[df['created_at'] > limite]
            
            m1, m2 = st.columns(2)
            m1.metric("Media Fatica", f"{df_week['fatica'].mean():.1f}/10")
            m2.metric("Media Sonno", f"{df_week['ore_sonno'].mean():.1f}h")

            fig = go.Figure()
            df_plot = df.sort_values('created_at').tail(14)
            fig.add_trace(go.Scatter(x=df_plot['created_at'], y=df_plot['fatica'], name="Fatica", line=dict(color='red', width=3)))
            fig.add_trace(go.Scatter(x=df_plot['created_at'], y=df_plot['ore_sonno'], name="Sonno", line=dict(color='blue', width=3)))
            fig.update_layout(height=350, template="plotly_white", margin=dict(l=0,r=0,t=10,b=0))
            st.plotly_chart(fig, use_container_width=True)
    except: st.info("Benvenuto! Inserisci i dati per generare i grafici.")

    # --- 7. COACH IA E COMANDI RAPIDI ---
    st.divider()
    st.subheader("🔬 Coach Scientifico Personalizzato")
    
    if "GROQ_API_KEY" in st.secrets:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        
        # Comandi Rapidi
        st.write("💡 **Azioni Rapide:**")
        col1, col2, col3 = st.columns(3)
        p_rapido = None
        if col1.button("🌙 Recupero Post-Notte"): p_rapido = "Consigli scientifici per recuperare dopo la notte."
        if col2.button("🥗 Dieta Turnista"): p_rapido = "Alimentazione ideale per chi lavora di notte."
        if col3.button("🗑️ Reset Chat"): 
            st.session_state.msgs = []
            st.rerun()

        chat_in = st.chat_input("Fai una domanda al coach...")
        q = p_rapido if p_rapido else chat_in

        if q:
            if "msgs" not in st.session_state: st.session_state.msgs = []
            st.session_state.msgs.append({"role": "user", "content": q})
            
            sys_msg = "Sei un esperto in cronobiologia. Aiuta i turnisti a stare meglio. Sii breve e scientifico."
            if "pdf_text" in st.session_state:
                sys_msg += f" Considera questi turni: {st.session_state.pdf_text[:500]}"
            
            res_ai = client.chat.completions.create(
                messages=[{"role": "system", "content": sys_msg}] + st.session_state.msgs,
                model="llama-3.1-8b-instant"
            )
            st.session_state.msgs.append({"role": "assistant", "content": res_ai.choices[0].message.content})

        if "msgs" in st.session_state:
            for m in st.session_state.msgs:
                with st.chat_message(m["role"]): st.write(m["content"])

    st.markdown("---")
    st.caption("📍 Sviluppato in Spagna | 🛡️ Dati a Zurigo (CH) | 🏥 TurnoSano AI")
