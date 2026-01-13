import streamlit as st
import pandas as pd
from supabase import create_client, Client
from groq import Groq
import streamlit_authenticator as stauth
from streamlit_authenticator.utilities.hasher import Hasher
import plotly.graph_objects as go
from fpdf import FPDF
from datetime import datetime
import io

# --- 1. CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="TurnoSano IA", page_icon="🏥", layout="wide")

# Inizializzazione variabili di sessione
if "auth_mode" not in st.session_state:
    st.session_state.auth_mode = "login"
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- 2. CONNESSIONE DATABASE ---
@st.cache_resource
def init_connection():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

sb = init_connection()

def fetch_users():
    try:
        res = sb.table("profiles").select("*").execute()
        usernames = {u["username"]: {
            "name": u["name"], "password": u["password"], "is_premium": u.get("is_premium", False)
        } for u in res.data}
        return {"usernames": usernames}
    except:
        return {"usernames": {}}

db_users = fetch_users()

# --- 3. AUTENTICAZIONE ---
authenticator = stauth.Authenticate(db_users, "turnosano_cookie", "signature_key_123", 30)

if not st.session_state.get("authentication_status"):
    if st.session_state.auth_mode == "login":
        st.title("🏥 TurnoSano IA - Accedi")
        authenticator.login(location='main')
        if st.session_state["authentication_status"] is False:
            st.error("Username o password errati.")
        st.write("---")
        if st.button("Registrati ora"):
            st.session_state.auth_mode = "signup"
            st.rerun()
    else:
        st.title("📝 Registrazione")
        with st.form("signup"):
            u = st.text_input("Username").lower().strip()
            n = st.text_input("Nome")
            p = st.text_input("Password", type="password")
            cp = st.text_input("Conferma Password", type="password")
            if st.form_submit_button("Crea Account"):
                if p == cp and u not in db_users["usernames"]:
                    hp = Hasher([p]).generate()[0]
                    sb.table("profiles").insert({"username": u, "name": n, "password": hp, "is_premium": False}).execute()
                    st.success("Fatto! Accedi ora.")
                    st.session_state.auth_mode = "login"
                    st.rerun()
        if st.button("Indietro"):
            st.session_state.auth_mode = "login"
            st.rerun()

else:
    # --- 4. AREA LOGGATA ---
    authenticator.logout('Disconnetti', 'sidebar')
    uid = st.session_state["username"]
    is_premium = db_users["usernames"].get(uid, {}).get("is_premium", False)

    st.sidebar.title(f"Operatore: {st.session_state['name']}")
    if is_premium:
        st.sidebar.success("✨ Piano: PREMIUM")
    else:
        st.sidebar.warning("🛡️ Piano: BASE")
        st.sidebar.markdown(f"[🚀 Attiva Premium]({st.secrets.get('STRIPE_CHECKOUT_URL', '#')})")

    st.title("📊 Dashboard")

    tab_in, tab_an, tab_ia = st.tabs(["📝 Diario", "📈 Analisi", "🔬 Coach IA"])

    with tab_in:
        with st.form("daily"):
            fat = st.select_slider("Stanchezza (1-10)", options=range(1,11), value=5)
            slp = st.number_input("Ore sonno", 0.0, 24.0, 7.0)
            if st.form_submit_button("Salva"):
                sb.table("wellness").insert({"user_id": uid, "fatica": fat, "ore_sonno": slp, "created_at": datetime.now().isoformat()}).execute()
                st.success("Dati salvati!")

    with tab_an:
        if not is_premium:
            st.error("🔒 Funzione Premium")
        else:
            res = sb.table("wellness").select("*").eq("user_id", uid).order("created_at").execute()
            if res.data:
                df = pd.DataFrame(res.data)
                df['created_at'] = pd.to_datetime(df['created_at'])
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df['created_at'], y=df['fatica'], name="Stanchezza", line=dict(color='red')))
                fig.add_trace(go.Bar(x=df['created_at'], y=df['ore_sonno'], name="Sonno"))
                st.plotly_chart(fig, use_container_width=True)
                
                if st.button("📄 Genera PDF"):
                    pdf = FPDF()
                    pdf.add_page()
                    pdf.set_font("Arial", 'B', 16); pdf.cell(200, 10, "REPORT TURNOSANO IA", ln=True, align='C')
                    pdf.set_font("Arial", size=12); pdf.ln(10); pdf.cell(200, 10, f"Operatore: {st.session_state['name']}", ln=True)
                    pdf.set_fill_color(200, 220, 255)
                    pdf.cell(60, 10, "Data", 1, 0, 'C', True); pdf.cell(60, 10, "Fatica", 1, 0, 'C', True); pdf.cell(60, 10, "Sonno", 1, 1, 'C', True)
                    for _, r in df.tail(10).iterrows():
                        pdf.cell(60, 10, r['created_at'].strftime('%d/%m/%Y'), 1)
                        pdf.cell(60, 10, str(r['fatica']), 1); pdf.cell(60, 10, str(r['ore_sonno']), 1, 1)
                    st.download_button("⬇️ Scarica PDF", pdf.output(dest='S').encode('latin-1', errors='replace'), "report.pdf", "application/pdf")

    with tab_ia:
        st.subheader("Chiedi al Coach")
        
        # --- COMANDI RAPIDI (Ecco la sezione aggiunta) ---
        st.write("💡 **Comandi Rapidi:**")
        c1, c2, c3, c4 = st.columns(4)
        fast_q = None
        if c1.button("🌙 Recupero Notte"): fast_q = "Dammi 3 consigli scientifici per recuperare dopo lo smonto notte."
        if c2.button("🥗 Dieta Turnista"): fast_q = "Cosa mangiare durante il turno di notte per non avere sonnolenza?"
        if c3.button("☕ Stop Caffeina"): fast_q = "A che ora dovrei bere l'ultimo caffè se devo dormire alle 15:00?"
        if c4.button("🗑️ Reset Chat"): 
            st.session_state.messages = []
            st.rerun()

        for m in st.session_state.messages:
            with st.chat_message(m["role"]): st.markdown(m["content"])

        prompt = st.chat_input("Scrivi qui...")
        query = fast_q or prompt

        if query:
            st.session_state.messages.append({"role": "user", "content": query})
            with st.chat_message("user"): st.markdown(query)
            with st.chat_message("assistant"):
                client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                sys = "Sei un esperto di cronobiologia. Rispondi in italiano."
                if not is_premium: sys += " Rispondi in max 30 parole."
                res = client.chat.completions.create(messages=[{"role":"system","content":sys}]+st.session_state.messages, model="llama-3.1-8b-instant")
                ans = res.choices[0].message.content
                st.markdown(ans)
                st.session_state.messages.append({"role": "assistant", "content": ans})

    st.caption("Dati protetti dal GDPR svizzero.")
