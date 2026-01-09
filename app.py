# --- AREA RISERVATA (LOGGATO) ---
else:
    # 1. Recupero dati per la Dashboard
    # In un'app avanzata, questi dati verrebbero calcolati dal database Profiles
    nome_utente = st.session_state['name']
    
    st.title(f"🏥 Dashboard di {nome_utente}")
    st.write(f"Benvenuto/a! Ecco il riepilogo del tuo benessere lavorativo oggi, {st.date_input('Oggi è:', help='Data attuale').strftime('%d/%m/%Y')}")

    # 2. Visualizzazione Metriche (KPI)
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(label="Stato Recupero", value="75%", delta="5%", help="Basato sulle ore di sonno dichiarate nell'ultimo turno")
    
    with col2:
        # Conteggio dei messaggi scambiati col Coach
        num_consigli = len([m for m in st.session_state.get("messages", []) if m["role"] == "assistant"])
        st.metric(label="Consigli Ricevuti", value=num_consigli, delta=None)
    
    with col3:
        # Stato del Turno (dinamico se il PDF è caricato)
        stato_turno = "Analizzato ✅" if st.session_state.get("testo_turno") else "Da caricare ❌"
        st.info(f"**Turno attuale:** {stato_turno}")

    st.divider()

    # 3. Sezione Suggerimento Proattivo del Coach
    if st.session_state.get("testo_turno"):
        st.subheader("💡 Il consiglio rapido per il tuo prossimo turno")
        st.warning("Secondo il PDF caricato, stasera hai una notte. Ricordati di idratarti bene e fare un riposino di 90 minuti prima delle 22:00.")
    else:
        st.info("Carica il tuo turno PDF nella barra laterale per ricevere analisi proattive.")

    # --- CHAT CON IL COACH (Sotto la Dashboard) ---
    st.write("---")
    st.subheader("💬 Parla con TurnoSano AI")
    
    # ... qui prosegue il resto del codice della chat con Groq che hai già ...
