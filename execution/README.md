# Execution Scripts

Questa cartella contiene gli script Python deterministici per l'esecuzione.

## Principi

1. **Deterministici**: Stesso input = stesso output, sempre
2. **Testabili**: Ogni script deve poter essere testato in isolamento
3. **Ben commentati**: Codice chiaro e documentato
4. **Veloci**: Ottimizzati per performance

## Come usare

Gli script vengono chiamati dall'agente di orchestrazione secondo le direttive in `directives/`.

## Dipendenze

Le dipendenze Python vanno listate in `requirements.txt` nella root del progetto.

## Variabili d'ambiente

Tutte le credenziali e token API vanno nel file `.env` nella root del progetto.

```python
# Esempio di come caricare le variabili d'ambiente
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("API_KEY")
```
