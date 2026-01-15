"""
Scopa Game Diary - Sistema di logging dettagliato delle partite

Questo modulo implementa:
- DiaryEntry: registra una singola mossa con stato completo
- GameDiary: contiene tutte le entry di una partita
- Funzioni per salvare/caricare diary in formato JSON
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any
from datetime import datetime
import json
import os


def card_to_str(card) -> str:
    """Converte una Card in stringa leggibile (es: '7d', '1c')."""
    suit_map = {'denari': 'd', 'coppe': 'c', 'spade': 's', 'bastoni': 'b'}
    return f"{card.value}{suit_map.get(card.suit.value, '?')}"


def cards_to_str(cards: List) -> List[str]:
    """Converte lista di Card in lista di stringhe."""
    return [card_to_str(c) for c in cards]


@dataclass
class MoveEvaluation:
    """Valutazione di una singola mossa."""
    move_description: str  # es: "7d prende 1d+6b"
    score: int
    reasons: List[str]
    card_played: str
    cards_captured: List[str]
    is_scopa: bool
    
    def to_dict(self) -> Dict:
        return {
            "move": self.move_description,
            "score": self.score,
            "reasons": self.reasons,
            "card": self.card_played,
            "captured": self.cards_captured,
            "is_scopa": self.is_scopa
        }


@dataclass
class DiaryEntry:
    """Una singola mossa nel diario."""
    turn: int
    player: str  # "bot" o "opponent"
    deck_remaining: int
    hand_before: List[str]
    table_before: List[str]
    opp_hand_size: int  # Numero carte in mano avversario (non vediamo le sue)
    
    # Mossa giocata
    move_played: Dict  # {card, captured, is_scopa, description}
    table_after: List[str]
    
    # Solo per il bot: tutte le mosse valutate
    all_moves_evaluated: List[Dict] = field(default_factory=list)
    
    # Contesto AI (solo per bot)
    ai_context: Dict = field(default_factory=dict)  # {phase, style, advantage}
    
    # Punteggi stimati correnti
    scores_current: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "turn": self.turn,
            "player": self.player,
            "deck_remaining": self.deck_remaining,
            "hand_before": self.hand_before,
            "table_before": self.table_before,
            "opp_hand_size": self.opp_hand_size,
            "move_played": self.move_played,
            "table_after": self.table_after,
            "all_moves": self.all_moves_evaluated,
            "ai_context": self.ai_context,
            "scores_current": self.scores_current
        }


@dataclass
class GameDiary:
    """Diario completo di una partita."""
    game_id: str
    timestamp: str
    bot_player: int  # 0 o 1
    opponent_type: str
    entries: List[DiaryEntry] = field(default_factory=list)
    final_result: Dict = field(default_factory=dict)
    
    def add_entry(self, entry: DiaryEntry):
        """Aggiunge una mossa al diario."""
        self.entries.append(entry)
    
    def set_final_result(self, bot_score, opp_score, last_capturer: Optional[int]):
        """Imposta il risultato finale."""
        self.final_result = {
            "bot_score": {
                "cards": bot_score.cards,
                "denari": bot_score.denari,
                "settebello": bot_score.settebello,
                "primiera": bot_score.primiera,
                "scope": bot_score.scope,
                "total": bot_score.total
            },
            "opp_score": {
                "cards": opp_score.cards,
                "denari": opp_score.denari,
                "settebello": opp_score.settebello,
                "primiera": opp_score.primiera,
                "scope": opp_score.scope,
                "total": opp_score.total
            },
            "winner": "bot" if bot_score.total > opp_score.total else (
                "opp" if opp_score.total > bot_score.total else "draw"
            ),
            "last_capturer": "bot" if last_capturer == self.bot_player else (
                "opp" if last_capturer is not None else "none"
            )
        }
    
    def to_dict(self) -> Dict:
        return {
            "game_id": self.game_id,
            "timestamp": self.timestamp,
            "bot_player": self.bot_player,
            "opponent_type": self.opponent_type,
            "entries": [e.to_dict() for e in self.entries],
            "final_result": self.final_result
        }
    
    def save(self, directory: str = ".tmp/game_diaries") -> str:
        """Salva il diario in un file JSON."""
        os.makedirs(directory, exist_ok=True)
        filename = f"{self.game_id}.json"
        filepath = os.path.join(directory, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        
        return filepath
    
    def format_for_review(self) -> str:
        """Formatta il diario per revisione umana."""
        lines = []
        lines.append(f"=" * 60)
        lines.append(f"DIARIO PARTITA: {self.game_id}")
        lines.append(f"Data: {self.timestamp}")
        lines.append(f"Bot: P{self.bot_player} vs {self.opponent_type}")
        lines.append(f"=" * 60)
        
        for entry in self.entries:
            lines.append("")
            lines.append(f"--- Turno {entry.turn} ({entry.player.upper()}) ---")
            lines.append(f"Mazzo: {entry.deck_remaining} | Tavolo: {entry.table_before}")
            
            if entry.player == "bot":
                lines.append(f"Mano: {entry.hand_before}")
                
                # Mosse valutate
                if entry.all_moves_evaluated:
                    lines.append("Mosse valutate:")
                    for m in sorted(entry.all_moves_evaluated, key=lambda x: x.get('score', 0), reverse=True):
                        reasons_str = ", ".join(m.get('reasons', [])) or "-"
                        lines.append(f"  [{m.get('score', 0):+5d}] {m.get('move', '?')} → {reasons_str}")
                
                # Contesto AI
                if entry.ai_context:
                    ctx = entry.ai_context
                    lines.append(f"AI: fase={ctx.get('phase')}, stile={ctx.get('style')}, vantaggio={ctx.get('advantage', 0):+.1f}")
            else:
                lines.append(f"Mano avversario: {entry.opp_hand_size} carte")
            
            # Mossa giocata
            move = entry.move_played
            if move.get('captured'):
                lines.append(f"→ GIOCA: {move.get('card')} prende {move.get('captured')}" + 
                           (" SCOPA!" if move.get('is_scopa') else ""))
            else:
                lines.append(f"→ GIOCA: {move.get('card')} (scarta)")
            
            lines.append(f"Tavolo dopo: {entry.table_after}")
        
        # Risultato finale
        lines.append("")
        lines.append("=" * 60)
        lines.append("RISULTATO FINALE")
        lines.append("=" * 60)
        
        if self.final_result:
            bs = self.final_result.get('bot_score', {})
            os = self.final_result.get('opp_score', {})
            lines.append(f"Bot:  carte={bs.get('cards')}, denari={bs.get('denari')}, "
                        f"7bello={bs.get('settebello')}, primiera={bs.get('primiera')}, "
                        f"scope={bs.get('scope')} → TOTALE: {bs.get('total')}")
            lines.append(f"Opp:  carte={os.get('cards')}, denari={os.get('denari')}, "
                        f"7bello={os.get('settebello')}, primiera={os.get('primiera')}, "
                        f"scope={os.get('scope')} → TOTALE: {os.get('total')}")
            lines.append(f"Vincitore: {self.final_result.get('winner', '?').upper()}")
            lines.append(f"Ultima presa: {self.final_result.get('last_capturer', '?')}")
        
        return "\n".join(lines)


def load_diary(filepath: str) -> GameDiary:
    """Carica un diario da file JSON."""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    diary = GameDiary(
        game_id=data['game_id'],
        timestamp=data['timestamp'],
        bot_player=data['bot_player'],
        opponent_type=data['opponent_type']
    )
    
    for e in data.get('entries', []):
        entry = DiaryEntry(
            turn=e['turn'],
            player=e['player'],
            deck_remaining=e['deck_remaining'],
            hand_before=e['hand_before'],
            table_before=e['table_before'],
            opp_hand_size=e.get('opp_hand_size', 0),
            move_played=e['move_played'],
            table_after=e['table_after'],
            all_moves_evaluated=e.get('all_moves', []),
            ai_context=e.get('ai_context', {}),
            scores_current=e.get('scores_current', {})
        )
        diary.entries.append(entry)
    
    diary.final_result = data.get('final_result', {})
    return diary


def create_game_diary(bot_player: int, opponent_type: str) -> GameDiary:
    """Crea un nuovo diario di partita."""
    now = datetime.now()
    game_id = now.strftime("%Y-%m-%d_%H-%M-%S")
    timestamp = now.isoformat()
    
    return GameDiary(
        game_id=game_id,
        timestamp=timestamp,
        bot_player=bot_player,
        opponent_type=opponent_type
    )


# === HELPER per integrazione con simulator ===

def create_move_description(move) -> str:
    """Crea descrizione testuale della mossa."""
    card = card_to_str(move.card_played)
    if move.is_capture:
        captured = "+".join(cards_to_str(move.cards_captured))
        desc = f"{card} prende {captured}"
        if move.is_scopa:
            desc += " SCOPA!"
        return desc
    else:
        return f"{card} scarta"


def create_move_dict(move) -> Dict:
    """Crea dizionario della mossa per il diary."""
    return {
        "card": card_to_str(move.card_played),
        "captured": cards_to_str(move.cards_captured) if move.is_capture else [],
        "is_scopa": move.is_scopa,
        "description": create_move_description(move)
    }


def estimate_current_scores(state, bot_player: int) -> Dict:
    """Stima punteggi correnti durante la partita."""
    bot = state.players[bot_player]
    opp = state.players[1 - bot_player]
    
    def player_stats(p):
        return {
            "cards": len(p.captured),
            "denari": sum(1 for c in p.captured if c.is_denaro),
            "sevens": sum(1 for c in p.captured if c.value == 7),
            "settebello": 1 if any(c.is_settebello for c in p.captured) else 0,
            "scope": p.scope
        }
    
    return {
        "bot": player_stats(bot),
        "opp": player_stats(opp)
    }
