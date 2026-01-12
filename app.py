import streamlit as st
import pandas as pd
from supabase import create_client, Client
from groq import Groq
from PyPDF2 import PdfReader
import streamlit_authenticator as stauth
import plotly.graph_objects as go
from datetime import datetime, timedelta
import pytz

# --- 1. CONFIGURAZIONE ---
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥", layout="wide")

def init_db():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

sb = init_db()

def load_users():
    """Carica gli utenti da Supabase e li formatta per l'Authenticator"""
    try:
        res = sb.table("profiles").select("*").execute()
        # La versione 0.3+ richiede questa struttura precisa
        user_dict = {"usernames": {}}
        for u in res.data:
            user_dict["usernames"][u["username"]] = {
                "name": u["name"],
                "password": u["password"]
            }
        return user_dict
    except:
        return {"usernames": {}}

# Inizializzazione Session State per la navigazione
if "auth_mode" not in st.session_state:
    st.session_state.auth_mode = "login"
if "user_db" not in st.session_state:
    st.session_state.user_db = load_users()

# --- 2. AUTENTICAZIONE ---
auth = stauth.Authenticate(
    st.session_state.user_db,
    "turnosano_cookie",
    "turnosano_key",
    30
)

# --- 3. LOGICA DI ACCESSO / REGISTRAZIONE ---
if not st.session_state.get("authentication_status"):
    placeholder = st.empty() # Pulisce l'interfaccia tra login e registrazione
    
    if st.session_state.auth_mode == "login":
        with placeholder.container():
            st.title("🏥 TurnoSano AI")
            auth.login(location='main')
            
            if st.session_state["authentication_status"] is False:
                st.error("Username o password errati.")
            
            st.write("---")
            if st.button("Non hai un account? Registrati qui"):
                st.session_state.auth_mode = "iscrizione"
                st.rerun()

    else:
        with placeholder.container():
            st.title("📝 Registrazione")
            with st.form("reg_form"):
                new_u = st.text_input("Username (per il login)").lower().strip()
                new_n = st.text_input("Nome Visualizzato")
                new_p = st.text_input("Password", type="password")
                conf_p = st.text_input("Conferma Password", type="password")
                
                st.info("🛡️ Privacy: I tuoi dati sanitari sono salvati in forma criptata a Zurigo (CH).")
                privacy = st.checkbox("Accetto la Privacy Policy e il trattamento dei dati.")
                
                if st.form_submit_button("Crea Account"):
                    if not privacy:
                        st.error("Devi accettare la privacy.")
                    elif new_p != conf_p:
                        st.error("Le password non coincidono.")
                    elif not new_u or not new_p:
                        st.error("Campi obbligatori mancanti.")
                    elif new_u in st.session_state.user_db["usernames"]:
                        st.error("Username già occupato.")
                    else:
                        hashed_pw = stauth.Hasher.hash(new_p)
                        try:
                            sb.table("profiles").insert({
                                "username": new_u, "name": new_n, "password": hashed_pw
                            }).execute()
                            st.session_state.user_db = load_users() # Aggiorna il DB utenti
                            st.success("✅ Account creato! Torna al login per entrare.")
                        except Exception as e:
                            st.error(f"Errore Database: {e}")
            
            if st.button("Torna al Login"):
                st.session_state.auth_mode = "login"
                st.rerun()

else:
    # --- 4. DASHBOARD (UTENTE LOGGATO) ---
    # RIGA 80 FIX: Parametri logout corretti per la versione stabile
    auth.logout('Esci', 'sidebar')
    
    st.sidebar.title(f"👋 {st.session_state['name']}")
    
    # Sezione Note Legali e Gestione Dati
    with st.sidebar.expander("⚖️ Privacy & Sicurezza"):
        st.caption("📍 Server: Zurigo, Svizzera")
        if st.button("Elimina i miei dati"):
            try:
                sb.table("wellness").delete().eq("user_id", st.session_state['username']).execute()
                st.success("Dati puliti!")
            except: st.error("Errore nella cancellazione.")

    # Caricamento PDF
    pdf_file = st.sidebar.file_uploader("📅 Carica i tuoi Turni (PDF)", type="pdf")
    if pdf_file:
        reader = PdfReader(pdf_file)
        st.session_state.pdf_text = "".join([p.extract_text() for p in reader.pages if p.extract_text()])
        st.sidebar.success("Turno analizzato!")

    st.title("📊 Monitoraggio Benessere")

    # --- 5. INSERIMENTO DATI E GRAFICI ---
    col_input, col_graph = st.columns([1, 2])
    
    with col_input:
        st.subheader("📝 Dati di oggi")
        with st.form("daily_wellness", clear_on_submit=True):
            f_val = st.slider("Livello Fatica (1-10)", 1, 10, 5)
            s_val = st.number_input("Ore di sonno", 0.0, 24.0, 7.0, step=0.5)
            if st.form_submit_button("Salva"):
                try:
                    sb.table("wellness").insert({
                        "user_id": st.session_state['username'], 
                        "fatica": float(f_val), 
                        "ore_sonno": float(s_val)
                    }).execute()
                    st.rerun()
                except Exception as e: st.error(f"Errore invio: {e}")

    with col_graph:
        st.subheader("📈 Andamento Settimanale")
        try:
            res = sb.table("wellness").select("*").eq("user_id", st.session_state['username']).execute()
            if res.data:
                df = pd.DataFrame(res.data).sort_values('created_at')
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df['created_at'], y=df['fatica'], name="Fatica", line=dict(color='#FF4B4B', width=3)))
                fig.add_trace(go.Scatter(x=df['created_at'], y=df['ore_sonno'], name="Sonno", line=dict(color='#0068C9', width=3)))
                fig.update_layout(height=300, margin=dict(l=0,r=0,t=0,b=0), template="plotly_white")
                st.plotly_chart(fig, use_container_width=True)
        except: st.info("Inserisci i primi dati per visualizzare il grafico.")

    # --- 6. COACH IA E COMANDI RAPIDI ---
    st.divider()
    st.subheader("🔬 Coach Scientifico TurnoSano")
    
    if "GROQ_API_KEY" in st.secrets:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        
        # --- COMANDI RAPIDI ---
        st.write("💡 **Azioni veloci:**")
        c1, c2, c3 = st.columns(3)
        fast_q = None
        if c1.button("🌙 Recupero Post-Notte"): fast_q = "Dammi 3 consigli scientifici per recuperare il ritmo circadiano dopo una notte."
        if c2.button("🥗 Alimentazione Notturna"): fast_q = "Cosa mangiare durante il turno di notte per non avere cali di energia?"
        if c3.button("🗑️ Svuota Chat"): 
            st.session_state.messages = []
            st.rerun()

        if "messages" not in st.session_state:
            st.session_state.messages = []

        chat_input = st.chat_input("Fai una domanda al coach...")
        final_query = fast_q if fast_q else chat_input

        if final_query:
            st.session_state.messages.append({"role": "user", "content": final_query})
            sys_prompt = "Sei un esperto di cronobiologia e salute dei turnisti. Rispondi in modo conciso e basato su prove scientifiche."
            if "pdf_text" in st.session_state:
                sys_prompt += f" Considera questi turni dell'utente: {st.session_state.pdf_text[:500]}"
            
            chat_completion = client.chat.completions.create(
                messages=[{"role": "system", "content": sys_prompt}] + st.session_state.messages,
                model="llama-3.1-8b-instant",
            )
            response = chat_completion.choices[0].message.content
            st.session_state.messages.append({"role": "assistant", "content": response})

        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

    st.markdown("---")
    st.caption("📍 Sviluppato tra Spagna e Italia | 🛡️ Database: Zurigo (CH) | 🏥 TurnoSano AI v1.0")
