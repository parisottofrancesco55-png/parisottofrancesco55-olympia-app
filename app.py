import streamlit as st
import requests
from PyPDF2 import PdfReader

# 1. Configurazione Pagina
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥", layout="wide")

# Inizializzazione della memoria
if "messages" not in st.session_state:
    st.session_state.messages = []
if "testo_turno" not in st.session_state:
    st.session_state.testo_turno = ""

st.title("🏥 TurnoSano AI")
st.write("Coach per Infermieri (Versione 2026)")

# --- FUNZIONE API ---
def chiedi_a_groq(messages):
    api_key = st.secrets.get("GROQ_API_KEY")
    # URL BLINDATO CON HTTPS
    url = "api.groq.com"
    
    system_prompt = "Sei TurnoSano AI, coach esperto per infermieri. Rispondi in italiano."
    if st.session_state.testo_turno:
        system_prompt += f"\nContesto turno: {st.session_state.testo_turno}"
    
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [{"role": "system", "content": system_prompt}] + messages,
        "temperature": 0.7
    }
    
    try:
        response = requests.post(url, headers={"Authorization": f"Bearer {api_key}"}, json=payload, timeout=20)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"⚠️ Errore API: {str(e)}"

# --- SIDEBAR ---
with st.sidebar:
    st.header("📂 Carica Turno")
    file_pdf = st.file_uploader("Carica il tuo PDF", type="pdf")
    if file_pdf:
        reader = PdfReader(file_pdf)
        testo_pdf = "".join([page.extract_text() or "" for page in reader.pages])
        st.session_state.testo_turno = testo_pdf
        st.success("✅ PDF Caricato")
    
    if st.button("🗑️ Reset Chat"):
        st.session_state.messages = []
        st.rerun()

# --- INTERFACCIA: TASTI RAPIDI ---
st.write("### ⚡ Suggerimenti Rapidi")
col1, col2, col3 = st.columns(3)

# Variabile per gestire l'input da pulsante
input_utente = None

with col1:
    if st.button("🌙 SOS Turno Notte"):
        input_utente = "Dammi una strategia per gestire il turno di notte e il riposo di domani."
with col2:
    if st.button("🥗 Alimentazione"):
        input_utente = "Cosa mangiare durante il turno per non essere stanchi?"
with col3:
    if st.button("🧘 Stress Relief"):
        input_utente = "Esercizio rapido per scaricare la tensione."

# --- CHAT INPUT ---
if prompt := st.chat_input("Scrivi qui la tua domanda..."):
    input_utente = prompt

# --- LOGICA DI RISPOSTA ---
if input_utente:
    # Aggiungi messaggio utente alla memoria
    st.session_state.messages.append({"role": "user", "content": input_utente})
    
    # Richiesta immediata all'AI
    with st.spinner("Il Coach sta analizzando..."):
        risposta_ai = chiedi_a_groq(st.session_state.messages)
        st.session_state.messages.append({"role": "assistant", "content": risposta_ai})

# --- VISUALIZZAZIONE CHAT ---
st.write("---")
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
