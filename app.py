import streamlit as st
import google.generativeai as genai
from PIL import Image

# Configurazione Pagina
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥")

# Configurazione API
if "GOOGLE_API_KEY" in st.secrets:
    # IMPORTANTE: Forziamo la configurazione a ignorare v1beta
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"], transport='rest')
else:
    st.error("Chiave API non trovata nei Secrets!")
    st.stop()

# Proviamo a usare il modello gemini-pro (quello più compatibile in assoluto)
model = genai.GenerativeModel('gemini-1.5-flash')

st.title("🏥 TurnoSano AI")
st.write("Coach per Infermieri")

domanda = st.text_input("Fai una domanda:")
foto = st.file_uploader("Carica foto turni:", type=["jpg", "jpeg", "png"])

if st.button("Chiedi al Coach"):
    if domanda or foto:
        with st.spinner("Analisi..."):
            try:
                # Costruiamo l'input
                parts = ["Sei un coach per infermieri. Rispondi alla domanda o analizza la foto."]
                if domanda: parts.append(domanda)
                if foto: parts.append(Image.open(foto))
                
                # Chiamata al modello
                response = model.generate_content(parts)
                st.markdown(response.text)
                
            except Exception as e:
                # Se fallisce ancora, proviamo il modello "gemini-pro"
                st.warning("Il modello Flash non risponde, provo il modello Pro...")
                try:
                    alt_model = genai.GenerativeModel('gemini-pro')
                    response = alt_model.generate_content(domanda if domanda else "Ciao")
                    st.markdown(response.text)
                except Exception as e2:
                    st.error(f"Errore persistente: {e2}")
    else:
        st.warning("Inserisci qualcosa!")
