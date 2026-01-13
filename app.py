import streamlit as st
import pandas as pd
from supabase import create_client, Client
from groq import Groq
import streamlit_authenticator as stauth
from stauth.hasher import Hasher
import plotly.graph_objects as go
from fpdf import FPDF
from datetime import datetime
import io

# --- 1. CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="TurnoSano IA", page_icon="🏥", layout="wide")

# --- 2. CONNESSIONE SUPABASE ---
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

sb = init_connection()

# --- 3. FUNZIONI DATABASE ---
def get_user_data():
    try:
        res = sb.table("profiles").select("*").execute()
        usernames = {}
        for u in res.data:
            usernames[u["username"]] = {
                "name": u["name"],
                "password": u["password"],
                "is_premium": u.get("is_premium", False)
            }
        return {"usernames": usernames}
    except Exception as e:
        st.error(f"Errore caricamento utenti: {e}")
        return {"usernames": {}}

# --- 4. GESTIONE AUTENTICAZIONE ---
if "auth_mode" not in st.session_state:
    st.session_state.auth_mode = "login"

db_users = get_user_data()
authenticator = stauth.Authenticate(
    db_users,
    "turnosano_cookie",
    "signature_key",
    30 # Giorni scadenza cookie
)

# --- 5. INTERFACCIA LOGIN / REGISTRAZIONE ---
if not st.session_state.get("authentication_status"):
    if st.session_state.auth_mode == "login":
        st.title("🏥 TurnoSano IA - Login")
        name, authentication_status, username = authenticator.login(location='main')
        
        if authentication_status is False:
            st.error("Username o password non corretti")
        elif authentication_status is None:
            st.warning("Inserisci le tue credenziali")
        
        st.write("---")
        if st.button("Nuovo utente? Registrati qui"):
            st.session_state.auth_mode = "signup"
            st.rerun()

    elif st.session_state.auth_mode == "signup":
        st.title("📝 Registrazione Operatore")
        with st.form("signup_form"):
            new_user = st.text_input("Username (es: mrossi)").lower().strip()
            new_name = st.text_input("Nome Completo")
            new_pw = st.text_input("Password", type="password")
            confirm_pw = st.text_input("Conferma Password", type="password")
            st.info("I tuoi dati risiedono su server crittografati a Zurigo (CH).")
            
            if st.form_submit_button("Crea Account"):
                if new_pw != confirm_pw:
                    st.error("Le password non coincidono")
                elif new_user in db_users["usernames"]:
                    st.error("Username già esistente")
                elif len(new_pw) < 6:
                    st.error("La password deve essere di almeno 6 caratteri")
                else:
                    hashed_pw = Hasher([new_pw]).generate()[0]
                    sb.table("profiles").insert({
                        "username": new_user,
                        "name": new_name,
                        "password": hashed_pw,
                        "is_premium": False
                    }).execute()
                    st.success("✅ Account creato con successo! Ora puoi accedere.")
                    st.session_state.auth_mode = "login"
                    st.rerun()
        
        if st.button("Vai al Login"):
            st.session_state.auth_mode = "login"
            st.rerun()

# --- 6. AREA APPLICATIVO (UTENTE LOGGATO) ---
else:
    # Logout in sidebar
    authenticator.logout('Disconnetti', 'sidebar')
    
    # Recupero stato Premium in tempo reale
    user_id = st.session_state["username"]
    user_info = db_users["usernames"].get(user_id, {})
    is_premium = user_info.get("is_premium", False)

    st.sidebar.title(f"Ciao, {st.session_state['name']}!")
    if is_premium:
        st.sidebar.success("💎 Account PREMIUM Attivo")
    else:
        st.sidebar.warning("🛡️ Account BASE")
        if st.sidebar.button("🚀 Passa a Premium"):
            st.sidebar.markdown(f"[Vai al pagamento sicuri su Stripe]({st.secrets.get('STRIPE_CHECKOUT_URL', '#')})")

    st.title("🏥 Dashboard Benessere Turnisti")

    tab1, tab2, tab3 = st.tabs(["📝 Diario Giornaliero", "📊 Analisi Dati", "🔬 Coach IA"])

    # --- TAB 1: DIARIO ---
    with tab1:
        st.subheader("Inserisci i parametri di oggi")
        with st.form("wellness_entry"):
            fatica = st.select_slider("Quanto ti senti stanco? (1=Riposato, 10=Esausto)", options=range(1,11), value=5)
            sonno = st.number_input("Ore di sonno effettive", min_value=0.0, max_value=24.0, value=7.0, step=0.5)
            note = st.text_area("Note sul turno (es: turno di notte, rientro)")
            
            if st.form_submit_button("Salva nel Database"):
                sb.table("wellness").insert({
                    "user_id": user_id,
                    "fatica": fatica,
                    "ore_sonno": sonno,
                    "created_at": datetime.now().isoformat()
                }).execute()
                st.success("Dati archiviati in modo sicuro a Zurigo.")

    # --- TAB 2: ANALISI E PDF ---
    with tab2:
        if not is_premium:
            st.error("🔒 Questa sezione è riservata agli utenti Premium.")
            st.image("https://via.placeholder.com/800x400.png?text=Abbonati+per+vedere+i+tuoi+grafici+storici")
        else:
            st.subheader("Il tuo andamento storico")
            res = sb.table("wellness").select("*").eq("user_id", user_id).order("created_at").execute()
            if res.data:
                df = pd.DataFrame(res.data)
                df['created_at'] = pd.to_datetime(df['created_at'])
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df['created_at'], y=df['fatica'], name="Livello Fatica", line=dict(color='#FF4B4B', width=3)))
                fig.add_trace(go.Bar(x=df['created_at'], y=df['ore_sonno'], name="Ore Sonno", marker_color='#1C83E1', opacity=0.6))
                st.plotly_chart(fig, use_container_width=True)
                
                st.divider()
                st.subheader("📄 Generazione Report Medico")
                if st.button("Compila Report PDF"):
                    pdf = FPDF()
                    pdf.add_page()
                    pdf.set_font("Arial", 'B', 16)
                    pdf.cell(200, 10, "REPORT CLINICO TURNOSANO IA", ln=True, align='C')
                    pdf.set_font("Arial", size=12)
                    pdf.ln(10)
                    pdf.cell(200, 10, f"Operatore: {st.session_state['name']}", ln=True)
                    pdf.cell(200, 10, f"Periodo: {df['created_at'].min().strftime('%d/%m/%Y')} - {df['created_at'].max().strftime('%d/%m/%Y')}", ln=True)
                    pdf.ln(10)
                    
                    # Tabella PDF
                    pdf.set_fill_color(230, 230, 230)
                    pdf.cell(60, 10, "Data", 1, 0, 'C', True)
                    pdf.cell(60, 10, "Fatica (1-10)", 1, 0, 'C', True)
                    pdf.cell(60, 10, "Ore Sonno", 1, 1, 'C', True)
                    
                    for _, row in df.tail(20).iterrows():
                        pdf.cell(60, 10, row['created_at'].strftime('%d/%m/%Y'), 1)
                        pdf.cell(60, 10, str(row['fatica']), 1)
                        pdf.cell(60, 10, str(row['ore_sonno']), 1, 1)
                    
                    html_pdf = pdf.output(dest='S').encode('latin-1', errors='replace')
                    st.download_button("⬇️ Scarica Report PDF", html_pdf, "report_turnosano.pdf", "application/pdf")
            else:
                st.info("Nessun dato trovato. Inizia a compilare il diario!")

    # --- TAB 3: COACH IA ---
    with tab3:
        st.subheader("🔬 Chiedi al Coach Scientifico")
        
        # Inizializzazione chat
        if "messages" not in st.session_state:
            st.session_state.messages = []

        # Comandi rapidi
        c1, c2, c3 = st.columns(3)
        fast_cmd = None
        if c1.button("🌙 Recupero post-notte"): fast_cmd = "Dammi 3 consigli scientifici per recuperare dopo un turno di notte."
        if c2.button("🥗 Dieta Turnista"): fast_cmd = "Cosa devo mangiare per non avere cali glicemici in turno?"
        if c3.button("☕ Gestione Caffeina"): fast_cmd = "Qual è l'orario limite per il caffè se finisco alle 14:00?"

        # Visualizzazione messaggi precedenti
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        # Input utente
        prompt = st.chat_input("Scrivi qui la tua domanda...")
        query = fast_cmd if fast_cmd else prompt

        if query:
            st.session_state.messages.append({"role": "user", "content": query})
            with st.chat_message("user"):
                st.markdown(query)

            with st.chat_message("assistant"):
                client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                
                system_prompt = "Sei un esperto di cronobiologia medica. Parla in italiano. "
                if not is_premium:
                    system_prompt += "Sei in modalità limitata: dai risposte brevi (max 50 parole) e invita l'utente a passare al Premium per analisi dettagliate."
                
                chat_completion = client.chat.completions.create(
                    messages=[{"role": "system", "content": system_prompt}] + st.session_state.messages,
                    model="llama-3.1-8b-instant",
                )
                response = chat_completion.choices[0].message.content
                st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})

    st.markdown("---")
    st.caption("Dati protetti dal GDPR svizzero. TurnoSano IA v2.0")
