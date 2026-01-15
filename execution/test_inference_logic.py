from scopa_ai import ScopaBot
from scopa_core import GameState, PlayerState, Card, Suit

def test_inference():
    print("=== TEST NEGATIVE INFERENCE ===")
    
    bot = ScopaBot()
    
    # Setup state
    # Table has 7D (Settebello) and 2C
    table = [Card(Suit.DENARI, 7), Card(Suit.COPPE, 2)]
    
    # Bot hand (irrelevant for opponent inference but needed for state)
    my_hand = [Card(Suit.BASTONI, 1)]
    
    state = GameState(
        deck=[],
        table=table,
        players=(
            PlayerState(hand=my_hand, captured=[]),
            PlayerState(hand=[], captured=[]) # Opponent
        ),
        current_player=0
    )
    
    # Scenario: Opponent discarded 5B.
    # If they had a 7, they would have taken 7D (Settebello!).
    # If they had a 2, they would have taken 2C.
    last_action = "Opponent Discard (5b)"
    
    print(f"Table: {table}")
    print(f"Action: {last_action}")
    
    # Trigger inference
    bot._update_memory_and_inference(state, last_action)
    
    # Check impossible cards
    impossible = bot.memory.impossible_cards
    print(f"\nImpossible Cards Count: {len(impossible)}")
    
    # Verify specific cards
    check_cards = [
        Card(Suit.COPPE, 7), # Should be impossible (missed 7D)
        Card(Suit.SPADE, 7), # Should be impossible
        Card(Suit.BASTONI, 7), # Should be impossible
        Card(Suit.DENARI, 2), # Should be impossible (missed 2C)
        Card(Suit.SPADE, 10) # Should NOT be impossible (Re doesn't match 7 or 2)
    ]
    
    for c in check_cards:
        is_imp = c in impossible
        status = "IMPOSSIBLE (OK)" if is_imp else "POSSIBLE"
        if c.value == 10 and not is_imp: status = "POSSIBLE (OK)"
        print(f"Card {c}: {status}") 

if __name__ == "__main__":
    test_inference()
