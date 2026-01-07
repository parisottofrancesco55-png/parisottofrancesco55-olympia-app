import streamlit as st
import google.generativeai as genai
from PIL import Image

# Configurazione
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥")
st.title("🏥 TurnoSano AI: Coach per Infermieri")

# Incolla la tua chiave qui
CHIAVE = "AIzaSyD6zZAeP8EPcbMZ9q7yKcid3z7HGRXA1ms"
genai.configure(api_key=CHIAVE)
model = genai.GenerativeModel('models/gemini-2.0-flash')

st.write("Benvenuto! Carica la foto del tuo turno per ricevere consigli personalizzati.")

file_caricato = st.file_uploader("Carica o scatta una foto al tabellone turni", type=["jpg", "jpeg", "png"])

if st.button("Analizza Turno"):
    if file_caricato:
        with st.spinner('Analisi in corso...'):
            img = Image.open(file_caricato)
            istruzioni = "Sei un coach per infermieri. Analizza il turno in foto e dai consigli su sonno e dieta."
            risposta = model.generate_content([istruzioni, img])
            st.success("Consiglio del Coach:")
            st.markdown(risposta.text)
    else:
        st.warning("Per favore, carica prima una foto!")
