import streamlit as st
import requests
from PyPDF2 import PdfReader

# 1. Configurazione Pagina
st.set_page_config(page_title="TurnoSano AI", page_icon="🏥", layout="wide")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "testo_turno" not in st.session_state:
    st.session_state.testo_turno = ""

# --- INTERFACCIA TITOLO ---
st.title("🏥 TurnoSano AI")
st.write("Il tuo Coach per la gestione dei turni (Versione Gennaio 2026)")

# --- SEZIONE: SUGGERIMENTI RAPIDI ---
st.write("### ⚡ Azioni Rapide")
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("🌙 SOS Turno Notte"):
        st.session_state.messages.append({"role": "user", "content": "Dammi una strategia pratica per gestire il turno di notte e il riposo di domani."})
        st.rerun()
with col2:
    if st.button("🥗 Alimentazione"):
        st.session_state.messages.append({"role": "user", "content": "Cosa mi consigli di mangiare durante e dopo il turno?"})
        st.rerun()
with col3:
    if st.button("🧘 Stress in Reparto"):
        st.session_state.messages.append({"role": "user", "content": "Consigliami un esercizio rapido per scaricare la tensione."})
        st.rerun()

# 2. Sidebar per il PDF
with st.sidebar:
    st.header("📂 Carica Turno")
    file_pdf = st.file_uploader("Trascina qui il tuo PDF", type="pdf")
    if file_pdf:
        try:
            reader = PdfReader(file_pdf)
            testo_estratto = "".join([page.extract_text() or "" for page in reader.pages])
            st.session_state.testo_turno = testo_estratto
            st.success("✅ Turno analizzato!")
        except Exception as e:
            st.error(f"Errore PDF: {e}")
    
    st.write("---")
    if st.button("🗑️ Reset Chat"):
        st.session_state.messages = []
        st.session_state.testo_turno = ""
        st.rerun()

# 3. Funzione API (CORRETTA CON URL COMPLETO)
def chiedi_a_groq(messages):
    api_key = st.secrets.get("GROQ_API_KEY")
    # URL COMPLETO E BLINDATO
    URL_CORRETTO = "api.groq.com"
    
    system_prompt = "Sei TurnoSano AI, un coach esperto per infermieri. Rispondi in italiano con consigli pratici."
    if st.session_state.testo_turno:
        system_prompt += f"\nContesto turno: {st.session_state.testo_turno}"
    
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [{"role": "system", "content": system_prompt}] + messages,
        "temperature": 0.7
    }
    
    try:
        # La richiesta DEVE usare l'URL con https://
        response = requests.post(
            URL_CORRETTO, 
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, 
            json=payload, 
            timeout=25
        )
        response.raise_for_status()
        data = response.json()
        # Accesso corretto al contenuto del messaggio
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"⚠️ Errore Tecnico: {str(e)}"

# 4. Visualizzazione Cronologia Chat
st.write("---")
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 5. Chat Input
if prompt := st.chat_input("Scrivi qui la tua domanda..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    with st.chat_message("assistant", avatar="🏥"):
        with st.spinner("Il Coach sta analizzando..."):
            risposta = chiedi_a_groq(st.session_state.messages)
            st.markdown(risposta)
            st.session_state.messages.append({"role": "assistant", "content": risposta})
            st.rerun()
