import streamlit as st
import requests

st.set_page_config(page_title="TurnoSano AI", page_icon="🏥")
st.title("🏥 TurnoSano AI")

# Recupero Chiave
API_KEY = st.secrets.get("GOOGLE_API_KEY")

def chiedi_a_gemini(testo):
    # Usiamo gemini-pro (versione 1.0 stabile, solo testo)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={API_KEY}"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{
            "parts": [{"text": f"Sei un coach per infermieri. Rispondi in italiano: {testo}"}]
        }]
    }
    response = requests.post(url, headers=headers, json=payload)
    return response.json()

domanda = st.text_input("Fai una domanda al coach (es. come gestire il turno di notte):")

if st.button("Chiedi 🚀"):
    if domanda:
        with st.spinner("Il Coach sta rispondendo..."):
            try:
                res = chiedi_a_gemini(domanda)
                if 'candidates' in res:
                    risposta = res['candidates'][0]['content']['parts'][0]['text']
                    st.success("Consiglio del Coach:")
                    st.markdown(risposta)
                else:
                    st.error(f"Errore API: {res.get('error', {}).get('message', 'Errore ignoto')}")
            except Exception as e:
                st.error(f"Errore tecnico: {e}")
    else:
        st.warning("Inserisci una domanda!")
