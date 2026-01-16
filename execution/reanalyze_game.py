import json
import sys
import os
from scopa_core import GameState, PlayerState, Card, Suit
from scopa_ai import ScopaBot, get_valid_moves

def parse_card_safe(code):
    try:
        if not code: return None
        # Handle '7b' format
        val = int(code[:-1])
        suit_char = code[-1].lower()
        suits = {'b': Suit.BASTONI, 'c': Suit.COPPE, 'd': Suit.DENARI, 's': Suit.SPADE}
        return Card(suits[suit_char], val)
    except Exception:
        return None

def reanalyze_diary(filename):
    print(f"Re-Analyzing: {filename}")
    try:
        with open(filename, "r") as f:
            data = json.load(f)
            
        moves = data.get("moves", [])
        print(f"Total Moves: {len(moves)}\n")
        
        bot = ScopaBot()
        # Cumulative memory for re-analysis
        global_seen = set()
        
        for i, turn in enumerate(moves):
            req = turn['request']
            dec = turn['decision']
            
            # 1. Reconstruct State
            hand_strs = req['hand']
            table_strs = req['table']
            
            hand = [parse_card_safe(c) for c in hand_strs if parse_card_safe(c)]
            table = [parse_card_safe(c) for c in table_strs if parse_card_safe(c)]
            
            # Update memory (cumulative)
            for c in hand + table:
                global_seen.add(c)
            
            # Sync bot memory
            bot.memory.seen = global_seen.copy()
            
            # Create GameState
            # We don't know opponent hand, so we leave it empty/unknown
            # We assume it's our turn
            my_player = 0
            state = GameState(
                table=table,
                players=[
                    PlayerState(hand=hand, captured=[], scope=0), # Us
                    PlayerState(hand=[], captured=[], scope=0)    # Opponent (unknown)
                ],
                current_player=my_player,
                deck=[] # Deck is unknown/irrelevant for immediate move scoring usually
            )
            
            # 2. Get Evaluations (Current Logic)
            print(f"=== TURN {i+1} ===")
            print(f"Hand:  {hand_strs}")
            print(f"Table: {table_strs}")
            print(f"Played: {dec['card_played']} ({dec['description']})")
            
            try:
                # Use faster MC or heuristic for analysis
                # NOTE: get_all_evaluations uses score_move which is heuristic!
                # If the bot used MC in the real game, score_move might differ.
                # But looking at score_move reasons is the best way to understand "Static" logic.
                evals = bot.get_all_evaluations(state)
                
                # If we want to verify MC choice, we would need to run choose_move
                # But let's look at evaluations first to see the scoring breakdown
                
                evals.sort(key=lambda x: x['score'], reverse=True)
                
                print("\n   [Re-Analysis] Top Moves by Static Score:")
                for idx, ev in enumerate(evals):
                    # Check if this was the played move
                    is_played = (str(ev['move'].card_played).lower() == dec['card_played'].lower())
                    if idx < 3 or is_played: # Show top 3 and played one
                        marker = "✅ PLAYED" if is_played else f"#{idx+1}"
                        if is_played: marker += " (CHOSEN)"
                        
                        print(f"   {marker:<15} Score: {ev['score']:>4} | {ev['move']}")
                        print(f"      Reasons: {ev['reasons']}")
            
            except Exception as e:
                print(f"   Error analyzing turn: {e}")
                import traceback
                traceback.print_exc()

            print("-" * 60 + "\n")
            
            # Update memory with played card for next turn
            played_card = parse_card_safe(dec['card_played'])
            if played_card:
                global_seen.add(played_card)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        reanalyze_diary(sys.argv[1])
    else:
        diary_dir = "game_diaries"
        files = [os.path.join(diary_dir, f) for f in os.listdir(diary_dir) if f.endswith(".json")]
        if not files:
            print("No diaries found.")
            sys.exit(1)
        latest_file = max(files, key=os.path.getmtime)
        reanalyze_diary(latest_file)
