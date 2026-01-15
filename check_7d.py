import json

with open('diary_analysis.json') as f:
    data = json.load(f)

for game in data['games']:
    for m in game['moves']:
        table = m['request']['table']
        hand = m['request']['hand']
        dec = m['decision']
        
        # Settebello on table, could have taken it but didn't?
        if dec['is_capture'] and '7d' in table:
            captured = dec['description']
            if '7D' not in captured.upper():
                print(f"MISSED SETTEBELLO! Move {m['move_number']}")
                print(f"  Hand={hand}, Table={table}")
                print(f"  Decision: {dec}")
        
        # Both 7s in hand, used one for capture
        if '7d' in hand and '7b' in hand and dec['is_capture']:
            print(f"BOTH 7s in hand! Move {m['move_number']}")
            print(f"  Hand={hand}, Table={table}")
            print(f"  Decision: {dec}")
