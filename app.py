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
        if "dashboard" in url:
            st.error("⚠️ URL Errato: Usa il 'Project URL' dalle impostazioni API di Supabase.")
            st.stop()
        return create_client(url, key)
    except Exception as e:
        st.error(f"Errore caricamento database: {e}")
        st.stop()

sb = init_db()

# --- 2. FUNZIONI DATABASE ---
def get_auth_data():
    try:
        res = sb.table("profiles").select("*").execute()
        u_map = {u["username"]: {"name": u["name"], "password": u["password"]} for u in res.data}
        return {"credentials": {"usernames": u_map}}
    except:
        return {"credentials": {"usernames": {}}}

# --- 3. AUTENTICAZIONE (v0.3.0+) ---
if "config" not in st.session_state:
    st.session_state.config = get_auth_data()

auth = stauth.Authenticate(st.session_state.config['credentials'], "ts_cookie", "sig_2026", 30)

if not st.session_state.get("authentication_status"):
    t1, t2 = st.tabs(["Accedi 🔑", "Iscriviti 📝"])
    with t1:
        auth.login(location='main')
    with t2:
        try:
            res_reg = auth.register_user(location='main')
            if res_reg and res_reg[0]:
                sb.table("profiles").insert({
                    "username": str(res_reg[0]), 
                    "name": str(res_reg[1]['name']), 
                    "password": str(res_reg[1]['password'])
                }).execute()
                st.success("Registrato! Ora puoi accedere.")
                st.session_state.config = get_auth_data()
        except:
            st.info("Password min. 6 caratteri.")
else:
    # --- 4. AREA UTENTE ---
    if "msgs" not in st.session_state: st.session_state.msgs = []
    
    st.sidebar.title(f"👋 {st.session_state['name']}")
    auth.logout('Esci', 'sidebar')
    
    pdf = st.sidebar.file_uploader("Carica Turno (PDF)", type="pdf")
    if pdf:
        reader = PdfReader(pdf)
        st.session_state.pdf_txt = "".join([p.extract_text() for p in reader.pages if p.extract_text()])
        st.sidebar.success("Turno analizzato")

    st.title("🏥 TurnoSano AI")

    # Diario Benessere
    with st.form("wellness_form"):
        st.subheader("📝 Diario del Benessere")
        f = st.slider("Fatica percepita (1-10)", 1, 10, 5)
        s = st.number_input("Ore di sonno (ultime 24h)", 0.0, 24.0, 7.0, step=0.5)
        
        if st.form_submit_button("Salva Parametri"):
            try:
                data = {"user_id": str(st.session_state['username']), "fatica": float(f), "ore_sonno": float(s)}
                sb.table("wellness").insert(data).execute()
                st.success("Dati salvati!")
                st.rerun()
            except Exception as e:
                st.error(f"Errore (controlla URL o RLS): {e}")

    # Storico
    with st.expander("📂 I tuoi ultimi dati"):
        try:
            res = sb.table("wellness").select("*").filter("user_id", "eq", st.session_state['username']).order("created_at", desc=True).limit(5).execute()
            if res.data:
                df = pd.DataFrame(res.data)
                df['Data'] = pd.to_datetime(df['created_at']).dt.strftime('%d/%m/%Y %H:%M')
                st.table(df[["Data", "fatica", "ore_sonno"]])
            else:
                st.info("Nessun dato registrato.")
        except:
            st.info("In attesa del primo inserimento...")

    # --- 5. ASSISTENTE SCIENTIFICO (NON MEDICO) ---
    st.divider()
    st.subheader("💬 Supporto Scientifico Turnisti")
    
    if "GROQ_API_KEY" in st.secrets:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        
        # Comandi rapidi per l'utente
        c1, c2, c3 = st.columns(3)
        p_rapido = None
        if c1.button("🌙 Strategia Notte"): p_rapido = "Quali studi suggeriscono come gestire il debito di sonno post-notte?"
        if c2.button("🥗 Nutrizione"): p_rapido = "Cosa dice la cronobiologia sui pasti durante il turno notturno?"
        if c3.button("🗑️ Reset Chat"):
            st.session_state.msgs = []
            st.rerun()

        chat_in = st.chat_input("Chiedi una strategia basata su studi...")
        q = chat_in or p_rapido

        if q:
            st.session_state.msgs.append({"role": "user", "content": q})
            
            # SYSTEM PROMPT MODIFICATO
            system_prompt = (
                "Sei un assistente esperto in cronobiologia e salute occupazionale per personale sanitario. "
                "IMPORTANTE: Non sei un medico e non devi dare consigli clinici o diagnosi. "
                "Il tuo compito è fornire consigli comportamentali basati esclusivamente su studi scientifici "
                "(es. NIOSH, OSHA, studi sul ritmo circadiano). Parla di igiene del sonno, gestione della luce, "
                "strategie di 'power nap' e alimentazione per turnisti. Cita le evidenze scientifiche."
            )
            
            if "pdf_txt" in st.session_state:
                system_prompt += f" Analizza questi turni per dare consigli mirati: {st.session_state.pdf_txt[:400]}"

            res_ai = client.chat.completions.create(
                messages=[{"role": "system", "content": system_prompt}] + st.session_state.msgs,
                model="llama-3.1-8b-instant"
            )
            st.session_state.msgs.append({"role": "assistant", "content": res_ai.choices[0].message.content})

        for m in st.session_state.msgs:
            with st.chat_message(m["role"]): st.write(m["content"])
    else:
        st.warning("Configura GROQ_API_KEY nei Secrets.")
