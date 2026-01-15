"""
Scopa Simulator - Simulatore partite per benchmark

Questo modulo implementa:
- Simulazione partite complete
- Benchmark su N partite
- Statistiche dettagliate (win rate, punti medi, scope medie)
- Modalità interattiva per debug

Uso:
    python scopa_simulator.py --games 1000 --opponent medium
    python scopa_simulator.py --interactive
"""

import argparse
import sys
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
import random
from collections import defaultdict

from scopa_core import (
    GameState, Move, Card, 
    initialize_game, get_valid_moves, apply_move,
    deal_cards, is_game_over, calculate_scores, Score
)
from scopa_ai import choose_best_move, HeuristicWeights, DEFAULT_WEIGHTS, ScopaBot
from scopa_opponents import BaseOpponent, create_opponent
from scopa_game_diary import (
    GameDiary, DiaryEntry, create_game_diary,
    cards_to_str, card_to_str, create_move_dict, create_move_description,
    estimate_current_scores
)


@dataclass
class GameResult:
    """Risultato di una singola partita."""
    bot_score: Score
    opponent_score: Score
    bot_won: bool
    bot_points: int
    opponent_points: int
    
    @property
    def margin(self) -> int:
        """Margine di vittoria (può essere negativo)."""
        return self.bot_points - self.opponent_points


@dataclass
class BenchmarkStats:
    """Statistiche aggregate di un benchmark."""
    games_played: int = 0
    bot_wins: int = 0
    opponent_wins: int = 0
    draws: int = 0
    total_bot_points: int = 0
    total_opponent_points: int = 0
    total_bot_scope: int = 0
    total_opponent_scope: int = 0
    
    # Dettagli punti
    bot_cards_won: int = 0
    bot_denari_won: int = 0
    bot_settebello_won: int = 0
    bot_primiera_won: int = 0
    
    @property
    def win_rate(self) -> float:
        if self.games_played == 0:
            return 0.0
        return self.bot_wins / self.games_played
    
    @property
    def avg_bot_points(self) -> float:
        if self.games_played == 0:
            return 0.0
        return self.total_bot_points / self.games_played
    
    @property
    def avg_opponent_points(self) -> float:
        if self.games_played == 0:
            return 0.0
        return self.total_opponent_points / self.games_played
    
    @property
    def avg_margin(self) -> float:
        return self.avg_bot_points - self.avg_opponent_points
    
    def add_result(self, result: GameResult):
        """Aggiunge un risultato alle statistiche."""
        self.games_played += 1
        self.total_bot_points += result.bot_points
        self.total_opponent_points += result.opponent_points
        self.total_bot_scope += result.bot_score.scope
        self.total_opponent_scope += result.opponent_score.scope
        
        if result.bot_won:
            self.bot_wins += 1
        elif result.opponent_points > result.bot_points:
            self.opponent_wins += 1
        else:
            self.draws += 1
        
        # Dettagli
        self.bot_cards_won += result.bot_score.cards
        self.bot_denari_won += result.bot_score.denari
        self.bot_settebello_won += result.bot_score.settebello
        self.bot_primiera_won += result.bot_score.primiera
    
    def __str__(self) -> str:
        lines = [
            f"{'='*50}",
            f"BENCHMARK RESULTS ({self.games_played} games)",
            f"{'='*50}",
            f"Win Rate:      {self.win_rate:.1%}",
            f"Wins/Losses:   {self.bot_wins}/{self.opponent_wins} (draws: {self.draws})",
            f"Avg Points:    Bot {self.avg_bot_points:.2f} vs Opp {self.avg_opponent_points:.2f}",
            f"Avg Margin:    {self.avg_margin:+.2f}",
            f"",
            f"Point Breakdown (bot win rate):",
            f"  Cards:      {self.bot_cards_won}/{self.games_played} ({self.bot_cards_won/self.games_played:.1%})",
            f"  Denari:     {self.bot_denari_won}/{self.games_played} ({self.bot_denari_won/self.games_played:.1%})",
            f"  Settebello: {self.bot_settebello_won}/{self.games_played} ({self.bot_settebello_won/self.games_played:.1%})",
            f"  Primiera:   {self.bot_primiera_won}/{self.games_played} ({self.bot_primiera_won/self.games_played:.1%})",
            f"  Avg Scope:  Bot {self.total_bot_scope/self.games_played:.2f} vs Opp {self.total_opponent_scope/self.games_played:.2f}",
            f"{'='*50}",
        ]
        return "\n".join(lines)


def simulate_game(
    opponent: BaseOpponent,
    bot_weights: HeuristicWeights = DEFAULT_WEIGHTS,
    bot_is_first: bool = True,
    verbose: bool = False,
    use_monte_carlo: bool = False,
    mc_simulations: int = 30,
    diary: bool = False
) -> Tuple[GameResult, Optional[GameDiary]]:
    """
    Simula una partita completa tra il bot e un avversario.
    
    Args:
        opponent: Bot avversario
        bot_weights: Pesi euristici per il nostro bot
        bot_is_first: True se il bot gioca per primo
        verbose: Se True, stampa le mosse
        use_monte_carlo: Se True, usa Monte Carlo per decisioni
        mc_simulations: Numero simulazioni MC
        diary: Se True, registra tutte le mosse nel diario
    
    Returns:
        Tuple (GameResult, GameDiary o None)
    """
    state = initialize_game()
    
    # Determina quale player è il bot
    bot_player = 0 if bot_is_first else 1
    
    # Crea bot con memoria persistente (necessario per diary)
    bot = ScopaBot(name="Bot")
    
    # Inizializza diary se richiesto
    game_diary = None
    if diary:
        game_diary = create_game_diary(bot_player, opponent.name)
    
    if verbose:
        print(f"\n--- Nuova Partita ---")
        print(f"Bot: P{bot_player}, Avversario: P{1 - bot_player}")
        print(f"Tavolo iniziale: {state.table}")
    
    # Loop di gioco
    turn_count = 0
    max_turns = 100  # Safety limit
    
    while not is_game_over(state) and turn_count < max_turns:
        # Se le mani sono vuote, distribuisci nuove carte
        if not state.players[0].hand and not state.players[1].hand:
            if state.deck:
                state = deal_cards(state, 3)
                if verbose:
                    print(f"\n[Distribuite nuove carte]")
                    print(f"  Mano P{bot_player}: {state.players[bot_player].hand}")
        
        if not state.current.hand:
            break
        
        turn_count += 1
        is_bot_turn = (state.current_player == bot_player)
        
        # Registra stato prima della mossa
        hand_before = cards_to_str(state.current.hand)
        table_before = cards_to_str(state.table)
        deck_remaining = len(state.deck)
        opp_hand_size = len(state.opponent.hand)
        
        # Scegli mossa
        all_moves_evaluated = []
        ai_context = {}
        
        if is_bot_turn:
            # Bot gioca - ottieni tutte le valutazioni per il diary
            if diary:
                evaluations = bot.get_all_evaluations(state)
                for ev in evaluations:
                    all_moves_evaluated.append({
                        "move": create_move_description(ev["move"]),
                        "score": ev["score"],
                        "reasons": ev["reasons"],
                        "card": card_to_str(ev["move"].card_played),
                        "captured": cards_to_str(ev["move"].cards_captured) if ev["move"].is_capture else [],
                        "is_scopa": ev["move"].is_scopa
                    })
                if evaluations:
                    ai_context = evaluations[0]["context"]
            
            move = bot.choose_move(state, bot_weights, use_monte_carlo, mc_simulations)
        else:
            move = opponent.choose_move(state)
        
        if verbose:
            player_name = "Bot" if is_bot_turn else "Opp"
            print(f"  {player_name}: {move}")
        
        # Applica mossa
        state = apply_move(state, move)
        
        # Registra nel diary
        if diary and game_diary:
            table_after = cards_to_str(state.table)
            
            entry = DiaryEntry(
                turn=turn_count,
                player="bot" if is_bot_turn else "opponent",
                deck_remaining=deck_remaining,
                hand_before=hand_before,
                table_before=table_before,
                opp_hand_size=opp_hand_size,
                move_played=create_move_dict(move),
                table_after=table_after,
                all_moves_evaluated=all_moves_evaluated if is_bot_turn else [],
                ai_context=ai_context if is_bot_turn else {},
                scores_current=estimate_current_scores(state, bot_player)
            )
            game_diary.add_entry(entry)
    
    # Calcola punteggi finali
    scores = calculate_scores(state)
    bot_score = scores[bot_player]
    opp_score = scores[1 - bot_player]
    
    # Finalizza diary
    if diary and game_diary:
        game_diary.set_final_result(bot_score, opp_score, state.last_capturer)
    
    if verbose:
        print(f"\n--- Fine Partita ---")
        print(f"Bot:  {bot_score}")
        print(f"Opp:  {opp_score}")
    
    result = GameResult(
        bot_score=bot_score,
        opponent_score=opp_score,
        bot_won=bot_score.total > opp_score.total,
        bot_points=bot_score.total,
        opponent_points=opp_score.total
    )
    
    return result, game_diary


def run_benchmark(
    opponent_level: str,
    num_games: int = 100,
    bot_weights: HeuristicWeights = DEFAULT_WEIGHTS,
    verbose: bool = False,
    progress: bool = True,
    use_monte_carlo: bool = False,
    mc_simulations: int = 30,
    save_diaries: int = 0
) -> BenchmarkStats:
    """
    Esegue un benchmark con N partite.
    
    Args:
        opponent_level: Livello avversario (random, beginner, medium, strong, pro)
        num_games: Numero di partite da simulare
        bot_weights: Pesi per il bot
        verbose: Mostra tutte le mosse
        progress: Mostra barra di progresso
        use_monte_carlo: Usa Monte Carlo per decisioni
        mc_simulations: Numero simulazioni MC
        save_diaries: Numero di partite da salvare come diary (0 = nessuna)
    
    Returns:
        BenchmarkStats con statistiche aggregate
    """
    opponent = create_opponent(opponent_level)
    stats = BenchmarkStats()
    diaries_saved = 0
    
    if progress:
        mc_str = " [MC]" if use_monte_carlo else ""
        diary_str = f" [DIARY: {save_diaries}]" if save_diaries > 0 else ""
        print(f"Benchmark vs {opponent.name} ({num_games} games){mc_str}{diary_str}...")
    
    for i in range(num_games):
        # Alterna chi inizia
        bot_is_first = (i % 2 == 0)
        
        # Salva diary solo per le prime N partite richieste
        record_diary = (diaries_saved < save_diaries)
        result, diary = simulate_game(
            opponent, bot_weights, bot_is_first, verbose, 
            use_monte_carlo, mc_simulations, diary=record_diary
        )
        stats.add_result(result)
        
        # Salva diary se richiesto
        if diary:
            filepath = diary.save()
            diaries_saved += 1
            if progress:
                print(f"  📓 Diary salvato: {filepath}")
        
        if progress and (i + 1) % 50 == 0:
            print(f"  {i + 1}/{num_games} ({stats.win_rate:.1%})")
    
    return stats


def interactive_mode():
    """
    Modalità interattiva: gioca contro il bot.
    """
    print("\n" + "="*50)
    print("SCOPA - Modalità Interattiva")
    print("="*50)
    print("\nGioca contro il bot. Tu sei P1.")
    
    state = initialize_game()
    bot_player = 0
    
    print(f"\nTavolo: {state.table}")
    
    while not is_game_over(state):
        # Distribuisci se necessario
        if not state.players[0].hand and not state.players[1].hand:
            if state.deck:
                state = deal_cards(state, 3)
                print(f"\n[Nuove carte distribuite]")
        
        if not state.current.hand:
            break
        
        print(f"\n--- Turno P{state.current_player} ---")
        print(f"Tavolo: {state.table}")
        
        if state.current_player == bot_player:
            # Bot gioca
            move = choose_best_move(state)
            print(f"Bot gioca: {move}")
            state = apply_move(state, move)
        else:
            # Umano gioca
            print(f"La tua mano: {state.current.hand}")
            moves = get_valid_moves(state)
            
            print("Mosse disponibili:")
            for idx, m in enumerate(moves):
                print(f"  [{idx}] {m}")
            
            while True:
                try:
                    choice = input("Scegli mossa (numero): ")
                    idx = int(choice)
                    if 0 <= idx < len(moves):
                        state = apply_move(state, moves[idx])
                        break
                    else:
                        print("Indice non valido.")
                except ValueError:
                    print("Inserisci un numero.")
    
    # Fine partita
    scores = calculate_scores(state)
    print("\n" + "="*50)
    print("FINE PARTITA")
    print("="*50)
    print(f"Bot (P0):  {scores[0]}")
    print(f"Tu (P1):   {scores[1]}")
    
    if scores[0].total > scores[1].total:
        print("\n🤖 Il bot ha vinto!")
    elif scores[1].total > scores[0].total:
        print("\n🎉 Hai vinto!")
    else:
        print("\n🤝 Pareggio!")


def main():
    parser = argparse.ArgumentParser(description="Scopa Bot Simulator")
    parser.add_argument("--games", "-n", type=int, default=100,
                        help="Numero di partite da simulare")
    parser.add_argument("--opponent", "-o", type=str, default="medium",
                        choices=["random", "beginner", "medium", "strong", "pro",
                                "human_casual", "human_amateur", "human_expert", "human_pro", "scopa_ai", "scopa_rl"],
                        help="Livello avversario")
    parser.add_argument("--interactive", "-i", action="store_true",
                        help="Modalità interattiva")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Mostra tutte le mosse")
    parser.add_argument("--all", "-a", action="store_true",
                        help="Benchmark contro tutti i livelli")
    parser.add_argument("--monte-carlo", "-mc", action="store_true",
                        help="Usa Monte Carlo")
    parser.add_argument("--mc-sims", type=int, default=50,
                        help="Numero simulazioni MC")
    parser.add_argument("--diary", "-d", type=int, default=0,
                        help="Numero di partite da salvare come diary (per debug)")
    
    args = parser.parse_args()
    
    if args.interactive:
        interactive_mode()
        return
    
    if args.all:
        # Include sia bot sintetici che umani
        levels = ["random", "beginner", "medium", "strong", "pro",
                  "human_casual", "human_amateur", "human_expert", "human_pro", "scopa_ai"]
        results = {}
        
        for level in levels:
            stats = run_benchmark(level, args.games, verbose=args.verbose, 
                                use_monte_carlo=args.monte_carlo, mc_simulations=args.mc_sims,
                                save_diaries=args.diary)
            results[level] = stats
        
        print("\n" + "="*60)
        print("SUMMARY - All Opponents")
        print("="*60)
        print(f"{'Level':<12} {'Win Rate':<12} {'Avg Margin':<12} {'Bot Pts':<10} {'Opp Pts':<10}")
        print("-"*60)
        for level, stats in results.items():
            print(f"{level:<12} {stats.win_rate:>10.1%} {stats.avg_margin:>+10.2f} {stats.avg_bot_points:>10.2f} {stats.avg_opponent_points:>10.2f}")
        print("="*60)
    else:
        stats = run_benchmark(args.opponent, args.games, verbose=args.verbose,
                            use_monte_carlo=args.monte_carlo, mc_simulations=args.mc_sims,
                            save_diaries=args.diary)
        print("\n" + str(stats))


if __name__ == "__main__":
    main()
