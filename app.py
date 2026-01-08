import streamlit as st
from groq import Groq
from PyPDF2 import PdfReader

# Configurazione Pagina
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥", layout="wide")

# Inizializzazione SDK Groq (Gestisce l'URL automaticamente)
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except Exception as e:
    st.error("Errore configurazione API Key nei Secrets.")

# Inizializzazione Sessione
if "messages" not in st.session_state:
    st.session_state.messages = []
if "testo_turno" not in st.session_state:
    st.session_state.testo_turno = ""

st.title("🏥 TurnoSano AI")
st.caption("Versione 2026 - Powered by Groq SDK")

# --- SIDEBAR ---
with st.sidebar:
    st.header("📂 Carica Turno")
    file_pdf = st.file_uploader("Carica PDF", type="pdf")
    if file_pdf:
        reader = PdfReader(file_pdf)
        testo = "".join([p.extract_text() or "" for p in reader.pages])
        st.session_state.testo_turno = testo
        st.success("PDF Caricato!")
    
    if st.button("🗑️ Reset Chat"):
        st.session_state.messages = []
        st.rerun()

# --- AZIONI RAPIDE ---
st.write("### ⚡ Suggerimenti")
c1, c2, c3 = st.columns(3)
input_utente = None

if c1.button("🌙 SOS Notte"): input_utente = "Consigli per turno di notte."
if c2.button("🥗 Dieta"): input_utente = "Cosa mangiare in turno?"
if c3.button("🧘 Stress"): input_utente = "Esercizio relax rapido."

# --- CHAT LOGIC ---
if prompt := st.chat_input("Scrivi qui..."):
    input_utente = prompt

if input_utente:
    st.session_state.messages.append({"role": "user", "content": input_utente})
    
    # Preparazione Messaggi per Groq
    prompt_sistema = "Sei TurnoSano AI, un coach per infermieri. Rispondi in italiano."
    if st.session_state.testo_turno:
        prompt_sistema += f"\nContesto turno: {st.session_state.testo_turno}"
    
    messages_api = [{"role": "system", "content": prompt_sistema}] + st.session_state.messages

    try:
        # Chiamata tramite SDK (Niente URL manuale = Niente errore Scheme)
        chat_completion = client.chat.completions.create(
            messages=messages_api,
            model="llama-3.1-8b-instant",
        )
        risposta = chat_completion.choices[0].message.content
        st.session_state.messages.append({"role": "assistant", "content": risposta})
    except Exception as e:
        st.error(f"Errore tecnico: {str(e)}")

# --- DISPLAY ---
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
