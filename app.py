import streamlit as st
import google.generativeai as genai
from PIL import Image

# Configurazione Pagina
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥")

# Configurazione API
if "GOOGLE_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
else:
    st.error("Configura la chiave API nei Secrets!")
    st.stop()

# Usiamo il nome del modello senza 'models/' davanti, 
# la libreria lo aggiungerà correttamente da sola.
model = genai.GenerativeModel('gemini-1.5-flash')

st.title("🏥 TurnoSano AI")

# Sezione Domanda
st.subheader("Chiedi al Coach")
domanda = st.text_input("Come posso aiutarti oggi?")

# Sezione Foto
st.subheader("Analizza Turno")
foto = st.file_uploader("Carica la foto del tabellone", type=["jpg", "jpeg", "png"])

if st.button("Invia richiesta 🚀"):
    if domanda or foto:
        with st.spinner("Il Coach sta elaborando i consigli..."):
            try:
                # Creiamo il contenuto da inviare
                richiesta = ["Sei TurnoSano AI, coach per infermieri. Rispondi in modo pratico."]
                
                if domanda:
                    richiesta.append(domanda)
                if foto:
                    img = Image.open(foto)
                    richiesta.append(img)
                
                # Generazione
                risposta = model.generate_content(richiesta)
                
                st.success("Ecco i tuoi consigli:")
                st.markdown(risposta.text)
                
            except Exception as e:
                # Se l'errore persiste, mostriamo un messaggio più pulito
                st.error(f"Nota: Il servizio Google è momentaneamente occupato o il modello non è raggiungibile. Dettaglio: {e}")
    else:
        st.warning("Per favore, scrivi qualcosa o carica una foto!")
