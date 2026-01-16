"""
Scopa AI v9.3 - Self-Play Safe (Refactored)

NUOVE STRATEGIE:
1. Adaptive Play - difensivo se avanti, aggressivo se indietro
2. Forcing Strategy - lascia configurazioni tavolo sfavorevoli per avversario
3. Trap detection - evita trappole comuni

DIFFERENZA CHIAVE vs Opponents:
- Noi usiamo analisi situazionale che opponents non fanno
- Consideriamo punteggio corrente per decidere stile di gioco
"""

from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import IntEnum
import random

from scopa_core import (
    GameState, Move, Card, Suit,
    get_valid_moves, apply_move, create_deck,
    PRIMIERA_VALUES, calculate_primiera, PlayerState
)
from scopa_memory import OpponentModel


# === CARD MEMORY + OPPONENT MODELING ===

@dataclass
class CardMemory:
    """Traccia carte viste e comportamento avversario."""
    seen: Set[Card] = field(default_factory=set)
    # Opponent modeling (v11.5 using external class)
    opponent: OpponentModel = field(default_factory=OpponentModel)
    
    # [NEW] Inferenza Negativa
    impossible_cards: Set[Card] = field(default_factory=set)
    
    def reset_inference(self):
        """Reset inferenze su nuova mano."""
        self.impossible_cards.clear()
        
    def infer_from_missed_capture(self, table: List[Card], played_card: Card):
        """Deduce carte mancanti da scarto."""
        table_values = {c.value for c in table}
        possible_opp = self.possible_opponent_cards()
        
        for card in possible_opp:
            # Se la carta mancante avrebbe permesso una presa diretta sul tavolo attuale
            # E l'avversario ha scartato
            # Allora probabilmente non ha quella carta.
            if card.value in table_values:
                # MARK IMPOSSIBLE
                self.impossible_cards.add(card)
                print(f"[AI-INFERENCE] Opponent missed capture on {card.value}. Deduced no {card}.")

    def update(self, state: GameState, my_player: int):
        self.seen.update(state.players[my_player].hand)
        self.seen.update(state.table)
        for p in state.players:
            self.seen.update(p.captured)
            
        # Rimuovi carte viste dalle impossibili (correzione errori inferenza)
        self.impossible_cards -= self.seen
    
    def record_opponent_move(self, was_capture: bool, was_scopa: bool = False):
        """Registra mossa avversario nel modello."""
        self.opponent.record_move(was_capture, was_scopa)

    def get_opponent_style(self) -> str:
        """Inferisce stile avversario usando OpponentModel."""
        return self.opponent.get_recommended_style()
    
    def unseen_cards(self) -> Set[Card]:
        return set(create_deck()) - self.seen
        
    def possible_opponent_cards(self) -> Set[Card]:
        """Carte che l'avversario POTREBBE avere (ignora impossibili)."""
        return self.unseen_cards() - self.impossible_cards
    
    def get_safe_discards(self, my_hand: List[Card], table: List[Card]) -> Set[Card]:
        """
        Ritorna le carte che possiamo scartare 'sicuramente' perché
        l'avversario non può catturarle (basato su impossible_cards).
        """
        safe = set()
        table_sum = sum(c.value for c in table)
        possible = self.possible_opponent_cards()
        possible_values = {c.value for c in possible}
        
        for card in my_hand:
            # Condition 1: Avversario non ha carte dello stesso valore
            can_match = card.value in possible_values
            
            # Condition 2: Carta scartata creerebbe sum catturabile?
            new_sum = table_sum + card.value
            can_sum = new_sum <= 10 and new_sum in possible_values
            
            if not can_match and not can_sum:
                safe.add(card)
        
        return safe
    
    def is_trap_possible(self, table: List[Card]) -> Dict:
        """
        Verifica se possiamo tendere una trappola:
        - Lasciare denari/punti sul tavolo sapendo che avversario è disarmato
        """
        if not table:
            return {"is_harmless": False, "can_direct": False, "can_sum": False}
            
        table_sum = sum(c.value for c in table)
        table_values = {c.value for c in table}
        possible = self.possible_opponent_cards()
        possible_values = {c.value for c in possible}
        
        # Check 1: Può fare match diretto?
        can_direct = bool(table_values & possible_values)
        
        # Check 2: Può fare sum?
        can_sum = table_sum <= 10 and table_sum in possible_values
        
        return {
            "is_harmless": not can_direct and not can_sum,
            "can_direct": can_direct,
            "can_sum": can_sum,
            "possible_cards": len(possible)
        }
    
    def prob_opp_has_card(self, card: Card, opp_hand_size: int) -> float:
        """Probabilità che l'avversario abbia una carta specifica."""
        if card in self.impossible_cards:
            return 0.0
            
        unseen = self.unseen_cards()
        if card not in unseen or opp_hand_size == 0:
            return 0.0
        # Probabilità semplice: opp_hand_size / len(unseen)
        return min(1.0, opp_hand_size / len(unseen))
    
    def dangerous_cards_prob(self, table: List[Card], opp_hand_size: int) -> Dict[str, float]:
        """Calcola probabilità che avversario abbia carte pericolose per il tavolo corrente."""
        result = {"settebello": 0.0, "scopa_card": 0.0, "capture_card": 0.0}
        unseen = self.unseen_cards()
        
        if not table or opp_hand_size == 0:
            return result
        
        table_sum = sum(c.value for c in table)
        table_values = {c.value for c in table}
        
        # Probabilità settebello
        settebello = Card(Suit.DENARI, 7)
        if settebello in unseen and settebello not in self.impossible_cards:
            result["settebello"] = self.prob_opp_has_card(settebello, opp_hand_size)
        
        # Probabilità scopa card
        scopa_cards = set()
        if len(table) == 1:
            for c in unseen:
                if c.value == table[0].value and c not in self.impossible_cards:
                    scopa_cards.add(c)
        if table_sum <= 10:
            for c in unseen:
                if c.value == table_sum and c not in self.impossible_cards:
                    scopa_cards.add(c)
        
        if scopa_cards:
            # P(almeno una)
            p_not = 1.0
            for _ in range(opp_hand_size):
                if len(unseen) > 0:
                    p_not *= (len(unseen) - len(scopa_cards)) / len(unseen)
            result["scopa_card"] = 1.0 - p_not
        
        # Probabilità cattura qualsiasi
        capture_cards = set()
        for c in unseen:
            if (c.value in table_values or c.value == table_sum) and c not in self.impossible_cards:
                capture_cards.add(c)
        
        if capture_cards:
            p_not = 1.0
            for _ in range(opp_hand_size):
                if len(unseen) > 0:
                    p_not *= max(0, (len(unseen) - len(capture_cards))) / len(unseen)
            result["capture_card"] = 1.0 - p_not
        
        return result
    
    def scopa_probability(self, table: List[Card], opp_hand_size: int) -> float:
        """Probabilità che avversario faccia scopa."""
        if not table or opp_hand_size == 0:
            return 0.0
        
        table_sum = sum(c.value for c in table)
        unseen = self.unseen_cards()
        
        # Carte che permettono scopa
        scopa_cards = set()
        
        if len(table) == 1:
            for card in unseen:
                if card.value == table[0].value and card not in self.impossible_cards:
                    scopa_cards.add(card)
        
        if table_sum <= 10:
            for card in unseen:
                if card.value == table_sum and card not in self.impossible_cards:
                    scopa_cards.add(card)
        
        if not scopa_cards or not unseen:
            return 0.0
        
        # P(almeno una scopa card)
        p_not = 1.0
        for _ in range(opp_hand_size):
            if len(unseen) > 0:
                p_not *= max(0, (len(unseen) - len(scopa_cards))) / len(unseen)
        return 1.0 - p_not


# === GAME ANALYSIS ===

def get_game_phase(state: GameState) -> str:
    cards_left = len(state.deck) + sum(len(p.hand) for p in state.players)
    if cards_left <= 6:
        return "endgame"
    elif cards_left <= 18:
        return "midgame"
    return "opening"


def get_advantage(state: GameState, my_player: int) -> Dict[str, int]:
    """Calcola vantaggio attuale."""
    me = state.players[my_player]
    opp = state.players[1 - my_player]
    
    # Punti attuali stimati
    my_cards = len(me.captured)
    opp_cards = len(opp.captured)
    my_denari = sum(1 for c in me.captured if c.is_denaro)
    opp_denari = sum(1 for c in opp.captured if c.is_denaro)
    my_sevens = sum(1 for c in me.captured if c.value == 7)
    opp_sevens = sum(1 for c in opp.captured if c.value == 7)
    
    # Settebello
    i_have_7d = any(c.is_settebello for c in me.captured)
    opp_has_7d = any(c.is_settebello for c in opp.captured)
    
    # Stima punti
    my_pts = me.scope
    opp_pts = opp.scope
    
    if my_cards > opp_cards:
        my_pts += 1
    elif opp_cards > my_cards:
        opp_pts += 1
    
    if my_denari > opp_denari:
        my_pts += 1
    elif opp_denari > my_denari:
        opp_pts += 1
    
    if i_have_7d:
        my_pts += 1
    elif opp_has_7d:
        opp_pts += 1
    
    if my_sevens > opp_sevens:
        my_pts += 0.5  # Probabile primiera
    elif opp_sevens > my_sevens:
        opp_pts += 0.5
    
    return {
        "my_pts": my_pts,
        "opp_pts": opp_pts,
        "advantage": my_pts - opp_pts,
        "cards_diff": my_cards - opp_cards,
        "denari_diff": my_denari - opp_denari,
        "sevens_diff": my_sevens - opp_sevens,
        "i_have_7d": i_have_7d,
        "opp_has_7d": opp_has_7d,
        "7d_available": not i_have_7d and not opp_has_7d,
    }


def get_play_style(advantage: Dict) -> str:
    """Determina stile di gioco basato sul vantaggio."""
    adv = advantage["advantage"]
    if adv >= 2:
        return "defensive"   # Siamo nettamente avanti: evita rischi
    elif adv >= 0.5:
        return "balanced"    # Leggero vantaggio: gioca normale
    elif adv >= -0.5:
        return "aggressive"  # Pareggio: cerca scope
    else:
        return "desperate"   # Indietro: rischia tutto


# === MOVE SCORING ===

class P(IntEnum):
    """Priority values - v11.0 SELF-PLAY OPTIMIZED"""
    MAX = 500
    CRITICAL = 199      # Optimized from 185 (capture_denari)
    VERY_HIGH = 105
    HIGH = 65           # Optimized from 62 (capture_seven)
    MEDIUM = 38         # Optimized from 32 (capture_base)
    LOW = 16
    MINIMAL = 6
    SCOPA_BONUS = 436   # Optimized from 500


def table_after_move(state: GameState, move: Move) -> List[Card]:
    table = state.table.copy()
    if move.is_capture:
        for c in move.cards_captured:
            table.remove(c)
    else:
        table.append(move.card_played)
    return table


def score_move(
    state: GameState,
    move: Move,
    memory: CardMemory,
    advantage: Dict,
    style: str,
    phase: str,
    match_score: Tuple[int, int] = (0, 0),
    dealer: str = "unknown"
) -> Tuple[int, List[str]]:
    """Scoring completo con adaptive strategy.
    
    Args:
        match_score: (my_points, opp_points)
        dealer: "me", "opp", "unknown"
    """
    
    score = 0
    reasons = []
    
    # === ADAPTIVE MATCH SCORE STRATEGY ===
    my_pts, opp_pts = match_score
    # Logic: If opponent is winning (>10) or we are winning.
    # We apply a 'risk_factor' to subsequent risk calculations.
    
    # 1. RISK ADJUSTMENT
    risk_factor = 1.0
    if opp_pts >= 10: # DANGER
        risk_factor = 1.5
        reasons.append("DEFENSE MODE")
    elif my_pts >= 10 and my_pts > opp_pts: # WINNING
        risk_factor = 0.8 # Play safer
        
    # 2. DEALER ADVANTAGE (Last Mover)
    is_last_hand = (len(state.deck) == 0)
    who_deals = dealer
    
    # === CARD PLAYED PENALTY (NEW!) ===
    # Penalize playing Denari when they could be preserved
    # This makes bot prefer playing Bastoni/Coppe/Spade over Denari
    card = move.card_played
    if card.is_denaro:
        if card.is_settebello:
            # ONLY penalize if DISCARDING Settebello (not capturing with it)
            if not move.is_capture:
                score -= P.MAX  # Huge penalty for discarding 7D
                reasons.append("7D rischio!")
            else:
                # v12.9: PROTECT SETTEBELLO - Check if another 7 in hand could do the same capture
                my_hand = state.players[state.current_player].hand
                other_sevens_in_hand = [c for c in my_hand if c.value == 7 and not c.is_settebello]
                
                if other_sevens_in_hand:
                    # Another 7 exists! Heavy penalty for using settebello
                    score -= P.CRITICAL  # -199: Strongly prefer other 7
                    reasons.append("PROTEGGI 7D! Usa altro 7")
                else:
                    # No alternative 7, small penalty is fine
                    score -= P.LOW
                    reasons.append("7D cattura")
        else:
            # v12.11: PROTECT DENARI - Different penalty for discard vs capture
            if not move.is_capture:
                # DISCARDING a Denaro is BAD - check if we have non-denari alternatives
                my_hand = state.players[state.current_player].hand
                non_denari_in_hand = [c for c in my_hand if not c.is_denaro]
                
                if non_denari_in_hand:
                    # v12.19: We have alternatives! VERY heavy penalty for discarding denaro
                    # Should be higher than the penalty for discarding a 7
                    score -= P.CRITICAL + P.HIGH  # -264: Strongly prefer non-denari for discard
                    reasons.append("NON SCARTARE DENARO!")
                else:
                    # All cards are denari, small penalty
                    score -= P.LOW
                    reasons.append("scarta denaro (forzato)")
            else:
                # v12.13: PREFER capturing WITH denari! 
                # When you capture with a denari, it goes to your pile = +1 denaro
                # Small BONUS for using denari to capture
                score += P.LOW
                reasons.append("cattura con denaro")
    
    # v12.13: PENALIZE capturing with NON-denari when denari alternative exists
    if move.is_capture and not card.is_denaro:
        my_hand = state.players[state.current_player].hand
        # v12.20 FIX: Exclude settebello - we WANT to protect it, not use it for captures!
        denari_same_value = [c for c in my_hand if c.is_denaro and c.value == card.value and not c.is_settebello]
        
        if denari_same_value:
            # We have a denari of same value! Heavy penalty for not using it
            score -= P.CRITICAL  # -199: Strongly prefer denari for capture
            reasons.append(f"USA {denari_same_value[0]} INVECE!")
    
    # v12.12: PROTECT SEVENS - Don't discard 7s (crucial for Primiera)
    if card.value == 7 and not card.is_settebello:  # Settebello already handled above
        if not move.is_capture:
            my_hand = state.players[state.current_player].hand
            non_seven_in_hand = [c for c in my_hand if c.value != 7]
            
            if non_seven_in_hand:
                # We have non-7 alternatives! Heavy penalty for discarding 7
                score -= P.CRITICAL  # -199: Strongly prefer non-7 for discard
                reasons.append("NON SCARTARE 7!")
            else:
                # All cards are 7s, small penalty
                score -= P.LOW
                reasons.append("scarta 7 (forzato)")
    
    # Bonus for playing high figures (8, 9, 10) which are less valuable
    if card.value >= 8:
        score += P.LOW
    
    # === CAPTURE VALUE ===
    if move.is_capture:
        # Base - BOOST cattura!
        score += P.MEDIUM  # Era P.LOW
        
        # Settebello = SEMPRE massima priorità
        if any(c.is_settebello for c in move.cards_captured):
            score += P.MAX
            reasons.append("SETTEBELLO!")
        
        # Denari - SUPER BOOST! Always prefer capturing Denari
        denari = sum(1 for c in move.cards_captured if c.is_denaro)
        if denari > 0:
            # Base bonus for any Denari capture
            score += P.CRITICAL  # Always attractive
            
            # Extra if behind
            if advantage["denari_diff"] < -2:
                score += denari * P.CRITICAL
            elif advantage["denari_diff"] < 0:
                score += denari * P.VERY_HIGH
            else:
                score += denari * P.HIGH
            reasons.append(f"denari x{denari}")
        
        # Sette (primiera) - BOOST!
        sevens = sum(1 for c in move.cards_captured if c.value == 7)
        if sevens > 0:
            if advantage["sevens_diff"] < 0:
                score += sevens * P.VERY_HIGH
            else:
                score += sevens * P.HIGH
            reasons.append(f"sette x{sevens}")
        
        # Sei (importanti per primiera)
        sixes = sum(1 for c in move.cards_captured if c.value == 6)
        if sixes > 0:
            score += sixes * P.MEDIUM
        
        # === PRIMIERA PROTECTION (v8.5) ===
        # Bonus esplicito per raccogliere 7 di semi mancanti
        my_captured = state.players[state.current_player].captured
        my_suits_with_7 = {c.suit for c in my_captured if c.value == 7}
        for c in move.cards_captured:
            if c.value == 7 and c.suit not in my_suits_with_7:
                score += P.HIGH  # Bonus per 7 di seme mancante
                reasons.append(f"7 {c.suit.value[:3]}!")
        
        # Numero carte catturate - MORE AGGRESSIVE!
        num_captured = len(move.cards_captured)
        
        # BASE CAPTURE BONUS: Ensure capture > safe discard (v12.7 fix)
        score += P.CRITICAL 
        
        score += num_captured * P.HIGH
        if num_captured >= 3:
            score += P.CRITICAL  # 3+ cards = big advantage
            reasons.append(f"cattura x{num_captured}")
        elif num_captured >= 2:
            score += P.MEDIUM  # 2 cards bonus
            reasons.append(f"cattura x{num_captured}")
        
        # SCOPA - CRITICAL in single-hand games!
        # v12.3 AGGRESSIVE SCOPE: +50% bonus per scope
        if move.is_scopa:
            scopa_bonus = int(P.MAX * 1.5)
            score += scopa_bonus
            reasons.append(f"SCOPA! (+{scopa_bonus})")
        
        # v12.3: Bonus per near-scopa (lasciare 1 carta)
        if move.is_capture and not move.is_scopa:
            new_table = table_after_move(state, move)
            if len(new_table) == 1:
                score += P.MEDIUM
                reasons.append("near-scopa")

        # === v12.15: ADVANCED ENDGAME LOGIC ===
        # The player who captures LAST gets all remaining table cards!
        # If opponent is dealer → I play last (advantage)
        # If I am dealer → opponent plays last (disadvantage)
        
        cards_in_play = len(state.deck) + sum(len(p.hand) for p in state.players)
        my_hand_size = len(state.players[state.current_player].hand)
        
        # Endgame = last 4 cards or less (was 6 - too aggressive)
        is_endgame = cards_in_play <= 4
        is_very_last = my_hand_size == 1 and len(state.deck) == 0
        
        if is_endgame:
            # Determine who plays last
            i_play_last = (who_deals == "opp")  # If opponent is dealer, I play last!
            opp_plays_last = (who_deals == "me")  # If I am dealer, opponent plays last
            
            if i_play_last:
                # I play last - BUT only if I actually get the final capture!
                # If I capture now but leave a card opponent can take, THEY get final table!
                if move.is_capture:
                    new_table = table_after_move(state, move)
                    
                    # v12.19: Check if leaving a card opponent can capture
                    if new_table and len(new_table) == 1 and memory:
                        left_card_value = new_table[0].value
                        # How many cards of this value are still unseen?
                        seen_of_value = sum(1 for c in memory.seen if c.value == left_card_value)
                        unseen_of_value = 4 - seen_of_value
                        
                        if unseen_of_value > 0:
                            # Opponent could have this card! If they do, THEY get final table!
                            # HEAVY penalty because we'd lose the final table advantage
                            score -= P.MAX  # -500: DON'T leave capturable single cards!
                            reasons.append(f"ATTENZIONE! Lasci {new_table[0]} catturabile!")
                        else:
                            # No cards left - safe to capture
                            score += P.MAX  # +500 - guaranteed final table!
                            reasons.append("ULTIMA PRESA SICURA!")
                    elif not new_table:
                        # SCOPA! Always good
                        pass  # SCOPA bonus already applied
                    elif is_very_last:
                        score += P.MAX  # +500 - this capture wins us the final table!
                        reasons.append("ULTIMA PRESA!")
                    else:
                        # Multiple cards left, harder for opponent to capture all
                        score += P.MEDIUM  # Small bonus
                        reasons.append("endgame capture")
                else:
                    reasons.append("endgame discard (I play last)")
                    
            elif opp_plays_last:
                # DISADVANTAGE: Opponent plays last
                if move.is_capture:
                    new_table = table_after_move(state, move)
                    if new_table:
                        # Only penalize if leaving valuable cards
                        valuable_left = sum(1 for c in new_table if c.is_denaro or c.value == 7)
                        if valuable_left > 0:
                            score -= valuable_left * P.LOW  # Reduced from P.MEDIUM
                            reasons.append(f"opp will get {valuable_left} valuable")
                else:
                    reasons.append("endgame discard (opp plays last)")
            else:
                # Unknown dealer - use old logic
                if is_last_hand and my_hand_size == 1:
                    score += P.CRITICAL
                    reasons.append("LAST CATCH")
    
    # === TABLE RISK ===
    new_table = table_after_move(state, move)
    
    if new_table:
        opp_hand = len(state.opponent.hand)
        scopa_prob = memory.scopa_probability(new_table, opp_hand)
        
        # ADAPTIVE: quanto pesiamo il rischio?
        adv = advantage.get("advantage", 0)
        if adv >= 3:
            risk_multiplier = 1.8
        elif style == "defensive":
            risk_multiplier = 1.5
        elif style == "balanced":
            risk_multiplier = 1.2
        elif style == "aggressive":
            risk_multiplier = 0.9
        else:  # desperate
            risk_multiplier = 0.5
        
        # Apply Match Context
        risk_multiplier *= risk_factor
        
        # === v12.24: USE IMPOSSIBLE_CARDS TO REDUCE SCOPA RISK ===
        # If we KNOW opponent can't have the "fatal" card, reduce/eliminate risk
        # CONSERVATIVE: Only significantly reduce risk with 3+ impossible cards
        if scopa_prob > 0 and memory and hasattr(memory, 'impossible_cards'):
            table_sum = sum(c.value for c in new_table)
            # Fatal card = card that could capture the table
            if len(new_table) == 1:
                fatal_value = new_table[0].value  # Direct capture
            else:
                fatal_value = table_sum  # Sum capture (if <= 10)
            
            if fatal_value <= 10:
                # Count how many cards of fatal value are IMPOSSIBLE for opponent
                impossible_fatal = sum(1 for c in memory.impossible_cards 
                                      if c.value == fatal_value)
                
                # CONSERVATIVE thresholds:
                if impossible_fatal >= 3:
                    # 3+ impossible = very low risk (but not zero - inference could be wrong)
                    scopa_prob *= 0.2
                    reasons.append(f"SAFE! ({impossible_fatal} {fatal_value}s impossible)")
                elif impossible_fatal >= 2:
                    # 2 impossible = modest risk reduction
                    scopa_prob *= 0.5
                    reasons.append(f"low risk ({impossible_fatal} {fatal_value}s impossible)")
                # 1 impossible = no reduction (too uncertain)

        
        # Penalità base per probabilità scopa
        # v12.10: PARANOID SCOPA RISK (User Request: "Don't risk Scopa for small gains")
        if scopa_prob > 0.5:
            penalty = P.CRITICAL  # -199: NEVER DO THIS
            reasons.append(f"RISCHIO SCOPA ESTREMO ({int(scopa_prob*100)}%)!")
        elif scopa_prob > 0.3:
            penalty = P.VERY_HIGH # -105: Almost never worth it
            reasons.append(f"rischio scopa alto ({int(scopa_prob*100)}%)")
        elif scopa_prob > 0.15:
            penalty = P.HIGH      # -65: Only if capture is P.CRITICAL
            reasons.append(f"rischio scopa ({int(scopa_prob*100)}%)")
        elif scopa_prob > 0.05:
            penalty = P.MEDIUM    # -38: Need good capture reward
            reasons.append("rischio scopa basso")
        elif scopa_prob < 0.01:
            # v12.10: EXPLICIT SAFETY BONUS
            table_sum = sum(c.value for c in new_table)
            
            # If sum > 10, Scopa is IMPOSSIBLE (cannot capture >10 with one card)
            if len(new_table) >= 2 and table_sum > 10:
                score += P.LOW
                reasons.append(f"SAFE (sum {table_sum} > 10)")
                
            # v12.18: Only say SAFE for low sums if we KNOW all cards are seen
            elif table_sum <= 10:
                if memory and len(memory.seen) >= 10:
                    seen_of_sum = sum(1 for c in memory.seen if c.value == table_sum)
                    if seen_of_sum >= 4:
                        reasons.append(f"SAFE (sum {table_sum}, all seen)")
                    elif table_sum <= 5:
                        reasons.append(f"sum {table_sum} (risky)")
                    else:
                        reasons.append(f"sum {table_sum}")
                elif table_sum <= 5:
                    # Early game, low sum = risky, don't say SAFE
                    reasons.append(f"sum {table_sum} (risky)")
            penalty = 0
        else:
            penalty = 0
            
        score -= int(penalty * risk_multiplier)

        
        # === SOMMA BASSA (v12.18 - INCREASED PENALTIES) ===
        # Leaving low sums is risky - opponent can easily capture!
        table_sum = sum(c.value for c in new_table)
        
        if table_sum <= 10:
            if table_sum <= 4:
                sum_penalty = int(P.MEDIUM)  # v12.18: Increased from P.LOW
            elif table_sum <= 6:
                sum_penalty = int(P.LOW)  # v12.18: Increased from P.MINIMAL
            else:
                sum_penalty = 0
            score -= sum_penalty
            
            # === EXHAUSTED SUM BONUS (v12.17 - CRITICAL FIX) ===
            # Only apply this logic when we have seen enough cards to make informed decisions
            # Without memory info, we should NOT heavily penalize captures!
            if memory and len(memory.seen) >= 10:  # Need at least 10 cards seen
                seen_of_sum_value = sum(1 for c in memory.seen if c.value == table_sum)
                if seen_of_sum_value >= 4:
                    # ALL cards of this value are out! COMPLETELY SAFE!
                    score += P.MAX  # +500 - ALWAYS prefer this
                    reasons.append(f"SAFE! (all {table_sum}s seen)")
                elif seen_of_sum_value == 3:
                    # v12.18: 3/4 = 1 card still out = risky but not catastrophic
                    score -= P.CRITICAL  # -199
                    reasons.append(f"RISCHIO ({4-seen_of_sum_value} {table_sum} left)")
                elif seen_of_sum_value <= 2 and table_sum <= 6:
                    # v12.18: 2+ cards still out AND low sum = moderate risk
                    # Only penalize for low sums that are easy to capture
                    score -= P.HIGH  # -65 (balanced penalty)
                    reasons.append(f"risk ({4-seen_of_sum_value} {table_sum}s left)")
            elif not memory or len(memory.seen) < 10:
                # Early game: just use basic scopa probability
                # Light penalty for low sums that are easy to capture
                if table_sum <= 3:
                    score -= P.LOW  # Very light penalty
                    reasons.append(f"low sum ({table_sum})")
        
        # === ENDGAME SAFETY (v12.1 - SIMPLIFIED) ===
        # Solo penalità leggera per tavoli molto rischiosi
        seen_count = len(memory.seen) if memory else 0
        if seen_count >= 35 and table_sum <= 5 and len(new_table) == 1:
            # Solo quando MOLTO ovvio che rischiano scopa
            scopa_card_value = table_sum
            seen_of_value = sum(1 for c in memory.seen if c.value == scopa_card_value)
            remaining_of_value = 4 - seen_of_value
            
            if remaining_of_value >= 2:  # Almeno 2 carte rimaste
                score -= P.MEDIUM  # Penalità leggera
                reasons.append(f"endgame risk {scopa_card_value}")
        
        # Settebello lasciato sul tavolo = catastrofe
        if any(c.is_settebello for c in new_table):
            score -= P.MAX * 3
            reasons.append("7D A RISCHIO!")
        
        # === ADVANCED CARD COUNTING (v12.25 - RE-ENABLED CONSERVATIVELY) ===
        # Only use in mid-game (10-30 cards seen) where inference is most reliable
        seen_count = len(memory.seen) if memory else 0
        opp_hand = len(state.opponent.hand) if hasattr(state, 'opponent') else 3
        
        if memory and 10 <= seen_count <= 30:
            danger_probs = memory.dangerous_cards_prob(new_table, opp_hand)
            
            # High scopa probability = extra penalty (on top of existing scopa_prob penalty)
            if danger_probs["scopa_card"] > 0.35:
                # Very dangerous - add moderate penalty
                extra_penalty = int(P.MEDIUM * (danger_probs["scopa_card"] - 0.35) * 2)
                score -= extra_penalty
                reasons.append(f"ACC: scopa risk {int(danger_probs['scopa_card']*100)}%")
            
            # Low capture probability = bonus for safe configuration
            if danger_probs["capture_card"] < 0.2:
                bonus = int(P.LOW * (1.0 - danger_probs["capture_card"]))
                score += bonus
                reasons.append("ACC: low capture risk")

        
        # === BONUS CONFIGURAZIONE SICURA (v7.3) ===
        # Tavolo con somma alta e molte carte = difficile fare scopa
        if len(new_table) >= 3 and table_sum > 15:
            score += P.HIGH  # Aumentato da MEDIUM
        elif len(new_table) >= 2 and table_sum > 12:
            score += P.MEDIUM  # Aumentato da LOW
        
        # === TRAP SETUP BONUS (BAITING v12.1) ===
        # Solo in endgame quando siamo sicuri: bonus se avversario non può catturare
        if phase == "endgame":
            trap_info = memory.is_trap_possible(new_table)
            if trap_info["is_harmless"] and trap_info["possible_cards"] < 20:
                # Piccolo bonus - configurazione trappola (solo con alta confidenza)
                has_value = any(c.is_denaro for c in new_table) or any(c.value == 7 for c in new_table)
                if has_value:
                    score += P.MEDIUM
                    reasons.append("trap setup")
    
    # === DISCARD PENALTY ===
    if not move.is_capture:
        card = move.card_played
        
        if card.is_settebello:
            # CRITICO: Mai scartare settebello! Penalità massima assoluta
            score -= P.MAX * 5  # Era P.MAX, ora x5 per garantire
            reasons.append("MAI SCARTARE 7D!")
        elif card.is_denaro:
            score -= P.HIGH
        
        if card.value == 7:
            score -= P.VERY_HIGH
        elif card.value == 6:
            score -= P.MEDIUM
        
        # FORCING STRATEGY: quando scartiamo, preferiamo lasciare
        # configurazioni difficili per l'avversario
        # Lasciare figure è meglio (meno probabile che avversario abbia)
        if card.value >= 8:
            score += P.LOW  # Bonus piccolo per scartare figure
        
        # === SMART DISCARD v12.6: Context-aware ===
        # DISABLED in extreme endgame (35+ cards seen) - last capture matters more!
        seen_count = len(memory.seen) if memory else 0
        in_extreme_endgame = seen_count >= 35
        
        if memory and len(state.table) == 0 and not in_extreme_endgame:
            # Count how many of this value have been seen
            seen_of_value = sum(1 for c in memory.seen if c.value == card.value)
            remaining_of_value = 4 - seen_of_value
            
            # Bonus for discarding cards with fewer remaining copies
            # Must be strong enough to override denaro penalty (P.HIGH=65)
            if remaining_of_value == 0:
                # BEST: No copies left - opponent CAN'T capture!
                score += P.CRITICAL  # +199
                reasons.append(f"SAFE! (0 left)")
            elif remaining_of_value == 1:
                # GOOD: Only 1 copy left - very unlikely capture
                score += P.CRITICAL  # +199 (must beat denaro penalty + others)
                reasons.append(f"smart discard (1 left)")
            elif remaining_of_value == 2:
                # OK: 2 copies left
                score += P.HIGH  # +65
                reasons.append(f"ok discard (2 left)")
            # 3-4 remaining = penalty (opponent likely has one)
            elif remaining_of_value >= 3:
                score -= P.MEDIUM  # -38
                reasons.append(f"risky discard ({remaining_of_value} left)")
        
        # === ENDGAME LAST CAPTURE PRESERVATION v12.6 ===
        # In extreme endgame, prefer keeping cards that can capture table cards
        if in_extreme_endgame and not move.is_capture:
            table_values = {c.value for c in state.table}
            table_sum = sum(c.value for c in state.table)
            
            # Can this card potentially capture something on current table?
            can_capture_future = (
                card.value in table_values or  # Direct match
                (table_sum <= 10 and card.value == table_sum)  # Sum capture (valid range)
            )
            
            if can_capture_future:
                # SEVERE penalty for discarding a card that could capture!
                score -= P.MAX
                reasons.append("KEEP FOR LAST CAPTURE!")
            else:
                # This card can't capture anything on table - better to discard
                score += P.HIGH
                reasons.append("no future capture")
        
        # === SAFE DISCARD BONUS (BAITING v12.1) ===
        # Bonus se scartiamo carte che l'avversario NON può catturare
        # Solo per carte non preziose (evita di preferire scartare 7 o denari)
        # DISABLED in extreme endgame
        if not in_extreme_endgame and not card.is_denaro and card.value not in (6, 7):
            safe_cards = memory.get_safe_discards([card], state.table)
            if card in safe_cards:
                score += P.HIGH  # Scarto sicuro di carta non preziosa!
                reasons.append("safe discard")
    
    # === ENDGAME BOOST (v7.7) ===
    if phase == "endgame":
        if move.is_capture:
            # Settebello in endgame = PRIORITÀ ASSOLUTA
            if any(c.is_settebello for c in move.cards_captured):
                score += P.MAX  # Boost extra in endgame
            
            # Denari in endgame = molto importanti
            denari_captured = sum(1 for c in move.cards_captured if c.is_denaro)
            if denari_captured > 0:
                score += denari_captured * P.HIGH
            
            # === PRIMIERA FOCUS (v8.0) ===
            # Se primiera è contesa, prioritizza 7 e 6
            if abs(advantage["sevens_diff"]) <= 1:  # Primiera contesa
                sevens = sum(1 for c in move.cards_captured if c.value == 7)
                sixes = sum(1 for c in move.cards_captured if c.value == 6)
                score += sevens * P.CRITICAL  # 7 cruciali per primiera
                score += sixes * P.HIGH  # 6 importanti
            
            # Se siamo indietro nelle carte, ogni cattura vale di più
            if advantage["cards_diff"] < 0:
                score += len(move.cards_captured) * P.HIGH
            
            # Se siamo avanti nei denari, proteggi il vantaggio
            if advantage["denari_diff"] > 0:
                score += P.MEDIUM  # Bonus stabilità
        
        # In endgame, non scartare MAI denari se possibile
        if not move.is_capture and move.card_played.is_denaro:
            score -= P.CRITICAL  # Penalità extra
        
        # In endgame, non scartare 7 se primiera è contesa
        if not move.is_capture and move.card_played.value == 7:
            if abs(advantage["sevens_diff"]) <= 1:
                score -= P.CRITICAL
    
    return score, reasons


# === ENDGAME MINIMAX ===

def clone_game_state(state: GameState) -> GameState:
    """Copia profonda dello stato per minimax."""
    return GameState(
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


def evaluate_final_position(state: GameState, my_player: int) -> int:
    """Valuta posizione finale per minimax. Score = differenza punti."""
    from scopa_core import calculate_scores
    
    # SIMULATE ENDGAME SWEEP rule:
    # If cards remain on table, they go to the last capturer
    if state.table and state.last_capturer is not None:
        last_cap = state.last_capturer
        state.players[last_cap].captured.extend(state.table)
        state.table.clear()
        
    scores = calculate_scores(state)
    my_score = scores[my_player].total
    opp_score = scores[1 - my_player].total
    
    return (my_score - opp_score) * 1000  # Scala per precisione


def is_game_finished(state: GameState) -> bool:
    """Verifica se partita terminata."""
    return (
        not state.deck and
        not state.players[0].hand and
        not state.players[1].hand
    )


def minimax(state: GameState, depth: int, my_player: int, maximizing: bool, alpha: int = -9999, beta: int = 9999) -> Tuple[int, Optional[Move]]:
    """
    Minimax con alpha-beta pruning per endgame.
    Ritorna (score, best_move).
    """
    # Condizione terminale
    if depth == 0 or is_game_finished(state) or not state.current.hand:
        return evaluate_final_position(state, my_player), None
    
    moves = get_valid_moves(state)
    if not moves:
        return evaluate_final_position(state, my_player), None
    
    best_move = moves[0]
    
    if maximizing:
        max_eval = -9999
        for move in moves:
            new_state = apply_move(clone_game_state(state), move)
            eval_score, _ = minimax(new_state, depth - 1, my_player, False, alpha, beta)
            if eval_score > max_eval:
                max_eval = eval_score
                best_move = move
            alpha = max(alpha, eval_score)
            if beta <= alpha:
                break  # Pruning
        return max_eval, best_move
    else:
        min_eval = 9999
        for move in moves:
            new_state = apply_move(clone_game_state(state), move)
            eval_score, _ = minimax(new_state, depth - 1, my_player, True, alpha, beta)
            if eval_score < min_eval:
                min_eval = eval_score
                best_move = move
            beta = min(beta, eval_score)
            if beta <= alpha:
                break  # Pruning
        return min_eval, best_move


def should_use_minimax(state: GameState) -> bool:
    """Determina se usare minimax (endgame con poche carte)."""
    total_cards = len(state.deck) + sum(len(p.hand) for p in state.players)
    # Keep at 12 - extension to 16 caused regression
    return total_cards <= 12


# === DEEP MONTE CARLO v2 ===

def smart_playout_move(state: GameState, moves: List[Move]) -> Move:
    """
    Smart playout policy for MC simulations (v12.1).
    More aggressive on valuable captures.
    """
    if not moves:
        return None
    
    # Prefer captures (natural Scopa instinct)
    captures = [m for m in moves if m.is_capture]
    if captures:
        # Priority 1: Settebello - always take!
        for c in captures:
            if any(card.is_settebello for card in c.cards_captured):
                return c
        
        # Priority 2: Scopa - clear table
        for c in captures:
            if c.is_scopa:
                return c
        
        # Priority 3: Denari captures (multiple preferred)
        denari_caps = [c for c in captures if any(card.is_denaro for card in c.cards_captured)]
        if denari_caps:
            # Prefer more denari
            best = max(denari_caps, key=lambda m: sum(1 for c in m.cards_captured if c.is_denaro))
            return best
        
        # Priority 4: Multi-card captures (more cards = better)
        if len(captures) > 1:
            best = max(captures, key=lambda m: len(m.cards_captured))
            if len(best.cards_captured) >= 2:
                return best
        
        # Random capture if no priority match
        return random.choice(captures)
    
    # Discard: AVOID discarding denari, prefer high non-denari values
    discards = [m for m in moves if not m.is_capture]
    if discards:
        # FIX 3: NEVER discard denari if possible
        non_denari = [m for m in discards if not m.card_played.is_denaro]
        if non_denari:
            # Prefer discarding 8, 9, 10 (figure) over valuable cards
            high_discards = [m for m in non_denari if m.card_played.value >= 8]
            if high_discards:
                return random.choice(high_discards)
            return random.choice(non_denari)
        
        # If we MUST discard denari, prefer low value (not 7d!)
        # Sort by value, take the lowest (least valuable)
        sorted_denari = sorted(discards, key=lambda m: (m.card_played.is_settebello, m.card_played.value))
        return sorted_denari[0]  # Lowest value denaro, never settebello
    
    return random.choice(moves)


def monte_carlo_evaluate(state: GameState, move: Move, my_player: int, simulations: int = 50) -> float:
    """
    Deep Monte Carlo evaluation with smart playouts.
    Uses card counting for informed simulation.
    Ritorna win rate [0.0, 1.0].
    """
    from scopa_core import deal_cards, is_game_over, calculate_scores
    
    wins = 0
    total_margin = 0
    
    for _ in range(simulations):
        # Applica la mossa e simula fino alla fine
        sim_state = apply_move(clone_game_state(state), move)
        
        # Simula partita con smart playouts
        turn_limit = 50  # Safety limit
        turns = 0
        
        while not is_game_over(sim_state) and turns < turn_limit:
            # Distribuisci carte se necessario
            if not sim_state.players[0].hand and not sim_state.players[1].hand:
                if sim_state.deck:
                    sim_state = deal_cards(sim_state, 3)
            
            if not sim_state.current.hand:
                break
            
            # Smart playout
            moves = get_valid_moves(sim_state)
            if not moves:
                break
            
            chosen = smart_playout_move(sim_state, moves)
            if chosen:
                sim_state = apply_move(sim_state, chosen)
            
            turns += 1
        
        # Calcola chi vince
        scores = calculate_scores(sim_state)
        my_score = scores[my_player].total
        opp_score = scores[1 - my_player].total
        margin = my_score - opp_score
        
        total_margin += margin
        
        if my_score > opp_score:
            wins += 1
        elif my_score == opp_score:
            wins += 0.5  # Pareggio
    
    # Return win rate weighted by margin for tie-breaking
    base_rate = wins / simulations
    avg_margin = total_margin / simulations
    
    # Small bonus for higher margin wins (max 0.05)
    margin_bonus = min(0.05, avg_margin * 0.01) if avg_margin > 0 else 0
    
    return min(1.0, base_rate + margin_bonus)


# === HELPER ===

def parse_card(card_str: str) -> Optional[Card]:
    """Converte stringa bot (es. '7d') in oggetto Card."""
    if not card_str:
        return None
    
    # Rimuovi parentesi e spazi
    card_str = card_str.replace("(", "").replace(")", "").strip().lower()
    
    # Esempi: "7d", "10c", "assob"
    
    suit_map = {
        'd': Suit.DENARI, 'b': Suit.BASTONI, 
        'c': Suit.COPPE, 's': Suit.SPADE
    }
    
    # Trova il seme (ultima lettera)
    suit_char = card_str[-1]
    if suit_char not in suit_map:
        return None
    
    suit = suit_map[suit_char]
    val_str = card_str[:-1]
    
    try:
        val = int(val_str)
        return Card(suit, val)
    except ValueError:
        return None




class ScopaBot:
    """
    Classe che incapsula la logica del bot e la sua memoria.
    Necessaria per Self-Play e per evitare collisioni di stato globale.
    """
    def __init__(self, name="Bot"):
        self.name = name
        self.memory = CardMemory()
    
    def _update_memory_and_inference(self, state: GameState, last_action_desc: str):
        """Common logic to update memory and perform negative inference."""
        my_player = state.current_player
        
        # 1. New Deal Reset
        if len(state.players[my_player].hand) == 3:
            self.memory.reset_inference()
            
        # 2. Analyze Opponent Discard
        if "Opponent Discard" in last_action_desc and "(" in last_action_desc:
            try:
                card_str = last_action_desc.split("(")[1].replace(")", "")
                if card_str != "unknown":
                    card_played = parse_card(card_str)
                    prev_table = [c for c in state.table if c != card_played]
                    self.memory.infer_from_missed_capture(prev_table, card_played)
            except Exception as e:
                print(f"[AI] Inference Error: {e}")
                
        self.memory.update(state, my_player)
    
    def _lookahead_penalty(self, state: GameState, move: Move) -> int:
        """Valuta la risposta dell'avversario (2-ply lookahead - v12.26).
        
        1-ply: Cosa può fare l'avversario dopo la nostra mossa
        2-ply: Cosa possiamo fare NOI dopo la risposta dell'avversario
        """
        from scopa_core import apply_move
        
        next_state = apply_move(state, move)
        
        # Se avversario non ha carte, nessuna penalità
        if not next_state.current.hand:
            return 0
        
        opp_moves = get_valid_moves(next_state)
        if not opp_moves:
            return 0
        
        # === 1-PLY: Trova miglior mossa avversario ===
        best_opp_score = 0
        best_opp_move = None
        
        for m in opp_moves:
            opp_score = 0
            if m.is_capture:
                opp_score += 15
                if any(c.is_settebello for c in m.cards_captured):
                    opp_score += 280
                if m.is_scopa:
                    opp_score += 120
                opp_score += sum(26 for c in m.cards_captured if c.is_denaro)
                opp_score += sum(22 for c in m.cards_captured if c.value == 7)
                opp_score += len(m.cards_captured) * 9
            if opp_score > best_opp_score:
                best_opp_score = opp_score
                best_opp_move = m
        
        # === 2-PLY: Valuta la nostra contro-risposta ===
        # Se l'avversario fa una mossa forte, possiamo recuperare?
        counter_bonus = 0
        if best_opp_move and best_opp_score > 50:  # Solo se avversario ha mossa significativa
            state_after_opp = apply_move(next_state, best_opp_move)
            
            # Nostre mosse disponibili dopo la risposta avversario
            if state_after_opp.current.hand:  # Abbiamo ancora carte
                our_responses = get_valid_moves(state_after_opp)
                
                if our_responses:
                    # Trova la nostra migliore contro-risposta
                    best_counter = 0
                    for r in our_responses:
                        counter_score = 0
                        if r.is_capture:
                            counter_score += 15
                            if any(c.is_settebello for c in r.cards_captured):
                                counter_score += 280
                            if r.is_scopa:
                                counter_score += 120
                            counter_score += sum(26 for c in r.cards_captured if c.is_denaro)
                            counter_score += sum(22 for c in r.cards_captured if c.value == 7)
                            counter_score += len(r.cards_captured) * 9
                        best_counter = max(best_counter, counter_score)
                    
                    # Se possiamo recuperare, riduci la penalità
                    # La nostra risposta compensa parte del danno dell'avversario
                    counter_bonus = int(best_counter * 0.15)  # 15% di recovery
        
        # Penalità netta = danno avversario - nostro recupero
        net_penalty = best_opp_score - counter_bonus
        
        # Penalizza (-20% del danno netto)
        return -int(net_penalty * 0.20)


    def choose_move(self, 
                   state: GameState, 
                   weights: Dict = None,
                   use_monte_carlo: bool = False,
                   mc_simulations: int = 50,
                   match_score: Tuple[int, int] = (0, 0),
                   dealer: str = "unknown",
                   last_action_desc: str = "") -> Move:
        """Sceglie la mossa migliore aggiornando la memoria interna."""
        
        self._update_memory_and_inference(state, last_action_desc)
        
        moves = get_valid_moves(state)
        
        if not moves:
            raise ValueError("Nessuna mossa!")
        
        if len(moves) == 1:
            return moves[0]
            
        # === PROTEZIONE SETTEBELLO (bypassa lookahead) ===
        # Se possiamo prendere il settebello, lo prendiamo SEMPRE
        captures = [m for m in moves if m.is_capture]
        for cap in captures:
            if any(c.is_settebello for c in cap.cards_captured):
                return cap
                
        # ... logica continua chiamando score_move ...
        # Poiché score_move è una funzione standalone (o metodo statico),
        # possiamo chiamarla passando self.memory
        
        return self._evaluate_moves(state, moves, weights, use_monte_carlo, mc_simulations, match_score, dealer)

    def _evaluate_moves(self, state, moves, weights, use_monte_carlo, mc_simulations, match_score=(0,0), dealer="unknown"):
        # Implementazione della selezione mossa (ex choose_best_move body)
        
        # === MINIMAX DISABLED (v12.4) ===
        # The minimax solver was causing TERRIBLE decisions, overriding good heuristic scores.
        # Example: Heuristic correctly scored 5b->capture at +508 and 1d->discard at -226,
        # but minimax chose the -226 move! 
        # Until we fix minimax properly, we rely on heuristic + MC which works well.
        
        # NOTE: Minimax code kept but disabled. To re-enable, uncomment the block below.
        # if should_use_minimax(state):
        #     ... minimax logic ...

        # Calcolo advantage
        adv = get_advantage(state, state.current_player)
        style = self.memory.get_opponent_style()
        phase = get_game_phase(state)
        
        scored = []
        for move in moves:
            score, reasons = score_move(state, move, self.memory, adv, style, phase, match_score, dealer)
            # v12.21: Aggiunge lookahead penalty (come Pro/HumanPro)
            lookahead = self._lookahead_penalty(state, move)
            score += lookahead
            scored.append((score, move, reasons))
        
        # Sort scores
        scored.sort(key=lambda x: x[0], reverse=True)
        
        # === v12.22: MINIMAX REATTIVATO come tiebreaker ===
        # Usato solo in endgame quando l'euristica ha punteggi molto vicini
        if should_use_minimax(state) and len(scored) > 1:
            best_score = scored[0][0]
            second_score = scored[1][0]
            heuristic_diff = best_score - second_score
            
            # Solo se mosse molto vicine (diff < 50) - euristica non è sicura
            if heuristic_diff < 50:
                # Raccogli candidati con score simile (max 3)
                candidates = [x for x in scored if x[0] >= best_score - 50][:3]
                
                if len(candidates) > 1:
                    # Usa minimax per decidere tra candidati equivalenti
                    best_mm_score = -9999
                    best_move = candidates[0][1]
                    my_player = state.current_player
                    
                    for _, move, _ in candidates:
                        # Applica mossa e valuta con minimax
                        next_state = apply_move(clone_game_state(state), move)
                        mm_score, _ = minimax(next_state, 6, my_player, False)  # False = next is opponent
                        if mm_score > best_mm_score:
                            best_mm_score = mm_score
                            best_move = move
                    
                    return best_move
        
        # === MONTE CARLO v12.5: Smart MC con protezioni ===
        if use_monte_carlo and len(scored) > 1:
            best_score = scored[0][0]
            second_score = scored[1][0]
            heuristic_diff = best_score - second_score
            
            # FIX 2: Se l'euristica è CHIARISSIMA (diff > 150), skip MC
            # Questo evita che MC scelga mosse stupide come scartare denari
            if heuristic_diff > 150:
                # Decisione chiara, non serve MC
                return scored[0][1]
            
            # FIX 1: Threshold dinamico basato sulla qualità della mossa migliore
            # Se la mossa migliore ha score alto, siamo più stretti sui candidati
            if best_score > 200:
                threshold = int(P.MEDIUM)  # 38 - molto stretto
            elif best_score > 100:
                threshold = int(P.HIGH) // 2  # ~32
            else:
                threshold = int(P.HIGH)  # 65 - più permissivo
            
            candidates = [x for x in scored if x[0] >= best_score - threshold]
            candidates = candidates[:min(3, len(candidates))]  # Max 3 candidati
            
            # Se c'è solo 1 candidato, skip MC
            if len(candidates) <= 1:
                return scored[0][1]
            
            mc_results = []
            for score, move, reasons in candidates:
                win_rate = monte_carlo_evaluate(state, move, state.current_player, simulations=mc_simulations)
                mc_results.append((win_rate, move))
            
            mc_results.sort(key=lambda x: x[0], reverse=True)
            return mc_results[0][1]
            
        return scored[0][1]
    
    def get_all_evaluations(self, state: GameState, match_score: Tuple[int, int] = (0, 0), dealer: str = "unknown") -> List[Dict]:
        """
        Restituisce tutte le mosse valutate con punteggi, ragioni e contesto.
        Usato dal GameDiary per logging dettagliato.
        
        Returns:
            Lista di dizionari con:
            - move: oggetto Move
            - score: punteggio
            - reasons: lista di ragioni
            - context: {phase, style, advantage}
        """
        my_player = state.current_player
        self.memory.update(state, my_player)
        
        moves = get_valid_moves(state)
        if not moves:
            return []
        
        adv = get_advantage(state, my_player)
        style = self.memory.get_opponent_style()
        phase = get_game_phase(state)
        
        evaluations = []
        for move in moves:
            score, reasons = score_move(state, move, self.memory, adv, style, phase, match_score, dealer)
            evaluations.append({
                "move": move,
                "score": score,
                "reasons": reasons,
                "context": {
                    "phase": phase,
                    "style": style,
                    "advantage": adv.get("advantage", 0)
                }
            })
        
        # Sort by score descending
        evaluations.sort(key=lambda x: x["score"], reverse=True)
        return evaluations


# === LEGACY WRAPPER ===

def reset_memory():
    # No-op, deprecated
    pass


def choose_best_move(
    state: GameState,
    weights=None,
    use_monte_carlo: bool = False,
    mc_simulations: int = 50
) -> Move:
    """Wrapper compatibile con codice esistente."""
    # Crea un bot al volo (stateless)
    bot = ScopaBot()
    return bot.choose_move(state, weights, use_monte_carlo, mc_simulations)
    




def get_move_rankings(state: GameState, weights=None) -> List[Tuple[int, Move]]:
    """Wrapper per debug."""
    bot = ScopaBot()
    # Copia logica semplificata solo euristica
    bot.memory.update(state, state.current_player)
    
    # Nota: score_move è standalone, possiamo usarlo
    
    advantage = get_advantage(state, state.current_player)
    style = get_play_style(advantage)
    phase = get_game_phase(state)
    
    moves = get_valid_moves(state)
    evaluated = []
    for move in moves:
        score, _ = score_move(state, move, bot.memory, advantage, style, phase)
        evaluated.append((score, move))
    
    evaluated.sort(key=lambda x: x[0], reverse=True)
    return evaluated


# Compatibility
DEFAULT_WEIGHTS = None
HeuristicWeights = type(None)


# === TEST ===
if __name__ == "__main__":
    from scopa_core import initialize_game, apply_move
    
    print("=== Test Scopa AI v6 (Adaptive Strategy) ===\n")
    
    reset_memory()
    state = initialize_game()
    
    my_player = 0
    advantage = get_advantage(state, my_player)
    style = get_play_style(advantage)
    phase = get_game_phase(state)
    
    print(f"Tavolo: {state.table}")
    print(f"Mano: {state.current.hand}")
    print(f"Fase: {phase}, Stile: {style}")
    print(f"Vantaggio: {advantage['advantage']:.1f}")
    
    rankings = get_move_rankings(state)
    print(f"\nMosse valutate:")
    for score, move in rankings:
        print(f"  [{score:+4d}] {move}")
    
    best = choose_best_move(state)
    print(f"\n✅ Mossa scelta: {best}")
    
    # Simula partita
    print("\n--- Simulazione ---")
    reset_memory()
    state = initialize_game()
    
    for turn in range(8):
        if not state.current.hand:
            break
        
        adv = get_advantage(state, state.current_player)
        style = get_play_style(adv)
        best = choose_best_move(state)
        
        print(f"P{state.current_player} [{style[:3]}]: {best}")
        state = apply_move(state, best)
    
    print("\n✅ Test completato!")
