"""
Test: Does knowing the dealer provide real advantage?

Compares bot performance with:
1. dealer="unknown" (never knows)
2. dealer=correct ("me"/"opp" alternating)

Runs 500 games each and compares win rates.
"""

import sys
import random
from typing import Tuple

from scopa_core import (
    GameState, PlayerState, Card, Suit,
    get_valid_moves, apply_move, create_deck, calculate_scores
)
from scopa_ai import ScopaBot, CardMemory

# Simple opponent that plays reasonably
def simple_opponent_move(state: GameState):
    """Simple opponent: prefers captures, avoids discarding denari."""
    moves = get_valid_moves(state)
    if not moves:
        return None
    
    # Prefer captures
    captures = [m for m in moves if m.is_capture]
    if captures:
        # Prefer settebello, then scope, then denari
        for c in captures:
            if any(card.is_settebello for card in c.cards_captured):
                return c
        for c in captures:
            if c.is_scopa:
                return c
        denari_caps = [c for c in captures if any(card.is_denaro for card in c.cards_captured)]
        if denari_caps:
            return max(denari_caps, key=lambda m: len(m.cards_captured))
        return max(captures, key=lambda m: len(m.cards_captured))
    
    # Discard: avoid denari
    discards = moves  # all discards
    non_denari = [m for m in discards if not m.card_played.is_denaro]
    if non_denari:
        return random.choice(non_denari)
    return random.choice(discards)


def simulate_game(bot: ScopaBot, dealer_mode: str, bot_is_dealer: bool) -> Tuple[int, int]:
    """
    Simulate one game.
    
    dealer_mode: "unknown" or "correct"
    bot_is_dealer: True if bot deals (plays second)
    
    Returns: (bot_total, opp_total)
    """
    deck = create_deck()
    random.shuffle(deck)
    
    # Deal initial cards
    p0_hand = [deck.pop() for _ in range(3)]
    p1_hand = [deck.pop() for _ in range(3)]
    table = [deck.pop() for _ in range(4)]
    
    state = GameState(
        deck=deck,
        table=table,
        players=(
            PlayerState(hand=p0_hand),
            PlayerState(hand=p1_hand)
        ),
        current_player=0,  # Always player 0 starts
        last_capturer=None
    )
    
    # Bot is player 0 if NOT dealer (first mover), else player 1
    bot_player = 1 if bot_is_dealer else 0
    
    # Determine dealer string for bot
    if dealer_mode == "unknown":
        dealer_str = "unknown"
    else:
        dealer_str = "me" if bot_is_dealer else "opp"
    
    # Reset bot memory
    bot.memory = CardMemory()
    
    # Play game
    while True:
        current = state.current_player
        moves = get_valid_moves(state)
        
        if not moves:
            # Check if need to deal more cards
            if state.deck and not state.players[0].hand and not state.players[1].hand:
                # Deal new hands
                for i in range(2):
                    for _ in range(3):
                        if state.deck:
                            state.players[i].hand.append(state.deck.pop())
                continue
            else:
                # Game over
                break
        
        # Choose move
        if current == bot_player:
            # Bot's turn
            bot.memory.update(state, bot_player)
            move = bot.choose_move(
                state,
                use_monte_carlo=True,
                mc_simulations=50,
                match_score=(0, 0),
                dealer=dealer_str
            )
        else:
            # Opponent's turn
            move = simple_opponent_move(state)
        
        if move:
            state = apply_move(state, move)
    
    # Assign remaining table cards
    if state.table and state.last_capturer is not None:
        state.players[state.last_capturer].captured.extend(state.table)
        state.table.clear()
    
    # Calculate scores
    scores = calculate_scores(state)
    bot_score = scores[bot_player].total
    opp_score = scores[1 - bot_player].total
    
    return bot_score, opp_score


def run_test(num_games: int = 500):
    """Run comparison test."""
    print("=" * 60)
    print("DEALER KNOWLEDGE TEST")
    print(f"Running {num_games} games per mode...")
    print("=" * 60)
    
    # Test 1: Unknown dealer
    print("\n[TEST 1] dealer='unknown' (no knowledge)")
    bot_unknown = ScopaBot()
    wins_unknown = 0
    total_margin_unknown = 0
    
    for i in range(num_games):
        if (i + 1) % 100 == 0:
            print(f"  Progress: {i+1}/{num_games}")
        
        bot_is_dealer = (i % 2 == 0)  # Alternate
        bot_pts, opp_pts = simulate_game(bot_unknown, "unknown", bot_is_dealer)
        
        if bot_pts > opp_pts:
            wins_unknown += 1
        total_margin_unknown += (bot_pts - opp_pts)
    
    win_rate_unknown = wins_unknown / num_games * 100
    avg_margin_unknown = total_margin_unknown / num_games
    
    print(f"  Win rate: {win_rate_unknown:.1f}%")
    print(f"  Avg margin: {avg_margin_unknown:.2f}")
    
    # Test 2: Known dealer
    print("\n[TEST 2] dealer='me'/'opp' (correct knowledge)")
    bot_known = ScopaBot()
    wins_known = 0
    total_margin_known = 0
    
    for i in range(num_games):
        if (i + 1) % 100 == 0:
            print(f"  Progress: {i+1}/{num_games}")
        
        bot_is_dealer = (i % 2 == 0)  # Alternate
        bot_pts, opp_pts = simulate_game(bot_known, "correct", bot_is_dealer)
        
        if bot_pts > opp_pts:
            wins_known += 1
        total_margin_known += (bot_pts - opp_pts)
    
    win_rate_known = wins_known / num_games * 100
    avg_margin_known = total_margin_known / num_games
    
    print(f"  Win rate: {win_rate_known:.1f}%")
    print(f"  Avg margin: {avg_margin_known:.2f}")
    
    # Compare
    print("\n" + "=" * 60)
    print("RESULTS COMPARISON")
    print("=" * 60)
    print(f"{'Mode':<20} {'Win Rate':<15} {'Avg Margin'}")
    print("-" * 50)
    print(f"{'Unknown':<20} {win_rate_unknown:.1f}%{'':<10} {avg_margin_unknown:.2f}")
    print(f"{'Known':<20} {win_rate_known:.1f}%{'':<10} {avg_margin_known:.2f}")
    print("-" * 50)
    
    diff = win_rate_known - win_rate_unknown
    if diff > 0.5:
        print(f"\n✅ DEALER KNOWLEDGE HELPS: +{diff:.1f}% win rate")
        print("   Recommendation: IMPLEMENT dealer detection")
    elif diff < -0.5:
        print(f"\n❌ DEALER KNOWLEDGE HURTS: {diff:.1f}% win rate")
        print("   Recommendation: SKIP dealer detection (may indicate bug)")
    else:
        print(f"\n⚪ NO SIGNIFICANT DIFFERENCE: {diff:.1f}%")
        print("   Recommendation: LOW PRIORITY (optional feature)")
    
    return diff


if __name__ == "__main__":
    games = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    run_test(games)
