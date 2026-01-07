import streamlit as st
import requests
import base64
from PIL import Image
import io

st.set_page_config(page_title="TurnoSano AI", page_icon="🏥")
st.title("🏥 TurnoSano AI")

API_KEY = st.secrets.get("GOOGLE_API_KEY")

if not API_KEY:
    st.error("Chiave API mancante!")
    st.stop()

def chiedi_a_gemini(testo, immagine=None):
    # Qui usiamo gemini-1.5-flash perché supporta le foto, 
    # ma se dà 404 scrivi solo testo e cambieremo in gemini-pro
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}"
    headers = {'Content-Type': 'application/json'}
    parts = [{"text": f"Sei un coach per infermieri: {testo}"}]
    
    if immagine:
        buffered = io.BytesIO()
        immagine.save(buffered, format="JPEG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        parts.append({"inline_data": {"mime_type": "image/jpeg", "data": img_str}})

    payload = {"contents": [{"parts": parts}]}
    response = requests.post(url, headers=headers, json=payload)
    return response.json()

domanda = st.text_input("Fai una domanda:")
foto = st.file_uploader("Carica foto:", type=["jpg", "png", "jpeg"])

if st.button("Chiedi 🚀"):
    if domanda or foto:
        with st.spinner("Pensando..."):
            try:
                img_obj = Image.open(foto) if foto else None
                res = chiedi_a_gemini(domanda if domanda else "Analizza turno", img_obj)
                if 'candidates' in res:
                    st.write(res['candidates'][0]['content']['parts'][0]['text'])
                else:
                    st.error(f"Errore: {res}")
            except Exception as e:
                st.error(f"Errore: {e}")
