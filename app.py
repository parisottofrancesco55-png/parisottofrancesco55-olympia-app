import streamlit as st
import pandas as pd
from supabase import create_client, Client
from groq import Groq
from PyPDF2 import PdfReader
import streamlit_authenticator as stauth

# --- 1. CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥", layout="centered")

# --- 2. CONNESSIONE SUPABASE ---
try:
    sb: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error("Errore: Credenziali Supabase mancanti nei Secrets.")
    st.stop()

# --- 3. FUNZIONI DATABASE ---
def carica_config_utenti():
    """Recupera gli utenti dal DB e li formatta per la nuova versione dell'authenticator"""
    try:
        res = sb.table("profiles").select("*").execute()
        utenti = {u["username"]: {"name": u["name"], "password": u["password"]} for u in res.data}
        return {"credentials": {"usernames": utenti}}
    except:
        return {"credentials": {"usernames": {}}}

def salva_benessere(u, f, s):
    try:
        sb.table("wellness").insert({"user_id": str(u), "fatica": int(f), "ore_sonno": float(s)}).execute()
        return True
    except:
        return False

# --- 4. GESTIONE AUTENTICAZIONE (VERSIONE 0.3.0+) ---
if "config" not in st.session_state:
    st.session_state.config = carica_config_utenti()

# Inizializzazione Authenticator (Parametri aggiornati)
auth = stauth.Authenticate(
    st.session_state.config['credentials'],
    "turnosano_cookie",
    "signature_key_2026",
    cookie_expiry_days=30
)

# Schermata di Login/Registrazione
if not st.session_state.get("authentication_status"):
    tab_login, tab_reg = st.tabs(["Accedi 🔑", "Iscriviti 📝"])
    
    with tab_login:
        # La funzione login() gestisce internamente la visualizzazione
        auth.login(location='main')
        if st.session_state["authentication_status"] is False:
            st.error("Username o Password errati.")
        elif st.session_state["authentication_status"] is None:
            st.warning("Inserisci le tue credenziali.")

    with tab_reg:
        try:
            # register_user non accetta più pre_authorized nelle nuove versioni
            res_reg = auth.register_user(location='main')
            if res_reg:
                new_username, user_info = res_reg
                if new_username:
                    sb.table("profiles").insert({
                        "username": str(new_username),
                        "name": str(user_info['name']),
                        "password": str(user_info['password'])
                    }).execute()
                    st.success("Registrazione completata! Ora puoi accedere.")
                    # Aggiorna la sessione con il nuovo utente
                    st.session_state.config = carica_config_utenti()
        except Exception as e:
            st.info("Scegli un username e una password valida (min. 6 caratteri).")

else:
    # --- 5. DASHBOARD UTENTE LOGGATO ---
    if "messages" not in st.session_state: st.session_state.messages = []
    if "turno_testo" not in st.session_state: st.session_state.turno_testo = ""

    with st.sidebar:
        st.title("👨‍⚕️ Area Personale")
        st.write(f"Benvenuto, **{st.session_state['name']}**")
        auth.logout('Esci', 'sidebar')
        st.divider()
        pdf_file = st.file_uploader("📂 Carica Turno PDF", type="pdf")
        if pdf_file:
            reader = PdfReader(pdf_file)
            st.session_state.turno_testo = "".join([p.extract_text() for p in reader.pages if p.extract_text()])
            st.success("Turno analizzato!")

    st.title("🏥 TurnoSano AI")

    # Diario Benessere (Senza Grafici)
    with st.form("diario_form"):
        st.subheader("📝 Il tuo stato oggi")
        fatica = st.slider("Fatica (1=Riposato, 10=Esausto)", 1, 10, 5)
        sonno = st.number_input("Ore di sonno", 0.0, 24.0, 7.0, step=0.5)
        if st.form_submit_button("Salva Parametri"):
            if salva_benessere(st.session_state['username'], fatica, sonno):
                st.success("Dati salvati correttamente!")

    # Storico Semplice
    with st.expander("📂 Vedi i tuoi ultimi dati"):
        res_w = sb.table("wellness").select("*").filter("user_id", "eq", st.session_state['username']).order("created_at", desc=True).limit(5).execute()
        if res_w.data:
            st.table(pd.DataFrame(res_w.data)[["created_at", "fatica", "ore_sonno"]])
        else:
            st.info("Nessun dato registrato.")

    # --- 6. COACH AI (GROQ) ---
    st.divider()
    st.subheader("💬 Coach AI")
    
    if "GROQ_API_KEY" in st.secrets:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        
        # Comandi Rapidi
        c1, c2, c3 = st.columns(3)
        p_rapido = None
        if c1.button("🌙 SOS Notte"): p_rapido = "Consigli per gestire il turno di notte."
        if c2.button("🥗 Dieta"): p_rapido = "Cosa mangiare per non avere cali di energia?"
        if c3.button("🗑️ Reset Chat"):
            st.session_state.messages = []
            st.rerun()

        chat_in = st.chat_input("Chiedi al Coach...")
        final_query = chat_in or p_rapido

        if final_query:
            st.session_state.messages.append({"role": "user", "content": final_query})
            ctx = f"Sei un coach per infermieri. Utente: {st.session_state['name']}."
            if st.session_state.turno_testo:
                ctx += f" Contesto turno: {st.session_state.turno_testo[:500]}"
            
            res_ai = client.chat.completions.create(
                messages=[{"role": "system", "content": ctx}] + st.session_state.messages,
                model="llama-3.1-8b-instant"
            )
            st.session_state.messages.append({"role": "assistant", "content": res_ai.choices[0].message.content})

        for m in st.session_state.messages:
            with st.chat_message(m["role"]): st.write(m["content"])
    else:
        st.warning("Configura GROQ_API_KEY nei Secrets.")
