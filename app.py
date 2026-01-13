import streamlit as st
import pandas as pd
from supabase import create_client, Client
from groq import Groq
import streamlit_authenticator as stauth
from streamlit_authenticator import Hasher 
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
            "name": u["name"], 
            "password": u["password"]
        } for u in res.data}
        return {"usernames": usernames}
    except:
        return {"usernames": {}}

user_dict = fetch_users()

# --- 3. AUTENTICAZIONE ---
authenticator = stauth.Authenticate(
    user_dict,
    "turnosano_cookie",
    "signature_key_123",
    30
)

# --- LOGICA LOGIN / REGISTRAZIONE ---
if not st.session_state.get("authentication_status"):
    if st.session_state.auth_mode == "login":
        st.title("🏥 TurnoSano IA - Login")
        authenticator.login(location='main')
        if st.session_state["authentication_status"] is False:
            st.error("Username o password errati.")
        st.write("---")
        if st.button("Non hai un account? Registrati"):
            st.session_state.auth_mode = "signup"
            st.rerun()

    elif st.session_state.auth_mode == "signup":
        st.title("📝 Registrazione")
        with st.form("signup_form"):
            u = st.text_input("Username").lower().strip()
            n = st.text_input("Nome e Cognome")
            p = st.text_input("Password", type="password")
            cp = st.text_input("Conferma Password", type="password")
            if st.form_submit_button("Crea Account"):
                if p != cp:
                    st.error("Le password non coincidono")
                elif u in user_dict["usernames"]:
                    st.error("Username già esistente")
                else:
                    hpw = Hasher([p]).generate()[0]
                    sb.table("profiles").insert({"username": u, "name": n, "password": hpw, "is_premium": False}).execute()
                    st.success("Account creato! Effettua il login.")
                    st.session_state.auth_mode = "login"
                    st.rerun()
        if st.button("Torna al Login"):
            st.session_state.auth_mode = "login"
            st.rerun()

else:
    # --- 4. APP PRINCIPALE ---
    authenticator.logout('Disconnetti', 'sidebar')
    curr_user = st.session_state["username"]
    
    # Stato premium in tempo reale
    res_p = sb.table("profiles").select("is_premium").eq("username", curr_user).single().execute()
    is_premium = res_p.data.get("is_premium", False) if res_p.data else False

    st.sidebar.title(f"Operatore: {st.session_state['name']}")
    if is_premium:
        st.sidebar.success("✨ Piano: PREMIUM")
    else:
        st.sidebar.warning("🛡️ Piano: BASE")
        st.sidebar.markdown(f"[🚀 Attiva Premium]({st.secrets.get('STRIPE_CHECKOUT_URL', '#')})")

    st.title("📊 Dashboard Operatore")

    t1, t2, t3 = st.tabs(["📝 Diario", "📈 Analisi & Report", "🔬 Coach IA"])

    with t1:
        st.subheader("Registra i tuoi parametri")
        with st.form("daily_entry"):
            f = st.select_slider("Stanchezza (1=Top, 10=Esausto)", options=range(1,11), value=5)
            s = st.number_input("Ore di sonno", 0.0, 24.0, 7.0)
            if st.form_submit_button("Salva Dati"):
                sb.table("wellness").insert({
                    "user_id": curr_user, "fatica": f, "ore_sonno": s,
                    "created_at": datetime.now().isoformat()
                }).execute()
                st.success("Dati salvati correttamente!")

    with t2:
        if not is_premium:
            st.error("🔒 Grafici e Report PDF sono funzioni riservate agli utenti Premium.")
        else:
            res_d = sb.table("wellness").select("*").eq("user_id", curr_user).order("created_at").execute()
            if res_d.data:
                df = pd.DataFrame(res_d.data)
                df['created_at'] = pd.to_datetime(df['created_at'])
                
                # Visualizzazione Grafico
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df['created_at'], y=df['fatica'], name="Stanchezza", line=dict(color='red')))
                fig.add_trace(go.Bar(x=df['created_at'], y=df['ore_sonno'], name="Sonno"))
                st.plotly_chart(fig, use_container_width=True)
                
                st.divider()
                
                # Generazione PDF Reale
                if st.button("📄 Genera Report PDF"):
                    pdf = FPDF()
                    pdf.add_page()
                    pdf.set_font("helvetica", 'B', 16)
                    pdf.cell(0, 10, "REPORT TURNOSANO IA", ln=True, align='C')
                    pdf.ln(10)
                    pdf.set_font("helvetica", size=12)
                    pdf.cell(0, 10, f"Operatore: {st.session_state['name']}", ln=True)
                    pdf.ln(5)
                    
                    pdf.set_fill_color(200, 220, 255)
                    pdf.cell(60, 10, "Data", 1, 0, 'C', True)
                    pdf.cell(60, 10, "Fatica", 1, 0, 'C', True)
                    pdf.cell(60, 10, "Sonno", 1, 1, 'C', True)
                    
                    for _, row in df.tail(15).iterrows():
                        pdf.cell(60, 10, row['created_at'].strftime('%d/%m/%Y'), 1)
                        pdf.cell(60, 10, str(row['fatica']), 1)
                        pdf.cell(60, 10, str(row['ore_sonno']), 1, 1)
                    
                    # Gestione byte PDF per Streamlit
                    pdf_output = pdf.output()
                    if isinstance(pdf_output, str):
                        pdf_bytes = pdf_output.encode('latin-1')
                    else:
                        pdf_bytes = bytes(pdf_output)

                    st.download_button(
                        label="⬇️ Scarica PDF",
                        data=pdf_bytes,
                        file_name=f"Report_{curr_user}.pdf",
                        mime="application/pdf"
                    )
            else:
                st.info("Nessun dato registrato nel diario.")

    with t3:
        st.subheader("🔬 Coach Scientifico IA")
        
        # --- COMANDI RAPIDI ---
        st.write("💡 **Azioni Rapide:**")
        c1, c2, c3, c4 = st.columns(4)
        fast_q = None
        if c1.button("🌙 Recupero Notte"): fast_q = "Dammi 3 consigli scientifici per recuperare dopo la notte."
        if c2.button("🥗 Dieta"): fast_q = "Cosa mangiare durante il turno notturno per restare vigili?"
        if c3.button("☕ Stop Caffeina"): fast_q = "A che ora dovrei bere l'ultimo caffè prima di dormire?"
        if c4.button("🗑️ Reset Chat"): 
            st.session_state.messages = []
            st.rerun()

        for m in st.session_state.messages:
            with st.chat_message(m["role"]): st.markdown(m["content"])

        prompt = st.chat_input("Chiedi al Coach...")
        query = fast_q or prompt

        if query:
            st.session_state.messages.append({"role": "user", "content": query})
            with st.chat_message("user"): st.markdown(query)
            with st.chat_message("assistant"):
                client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                sys_msg = "Sei un esperto di cronobiologia. Rispondi in italiano."
                if not is_premium: sys_msg += " Rispondi in max 30 parole."
                
                chat_res = client.chat.completions.create(
                    messages=[{"role": "system", "content": sys_msg}] + st.session_state.messages,
                    model="llama-3.1-8b-instant"
                )
                ans = chat_res.choices[0].message.content
                st.markdown(ans)
                st.session_state.messages.append({"role": "assistant", "content": ans})

    st.caption("Dati protetti dal GDPR svizzero (Zurigo).")
