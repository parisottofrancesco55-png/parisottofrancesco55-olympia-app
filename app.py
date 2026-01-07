import streamlit as st
import google.generativeai as genai
from PIL import Image

# Configurazione Pagina
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥")

# Configurazione API
if "GOOGLE_API_KEY" in st.secrets:
    # Forziamo la configurazione pulita
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
else:
    st.error("Configura la chiave API nei Secrets!")
    st.stop()

# Usiamo il modello PRO che ha una compatibilità più ampia
model = genai.GenerativeModel('gemini-1.5-pro')

st.title("🏥 TurnoSano AI")
st.write("Il coach per infermieri è pronto ad aiutarti.")

# Input
domanda = st.text_input("Fai una domanda (es: consigli per il turno di notte):")
foto = st.file_uploader("O carica la foto del tabellone turni:", type=["jpg", "jpeg", "png"])

if st.button("Chiedi al Coach 🚀"):
    if domanda or foto:
        with st.spinner("Il Coach sta analizzando..."):
            try:
                contenuto = []
                # Istruzione di sistema come stringa
                istruzioni = "Sei TurnoSano AI, un coach per infermieri. Dai consigli pratici su sonno e dieta."
                
                if foto:
                    img = Image.open(foto)
                    # Se c'è una foto, inviamo una lista con testo e immagine
                    testo_completo = f"{istruzioni}\nDomanda: {domanda}" if domanda else istruzioni
                    risposta = model.generate_content([testo_completo, img])
                else:
                    # Se c'è solo testo
                    risposta = model.generate_content(f"{istruzioni}\nDomanda: {domanda}")
                
                st.success("Consiglio del Coach:")
                st.markdown(risposta.text)
                
            except Exception as e:
                st.error(f"Errore: {e}")
                st.info("Prova a ricaricare la pagina tra un istante.")
    else:
        st.warning("Inserisci una domanda o una foto!")
