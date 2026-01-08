import streamlit as st
import requests
from PyPDF2 import PdfReader

# Configurazione Pagina
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥")
st.title("🏥 TurnoSano AI")
st.write("Coach per Infermieri - Carica il tuo turno PDF")

# Recupero Chiave Groq
API_KEY = st.secrets.get("GROQ_API_KEY")

def estrai_testo_da_pdf(pdf_file):
    try:
        reader = PdfReader(pdf_file)
        testo = ""
        for page in reader.pages:
            testo += page.extract_text()
        return testo
    except Exception as e:
        st.error(f"Errore nella lettura del PDF: {e}")
        return None

def chiedi_a_groq(testo_utente, contesto_pdf=""):
    url = "api.groq.com"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Costruiamo il messaggio includendo il turno se presente
    prompt_sistema = "Sei TurnoSano AI, un coach esperto per infermieri. "
    if contesto_pdf:
        prompt_sistema += f"In allegato trovi il testo estratto dal turno dell'utente: {contesto_pdf}. "
    prompt_sistema += "Rispondi in italiano con consigli pratici su sonno e gestione dei turni."

    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": testo_utente}
        ],
        "temperature": 0.5
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error_interno": str(e)}

# --- INTERFACCIA ---

# 1. Caricamento PDF (Opzionale)
st.sidebar.header("📂 Carica Turno")
file_pdf = st.sidebar.file_uploader("Carica il tuo turno in PDF", type="pdf")
testo_turno = ""

if file_pdf:
    testo_turno = estrai_testo_da_pdf(file_pdf)
    if testo_turno:
        st.sidebar.success("Turno caricato correttamente!")

# 2. Chat principale
domanda = st.text_input("Chiedi un consiglio (il Coach vedrà il turno se lo hai caricato):")

if st.button("Chiedi al Coach 🚀"):
    if not API_KEY:
        st.error("Configura la GROQ_API_KEY nei Secrets.")
    elif domanda:
        with st.spinner("Analizzando il turno e preparando i consigli..."):
            res = chiedi_a_groq(domanda, contesto_pdf=testo_turno)
            
            if 'choices' in res:
                risposta = res['choices'][0]['message']['content']
                st.success("Consiglio personalizzato:")
                st.markdown(risposta)
            else:
                st.error(f"Errore: {res.get('error_interno', 'Errore API')}")
    else:
        st.warning("Scrivi una domanda!")

st.divider()
st.caption("Gennaio 2026 - Powered by Groq & Llama 3.1")
