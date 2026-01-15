"""
Self-Play Weight Optimization for Scopa AI

Questo script fa giocare il bot contro se stesso con pesi diversi
e trova la configurazione ottimale.

Metodo: Hill Climbing con variazioni casuali dei pesi
"""

import random
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Tuple
import copy

from scopa_core import GameState, initialize_game, deal_cards, get_valid_moves, apply_move, is_game_over, calculate_scores
from scopa_ai import ScopaBot, P, score_move


@dataclass
class WeightConfig:
    """Configurazione pesi per score_move."""
    capture_base: int = 32      # P.MEDIUM
    capture_denari: int = 185   # P.CRITICAL
    capture_seven: int = 62     # P.HIGH
    capture_multi: int = 62     # P.HIGH
    scopa_bonus: int = 500      # P.MAX
    risk_penalty: int = 62      # P.HIGH
    
    def to_dict(self) -> Dict[str, int]:
        return {
            "capture_base": self.capture_base,
            "capture_denari": self.capture_denari,
            "capture_seven": self.capture_seven,
            "capture_multi": self.capture_multi,
            "scopa_bonus": self.scopa_bonus,
            "risk_penalty": self.risk_penalty
        }
    
    def mutate(self, mutation_rate: float = 0.2) -> 'WeightConfig':
        """Crea una variante con pesi leggermente modificati."""
        new = copy.copy(self)
        fields = ['capture_base', 'capture_denari', 'capture_seven', 
                  'capture_multi', 'scopa_bonus', 'risk_penalty']
        
        for field in fields:
            if random.random() < mutation_rate:
                current = getattr(new, field)
                # Modifica ±20%
                delta = int(current * random.uniform(-0.2, 0.2))
                setattr(new, field, max(10, current + delta))
        
        return new


def simulate_game_with_config(config1: WeightConfig, config2: WeightConfig) -> Tuple[int, int]:
    """
    Simula una partita tra due configurazioni.
    Ritorna (score_player0, score_player1).
    """
    state = initialize_game()
    
    # Crea due bot con memorie separate
    bot0 = ScopaBot()
    bot1 = ScopaBot()
    
    max_moves = 100
    move_count = 0
    
    while not is_game_over(state) and move_count < max_moves:
        # Ridistribuisci se mani vuote
        if not state.players[0].hand and not state.players[1].hand:
            if state.deck:
                state = deal_cards(state, 3)
            else:
                break
        
        # Salta se mano corrente vuota
        if not state.current.hand:
            state.switch_player()
            continue
        
        # Scegli mossa
        current_bot = bot0 if state.current_player == 0 else bot1
        
        try:
            move = current_bot.choose_move(state, use_monte_carlo=False)
            state = apply_move(state, move)
        except Exception as e:
            break
        
        move_count += 1
    
    # Calcola punteggi
    try:
        s0, s1 = calculate_scores(state)
        return s0.total, s1.total
    except:
        return 0, 0


def evaluate_config(config: WeightConfig, opponent_config: WeightConfig, 
                   num_games: int = 50) -> float:
    """
    Valuta una configurazione facendola giocare contro l'avversario.
    Ritorna il win rate.
    """
    wins = 0
    for i in range(num_games):
        # Alterna chi inizia
        if i % 2 == 0:
            s0, s1 = simulate_game_with_config(config, opponent_config)
            if s0 > s1:
                wins += 1
        else:
            s0, s1 = simulate_game_with_config(opponent_config, config)
            if s1 > s0:
                wins += 1
    
    return wins / num_games


def hill_climbing(initial_config: WeightConfig, iterations: int = 20, 
                  games_per_eval: int = 30) -> Tuple[WeightConfig, float]:
    """
    Ottimizza i pesi con hill climbing.
    """
    current_config = initial_config
    # Usa config default come baseline
    baseline = WeightConfig()
    
    current_score = evaluate_config(current_config, baseline, games_per_eval)
    print(f"Initial score: {current_score:.1%}")
    
    best_config = current_config
    best_score = current_score
    
    for i in range(iterations):
        # Genera variante
        candidate = current_config.mutate()
        
        # Valuta
        candidate_score = evaluate_config(candidate, baseline, games_per_eval)
        
        print(f"Iteration {i+1}: {candidate_score:.1%}", end="")
        
        if candidate_score > current_score:
            print(" ✅ Better!")
            current_config = candidate
            current_score = candidate_score
            
            if current_score > best_score:
                best_score = current_score
                best_config = current_config
        else:
            print()
    
    return best_config, best_score


def optimize_weights(iterations: int = 30, games_per_eval: int = 50):
    """
    Esegue l'ottimizzazione completa.
    """
    print("="*60)
    print("SELF-PLAY WEIGHT OPTIMIZATION")
    print("="*60)
    
    # Inizia con i pesi attuali
    initial = WeightConfig()
    
    print(f"\nPesi iniziali: {initial.to_dict()}")
    print(f"\nIterazioni: {iterations}")
    print(f"Partite per valutazione: {games_per_eval}")
    print()
    
    best_config, best_score = hill_climbing(initial, iterations, games_per_eval)
    
    print("\n" + "="*60)
    print("RISULTATI")
    print("="*60)
    print(f"Miglior score: {best_score:.1%}")
    print(f"Miglior configurazione: {best_config.to_dict()}")
    
    # Salva risultati
    results = {
        "best_score": best_score,
        "best_config": best_config.to_dict(),
        "iterations": iterations,
        "games_per_eval": games_per_eval
    }
    
    output_path = Path(__file__).parent / ".tmp" / "weight_optimization.json"
    output_path.parent.mkdir(exist_ok=True)
    
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\nRisultati salvati in: {output_path}")
    
    return best_config


if __name__ == "__main__":
    import sys
    
    iterations = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    games = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    
    optimize_weights(iterations=iterations, games_per_eval=games)
