from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uvicorn
import logging
import json
import time
import os

# Import internal logic
from scopa_core import GameState, PlayerState, Card, Suit, calculate_scores, Score, create_deck
from scopa_ai import ScopaBot

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ScopaServer")

app = FastAPI(title="Scopa Bot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- PERSISTENT DIARY (REAL-TIME SAVE) ---
DIARY_DIR = "game_diaries"
DIARY_INDEX = "game_diary.json"  # Keep for backward compatibility

def ensure_diary_dir():
    """Ensure diary directory exists."""
    if not os.path.exists(DIARY_DIR):
        os.makedirs(DIARY_DIR)

def get_current_game_path(game_id):
    """Get path for current game's diary file."""
    ensure_diary_dir()
    return os.path.join(DIARY_DIR, f"game_{game_id}.json")

def save_game_realtime(game_id, game_data):
    """Save game data immediately (called after each move)."""
    filepath = get_current_game_path(game_id)
    with open(filepath, "w") as f:
        json.dump(game_data, f, indent=2)
    logger.info(f"Game {game_id} saved to {filepath}")

def load_diary():
    """Load all games from individual files for backward compatibility."""
    ensure_diary_dir()
    games = []
    
    # Load from individual game files
    for filename in sorted(os.listdir(DIARY_DIR), reverse=True):
        if filename.startswith("game_") and filename.endswith(".json"):
            try:
                with open(os.path.join(DIARY_DIR, filename), "r") as f:
                    game_data = json.load(f)
                    games.append(game_data)
            except:
                pass
    
    # Also load from old monolithic file if exists
    if os.path.exists(DIARY_INDEX):
        try:
            with open(DIARY_INDEX, "r") as f:
                old_diary = json.load(f)
                # Add old games that aren't already in games list
                old_ids = {g.get("game_id") for g in games}
                for g in old_diary.get("games", []):
                    if g.get("game_id") not in old_ids:
                        games.append(g)
        except:
            pass
    
    return {"games": games}

def save_to_diary(entry):
    """Legacy function - now saves to individual file."""
    save_game_realtime(entry.get("game_id", int(time.time())), entry)

# --- SESSION MANAGEMENT ---
game_counter = 0

class GameSession:
    def __init__(self):
        self.bot = ScopaBot()
        self.seen_cards = set()
        self.dead_cards = set()
        self.move_history = []  # Current game log
        self.last_table_count = None
        self.last_table_state: List[Card] = []  # Full table state for tracking changes
        
        # SCORE TRACKING
        self.my_captures: List[Card] = []
        self.opp_captures: List[Card] = []
        self.my_scope: int = 0
        self.opp_scope: int = 0
        
        self.game_id = int(time.time())
        self.last_reset_time = 0  # Track when last reset happened for cooldown
        
    def reset(self):
        global game_counter
        # Save current game to diary before reset
        if self.move_history:
            save_to_diary({
                "game_id": self.game_id,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "moves": self.move_history,
                "total_moves": len(self.move_history),
                "final_memory": len(self.seen_cards)
            })
            logger.info(f"Game {self.game_id} saved to diary ({len(self.move_history)} moves)")
        
        self.bot = ScopaBot()
        self.seen_cards = set()
        self.dead_cards = set()
        self.move_history = []
        self.last_table_state: List[Card] = []  # Full table state for tracking changes
        
        # SCORE TRACKING
        self.my_captures: List[Card] = []
        self.opp_captures: List[Card] = []
        self.my_scope: int = 0
        self.opp_scope: int = 0
        
        game_counter += 1
        self.game_id = int(time.time())
        logger.info(f"SESSION RESET: New Game ID {self.game_id}")

    def update_dead_cards(self, played_card: Card, captured_cards: List[Card]):
        """Mark cards as 'dead' (removed from play)."""
        if played_card: self.dead_cards.add(played_card)
        for c in captured_cards:
            self.dead_cards.add(c)

    def check_auto_reset(self, current_visible: List[Card]) -> bool:
        """
        Check if multiple visible cards are in 'dead_cards'.
        Requires 2+ dead cards AND 30s cooldown to avoid spurious resets.
        """
        # Cooldown: Don't reset within 30 seconds of last reset
        MIN_RESET_INTERVAL = 30
        time_since_reset = time.time() - self.last_reset_time
        if time_since_reset < MIN_RESET_INTERVAL:
            return False
        
        # Count how many visible cards are "dead"
        dead_visible = [c for c in current_visible if c in self.dead_cards]
        
        # Require at least 2 dead cards to trigger reset (avoids DOM glitches)
        MIN_DEAD_FOR_RESET = 2
        if len(dead_visible) >= MIN_DEAD_FOR_RESET:
            logger.warning(f"AUTO-RESET TRIGGER: Found {len(dead_visible)} dead cards: {dead_visible[:3]}... (Total dead: {len(self.dead_cards)})")
            self.last_reset_time = time.time()
            return True
        
        return False

    def update_memory(self, visible_cards: List[Card]):
        added = []
        for c in visible_cards:
            if c not in self.seen_cards:
                self.seen_cards.add(c)
                added.append(str(c))
        # Sync with bot's internal memory (CardMemory uses 'seen' not 'seen_cards')
        self.bot.memory.seen = self.seen_cards.copy()
        return added
        
# --- SERVER STATE ---
sessions: Dict[str, GameSession] = {}

def get_session(session_id: str) -> GameSession:
    """Retrieve or create a session for the given ID."""
    if not session_id:
        return None # Should handle default/legacy case?
        
    if session_id not in sessions:
        logger.info(f"Creating NEW session for ID: {session_id}")
        sessions[session_id] = GameSession()
    return sessions[session_id]

def cleanup_sessions():
    """Remove old sessions to prevent memory leaks (optional, simple implementation)."""
    # For now, just keep them. In production, check timestamp.
    pass

# --- HELPERS ---
def parse_card(code: str) -> Card:
    code = code.lower().strip()
    if len(code) < 2: raise ValueError(f"Invalid card code: {code}")
    s_char = code[-1]
    val_str = code[:-1]
    try: val = int(val_str)
    except: val = 0
    if s_char == 'd': suit = Suit.DENARI
    elif s_char == 'c': suit = Suit.COPPE
    elif s_char == 's': suit = Suit.SPADE
    elif s_char == 'b': suit = Suit.BASTONI
    else: raise ValueError(f"Invalid suit char: {s_char}")
    return Card(suit, val)

def card_to_str(card: Card) -> str:
    s_char = ""
    if card.suit == Suit.DENARI: s_char = "d"
    elif card.suit == Suit.COPPE: s_char = "c"
    elif card.suit == Suit.SPADE: s_char = "s"
    elif card.suit == Suit.BASTONI: s_char = "b"
    return f"{card.value}{s_char}"

# --- MODELS ---
class GameStateRequest(BaseModel):
    session_id: str = "default"  # ADDED: Unique ID for the browser tab/window
    hand: List[str]
    table: List[str]
    seen_history: List[str] = [] 
    my_score_cards: int = 0
    opp_score_cards: int = 0
    # NEW METADATA
    my_score_match: int = 0
    opp_score_match: int = 0
    dealer: str = "unknown" # me, opp, unknown
    last_action_desc: str = "None"
    # DOM Score details (v1.2)
    my_score_details: Optional[Dict[str, int]] = None
    opp_score_details: Optional[Dict[str, int]] = None
    # Opponent's last move tracking (v1.2)
    opponent_last_move: Optional[Dict[str, Any]] = None

class MoveResponse(BaseModel):
    card_played: str
    is_capture: bool
    description: str
    reasoning: List[str] = []
    score_summary: Dict[str, Any] = None

# --- ENDPOINTS ---

@app.get("/")
def health_check():
    return {"status": "ok", "active_sessions": len(sessions), "server": "v12.6 MULTI-SESSION"}

class ResetRequest(BaseModel):
    session_id: str = "default"

@app.post("/reset")
def reset_game(req: ResetRequest = ResetRequest()): 
    """Reset game memory for a session. Accepts JSON body with session_id or nothing."""
    sid = req.session_id
    session = get_session(sid)
    session.reset()
    logger.info(f"SESSION RESET: {sid} - New game ID {session.game_id}")
    return {"status": "memory_cleared", "new_game_id": session.game_id, "session_id": sid}

@app.get("/history")
def get_history():
    # This endpoint needs to be updated to take a session_id, but the instruction does not include it.
    # For now, it will implicitly use the 'default' session if not explicitly handled.
    session = get_session("default") # Assuming default for now, or it will error if 'session' is not defined.
    return JSONResponse(content=session.move_history)

@app.get("/diary")
def get_diary():
    """Returns all saved games from diary"""
    return JSONResponse(content=load_diary())

@app.get("/diary_viewer", response_class=HTMLResponse)
def diary_viewer():
    return """
    <html>
    <head>
        <title>Scopa Bot Diary</title>
        <style>
            body { font-family: monospace; background: #1a1a1a; color: #eee; padding: 20px; }
            .container { display: flex; gap: 20px; }
            .sidebar { width: 300px; background: #2a2a2a; padding: 10px; height: 90vh; overflow-y: auto; }
            .content { flex: 1; background: #222; padding: 20px; height: 90vh; overflow-y: auto; }
            .game-item { padding: 10px; border-bottom: 1px solid #444; cursor: pointer; }
            .game-item:hover { background: #333; }
            .game-item.active { background: #004400; border-left: 4px solid #0f0; }
            .move-card { background: #333; margin-bottom: 10px; padding: 10px; border-radius: 5px; }
            .cards { display: flex; gap: 5px; margin: 5px 0; }
            .card { background: white; color: black; padding: 2px 5px; border-radius: 3px; font-weight: bold; }
            .denari { color: #d4af37; } 
            .coppe { color: #b22222; }
            .bastoni { color: #006400; }
            .spade { color: #00008b; }
            h1 { color: #0f0; margin-top:0; }
        </style>
        <script>
            let diaryData = null;

            async function loadDiary() {
                const res = await fetch('/diary');
                const data = await res.json();
                diaryData = data.games.reverse();
                renderSidebar();
            }

            function renderSidebar() {
                const sb = document.getElementById('sidebar');
                sb.innerHTML = '';
                diaryData.forEach((game, idx) => {
                    const div = document.createElement('div');
                    div.className = 'game-item';
                    div.innerHTML = `
                        <div><b>Game #${game.game_id}</b></div>
                        <div style="font-size:12px; color:#aaa">${game.timestamp || 'N/A'}</div>
                        <div style="font-size:12px">Moves: ${game.total_moves} | Final Mem: ${game.final_memory}/40</div>
                    `;
                    div.onclick = () => showGame(game, div);
                    sb.appendChild(div);
                });
            }

            function formatCard(code) {
                const suit = code.slice(-1);
                const val = code.slice(0,-1);
                let colorClass = '';
                if(suit==='d') colorClass='denari';
                if(suit==='c') colorClass='coppe';
                if(suit==='b') colorClass='bastoni';
                if(suit==='s') colorClass='spade';
                return `<span class="card \${colorClass}">\${val}\${suit.toUpperCase()}</span>`;
            }

            function showGame(game, el) {
                document.querySelectorAll('.game-item').forEach(d => d.classList.remove('active'));
                el.classList.add('active');
                
                const c = document.getElementById('content');
                let html = `<h1>Game #${game.game_id}</h1>`;
                html += `<h3>Replay (${game.total_moves} moves)</h3>`;
                
                game.moves.forEach(m => {
                    const hand = m.request.hand.map(formatCard).join(' ');
                    const table = m.request.table.map(formatCard).join(' ');
                    const dec = m.decision ? m.decision.description : 'ERROR';
                    const mem = m.memory_after || '?';
                    
                    html += `
                    <div class="move-card">
                        <div style="color:#aaa; font-size:12px;">Move ${m.move_number} | Mem: ${mem}/40</div>
                        <div style="margin:5px 0;">✋ <b>Hand:</b> <span class="cards">${hand}</span></div>
                        <div style="margin:5px 0;">🟩 <b>Table:</b> <span class="cards">${table}</span></div>
                        <div style="margin-top:5px; border-top:1px solid #444; padding-top:5px;">
                            🤖 <b>Action:</b> <span style="color:#0f0; font-weight:bold;">${dec}</span>
                        </div>
                    </div>`;
                });
                c.innerHTML = html;
            }
            
            window.onload = loadDiary;
        </script>
    </head>
    <body>
        <div class="container">
            <div id="sidebar" class="sidebar">Loading...</div>
            <div id="content" class="content">Select a game to view details...</div>
        </div>
    </body>
    </html>
    """

@app.get("/memory_state")
def get_memory_state(sid: str = "default"):
    s = get_session(sid)
    return {
        "seen_count": len(s.seen_cards),
        "seen_list": sorted([str(c) for c in s.seen_cards]),
        "remaining_unknown": 40 - len(s.seen_cards),
        "session_id": sid
    }

@app.post("/next_move", response_model=MoveResponse)
def get_next_move(req: GameStateRequest):
    sid = req.session_id
    current_session = get_session(sid)
    
    print(f"\n[MOVE] 🔵 Session={sid} | Score={req.my_score_match}-{req.opp_score_match}")
    print(f"       🃏 Hand: {req.hand} | Table: {req.table}")

    log_entry = {
        "timestamp": time.time(),
        "move_number": len(current_session.move_history) + 1,
        "request": req.dict(),
        "memory_before": len(current_session.seen_cards),
        "decision": None,
        "all_moves_evaluated": [], 
        "ai_context": {},
        "error": None,
        "session_id": sid
    }
    
    try:
        hand_cards = [parse_card(c) for c in req.hand]
        table_cards = [parse_card(c) for c in req.table]
        
        # Note: AUTO-RESET removed - use manual RESET button if needed
        history_cards = [parse_card(c) for c in req.seen_history]
        
        # UPDATE SESSION MEMORY
        newly_seen = current_session.update_memory(hand_cards + table_cards + history_cards)
        log_entry["newly_seen"] = len(newly_seen)
        log_entry["memory_after"] = len(current_session.seen_cards)
        
        # === STATEFUL SCORE TRACKING: INFER OPPONENT ACTION ===
        if current_session.last_table_state:
            # Check what cards disappeared from the previous table state
            prev_table_codes = {str(c) for c in current_session.last_table_state}
            curr_table_codes = {str(c) for c in table_cards}
            
            missing_from_table = []
            for c in current_session.last_table_state:
                if str(c) not in curr_table_codes:
                    missing_from_table.append(c)
            
            # If cards are missing, opponent captured them!
            # (ignoring dealing phase where table resets or grows)
            if missing_from_table:
                # We simply attribute missing cards to opponent captures
                current_session.opp_captures.extend(missing_from_table)
                logger.info(f"Infer Opponent Capture: {missing_from_table}")
                
                # FIX 1: Also track opponent's played card from DOM tracking
                if req.opponent_last_move and req.opponent_last_move.get('type') == 'capture':
                    opp_card_code = req.opponent_last_move.get('cardPlayed')
                    if opp_card_code and opp_card_code != 'unknown':
                        try:
                            opp_card = parse_card(opp_card_code)
                            if opp_card not in current_session.opp_captures:
                                current_session.opp_captures.append(opp_card)
                                logger.info(f"FIX1: Added opponent's played card: {opp_card}")
                        except:
                            pass
                
                # Check for SCOPA by Opponent
                # If table is empty now, but wasn't before
                if not table_cards and current_session.last_table_state:
                     # Check if 'scopa' mentioned in last action description
                     if "scopa" in req.last_action_desc.lower() or "capture" in req.last_action_desc.lower():
                         # Heuristic: likely a scopa if table cleared
                         current_session.opp_scope += 1
                         logger.info("Infer Opponent SCOPA!")
        
        # DEBUG: Verify bot memory sync
        eights_in_memory = sum(1 for c in current_session.bot.memory.seen if c.value == 8)
        logger.info(f"DEBUG: Sess={len(current_session.seen_cards)}, BotMem={len(current_session.bot.memory.seen)}")
        
        dummy_player = PlayerState(hand=hand_cards)
        dummy_opp = PlayerState(hand=[]) 
        
        # FIX 2: Use actual unseen cards instead of repeating same card
        all_cards = set(create_deck())
        seen_set = current_session.seen_cards | set(hand_cards) | set(table_cards)
        unseen_cards = list(all_cards - seen_set)
        mock_deck = unseen_cards  # Use real unseen cards
        
        state = GameState(
            table=table_cards,
            players=(
                PlayerState(hand=hand_cards, captured=current_session.my_captures, scope=current_session.my_scope), 
                PlayerState(hand=[], captured=current_session.opp_captures, scope=current_session.opp_scope)
            ),
            deck=mock_deck,
            current_player=0,
            last_capturer=None
        )
        
        # --- BOT DECISION ---
        # Get ALL evaluations for logging
        all_evals = current_session.bot.get_all_evaluations(state, match_score=(req.my_score_match, req.opp_score_match), dealer=req.dealer)
        
        # Transform all_evals for log_entry["all_moves_evaluated"]
        transformed_evals = []
        for ev in all_evals:
            move_data = {
                "move": str(ev["move"]),
                "score": ev["score"],
                "reasons": ev["reasons"],
                "card": card_to_str(ev["move"].card_played),
                "captured": [card_to_str(c) for c in ev["move"].cards_captured] if ev["move"].is_capture else [],
                "is_scopa": ev["move"].is_scopa
            }
            
            # Get AI context from first evaluation
            if not log_entry["ai_context"] and ev.get("context"):
                log_entry["ai_context"] = ev["context"]
        
        # BOT DECISION - Monte Carlo ENABLED for better decisions (v12.1)
        move = current_session.bot.choose_move(
            state, 
            use_monte_carlo=True,  # ENABLED - +10% win rate vs Pro!
            mc_simulations=100,    # 100 sims = optimal (tested: 62.6% vs Pro)
            match_score=(req.my_score_match, req.opp_score_match),
            dealer=req.dealer,
            last_action_desc=req.last_action_desc
        )
        
        if not move:
            raise HTTPException(status_code=400, detail="No valid moves found")
            
        # UPDATE DEAD CARDS (for Auto-Reset logic)
        current_session.update_dead_cards(move.card_played, move.cards_captured)
        
        # 3. Track My Capture
        if move.is_capture:
            # Add captured cards + played card to my captures
            captured_bunch = list(move.cards_captured) + [move.card_played]
            current_session.my_captures.extend(captured_bunch)
            if move.is_scopa:
                current_session.my_scope += 1
                logger.info("Bot SCOPA!")
        
        # 4. Update Final Table State (after my move)
        # This will be 'last_table_state' for the NEXT turn
        table_after_my_move = [c for c in table_cards if c not in move.cards_captured]
        if not move.is_capture:
            table_after_my_move.append(move.card_played)
        
        current_session.last_table_state = table_after_my_move
        
        # 5. Use DOM Score (v1.2) - More accurate than internal calculation
        # The DOM updates live during the game
        if req.my_score_details and req.opp_score_details:
            my_total = req.my_score_details.get("totale", 0)
            opp_total = req.opp_score_details.get("totale", 0)
            my_details = req.my_score_details
            opp_details = req.opp_score_details
            
            score_summary = {
                "my": my_total,
                "opp": opp_total,
                "details": f"Me: S{my_details.get('settebello',0)} D{my_details.get('denari',0)} C{my_details.get('carte',0)} | Opp: S{opp_details.get('settebello',0)} D{opp_details.get('denari',0)} C{opp_details.get('carte',0)}"
            }
        else:
            # Fallback to internal calculation if DOM data not available
            score_state = GameState(
                players=(
                    PlayerState(captured=current_session.my_captures, scope=current_session.my_scope),
                    PlayerState(captured=current_session.opp_captures, scope=current_session.opp_scope)
                )
            )
            my_score_obj, opp_score_obj = calculate_scores(score_state)
            
            score_summary = {
                "my": my_score_obj.total,
                "opp": opp_score_obj.total,
                "details": f"Me: {my_score_obj} | Opp: {opp_score_obj}"
            }
            
        logger.info(f"Game {current_session.game_id} | Move {log_entry['move_number']}: {move} | Mem={len(current_session.seen_cards)} | Dead={len(current_session.dead_cards)}")
        
        # Find reasoning for the chosen move
        chosen_reasons = []
        chosen_str = str(move)
        for ev in all_evals:
            # Match by string description to be safe
            if str(ev["move"]) == chosen_str:
                chosen_reasons = ev["reasons"]
                break
        
        response = MoveResponse(
            card_played=card_to_str(move.card_played),
            is_capture=move.is_capture,
            description=str(move),
            reasoning=chosen_reasons,
            score_summary=score_summary
        )
        
        log_entry["decision"] = response.dict()
        current_session.move_history.append(log_entry)
        
        # === SAVE GAME IMMEDIATELY (REAL-TIME) ===
        save_game_realtime(current_session.game_id, {
            "game_id": current_session.game_id,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "moves": current_session.move_history,
            "total_moves": len(current_session.move_history),
            "current_memory": len(current_session.seen_cards),
            "status": "in_progress"
        })
        
        # Update last table count
        captured_count = len(move.cards_captured)
        if move.is_capture:
             current_session.last_table_count = len(table_cards) - captured_count
        else:
             current_session.last_table_count = len(table_cards) + 1
        
        return response
        
    except Exception as e:
        logger.error(f"Error: {e}")
        log_entry["error"] = str(e)
        current_session.move_history.append(log_entry)
        
        # Save even on error
        save_game_realtime(current_session.game_id, {
            "game_id": current_session.game_id,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "moves": current_session.move_history,
            "total_moves": len(current_session.move_history),
            "current_memory": len(current_session.seen_cards),
            "status": "error"
        })
        
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    # 0.0.0.0 = accessible from any device on the network
    uvicorn.run(app, host="0.0.0.0", port=8000)
