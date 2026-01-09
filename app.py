import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client, Client
from groq import Groq
from PyPDF2 import PdfReader
import streamlit_authenticator as stauth

# --- 1. CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥", layout="wide")

# CSS per rendere l'interfaccia più professionale
st.markdown("""
    <style>
        .stButton>button { border-radius: 20px; font-weight: bold; width: 100%; height: 3em; background-color: #007bff; color: white; }
        .stChatMessage { border-radius: 15px; }
        [data-testid="stExpander"] { border-radius: 15px; background-color: #f8f9fa; border: 1px solid #dee2e6; }
    </style>
""", unsafe_allow_html=True)

# --- 2. CONNESSIONE SUPABASE ---
try:
    URL_DB = st.secrets["SUPABASE_URL"]
    KEY_DB = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(URL_DB, KEY_DB)
except Exception as e:
    st.error("Errore: Credenziali Supabase non trovate nei Secrets!")
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
    Risolve l'errore 405 forzando i tipi di dato Python nativi.
    """
    try:
        payload = {
            "user_id": str(username),
            "fatica": int(fatica),
            "ore_sonno": float(sonno)
        }
        supabase.table("wellness").insert(payload).execute()
        return True
    except Exception as e:
        st.error(f"Errore durante il salvataggio: {e}")
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
        try:
            res_reg = authenticator.register_user(pre_authorized=None)
            if res_reg:
                username, user_info = res_reg
                if username:
                    salva_nuovo_utente(username, user_info['name'], user_info['password'])
                    st.success('Account creato! Ora puoi accedere.')
                    st.session_state.config = carica_credenziali()
        except Exception as e: st.error(f"Errore registrazione: {e}")
            
    with t1:
        authenticator.login()
        if st.session_state.get("authentication_status"): st.rerun()

else:
    # --- 5. DASHBOARD PRINCIPALE ---
    if "messages" not in st.session_state: st.session_state.messages = []
    if "testo_turno" not in st.session_state: st.session_state.testo_turno = ""

    with st.sidebar:
        st.write(f"Utente: **{st.session_state['name']}**")
        if authenticator.logout('Disconnetti', 'sidebar'): 
            st.session_state.messages = []
            st.rerun()
        st.divider()
        file_pdf = st.file_uploader("📂 Carica il tuo Turno (PDF)", type="pdf")
        if file_pdf:
            reader = PdfReader(file_pdf)
            st.session_state.testo_turno = "".join([p.extract_text() or "" for p in reader.pages])
            st.success("Turno analizzato con successo!")

    st.title("🏥 TurnoSano AI")
    st.info("Benvenuto! Registra il tuo stato fisico per monitorare il tuo benessere lavorativo.")

    # REGISTRAZIONE DATI (Risoluzione Errore 405)
    with st.expander("📝 Registra come stai oggi"):
        c1, c2 = st.columns(2)
        f_val = c1.slider("Grado di Fatica (1-10)", 1, 10, 5)
        s_val = c2.number_input("Ore di Sonno (es. 7.5)", 0.0, 20.0, 7.0, step=0.5)
        if st.button("💾 Salva nel Diario"):
            if salva_benessere(st.session_state['username'], f_val, s_val):
                st.success("Dati memorizzati correttamente!")
                st.rerun()

    # VISUALIZZAZIONE GRAFICI
    df = carica_dati_benessere(st.session_state['username'])
    if not df.empty:
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            fig_f = px.line(df, x='created_at', y='fatica', title="Andamento Fatica", markers=True)
            st.plotly_chart(fig_f, use_container_width=True)
        with col_g2:
            fig_s = px.bar(df, x='created_at', y='ore_sonno', title="Ore Sonno per Giorno")
            st.plotly_chart(fig_s, use_container_width=True)
    else:
        st.warning("Nessun dato disponibile. Inizia salvando il tuo primo stato fisico!")

    # --- 6. COACH AI (GROQ) ---
    st.divider()
    st.subheader("💬 Coach AI per Infermieri")

    try:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
    except:
        st.error("GROQ_API_KEY non trovata!")
        st.stop()

    def chiedi_coach(testo):
        st.session_state.messages.append({"role": "user", "content": testo})
        istruzioni = f"Sei TurnoSano AI, un coach esperto nel benessere degli infermieri. Utente: {st.session_state['name']}."
        if st.session_state.testo_turno:
            istruzioni += f"\nContesto Turno: {st.session_state.testo_turno[:1000]}"
        
        try:
            res = client.chat.completions.create(
                messages=[{"role": "system", "content": istruzioni}] + st.session_state.messages,
                model="llama-3.1-8b-instant",
            )
            st.session_state.messages.append({"role": "assistant", "content": res.choices[0].message.content})
        except Exception as e: st.error(f"Errore Coach: {e}")

    # Pulsanti Rapidi
    tr1, tr2, tr3 = st.columns(3)
    p_veloce = None
    if tr1.button("🌙 SOS Notte"): p_veloce = "Come prepararsi a un turno di notte?"
    if tr2.button("🥗 Alimentazione"): p_veloce = "Consigli su cosa mangiare dopo il turno."
    if tr3.button("🧹 Pulisci Chat"): 
        st.session_state.messages = []
        st.rerun()

    chat_input = st.chat_input("Chiedi qualcosa al coach...")
    prompt_finale = chat_input or p_veloce
    if prompt_finale:
        chiedi_coach(prompt_finale)

    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
