import streamlit as st
import requests

st.set_page_config(page_title="TurnoSano AI", page_icon="🏥")
st.title("🏥 TurnoSano AI")
st.write("Coach per Infermieri (Powered by Llama 3)")

# Recupero Chiave Groq
API_KEY = st.secrets.get("GROQ_API_KEY")

def chiedi_a_groq(testo):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama3-8b-8192",
        "messages": [
            {"role": "system", "content": "Sei TurnoSano AI, un coach esperto per infermieri turnisti. Rispondi in italiano con consigli pratici su sonno, alimentazione e gestione dei turni."},
            {"role": "user", "content": testo}
        ]
    }
    response = requests.post(url, headers=headers, json=payload)
    return response.json()

domanda = st.text_input("Chiedi un consiglio (es: come gestire il turno di notte?):")

if st.button("Chiedi al Coach 🚀"):
    if domanda and API_KEY:
        with st.spinner("Il Coach sta elaborando..."):
            try:
                res = chiedi_a_groq(domanda)
                if 'choices' in res:
                    risposta = res['choices'][0]['message']['content']
                    st.success("Consiglio del Coach:")
                    st.markdown(risposta)
                else:
                    st.error(f"Errore: {res}")
            except Exception as e:
                st.error(f"Errore tecnico: {e}")
    else:
        st.warning("Inserisci una domanda o controlla la chiave API!")
