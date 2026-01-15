import json
import sys
import os
from collections import defaultdict

def analyze_luck(filename):
    print(f"🍀 LUCK ANALYSIS: {filename}")
    try:
        with open(filename, "r") as f:
            data = json.load(f)
            
        moves = data.get("moves", [])
        
        # Stats
        my_denari = 0
        opp_denari = 0
        my_settebello = False
        opp_settebello = False
        
        opp_scopas = 0
        opp_scopas_avoidable = 0
        
        # Track full deck to see distribution
        my_hand_cards = []
        opp_played_cards = []
        
        for i, turn in enumerate(moves):
            req = turn['request']
            dec = turn['decision']
            
            # 1. Analyze My Hand (Luck of the Deal)
            # We see our hand every turn, but we only want to count UNIQUE cards dealt
            # Simplification: Count cards when hand size is 3 (new deal) or track unique codes
            if i == 0 or (len(req['hand']) == 3 and i > 0):
                for c_code in req['hand']:
                    if c_code not in my_hand_cards:
                        my_hand_cards.append(c_code)
                        if "7d" in c_code: my_settebello = True
                        if c_code.endswith("d"): my_denari += 1

            # 2. Analyze Opponent Scopa
            # If opp score increased by > 1 (Settebello?) or just check 'last_action_desc' from NEXT turn?
            # The log stores "last_action_desc" in the request of the CURRENT turn (referring to prev).
            # But "opp_score_match" is cumulative.
            
            # Let's look at the "last_action_desc" of the NEXT turn to see what Opponent did after My Move.
            if i < len(moves) - 1:
                next_req = moves[i+1]['request']
                last_act = next_req.get('last_action_desc', "")
                
                if "Scopa" in last_act or "scopa" in last_act: # Opponent made Scopa
                    opp_scopas += 1
                    
                    # Was it avoidable?
                    # Check table state AFTER my move in current turn
                    # We need to simulate the move 'dec' on 'req.table'
                    my_card = dec['card_played']
                    is_capt = dec['is_capture']
                    
                    table_after = list(req['table'])
                    if is_capt:
                        # Cannot easily know WHICH cards capture without re-running logic
                        # But we assume the table became safer or empty.
                        # If I made a capture, I usually leave fewer cards.
                        pass 
                    else:
                        table_after.append(my_card)
                        
                    # Heuristic:
                    # If TableAfter had < 10 sum OR single card <= 7, it's risky.
                    # We can't fully reconstruct without logic, but let's count Total Opp Scopes first.
            
            # 3. Track Opponent Cards (played)
            # This is hard from just my moves logs, because I don't confirm exactly what opp played 
            # unless I parse 'last_action_desc' perfectly.
            
        print("\n--- 🃏 DISTRIBUTION ---")
        print(f"My Hand Total Cards Tracked: {len(my_hand_cards)}")
        print(f"My Denari Dealt: {my_denari} / 10")
        print(f"My Settebello: {'YES' if my_settebello else 'NO'}")
        
        print(f"\n--- ⚠️ OPPONENT SCOPAS ---")
        print(f"Opponent Scopas Made: {opp_scopas}")
        
        # Hard to judge "Skill error" without full enemy hand, 
        # but if we had Settebello and lost it, that's bad luck or bad play.
        
        if my_settebello and opp_scopas > 0:
            print("\nResult: You had Settebello but Opponent made Scopas.")
        elif not my_settebello:
            print("\nResult: Opponent likely had Settebello (Bad Luck).")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    diary_dir = "game_diaries"
    files = [os.path.join(diary_dir, f) for f in os.listdir(diary_dir) if f.endswith(".json")]
    if files:
        latest = max(files, key=os.path.getmtime)
        analyze_luck(latest)
