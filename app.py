import streamlit as st
import google.generativeai as genai
from PIL import Image

# 1. Configurazione della Pagina
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥", layout="centered")

# 2. Configurazione Sicura dell'API
if "GOOGLE_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
else:
    st.error("⚠️ Chiave API non trovata nei Secrets di Streamlit!")
    st.stop()

# Inizializzazione del modello Gemini
model = genai.GenerativeModel(model_name='models/gemini-1.5-flash')

# 3. Interfaccia Utente
st.title("🏥 TurnoSano AI")
st.subheader("Il tuo Coach per la gestione dei turni")

# --- NUOVA SEZIONE DOMANDE INIZIALI ---
st.write("---")
st.markdown("### 💬 Chiedi qualcosa al Coach")
domanda_testo = st.text_input("Esempio: 'Cosa posso mangiare prima di una notte?' oppure 'Come dormire dopo lo smonto?'")

st.markdown("### 📸 Oppure analizza il tuo turno")
file_caricato = st.file_uploader("Carica la foto del tabellone turni", type=["jpg", "png", "jpeg"])
st.write("---")

# 4. Logica di Risposta
if st.button("Ottieni Consigli 🚀"):
    # Verifichiamo che l'utente abbia inserito almeno una domanda o una foto
    if domanda_testo or file_caricato:
        with st.spinner("Il Coach sta analizzando..."):
            try:
                # Prepariamo la richiesta per l'IA
                prompt_base = (
                    "Sei TurnoSano AI, un coach esperto per infermieri turnisti. "
                    "Fornisci consigli pratici su sonno, alimentazione e gestione dell'energia. "
                    "Sii empatico e professionale. Chiudi sempre ricordando che non sei un medico."
                )
                
                input_per_ia = [prompt_base]
                
                if domanda_testo:
                    input_per_ia.append(f"Domanda dell'utente: {domanda_testo}")
                
                if file_caricato:
                    immagine = Image.open(file_caricato)
                    input_per_ia.append(immagine)
                    input_per_ia.append("Analizza questa foto dei turni e integra i consigli.")

                # Generazione della risposta
                risposta = model.generate_content(input_per_ia)
                
                # Visualizzazione Risultato
                st.success("✅ Ecco i consigli per te:")
                st.markdown(risposta.text)
                
            except Exception as e:
                st.error(f"Si è verificato un errore: {e}")
    else:
        st.warning("Per favore, scrivi una domanda o carica una foto per iniziare!")

# Piè di pagina
st.caption("Creato per supportare gli eroi in corsia. 💙")
