import streamlit as st
import requests
import base64
from PIL import Image
import io

# 1. Configurazione Pagina
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥")
st.title("🏥 TurnoSano AI")

# 2. Recupero Chiave
API_KEY = st.secrets.get("GOOGLE_API_KEY")

if not API_KEY:
    st.error("Chiave API non trovata nei Secrets!")
    st.stop()

# 3. Funzione per chiamare Google direttamente (senza libreria genai)
def chiedi_a_gemini(testo, immagine=None):
    # Forziamo l'indirizzo V1 (NON beta)
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={API_KEY}"
    
    headers = {'Content-Type': 'application/json'}
    
    # Prepariamo il testo
    parts = [{"text": f"Sei un coach per infermieri. Rispondi in italiano: {testo}"}]
    
    # Prepariamo l'immagine se presente
    if immagine:
        buffered = io.BytesIO()
        immagine.save(buffered, format="JPEG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        parts.append({
            "inline_data": {
                "mime_type": "image/jpeg",
                "data": img_str
            }
        })

    payload = {"contents": [{"parts": parts}]}
    
    response = requests.post(url, headers=headers, json=payload)
    return response.json()

# 4. Interfaccia
domanda = st.text_input("Fai una domanda al coach:")
foto = st.file_uploader("Carica foto turni:", type=["jpg", "jpeg", "png"])

if st.button("Chiedi al Coach 🚀"):
    if domanda or foto:
        with st.spinner("Analisi in corso..."):
            try:
                img_obj = Image.open(foto) if foto else None
                risultato = chiedi_a_gemini(domanda if domanda else "Analizza questo turno", img_obj)
                
                # Estraiamo la risposta dal JSON di Google
                if 'candidates' in risultato:
                    testo_risposta = risultato['candidates'][0]['content']['parts'][0]['text']
                    st.success("Consiglio del Coach:")
                    st.markdown(testo_risposta)
                else:
                    st.error(f"Errore API: {risultato}")
            except Exception as e:
                st.error(f"Errore: {e}")
    else:
        st.warning("Inserisci qualcosa!")
