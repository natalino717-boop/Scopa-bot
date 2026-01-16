"""
Scopa Core Engine - Logica di gioco completa

Questo modulo implementa:
- Strutture dati per carte, mazzo, stato di gioco
- Logica di presa (singola e somma)
- Calcolo punteggio (carte, denari, settebello, primiera, scope)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Set, Tuple, Optional
from itertools import combinations
import random


class Suit(Enum):
    """Semi delle carte italiane"""
    DENARI = "denari"
    COPPE = "coppe"
    SPADE = "spade"
    BASTONI = "bastoni"


# Valori Primiera per ogni valore carta
PRIMIERA_VALUES = {
    7: 21,
    6: 18,
    1: 16,  # Asso
    5: 15,
    4: 14,
    3: 13,
    2: 12,
    8: 10,  # Fante
    9: 10,  # Cavallo
    10: 10  # Re
}


@dataclass(frozen=True)
class Card:
    """Rappresenta una carta del mazzo italiano"""
    suit: Suit
    value: int  # 1-10 (1=Asso, 8=Fante, 9=Cavallo, 10=Re)
    
    @property
    def primiera_value(self) -> int:
        """Valore della carta per il calcolo della Primiera"""
        return PRIMIERA_VALUES[self.value]
    
    @property
    def is_settebello(self) -> bool:
        """True se è il 7 di denari"""
        return self.suit == Suit.DENARI and self.value == 7
    
    @property
    def is_denaro(self) -> bool:
        """True se è una carta di denari"""
        return self.suit == Suit.DENARI
    
    def __repr__(self) -> str:
        names = {1: "A", 8: "F", 9: "C", 10: "R"}
        val = names.get(self.value, str(self.value))
        suit_names = {"denari": "D", "coppe": "C", "spade": "S", "bastoni": "B"}
        return f"{val}{suit_names[self.suit.value]}"


def create_deck() -> List[Card]:
    """Crea un mazzo italiano completo di 40 carte"""
    deck = []
    for suit in Suit:
        for value in range(1, 11):
            deck.append(Card(suit, value))
    return deck


@dataclass
class Move:
    """Rappresenta una mossa possibile"""
    card_played: Card
    cards_captured: Tuple[Card, ...]  # Tuple vuota se si scarta
    is_scopa: bool = False
    
    @property
    def is_capture(self) -> bool:
        return len(self.cards_captured) > 0
    
    def __repr__(self) -> str:
        if self.is_capture:
            captured = ", ".join(str(c) for c in self.cards_captured)
            scopa_str = " SCOPA!" if self.is_scopa else ""
            return f"Gioca {self.card_played} → prende [{captured}]{scopa_str}"
        return f"Gioca {self.card_played} → scarta"


@dataclass
class PlayerState:
    """Stato di un giocatore"""
    hand: List[Card] = field(default_factory=list)
    captured: List[Card] = field(default_factory=list)
    scope: int = 0
    
    def add_captured(self, cards: List[Card], is_scopa: bool = False):
        """Aggiunge carte catturate"""
        self.captured.extend(cards)
        if is_scopa:
            self.scope += 1


@dataclass
class GameState:
    """Stato completo di una partita di Scopa"""
    deck: List[Card] = field(default_factory=list)
    table: List[Card] = field(default_factory=list)
    players: Tuple[PlayerState, PlayerState] = field(
        default_factory=lambda: (PlayerState(), PlayerState())
    )
    current_player: int = 0  # 0 o 1
    last_capturer: Optional[int] = None
    is_last_hand: bool = False  # True se è l'ultima mano
    
    @property
    def current(self) -> PlayerState:
        """Giocatore di turno"""
        return self.players[self.current_player]
    
    @property
    def opponent(self) -> PlayerState:
        """Avversario"""
        return self.players[1 - self.current_player]
    
    def switch_player(self):
        """Passa il turno"""
        self.current_player = 1 - self.current_player


def get_all_capture_combinations(table: List[Card], card_value: int) -> List[Tuple[Card, ...]]:
    """
    Trova tutte le combinazioni di carte sul tavolo che sommano al valore dato.
    Ritorna lista di tuple di carte catturabili.
    
    Regola: se c'è una carta singola uguale, DEVE prendere quella.
    """
    captures = []
    
    # Prima controlla carte singole uguali
    single_matches = [c for c in table if c.value == card_value]
    if single_matches:
        # Se c'è match singolo, può prendere SOLO carte singole
        return [(c,) for c in single_matches]
    
    # Altrimenti cerca combinazioni che sommano al valore
    for r in range(2, len(table) + 1):
        for combo in combinations(table, r):
            if sum(c.value for c in combo) == card_value:
                captures.append(combo)
    
    return captures


def get_valid_moves(state: GameState) -> List[Move]:
    """
    Genera tutte le mosse valide per il giocatore di turno.
    """
    moves = []
    hand = state.current.hand
    table = state.table
    
    for card in hand:
        captures = get_all_capture_combinations(table, card.value)
        
        if captures:
            # Per ogni possibile presa
            for captured in captures:
                remaining = len(table) - len(captured)
                is_scopa = (remaining == 0) and not state.is_last_hand
                moves.append(Move(card, captured, is_scopa))
        else:
            # Nessuna presa possibile: scarta
            moves.append(Move(card, tuple()))
    
    return moves


def apply_move(state: GameState, move: Move) -> GameState:
    """
    Applica una mossa e ritorna il nuovo stato.
    Non modifica lo stato originale (immutabile).
    """
    # Copia profonda dello stato
    new_deck = state.deck.copy()
    new_table = state.table.copy()
    new_players = (
        PlayerState(
            hand=state.players[0].hand.copy(),
            captured=state.players[0].captured.copy(),
            scope=state.players[0].scope
        ),
        PlayerState(
            hand=state.players[1].hand.copy(),
            captured=state.players[1].captured.copy(),
            scope=state.players[1].scope
        )
    )
    
    new_state = GameState(
        deck=new_deck,
        table=new_table,
        players=new_players,
        current_player=state.current_player,
        last_capturer=state.last_capturer,
        is_last_hand=state.is_last_hand
    )
    
    # Rimuovi carta dalla mano
    new_state.current.hand.remove(move.card_played)
    
    if move.is_capture:
        # Cattura le carte
        captured_list = list(move.cards_captured) + [move.card_played]
        new_state.current.add_captured(captured_list, move.is_scopa)
        
        # Rimuovi carte dal tavolo
        for card in move.cards_captured:
            new_state.table.remove(card)
        
        new_state.last_capturer = new_state.current_player
    else:
        # Scarta sul tavolo
        new_state.table.append(move.card_played)
    
    # Passa il turno
    new_state.switch_player()
    
    return new_state


def deal_cards(state: GameState, cards_per_player: int = 3) -> GameState:
    """
    Distribuisce carte ai giocatori dal mazzo.
    """
    new_state = GameState(
        deck=state.deck.copy(),
        table=state.table.copy(),
        players=(
            PlayerState(
                hand=state.players[0].hand.copy(),
                captured=state.players[0].captured.copy(),
                scope=state.players[0].scope
            ),
            PlayerState(
                hand=state.players[1].hand.copy(),
                captured=state.players[1].captured.copy(),
                scope=state.players[1].scope
            )
        ),
        current_player=state.current_player,
        last_capturer=state.last_capturer,
        is_last_hand=state.is_last_hand
    )
    
    for _ in range(cards_per_player):
        for player in new_state.players:
            if new_state.deck:
                player.hand.append(new_state.deck.pop())
    
    # Controlla se questa è l'ultima mano
    if not new_state.deck:
        new_state.is_last_hand = True
    
    return new_state


def initialize_game(shuffle: bool = True, _retry_count: int = 0) -> GameState:
    """
    Inizializza una nuova partita.
    """
    MAX_RETRIES = 10  # Prevent infinite recursion

    deck = create_deck()
    if shuffle:
        random.shuffle(deck)

    state = GameState(deck=deck)

    # Metti 4 carte sul tavolo
    state.table = [state.deck.pop() for _ in range(4)]

    # Controlla regola: se ci sono 3+ Re, rimescola
    kings = sum(1 for c in state.table if c.value == 10)
    if kings >= 3:
        if _retry_count >= MAX_RETRIES:
            # Accept the hand anyway after max retries (extremely rare)
            pass
        else:
            return initialize_game(shuffle=True, _retry_count=_retry_count + 1)

    # Distribuisci 3 carte a testa
    state = deal_cards(state, 3)

    return state


@dataclass
class Score:
    """Punteggio di un giocatore a fine partita"""
    cards: int = 0           # 1 se ha più carte
    denari: int = 0          # 1 se ha più denari
    settebello: int = 0      # 1 se ha il settebello
    primiera: int = 0        # 1 se ha primiera migliore
    scope: int = 0           # numero di scope
    
    @property
    def total(self) -> int:
        return self.cards + self.denari + self.settebello + self.primiera + self.scope
    
    def __repr__(self) -> str:
        parts = []
        if self.cards: parts.append("Carte")
        if self.denari: parts.append("Denari")
        if self.settebello: parts.append("Settebello")
        if self.primiera: parts.append("Primiera")
        if self.scope: parts.append(f"Scope x{self.scope}")
        return f"[{self.total}] " + ", ".join(parts) if parts else "[0]"


def calculate_primiera(captured: List[Card]) -> int:
    """
    Calcola il valore primiera per le carte catturate.
    Ritorna -1 se manca almeno un seme.
    """
    best_per_suit = {}
    for card in captured:
        suit = card.suit
        if suit not in best_per_suit or card.primiera_value > best_per_suit[suit]:
            best_per_suit[suit] = card.primiera_value
    
    # Deve avere almeno una carta per seme
    if len(best_per_suit) < 4:
        return -1
    
    return sum(best_per_suit.values())


def calculate_scores(state: GameState) -> Tuple[Score, Score]:
    """
    Calcola i punteggi finali per entrambi i giocatori.
    Note: This function is read-only and does not mutate the original state.
    """
    # Create copies to avoid mutating original state
    p0_captured = state.players[0].captured.copy()
    p1_captured = state.players[1].captured.copy()
    remaining_table = state.table.copy()

    # Assegna carte rimaste sul tavolo all'ultimo che ha catturato
    if state.last_capturer is not None and remaining_table:
        if state.last_capturer == 0:
            p0_captured.extend(remaining_table)
        else:
            p1_captured.extend(remaining_table)
        remaining_table.clear()
    
    p0, p1 = state.players
    s0, s1 = Score(), Score()

    # Scope
    s0.scope = p0.scope
    s1.scope = p1.scope

    # Carte (use copies that include remaining table cards)
    c0, c1 = len(p0_captured), len(p1_captured)
    if c0 > c1:
        s0.cards = 1
    elif c1 > c0:
        s1.cards = 1

    # Denari (use copies)
    d0 = sum(1 for c in p0_captured if c.is_denaro)
    d1 = sum(1 for c in p1_captured if c.is_denaro)
    if d0 > d1:
        s0.denari = 1
    elif d1 > d0:
        s1.denari = 1

    # Settebello (use copies)
    for c in p0_captured:
        if c.is_settebello:
            s0.settebello = 1
            break
    for c in p1_captured:
        if c.is_settebello:
            s1.settebello = 1
            break

    # Primiera (use copies)
    pr0 = calculate_primiera(p0_captured)
    pr1 = calculate_primiera(p1_captured)
    if pr0 > pr1:
        s0.primiera = 1
    elif pr1 > pr0:
        s1.primiera = 1
    
    return s0, s1


def is_game_over(state: GameState) -> bool:
    """
    Verifica se la partita è terminata.
    """
    return (
        not state.deck and
        not state.players[0].hand and
        not state.players[1].hand
    )


# === TEST RAPIDO ===
if __name__ == "__main__":
    print("=== Test Scopa Core ===\n")
    
    # Test creazione mazzo
    deck = create_deck()
    print(f"Mazzo creato: {len(deck)} carte")
    assert len(deck) == 40, "Il mazzo deve avere 40 carte"
    
    # Test valori primiera
    sette_denari = Card(Suit.DENARI, 7)
    print(f"\nSettebello: {sette_denari}")
    print(f"  - is_settebello: {sette_denari.is_settebello}")
    print(f"  - primiera_value: {sette_denari.primiera_value}")
    assert sette_denari.is_settebello
    assert sette_denari.primiera_value == 21
    
    # Test inizializzazione partita
    state = initialize_game()
    print(f"\nPartita inizializzata:")
    print(f"  - Tavolo: {state.table}")
    print(f"  - Mano P0: {state.players[0].hand}")
    print(f"  - Mano P1: {state.players[1].hand}")
    print(f"  - Carte restanti nel mazzo: {len(state.deck)}")
    
    # Test mosse valide
    moves = get_valid_moves(state)
    print(f"\nMosse valide per P{state.current_player}: {len(moves)}")
    for m in moves[:5]:
        print(f"  - {m}")
    
    # Test applicazione mossa
    if moves:
        new_state = apply_move(state, moves[0])
        print(f"\nDopo mossa '{moves[0]}':")
        print(f"  - Tavolo: {new_state.table}")
        print(f"  - Turno: P{new_state.current_player}")
    
    print("\n✅ Tutti i test superati!")
