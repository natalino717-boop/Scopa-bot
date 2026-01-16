import json
import sys
import os

def analyze_diary(filename):
    print(f"Analyzing: {filename}")
    try:
        with open(filename, "r") as f:
            data = json.load(f)
            
        moves = data.get("moves", [])
        print(f"Total Moves: {len(moves)}\n")
        
        for i, turn in enumerate(moves):
            req = turn['request']
            dec = turn['decision']
            evals = turn.get('evaluations', [])
            
            try:
                my_s = req.get('my_score_match', 0)
                opp_s = req.get('opp_score_match', 0)
            except Exception:
                my_s, opp_s = 0, 0
                
            print(f"=== TURN {i+1} ===")
            print(f"Hand:  {req['hand']}")
            print(f"Table: {req['table']}")
            print(f"Score: My {my_s} - Opp {opp_s}")
            
            # Show chosen move details
            print(f"👉 CHOSEN: {dec['card_played']} ({dec['description']})")
            
            # Find chosen move in evals to get its score
            chosen_score = "N/A"
            chosen_reasons = []
            
            # Sort evals by score descending
            evals.sort(key=lambda x: x['score'], reverse=True)
            
            print("\n   Alternatives considered:")
            for ev in evals:
                is_chosen = (str(ev['move']) == dec['description'] or 
                           (ev['card'] == dec['card_played'] and str(ev['move']) == dec['description']))
                
                # Simple check might fail if description varies slightly, but let's try
                # Actually server.py saves 'move': str(ev['move']) which is the description
                
                marker = "✅" if is_chosen else "❌"
                print(f"   {marker} Score: {ev['score']:>4} | Card: {ev['card']} | {ev['move']}")
                print(f"      Reasons: {ev['reasons']}")
            
            print("-" * 60 + "\n")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        analyze_diary(sys.argv[1])
    else:
        # Find latest file
        diary_dir = "game_diaries"
        files = [os.path.join(diary_dir, f) for f in os.listdir(diary_dir) if f.endswith(".json")]
        if not files:
            print("No diaries found.")
            sys.exit(1)
        latest_file = max(files, key=os.path.getmtime)
        analyze_diary(latest_file)
