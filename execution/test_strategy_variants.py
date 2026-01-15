#!/usr/bin/env python3
"""
Test Strategy Variants - Confronto tra due approcci:
- Variante A: Ottimizzazione aggressiva scope
- Variante B: Minimax migliorato con stima mano avversaria

Esegue benchmark su tutti i livelli di avversario.
"""

import sys
import time
from dataclasses import dataclass
from typing import Dict, List, Tuple
import copy

# Import base modules
from scopa_core import (
    GameState, Move, Card, Suit, PlayerState,
    get_valid_moves, apply_move, create_deck, deal_cards,
    calculate_scores, is_game_over, PRIMIERA_VALUES
)
from scopa_ai import (
    ScopaBot, CardMemory, P, score_move, get_advantage, 
    get_play_style, get_game_phase, table_after_move,
    minimax, should_use_minimax, clone_game_state, monte_carlo_evaluate
)
from scopa_opponents import create_opponent


# ========================== VARIANTE A: AGGRESSIVE SCOPE ==========================

class AggressiveScopeBot(ScopaBot):
    """
    Variante A: Aumenta il peso delle scope e riduce la difesa.
    Filosofia: Meglio rischiare e fare scope che giocare troppo difensivo.
    """
    
    def __init__(self, name="AggressiveBot"):
        super().__init__(name)
        # Modificatori di punteggio
        self.scopa_bonus_multiplier = 1.5  # +50% bonus per scope
        self.risk_penalty_reduction = 0.6  # -40% penalità rischio
        
    def _evaluate_moves(self, state, moves, weights, use_monte_carlo, mc_simulations, match_score=(0,0), dealer="unknown"):
        """Override con scoring più aggressivo."""
        
        adv = get_advantage(state, state.current_player)
        style = self.memory.get_opponent_style()
        phase = get_game_phase(state)
        
        scored = []
        for move in moves:
            # Usa score_move base
            base_score, reasons = score_move(state, move, self.memory, adv, style, phase, match_score, dealer)
            
            # MODIFICA A1: Boost per scope
            if move.is_scopa:
                bonus = int(P.MAX * (self.scopa_bonus_multiplier - 1.0))
                base_score += bonus
                reasons.append(f"SCOPA BOOST +{bonus}")
            
            # MODIFICA A2: Boost per catture che svuotano tavolo quasi del tutto
            if move.is_capture:
                new_table = table_after_move(state, move)
                if len(new_table) == 1:
                    # Lasciamo 1 carta - prossima mossa potrebbe essere scopa!
                    base_score += P.MEDIUM
                    reasons.append("near-scopa setup")
            
            # MODIFICA A3: Riduci penalità rischio scopa avversario
            # Già calcolato in score_move, ma possiamo compensare parzialmente
            new_table = table_after_move(state, move)
            if new_table and not move.is_capture:
                # Se stiamo scartando, riduci la paura
                compensation = int(P.MEDIUM * (1.0 - self.risk_penalty_reduction))
                base_score += compensation
            
            scored.append((base_score, move, reasons))
        
        scored.sort(key=lambda x: x[0], reverse=True)
        
        # Monte Carlo su top candidates
        if use_monte_carlo and len(scored) > 1:
            best_score = scored[0][0]
            candidates = [x for x in scored if x[0] >= best_score - P.HIGH]  # Più tollerante
            candidates = candidates[:min(4, len(candidates))]  # Più candidati
            
            mc_results = []
            for score, move, reasons in candidates:
                win_rate = monte_carlo_evaluate(state, move, state.current_player, simulations=mc_simulations)
                mc_results.append((win_rate, move))
            
            mc_results.sort(key=lambda x: x[0], reverse=True)
            return mc_results[0][1]
        
        return scored[0][1]


# ========================== VARIANTE B: SMART MINIMAX ==========================

class SmartMinimaxBot(ScopaBot):
    """
    Variante B: Minimax migliorato con stima probabilistica della mano avversaria.
    Invece di assegnare TUTTE le carte sconosciute all'avversario,
    stima quante ne ha in base al contesto di gioco.
    """
    
    def __init__(self, name="SmartMinimaxBot"):
        super().__init__(name)
        
    def _evaluate_moves(self, state, moves, weights, use_monte_carlo, mc_simulations, match_score=(0,0), dealer="unknown"):
        """Override con minimax più intelligente."""
        
        # === SMART MINIMAX ===
        # Attiva minimax anche con più carte sconosciute, ma stima la mano avversaria
        if should_use_minimax(state):
            if not state.players[1].hand:
                all_cards = set(create_deck())
                unknown_cards = list(all_cards - self.memory.seen)
                my_hand_size = len(state.players[state.current_player].hand)
                
                # MODIFICA B1: Stima intelligente della mano avversaria
                # In Scopa, dopo una distribuzione entrambi hanno 3 carte
                # Man mano che giochiamo, le carte diminuiscono
                estimated_opp_hand_size = min(my_hand_size, len(unknown_cards))
                
                if estimated_opp_hand_size > 0 and len(unknown_cards) <= 6:
                    # MODIFICA B2: Assegna solo le carte più probabili
                    # Priorità: 7, poi 6, poi denari, poi altri
                    def card_priority(c):
                        prio = 0
                        if c.value == 7: prio += 100
                        if c.value == 6: prio += 50
                        if c.is_denaro: prio += 30
                        if c.is_settebello: prio += 200
                        return prio
                    
                    unknown_cards.sort(key=card_priority, reverse=True)
                    inferred_opp_hand = unknown_cards[:estimated_opp_hand_size]
                    
                    state.players[1].hand = inferred_opp_hand
                    state.deck = []
                    
                    cards_left = sum(len(p.hand) for p in state.players)
                    score, best_move = minimax(state, depth=cards_left, my_player=state.current_player, maximizing=True)
                    
                    if best_move:
                        return best_move
        
        # Fallback a logica standard
        adv = get_advantage(state, state.current_player)
        style = self.memory.get_opponent_style()
        phase = get_game_phase(state)
        
        scored = []
        for move in moves:
            score, reasons = score_move(state, move, self.memory, adv, style, phase, match_score, dealer)
            scored.append((score, move, reasons))
        
        scored.sort(key=lambda x: x[0], reverse=True)
        
        if use_monte_carlo and len(scored) > 1:
            best_score = scored[0][0]
            candidates = [x for x in scored if x[0] >= best_score - P.MEDIUM]
            candidates = candidates[:min(3, len(candidates))]
            
            mc_results = []
            for score, move, reasons in candidates:
                win_rate = monte_carlo_evaluate(state, move, state.current_player, simulations=mc_simulations)
                mc_results.append((win_rate, move))
            
            mc_results.sort(key=lambda x: x[0], reverse=True)
            return mc_results[0][1]
        
        return scored[0][1]


# ========================== BENCHMARK ==========================

def simulate_game_with_bot(bot_class, opponent, use_mc=True, mc_sims=50):
    """Simula una partita con un bot specifico."""
    from scopa_core import initialize_game
    
    bot = bot_class()
    state = initialize_game()
    
    # Bot gioca come player 0
    bot_player = 0
    
    max_turns = 100
    turns = 0
    
    while not is_game_over(state) and turns < max_turns:
        # Distribuisci se mani vuote
        if not state.players[0].hand and not state.players[1].hand:
            if state.deck:
                state = deal_cards(state, 3)
            else:
                break
        
        if not state.current.hand:
            break
        
        moves = get_valid_moves(state)
        if not moves:
            break
        
        if state.current_player == bot_player:
            # Turno del bot
            move = bot.choose_move(state, use_monte_carlo=use_mc, mc_simulations=mc_sims)
        else:
            # Turno avversario
            move = opponent.choose_move(state)
        
        if move:
            state = apply_move(state, move)
        
        turns += 1
    
    # Assegna carte rimanenti all'ultimo catturatore
    if state.table and state.last_capturer is not None:
        state.players[state.last_capturer].captured.extend(state.table)
        state.table.clear()
    
    scores = calculate_scores(state)
    bot_score = scores[bot_player].total
    opp_score = scores[1 - bot_player].total
    
    return bot_score, opp_score, scores[bot_player].scope, scores[1 - bot_player].scope


def run_comparison(num_games=50, use_mc=True, mc_sims=50):
    """Esegue confronto completo tra le varianti."""
    
    opponents = ['beginner', 'medium', 'pro']
    bot_classes = {
        'Current': ScopaBot,
        'AggressiveScope': AggressiveScopeBot,
        'SmartMinimax': SmartMinimaxBot
    }
    
    results = {}
    
    for opp_level in opponents:
        print(f"\n{'='*60}")
        print(f"Testing vs {opp_level.upper()} ({num_games} games each)")
        print('='*60)
        
        opponent = create_opponent(opp_level)
        results[opp_level] = {}
        
        for bot_name, bot_class in bot_classes.items():
            wins = 0
            draws = 0
            total_scope_bot = 0
            total_scope_opp = 0
            
            print(f"\n  {bot_name}:", end=" ", flush=True)
            
            for i in range(num_games):
                if (i + 1) % 10 == 0:
                    print(f"{i+1}", end=" ", flush=True)
                
                bot_score, opp_score, scope_bot, scope_opp = simulate_game_with_bot(
                    bot_class, opponent, use_mc, mc_sims
                )
                
                if bot_score > opp_score:
                    wins += 1
                elif bot_score == opp_score:
                    draws += 1
                
                total_scope_bot += scope_bot
                total_scope_opp += scope_opp
            
            win_rate = wins / num_games * 100
            avg_scope_bot = total_scope_bot / num_games
            avg_scope_opp = total_scope_opp / num_games
            
            results[opp_level][bot_name] = {
                'win_rate': win_rate,
                'wins': wins,
                'draws': draws,
                'losses': num_games - wins - draws,
                'avg_scope_bot': avg_scope_bot,
                'avg_scope_opp': avg_scope_opp
            }
            
            print(f"-> {win_rate:.1f}% wins, scope: {avg_scope_bot:.2f} vs {avg_scope_opp:.2f}")
    
    # Riepilogo finale
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"{'Bot':<20} {'vs Amateur':<15} {'vs Medium':<15} {'vs Pro':<15} {'AVG':<10}")
    print("-"*70)
    
    for bot_name in bot_classes.keys():
        rates = [results[opp][bot_name]['win_rate'] for opp in opponents]
        avg_rate = sum(rates) / len(rates)
        print(f"{bot_name:<20} {rates[0]:>6.1f}%        {rates[1]:>6.1f}%        {rates[2]:>6.1f}%        {avg_rate:>6.1f}%")
    
    print("="*70)
    
    return results


if __name__ == "__main__":
    print("="*70)
    print("STRATEGY VARIANT COMPARISON")
    print("Testing 3 bot variants against 3 opponent levels")
    print("="*70)
    
    # Default: 30 games per matchup, MC enabled with 50 sims
    num_games = 30
    if len(sys.argv) > 1:
        num_games = int(sys.argv[1])
    
    start_time = time.time()
    results = run_comparison(num_games=num_games, use_mc=True, mc_sims=50)
    elapsed = time.time() - start_time
    
    print(f"\nTotal time: {elapsed:.1f}s ({elapsed/60:.1f} min)")
