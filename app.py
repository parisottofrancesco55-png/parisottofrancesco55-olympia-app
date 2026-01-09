import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client, Client
from groq import Groq
from PyPDF2 import PdfReader
import streamlit_authenticator as stauth

# --- 1. CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥", layout="wide")

st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        .stButton>button { border-radius: 20px; font-weight: bold; width: 100%; height: 3em; }
        .stChatMessage { border-radius: 15px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. CONNESSIONE SUPABASE ---
try:
    URL_DB = st.secrets["SUPABASE_URL"]
    KEY_DB = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(URL_DB, KEY_DB)
except Exception as e:
    st.error("Errore: Credenziali Supabase mancanti nei Secrets!")
    st.stop()

# --- 3. FUNZIONI DATABASE ---
def carica_credenziali():
    try:
        res = supabase.table("profiles").select("*").execute()
        credenziali = {"usernames": {}}
        for u in res.data:
            credenziali["usernames"][u["username"]] = {"name": u["name"], "password": u["password"]}
        return credenziali
    except: return {"usernames": {}}

def salva_nuovo_utente(username, name, password_hash):
    try:
        supabase.table("profiles").insert({"username": username, "name": name, "password": password_hash}).execute()
    except Exception as e: st.error(f"Errore registrazione: {e}")

def salva_benessere(username, fatica, sonno):
    try:
        # PULIZIA DATI PER EVITARE ERRORE 405 JSON
        payload = {
            "user_id": str(username),
            "fatica": int(fatica),
            "ore_sonno": float(sonno)
        }
        supabase.table("wellness").insert(payload).execute()
        return True
    except Exception as e:
        st.error(f"Errore database: {e}")
        return False

def carica_dati_benessere(username):
    try:
        res = supabase.table("wellness").select("*").filter("user_id", "eq", username).order("created_at").execute()
        return pd.DataFrame(res.data)
    except: return pd.DataFrame()

# --- 4. GESTIONE AUTENTICAZIONE ---
if "config" not in st.session_state:
    st.session_state.config = carica_credenziali()

authenticator = stauth.Authenticate(
    st.session_state.config,
    "turnosano_cookie",
    "auth_key",
    cookie_expiry_days=30
)

if not st.session_state.get("authentication_status"):
    t1, t2 = st.tabs(["Accedi 🔑", "Iscriviti 📝"])
    with t2:
        res_reg = authenticator.register_user(pre_authorized=None)
        if res_reg:
            u, info = res_reg
            salva_nuovo_utente(u, info['name'], info['password'])
            st.success('Registrato! Accedi ora.')
            st.session_state.config = carica_credenziali()
    with t1:
        authenticator.login()
        if st.session_state.get("authentication_status"): st.rerun()

else:
    # --- 5. AREA RISERVATA (LOGGATO) ---
    if "messages" not in st.session_state: st.session_state.messages = []
    if "testo_turno" not in st.session_state: st.session_state.testo_turno = ""

    # Sidebar
    with st.sidebar:
        st.write(f"In servizio: **{st.session_state['name']}** 👋")
        if authenticator.logout('Esci', 'sidebar'): 
            st.session_state.messages = []
            st.rerun()
        st.divider()
        file_pdf = st.file_uploader("📂 Carica Turno PDF", type="pdf")
        if file_pdf:
            reader = PdfReader(file_pdf)
            st.session_state.testo_turno = "".join([p.extract_text() or "" for p in reader.pages])
            st.success("Turno analizzato!")

    st.title("🏥 TurnoSano Dashboard")

    # --- REGISTRAZIONE STATO FISICO ---
    with st.expander("📝 Come stai oggi?"):
        c1, c2 = st.columns(2)
        f_val = c1.slider("Livello di Fatica (1-10)", 1, 10, 5)
        s_val = c2.number_input("Ore di Sonno", 0.0, 15.0, 7.0)
        if st.button("Salva Dati Giornalieri"):
            if salva_benessere(st.session_state['username'], f_val, s_val):
                st.success("Dati salvati con successo!")
                st.rerun()

    # --- ANALISI GRAFICA ---
    df = carica_dati_benessere(st.session_state['username'])
    if not df.empty:
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            fig_f = px.line(df, x='created_at', y='fatica', title="Trend Fatica", markers=True)
            st.plotly_chart(fig_f, use_container_width=True)
        with col_g2:
            fig_s = px.bar(df, x='created_at', y='ore_sonno', title="Trend Sonno")
            st.plotly_chart(fig_s, use_container_width=True)
    else:
        st.info("Nessun dato registrato. Inizia oggi per monitorare il tuo benessere!")

    # --- COACH AI (GROQ) ---
    st.divider()
    st.subheader("💬 Coach TurnoSano AI")

    try:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
    except:
        st.error("GROQ_API_KEY mancante!")
        st.stop()

    # Funzione per gestire la chat
    def chiedi_coach(testo):
        st.session_state.messages.append({"role": "user", "content": testo})
        context = f"Sei TurnoSano AI, esperto di salute per infermieri. Utente: {st.session_state['name']}."
        if st.session_state.testo_turno:
            context += f"\nContesto Turno PDF: {st.session_state.testo_turno[:800]}"
        
        try:
            res = client.chat.completions.create(
                messages=[{"role": "system", "content": context}] + st.session_state.messages,
                model="llama-3.1-8b-instant",
            )
            st.session_state.messages.append({"role": "assistant", "content": res.choices[0].message.content})
        except Exception as e:
            st.error(f"Errore Coach: {e}")

    # Tasti Rapidi
    tr1, tr2, tr3 = st.columns(3)
    p_rapido = None
    if tr1.button("🌙 SOS Notte"): p_rapido = "Consigli per il turno di notte."
    if tr2.button("🥗 Dieta Turnista"): p_rapido = "Cosa dovrei mangiare per non sentirmi stanco?"
    if tr3.button("🗑️ Reset Chat"): 
        st.session_state.messages = []
        st.rerun()

    # Input Libero
    user_input = st.chat_input("Chiedi aiuto al coach o incolla un turno...")
    
    # Esecuzione (priorità all'input manuale, poi ai bottoni)
    final_query = user_input or p_rapido
    if final_query:
        chiedi_coach(final_query)

    # Visualizzazione Messaggi
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
