import streamlit as st
import pandas as pd
from supabase import create_client, Client
from groq import Groq
from PyPDF2 import PdfReader
import streamlit_authenticator as stauth
import plotly.graph_objects as go
from datetime import datetime, timedelta
import pytz

# --- 1. CONFIGURAZIONE INIZIALE ---
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥", layout="wide")

def init_db():
    """Inizializza la connessione a Supabase"""
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

sb = init_db()

def load_users():
    """Carica gli utenti dal DB e li formatta per l'autenticatore"""
    try:
        res = sb.table("profiles").select("*").execute()
        return {"usernames": {u["username"]: {"name": u["name"], "password": u["password"]} for u in res.data}}
    except:
        return {"usernames": {}}

# Gestione della modalità Login o Registrazione
if "auth_mode" not in st.session_state:
    st.session_state.auth_mode = "login"

# Caricamento utenti in tempo reale
user_db = load_users()

# --- 2. SISTEMA DI AUTENTICAZIONE (Versione 0.3.1) ---
auth = stauth.Authenticate(
    user_db,
    "turnosano_cookie", # Nome del cookie salvato nel browser
    "turnosano_key",    # Chiave di cifratura
    0  # 0 giorni: non ti 'ricorda' se chiudi il browser, risolve il problema del login bloccato
)

# --- 3. LOGICA DI ACCESSO / REGISTRAZIONE ---
if not st.session_state.get("authentication_status"):
    
    if st.session_state.auth_mode == "login":
        st.title("🏥 TurnoSano AI - Accedi")
        auth.login(location='main')
        
        if st.session_state["authentication_status"] is False:
            st.error("Username o password errati.")
        
        st.write("---")
        # Pulsante per cambiare in modalità registrazione
        if st.button("Non hai un account? Crea un nuovo profilo"):
            st.session_state.auth_mode = "iscrizione"
            st.rerun()

    else:
        st.title("📝 Registrazione Nuovo Operatore")
        with st.form("reg_form"):
            new_u = st.text_input("Scegli Username (unico)").lower().strip()
            new_n = st.text_input("Tuo Nome e Cognome")
            new_p = st.text_input("Password", type="password")
            conf_p = st.text_input("Conferma Password", type="password")
            
            st.markdown("---")
            st.info("🛡️ **Note sulla Privacy:** I tuoi dati sanitari (sonno/fatica) sono salvati a Zurigo (Svizzera) e protetti dal GDPR. Non verranno ceduti a terzi.")
            privacy = st.checkbox("Accetto la Privacy Policy e il trattamento dei dati.")
            
            if st.form_submit_button("Crea Account"):
                if not privacy:
                    st.error("Devi accettare la privacy per iscriverti.")
                elif new_p != conf_p:
                    st.error("Le password non coincidono.")
                elif new_u in user_db["usernames"]:
                    st.error("Questo Username è già occupato.")
                elif len(new_p) < 6:
                    st.error("La password deve essere di almeno 6 caratteri.")
                else:
                    hashed_pw = stauth.Hasher.hash(new_p)
                    try:
                        sb.table("profiles").insert({"username": new_u, "name": new_n, "password": hashed_pw}).execute()
                        st.success("✅ Account creato! Torna al login per accedere.")
                        st.session_state.auth_mode = "login"
                        # Non facciamo rerun automatico per permettere di leggere il successo
                    except Exception as e:
                        st.error(f"Errore database: {e}")
        
        if st.button("Torna alla pagina di Login"):
            st.session_state.auth_mode = "login"
            st.rerun()

else:
    # --- 4. AREA DASHBOARD (UTENTE LOGGATO) ---
    # Logout nella sidebar per pulire la sessione
    auth.logout('Disconnetti Account', 'sidebar')
    
    st.sidebar.title(f"👋 Benvenuto, {st.session_state['name']}")
    
    # Pulsante speciale per forzare la creazione di un altro account dallo stesso PC
    if st.sidebar.button("➕ Registra un altro profilo"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.session_state.auth_mode = "iscrizione"
        st.rerun()

    # Diritto all'oblio (Cancellazione)
    with st.sidebar.expander("⚖️ Gestione Dati"):
        st.caption("Server: Zurigo (CH)")
        if st.button("Elimina i miei dati"):
            sb.table("wellness").delete().eq("user_id", st.session_state['username']).execute()
            st.warning("Cronologia dati cancellata.")

    # Analisi PDF
    pdf_file = st.sidebar.file_uploader("📅 Carica Turno (PDF)", type="pdf")
    if pdf_file:
        reader = PdfReader(pdf_file)
        st.session_state.pdf_text = "".join([p.extract_text() for p in reader.pages if p.extract_text()])
        st.sidebar.success("Turno analizzato con successo!")

    st.title("📊 Monitoraggio Wellness Operatori")

    # --- 5. INPUT E GRAFICI ---
    col_input, col_graph = st.columns([1, 2])
    
    with col_input:
        st.subheader("📝 Diario Giornaliero")
        with st.form("wellness_data", clear_on_submit=True):
            fatica = st.slider("Livello Fatica (1-10)", 1, 10, 5)
            sonno = st.number_input("Ore di sonno effettive", 0.0, 24.0, 7.0, step=0.5)
            if st.form_submit_button("Salva nel Database"):
                sb.table("wellness").insert({
                    "user_id": st.session_state['username'], 
                    "fatica": float(fatica), 
                    "ore_sonno": float(sonno)
                }).execute()
                st.rerun()

    with col_graph:
        st.subheader("📈 Andamento Parametri")
        try:
            res = sb.table("wellness").select("*").eq("user_id", st.session_state['username']).execute()
            if res.data:
                df = pd.DataFrame(res.data).sort_values('created_at')
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df['created_at'], y=df['fatica'], name="Fatica", line=dict(color='red', width=3)))
                fig.add_trace(go.Scatter(x=df['created_at'], y=df['ore_sonno'], name="Sonno", line=dict(color='blue', width=3)))
                fig.update_layout(height=300, margin=dict(l=0,r=0,t=0,b=0), template="plotly_white")
                st.plotly_chart(fig, use_container_width=True)
        except:
            st.info("Inserisci i tuoi primi dati per generare il grafico.")

    # --- 6. COACH IA CON COMANDI RAPIDI ---
    st.divider()
    st.subheader("🔬 Coach Scientifico IA")
    
    if "GROQ_API_KEY" in st.secrets:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        
        st.write("💡 **Azioni Rapide:**")
        c1, c2, c3 = st.columns(3)
        fast_q = None
        if c1.button("🌙 Recupero Post-Notte"): fast_q = "Consigli scientifici per recuperare dopo la notte."
        if c2.button("🥗 Alimentazione Notturna"): fast_q = "Cosa mangiare per non avere cali di energia nel turno di notte?"
        if c3.button("🗑️ Reset Conversazione"): 
            st.session_state.chat_history = []
            st.rerun()

        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []

        user_chat = st.chat_input("Fai una domanda al Coach...")
        query = fast_q if fast_q else user_chat

        if query:
            st.session_state.chat_history.append({"role": "user", "content": query})
            sys_msg = "Sei un esperto di cronobiologia. Rispondi in modo breve e basato sulla scienza."
            if "pdf_text" in st.session_state:
                sys_msg += f" Considera i turni caricati dall'utente: {st.session_state.pdf_text[:500]}"
            
            res_ai = client.chat.completions.create(
                messages=[{"role": "system", "content": sys_msg}] + st.session_state.chat_history,
                model="llama-3.1-8b-instant"
            )
            st.session_state.chat_history.append({"role": "assistant", "content": res_ai.choices[0].message.content})

        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

    st.markdown("---")
    st.caption("📍 Spagna-Italia | 🛡️ Server: Zurigo (CH) | 🏥 Progetto TurnoSano AI")
