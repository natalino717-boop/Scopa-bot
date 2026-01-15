
import json
import os
import glob
from dataclasses import dataclass
from typing import List, Dict, Optional

# Constants matching scopa_ai.py P values for context
P_HIGH = 65
P_MEDIUM = 38

@dataclass
class Mistake:
    game_id: str
    move_num: int
    turn_type: str
    description: str
    severity: str  # CRITICAL, WARNING, INFO

def load_diaries(base_path: str) -> List[dict]:
    files = glob.glob(os.path.join(base_path, "*.json"))
    diaries = []
    print(f"Found {len(files)} diaries in {base_path}")
    for f in files:
        try:
            with open(f, 'r') as fp:
                data = json.load(fp)
                # Normalize structure (some might be list of entries, some might be dict with 'moves')
                if isinstance(data, list):
                    # Old format, usually just raw list of moves? 
                    # Assuming standard format: {"game_id": ..., "moves": [...]}
                    pass # Skip raw lists if any
                elif "moves" in data:
                    diaries.append(data)
        except Exception as e:
            print(f"Error loading {f}: {e}")
    return diaries

def analyze_game(game: dict) -> List[Mistake]:
    mistakes = []
    moves = game.get("moves", [])
    game_id = str(game.get("game_id", "unknown"))
    
    for i, entry in enumerate(moves):
        move_num = entry.get("move_number", i+1)
        
        # 1. Check for Suboptimal Choice (Score Discrepancy)
        decision = entry.get("decision", {})
        chosen_card = decision.get("card_played", "")
        chosen_desc = decision.get("description", "")
        
        evals = entry.get("all_moves_evaluated", [])
        if not evals:
            continue
            
        # Find score of chosen move
        # We match by description or card logic
        chosen_score = -99999
        best_score = -99999
        best_move_desc = ""
        
        # Parse evals
        parsed_evals = []
        for e in evals:
            s = e.get("score", -9999)
            parsed_evals.append((s, e))
            if s > best_score:
                best_score = s
                best_move_desc = e.get("move", "")
        
        # Find chosen in evals
        for e in evals:
            # Match by strict string equality of description or card if description is generic
            # Diary format: decision.description matches e["move"] usually
            if e.get("move") == chosen_desc:
                chosen_score = e.get("score", -9999)
                break
        
        # If chosen score not found, try heuristics
        if chosen_score == -99999:
            # Maybe description format differs?
            pass

        # Check discrepancy
        if chosen_score != -99999 and best_score > chosen_score:
            diff = best_score - chosen_score
            if diff > P_MEDIUM: # Significant difference
                 mistakes.append(Mistake(
                     game_id, move_num, "SUBOPTIMAL_MOVE",
                     f"Chose {chosen_desc} (score {chosen_score}) instead of {best_move_desc} (score {best_score}). Diff: {diff}",
                     "WARNING"
                 ))

        # 2. Check Missed Opportunities (Settebello/Scopa)
        # Scan best moves vs chosen
        if chosen_score != -99999:
            chosen_eval = next((e for e in evals if e.get("move") == chosen_desc), {})
            chosen_reasons = chosen_eval.get("reasons", [])
            
            # Did we miss Settebello?
            # Check if any OTHER move has "7d" or "settebello" in reasons and we don't
            has_settebello = any("7D" in str(r).upper() for r in chosen_reasons)
            
            if not has_settebello:
                for e in evals:
                    r_list = e.get("reasons", [])
                    if any("7D" in str(r).upper() for r in r_list):
                        # We missed 7D!
                        mistakes.append(Mistake(
                            game_id, move_num, "MISSED_SETTEBELLO",
                            f"Missed capturing 7D! Available in move {e['move']}",
                            "CRITICAL"
                        ))
                        break

            # Did we miss Scopa?
            is_scopa = chosen_eval.get("is_scopa", False)
            if not is_scopa:
                for e in evals:
                    if e.get("is_scopa", False):
                        mistakes.append(Mistake(
                            game_id, move_num, "MISSED_SCOPA",
                            f"Missed Scopa! Available in move {e['move']}",
                            "CRITICAL"
                        ))
                        break

        # 3. Opponent Scopa Detection (Lookahead to next turn)
        if i < len(moves) - 1:
            next_entry = moves[i+1]
            
            # Reconstruct table state after my move
            # Current req.table
            table_before = entry.get("request", {}).get("table", [])
            
            # Logic:
            # If I captured: table len decreases.
            # If I discarded: table len increases +1.
            
            # We need to know if I captured. `decision.is_capture`.
            is_capture = decision.get("is_capture", False)
            # How many captured? Not in decision directly easily unless parsed.
            # But the diary stores `memory_after`.
            # We can infer from table_before and next_entry table_before?
            # No, opponent moves in between.
            
            # Heuristic: If next entry table is empty, and it wasn't empty after my move.
            # Calculate table after my move explicitly?
            # Hard without parsing card objects.
            
            # Simpler: If next_entry["request"]["table"] is empty (len==0)
            # AND table_before was NOT empty (or my move didn't clear it).
            
            next_table = next_entry.get("request", {}).get("table", [])
            
            if len(next_table) == 0:
                # Opponent cleared table OR I cleared it and opponent did nothing (unlikely - dealing?)
                # If I cleared it (Scopa), then fine.
                
                # If I didn't Scopa, and next table is empty -> Opponent Scopa!
                # (Unless opponent captured last card but didn't Scopa? No, capture last = Scopa usually, except end of deck).
                
                my_scopa = False
                if chosen_score != -99999:
                     my_scopa = next((e.get("is_scopa") for e in evals if e.get("move") == chosen_desc), False)
                
                if not my_scopa and len(table_before) > 0:
                    # Opponent cleared table!
                    # Check if I left a sum <= 10
                    # This requires parsing table. Skipping complex logic for now.
                    mistakes.append(Mistake(
                        game_id, move_num, "OPPONENT_CLEARED_TABLE",
                        "Opponent found empty table next turn (Possible Scopa/Capture All). Check if we left an easy sum.",
                        "INFO"
                    ))

    return mistakes

def main():
    diaries = load_diaries("game_diaries")
    # Also check .tmp/game_diaries
    diaries += load_diaries(".tmp/game_diaries")
    
    all_mistakes = []
    
    for d in diaries:
        mistakes = analyze_game(d)
        all_mistakes.extend(mistakes)
    
    print(f"\nANALYSIS COMPLETE. Found {len(all_mistakes)} potential issues.\n")
    
    # Sort by severity
    critical = [m for m in all_mistakes if m.severity == "CRITICAL"]
    warning = [m for m in all_mistakes if m.severity == "WARNING"]
    info = [m for m in all_mistakes if m.severity == "INFO"]
    
    print("=== CRITICAL MISTAKES (Missed 7D/Scopa) ===")
    for m in critical:
        print(f"[{m.game_id}] Move {m.move_num}: {m.description}")
    
    print("\n=== WARNINGS (Suboptimal Moves) ===")
    for m in warning:
        print(f"[{m.game_id}] Move {m.move_num}: {m.description}")
        
    print("\n=== INFO (Opponent Clears) ===")
    for m in info[:10]: # Limit info output
        print(f"[{m.game_id}] Move {m.move_num}: {m.description}")

if __name__ == "__main__":
    main()
