import streamlit as st
import requests
import base64
from PIL import Image
import io

# 1. Configurazione Pagina
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥")
st.title("🏥 TurnoSano AI")

# 2. Recupero Chiave dai Secrets
API_KEY = st.secrets.get("GOOGLE_API_KEY")

if not API_KEY:
    st.error("⚠️ Chiave API non trovata! Vai in Settings > Secrets e aggiungi: GOOGLE_API_KEY = 'tua_chiave'")
    st.stop()

# 3. Funzione di comunicazione diretta con Google
def chiedi_a_gemini(testo, immagine=None):
    # Usiamo l'URL diretto per evitare errori della libreria
    # Cerca questa riga e sostituiscila:
url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={API_KEY}"
    
    headers = {'Content-Type': 'application/json'}
    
    # Prompt di sistema per istruire l'IA
    prompt_sistema = "Sei TurnoSano AI, un coach esperto per infermieri. Rispondi in italiano in modo empatico e pratico."
    testo_finale = f"{prompt_sistema}\n\nDomanda utente: {testo}"
    
    parts = [{"text": testo_finale}]
    
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

# 4. Interfaccia Utente
st.write("Benvenuto! Chiedi consigli su turni, riposo o alimentazione.")

domanda = st.text_input("Scrivi qui la tua domanda:")
foto = st.file_uploader("Oppure carica la foto dei turni:", type=["jpg", "jpeg", "png"])

if st.button("Chiedi al Coach 🚀"):
    if domanda or foto:
        with st.spinner("Il Coach sta pensando..."):
            try:
                img_obj = Image.open(foto) if foto else None
                testo_invio = domanda if domanda else "Analizza questa foto e dai consigli per gestire il turno."
                
                risultato = chiedi_a_gemini(testo_invio, img_obj)
                
                if 'candidates' in risultato:
                    risposta_ai = risultato['candidates'][0]['content']['parts'][0]['text']
                    st.success("✅ Consiglio del Coach:")
                    st.markdown(risposta_ai)
                else:
                    errore_msg = risultato.get('error', {}).get('message', 'Errore sconosciuto')
                    st.error(f"Errore dall'API di Google: {errore_msg}")
                    st.info("Se l'errore è 404, prova a generare una nuova chiave su Google AI Studio.")
            except Exception as e:
                st.error(f"Errore tecnico: {e}")
    else:
        st.warning("Inserisci una domanda o carica una foto per iniziare.")
