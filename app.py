import streamlit as st
import requests

# Configurazione Pagina
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥")
st.title("🏥 TurnoSano AI")
st.write("Coach per Infermieri (Aggiornato 2026)")

# Recupero Chiave Groq
API_KEY = st.secrets.get("GROQ_API_KEY")

def chiedi_a_groq(testo):
    # L'URL DEVE iniziare con https://
    url = "https://api.groq.com/openai/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "llama-3.1-8b-instant", # Modello aggiornato 2026
        "messages": [
            {
                "role": "system", 
                "content": "Sei TurnoSano AI, un coach esperto per infermieri turnisti. Rispondi in italiano con consigli pratici."
            },
            {"role": "user", "content": testo}
        ]
    }
    
    try:
        # Passiamo l'URL esatto assicurandoci che non ci siano spazi
        response = requests.post(url.strip(), headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.MissingSchema:
        return {"error_interno": "URL malformato. Assicurati che inizi con https://"}
    except Exception as e:
        return {"error_interno": str(e)}

# Interfaccia Streamlit
domanda = st.text_input("Chiedi un consiglio:")

if st.button("Chiedi al Coach 🚀"):
    if not API_KEY:
        st.error("Chiave API mancante nei Secrets!")
    elif domanda:
        with st.spinner("Il Coach sta elaborando..."):
            res = chiedi_a_groq(domanda)
            
            if 'choices' in res:
                risposta = res['choices'][0]['message']['content']
                st.success("Consiglio:")
                st.markdown(risposta)
            else:
                errore = res.get('error_interno') or res.get('error', {}).get('message', 'Errore ignoto')
                st.error(f"Errore: {errore}")
    else:
        st.warning("Inserisci una domanda!")
