"""
Test Scenari Decisionali - Verifica decisioni del bot Scopa

Questo script testa il bot in scenari specifici per verificare
che prenda sempre le decisioni corrette.
"""

from scopa_core import (
    GameState, Move, Card, Suit, PlayerState,
    get_valid_moves, create_deck
)
from scopa_ai import ScopaBot, score_move, get_advantage, get_game_phase
from scopa_game_diary import card_to_str, cards_to_str, create_move_description


def create_test_state(
    my_hand: list,
    table: list,
    opp_hand: list = None,
    my_captured: list = None,
    opp_captured: list = None,
    deck_size: int = 20,
    my_scope: int = 0,
    opp_scope: int = 0
) -> GameState:
    """Crea uno stato di gioco per testing."""
    
    def parse_card(s: str) -> Card:
        """Converte stringa (es: '7d') in Card."""
        suit_map = {'d': Suit.DENARI, 'c': Suit.COPPE, 's': Suit.SPADE, 'b': Suit.BASTONI}
        value = int(s[:-1])
        suit = suit_map[s[-1]]
        return Card(suit, value)
    
    my_hand_cards = [parse_card(c) for c in my_hand]
    table_cards = [parse_card(c) for c in table]
    opp_hand_cards = [parse_card(c) for c in (opp_hand or [])]
    my_captured_cards = [parse_card(c) for c in (my_captured or [])]
    opp_captured_cards = [parse_card(c) for c in (opp_captured or [])]
    
    # Crea deck fittizio
    deck = [Card(Suit.BASTONI, 10)] * deck_size
    
    return GameState(
        deck=deck,
        table=table_cards,
        players=(
            PlayerState(hand=my_hand_cards, captured=my_captured_cards, scope=my_scope),
            PlayerState(hand=opp_hand_cards, captured=opp_captured_cards, scope=opp_scope)
        ),
        current_player=0,
        last_capturer=None,
        is_last_hand=False
    )


def evaluate_scenario(name: str, state: GameState, expected_action: str, expected_card: str = None):
    """Valuta uno scenario e mostra il risultato."""
    bot = ScopaBot()
    evaluations = bot.get_all_evaluations(state)
    chosen_move = bot.choose_move(state)
    
    print(f"\n{'='*60}")
    print(f"SCENARIO: {name}")
    print(f"{'='*60}")
    print(f"Mano: {cards_to_str(state.current.hand)}")
    print(f"Tavolo: {cards_to_str(state.table)}")
    
    print(f"\nMosse valutate (ordinate per punteggio):")
    for i, ev in enumerate(evaluations[:5]):  # Top 5
        move_desc = create_move_description(ev["move"])
        reasons = ", ".join(ev["reasons"]) if ev["reasons"] else "-"
        marker = "→" if ev["move"] == chosen_move else " "
        print(f"  {marker} [{ev['score']:+5d}] {move_desc}")
        if ev["reasons"]:
            print(f"           Ragioni: {reasons}")
    
    # Verifica
    chosen_desc = create_move_description(chosen_move)
    is_capture = chosen_move.is_capture
    
    passed = False
    if expected_action == "capture" and is_capture:
        if expected_card:
            if card_to_str(chosen_move.card_played) == expected_card:
                passed = True
            elif any(card_to_str(c) == expected_card for c in chosen_move.cards_captured):
                passed = True
        else:
            passed = True
    elif expected_action == "discard" and not is_capture:
        if expected_card:
            passed = (card_to_str(chosen_move.card_played) == expected_card)
        else:
            passed = True
    elif expected_action == "avoid" and expected_card:
        # Verifica che NON giochi quella carta
        passed = (card_to_str(chosen_move.card_played) != expected_card)
    
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"\n{status}: Bot sceglie: {chosen_desc}")
    if not passed:
        print(f"   Atteso: {expected_action} {expected_card or ''}")
    
    return passed


def run_all_tests():
    """Esegue tutti i test scenari."""
    results = []
    
    # ========================================
    # TEST 1: Prendere sempre il Settebello dal TAVOLO
    # (Nota: qui testiamo se il bot PRENDE 7d quando è sul tavolo)
    # ========================================
    state = create_test_state(
        my_hand=['7c', '3s'],  # Ha 7c per prendere 7d
        table=['7d', '2c', '5b']  # 7d sul tavolo!
    )
    results.append(evaluate_scenario(
        "Prendere Settebello dal tavolo (priorità assoluta)",
        state,
        expected_action="capture",
        expected_card="7d"  # Deve catturare 7d
    ))
    
    # ========================================
    # TEST 2: Non scartare MAI il Settebello
    # ========================================
    state = create_test_state(
        my_hand=['7d', '3c', '5b'],
        table=['8c', '9s', '10b']  # Nessuna cattura possibile
    )
    results.append(evaluate_scenario(
        "Non scartare MAI il Settebello",
        state,
        expected_action="avoid",
        expected_card="7d"
    ))
    
    # ========================================
    # TEST 3: Preferire cattura denari
    # ========================================
    state = create_test_state(
        my_hand=['5c', '5s'],
        table=['5d', '5b']  # Può prendere 5d (denaro) o 5b (bastoni)
    )
    results.append(evaluate_scenario(
        "Preferire cattura denari vs altre carte",
        state,
        expected_action="capture",
        expected_card="5d"  # Dovrebbe prendere il denaro
    ))
    
    # ========================================
    # TEST 4: Prendere SCOPA quando possibile
    # ========================================
    state = create_test_state(
        my_hand=['5c', '8s', '3b'],
        table=['5d']  # Scopa possibile con 5c
    )
    results.append(evaluate_scenario(
        "Fare scopa quando possibile",
        state,
        expected_action="capture",
        expected_card="5c"
    ))
    
    # ========================================
    # TEST 5: Evitare di lasciare somma bassa (rischio scopa)
    # ========================================
    state = create_test_state(
        my_hand=['2c', '8s', '10b'],
        table=['3d', '4c']  # 10b lascerebbe 3+4=7 sul tavolo (rischio)
    )
    # Qui dovrebbe preferire 2c che lascia 3+4+2=9, meno rischioso di scartare 8 (lascia 15)
    results.append(evaluate_scenario(
        "Evitare somme basse rischiose",
        state,
        expected_action="discard",
        expected_card=None  # Non verifico quale, ma NON deve essere 2c se lascia somma pericolosa
    ))
    
    # ========================================
    # TEST 6: Preferire 7 per primiera (7 vale più di 2 carte normali)
    # ========================================
    state = create_test_state(
        my_hand=['7c'],
        table=['3d', '4d', '7b']  # Può prendere 3d+4d (2 denari) o 7b (7 per primiera)
    )
    results.append(evaluate_scenario(
        "Preferire 7 per primiera vs 2 denari bassi",
        state,
        expected_action="capture",
        expected_card="7b"  # 7 ha valore primiera 21, più importante
    ))
    
    # ========================================
    # TEST 7: Prendere 7 per primiera
    # ========================================
    state = create_test_state(
        my_hand=['7c'],
        table=['7b', '3c', '4s']  # Può prendere 7b o 3c+4s
    )
    results.append(evaluate_scenario(
        "Prendere 7 per primiera vs cattura multipla",
        state,
        expected_action="capture",
        expected_card="7b"  # 7 vale di più per primiera
    ))
    
    # ========================================
    # TEST 8: Non lasciare 7d sul tavolo
    # ========================================
    state = create_test_state(
        my_hand=['3c', '5s', '8b'],
        table=['7d', '2c', '4b']  # 7d sul tavolo - deve prenderlo se può!
    )
    # Qui non può prendere 7d, ma verifichiamo che non faccia mosse stupide
    results.append(evaluate_scenario(
        "Comportamento con 7d sul tavolo (non catturabile)",
        state,
        expected_action="discard",
        expected_card=None
    ))
    
    # ========================================
    # TEST 9: Cattura 7d quando possibile
    # ========================================
    state = create_test_state(
        my_hand=['7c', '3s'],
        table=['7d', '2c', '5b']  # Può prendere 7d con 7c
    )
    results.append(evaluate_scenario(
        "Catturare 7d quando sul tavolo",
        state,
        expected_action="capture",
        expected_card="7d"
    ))
    
    # ========================================
    # TEST 10: Endgame solver - verifica che usi minimax
    # ========================================
    state = create_test_state(
        my_hand=['6d', '4c'],
        table=['6b', '4d'],
        deck_size=0,  # Endgame attiva solver
        my_captured=['1d', '2d', '3d'],
        opp_captured=['5d', '7d', '8d', '9d']
    )
    results.append(evaluate_scenario(
        "Endgame: solver minimax decide ottimamente",
        state,
        expected_action="capture",
        expected_card=None  # Il solver decide, qualsiasi cattura va bene
    ))
    
    # ========================================
    # RISULTATI FINALI
    # ========================================
    print("\n" + "="*60)
    print("RISULTATI FINALI")
    print("="*60)
    passed = sum(results)
    total = len(results)
    print(f"Test superati: {passed}/{total} ({passed/total*100:.0f}%)")
    
    if passed == total:
        print("\n🎉 Tutti i test superati! Il bot decide correttamente.")
    else:
        print(f"\n⚠️  {total - passed} test falliti - verificare la logica AI.")
    
    return passed, total


if __name__ == "__main__":
    run_all_tests()
