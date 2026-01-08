import streamlit as st
import requests

# Configurazione Pagina
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥")
st.title("🏥 TurnoSano AI")
st.write("Coach per Infermieri (Aggiornato 2026)")

# Recupero Chiave Groq dai Secrets di Streamlit
API_KEY = st.secrets.get("GROQ_API_KEY")

def chiedi_a_groq(testo):
    url = "api.groq.com"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        # Modello aggiornato: llama3-8b-8192 è deprecato
        "model": "llama-3.1-8b-instant", 
        "messages": [
            {
                "role": "system", 
                "content": "Sei TurnoSano AI, un coach esperto per infermieri turnisti. Rispondi in italiano con consigli pratici, empatici e scientifici su sonno, alimentazione e gestione dello stress da turnazione."
            },
            {"role": "user", "content": testo}
        ],
        "temperature": 0.7
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status() # Controlla se ci sono errori HTTP
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error_interno": str(e)}

# Interfaccia Utente
domanda = st.text_input("Chiedi un consiglio (es: come gestire il riposo post-notte?):")

if st.button("Chiedi al Coach 🚀"):
    if not API_KEY:
        st.error("Chiave API mancante! Configura GROQ_API_KEY nei Secrets di Streamlit.")
    elif domanda:
        with st.spinner("Il Coach sta analizzando il tuo turno..."):
            res = chiedi_a_groq(domanda)
            
            if 'choices' in res:
                risposta = res['choices'][0]['message']['content']
                st.success("Consiglio del Coach:")
                st.markdown(risposta)
            elif "error_interno" in res:
                st.error(f"Errore di connessione: {res['error_interno']}")
            else:
                # Gestione errore specifico di Groq (es. modello non trovato o limite raggiunto)
                errore_messaggio = res.get('error', {}).get('message', 'Errore sconosciuto')
                st.error(f"Errore API: {errore_messaggio}")
    else:
        st.warning("Per favore, inserisci una domanda!")

# Footer informativo
st.divider()
st.caption("Nota: I consigli di TurnoSano AI sono a scopo informativo e non sostituiscono il parere di un medico.")
