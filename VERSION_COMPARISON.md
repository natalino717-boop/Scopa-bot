# 📊 Scopa Bot - Comparazione Versioni

## Evoluzione Win Rate vs Pro (400+ games)

| Versione | Descrizione | WR vs Pro | Margine | Note |
|----------|-------------|-----------|---------|------|
| v12.20 | Initial commit | ~53% | +0.64 | Baseline |
| v12.21 | 1-ply lookahead | 58% | +0.78 | +5% |
| v12.22 | Minimax tiebreaker | 57% | +0.89 | Margine ↑ |
| v12.23 | Server-extension fix | 57% | - | Bug fixes |
| v12.24 | impossible_cards | 57% | +0.78 | Stabilità |
| v12.25-27 | 3 enhancements (reverted) | 54% | +0.50 | ❌ Regressione |
| **v12.29** | **Aggressive lookahead** | **59%** | **+0.92** | 🏆 **BEST** |

---

## 🏆 Risultato Migliore: v12.29

```
Win Rate:      59.0% (400 games)
Margine:       +0.92 punti/game
Scope:         Bot 0.19 vs Opp 0.36
```

## Benchmark Completi v12.29 (1000 games ciascuno)

| Avversario | Win Rate | Margine |
|------------|----------|---------|
| human_casual | 67.8% | +1.74 |
| human_amateur | 66.5% | +1.57 |
| human_expert | 67.3% | +1.56 |
| human_pro | 56.2% | +0.80 |
| **pro** | **59.0%** | **+0.92** |

---

## Ottimizzazioni Chiave v12.29

```python
# Penalità lookahead aggressive
settebello_opponent: 55% × score
scopa_opponent:      45% × score  
base_capture:        28% × score
```

## Commits
```
319041a - v12.29 (BEST: 59% WR)
99ed8d6 - v12.24 (impossible_cards)
8a9c50d - v12.22 (minimax)
5ade4b1 - v12.21 (1-ply)
099289b - v12.20 (initial)
```
