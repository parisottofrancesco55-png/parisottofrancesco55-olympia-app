import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client, Client
from groq import Groq
from PyPDF2 import PdfReader
import streamlit_authenticator as stauth

# --- 1. CONFIGURAZIONE ---
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥", layout="wide")

# --- 2. CONNESSIONE SUPABASE ---
try:
    URL_DB = st.secrets["SUPABASE_URL"]
    KEY_DB = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(URL_DB, KEY_DB)
except Exception as e:
    st.error("Errore Secrets Supabase!")
    st.stop()

# --- 3. FUNZIONI DB ---
def carica_credenziali():
    try:
        res = supabase.table("profiles").select("*").execute()
        credenziali = {"usernames": {}}
        for u in res.data:
            credenziali["usernames"][u["username"]] = {"name": u["name"], "password": u["password"]}
        return credenziali
    except: return {"usernames": {}}

def salva_nuovo_utente(u, n, p):
    try:
        supabase.table("profiles").insert({"username": str(u), "name": str(n), "password": str(p)}).execute()
    except: pass

def salva_benessere(username, fatica, sonno):
    try:
        payload = {"user_id": str(username), "fatica": float(fatica), "ore_sonno": float(sonno)}
        supabase.table("wellness").insert(payload).execute()
        return True
    except Exception as e:
        st.error(f"Errore DB: {e}")
        return False

def carica_dati_benessere(username):
    try:
        res = supabase.table("wellness").select("*").filter("user_id", "eq", username).order("created_at").execute()
        df = pd.DataFrame(res.data)
        if not df.empty:
            df['fatica'] = pd.to_numeric(df['fatica'])
            df['ore_sonno'] = pd.to_numeric(df['ore_sonno'])
        return df
    except: return pd.DataFrame()

# --- 4. AUTENTICAZIONE ---
if "config" not in st.session_state:
    st.session_state.config = carica_credenziali()

auth = stauth.Authenticate(st.session_state.config, "ts_cookie", "auth_key", 30)

if not st.session_state.get("authentication_status"):
    t1, t2 = st.tabs(["Accedi 🔑", "Iscriviti 📝"])
    with t2:
        res = auth.register_user(pre_authorized=None)
        if res:
            u, info = res
            if u:
                salva_nuovo_utente(u, info['name'], info['password'])
                st.success('Registrato! Accedi ora.')
                st.session_state.config = carica_credenziali()
    with t1:
        auth.login()
else:
    # --- 5. DASHBOARD ---
    if "messages" not in st.session_state: st.session_state.messages = []
    if "testo_turno" not in st.session_state: st.session_state.testo_turno = ""

    with st.sidebar:
        st.title("👨‍⚕️ Menù")
        st.write(f"In servizio: **{st.session_state['name']}**")
        auth.logout('Esci', 'sidebar')
        st.divider()
        pdf = st.file_uploader("📂 Carica Turno PDF", type="pdf")
        if pdf:
            reader = PdfReader(pdf)
            st.session_state.testo_turno = "".join([p.extract_text() for p in reader.pages if p.extract_text()])
            st.success("Turno analizzato!")

    st.title("🏥 TurnoSano AI")

    with st.expander("📝 Diario del Benessere"):
        c1, c2 = st.columns(2)
        f_val = c1.slider("Fatica (1-10)", 1, 10, 5)
        s_val = c2.number_input("Ore di Sonno", 0.0, 20.0, 7.0, step=0.5)
        if st.button("💾 Salva Dati"):
            if salva_benessere(st.session_state['username'], f_val, s_val):
                st.success("Dati registrati!")
                st.rerun()

    df = carica_dati_benessere(st.session_state['username'])
    if not df.empty:
        col1, col2 = st.columns(2)
        with col1: st.plotly_chart(px.line(df, x='created_at', y='fatica', title="Trend Fatica", markers=True), use_container_width=True)
        with col2: st.plotly_chart(px.bar(df, x='created_at', y='ore_sonno', title="Trend Sonno"), use_container_width=True)
    else:
        st.info("Registra i tuoi dati per vedere i grafici.")

    # --- 6. COACH AI ---
    st.divider()
    st.subheader("💬 Coach AI Benessere")
    
    if "GROQ_API_KEY" in st.secrets:
        try:
            client = Groq(api_key=st.secrets["GROQ_API_KEY"])
            
            def chiedi_coach(p):
                st.session_state.messages.append({"role": "user", "content": p})
                ctx = f"Sei TurnoSano AI, coach per infermieri. Utente: {st.session_state['name']}."
                if st.session_state.testo_turno: ctx += f" Turno: {st.session_state.testo_turno[:500]}"
                res = client.chat.completions.create(
                    messages=[{"role": "system", "content": ctx}] + st.session_state.messages,
                    model="llama-3.1-8b-instant"
                )
                st.session_state.messages.append({"role": "assistant", "content": res.choices[0].message.content})

            # Comandi Rapidi
            r1, r2, r3 = st.columns(3)
            q_rapida = None
            if r1.button("🌙 SOS Notte"): q_rapida = "Consigli per il turno di notte"
            if r2.button("🥗 Dieta"): q_rapida = "Cosa mangiare in turno?"
            if r3.button("🗑️ Reset Chat"):
                st.session_state.messages = []
                st.rerun()

            chat_in = st.chat_input("Chiedi al coach...")
            final_q = chat_in or q_rapida
            if final_q: chiedi_coach(final_q)

            for m in st.session_state.messages:
                with st.chat_message(m["role"]): st.markdown(m["content"])
        except Exception as e: st.error(f"Errore AI: {e}")
    else:
        st.warning("Configura GROQ_API_KEY nei Secrets.")
