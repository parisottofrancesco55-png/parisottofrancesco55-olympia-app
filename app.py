import streamlit as st
import requests
import base64
from PIL import Image
import io

# 1. Configurazione Pagina
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥")
st.title("🏥 TurnoSano AI")

# 2. Recupero della NUOVA chiave dai Secrets
API_KEY = st.secrets.get("GOOGLE_API_KEY")

if not API_KEY:
    st.error("Chiave API non trovata nei Secrets!")
    st.stop()

# 3. Funzione aggiornata alla versione stabile (v1) e modello flash
def chiedi_a_gemini(testo, immagine=None):
    # NOTA: Usiamo /v1/ e gemini-1.5-flash
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={API_KEY}"
    
    headers = {'Content-Type': 'application/json'}
    
    # Prepariamo il contenuto
    prompt_sistema = "Sei un coach per infermieri. Rispondi in italiano."
    parts = [{"text": f"{prompt_sistema}\n\nDomanda: {testo}"}]
    
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
    
    # Chiamata HTTP
    response = requests.post(url, headers=headers, json=payload)
    return response.json()

# 4. Interfaccia
domanda = st.text_input("Fai la tua domanda:")
foto = st.file_uploader("Carica foto turni:", type=["jpg", "jpeg", "png"])

if st.button("Chiedi al Coach 🚀"):
    if domanda or foto:
        with st.spinner("Il Coach sta analizzando..."):
            try:
                img_obj = Image.open(foto) if foto else None
                risultato = chiedi_a_gemini(domanda if domanda else "Analizza questo turno", img_obj)
                
                if 'candidates' in risultato:
                    testo_risposta = risultato['candidates'][0]['content']['parts'][0]['text']
                    st.success("✅ Risposta:")
                    st.markdown(testo_risposta)
                else:
                    msg_errore = risultato.get('error', {}).get('message', 'Errore ignoto')
                    st.error(f"Errore da Google: {msg_errore}")
            except Exception as e:
                st.error(f"Errore tecnico: {e}")
    else:
        st.warning("Scrivi qualcosa!")
