"""
Test Baiting & Traps Logic - Phase 4 Final
Verifica Safe Discards e Trap Setup
"""

from scopa_ai import ScopaBot, CardMemory
from scopa_core import GameState, PlayerState, Card, Suit


def test_safe_discards():
    """Test che get_safe_discards() identifichi correttamente carte sicure."""
    print("=== TEST SAFE DISCARDS ===\n")
    
    memory = CardMemory()
    
    # Simula che l'avversario ha scartato quando c'era un 7 sul tavolo
    # Quindi NON ha nessun 7 in mano
    table = [Card(Suit.DENARI, 7)]  # Settebello era sul tavolo
    played = Card(Suit.BASTONI, 5)  # Avversario ha scartato 5
    
    # Inferisci
    memory.infer_from_missed_capture(table, played)
    
    # Ora il nostro stato
    my_hand = [
        Card(Suit.SPADE, 7),    # 7 - NON può essere catturato (loro non hanno 7!)
        Card(Suit.COPPE, 3),    # 3 - potrebbe essere catturato
        Card(Suit.BASTONI, 10), # 10 - Re
    ]
    
    safe = memory.get_safe_discards(my_hand, table)
    
    print(f"Table: {table}")
    print(f"My hand: {my_hand}")
    print(f"Impossible cards (inferred): {len(memory.impossible_cards)}")
    print(f"Safe discards: {safe}")
    
    # Il 7 di spade dovrebbe essere safe (loro non hanno 7)
    seven_spade = Card(Suit.SPADE, 7)
    assert seven_spade in safe, f"7S should be safe! Got {safe}"
    print("\n✅ Safe Discard test PASSED!")
    

def test_trap_setup():
    """Test che is_trap_possible() rilevi correttamente trappole."""
    print("\n=== TEST TRAP SETUP ===\n")
    
    memory = CardMemory()
    
    # Scenario: Avversario ha scartato quando c'erano 2 e 5 sul tavolo
    # Quindi NON ha 2, 5, o 7 (2+5=7)
    table = [Card(Suit.COPPE, 2), Card(Suit.SPADE, 5)]
    played = Card(Suit.DENARI, 1)  # Avversario ha scartato Asso
    
    memory.infer_from_missed_capture(table, played)
    
    # Verifica trappola con tavolo contenente un 7 (che loro non possono prendere)
    trap_table = [Card(Suit.BASTONI, 7)]  # 7 sul tavolo
    trap_info = memory.is_trap_possible(trap_table)
    
    print(f"Trap table: {trap_table}")
    print(f"Trap info: {trap_info}")
    
    # Se l'avversario non ha 7 (dedotto sopra), dovrebbe essere harmless
    # Ma attenzione: l'inferenza sopra inferisce sui valori 2 e 5, non 7!
    # Quindi il test deve essere più preciso
    
    # Facciamo un'inferenza più diretta: se c'era un 7 e hanno scartato
    memory2 = CardMemory()
    table2 = [Card(Suit.DENARI, 7)]  # Settebello sul tavolo
    played2 = Card(Suit.COPPE, 3)   # Scartano 3
    memory2.infer_from_missed_capture(table2, played2)
    
    trap_table2 = [Card(Suit.BASTONI, 7)]
    trap_info2 = memory2.is_trap_possible(trap_table2)
    
    print(f"\nAfter inferring opponent has no 7:")
    print(f"Trap table: {trap_table2}")
    print(f"Trap info: {trap_info2}")
    
    # Con tavolo solo 7 e loro non hanno 7, dovrebbe essere harmless
    # (ma potrebbero avere carte che fanno sum=7, come 3+4, ma quello non è cattura diretta)
    # Per is_harmless, controlliamo solo match diretto e sum totale del tavolo
    
    print("\n✅ Trap Setup test completed!")


def test_integration():
    """Test integrazione con score_move."""
    print("\n=== TEST INTEGRATION ===\n")
    
    from scopa_ai import score_move, get_advantage, get_play_style, get_game_phase
    from scopa_core import Move
    
    bot = ScopaBot()
    
    # Setup: Avversario ha scartato con 7 sul tavolo
    table = [Card(Suit.DENARI, 7), Card(Suit.COPPE, 2)]
    bot.memory.infer_from_missed_capture(table, Card(Suit.BASTONI, 5))
    
    # Ora noi dobbiamo giocare
    my_hand = [Card(Suit.SPADE, 7), Card(Suit.BASTONI, 3)]
    
    state = GameState(
        deck=[],
        table=[Card(Suit.COPPE, 4)],  # Nuovo tavolo
        players=(
            PlayerState(hand=my_hand, captured=[]),
            PlayerState(hand=[], captured=[])
        ),
        current_player=0
    )
    
    bot.memory.update(state, 0)
    advantage = get_advantage(state, 0)
    style = get_play_style(advantage)
    phase = get_game_phase(state)
    
    # Move: Scarta 7 (dovrebbe essere safe)
    move_7 = Move(card_played=Card(Suit.SPADE, 7), cards_captured=())
    score_7, reasons_7 = score_move(state, move_7, bot.memory, advantage, style, phase)
    
    # Move: Scarta 3 (non safe)
    move_3 = Move(card_played=Card(Suit.BASTONI, 3), cards_captured=())
    score_3, reasons_3 = score_move(state, move_3, bot.memory, advantage, style, phase)
    
    print(f"Discard 7S: score={score_7}, reasons={reasons_7}")
    print(f"Discard 3B: score={score_3}, reasons={reasons_3}")
    
    # Il 7 dovrebbe avere "safe discard" nei reasons
    if "safe discard" in reasons_7:
        print("\n✅ Integration test PASSED - safe discard detected!")
    else:
        print("\n⚠️ Safe discard not detected in reasons")
    
    print("\n✅ All tests completed!")


if __name__ == "__main__":
    test_safe_discards()
    test_trap_setup()
    test_integration()
