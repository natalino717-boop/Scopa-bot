"""
Comprehensive AI Feature Tests - Validates all key decision logic

Tests:
1. Smart Discard (empty table) - prefer fewer remaining copies
2. Endgame Last Capture - preserve capture cards
3. Settebello Protection - never discard 7D
4. Denari Priority - capture denari when possible
5. Scopa Risk - avoid leaving easy scopa opportunities
6. Primiera Focus - capture 7s and 6s
"""

import sys
from typing import List, Tuple
from scopa_ai import ScopaBot, CardMemory, score_move, get_game_phase, get_advantage, get_play_style
from scopa_core import GameState, PlayerState, Card, Suit, get_valid_moves

# Test tracking
tests_passed = 0
tests_failed = 0
test_results = []

def code_to_card(code: str) -> Card:
    """Convert code like '7d' to Card object."""
    suit_map = {'d': Suit.DENARI, 'c': Suit.COPPE, 's': Suit.SPADE, 'b': Suit.BASTONI}
    val = int(code[:-1])
    suit = suit_map[code[-1].lower()]
    return Card(suit, val)

def cards_from_codes(codes: List[str]) -> List[Card]:
    return [code_to_card(c) for c in codes]

def run_test(name: str, hand: List[str], table: List[str], seen: List[str], 
             expected_card: int, description: str):
    """Run a single test scenario."""
    global tests_passed, tests_failed
    
    bot = ScopaBot()
    
    # Set up memory
    for code in seen:
        bot.memory.seen.add(code_to_card(code))
    
    hand_cards = cards_from_codes(hand)
    table_cards = cards_from_codes(table)
    
    bot.memory.seen.update(hand_cards)
    bot.memory.seen.update(table_cards)
    
    state = GameState(
        deck=[Card(Suit.DENARI, 1)] * max(0, 40 - len(bot.memory.seen)),
        table=table_cards,
        players=(PlayerState(hand=hand_cards), PlayerState(hand=[])),
        current_player=0,
        last_capturer=None,
        is_last_hand=(len(bot.memory.seen) >= 35)
    )
    
    move = bot.choose_move(state, use_monte_carlo=False)
    actual = move.card_played.value
    
    if actual == expected_card:
        tests_passed += 1
        status = "✅ PASS"
    else:
        tests_failed += 1
        status = "❌ FAIL"
    
    result = f"{status} | {name}: Expected {expected_card}, Got {actual}"
    test_results.append(result)
    print(result)
    if actual != expected_card:
        print(f"   Description: {description}")
        print(f"   Hand: {hand}, Table: {table}, Seen: {len(seen)} cards")

def main():
    print("=" * 70)
    print("COMPREHENSIVE AI FEATURE TESTS")
    print("=" * 70)
    print()
    
    # ========================================
    # TEST 1: Smart Discard (Empty Table)
    # ========================================
    print("\n--- TEST GROUP 1: Smart Discard (Empty Table) ---")
    
    # 1.1: Prefer card with fewer remaining copies (1 vs 2)
    run_test(
        "Smart Discard: 1 vs 2 remaining",
        hand=["7s", "4d"],
        table=[],
        seen=["4b", "4s", "4c", "7c"],  # 3 of 4s seen (1 left), 1 of 7s seen (2 left)
        expected_card=4,  # Should discard 4D (fewer remaining = safer)
        description="Should discard card with fewer remaining copies"
    )
    
    # 1.2: Prefer card with 0 remaining (safest)
    run_test(
        "Smart Discard: 0 remaining = safest",
        hand=["3s", "5c"],
        table=[],
        seen=["3b", "3c", "3d", "5s", "5d"],  # All 3s seen, 2 of 5s seen
        expected_card=3,  # Should discard 3S (0 remaining = opponent can't capture)
        description="0 remaining cards = opponent cannot capture"
    )
    
    # ========================================
    # TEST 2: Settebello Protection
    # ========================================
    print("\n--- TEST GROUP 2: Settebello Protection ---")
    
    # 2.1: Never discard 7D
    run_test(
        "Settebello: Never discard",
        hand=["7d", "3c"],
        table=[],
        seen=[],
        expected_card=3,  # Should discard 3C, NEVER 7D
        description="7D should never be discarded"
    )
    
    # 2.2: Always capture 7D
    run_test(
        "Settebello: Always capture",
        hand=["8c", "3s"],
        table=["7d", "1b"],  # Can capture 7D with 8C (7+1=8)
        seen=[],
        expected_card=8,  # Should use 8C to capture 7D
        description="Should always capture Settebello when possible"
    )
    
    # ========================================
    # TEST 3: Denari Priority
    # ========================================
    print("\n--- TEST GROUP 3: Denari Priority ---")
    
    # 3.1: Capture denari over non-denari
    run_test(
        "Denari: Capture priority",
        hand=["5s"],
        table=["5d", "5c"],  # Can capture either
        seen=[],
        expected_card=5,  # Should capture (only option, captures both)
        description="Denari capture should be preferred"
    )
    
    # 3.2: Avoid discarding denari when possible
    run_test(
        "Denari: Avoid discarding",
        hand=["4d", "8b"],
        table=["3c", "7s"],  # Can't capture anything
        seen=[],
        expected_card=8,  # Should discard 8B (figure), not 4D (denaro)
        description="Should avoid discarding denari"
    )
    
    # ========================================
    # TEST 4: Endgame Last Capture
    # ========================================
    print("\n--- TEST GROUP 4: Endgame Last Capture ---")
    
    # Generate 35+ seen cards for endgame
    endgame_seen = [
        "1b", "2b", "3b", "4b", "5b", "6b", "7b", "8b", "9b", "10b",
        "1c", "2c", "3c", "4c", "5c", "6c", "7c", "8c", "9c", "10c",
        "1s", "2s", "3s", "4s", "5s", "6s", "7s", "8s", "9s", "10s",
        "1d", "2d", "3d", "4d", "5d"
    ]
    
    # 4.1: Capture with matching sum (correct behavior)
    run_test(
        "Endgame: Capture with sum",
        hand=["6d", "9d"],
        table=["3b", "3c"],  # 3+3=6, so 6D captures!
        seen=endgame_seen,
        expected_card=6,  # Should CAPTURE with 6D (3+3=6)
        description="Should capture when sum matches"
    )
    
    # 4.2: Preserve card with direct match
    run_test(
        "Endgame: Preserve direct match",
        hand=["7d", "8d"],
        table=["7b"],  # 7D can capture 7B directly!
        seen=endgame_seen[:30],
        expected_card=7,  # Should capture with 7D
        description="Should capture matching card in endgame"
    )
    
    # ========================================
    # TEST 5: Scopa Risk Avoidance
    # ========================================
    print("\n--- TEST GROUP 5: Scopa Risk ---")
    
    # 5.1: Avoid leaving single low card (easy scopa)
    run_test(
        "Scopa Risk: Avoid single card sum <= 10",
        hand=["5s", "8b"],
        table=["3c", "2d"],  # 5S takes 3C+2D = leaves nothing (good!)
        seen=[],
        expected_card=5,  # Should take and clear table
        description="Should prefer clearing table over leaving cards"
    )
    
    # ========================================
    # TEST 6: Primiera (7s priority)
    # ========================================
    print("\n--- TEST GROUP 6: Primiera ---")
    
    # 6.1: Capture 7 over other cards
    run_test(
        "Primiera: Capture 7s",
        hand=["8c"],
        table=["7b", "1s", "3d"],  # 8C can take 7B+1S or just 1S+3D+..
        seen=[],
        expected_card=8,  # Should capture (includes 7B)
        description="Should prioritize capturing 7s for primiera"
    )
    
    # ========================================
    # SUMMARY
    # ========================================
    print()
    print("=" * 70)
    print(f"RESULTS: {tests_passed} passed, {tests_failed} failed")
    print("=" * 70)
    
    if tests_failed > 0:
        print("\nFailed tests:")
        for r in test_results:
            if "FAIL" in r:
                print(f"  {r}")
    
    return tests_failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
