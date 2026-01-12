import streamlit as st
import pandas as pd
from supabase import create_client, Client
from groq import Groq
from PyPDF2 import PdfReader
import streamlit_authenticator as stauth

# --- 1. CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥", layout="centered")

# Connessione Supabase
try:
    sb: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except:
    st.error("Errore: Credenziali Supabase mancanti nei Secrets!")
    st.stop()

# --- 2. FUNZIONI DATABASE ---
def get_user_config():
    try:
        res = sb.table("profiles").select("*").execute()
        utenti = {u["username"]: {"name": u["name"], "password": u["password"]} for u in res.data}
        return {"credentials": {"usernames": utenti}}
    except:
        return {"credentials": {"usernames": {}}}

def save_wellness(u, f, s):
    try:
        sb.table("wellness").insert({"user_id": str(u), "fatica": float(f), "ore_sonno": float(s)}).execute()
        return True
    except Exception as e:
        st.error(f"Errore salvataggio: {e}")
        return False

# --- 3. AUTENTICAZIONE (v0.3.0+) ---
if "config" not in st.session_state:
    st.session_state.config = get_user_config()

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
            st.error("Username o password errati.")
    
    with t_reg:
        try:
            res = auth.register_user(location='main')
            if res:
                uname, info = res
                if uname:
                    sb.table("profiles").insert({"username": str(uname), "name": str(info['name']), "password": str(info['password'])}).execute()
                    st.success("Registrato! Ora puoi accedere.")
                    st.session_state.config = get_user_config()
        except:
            st.info("Scegli un username e password (min. 6 caratteri).")

else:
    # --- 4. DASHBOARD UTENTE ---
    if "msgs" not in st.session_state: st.session_state.msgs = []
    if "pdf_txt" not in st.session_state: st.session_state.pdf_txt = ""

    with st.sidebar:
        st.title("👨‍⚕️ Menù")
        st.write(f"In servizio: **{st.session_state['name']}**")
        auth.logout('Disconnetti', 'sidebar')
        st.divider()
        pdf = st.file_uploader("Carica Turno (PDF)", type="pdf")
        if pdf:
            reader = PdfReader(pdf)
            st.session_state.pdf_txt = "".join([p.extract_text() for p in reader.pages if p.extract_text()])
            st.sidebar.success("PDF analizzato!")

    st.title("🏥 TurnoSano AI")

    # Modulo Inserimento
    with st.form("wellness_form"):
        st.subheader("📝 Diario del Benessere")
        f_val = st.slider("Livello Fatica (1-10)", 1, 10, 5)
        s_val = st.number_input("Ore Sonno", 0.0, 24.0, 7.0, step=0.5)
        if st.form_submit_button("Salva Parametri"):
            if save_wellness(st.session_state['username'], f_val, s_val):
                st.success("Dati salvati!")
                st.rerun()

    # Storico con Debug
    with st.expander("📂 I tuoi ultimi inserimenti"):
        try:
            res_w = sb.table("wellness").select("*").filter("user_id", "eq", st.session_state['username']).order("created_at", desc=True).limit(10).execute()
            
            if res_w.data:
                df = pd.DataFrame(res_w.data)
                # Formattazione data leggibile
                df['Data'] = pd.to_datetime(df['created_at']).dt.strftime('%d/%m/%Y %H:%M')
                st.table(df[["Data", "fatica", "ore_sonno"]])
            else:
                st.info("Nessun dato registrato nel database.")
        except Exception as e:
            st.error(f"Errore nel caricamento dei dati: {e}")

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
