import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client, Client
from groq import Groq
from PyPDF2 import PdfReader
import streamlit_authenticator as stauth

# --- 1. CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥", layout="wide")

# CSS Personalizzato
st.markdown("""
    <style>
        .stButton>button { border-radius: 20px; font-weight: bold; width: 100%; }
        .stChatMessage { border-radius: 15px; }
        .stSlider { padding-top: 10px; }
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
        supabase.table("profiles").insert({
            "username": str(username), 
            "name": str(name), 
            "password": str(password_hash)
        }).execute()
    except Exception as e: st.error(f"Errore registrazione DB: {e}")

def salva_benessere(username, fatica, sonno):
    """
    Funzione critica: converte i dati in tipi Python puri 
    per evitare l'errore 'JSON could not be generated' (405).
    """
    try:
        # PULIZIA DATI
        dati_puliti = {
            "user_id": str(username),
            "fatica": int(fatica),
            "ore_sonno": float(sonno)
        }
        # INVIO
        supabase.table("wellness").insert(dati_puliti).execute()
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

# Pagina di Login/Registrazione
if not st.session_state.get("authentication_status"):
    t1, t2 = st.tabs(["Accedi 🔑", "Iscriviti 📝"])
    with t2:
        try:
            res_reg = authenticator.register_user(pre_authorized=None)
            if res_reg:
                username, user_info = res_reg
                if username:
                    salva_nuovo_utente(username, user_info['name'], user_info['password'])
                    st.success('Registrazione avvenuta! Ora puoi accedere.')
                    st.session_state.config = carica_credenziali()
        except Exception as e: st.error(f"Errore: {e}")
            
    with t1:
        authenticator.login()
        if st.session_state.get("authentication_status"): st.rerun()

else:
    # --- 5. AREA RISERVATA (LOGGATO) ---
    if "messages" not in st.session_state: st.session_state.messages = []
    if "testo_turno" not in st.session_state: st.session_state.testo_turno = ""

    with st.sidebar:
        st.title("👨‍⚕️ Menù")
        st.write(f"In servizio: **{st.session_state['name']}**")
        if authenticator.logout('Esci', 'sidebar'): 
            st.session_state.messages = []
            st.rerun()
        st.divider()
        file_pdf = st.file_uploader("📂 Carica Turno (PDF)", type="pdf")
        if file_pdf:
            reader = PdfReader(file_pdf)
            st.session_state.testo_turno = "".join([p.extract_text() or "" for p in reader.pages])
            st.success("Turno analizzato!")

    st.title("🏥 TurnoSano AI")
    st.write("Monitora il tuo benessere e ottimizza i tuoi turni.")

    # --- REGISTRAZIONE STATO FISICO ---
    with st.expander("📝 Come stai oggi? Registra i tuoi parametri"):
        c1, c2 = st.columns(2)
        with c1:
            f_val = st.slider("Livello di Fatica (1=Riposato, 10=Esausto)", 1, 10, 5)
        with c2:
            s_val = st.number_input("Ore di Sonno effettive", 0.0, 16.0, 7.0, step=0.5)
        
        if st.button("💾 Salva Dati Giornalieri"):
            if salva_benessere(st.session_state['username'], f_val, s_val):
                st.success("Dati salvati con successo!")
                st.rerun()

    # --- VISUALIZZAZIONE DATI ---
    df = carica_dati_benessere(st.session_state['username'])
    if not df.empty:
        st.subheader("📈 Il tuo andamento")
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            fig_f = px.line(df, x='created_at', y='fatica', title="Fatica nel tempo", markers=True, color_discrete_sequence=['#FF4B4B'])
            st.plotly_chart(fig_f, use_container_width=True)
        with col_g2:
            fig_s = px.bar(df, x='created_at', y='ore_sonno', title="Ore di Sonno", color_discrete_sequence=['#00CC96'])
            st.plotly_chart(fig_s, use_container_width=True)
    else:
        st.info("Non ci sono ancora dati. Registra la tua prima giornata sopra!")

    # --- COACH AI (GROQ) ---
    st.divider()
    st.subheader("💬 Coach AI Benessere")

    try:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
    except:
        st.error("Errore: Chiave API Groq non configurata correttamente.")
        st.stop()

    def chiedi_coach(prompt_utente):
        st.session_state.messages.append({"role": "user", "content": prompt_utente})
        # Sistema di istruzioni
        istruzioni = "Sei TurnoSano AI, un coach esperto per infermieri turnisti. Sii empatico e pratico."
        if st.session_state.testo_turno:
            istruzioni += f"\nContesto turno dell'utente: {st.session_state.testo_turno[:1000]}"
        
        try:
            risposta = client.chat.completions.create(
                messages=[{"role": "system", "content": istruzioni}] + st.session_state.messages,
                model="llama-3.1-8b-instant",
            )
            st.session_state.messages.append({"role": "assistant", "content": risposta.choices[0].message.content})
        except Exception as e:
            st.error(f"Errore AI: {e}")

    # Prompt Rapidi
    tr1, tr2, tr3 = st.columns(3)
    p_rapido = None
    if tr1.button("🌙 SOS Turno Notte"): p_rapido = "Ho un turno di notte tra poco, come mi preparo?"
    if tr2.button("🥗 Snack Energetici"): p_rapido = "Cosa posso mangiare di sano durante un turno intenso?"
    if tr3.button("🗑️ Svuota Chat"): 
        st.session_state.messages = []
        st.rerun()

    input_testo = st.chat_input("Scrivi qui la tua domanda...")
    query_finale = input_testo or p_rapido
    
    if query_finale:
        chiedi_coach(query_finale)

    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
