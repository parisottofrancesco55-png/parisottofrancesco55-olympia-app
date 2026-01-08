import streamlit as st
import requests
from PyPDF2 import PdfReader

# Configurazione Pagina
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥")
st.title("🏥 TurnoSano AI")

# Recupero Chiave Groq
API_KEY = st.secrets.get("GROQ_API_KEY")

def chiedi_a_groq(testo_utente, contesto_pdf=""):
    # URL DEFINITO IN MODO RIGIDO PER EVITARE ERRORI DI SCHEMA
    base_url = "https://api.groq.com/openai/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    prompt_sistema = "Sei TurnoSano AI, un coach esperto per infermieri. "
    if contesto_pdf:
        prompt_sistema += f"Dati del turno: {contesto_pdf}. "
    prompt_sistema += "Rispondi in italiano."

    payload = {
        "model": "llama-3.1-8b-instant", # Modello supportato nel 2026
        "messages": [
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": testo_utente}
        ]
    }
    
    try:
        # .strip() rimuove eventuali spazi o invii invisibili
        response = requests.post(base_url.strip(), headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error_tecnico": str(e)}

# --- INTERFACCIA ---
file_pdf = st.sidebar.file_uploader("Carica turno PDF", type="pdf")
testo_estratto = ""

if file_pdf:
    reader = PdfReader(file_pdf)
    for page in reader.pages:
        testo_estratto += page.extract_text() + "\n"
    st.sidebar.success("PDF Letto!")

domanda = st.text_input("Fai una domanda:")

if st.button("Invia 🚀"):
    if domanda and API_KEY:
        with st.spinner("Risposta in corso..."):
            res = chiedi_a_groq(domanda, testo_estratto)
            if 'choices' in res:
                st.markdown(res['choices'][0]['message']['content'])
            else:
                st.error(f"Errore: {res.get('error_tecnico', 'Errore API')}")
