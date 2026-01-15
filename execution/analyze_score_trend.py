import json
import sys
import os

def analyze_score_trend(filename):
    print(f"📉 SCORE TREND ANALYSIS: {filename}")
    try:
        with open(filename, "r") as f:
            data = json.load(f)
            
        moves = data.get("moves", [])
        
        last_my = 0
        last_opp = 0
        
        print(f"{'TURN':<5} | {'MY':<5} | {'OPP':<5} | {'EVENT'}")
        print("-" * 40)
        
        opp_scope_cnt = 0
        my_scope_cnt = 0
        
        for i, turn in enumerate(moves):
            req = turn['request']
            dec = turn['decision']
            
            # scores in request (before my move?) or current?
            # usually score is current state
            try:
                cur_my = req.get('my_score_match', 0)
                cur_opp = req.get('opp_score_match', 0)
            except:
                cur_my, cur_opp = 0, 0
            
            event = ""
            if cur_opp > last_opp:
                diff = cur_opp - last_opp
                event = f"🔴 OPP +{diff} (Scopa?)"
                opp_scope_cnt += diff
            
            if cur_my > last_my:
                diff = cur_my - last_my
                event = f"🟢 MY +{diff} (Scopa?)"
                my_scope_cnt += diff
                
            print(f"{i+1:<5} | {cur_my:<5} | {cur_opp:<5} | {event}")
            
            last_my = cur_my
            last_opp = cur_opp
            
        print("-" * 40)
        print(f"detected Scope MY: {my_scope_cnt}")
        print(f"detected Scope OPP: {opp_scope_cnt}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    diary_dir = "game_diaries"
    files = [os.path.join(diary_dir, f) for f in os.listdir(diary_dir) if f.endswith(".json")]
    if files:
        latest = max(files, key=os.path.getmtime)
        analyze_score_trend(latest)
