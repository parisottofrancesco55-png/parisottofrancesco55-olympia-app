import streamlit as st
import requests
from PyPDF2 import PdfReader

# 1. Configurazione Pagina
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥", layout="wide")

# Inizializzazione sicura dello stato
if "messages" not in st.session_state:
    st.session_state.messages = []
if "testo_turno" not in st.session_state:
    st.session_state.testo_turno = ""

st.title("🏥 TurnoSano AI")

# 2. Sidebar con gestione PDF migliorata
with st.sidebar:
    st.header("Comandi")
    file_pdf = st.file_uploader("Carica Turno (PDF)", type="pdf")
    
    if file_pdf:
        try:
            reader = PdfReader(file_pdf)
            testo = ""
            for page in reader.pages:
                testo_estratto = page.extract_text()
                if testo_estratto:
                    testo += testo_estratto + "\n"
            st.session_state.testo_turno = testo
            st.success("✅ Turno caricato correttamente")
        except Exception as e:
            st.error(f"Errore lettura PDF: {e}")

    if st.button("🗑️ Cancella Chat"):
        st.session_state.messages = []
        st.rerun()

# 3. Funzione API Robusta (Evita TypeError)
def chiedi_a_groq(messages):
    api_key = st.secrets.get("GROQ_API_KEY")
    if not api_key:
        return "❌ Errore: Manca la chiave API nei Secrets di Streamlit."
    
    url = "api.groq.com"
    
    system_message = "Sei TurnoSano AI, coach per infermieri. Rispondi in italiano."
    if st.session_state.testo_turno:
        system_message += f"\nContesto turno: {st.session_state.testo_turno}"
    
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [{"role": "system", "content": system_message}] + messages,
        "temperature": 0.7
    }
    
    try:
        response = requests.post(url, headers={"Authorization": f"Bearer {api_key}"}, json=payload, timeout=20)
        data = response.json()
        
        # Controllo di sicurezza per evitare TypeError se la struttura è diversa
        if "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0].get("message", {}).get("content", "Errore: Contenuto vuoto")
        else:
            messaggio_errore = data.get("error", {}).get("message", "Risposta API invalida")
            return f"⚠️ Errore da Groq: {messaggio_errore}"
            
    except Exception as e:
        return f"⚠️ Errore di connessione: {str(e)}"

# 4. Chat Interattiva
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Scrivi qui la tua domanda..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="🏥"):
        with st.spinner("Il Coach sta analizzando..."):
            risposta = chiedi_a_groq(st.session_state.messages)
            st.markdown(risposta)
            st.session_state.messages.append({"role": "assistant", "content": risposta})
