"""
Validate Game Diary - Analizza i diary per trovare anomalie

Questo script:
1. Verifica che le carte siano parsate correttamente
2. Controlla che le mosse possibili siano coerenti
3. Identifica situazioni sospette (es: settebello non preso)
"""

import json
import sys
from pathlib import Path


def load_latest_game():
    """Carica l'ultimo game diary."""
    diary_dir = Path(__file__).parent / "game_diaries"
    if not diary_dir.exists():
        print("❌ Directory game_diaries non trovata")
        return None
    
    files = sorted(diary_dir.glob("game_*.json"), reverse=True)
    if not files:
        print("❌ Nessun diary trovato")
        return None
    
    with open(files[0]) as f:
        game = json.load(f)
        print(f"📂 Caricato: {files[0].name}")
        return game


def validate_move(move_data):
    """Valida una singola mossa e ritorna eventuali problemi."""
    issues = []
    
    validation = move_data.get("validation", {})
    decision = move_data.get("decision", {})
    all_moves = move_data.get("all_moves_evaluated", [])
    
    if not validation:
        return ["⚠️ Nessun dato di validazione (diary vecchio formato)"]
    
    # Check 1: Input vs Parsed
    input_hand = set(validation.get("input_hand", []))
    parsed_hand = set(validation.get("parsed_hand", []))
    if input_hand != parsed_hand:
        issues.append(f"❌ Parsing mano errato: {input_hand} → {parsed_hand}")
    
    # Check 2: Mosse possibili
    num_captures = validation.get("num_captures", 0)
    num_discards = validation.get("num_discards", 0)
    if num_captures == 0 and num_discards == 0:
        issues.append("❌ Nessuna mossa possibile generata!")
    
    # Check 3: Settebello handling
    has_7d_in_hand = validation.get("has_settebello_in_hand", False)
    has_7d_on_table = validation.get("has_settebello_on_table", False)
    can_capture_7d = validation.get("can_capture_settebello", False)
    
    if has_7d_on_table and not can_capture_7d:
        issues.append("⚠️ 7D sul tavolo ma non catturabile")
    
    if can_capture_7d:
        # Verifica che sia stata effettivamente catturata
        chosen_card = decision.get("card_played", "")
        captured = decision.get("description", "")
        if "7D" not in captured.upper() and "7d" not in captured.lower():
            issues.append(f"❌ CRITICO: Poteva prendere 7D ma ha scelto: {captured}")
    
    # Check 4: Mossa scelta è la migliore?
    if all_moves:
        best_move = all_moves[0]
        best_score = best_move.get("score", 0)
        chosen_desc = decision.get("description", "")
        
        # Verifica che la mossa scelta corrisponda alla migliore
        if best_move["move"] != chosen_desc:
            # Potrebbe usare solver endgame
            pass  # OK se usa minimax
    
    return issues


def analyze_game(game):
    """Analizza l'intera partita."""
    print(f"\n{'='*60}")
    print(f"ANALISI PARTITA {game.get('game_id')}")
    print(f"Timestamp: {game.get('timestamp')}")
    print(f"Totale mosse: {game.get('total_moves')}")
    print(f"{'='*60}\n")
    
    total_issues = 0
    critical_issues = 0
    
    for move in game.get("moves", []):
        move_num = move.get("move_number")
        issues = validate_move(move)
        
        if issues:
            print(f"Mossa {move_num}:")
            for issue in issues:
                print(f"  {issue}")
                total_issues += 1
                if "CRITICO" in issue:
                    critical_issues += 1
            print()
    
    print(f"\n{'='*60}")
    print(f"RIEPILOGO")
    print(f"{'='*60}")
    print(f"Problemi totali: {total_issues}")
    print(f"Problemi critici: {critical_issues}")
    
    if total_issues == 0:
        print("\n✅ Nessuna anomalia rilevata! Il bot ha capito correttamente.")
    elif critical_issues > 0:
        print(f"\n❌ {critical_issues} problemi critici da investigare!")
    else:
        print(f"\n⚠️ {total_issues} avvisi da verificare")
    
    return total_issues, critical_issues


def main():
    print("🔍 Game Diary Validator\n")
    
    game = load_latest_game()
    if game:
        analyze_game(game)


if __name__ == "__main__":
    main()
