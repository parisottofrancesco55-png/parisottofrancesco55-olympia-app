import streamlit as st
import pandas as pd
from supabase import create_client, Client
from groq import Groq
from PyPDF2 import PdfReader
import streamlit_authenticator as stauth

# --- 1. CONFIGURAZIONE ---
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥", layout="centered")

def init_db():
    try:
        url = st.secrets["SUPABASE_URL"].strip().rstrip('/')
        key = st.secrets["SUPABASE_KEY"].strip()
        return create_client(url, key)
    except Exception as e:
        st.error(f"Errore Database: {e}")
        st.stop()

sb = init_db()

def load_users():
    try:
        res = sb.table("profiles").select("*").execute()
        return {u["username"]: {"name": u["name"], "password": u["password"]} for u in res.data}
    except:
        return {}

# Sincronizzazione utenti
if "user_db" not in st.session_state:
    st.session_state.user_db = load_users()

if "auth_mode" not in st.session_state:
    st.session_state.auth_mode = "login"

# --- 2. AUTENTICAZIONE ---
auth = stauth.Authenticate(
    {"usernames": st.session_state.user_db},
    "turnosano_cookie",
    "turnosano_key",
    30
)

# --- 3. LOGICA DI ACCESSO / REGISTRAZIONE ---
if not st.session_state.get("authentication_status"):
    st.title("🏥 TurnoSano AI")
    
    if st.session_state.auth_mode == "login":
        auth.login(location='main')
        if st.session_state["authentication_status"] is False:
            st.error("Username o password errati.")
        
        st.write("---")
        if st.button("Non hai un account? Iscriviti qui"):
            st.session_state.auth_mode = "iscrizione"
            st.rerun()

    else:
        st.subheader("📝 Registrazione Nuovo Utente")
        
        with st.form("registration_form"):
            new_user = st.text_input("Username (per il login)")
            new_name = st.text_input("Nome Visualizzato")
            new_pw = st.text_input("Password", type="password")
            confirm_pw = st.text_input("Conferma Password", type="password")
            
            submit_reg = st.form_submit_button("Crea Account")
            
            if submit_reg:
                if not new_user or not new_pw or not new_name:
                    st.warning("Compila tutti i campi!")
                elif new_pw != confirm_pw:
                    st.error("Le password non coincidono.")
                elif len(new_pw) < 6:
                    st.error("La password deve avere almeno 6 caratteri.")
                elif new_user in st.session_state.user_db:
                    st.error("Username già occupato.")
                else:
                    # NUOVA LOGICA HASHING (Compatibile con 0.3.0+)
                    hashed_pw = stauth.Hasher.hash(new_pw)
                    
                    try:
                        sb.table("profiles").insert({
                            "username": new_user,
                            "name": new_name,
                            "password": hashed_pw
                        }).execute()
                        
                        st.success(f"✅ Utente {new_user} creato!")
                        st.session_state.user_db = load_users()
                        st.info("Ora clicca su 'Torna al Login'.")
                    except Exception as e:
                        st.error(f"Errore database: {e}")
        
        if st.button("Torna al Login"):
            st.session_state.auth_mode = "login"
            st.rerun()

else:
    # --- 4. APP PRINCIPALE ---
    st.sidebar.title(f"👋 Benvenuto, {st.session_state['name']}")
    auth.logout('Esci', 'sidebar')
    
    pdf_file = st.sidebar.file_uploader("Carica Turno (PDF)", type="pdf")
    if pdf_file:
        reader = PdfReader(pdf_file)
        st.session_state.pdf_text = "".join([p.extract_text() for p in reader.pages if p.extract_text()])
        st.sidebar.success("Turno analizzato!")

    st.title("🏥 Dashboard Operatore")

    with st.form("wellness_form", clear_on_submit=True):
        st.subheader("📝 Diario Benessere")
        f_val = st.slider("Livello Fatica (1-10)", 1, 10, 5)
        s_val = st.number_input("Ore di sonno effettive", 0.0, 24.0, 7.0)
        if st.form_submit_button("Salva Dati"):
            try:
                sb.table("wellness").insert({
                    "user_id": st.session_state['username'], 
                    "fatica": float(f_val), 
                    "ore_sonno": float(s_val)
                }).execute()
                st.success("Dati salvati!")
            except: st.error("Errore salvataggio.")

    # Storico
    with st.expander("📂 I tuoi dati recenti"):
        try:
            res_w = sb.table("wellness").select("*").filter("user_id", "eq", st.session_state['username']).order("created_at", desc=True).limit(5).execute()
            if res_w.data:
                df = pd.DataFrame(res_w.data)
                df['Data'] = pd.to_datetime(df['created_at']).dt.strftime('%d/%m/%Y %H:%M')
                st.table(df[["Data", "fatica", "ore_sonno"]])
        except: st.info("Ancora nessun dato registrato.")

    # --- 5. COACH SCIENTIFICO ---
    st.divider()
    st.subheader("🔬 Supporto Scientifico")
    
    if "GROQ_API_KEY" in st.secrets:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        c1, c2, c3 = st.columns(3)
        q_click = None
        if c1.button("🌙 Recupero Notte"): q_click = "Strategie scientifiche per il recupero post-notte."
        if c2.button("🥗 Dieta Turnista"): q_click = "Consigli cronobiologici sull'alimentazione."
        if c3.button("🗑️ Reset Chat"): st.session_state.msgs = []; st.rerun()

        chat_in = st.chat_input("Chiedi al coach...")
        final_q = chat_in or q_click

        if final_q:
            if "msgs" not in st.session_state: st.session_state.msgs = []
            st.session_state.msgs.append({"role": "user", "content": final_q})
            
            sys_prompt = "Sei un esperto in cronobiologia. Dai consigli basati su studi scientifici. Non sei un medico."
            if "pdf_text" in st.session_state:
                sys_prompt += f" Considera questi turni: {st.session_state.pdf_text[:300]}"

            res_ai = client.chat.completions.create(
                messages=[{"role": "system", "content": sys_prompt}] + st.session_state.msgs,
                model="llama-3.1-8b-instant"
            )
            st.session_state.msgs.append({"role": "assistant", "content": res_ai.choices[0].message.content})

        if "msgs" in st.session_state:
            for m in st.session_state.msgs:
                with st.chat_message(m["role"]): st.write(m["content"])
