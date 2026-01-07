import streamlit as st
import google.generativeai as genai
from PIL import Image

# 1. Configurazione Pagina
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥")
st.title("🏥 TurnoSano AI: Coach per Infermieri")

# 2. Configurazione Sicura (usa i Secrets che hai impostato)
# Using the CHIAVE_API available in the kernel state
genai.configure(api_key=CHIAVE_API)

# Usiamo l'ultimo modello disponibile
model = genai.GenerativeModel('gemini-1.5-flash')

st.write("Ciao! Sono il tuo coach. Puoi caricarmi una foto dei turni o semplicemente farmi una domanda.")

# --- SEZIONE INPUT ---
col1, col2 = st.columns(2)

with col1:
    file_caricato = st.file_uploader("📸 Foto Turni (opzionale)", type=["jpg", "jpeg", "png"])

with col2:
    domanda_testo = st.text_input("💬 Oppure scrivi qui la tua domanda:")

# --- LOGICA DI RISPOSTA ---
if st.button("Chiedi al Coach"):
    # Controllo se l'utente ha inserito almeno qualcosa
    if file_caricato or domanda_testo:
        with st.spinner('Il Coach sta riflettendo...'):
            try:
                contenuto = []

                # Definiamo le istruzioni di base
                istruzioni = (
                    "Sei TurnoSano AI, esperto in cronobiologia per infermieri. "
                    "Analizza l'input e dai consigli pratici su sonno, dieta ed energia. "
                    "Sii motivante ma scientifico. Chiudi ricordando che non sei un medico."
                )
                contenuto.append(istruzioni)

                # Se c'è una domanda scritta, la aggiungiamo
                if domanda_testo:
                    contenuto.append(f"Domanda dell'infermiere: {domanda_testo}")

                # Se c'è una foto, la aggiungiamo
                if file_caricato:
                    img = Image.open(file_caricato)
                    contenuto.append(img)

                # Generazione risposta
                risposta = model.generate_content(contenuto)

                st.success("Consiglio del Coach:")
                st.markdown(risposta.text)

            except Exception as e:
                st.error(f"Si è verificato un errore: {e}")
    else:
        st.warning("Per favore, scrivi una domanda o carica una foto!")
