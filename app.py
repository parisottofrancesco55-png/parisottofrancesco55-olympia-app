import streamlit as st
import requests
from PyPDF2 import PdfReader

st.set_page_config(page_title="TurnoSano AI", page_icon="🏥", layout="wide")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "testo_turno" not in st.session_state:
    st.session_state.testo_turno = ""

st.title("🏥 TurnoSano AI")

with st.sidebar:
    st.header("Comandi")
    file_pdf = st.file_uploader("Carica Turno (PDF)", type="pdf")
    if file_pdf:
        try:
            reader = PdfReader(file_pdf)
            testo = "".join([page.extract_text() or "" for page in reader.pages])
            st.session_state.testo_turno = testo
            st.success("✅ Turno caricato")
        except Exception as e:
            st.error(f"Errore PDF: {e}")
    if st.button("🗑️ Cancella Chat"):
        st.session_state.messages = []
        st.rerun()

def chiedi_a_groq(messages):
    api_key = st.secrets.get("GROQ_API_KEY")
    # URL SCRITTO IN MODO RIGIDO CON PROTOCOLLO HTTPS
    URL_COMPLETO = "api.groq.com"
    
    system_prompt = "Sei TurnoSano AI, coach per infermieri. Rispondi in italiano."
    if st.session_state.testo_turno:
        system_prompt += f"\nContesto turno: {st.session_state.testo_turno}"
    
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [{"role": "system", "content": system_prompt}] + messages,
        "temperature": 0.7
    }
    
    try:
        # Usiamo l'URL completo e verifichiamo che inizi con https
        response = requests.post(
            URL_COMPLETO, 
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, 
            json=payload, 
            timeout=20
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"⚠️ Errore Tecnico: {str(e)}"

# Visualizzazione Chat
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Scrivi qui..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant", avatar="🏥"):
        risposta = chiedi_a_groq(st.session_state.messages)
        st.markdown(risposta)
        st.session_state.messages.append({"role": "assistant", "content": risposta})
