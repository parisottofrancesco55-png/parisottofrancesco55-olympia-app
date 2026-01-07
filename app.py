import streamlit as st
import google.generativeai as genai
from PIL import Image
import os

# Configurazione Pagina
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥")

# Funzione di configurazione pulita
def init_google_ai():
    if "GOOGLE_API_KEY" in st.secrets:
        # Forziamo l'uso della versione 1 stabile dell'API
        os.environ["GOOGLE_API_VERSION"] = "v1"
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        # Usiamo il modello più recente e supportato
        return genai.GenerativeModel('gemini-1.5-flash-latest')
    else:
        st.error("Chiave API mancante nei Secrets!")
        return None

model = init_google_ai()

st.title("🏥 TurnoSano AI")
st.write("Coach per Infermieri - Pronto a rispondere")

domanda = st.text_input("Fai la tua domanda:")
foto = st.file_uploader("O carica il tabellone turni:", type=["jpg", "jpeg", "png"])

if st.button("Invia al Coach"):
    if model and (domanda or foto):
        with st.spinner("Analisi in corso..."):
            try:
                contenuto = []
                if domanda: contenuto.append(domanda)
                if foto: contenuto.append(Image.open(foto))
                
                # Istruzione di sistema aggiunta nel prompt
                prompt = "Sei un coach per infermieri. Rispondi in italiano in modo utile."
                contenuto.insert(0, prompt)
                
                response = model.generate_content(contenuto)
                st.success("Risposta del Coach:")
                st.markdown(response.text)
            except Exception as e:
                st.error(f"Errore tecnico: {e}")
                st.info("Se vedi ancora 404, prova a rigenerare la chiave API su Google AI Studio.")
    else:
        st.warning("Inserisci del testo o una foto.")
