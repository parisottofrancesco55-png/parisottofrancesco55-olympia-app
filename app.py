import streamlit as st
import requests
from PyPDF2 import PdfReader

# Configurazione Pagina
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥")
st.title("🏥 TurnoSano AI")
st.write("Coach per Infermieri (Versione Gennaio 2026)")

# Recupero Chiave Groq
API_KEY = st.secrets.get("GROQ_API_KEY")

def estrai_testo_da_pdf(pdf_file):
    try:
        reader = PdfReader(pdf_file)
        testo = ""
        for page in reader.pages:
            estratto = page.extract_text()
            if estratto:
                testo += estratto + "\n"
        return testo
    except Exception as e:
        st.error(f"Errore nella lettura del PDF: {e}")
        return ""

def chiedi_a_groq(testo_utente, contesto_pdf=""):
    # URL SCRITTO IN MODO ESPLICITO E PULITO
    URL_GROQ = "api.groq.com"
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    prompt_sistema = "Sei TurnoSano AI, un coach esperto per infermieri turnisti. "
    if contesto_pdf:
        prompt_sistema += f"Analizza questo turno: {contesto_pdf}. "
    prompt_sistema += "Rispondi in italiano con consigli pratici."

    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": testo_utente}
        ],
        "temperature": 0.6
    }
    
    try:
        # Usiamo l'URL esplicito
        response = requests.post(URL_GROQ, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error_custom": str(e)}

# --- INTERFACCIA ---

st.sidebar.header("📂 Documenti")
file_pdf = st.sidebar.file_uploader("Carica il tuo turno PDF", type="pdf")

if file_pdf:
    if "testo_turno" not in st.session_state:
        st.session_state.testo_turno = estrai_testo_da_pdf(file_pdf)
    st.sidebar.success("Turno analizzato!")
else:
    st.session_state.testo_turno = ""

domanda = st.text_input("Fai una domanda al Coach:")

if st.button("Chiedi al Coach 🚀"):
    if not API_KEY:
        st.error("Configura GROQ_API_KEY nei Secrets.")
    elif domanda:
        with st.spinner("Generazione risposta..."):
            res = chiedi_a_groq(domanda, st.session_state.get("testo_turno", ""))
            
            if 'choices' in res:
                # CORREZIONE: choices è una lista, serve [0]
                risposta = res['choices'][0]['message']['content']
                st.success("Consiglio:")
                st.markdown(risposta)
            elif "error_custom" in res:
                st.error(f"Errore Tecnico: {res['error_custom']}")
            else:
                st.error(f"Errore API: {res.get('error', {}).get('message', 'Errore ignoto')}")
    else:
        st.warning("Scrivi qualcosa!")
