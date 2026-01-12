import streamlit as st
import pandas as pd
from supabase import create_client, Client
from groq import Groq
from PyPDF2 import PdfReader
import streamlit_authenticator as stauth

# --- 1. CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥", layout="centered")

# Inizializzazione sicura del database
def init_supabase():
    try:
        # Pulisce l'URL da eventuali spazi o slash finali che causano errori 404/405
        url = st.secrets["SUPABASE_URL"].strip().rstrip('/')
        key = st.secrets["SUPABASE_KEY"].strip()
        return create_client(url, key)
    except Exception as e:
        st.error(f"Errore nei Secrets: {e}")
        st.stop()

sb = init_supabase()

# --- 2. FUNZIONI DI SUPPORTO ---
def get_auth_config():
    try:
        res = sb.table("profiles").select("*").execute()
        utenti = {u["username"]: {"name": u["name"], "password": u["password"]} for u in res.data}
        return {"credentials": {"usernames": utenti}}
    except:
        return {"credentials": {"usernames": {}}}

# --- 3. GESTIONE AUTENTICAZIONE (v0.3.0+) ---
if "config" not in st.session_state:
    st.session_state.config = get_auth_config()

auth = stauth.Authenticate(
    st.session_state.config['credentials'],
    "ts_cookie",
    "signature_key_2026",
    30
)

if not st.session_state.get("authentication_status"):
    t_login, t_reg = st.tabs(["Accedi 🔑", "Iscriviti 📝"])
    
    with t_login:
        auth.login(location='main')
        if st.session_state["authentication_status"] is False:
            st.error("Credenziali errate.")
    
    with t_reg:
        try:
            res_reg = auth.register_user(location='main')
            if res_reg and res_reg[0]:
                sb.table("profiles").insert({
                    "username": str(res_reg[0]), 
                    "name": str(res_reg[1]['name']), 
                    "password": str(res_reg[1]['password'])
                }).execute()
                st.success("Registrato! Ora puoi accedere.")
                st.session_state.config = get_auth_config()
        except:
            st.info("Inserisci username e password (min. 6 caratteri).")
else:
    # --- 4. AREA RISERVATA UTENTE ---
    if "msgs" not in st.session_state: st.session_state.msgs = []
    
    st.sidebar.title(f"Ciao {st.session_state['name']}")
    auth.logout('Disconnetti', 'sidebar')
    
    pdf = st.sidebar.file_uploader("Carica Turno (PDF)", type="pdf")
    if pdf:
        reader = PdfReader(pdf)
        st.session_state.pdf_txt = "".join([p.extract_text() for p in reader.pages if p.extract_text()])
        st.sidebar.success("PDF pronto!")

    st.title("🏥 TurnoSano AI")

    # Diario Benessere
    with st.form("wellness_form"):
        st.subheader("📝 Diario del Benessere")
        f_val = st.slider("Livello Fatica (1-10)", 1, 10, 5)
        s_val = st.number_input("Ore Sonno", 0.0, 24.0, 7.0, step=0.5)
        
        if st.form_submit_button("Salva Parametri"):
            try:
                # Payload semplificato per massima compatibilità
                data = {
                    "user_id": str(st.session_state['username']), 
                    "fatica": float(f_val), 
                    "ore_sonno": float(s_val)
                }
                sb.table("wellness").insert(data).execute()
                st.success("Dati registrati correttamente!")
                st.rerun()
            except Exception as e:
                st.error(f"Errore durante il salvataggio: {e}")

    # Storico Semplice (Tabella)
    with st.expander("📂 I tuoi ultimi dati"):
        try:
            res_w = sb.table("wellness").select("*").filter("user_id", "eq", st.session_state['username']).order("created_at", desc=True).limit(10).execute()
            if res_w.data:
                df = pd.DataFrame(res_w.data)
                df['Data'] = pd.to_datetime(df['created_at']).dt.strftime('%d/%m/%Y %H:%M')
                st.table(df[["Data", "fatica", "ore_sonno"]])
            else:
                st.info("Nessun dato registrato nel database.")
        except Exception as e:
            st.error(f"Impossibile caricare lo storico: {e}")

    # --- 5. COACH AI (GROQ) ---
    st.divider()
    st.subheader("💬 Coach AI")
    
    if "GROQ_API_KEY" in st.secrets:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        
        # Comandi Rapidi
        c1, c2, c3 = st.columns(3)
        if c1.button("🌙 SOS Notte"): prompt = "Consigli per il turno di notte."
        elif c2.button("🥗 Dieta"): prompt = "Cosa mangiare per avere energia?"
        elif c3.button("🗑️ Reset"):
            st.session_state.msgs = []
            st.rerun()
        else:
            prompt = st.chat_input("Chiedi aiuto al coach...")

        if prompt:
            st.session_state.msgs.append({"role": "user", "content": prompt})
            
            # Contesto
            context = f"Sei un coach per infermieri. Utente: {st.session_state['name']}."
            if "pdf_txt" in st.session_state: 
                context += f" Turno: {st.session_state.pdf_txt[:300]}"
            
            resp = client.chat.completions.create(
                messages=[{"role": "system", "content": context}] + st.session_state.msgs,
                model="llama-3.1-8b-instant"
            )
            st.session_state.msgs.append({"role": "assistant", "content": resp.choices[0].message.content})

        for m in st.session_state.msgs:
            with st.chat_message(m["role"]): st.write(m["content"])
    else:
        st.warning("Aggiungi GROQ_API_KEY nei Secrets per usare il Coach.")
