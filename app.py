import streamlit as st
import pandas as pd
from supabase import create_client, Client
from groq import Groq
from PyPDF2 import PdfReader
import streamlit_authenticator as stauth

# --- 1. CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥", layout="centered")

def init_db():
    try:
        url = st.secrets["SUPABASE_URL"].strip().rstrip('/')
        key = st.secrets["SUPABASE_KEY"].strip()
        return create_client(url, key)
    except Exception as e:
        st.error(f"Errore configurazione Database: {e}")
        st.stop()

sb = init_db()

# --- 2. RECUPERO UTENTI (Per Login Persistente) ---
def get_auth_config():
    try:
        res = sb.table("profiles").select("*").execute()
        utenti_db = {u["username"]: {"name": u["name"], "password": u["password"]} for u in res.data}
        return {"credentials": {"usernames": utenti_db}}
    except:
        return {"credentials": {"usernames": {}}}

if "config" not in st.session_state:
    st.session_state.config = get_auth_config()

auth = stauth.Authenticate(
    st.session_state.config['credentials'], 
    "turnosano_cookie", 
    "signature_key_2026", 
    30 
)

# --- 3. LOGICA DI ACCESSO ---
if not st.session_state.get("authentication_status"):
    t1, t2 = st.tabs(["Accedi 🔑", "Iscriviti 📝"])
    with t1:
        auth.login(location='main')
    with t2:
        try:
            res_reg = auth.register_user(location='main')
            if res_reg and res_reg[0]:
                u_name, u_info = res_reg
                sb.table("profiles").insert({"username": str(u_name), "name": str(u_info['name']), "password": str(u_info['password'])}).execute()
                st.success("Iscrizione riuscita! Ora puoi accedere dal tab Accedi.")
                st.session_state.config = get_auth_config()
        except: st.info("Scegli le tue credenziali.")
else:
    # --- 4. DASHBOARD UTENTE ---
    st.sidebar.title(f"👋 {st.session_state['name']}")
    auth.logout('Esci', 'sidebar')
    
    pdf_file = st.sidebar.file_uploader("Carica Turno (PDF)", type="pdf")
    if pdf_file:
        reader = PdfReader(pdf_file)
        st.session_state.pdf_text = "".join([p.extract_text() for p in reader.pages if p.extract_text()])
        st.sidebar.success("Turno analizzato")

    st.title("🏥 TurnoSano AI")

    # --- FORM BENESSERE (Con Submit Button Corretto) ---
    with st.form("wellness_form", clear_on_submit=True):
        st.subheader("📝 Diario del Benessere")
        f_val = st.slider("Fatica percepita (1-10)", 1, 10, 5)
        s_val = st.number_input("Ore di sonno effettive", 0.0, 24.0, 7.0, step=0.5)
        
        # IL PULSANTE DI INVIO DEVE ESSERE DENTRO IL "WITH ST.FORM"
        submitted = st.form_submit_button("Salva Parametri")
        
        if submitted:
            try:
                data_in = {"user_id": str(st.session_state['username']), "fatica": float(f_val), "ore_sonno": float(s_val)}
                sb.table("wellness").insert(data_in).execute()
                st.success("Dati salvati correttamente!")
                st.rerun()
            except Exception as e: 
                st.error(f"Errore nel salvataggio: {e}")

    with st.expander("📂 I tuoi ultimi dati"):
        try:
            res_w = sb.table("wellness").select("*").filter("user_id", "eq", st.session_state['username']).order("created_at", desc=True).limit(5).execute()
            if res_w.data:
                df = pd.DataFrame(res_w.data)
                df['Data'] = pd.to_datetime(df['created_at']).dt.strftime('%d/%m/%Y %H:%M')
                st.table(df[["Data", "fatica", "ore_sonno"]])
        except: st.info("Nessun dato presente nel database.")

    # --- 5. ASSISTENTE SCIENTIFICO CON DOMANDE RAPIDE ---
    st.divider()
    st.subheader("🔬 Supporto Scientifico per Turnisti")
    
    if "GROQ_API_KEY" in st.secrets:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        
        # DOMANDE RAPIDE
        c1, c2, c3 = st.columns(3)
        p_rapido = None
        if c1.button("🌙 Strategia Notte"): p_rapido = "Fornisci strategie basate su studi scientifici per gestire il post-turno di notte."
        if c2.button("🥗 Nutrizione"): p_rapido = "Cosa dice la letteratura scientifica sull'alimentazione ideale per chi lavora di notte?"
        if c3.button("🗑️ Reset Chat"):
            st.session_state.msgs = []
            st.rerun()

        chat_in = st.chat_input("Chiedi una strategia scientifica...")
        q = chat_in or p_rapido

        if q:
            if "msgs" not in st.session_state: st.session_state.msgs = []
            st.session_state.msgs.append({"role": "user", "content": q})
            
            sys_prompt = (
                "Sei un assistente esperto in cronobiologia e medicina occupazionale. "
                "NON sei un medico e NON fornisci diagnosi. Il tuo compito è dare consigli "
                "basati esclusivamente su evidenze scientifiche riguardo i ritmi circadiani e il sonno."
            )
            if "pdf_text" in st.session_state:
                sys_prompt += f" Considera questi turni: {st.session_state.pdf_text[:400]}"

            res_ai = client.chat.completions.create(
                messages=[{"role": "system", "content": sys_prompt}] + st.session_state.msgs,
                model="llama-3.1-8b-instant"
            )
            st.session_state.msgs.append({"role": "assistant", "content": res_ai.choices[0].message.content})

        if "msgs" in st.session_state:
            for m in st.session_state.msgs:
                with st.chat_message(m["role"]): st.write(m["content"])
