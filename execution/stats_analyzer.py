import json
import os
import glob
from collections import defaultdict
from scopa_core import Card, Suit, calculate_primiera, Score

def parse_card_safe(code):
    try:
        if not code: return None
        val = int(code[:-1])
        suit_char = code[-1].lower()
        suits = {'b': Suit.BASTONI, 'c': Suit.COPPE, 'd': Suit.DENARI, 's': Suit.SPADE}
        return Card(suits[suit_char], val)
    except:
        return None

def analyze_all_games():
    diary_dir = "game_diaries"
    files = glob.glob(os.path.join(diary_dir, "game_*.json"))
    
    total_games = 0
    wins = 0
    losses = 0
    draws = 0
    
    print(f"📊 SCOPA BOT - PERFORMANCE REPORT")
    print("="*60)
    
    for filepath in sorted(files):
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
            
            moves = data.get("moves", [])
            if not moves: continue
            
            # Skip short games (testing)
            if len(moves) < 10: continue
            
            # --- REPLAY & SCORE ---
            my_captured = []
            my_scope = 0
            
            # Tracking table changes to detect Opponent Scope
            # We assume initial table from turn 0
            # But wait, request contains CURRENT table.
            
            for i, turn in enumerate(moves):
                req = turn['request']
                dec = turn['decision']
                
                # My Move
                if dec['is_capture']:
                    # We can't trust dec['description'] parsing perfectly without logic
                    # relying on 'is_capture' flag
                    # We know we played 'played_card'
                    played_card = parse_card_safe(dec['card_played'])
                    if played_card:
                         my_captured.append(played_card)
                    
                    # Determining what was captured is hard without re-simulating
                    # Heuristic: Compare Table T(i) and Table T(i+1) is impossible (we only see T(i))
                    # Wait, we see T(next_turn) in next move!
                    
                    if i < len(moves) - 1:
                        next_table_strs = moves[i+1]['request']['table']
                        curr_table_strs = req['table']
                        
                        # Captured = (CurrentTable + Played) - NextTable? 
                        # NO. NextTable is AFTER Opponent move!
                        # So we can't easily distinguish MyCapture from OppCapture logic intermediate.
                        
                        # FALLBACK: Use heuristic on MY logged description?
                        # "Gioca 3C -> prende [2S]"
                        # Extract captured cards from description string if possible.
                        desc = dec['description']
                        if "prende [" in desc:
                            content = desc.split("prende [")[1].split("]")[0]
                            # content eg "2S, 3D"
                            parts = content.split(",")
                            for p in parts:
                                c = parse_card_safe(p.strip())
                                if c: my_captured.append(c)
                            
                        if "SCOPA!" in desc:
                            my_scope += 1
            
            # Calculate My Points Components
            denari = sum(1 for c in my_captured if c.is_denaro)
            settebello = any(c.is_settebello for c in my_captured)
            carte_count = len(my_captured)
            primiera_val = calculate_primiera(my_captured)
            
            # APPROXIMATION:
            # We don't know Opponent stats accurately. 
            # But we know total cards = 40, total denari = 10.
            
            opp_denari = 10 - denari
            opp_carte = 40 - carte_count # approx (cards on table at end?)
            
            # Scoring
            my_pts = my_scope
            opp_pts = 0 # Can't calculate opponent scope easily log-based
            
            if denari > 5: my_pts += 1
            elif opp_denari > 5: opp_pts += 1
            
            if settebello: my_pts += 1
            else: opp_pts += 1 # If I don't have it, he has it (unless on table at end, rare)
            
            if carte_count > 20: my_pts += 1
            elif opp_carte > 20: opp_pts += 1
            
            # Primiera: We need opponent captured cards to compare.
            # If my primiera is very high (e.g. > 70 with 7777), likely win.
            # Let's assume > 60 is a win? 
            # Standard max is 84 (4x21). Min 0.
            # If I have 3 sevens, I usually win primiera.
            sevens = sum(1 for c in my_captured if c.value == 7)
            if sevens >= 3: my_pts += 1
            elif sevens <= 1: opp_pts += 1
            # Else draw or unknown (2 vs 2) -> Ignore point
            
            # Result
            outcome = "?"
            if my_pts > 3.5: outcome = "WIN" # 3.5? Scopa points usually to 11.
            # In single round (4 points max + scope):
            # If we extract > 2 points from the 4 fixed points, plus scopes.
            # Let's simple check:
            
            if my_pts > opp_pts: 
                wins += 1
                outcome = "WIN"
            elif opp_pts > my_pts: 
                losses += 1
                outcome = "LOSS"
            else:
                draws += 1
                outcome = "DRAW"
                
            game_id = os.path.basename(filepath)
            print(f"📄 {game_id}: {outcome:<4} (MyPts Est: {my_pts} | Den: {denari} | 7B: {settebello} | Scope: {my_scope})")
            
            total_games += 1
            
        except Exception as e:
            print(f"Error parsing {filepath}: {e}")
            
    print("="*60)
    if total_games > 0:
        rate = (wins / total_games) * 100
        print(f"TOTAL GAMES: {total_games}")
        print(f"WINS: {wins} | LOSSES: {losses} | DRAWS: {draws}")
        print(f"📈 ESTIMATED WIN RATE: {rate:.1f}%")
    else:
        print("No valid games found.")

if __name__ == "__main__":
    analyze_all_games()
