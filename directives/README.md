# Direttive

Questa cartella contiene le SOP (Standard Operating Procedures) scritte in Markdown.

## Come funzionano

Le direttive definiscono:
- **Obiettivi**: cosa deve essere fatto
- **Input**: quali dati o informazioni sono necessari
- **Tool/Script**: quali script in `execution/` usare
- **Output**: cosa produrre come risultato
- **Casi limite**: come gestire situazioni anomale

## Formato consigliato

```markdown
# Nome Direttiva

## Obiettivo
Descrizione chiara di cosa deve essere fatto.

## Input
- Input 1
- Input 2

## Script da usare
- `execution/nome_script.py`

## Output atteso
Descrizione dell'output.

## Casi limite
- Caso 1: come gestirlo
- Caso 2: come gestirlo
```

## Note importanti

Le direttive sono documenti vivi. Aggiornale quando:
- Scopri vincoli API
- Trovi approcci migliori
- Incontri errori comuni
- Cambia il timing delle operazioni
