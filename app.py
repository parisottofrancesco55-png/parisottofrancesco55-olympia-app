import streamlit as st
import pandas as pd
from supabase import create_client, Client
from groq import Groq
from PyPDF2 import PdfReader
import streamlit_authenticator as stauth

# --- 1. CONFIGURAZIONE ---
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥", layout="centered")

# Funzione connessione sicura (Risolve l'errore 404/JSON)
def connect_db():
    try:
        url = st.secrets["SUPABASE_URL"].strip().rstrip('/')
        key = st.secrets["SUPABASE_KEY"].strip()
        return create_client(url, key)
    except Exception as e:
        st.error(f"Configurazione Secrets incompleta: {e}")
        st.stop()

sb = connect_db()

# --- 2. FUNZIONI DATABASE ---
def get_auth_data():
    try:
        res = sb.table("profiles").select("*").execute()
        utenti = {u["username"]: {"name": u["name"], "password": u["password"]} for u in res.data}
        return {"credentials": {"usernames": utenti}}
    except:
        return {"credentials": {"usernames": {}}}

# --- 3. GESTIONE AUTENTICAZIONE (v0.3.0+) ---
if "config" not in st.session_state:
    st.session_state.config = get_auth_data()

auth = stauth.Authenticate(
    st.session_state.config['credentials'],
    "turnosano_cookie",
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
                st.success("Registrato! Ora puoi accedere dal tab Accedi.")
                st.session_state.config = get_auth_data()
        except:
            st.info("Inserisci username e password (min. 6 caratteri).")
else:
    # --- 4. DASHBOARD UTENTE LOGGATO ---
    if "msgs" not in st.session_state: st.session_state.msgs = []
    if "pdf_txt" not in st.session_state: st.session_state.pdf_txt = ""

    with st.sidebar:
        st.title("👨‍⚕️ Menù")
        st.write(f"In servizio: **{st.session_state['name']}**")
        auth.logout('Esci', 'sidebar')
        st.divider()
        pdf = st.file_uploader("Carica Turno (PDF)", type="pdf")
        if pdf:
            reader = PdfReader(pdf)
            st.session_state.pdf_txt = "".join([p.extract_text() for p in reader.pages if p.extract_text()])
            st.success("PDF caricato!")

    st.title("🏥 TurnoSano AI")

    # Inserimento Dati
    with st.form("wellness_form"):
        st.subheader("📝 Diario del Benessere")
        f_val = st.slider("Fatica (1-10)", 1, 10, 5)
        s_val = st.number_input("Ore Sonno", 0.0, 24.0, 7.0, step=0.5)
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

    # Storico Semplice
    with st.expander("📂 I tuoi ultimi dati"):
        try:
            res_w = sb.table("wellness").select("*").filter("user_id", "eq", st.session_state['username']).order("created_at", desc=True).limit(10).execute()
            if res_w.data:
                df = pd.DataFrame(res_w.data)
                df['Data'] = pd.to_datetime(df['created_at']).dt.strftime('%d/%m/%Y %H:%M')
                st.table(df[["Data", "fatica", "ore_sonno"]])
            else:
                st.info("Nessun dato presente.")
        except Exception as e:
            st.error(f"Errore caricamento storico: {e}")

    # --- 5. COACH AI (GROQ) ---
    st.divider()
    st.subheader("💬 Coach AI")
    
    if "GROQ_API_KEY" in st.secrets:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        
        c1, c2, c3 = st.columns(3)
        p_rapido = None
        if c1.button("🌙 SOS Notte"): p_rapido = "Consigli per il turno di notte."
        if c2.button("🥗 Dieta"): p_rapido = "Cosa mangiare in turno?"
        if c3.button("🗑️ Reset"):
            st.session_state.msgs = []
            st.rerun()

        chat_input = st.chat_input("Chiedi al coach...")
        q = chat_input or p_rapido

        if q:
            st.session_state.msgs.append({"role": "user", "content": q})
            ctx = f"Sei un coach per infermieri. Utente: {st.session_state['name']}."
            if st.session_state.pdf_txt: ctx += f" Turno: {st.session_state.pdf_txt[:400]}"
            
            resp = client.chat.completions.create(
                messages=[{"role": "system", "content": ctx}] + st.session_state.msgs,
                model="llama-3.1-8b-instant"
            )
            st.session_state.msgs.append({"role": "assistant", "content": resp.choices[0].message.content})

        for m in st.session_state.msgs:
            with st.chat_message(m["role"]): st.write(m["content"])
    else:
        st.warning("Configura GROQ_API_KEY nei Secrets.")
