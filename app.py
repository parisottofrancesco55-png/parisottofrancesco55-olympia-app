import streamlit as st
import requests
from PyPDF2 import PdfReader

# 1. Configurazione Visiva Moderna
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥", layout="wide")

# CSS Personalizzato per migliorare l'estetica
st.markdown("""
    <style>
    .stChatMessage { border-radius: 15px; margin-bottom: 10px; }
    .stButton>button { width: 100%; border-radius: 20px; background-color: #007bff; color: white; }
    </style>
    """, unsafe_allow_stdio=True)

st.title("🏥 TurnoSano AI")
st.caption("Il tuo assistente intelligente per la gestione dei turni infermieristici")

# 2. Inizializzazione Session State (Memoria della Chat)
if "messages" not in st.session_state:
    st.session_state.messages = []
if "testo_turno" not in st.session_state:
    st.session_state.testo_turno = ""

# 3. Sidebar Organizzata
with st.sidebar:
    st.image("img.icons8.com", width=80)
    st.header("Centro Comandi")
    
    file_pdf = st.file_uploader("📂 Carica il tuo turno (PDF)", type="pdf")
    if file_pdf:
        reader = PdfReader(file_pdf)
        testo = ""
        for page in reader.pages:
            testo += page.extract_text() + "\n"
        st.session_state.testo_turno = testo
        st.success("✅ Turno caricato!")
    
    if st.button("🗑️ Cancella Cronologia"):
        st.session_state.messages = []
        st.rerun()

# 4. Funzione di Chiamata API (Modello 2026)
def chiedi_a_groq(messages):
    API_KEY = st.secrets.get("GROQ_API_KEY")
    URL = "api.groq.com"
    
    # Prepariamo il contesto di sistema
    system_prompt = "Sei TurnoSano AI, un coach esperto per infermieri. Sii empatico e pratico."
    if st.session_state.testo_turno:
        system_prompt += f"\nContesto Turno Utente: {st.session_state.testo_turno}"
    
    full_messages = [{"role": "system", "content": system_prompt}] + messages

    try:
        res = requests.post(
            URL,
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={"model": "llama-3.1-8b-instant", "messages": full_messages, "temperature": 0.7},
            timeout=30
        )
        return res.json()['choices'][0]['message']['content']
    except Exception as e:
        return f"⚠️ Errore: {str(e)}"

# 5. Visualizzazione Cronologia Chat
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 6. Chat Input Interattivo
if prompt := st.chat_input("Come posso aiutarti oggi?"):
    # Mostra messaggio utente
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Genera risposta del Coach
    with st.chat_message("assistant", avatar="🏥"):
        with st.spinner("Il Coach sta riflettendo..."):
            risposta = chiedi_a_groq(st.session_state.messages)
            st.markdown(risposta)
            st.session_state.messages.append({"role": "assistant", "content": risposta})

# 7. Suggerimenti Rapidi (Bottoni Interattivi)
if not st.session_state.messages:
    st.write("---")
    st.subheader("Suggerimenti rapidi:")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🌙 Come gestire il turno di notte?"):
            st.info("Scrivi la domanda nel box sotto per ricevere il consiglio!")
    with col2:
        if st.button("🥗 Cosa mangiare post-smonto?"):
            st.info("Chiedimi pure consigli alimentari specifici!")
