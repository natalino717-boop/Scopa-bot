import json
import sys
import os
from scopa_core import Card, Suit

def parse_card_safe(code):
    try:
        if not code: return None
        val = int(code[:-1])
        suit_char = code[-1].lower()
        suits = {'b': Suit.BASTONI, 'c': Suit.COPPE, 'd': Suit.DENARI, 's': Suit.SPADE}
        return Card(suits[suit_char], val)
    except Exception:
        return None

def analyze_endgames(filename):
    print(f"🕵️‍♂️ ENDGAME ANALYSIS: {filename}")
    try:
        with open(filename, "r") as f:
            data = json.load(f)
            
        all_moves = data.get("moves", [])
        if not all_moves:
            print("No moves found.")
            return

        # Split into games
        games = []
        current_game = []
        
        for i, move in enumerate(all_moves):
            # Detection of new game:
            # - If hand size jumps to 3 from 0/1 (and cards change completely)
            # - Or purely based on timestamps if available
            # - Or if 'req.table' has 4 new cards and hand has 3.
            
            # Simple heuristic: If we played 30+ moves and hand becomes 3 again -> New Game.
            # OR if i == 0.
            
            is_new_game = False
            if i == 0:
                is_new_game = True
            elif len(current_game) > 30 and len(move['request']['hand']) == 3:
                 # Check if cards are different from previous hand remnants?
                 # If previous hand was empty (0), then 3 is new deal. 
                 # But dealing happens within game too.
                 # End of game is when deck is empty and hands are empty.
                 pass
            
            # Better heuristic: Check time gap?
            # data has timestamps.
            
            # Let's rely on manual inspection logic within loop
            # Just collect everything and then find "Last 6 moves" of the chunks.
            # A game is ~35-40 turns (my moves).
            
            current_game.append(move)
            
        # Since logic to split perfectly is hard without clear delimiter, 
        # let's assume the file grew, so the last moves are the LATEST game.
        # AND user played "two more games". So we might have Game 1 (old), Game 2, Game 3.
        
        # Let's look at the TIMESTAMPS to identify breaks.
        breaks = []
        last_ts = all_moves[0].get('timestamp', 0)
        
        for i, m in enumerate(all_moves):
            ts = m.get('timestamp', 0)
            if ts - last_ts > 60: # > 1 minute break -> New Game
                breaks.append(i)
            last_ts = ts
            
        print(f"Detected potential game breaks at indices: {breaks}")
        
        # Define ranges
        ranges = []
        start = 0
        for b in breaks:
            ranges.append((start, b))
            start = b
        ranges.append((start, len(all_moves)))
        
        print(f"Found {len(ranges)} segments.")
        
        # Analyze last 2 segments (the "two more games")
        for idx, (start, end) in enumerate(ranges[-2:]): 
            print(f"\n=== GAME SEGMENT {idx+1} (Moves {start} to {end-1}) ===")
            segment = all_moves[start:end]
            
            # Show last 8 moves
            last_n = 8
            if len(segment) < last_n: last_n = len(segment)
            
            print(f"Showing LAST {last_n} moves (Endgame)...")
            
            for i in range(len(segment)-last_n, len(segment)):
                turn = segment[i]
                req = turn['request']
                dec = turn['decision']
                evals = turn.get('evaluations', [])
                
                print(f"\n--- Move {i+1} (Global {start+i+1}) ---")
                print(f"Hand: {req['hand']}")
                print(f"Table: {req['table']}")
                print(f"Played: {dec['card_played']} -> {dec['description']}")
                
                # Show top 2 evaluations
                if evals:
                    evals.sort(key=lambda x: x['score'], reverse=True)
                    print("   Evaluations:")
                    for ev in evals[:2]:
                         err_mark = "✅" if ev['card'] == dec['card_played'] else ""
                         print(f"   {err_mark} {ev['card']:<3} Score: {ev['score']:>4} | {ev['reasons']}")
                else:
                    print("   (No evaluations recorded)")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        analyze_endgames(sys.argv[1])
    else:
        # Find latest
        diary_dir = "game_diaries"
        files = [os.path.join(diary_dir, f) for f in os.listdir(diary_dir) if f.endswith(".json")]
        if files:
            latest = max(files, key=os.path.getmtime)
            analyze_endgames(latest)
