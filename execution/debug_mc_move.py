from scopa_core import GameState, PlayerState, Card, Suit, get_valid_moves, Move
from scopa_ai import ScopaBot, monte_carlo_evaluate, smart_playout_move
import random

def make_card(code):
    suits = {'b': Suit.BASTONI, 'c': Suit.COPPE, 'd': Suit.DENARI, 's': Suit.SPADE}
    return Card(suits[code[-1]], int(code[:-1]))

def debug_scenario():
    print("=== DEBUG SCENARIO (Turn 17) ===")
    
    # Setup State
    hand = [make_card("2d"), make_card("4b")]
    table = [make_card("4c"), make_card("5b"), make_card("6s"), make_card("7b"), make_card("9d")]
    
    # Create Deck (exclude hand & table)
    full_deck = []
    used = set(hand + table)
    for s in Suit:
        for v in range(1, 11):
            c = Card(s, v)
            if c not in used:
                full_deck.append(c)
    
    # Opponent hand? We don't know size exactly but late game.
    # Turn 17 means 16 moves done -> 8 each.
    # Total 40 cards. Let's assume typical late game.
    
    state = GameState(
        deck=full_deck, # Will be shuffled in MC
        table=table,
        players=[
            PlayerState(hand=hand, captured=[], scope=0),
            PlayerState(hand=[], captured=[], scope=0) 
        ],
        current_player=0
    )
    
    moves = get_valid_moves(state)
    print(f"\nValid Moves ({len(moves)}):")
    for m in moves:
        print(f" - {m}")
        
    print("\n--- Running Monte Carlo (100 sims) ---")
    bot = ScopaBot()
    # Force memory update to exclude visible cards
    bot.memory.seen = set(hand + table)
    
    for move in moves:
        win_rate = monte_carlo_evaluate(state, move, 0, simulations=100)
        print(f"Move: {move} -> Win Rate: {win_rate:.4f}")
        
    print("\n--- Smart Playout Logic Check ---")
    # Simulate one playout step
    print("Checking if smart_playout_move prefers capture...")
    selected = smart_playout_move(state, moves)
    print(f"Smart Playout chooses: {selected}")

if __name__ == "__main__":
    debug_scenario()
