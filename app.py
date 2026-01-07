import streamlit as st
import google.generativeai as genai
from PIL import Image

# Configurazione Pagina
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥")

# Funzione per configurare il modello
def setup_model():
    if "GOOGLE_API_KEY" not in st.secrets:
        st.error("⚠️ Chiave API non trovata nei Secrets!")
        return None
    
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    
    # Proviamo a usare il modello flash (molto veloce)
    # Se da errore 404, il sistema proverà la versione alternativa
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        # Test rapido per vedere se il modello risponde
        return model
    except:
        return genai.GenerativeModel('gemini-pro')

model = setup_model()

# --- INTERFACCIA ---
st.title("🏥 TurnoSano AI")
st.subheader("Il Coach per Infermieri")

domanda = st.text_input("Fai una domanda (es. Consigli per il turno di notte):")
foto = st.file_uploader("O carica la foto dei turni:", type=["jpg", "jpeg", "png"])

if st.button("Chiedi al Coach 🚀"):
    if model and (domanda or foto):
        with st.spinner("Analisi in corso..."):
            try:
                contenuto_input = []
                prompt_base = "Sei un coach esperto per infermieri. Rispondi in modo empatico e pratico."
                contenuto_input.append(prompt_base)
                
                if domanda:
                    contenuto_input.append(domanda)
                if foto:
                    img = Image.open(foto)
                    contenuto_input.append(img)
                
                risposta = model.generate_content(contenuto_input)
                st.success("Consiglio del Coach:")
                st.markdown(risposta.text)
                
            except Exception as e:
                st.error(f"Si è verificato un errore: {e}")
    else:
        st.warning("Inserisci una domanda o carica una foto!")
