# 📊 Scopa Bot - Comparazione Storica Completa

## 🏆 MIGLIOR RISULTATO PER LIVELLO

| Livello | Miglior WR | Versione |
|---------|------------|----------|
| Random | 77.3% | v8.6 |
| Beginner | ~70% | v12.29* |
| Medium | 72.5% | v9.2 |
| Strong | 70.5% | v9.2 |
| **Pro** | **64.5%** | **v9.2** |
| human_casual | **78.5%** | **v9.2** 🏆 |
| human_amateur | 72.0% | v9.3 |
| human_expert | **74.7%** | **v8.6** 🏆 |
| **human_pro** | **71.0%** | **v9.3** 🏆 |

---

## Evoluzione Storica (400+ games per benchmark)

### vs Pro (AI avversario)

| Versione | WR | Note |
|----------|-----|------|
| v6 | 51.5% | Baseline adaptive |
| v8.2 | ~55% | Minimax 10 carte |
| v8.6 | 64.3% | Primiera protection |
| v9.2 | **64.5%** 🏆 | Deep Monte Carlo |
| v9.3 | 60.0% | Tuning regressione |
| v11.5 | 52.5% | Multi-session fix |
| v12.20 | ~53% | Extension integration |
| v12.21 | 58.0% | 1-ply lookahead |
| v12.29 | 59.0% | Aggressive penalties |

### vs HumanPro (umano esperto simulato)

| Versione | WR | Note |
|----------|-----|------|
| v7.6 | 46.5% | Baseline |
| v7.9 | 61.6% | +15.1% |
| v8.1 | 64.0% | +17.5% |
| v8.2 | 68.0% | Minimax |
| v8.6 | 64.3% | Primiera |
| v9.2 | 67.5% | Monte Carlo 50 sim |
| **v9.3** | **71.0%** 🏆 | **Record storico!** |

### vs human_expert

| Versione | WR | Note |
|----------|-----|------|
| v8.5 | 69.5% | Baseline |
| **v8.6** | **74.7%** 🏆 | +5.2% |
| v9.3 | 72.0% | |
| v11.5 | 66.0% | |
| v12.29 | 67.3% | 1000 games |

---

## v12.29 - Benchmark Attuali (1000 games)

| Livello | WR | Margine |
|---------|-----|---------|
| human_casual | 67.8% | +1.74 |
| human_amateur | 66.5% | +1.57 |
| human_expert | 67.3% | +1.56 |
| human_pro | 56.2% | +0.80 |

---

## 🔑 Tecnologie Chiave per Versione

| Versione | Innovazione | Impatto |
|----------|-------------|---------|
| v6 | Adaptive Play | +15% |
| v8.2 | Minimax Endgame | +5% |
| v8.6 | Primiera Protection | +5% |
| v9.2 | Monte Carlo 50 sim | +3% |
| v9.3 | ScopaBot Class refactor | +3.5% |
| v12.21 | 1-ply Lookahead | +5% |
| v12.29 | Aggressive Penalties | +6% |

---

## Note

1. **v9.3** detiene il record storico vs HumanPro (71.0%)
2. **v9.2** era ottimale vs Pro AI (64.5%)  
3. **v12.29** è ottimizzato per live play (extension)
4. Monte Carlo ha causato varianza nei risultati
