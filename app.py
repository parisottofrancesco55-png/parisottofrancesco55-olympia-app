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
        raw_url = st.secrets["SUPABASE_URL"].strip().rstrip('/')
        key = st.secrets["SUPABASE_KEY"].strip()
        
        # LOGICA ANTI-405: Verifica se l'URL è quello della Dashboard invece dell'API
        if "supabase.com/dashboard" in raw_url or "project" in raw_url:
            st.error("⚠️ URL NON VALIDO NEI SECRETS!")
            st.warning("Hai inserito l'URL della Dashboard. Devi usare il 'Project URL'.")
            st.info("Vai su Supabase -> Settings (Ingranaggio) -> API. Copia l'URL che finisce con '.supabase.co'")
            st.stop()
            
        return create_client(raw_url, key)
    except Exception as e:
        st.error(f"Errore caricamento Secrets: {e}")
        st.stop()

sb = init_db()

# --- 2. FUNZIONI DATABASE ---
def get_users():
    try:
        res = sb.table("profiles").select("*").execute()
        u_map = {u["username"]: {"name": u["name"], "password": u["password"]} for u in res.data}
        return {"credentials": {"usernames": u_map}}
    except:
        return {"credentials": {"usernames": {}}}

# --- 3. GESTIONE AUTENTICAZIONE (v0.3.0+) ---
if "config" not in st.session_state:
    st.session_state.config = get_users()

auth = stauth.Authenticate(
    st.session_state.config['credentials'], 
    "ts_cookie", 
    "sig_2026", 
    30
)

if not st.session_state.get("authentication_status"):
    t1, t2 = st.tabs(["Accedi 🔑", "Iscriviti 📝"])
    
    with t1:
        auth.login(location='main')
        if st.session_state["authentication_status"] is False:
            st.error("Username o password errati.")
            
    with t2:
        try:
            res_reg = auth.register_user(location='main')
            if res_reg and res_reg[0]:
                sb.table("profiles").insert({
                    "username": str(res_reg[0]), 
                    "name": str(res_reg[1]['name']), 
                    "password": str(res_reg[1]['password'])
                }).execute()
                st.success("Registrato! Ora puoi accedere dal tab 'Accedi'.")
                st.session_state.config = get_users()
        except:
            st.info("Inserisci i dati per la registrazione (Password min. 6 caratteri).")
else:
    # --- 4. DASHBOARD UTENTE ---
    if "msgs" not in st.session_state: st.session_state.msgs = []
    
    st.sidebar.title(f"👋 Ciao {st.session_state['name']}")
    auth.logout('Esci', 'sidebar')
    
    pdf = st.sidebar.file_uploader("Carica Turno (PDF)", type="pdf")
    if pdf:
        reader = PdfReader(pdf)
        st.session_state.pdf_txt = "".join([p.extract_text() for p in reader.pages if p.extract_text()])
        st.sidebar.success("Turno analizzato!")

    st.title("🏥 TurnoSano AI")

    # Modulo Diario
    with st.form("wellness_form"):
        st.subheader("📝 Diario del Benessere")
        f = st.slider("Livello Fatica (1-10)", 1, 10, 5)
        s = st.number_input("Ore di Sonno", 0.0, 24.0, 7.0, step=0.5)
        
        if st.form_submit_button("Salva Parametri"):
            try:
                # Inserimento dati
                data = {
                    "user_id": str(st.session_state['username']), 
                    "fatica": float(f), 
                    "ore_sonno": float(s)
                }
                sb.table("wellness").insert(data).execute()
                st.success("Dati salvati con successo!")
                st.rerun()
            except Exception as e:
                st.error(f"Errore tecnico: {e}")
                st.info("Se l'errore è '405', controlla l'URL nei Secrets.")

    # Storico
    with st.expander("📂 I tuoi ultimi dati"):
        try:
            res = sb.table("wellness").select("*").filter("user_id", "eq", st.session_state['username']).order("created_at", desc=True).limit(5).execute()
            if res.data:
                df = pd.DataFrame(res.data)
                df['Data'] = pd.to_datetime(df['created_at']).dt.strftime('%d/%m/%Y %H:%M')
                st.table(df[["Data", "fatica", "ore_sonno"]])
            else:
                st.info("Nessun dato ancora registrato.")
        except:
            st.warning("Impossibile caricare lo storico.")

    # --- 5. COACH AI (GROQ) ---
    st.divider()
    st.subheader("💬 Coach Personale")
    
    if "GROQ_API_KEY" in st.secrets:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        chat_in = st.chat_input("Chiedi un consiglio sul tuo turno...")
        
        if chat_in:
            st.session_state.msgs.append({"role": "user", "content": chat_in})
            
            ctx = f"Sei un coach per infermieri. Utente: {st.session_state['name']}."
            if "pdf_txt" in st.session_state:
                ctx += f" Contesto turno: {st.session_state.pdf_txt[:400]}"

            res_ai = client.chat.completions.create(
                messages=[{"role": "system", "content": ctx}] + st.session_state.msgs,
                model="llama-3.1-8b-instant"
            )
            st.session_state.msgs.append({"role": "assistant", "content": res_ai.choices[0].message.content})

        for m in st.session_state.msgs:
            with st.chat_message(m["role"]): st.write(m["content"])
