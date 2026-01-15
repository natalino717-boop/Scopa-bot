"""
Scopa Opponents v2 - Bot avversari con strategie differenziate

Livelli:
- RandomBot: casuale puro
- BeginnerBot: prende sempre, nessuna strategia
- MediumBot: alcune regole base, errori frequenti
- StrongBot: regole complete, errori rari
- ProBot: strategie avanzate, quasi perfetto
"""

from typing import List, Tuple
from abc import ABC, abstractmethod
import random

from scopa_core import GameState, Move, Card, get_valid_moves, apply_move


class BaseOpponent(ABC):
    """Classe base per tutti gli avversari."""
    
    name: str = "Base"
    
    @abstractmethod
    def choose_move(self, state: GameState) -> Move:
        """Sceglie una mossa dato lo stato corrente."""
        pass


class RandomBot(BaseOpponent):
    """Gioca casualmente. Baseline."""
    name = "Random"
    
    def choose_move(self, state: GameState) -> Move:
        moves = get_valid_moves(state)
        return random.choice(moves)


class BeginnerBot(BaseOpponent):
    """
    Principiante assoluto:
    - Prende sempre se può
    - Nessuna strategia
    - Non considera rischi
    """
    name = "Beginner"
    
    def choose_move(self, state: GameState) -> Move:
        moves = get_valid_moves(state)
        
        # Separa prese e scarti
        captures = [m for m in moves if m.is_capture]
        discards = [m for m in moves if not m.is_capture]
        
        # Prende sempre se può
        if captures:
            return random.choice(captures)
        return random.choice(discards)


class MediumBot(BaseOpponent):
    """
    Giocatore medio:
    - Prende settebello e scope
    - Preferisce denari
    - NON considera rischio scopa (errore comune)
    - Errori casuali 20% del tempo
    """
    name = "Medium"
    error_rate = 0.2
    
    def score_move(self, state: GameState, move: Move) -> int:
        score = 0
        
        if move.is_capture:
            score += 10  # Preferisce catturare
            
            # Settebello
            if any(c.is_settebello for c in move.cards_captured):
                score += 100
            
            # Scopa
            if move.is_scopa:
                score += 50
            
            # Denari
            for c in move.cards_captured:
                if c.is_denaro:
                    score += 15
                if c.value == 7:
                    score += 10
            
            # Più carte
            score += len(move.cards_captured) * 3
        
        return score
    
    def choose_move(self, state: GameState) -> Move:
        moves = get_valid_moves(state)
        
        # Errore casuale
        if random.random() < self.error_rate:
            return random.choice(moves)
        
        # Valuta mosse
        scored = [(self.score_move(state, m), m) for m in moves]
        scored.sort(key=lambda x: x[0], reverse=True)
        
        return scored[0][1]


class StrongBot(BaseOpponent):
    """
    Giocatore forte:
    - Regole complete
    - Evita dare scope
    - Protegge settebello
    - Errori rari (5%)
    """
    name = "Strong"
    error_rate = 0.05
    
    def get_table_after(self, state: GameState, move: Move) -> List[Card]:
        table = state.table.copy()
        if move.is_capture:
            for c in move.cards_captured:
                table.remove(c)
        else:
            table.append(move.card_played)
        return table
    
    def score_move(self, state: GameState, move: Move) -> int:
        score = 0
        
        if move.is_capture:
            score += 10
            
            # Settebello - MASSIMA priorità
            if any(c.is_settebello for c in move.cards_captured):
                score += 200
            
            # Scopa
            if move.is_scopa:
                score += 80
            
            # Denari
            for c in move.cards_captured:
                if c.is_denaro:
                    score += 20
                if c.value == 7:
                    score += 15
            
            score += len(move.cards_captured) * 5
        
        # Analisi rischio tavolo
        table_after = self.get_table_after(state, move)
        
        if table_after:
            table_sum = sum(c.value for c in table_after)
            
            # Rischio scopa
            if len(table_after) == 1:
                if table_after[0].value <= 7:
                    score -= 100  # Carta singola comune = MALE
                else:
                    score -= 50  # Figura = meno male
            
            if table_sum <= 10:
                score -= 30
            
            # Settebello sul tavolo = DISASTRO
            if any(c.is_settebello for c in table_after):
                score -= 150
        
        # Penalità scarto preziose
        if not move.is_capture:
            if move.card_played.is_denaro:
                score -= 15
            if move.card_played.value == 7:
                score -= 20
            if move.card_played.is_settebello:
                score -= 100
        
        return score
    
    def choose_move(self, state: GameState) -> Move:
        moves = get_valid_moves(state)
        
        # Errore raro
        if random.random() < self.error_rate:
            return random.choice(moves)
        
        scored = [(self.score_move(state, m), m) for m in moves]
        scored.sort(key=lambda x: x[0], reverse=True)
        
        return scored[0][1]


class ProBot(BaseOpponent):
    """
    Giocatore professionista:
    - Strategie avanzate
    - Considera configurazione ottimale tavolo
    - Lookahead 1 mossa
    - Quasi mai errori (1%)
    """
    name = "Pro"
    error_rate = 0.01
    
    def get_table_after(self, state: GameState, move: Move) -> List[Card]:
        table = state.table.copy()
        if move.is_capture:
            for c in move.cards_captured:
                table.remove(c)
        else:
            table.append(move.card_played)
        return table
    
    def score_move(self, state: GameState, move: Move) -> int:
        score = 0
        
        if move.is_capture:
            score += 15
            
            # Settebello
            if any(c.is_settebello for c in move.cards_captured):
                score += 300
            
            # Scopa
            if move.is_scopa:
                score += 120
            
            # Denari
            denari_count = sum(1 for c in move.cards_captured if c.is_denaro)
            score += denari_count * 25
            
            # Sette per primiera
            sevens = sum(1 for c in move.cards_captured if c.value == 7)
            score += sevens * 20
            
            # Sei (secondo miglior valore primiera)
            sixes = sum(1 for c in move.cards_captured if c.value == 6)
            score += sixes * 12
            
            # Assi
            aces = sum(1 for c in move.cards_captured if c.value == 1)
            score += aces * 8
            
            # Più carte = meglio
            score += len(move.cards_captured) * 8
        
        # RISCHIO TAVOLO
        table_after = self.get_table_after(state, move)
        
        if table_after:
            table_sum = sum(c.value for c in table_after)
            
            # Carta singola = RISCHIO CRITICO
            if len(table_after) == 1:
                card = table_after[0]
                if card.value <= 7:
                    score -= 150  # Molto probabile che avversario abbia
                elif card.value <= 10:
                    score -= 80
            
            # Somma bassa
            if table_sum <= 7:
                score -= 60
            elif table_sum <= 10:
                score -= 40
            
            # Settebello sul tavolo = CATASTROFE
            if any(c.is_settebello for c in table_after):
                score -= 250
            
            # Strategia avanzata: lascia somma > 10 con carte multiple
            if len(table_after) >= 2 and table_sum > 10:
                score += 20  # Buona configurazione
        
        # PENALITÀ SCARTO
        if not move.is_capture:
            card = move.card_played
            if card.is_settebello:
                score -= 200
            elif card.is_denaro:
                score -= 25
            if card.value == 7:
                score -= 30
            elif card.value == 6:
                score -= 15
        
        return score
    
    def lookahead_penalty(self, state: GameState, move: Move) -> int:
        """Valuta risposta avversario."""
        next_state = apply_move(state, move)
        
        if not next_state.current.hand:
            return 0
        
        # Simula mossa avversario
        opp_moves = get_valid_moves(next_state)
        if not opp_moves:
            return 0
        
        # Trova miglior mossa avversario
        best_opp_score = max(self.score_move(next_state, m) for m in opp_moves)
        
        # Penalizza se avversario ha buone opzioni
        return -best_opp_score * 0.2
    
    def choose_move(self, state: GameState) -> Move:
        moves = get_valid_moves(state)
        
        # Errore rarissimo
        if random.random() < self.error_rate:
            return random.choice(moves)
        
        # Valutazione con lookahead
        scored = []
        for move in moves:
            base_score = self.score_move(state, move)
            lookahead = self.lookahead_penalty(state, move)
            total = base_score + lookahead
            scored.append((total, move))
        
        scored.sort(key=lambda x: x[0], reverse=True)
        
        return scored[0][1]


# =============================================================================
# HUMAN-REALISTIC BOTS v2
# Comportamenti umani REALISTICI:
# - Casual: non vede catture, scarta male, lascia scope facili
# - Amateur: errori frequenti, qualche strategia
# - Expert: buono ma stanchezza e tilt
# - Pro: quasi perfetto
# =============================================================================

class HumanCasualBot(BaseOpponent):
    """
    Giocatore casual della domenica - MOLTO DEBOLE:
    - 35% delle volte NON VEDE che può catturare!
    - Scarta carte preziose senza pensarci
    - Lascia spesso carta singola (non sa che è male)
    - Non conosce il valore del settebello (50% lo ignora)
    """
    name = "HumanCasual"
    
    def __init__(self):
        self.moves_count = 0
    
    def choose_move(self, state: GameState) -> Move:
        moves = get_valid_moves(state)
        self.moves_count += 1
        
        captures = [m for m in moves if m.is_capture]
        discards = [m for m in moves if not m.is_capture]
        
        # 35% delle volte NON VEDE la cattura e scarta!
        if captures and discards and random.random() < 0.35:
            return random.choice(discards)
        
        if captures:
            # 50% delle volte NON riconosce il settebello!
            if random.random() < 0.50:
                # Prende a caso (potrebbe perdere il settebello)
                return random.choice(captures)
            
            # Altrimenti prende settebello se lo vede
            for m in captures:
                if any(c.is_settebello for c in m.cards_captured):
                    return m
            
            # Prende scopa solo 60% delle volte (non sempre la vede)
            scope = [m for m in captures if m.is_scopa]
            if scope and random.random() < 0.60:
                return scope[0]
            
            return random.choice(captures)
        
        # Scarta MALE: preferisce scartare carte preziose!
        # (Non sa cosa ha valore)
        if random.random() < 0.40:
            # Scarta settebello/denari/sette senza pensare
            bad_discards = [m for m in discards if 
                          m.card_played.is_settebello or
                          m.card_played.is_denaro or
                          m.card_played.value == 7]
            if bad_discards:
                return random.choice(bad_discards)
        
        return random.choice(discards)


class HumanAmateurBot(BaseOpponent):
    """
    Giocatore amatoriale - MEDIOCRE:
    - Conosce le basi ma sbaglia spesso (20%)
    - A volte non vede catture (15%)
    - Lascia carta singola abbastanza spesso
    - Protegge settebello (ma non sempre)
    - Tilt: dopo errore, gioca peggio
    """
    name = "HumanAmateur"
    
    def __init__(self):
        self.moves_count = 0
        self.tilt = 0  # 0-2
    
    def get_table_after(self, state: GameState, move: Move) -> List[Card]:
        table = state.table.copy()
        if move.is_capture:
            for c in move.cards_captured:
                table.remove(c)
        else:
            table.append(move.card_played)
        return table
    
    def choose_move(self, state: GameState) -> Move:
        moves = get_valid_moves(state)
        self.moves_count += 1
        
        captures = [m for m in moves if m.is_capture]
        discards = [m for m in moves if not m.is_capture]
        
        # Errore base + tilt
        error_rate = 0.20 + self.tilt * 0.10
        
        # 15% non vede cattura
        if captures and discards and random.random() < 0.15:
            return random.choice(discards)
        
        # 20% (+tilt) errore random
        if random.random() < error_rate:
            return random.choice(moves)
        
        if captures:
            # Priorità settebello (90% delle volte lo vede)
            if random.random() < 0.90:
                for m in captures:
                    if any(c.is_settebello for c in m.cards_captured):
                        return m
            
            # Scopa (85%)
            scope = [m for m in captures if m.is_scopa]
            if scope and random.random() < 0.85:
                return scope[0]
            
            # Preferisce denari (70%)
            if random.random() < 0.70:
                denari_moves = sorted(captures, 
                    key=lambda m: sum(1 for c in m.cards_captured if c.is_denaro),
                    reverse=True)
                if denari_moves[0].cards_captured:
                    return denari_moves[0]
            
            return random.choice(captures)
        
        # Scarta - a volte lascia carta singola bassa (male!)
        # 40% delle volte non pensa al rischio
        if random.random() < 0.40:
            return random.choice(discards)
        
        # Prova a non lasciare carta singola (60%)
        safe_discards = []
        for m in discards:
            table_after = self.get_table_after(state, m)
            if len(table_after) != 1 or table_after[0].value > 7:
                safe_discards.append(m)
        
        if safe_discards:
            return random.choice(safe_discards)
        return random.choice(discards)


class HumanExpertBot(BaseOpponent):
    """
    Esperto di tornei locali - BUONO:
    - Strategia solida
    - Errori rari (8%) ma aumentano con stanchezza
    - Conosce rischi carta singola
    - Tilt dopo scope subite
    - Stanchezza: dopo 12 mosse, errore aumenta
    """
    name = "HumanExpert"
    
    def __init__(self):
        self.moves_count = 0
        self.tilt = 0
    
    def get_table_after(self, state: GameState, move: Move) -> List[Card]:
        table = state.table.copy()
        if move.is_capture:
            for c in move.cards_captured:
                table.remove(c)
        else:
            table.append(move.card_played)
        return table
    
    @property
    def error_rate(self):
        base = 0.08
        fatigue = max(0, (self.moves_count - 12) * 0.015)
        tilt_penalty = self.tilt * 0.04
        return min(0.30, base + fatigue + tilt_penalty)
    
    def score_move(self, state: GameState, move: Move) -> int:
        score = 0
        
        if move.is_capture:
            score += 10
            
            if any(c.is_settebello for c in move.cards_captured):
                score += 200
            
            if move.is_scopa:
                score += 90
            
            for c in move.cards_captured:
                if c.is_denaro:
                    score += 22
                if c.value == 7:
                    score += 18
            
            score += len(move.cards_captured) * 6
        
        # Rischio tavolo
        table_after = self.get_table_after(state, move)
        if table_after:
            if len(table_after) == 1:
                if table_after[0].value <= 7:
                    score -= 100
                else:
                    score -= 50
            
            table_sum = sum(c.value for c in table_after)
            if table_sum <= 10:
                score -= 35
            
            if any(c.is_settebello for c in table_after):
                score -= 150
        
        if not move.is_capture:
            if move.card_played.is_settebello:
                score -= 120
            elif move.card_played.is_denaro:
                score -= 18
            if move.card_played.value == 7:
                score -= 22
        
        return score
    
    def choose_move(self, state: GameState) -> Move:
        moves = get_valid_moves(state)
        self.moves_count += 1
        
        # Tilt decay
        if self.moves_count % 5 == 0 and self.tilt > 0:
            self.tilt -= 1
        
        # Errore: prende 2a o 3a scelta
        if random.random() < self.error_rate:
            scored = [(self.score_move(state, m), m) for m in moves]
            scored.sort(key=lambda x: x[0], reverse=True)
            idx = min(random.randint(1, 2), len(scored) - 1)
            return scored[idx][1]
        
        scored = [(self.score_move(state, m), m) for m in moves]
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1]


class HumanProBot(BaseOpponent):
    """
    Professionista - MOLTO FORTE:
    - Card counting
    - Lookahead 1 mossa
    - Errori rarissimi (3%)
    - Gestisce bene il tilt
    - Strategia ottimale
    """
    name = "HumanPro"
    
    def __init__(self):
        self.moves_count = 0
        self.tilt = 0
    
    @property
    def error_rate(self):
        return min(0.12, 0.03 + self.tilt * 0.02)
    
    def get_table_after(self, state: GameState, move: Move) -> List[Card]:
        table = state.table.copy()
        if move.is_capture:
            for c in move.cards_captured:
                table.remove(c)
        else:
            table.append(move.card_played)
        return table
    
    def score_move(self, state: GameState, move: Move) -> int:
        score = 0
        
        if move.is_capture:
            score += 15
            
            if any(c.is_settebello for c in move.cards_captured):
                score += 280
            
            if move.is_scopa:
                score += 120
            
            denari = sum(1 for c in move.cards_captured if c.is_denaro)
            score += denari * 26
            
            sevens = sum(1 for c in move.cards_captured if c.value == 7)
            score += sevens * 22
            
            score += len(move.cards_captured) * 9
        
        table_after = self.get_table_after(state, move)
        
        if table_after:
            table_sum = sum(c.value for c in table_after)
            
            if len(table_after) == 1:
                if table_after[0].value <= 7:
                    score -= 160
                else:
                    score -= 80
            
            if table_sum <= 7:
                score -= 60
            elif table_sum <= 10:
                score -= 40
            
            if any(c.is_settebello for c in table_after):
                score -= 250
            
            if len(table_after) >= 2 and table_sum > 12:
                score += 20
        
        if not move.is_capture:
            if move.card_played.is_settebello:
                score -= 200
            elif move.card_played.is_denaro:
                score -= 25
            if move.card_played.value == 7:
                score -= 28
        
        return score
    
    def lookahead(self, state: GameState, move: Move) -> int:
        next_state = apply_move(state, move)
        
        if not next_state.current.hand:
            return 0
        
        opp_moves = get_valid_moves(next_state)
        if not opp_moves:
            return 0
        
        best_opp = max(self.score_move(next_state, m) for m in opp_moves)
        return -int(best_opp * 0.22)
    
    def choose_move(self, state: GameState) -> Move:
        moves = get_valid_moves(state)
        self.moves_count += 1
        
        # Tilt decay veloce
        if self.moves_count % 3 == 0 and self.tilt > 0:
            self.tilt -= 1
        
        # Errore raro
        if random.random() < self.error_rate:
            scored = [(self.score_move(state, m), m) for m in moves]
            scored.sort(key=lambda x: x[0], reverse=True)
            return scored[min(1, len(scored) - 1)][1]
        
        # Valutazione con lookahead
        scored = []
        for move in moves:
            base = self.score_move(state, move)
            look = self.lookahead(state, move)
            scored.append((base + look, move))
        
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1]



class ScopaAIOpponent(BaseOpponent):
    """
    Wrapper per ScopaAI v9.x per usarla come avversario.
    Permette Self-Play (AI vs AI).
    """
    name = "ScopaAI"
    
    def choose_move(self, state: GameState) -> Move:
        # Import lazy per evitare cicli
        from scopa_ai import choose_best_move, P
        
        # Configurazione standard (Deep MC)
        weights = {
            "CAPTURE_SCOPA": int(P.VERY_HIGH),  # ~105
            "CAPTURE_SETTEBELLO": int(P.MAX),   # 500
            "CAPTURE_DENARI": int(P.HIGH),      # 62
            "CAPTURE_SEVEN": int(P.HIGH),       # 62
        }
        
        # ScopaAI deve sapere chi è (giocatore corrente)
        # choose_best_move assume che 'state' sia dal punto di vista del bot
        # Se siamo nel framework BaseOpponent, 'state' è già corretto
        return choose_best_move(state, weights, use_monte_carlo=True, mc_simulations=50)



class ScopaRLOpponent(BaseOpponent):
    """
    Wrapper for Reinforcement Learning Agent.
    Requires 'scopa_dqn.pth' model.
    """
    name = "ScopaRL"
    
    def __init__(self):
        super().__init__()
        self.agent = None
        try:
            from scopa_rl_agent import ScopaRLAgent
            # Initialize agent
            self.agent = ScopaRLAgent(state_dim=126, action_dim=40)
            # Load model if exists
            model_path = "scopa_dqn.pth"
            try:
                self.agent.load(model_path)
                print(f"[{self.name}] Model loaded: {model_path}")
            except Exception as e:
                print(f"[{self.name}] Warning: Could not load model ({e}). Using random initialization.")
                
        except ImportError:
            print(f"[{self.name}] ERROR: PyTorch not installed. RL Agent disabled.")
            self.agent = None

    def choose_move(self, state: GameState) -> Move:
        if self.agent is None:
            # Fallback if Torch missing
            import random
            return random.choice(get_valid_moves(state))
            
        from scopa_core import get_valid_moves
        valid_moves = get_valid_moves(state)
        
        # Select action (Greedy, epsilon=0)
        move, _ = self.agent.select_action(state, valid_moves, epsilon=0, training=False)
        return move


# Factory
def create_opponent(level: str) -> BaseOpponent:
    """Crea un bot avversario dato il livello."""
    bots = {
        "random": RandomBot,
        "beginner": BeginnerBot,
        "medium": MediumBot,
        "scopa_rl": ScopaRLOpponent,

        "strong": StrongBot,
        "pro": ProBot,
        "human_casual": HumanCasualBot,
        "human_amateur": HumanAmateurBot,
        "human_expert": HumanExpertBot,
        "human_pro": HumanProBot,
        "scopa_ai": ScopaAIOpponent,  # Added for self-play
    }
    
    level_lower = level.lower()
    if level_lower not in bots:
        raise ValueError(f"Livello sconosciuto: {level}. Usa: {list(bots.keys())}")
    
    return bots[level_lower]()


# === TEST ===
if __name__ == "__main__":
    from scopa_core import initialize_game
    
    print("=== Test Opponents v2 ===\n")
    
    for level in ["random", "beginner", "medium", "strong", "pro"]:
        bot = create_opponent(level)
        state = initialize_game()
        
        moves_made = []
        for _ in range(3):
            if not state.current.hand:
                break
            move = bot.choose_move(state)
            moves_made.append(str(move))
            state = apply_move(state, move)
        
        print(f"{bot.name}Bot:")
        for m in moves_made:
            print(f"  - {m}")
        print()
    
    print("✅ Test completato!")
