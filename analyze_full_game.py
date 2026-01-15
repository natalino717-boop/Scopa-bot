import json

try:
    with open("game_dump.json", "r") as f:
        history = json.load(f)

    print(f"Total Moves Recorded: {len(history)}")

    for i, turn in enumerate(history):
        req = turn['request']
        dec = turn['decision']
        
        print(f"\n--- MOVE {i+1} ---")
        print(f"Hand: {req['hand']}")
        print(f"Table: {req['table']}")
        print(f"Played: {dec['card_played']} ({dec['description']})")
        
        # Calculate what was left on table roughly
        # This is hard without full logic, but let's look at the description
        # If it says "Gioca X -> prende Y", we know Y is gone.
        
        # Check if 7 was taken
        if "7" in dec['description'] and "prende" in dec['description']:
            print(">>> TOOK A 7 (Potentially Greedy)")

        # In memory state
        print(f"Memory Size: {len(turn['memory_before'])}")

except Exception as e:
    print(e)
