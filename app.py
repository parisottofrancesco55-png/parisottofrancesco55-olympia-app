import streamlit as st
import pandas as pd
from supabase import create_client, Client
from groq import Groq
from PyPDF2 import PdfReader
import streamlit_authenticator as stauth

# --- 1. CONFIGURAZIONE ---
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥")

# --- 2. CONNESSIONE SUPABASE ---
try:
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except:
    st.error("Errore: Credenziali Supabase mancanti!")
    st.stop()

# --- 3. FUNZIONI DATABASE ---
def carica_credenziali():
    try:
        res = supabase.table("profiles").select("*").execute()
        return {"usernames": {u["username"]: {"name": u["name"], "password": u["password"]} for u in res.data}}
    except: return {"usernames": {}}

def salva_benessere(username, fatica, sonno):
    try:
        payload = {"user_id": str(username), "fatica": int(fatica), "ore_sonno": float(sonno)}
        supabase.table("wellness").insert(payload).execute()
        return True
    except Exception as e:
        st.error(f"Errore salvataggio: {e}")
        return False

# --- 4. AUTENTICAZIONE ---
if "config" not in st.session_state:
    st.session_state.config = carica_credenziali()

auth = stauth.Authenticate(st.session_state.config, "ts_cookie", "auth_key", 30)

if not st.session_state.get("authentication_status"):
    t1, t2 = st.tabs(["Accedi 🔑", "Iscriviti 📝"])
    with t2:
        res_reg = auth.register_user(pre_authorized=None)
        if res_reg and res_reg[0]:
            supabase.table("profiles").insert({"username": str(res_reg[0]), "name": str(res_reg[1]['name']), "password": str(res_reg[1]['password'])}).execute()
            st.success('Registrato! Ora puoi accedere.')
    with t1:
        auth.login()
else:
    # --- 5. AREA RISERVATA ---
    if "messages" not in st.session_state: st.session_state.messages = []
    if "testo_turno" not in st.session_state: st.session_state.testo_turno = ""

    with st.sidebar:
        st.title("👨‍⚕️ Menù")
        st.write(f"Utente: **{st.session_state['name']}**")
        auth.logout('Esci', 'sidebar')
        st.divider()
        pdf = st.file_uploader("📂 Carica Turno PDF", type="pdf")
        if pdf:
            reader = PdfReader(pdf)
            st.session_state.testo_turno = "".join([p.extract_text() for p in reader.pages if p.extract_text()])
            st.success("Turno analizzato!")

    st.title("🏥 TurnoSano AI")

    # REGISTRAZIONE DATI
    st.subheader("📝 Il tuo Diario")
    with st.form("wellness_form"):
        f_val = st.slider("Livello Fatica (1-10)", 1, 10, 5)
        s_val = st.number_input("Ore di Sonno", 0.0, 20.0, 7.0, step=0.5)
        submit = st.form_submit_button("Salva Parametri")
        
        if submit:
            if salva_benessere(st.session_state['username'], f_val, s_val):
                st.success("Dati registrati correttamente!")

    # STORICO SEMPLICE (TABELLA)
    with st.expander("📂 Vedi i tuoi ultimi inserimenti"):
        res = supabase.table("wellness").select("created_at, fatica, ore_sonno").filter("user_id", "eq", st.session_state['username']).order("created_at", desc=True).limit(10).execute()
        if res.data:
            st.table(res.data)
        else:
            st.info("Nessun dato ancora registrato.")

    # --- 6. COACH AI ---
    st.divider()
    st.subheader("💬 Coach AI Benessere")
    
    if "GROQ_API_KEY" in st.secrets:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        
        # Tasti Rapidi
        c1, c2, c3 = st.columns(3)
        prompt_rapido = None
        if c1.button("🌙 SOS Notte"): prompt_rapido = "Consigli per il turno di notte."
        if c2.button("🥗 Dieta"): prompt_rapido = "Cosa mangiare per avere energia?"
        if c3.button("🗑️ Svuota Chat"):
            st.session_state.messages = []
            st.rerun()

        chat_in = st.chat_input("Chiedi al coach...")
        final_query = chat_in or prompt_rapido

        if final_query:
            st.session_state.messages.append({"role": "user", "content": final_query})
            ctx = f"Sei TurnoSano AI, coach per infermieri. Utente: {st.session_state['name']}."
            if st.session_state.testo_turno: ctx += f" Turno: {st.session_state.testo_turno[:500]}"
            
            resp = client.chat.completions.create(
                messages=[{"role": "system", "content": ctx}] + st.session_state.messages,
                model="llama-3.1-8b-instant"
            )
            st.session_state.messages.append({"role": "assistant", "content": resp.choices[0].message.content})

        for m in st.session_state.messages:
            with st.chat_message(m["role"]): st.markdown(m["content"])
    else:
        st.warning("Configura GRO
