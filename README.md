# Arena Azionaria AI

Sei AI hanno investito 1.000 € virtuali il 18 novembre 2026. Ogni giorno di borsa un job gratuito di GitHub Actions scarica i prezzi di chiusura, ricalcola le statistiche e aggiorna la pagina web.

## Setup (circa 10 minuti)

1. **Crea il repository.** Su github.com premi New repository, scegli un nome (per esempio `arena-ai`) e lascialo **pubblico**: GitHub Pages gratuito funziona solo con i repository pubblici. Non c'è nulla di riservato qui dentro.
2. **Carica i file.** Estrai lo zip, poi nella pagina del repository premi Add file, Upload files e trascina tutto il contenuto della cartella, comprese `.github`, `config`, `docs` e `scripts`. Se il browser non mostra la cartella nascosta `.github`, caricala col comando `git` oppure da GitHub Desktop.
3. **Permessi di scrittura.** Settings, Actions, General, Workflow permissions: scegli *Read and write permissions* e salva. Serve perché il job possa salvare i dati nel repository.
4. **Attiva la pagina.** Settings, Pages: Source *Deploy from a branch*, branch `main`, cartella `/docs`, poi Save. L'indirizzo sarà `https://TUO-UTENTE.github.io/NOME-REPO/`.
5. **Primo aggiornamento.** Scheda Actions, workflow *Aggiorna prezzi e statistiche*, Run workflow. Dopo un minuto circa la pagina mostra i dati veri a partire dal 18 novembre.

Da quel momento il job parte da solo ogni giorno feriale alle 22:00 UTC (23:00 in Italia d'inverno, 00:00 d'estate), dopo la chiusura di Milano e di Wall Street.

## Come funziona

- `config/allocations.json` contiene gli ordini di ogni AI: ticker e importo in euro. Non cambiano dopo la partenza.
- `scripts/update.py` scarica i prezzi con `yfinance`, simula il buy-and-hold e scrive `docs/data/state.json`.
- `docs/index.html` legge `state.json` e mostra classifica, grafico e dettaglio per AI.

Regole del calcolo:
- Ogni ordine entra alla chiusura del 18 novembre, uguale per tutte le AI. Se un titolo non ha prezzo quel giorno, entra alla prima chiusura disponibile e compare un avviso.
- Un ticker senza prezzi resta in liquidità e genera un avviso in cima alla pagina.
- Prezzi *adjusted*: il rendimento include i dividendi reinvestiti, così ETF ad accumulazione e a distribuzione sono confrontabili.
- I titoli in dollari sono convertiti in euro con il cambio EUR/USD della stessa data. Altre valute non sono gestite.
- Nessuna commissione, nessuna tassa, nessun ribilanciamento.

Statistiche per AI: valore, rendimento, utile o perdita, liquidità, perdita massima dal picco, oscillazione giornaliera (deviazione standard dei rendimenti giornalieri), composizione, miglior e peggior titolo.

## Cose da sapere

- **TECH.MI** (DeepSeek) potrebbe non esistere su Yahoo. In quel caso i 200 € restano in liquidità e la pagina lo segnala. Per correggere, sostituisci il ticker in `config/allocations.json`: il job riparte da solo al salvataggio.
- I prezzi vengono da Yahoo Finance tramite una libreria non ufficiale. Può capitare un giorno senza dati: basta rilanciare il workflow a mano.
- Se il repository resta senza attività per 60 giorni GitHub può sospendere i job programmati. Si riattivano dalla scheda Actions.
- È un gioco con denaro virtuale. Non è consulenza finanziaria.

## Idee per dopo

- Far decidere alle AI i ribilanciamenti ogni giorno o ogni settimana, chiamando le loro API dal job (le chiavi vanno nei *Secrets* del repository).
- Aggiungere un indice di riferimento (per esempio un ETF globale) per confrontare le AI con il mercato.
