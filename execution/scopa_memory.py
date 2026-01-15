"""
Scopa Memory - Card tracking e inferenza probabilistica

Questo modulo implementa:
- Tracking delle carte viste durante la partita
- Stima delle carte in mano all'avversario
- Probabilità di presa per carte non viste
"""

from typing import List, Set, Dict, Optional
from dataclasses import dataclass, field
from scopa_core import Card, Suit, GameState, create_deck


@dataclass
class CardTracker:
    """
    Tiene traccia di tutte le carte viste durante la partita.
    Permette di inferire quali carte potrebbero essere in mano all'avversario.
    """
    # Carte sicuramente viste (giocate o catturate)
    seen_cards: Set[Card] = field(default_factory=set)
    
    # Carte nella nostra mano
    my_hand: Set[Card] = field(default_factory=set)
    
    # Carte sul tavolo
    table_cards: Set[Card] = field(default_factory=set)
    
    # [NEW] Carte impossibili (che l'avversario sicuramente non ha)
    impossible_cards: Set[Card] = field(default_factory=set)
    
    # Tutte le carte del mazzo
    all_cards: Set[Card] = field(default_factory=lambda: set(create_deck()))
    
    def reset_inference(self):
        """Reset delle inferenze (chiamata quando vengono date nuove carte)."""
        self.impossible_cards.clear()
        
    def update_from_state(self, state: GameState, my_player_id: int):
        """Aggiorna il tracker dallo stato di gioco corrente."""
        self.my_hand = set(state.players[my_player_id].hand)
        self.table_cards = set(state.table)
        
        # Le carte catturate sono "viste"
        for player in state.players:
            self.seen_cards.update(player.captured)
        
        # Anche le carte sul tavolo sono viste
        self.seen_cards.update(state.table)
        
        # Anche la nostra mano
        self.seen_cards.update(self.my_hand)
        
    def infer_from_missed_capture(self, table: List[Card], played_card: Card):
        """
        Deduce cosa l'avversario NON ha, basandosi sul fatto che ha scartato
        invece di prendere. Assumiamo che se POTEVA prendere, AVREBBE preso.
        """
        # 1. Se ha scartato, non aveva carte uguali a quelle sul tavolo
        # (A meno che non abbia scartato proprio quella, ma qui analizziamo cosa
        # NON ha nelle ALTRE carte in mano).
        
        # Logica: Se c'era un 7 sul tavolo e lui ha scartato (e non ha preso il 7),
        # allora probabilmente NON ha un 7 in mano.
        table_values = {c.value for c in table}
        possible_opponent_cards = self.get_possible_opponent_cards()
        
        for card in possible_opponent_cards:
            # Se questa carta avesse permesso una presa "facile" (match diretto),
            # e l'avversario non l'ha usata, allora probabilmente non ce l'ha.
            if card.value in table_values:
                # Ecezione: Se la carta giocata era l'unica opzione? No, stiamo inferendo sulle ALTRE.
                self.impossible_cards.add(card)
                
    def is_impossible(self, card: Card) -> bool:
        """Ritorna True se abbiamo dedotto che l'avversario non ha questa carta."""
        return card in self.impossible_cards

    def card_played(self, card: Card):
        """Registra che una carta è stata giocata."""
        self.seen_cards.add(card)
    
    def cards_captured(self, cards: List[Card]):
        """Registra carte catturate."""
        for card in cards:
            self.seen_cards.add(card)
    
    def get_unseen_cards(self) -> Set[Card]:
        """Ritorna le carte non ancora viste."""
        return self.all_cards - self.seen_cards
    
    def get_possible_opponent_cards(self) -> Set[Card]:
        """
        Ritorna le carte che potrebbero essere in mano all'avversario.
        Sono le carte non viste, MENO quelle dedotte impossibili.
        """
        unseen = self.get_unseen_cards()
        # Rimuovi le carte nella nostra mano
        base_possible = unseen - self.my_hand - self.table_cards
        # Rimuovi le impossibili
        return base_possible - self.impossible_cards
    
    def probability_opponent_has(self, card: Card, opponent_hand_size: int = 3) -> float:
        """
        Stima la probabilità che l'avversario abbia una specifica carta.
        """
        if card in self.seen_cards:
            return 0.0
        if card in self.my_hand:
            return 0.0
        if card in self.table_cards:
            return 0.0
        
        possible_cards = self.get_possible_opponent_cards()
        if not possible_cards:
            return 0.0
        
        if card not in possible_cards:
            return 0.0
        
        # Probabilità semplice: mano avversario / carte possibili
        return min(1.0, opponent_hand_size / len(possible_cards))
    
    def probability_deck_has(self, card: Card, deck_size: int) -> float:
        """
        Stima la probabilità che una carta sia nel mazzo.
        """
        if card in self.seen_cards or card in self.my_hand or card in self.table_cards:
            return 0.0
        
        unseen = self.get_unseen_cards()
        if not unseen:
            return 0.0
        
        return deck_size / len(unseen) if len(unseen) >= deck_size else 0.0
    
    def get_statistics(self) -> Dict[str, any]:
        """Ritorna statistiche utili per il debugging."""
        unseen = self.get_unseen_cards()
        return {
            "total_seen": len(self.seen_cards),
            "total_unseen": len(unseen),
            "unseen_denari": sum(1 for c in unseen if c.suit == Suit.DENARI),
            "unseen_sevens": sum(1 for c in unseen if c.value == 7),
            "settebello_seen": any(c.is_settebello for c in self.seen_cards),
        }


@dataclass
class OpponentModel:
    """
    Modella il comportamento dell'avversario e adatta la strategia.
    
    Traccia:
    - Frequenza catture vs scarti
    - Errori commessi (mancate catture denari/settebello)
    - Aggressività (scope tentate)
    """
    # Contatori mosse
    total_moves: int = 0
    captures: int = 0
    discards: int = 0
    scope_made: int = 0
    
    # Errori osservati
    missed_settebello: int = 0
    missed_denari: int = 0
    missed_scope: int = 0
    
    # Carte preziose scartate
    valuable_discards: int = 0  # Denari/sette scartati
    
    def record_move(self, was_capture: bool, was_scopa: bool = False):
        """Registra una mossa dell'avversario."""
        self.total_moves += 1
        if was_capture:
            self.captures += 1
            if was_scopa:
                self.scope_made += 1
        else:
            self.discards += 1
    
    def record_error(self, error_type: str):
        """Registra un errore osservato."""
        if error_type == "settebello":
            self.missed_settebello += 1
        elif error_type == "denari":
            self.missed_denari += 1
        elif error_type == "scopa":
            self.missed_scope += 1
    
    def record_valuable_discard(self):
        """Registra quando avversario scarta carta preziosa."""
        self.valuable_discards += 1
    
    @property
    def capture_rate(self) -> float:
        """Percentuale di mosse che sono catture."""
        if self.total_moves == 0:
            return 0.5  # Default
        return self.captures / self.total_moves
    
    @property
    def error_rate(self) -> float:
        """Percentuale stimata di errori."""
        if self.total_moves < 3:
            return 0.2  # Default medio
        
        total_errors = (self.missed_settebello + self.missed_denari + 
                       self.missed_scope + self.valuable_discards)
        return min(0.5, total_errors / self.total_moves)
    
    def get_skill_level(self) -> str:
        """
        Stima il livello dell'avversario basandosi sul comportamento.
        Returns: 'weak', 'medium', 'strong', 'expert'
        """
        if self.total_moves < 4:
            return 'unknown'
        
        err = self.error_rate
        cap = self.capture_rate
        
        # Avversario debole: molti errori, poche catture
        if err > 0.3 or cap < 0.4:
            return 'weak'
        # Avversario medio: alcuni errori
        elif err > 0.15:
            return 'medium'
        # Avversario forte: pochi errori, buon capture rate
        elif err > 0.05:
            return 'strong'
        # Esperto: quasi perfect play
        else:
            return 'expert'
    
    def get_recommended_style(self) -> str:
        """
        Raccomanda uno stile di gioco basato sull'avversario.
        """
        level = self.get_skill_level()
        
        if level == 'weak':
            # Contro deboli: capitalizza errori, più aggressivo
            return 'aggressive'
        elif level == 'medium':
            # Contro medi: bilanciato
            return 'balanced'
        elif level == 'strong':
            # Contro forti: attenzione a non lasciare opportunità
            return 'defensive'
        else:  # expert
            # Contro esperti: massima precisione
            return 'perfect'
    
    def get_risk_adjustment(self) -> float:
        """
        Fattore di aggiustamento rischio basato sull'avversario.
        Returns: 0.5-1.5 (0.5 = meno rischio, 1.5 = più rischio)
        """
        level = self.get_skill_level()
        
        if level == 'weak':
            return 1.3  # Più aggressivi
        elif level == 'medium':
            return 1.1
        elif level == 'strong':
            return 0.9
        else:  # expert
            return 0.8  # Più conservativi
    
    def to_dict(self) -> Dict[str, any]:
        """Export stats."""
        return {
            "total_moves": self.total_moves,
            "capture_rate": self.capture_rate,
            "error_rate": self.error_rate,
            "skill_level": self.get_skill_level(),
            "recommended_style": self.get_recommended_style()
        }


def estimate_remaining_points(tracker: CardTracker, my_captured: List[Card], opp_captured: List[Card]) -> Dict[str, float]:
    """
    Stima i punti rimanenti da assegnare basandosi sulle carte non viste.
    """
    unseen = tracker.get_unseen_cards()
    
    # Carte attuali
    my_cards = len(my_captured)
    opp_cards = len(opp_captured)
    remaining_cards = len(unseen) + len(tracker.table_cards)
    
    # Denari
    my_denari = sum(1 for c in my_captured if c.is_denaro)
    opp_denari = sum(1 for c in opp_captured if c.is_denaro)
    unseen_denari = sum(1 for c in unseen if c.is_denaro)
    table_denari = sum(1 for c in tracker.table_cards if c.is_denaro)
    
    return {
        "my_cards": my_cards,
        "opp_cards": opp_cards,
        "remaining_cards": remaining_cards,
        "my_denari": my_denari,
        "opp_denari": opp_denari,
        "remaining_denari": unseen_denari + table_denari,
    }


# === TEST ===
if __name__ == "__main__":
    from scopa_core import initialize_game
    
    print("=== Test Scopa Memory ===\n")
    
    state = initialize_game()
    tracker = CardTracker()
    tracker.update_from_state(state, my_player_id=0)
    
    print(f"Mano P0: {state.players[0].hand}")
    print(f"Tavolo: {state.table}")
    
    stats = tracker.get_statistics()
    print(f"\nStatistiche:")
    print(f"  - Carte viste: {stats['total_seen']}")
    print(f"  - Carte non viste: {stats['total_unseen']}")
    print(f"  - Denari non visti: {stats['unseen_denari']}")
    print(f"  - Settebello visto: {stats['settebello_seen']}")
    
    possible_opp = tracker.get_possible_opponent_cards()
    print(f"\nCarte possibili in mano avversario: {len(possible_opp)}")
    
    # Test probabilità
    settebello = Card(Suit.DENARI, 7)
    prob = tracker.probability_opponent_has(settebello, opponent_hand_size=3)
    print(f"\nP(avversario ha settebello): {prob:.2%}")
    
    print("\n✅ Test Memory completato!")
