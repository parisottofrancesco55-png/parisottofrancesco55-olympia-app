import streamlit as st
import pandas as pd
from supabase import create_client, Client
from groq import Groq
from PyPDF2 import PdfReader
import streamlit_authenticator as stauth

# --- 1. CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥", layout="centered")

# Inizializzazione Database con pulizia URL (Anti-405)
def init_db():
    try:
        url = st.secrets["SUPABASE_URL"].strip().split('/dashboard')[0].rstrip('/')
        key = st.secrets["SUPABASE_KEY"].strip()
        return create_client(url, key)
    except Exception as e:
        st.error(f"Errore Secrets: {e}")
        st.stop()

sb = init_db()

# --- 2. FUNZIONI DI SUPPORTO ---
def get_users():
    try:
        res = sb.table("profiles").select("*").execute()
        u_dict = {u["username"]: {"name": u["name"], "password": u["password"]} for u in res.data}
        return {"credentials": {"usernames": u_dict}}
    except:
        return {"credentials": {"usernames": {}}}

# --- 3. AUTENTICAZIONE ---
if "config" not in st.session_state:
    st.session_state.config = get_users()

auth = stauth.Authenticate(
    st.session_state.config['credentials'],
    "ts_cookie",
    "signature_key_2026",
    30
)

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
                st.session_state.config = get_users()
        except:
            st.info("Minimo 6 caratteri per la password.")
else:
    # --- 4. DASHBOARD UTENTE ---
    if "msgs" not in st.session_state: st.session_state.msgs = []
    
    st.sidebar.title(f"Benvenuto {st.session_state['name']}")
    auth.logout('Esci', 'sidebar')
    
    # Caricamento PDF
    pdf_file = st.sidebar.file_uploader("Carica Turno (PDF)", type="pdf")
    if pdf_file:
        reader = PdfReader(pdf_file)
        st.session_state.turno = "".join([p.extract_text() for p in reader.pages if p.extract_text()])
        st.sidebar.success("Turno acquisito")

    st.title("🏥 TurnoSano AI")

    # Diario Benessere
    with st.form("wellness_form"):
        st.subheader("📝 Come stai oggi?")
        f_val = st.slider("Livello Fatica (1-10)", 1, 10, 5)
        s_val = st.number_input("Ore di Sonno", 0.0, 24.0, 7.0, step=0.5)
        
        if st.form_submit_button("Salva Parametri"):
            try:
                # Inserimento dati con formato esplicito
                data_to_insert = {
                    "user_id": str(st.session_state['username']),
                    "fatica": float(f_val),
                    "ore_sonno": float(s_val)
                }
                sb.table("wellness").insert(data_to_insert).execute()
                st.success("Dati salvati con successo!")
                st.rerun()
            except Exception as e:
                st.error(f"Errore tecnico: {e}")
                st.info("Assicurati di aver lanciato il comando SQL per disabilitare RLS.")

    # Storico
    with st.expander("📂 I tuoi ultimi dati"):
        try:
            res_w = sb.table("wellness").select("*").filter("user_id", "eq", st.session_state['username']).order("created_at", desc=True).limit(5).execute()
            if res_w.data:
                df = pd.DataFrame(res_w.data)
                df['Data'] = pd.to_datetime(df['created_at']).dt.strftime('%d/%m/%Y %H:%M')
                st.table(df[["Data", "fatica", "ore_sonno"]])
            else:
                st.info("Nessun dato registrato.")
        except Exception as e:
            st.error("Errore nel caricamento storico.")

    # --- 5. COACH AI ---
    st.divider()
    st.subheader("💬 Coach AI")
    
    if "GROQ_API_KEY" in st.secrets:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        chat_input = st.chat_input("Chiedi un consiglio...")
        
        if chat_input:
            st.session_state.msgs.append({"role": "user", "content": chat_input})
            
            # Prepariamo il contesto
            system_prompt = f"Sei un coach per infermieri. Utente: {st.session_state['name']}."
            if "turno" in st.session_state:
                system_prompt += f" Contesto turno: {st.session_state.turno[:300]}"

            response = client.chat.completions.create(
                messages=[{"role": "system", "content": system_prompt}] + st.session_state.msgs,
                model="llama-3.1-8b-instant"
            )
            st.session_state.msgs.append({"role": "assistant", "content": response.choices[0].message.content})

        for m in st.session_state.msgs:
            with st.chat_message(m["role"]): st.write(m["content"])
