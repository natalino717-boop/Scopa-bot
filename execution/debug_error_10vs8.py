
import sys
from scopa_ai import ScopaBot, CardMemory, score_move, get_game_phase
from scopa_core import GameState, PlayerState, Card, Suit, get_valid_moves

def code_to_card(code):
    code = code.strip().lower()
    suit_map = {'d': Suit.DENARI, 'c': Suit.COPPE, 's': Suit.SPADE, 'b': Suit.BASTONI}
    val = int(code[:-1])
    suit = suit_map[code[-1]]
    return Card(suit, val)

def recreate_scenario():
    print("=== RECREATING ERROR SCENARIO ===")
    
    # 1. Setup Bot and Memory
    bot = ScopaBot()
    
    seen_codes = [
        "2c", "10c", "7b", "5s", "10d", "7d", "2d", "7c", "4b", "4d", 
        "4s", "3s", "8d", "9b", "8b", "7s", "8c", "5b", "9s", "10s", 
        "1b", "3d", "1s", "5d", "3b", "2b", "5c", "2s", "8s", "3c", 
        "10b", "6b", "1c"
    ]
    
    # Verify 7s are present
    sevens = [c for c in seen_codes if c.startswith("7")]
    print(f"Sevens in history: {sevens} (Expect 4)")
    
    for code in seen_codes:
        bot.memory.seen.add(code_to_card(code))
        
    print(f"Memory size: {len(bot.memory.seen)}/40")
    
    # 2. Setup Game State
    # Hand: 8s, 10b
    hand = [code_to_card("8s"), code_to_card("10b")]
    
    # Table: 1c, 6b, 8c
    table = [code_to_card("1c"), code_to_card("6b"), code_to_card("8c")]
    
    print(f"Hand: {hand}")
    print(f"Table: {table}")
    
    # Adding deck to state (safeguard)
    state = GameState(
        deck=[], 
        table=table,
        players=(PlayerState(hand=hand), PlayerState(hand=[])),
        current_player=0
    )
    
    moves = get_valid_moves(state)
    print(f"\nValid Moves ({len(moves)}):")
    
    for move in moves:
        print(f"\n--- Analyzing Move: {move} ---")
        if move.card_played.value == 8:
            if not move.is_capture:
                print("ERROR: 8s should capture 8c but is flagged as discard!")
            else:
                remaining = [c for c in table if c not in move.cards_captured]
                rem_sum = sum(c.value for c in remaining)
                print(f"Remaining table: {remaining} (Sum: {rem_sum})")
                prob = bot.memory.scopa_probability(remaining, 3)
                print(f"Scopa Probability for sum {rem_sum}: {prob}")
                
        # Helper args
        phase = get_game_phase(state)
        style = "perfect"
        advantage = {"advantage": 0, "cards_diff": 0, "denari_diff": 0, "sevens_diff": 0}

        # Score the move
        # Correct Signature: score_move(state, move, memory, advantage, style, phase)
        score, reasons = score_move(state, move, bot.memory, advantage, style, phase)
        print(f"Score: {score}")
        print(f"Reasons: {reasons}")

if __name__ == "__main__":
    recreate_scenario()
