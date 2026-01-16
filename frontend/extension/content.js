/**
 * Scopa Bot - Content Script V12.20 (DEALER FIX)
 * Features:
 * - HUD always visible
 * - No console logs (by default)
 * - Randomized timing
 * - Human-like click simulation
 * - Server calculates score (more reliable than DOM parsing)
 * - Enhanced Dealer Detection (Relative Position)
 */


// ==================== STEALTH CONFIG ====================
const STEALTH = {
    enabled: true,                   // Master stealth switch
    removeBorders: true,             // Remove card highlighting borders
    hudVisible: true,                // HUD always visible
    // toggleKey removed - HUD stays fixed
    minDelay: 800,                  // Min ms before action
    maxDelay: 2500,                 // Max ms before action  
    clickVariance: 50,              // Pixel variance for clicks
    enableLogs: false,              // Disable all console output
    humanizeClicks: true            // Add mouse movement simulation
};

// Stealth logger (only logs if enabled)
const log = (...args) => {
    if (STEALTH.enableLogs) console.log('[ScopaBot]', ...args);
};

// Random delay generator (human-like)
function randomDelay(min = STEALTH.minDelay, max = STEALTH.maxDelay) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
}

// Random variance for coordinates
function addVariance(value, variance = STEALTH.clickVariance) {
    return value + (Math.random() - 0.5) * variance;
}

// ==================== CARD MAPPER ====================
class CardMapper {
    static getCode(fileId) {
        const id = parseInt(fileId);
        if (isNaN(id)) return "unknown";
        let suit = "";
        let val = 0;
        if (id >= 1 && id <= 10) { suit = "c"; val = id; }
        else if (id >= 11 && id <= 20) { suit = "d"; val = id - 10; }
        else if (id >= 21 && id <= 30) { suit = "b"; val = id - 20; }
        else if (id >= 31 && id <= 40) { suit = "s"; val = id - 30; }
        else return "unknown";
        return `${val}${suit}`;
    }
}

// ==================== STATE & OBSERVER ====================
const globalSeenBuffer = new Set();
let currentHand = [];
let currentTable = [];
let previousHand = [];
let previousTable = [];
let gameScore = { my: 0, opp: 0 };
let dealer = "unknown";
let lastAction = "None";

// v12.12: Auto-reset tracking (DISABLED per user request)
// let wasGameActive = false;
// let noCardsCounter = 0;
// let hasAutoReset = false;

const observer = new MutationObserver((mutations) => {
    mutations.forEach(mutation => {
        mutation.addedNodes.forEach(node => {
            if (node.nodeType === 1) {
                const imgs = node.tagName === "IMG" ? [node] : node.querySelectorAll("img");
                imgs.forEach(scanImage);
            }
        });
        if (mutation.type === "attributes" && mutation.attributeName === "src") {
            scanImage(mutation.target);
        }
    });
});

function scanImage(img) {
    if (!img.src) return;
    if (img.offsetParent === null) return;
    if (img.src.includes("dorso") || img.src.includes("back")) return;
    const match = img.src.match(/(\d+)\.svg/);
    if (!match) return;
    const code = CardMapper.getCode(match[1]);
    if (code !== "unknown") {
        globalSeenBuffer.add(code);
    }
}

// Wait for document.body to exist before observing
function startObserver() {
    if (document.body) {
        observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ["src"] });
    } else {
        // Body not ready yet, wait and retry
        setTimeout(startObserver, 50);
    }
}
startObserver();

// ==================== GAME SCANNER ====================
function scanGame() {
    const hand = [];
    const table = [];
    const viewportHeight = window.innerHeight;  // FIX 3: Use viewport percentages

    document.querySelectorAll('div[id^="carta_mazzo_"]').forEach(div => {
        const topVal = parseInt((div.style.top || "").replace("px", ""));
        if (isNaN(topVal)) return;
        const img = div.querySelector("img");
        if (!img || img.offsetParent === null) return;
        if (img.src.includes("dorso")) return;

        const match = img.src.match(/(\d+)\.svg/);
        if (!match) return;
        const code = CardMapper.getCode(match[1]);
        if (code === "unknown") return;

        // STEALTH: Store code in data attribute but NO visual border
        div.setAttribute("data-scopabot-code", code);

        // STEALTH: Remove any existing borders we may have added
        if (STEALTH.removeBorders) {
            div.style.border = "";
        }

        // FIX 3: Use viewport percentage thresholds instead of fixed pixels
        // This works across different screen resolutions
        const topPercent = (topVal / viewportHeight) * 100;

        if (topPercent > 60) hand.push(code);           // Bottom 40% = hand
        else if (topPercent > 30 && topPercent < 55) table.push(code);  // Middle area = table
    });


    if (previousHand.length > 0 || previousTable.length > 0) {
        inferStateChanges(hand, table);
    }

    previousHand = currentHand;
    previousTable = currentTable;
    currentHand = hand;
    currentTable = table;

    scanScores();
    detectDealer();
}

function inferStateChanges(newHand, newTable) {
    const cardsPlayed = currentHand.filter(x => !newHand.includes(x));

    if (cardsPlayed.length === 1) {
        // MY MOVE
        const card = cardsPlayed[0];
        const tableDiff = currentTable.length - newTable.length;
        if (tableDiff >= 0) {
            lastAction = `My Capture (${card})`;
        } else {
            lastAction = `My Discard (${card})`;
        }
    } else if (cardsPlayed.length === 0) {
        // OPPONENT MOVE - Enhanced tracking
        if (JSON.stringify(currentTable.sort()) !== JSON.stringify(newTable.sort())) {
            // Find cards that appeared on table (opponent's played card)
            const appearedCards = newTable.filter(x => !currentTable.includes(x));
            // Find cards that disappeared from table (captured)
            const disappearedCards = currentTable.filter(x => !newTable.includes(x));

            const tableDiff = currentTable.length - newTable.length;

            if (tableDiff > 0) {
                // OPPONENT CAPTURE
                // The appeared card is what opponent played (if visible)
                // The disappeared cards are what was captured
                const oppCard = appearedCards.length === 1 ? appearedCards[0] : "unknown";
                const captured = disappearedCards;

                // Store opponent move details for the bot
                opponentLastMove = {
                    type: 'capture',
                    cardPlayed: oppCard,
                    cardsCaptured: captured,
                    wasScopa: newTable.length === 0 && currentTable.length > 0,
                    timestamp: Date.now()
                };

                if (opponentLastMove.wasScopa) {
                    lastAction = `Opponent SCOPA! (${oppCard} took ${captured.join(', ')})`;
                } else {
                    lastAction = `Opponent Capture (${oppCard} took ${captured.join(', ')})`;
                }

                log('[OPP MOVE]', opponentLastMove);

            } else if (tableDiff < 0) {
                // OPPONENT DISCARD
                const card = appearedCards.length === 1 ? appearedCards[0] : "unknown";

                opponentLastMove = {
                    type: 'discard',
                    cardPlayed: card,
                    cardsCaptured: [],
                    wasScopa: false,
                    timestamp: Date.now()
                };

                lastAction = `Opponent Discard (${card})`;
                log('[OPP MOVE]', opponentLastMove);

            } else {
                lastAction = "Opponent Action";
            }
        }
    }
}

// Store opponent's last move for the bot
let opponentLastMove = null;

let lastServerScore = null; // Store realtime score from server

// Detailed score from DOM
let domScore = {
    my: { scope: 0, settebello: 0, carte: 0, denari: 0, primiera: 0, totale: 0 },
    opp: { scope: 0, settebello: 0, carte: 0, denari: 0, primiera: 0, totale: 0 }
};

function scanScores() {
    // === GOLDBET DOM SELECTORS ===
    // Read score directly from the game's score panel

    const getValue = (id) => {
        const el = document.getElementById(id);
        return el ? parseInt(el.textContent) || 0 : 0;
    };

    // My scores (Noi)
    domScore.my.scope = getValue('punteggi_scope_noi');
    domScore.my.settebello = getValue('punteggi_settebello_noi');
    domScore.my.carte = getValue('punteggi_carte_noi');
    domScore.my.denari = getValue('punteggi_denari_noi');
    domScore.my.primiera = getValue('punteggi_primiera_noi');
    domScore.my.totale = getValue('punteggi_totale_scopa_noi');

    // Opponent scores (Loro)
    domScore.opp.scope = getValue('punteggi_scope_loro');
    domScore.opp.settebello = getValue('punteggi_settebello_loro');
    domScore.opp.carte = getValue('punteggi_carte_loro');
    domScore.opp.denari = getValue('punteggi_denari_loro');
    domScore.opp.primiera = getValue('punteggi_primiera_loro');
    domScore.opp.totale = getValue('punteggi_totale_scopa_loro');

    // Update legacy gameScore for backward compatibility
    gameScore.my = domScore.my.totale;
    gameScore.opp = domScore.opp.totale;

    log('DOM Score:', domScore);
}

// v12.20: Enhanced Dealer Detection
// Uses relative position (half screen) instead of fixed pixels
// Persists dealer state when deck disappears (last round)
function detectDealer() {
    const mazzo = document.getElementById("carta_tallone_spessore");

    // If deck exists, update logic
    if (mazzo && mazzo.getBoundingClientRect().height > 0) {
        // Use getBoundingClientRect for absolute viewport position
        const rect = mazzo.getBoundingClientRect();
        const deckY = rect.top;
        const windowHeight = window.innerHeight;
        const threshold = windowHeight / 2;

        // Debug info for HUD
        window.dealerDebugInfo = `Y:${Math.round(deckY)}/${windowHeight}`;

        if (deckY < threshold) {
            // Deck is in TOP half -> Opponent is dealer -> I PLAY LAST
            if (dealer !== "opp") {
                dealer = "opp";
                log(`[DEALER] OPP is dealer (Deck Y=${Math.round(deckY)} < ${threshold}) -> I PLAY LAST`);
            }
        } else {
            // Deck is in BOTTOM half -> I am dealer -> OPP PLAYS LAST
            if (dealer !== "me") {
                dealer = "me";
                log(`[DEALER] ME am dealer (Deck Y=${Math.round(deckY)} >= ${threshold}) -> OPP PLAYS LAST`);
            }
        }
    } else {
        // Deck gone (last round) - keep existing dealer
        if (!window.dealerDebugInfo) window.dealerDebugInfo = "Deck Gone";
    }
}

// ==================== STEALTH HUD ====================
let hudElement = null;

function createHUD() {
    if (document.getElementById("scopabot-hud")) return;

    hudElement = document.createElement("div");
    hudElement.id = "scopabot-hud";

    // STEALTH: Hidden by default, minimal footprint
    hudElement.style.cssText = `
        position: fixed; top: 10px; right: 10px; width: 250px;
        background: rgba(0, 0, 0, 0.85); color: #0f0; 
        border: 2px solid #0f0; border-radius: 10px;
        font-family: monospace; font-size: 12px;
        padding: 10px; z-index: 100000; box-shadow: 0 0 15px rgba(0,0,0,0.5);
        display: ${STEALTH.hudVisible ? 'block' : 'none'};
    `;

    hudElement.innerHTML = `
        <div style="border-bottom:1px solid #444; padding-bottom:5px; margin-bottom:5px; font-weight:bold; display:flex; justify-content:space-between; align-items:center;">
            <span>🤖 SCOPABOT [STEALTH]</span>
            <button id="hud-close" style="background:none; border:none; color:#f00; font-size:16px; cursor:pointer; padding:0 5px;">✕</button>
        </div>
        <div style="font-size:10px; color:#888; margin-bottom:5px;">Press ${STEALTH.toggleKey} to toggle</div>
        <div>✋ Hand: <span id="hud-hand" style="color:white">--</span></div>
        <div>🟩 Table: <span id="hud-table" style="color:white">--</span></div>
        <div>🧠 Memory: <span id="hud-mem" style="color:yellow">--/40</span></div>
        <div id="hud-msg" style="margin-top:5px; color:#aaa; font-style:italic;">Ready</div>
        
        <div style="margin-top:8px; border-top:1px solid #444; padding-top:5px;">
            <div style="font-size:10px; color:#888; margin-bottom:3px;">📊 Carte Rimanenti:</div>
            <div id="card-grid" style="display:grid; grid-template-columns:repeat(10,1fr); gap:2px; font-size:9px; text-align:center;">
                <div>A</div><div>2</div><div>3</div><div>4</div><div>5</div><div>6</div><div>7</div><div>8</div><div>9</div><div>R</div>
                <div id="cnt-1" style="color:#0f0">4</div>
                <div id="cnt-2" style="color:#0f0">4</div>
                <div id="cnt-3" style="color:#0f0">4</div>
                <div id="cnt-4" style="color:#0f0">4</div>
                <div id="cnt-5" style="color:#0f0">4</div>
                <div id="cnt-6" style="color:#0f0">4</div>
                <div id="cnt-7" style="color:#ff0">4</div>
                <div id="cnt-8" style="color:#0f0">4</div>
                <div id="cnt-9" style="color:#0f0">4</div>
                <div id="cnt-10" style="color:#0f0">4</div>
            </div>
        </div>
        
        <div style="margin-top:5px; border-top:1px solid #444; padding-top:5px; font-size:10px; color:#aaa;">
            <div>🏆 Score: <span id="hud-score" style="color:white; font-weight:bold;">?-?</span></div>
            <div>🎩 Dealer: <span id="hud-dealer" style="color:white">?</span></div>
            <div>⚡ Action: <span id="hud-action" style="color:#ccc">--</span></div>
            <div style="margin-top:2px;">💡 Reason: <span id="hud-reason" style="color:#ff0; font-weight:bold;">-</span></div>
            <div style="margin-top:2px; font-size:9px; color:#666;">SID: <span id="hud-sid">--</span></div>
        </div>
        
        <div style="margin-top:10px; display:flex; gap:5px;">
            <button id="btn-play" style="flex:1; background:#006400; color:white; border:none; padding:5px; cursor:pointer;">PLAY MOVE</button>
            <button id="btn-reset" style="flex:1; background:#8b0000; color:white; border:none; padding:5px; cursor:pointer;">RESET</button>
        </div>
    `;
    document.body.appendChild(hudElement);

    // Draggable functionality
    let isDragging = false;
    let offsetX, offsetY;

    hudElement.addEventListener('mousedown', (e) => {
        if (e.target.tagName === 'BUTTON') return;
        isDragging = true;
        offsetX = e.clientX - hudElement.getBoundingClientRect().left;
        offsetY = e.clientY - hudElement.getBoundingClientRect().top;
        hudElement.style.cursor = 'grabbing';
    });

    document.addEventListener('mousemove', (e) => {
        if (!isDragging) return;
        hudElement.style.left = (e.clientX - offsetX) + 'px';
        hudElement.style.top = (e.clientY - offsetY) + 'px';
        hudElement.style.right = 'auto';
    });

    document.addEventListener('mouseup', () => {
        isDragging = false;
        hudElement.style.cursor = 'grab';
    });

    hudElement.style.cursor = 'grab';

    document.getElementById("btn-play").onclick = () => runBotStep();
    document.getElementById("btn-reset").onclick = () => doReset();
    document.getElementById("hud-close").onclick = () => {
        STEALTH.hudVisible = false;
        hudElement.style.display = 'none';
    };

    // Set Session ID
    const sidEl = document.getElementById("hud-sid");
    if (sidEl) sidEl.innerText = sessionId.substr(-4);
}

// STEALTH: Keyboard toggle for HUD
document.addEventListener('keydown', (e) => {
    if (e.key === STEALTH.toggleKey) {
        e.preventDefault();
        STEALTH.hudVisible = !STEALTH.hudVisible;
        if (hudElement) {
            hudElement.style.display = STEALTH.hudVisible ? 'block' : 'none';
        }
        log('HUD toggled:', STEALTH.hudVisible);
    }
});

function updateHUD() {
    if (!hudElement) createHUD();

    // Only update if visible (performance optimization)
    if (!STEALTH.hudVisible) return;

    const handEl = document.getElementById("hud-hand");
    const tableEl = document.getElementById("hud-table");
    const memEl = document.getElementById("hud-mem");
    const scoreEl = document.getElementById("hud-score");
    const dealerEl = document.getElementById("hud-dealer");
    const actionEl = document.getElementById("hud-action");

    if (handEl) handEl.innerText = currentHand.join(", ");
    if (tableEl) tableEl.innerText = currentTable.join(", ");
    if (memEl) {
        memEl.innerText = `${globalSeenBuffer.size} (Local)`;
    }
    if (scoreEl) {
        if (lastServerScore) {
            scoreEl.innerText = `${lastServerScore.my} - ${lastServerScore.opp}`;
            scoreEl.title = lastServerScore.details;
            scoreEl.style.color = "#0ff"; // Cyan for live score
        } else {
            scoreEl.innerText = `${gameScore.my} - ${gameScore.opp}`;
            scoreEl.title = "Match Score (scanned from page)";
            scoreEl.style.color = "white";
        }
    }

    // v12.20: Explicit Last Player + Debug Info
    if (dealerEl) {
        let dealerText = "Last: UNKNOWN";
        let color = "#fff";

        if (dealer === "me") {
            dealerText = "Last: OPP";
            color = "#fa0"; // Orange
        } else if (dealer === "opp") {
            dealerText = "Last: ME";
            color = "#0f0"; // Green
        }

        if (window.dealerDebugInfo) {
            dealerText += ` [${window.dealerDebugInfo}]`;
        }

        dealerEl.innerText = dealerText;
        dealerEl.style.color = color;
    }

    if (actionEl) actionEl.innerText = lastAction;

    updateCardGrid();
}

function updateCardGrid() {
    if (!STEALTH.hudVisible) return;

    const seenByValue = {};
    for (let v = 1; v <= 10; v++) seenByValue[v] = 0;

    globalSeenBuffer.forEach(code => {
        const val = parseInt(code.slice(0, -1));
        if (val >= 1 && val <= 10) seenByValue[val]++;
    });

    for (let v = 1; v <= 10; v++) {
        const remaining = 4 - seenByValue[v];
        const el = document.getElementById(`cnt-${v}`);

        if (el && el.style) {
            el.innerText = remaining;
            if (remaining === 0) {
                el.style.color = '#666';
            } else if (remaining <= 1) {
                el.style.color = '#f00';
            } else if (remaining <= 2) {
                el.style.color = '#ff0';
            } else {
                el.style.color = '#0f0';
            }
        }
    }
}

// ==================== HUMAN-LIKE CLICK SIMULATION ====================
function humanClick(element) {
    if (!element) return;

    const rect = element.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;

    // Add slight randomness to click position (human imprecision)
    const clickX = addVariance(centerX, 10);
    const clickY = addVariance(centerY, 10);

    // Create MouseEvent with realistic properties
    const mouseEventInit = {
        bubbles: true,
        cancelable: true,
        view: window,
        clientX: clickX,
        clientY: clickY,
        screenX: clickX + window.screenX,
        screenY: clickY + window.screenY,
        button: 0,
        buttons: 1,
        // IMPORTANT: These make it look more like a real event
        isTrusted: false, // We can't fake this, but other properties help
        pointerId: 1,
        pointerType: 'mouse',
        isPrimary: true
    };

    // Simulate natural mouse behavior: move -> down -> up -> click
    // With small random delays between each
    const moveEvent = new MouseEvent('mousemove', mouseEventInit);
    const enterEvent = new MouseEvent('mouseenter', mouseEventInit);
    const overEvent = new MouseEvent('mouseover', mouseEventInit);
    const downEvent = new MouseEvent('mousedown', mouseEventInit);
    const upEvent = new MouseEvent('mouseup', mouseEventInit);
    const clickEvent = new MouseEvent('click', mouseEventInit);

    // Dispatch with micro-delays
    element.dispatchEvent(moveEvent);
    element.dispatchEvent(enterEvent);
    element.dispatchEvent(overEvent);

    setTimeout(() => {
        element.dispatchEvent(downEvent);
        setTimeout(() => {
            element.dispatchEvent(upEvent);
            setTimeout(() => {
                element.dispatchEvent(clickEvent);
            }, 20 + Math.random() * 30);
        }, 50 + Math.random() * 50);
    }, 10 + Math.random() * 20);
}

// ==================== BOT LOGIC ====================
let isBusy = false;

function doReset() {
    globalSeenBuffer.clear();
    lastServerScore = null; // Reset score
    for (let v = 1; v <= 10; v++) {
        const el = document.getElementById(`cnt-${v}`);
        if (el) { el.innerText = '4'; el.style.color = '#0f0'; }
    }

    // Pass session_id to reset only THIS session
    const resetPayload = { session_id: sessionId };

    // FETCH_RESET expects a POST body now for session targeting
    // We need to update background.js to handle this or just pass it as state
    // Actually, background.js just forwards POSTs for FETCH_MOVE.
    // FETCH_RESET logic in background.js needs a quick check or just use FETCH_Reset with body.
    // Let's modify doReset to use a custom action that supports body or reuse the logic.
    // Wait, background.js lines 20-22 only add body for FETCH_MOVE. 
    // I need to update background.js OR make FETCH_RESET handle body.

    // Let's send it as FETCH_MOVE with a special flag? No, let's fix background.js

    chrome.runtime.sendMessage({ action: "FETCH_RESET", state: resetPayload }, (res) => {
        if (chrome.runtime.lastError) {
            log("Reset warning:", chrome.runtime.lastError.message);
        }
        if (res && res.status === "success") {
            const msgEl = document.getElementById("hud-msg");
            if (msgEl) {
                msgEl.innerText = "Memory Reset!";
                msgEl.style.color = "cyan";
                setTimeout(() => msgEl.innerText = "Ready", 2000);
            }
        }
    });
}

// Generate unique session ID for this tab
// Generate or retrieve unique session ID
let sessionId = sessionStorage.getItem('scopabot_session_id');
if (!sessionId) {
    sessionId = 'sess_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now().toString(36);
    sessionStorage.setItem('scopabot_session_id', sessionId);
}
log("Session ID:", sessionId);

function runBotStep() {
    if (isBusy) {
        log("Debounce: already processing...");
        return;
    }
    isBusy = true;

    // STEALTH: Variable cooldown (human-like)
    const cooldown = randomDelay(1500, 3000);
    setTimeout(() => isBusy = false, cooldown);

    scanGame();
    if (currentHand.length === 0) {
        const msgEl = document.getElementById("hud-msg");
        if (msgEl) msgEl.innerText = "No cards in hand!";
        isBusy = false;
        return;
    }

    const msgEl = document.getElementById("hud-msg");
    if (msgEl) msgEl.innerText = "Thinking...";

    const state = {
        session_id: sessionId, // ADDED: Unique session ID
        hand: currentHand,
        table: currentTable,
        seen_history: Array.from(globalSeenBuffer),
        my_score_match: gameScore.my,
        opp_score_match: gameScore.opp,
        dealer: dealer,
        last_action_desc: lastAction,
        // Detailed DOM scores
        my_score_details: domScore.my,
        opp_score_details: domScore.opp,
        my_score_cards: domScore.my.carte,
        opp_score_cards: domScore.opp.carte,
        // Opponent's last move (if detected)
        opponent_last_move: opponentLastMove
    };

    chrome.runtime.sendMessage({ action: "FETCH_MOVE", state: state }, (res) => {
        if (chrome.runtime.lastError) {
            log("Error:", chrome.runtime.lastError.message);
        }
        if (res && res.status === "success") {
            const data = res.data;
            const move = data.move || data;

            // STEALTH: Random delay before playing (thinking simulation)
            const thinkTime = randomDelay();
            log(`Thinking for ${thinkTime}ms...`);

            setTimeout(() => {
                if (msgEl) msgEl.innerText = `Move: ${move.description}`;
                if (msgEl) msgEl.innerText = `Move: ${move.description}`;

                // UPDATE REASONING
                const reasonEl = document.getElementById("hud-reason");
                if (reasonEl) {
                    if (move.reasoning && move.reasoning.length > 0) {
                        reasonEl.innerText = move.reasoning.join(", ");
                    } else {
                        reasonEl.innerText = "-";
                    }
                }

                // UPDATE SCORE FROM SERVER
                if (move.score_summary) {
                    lastServerScore = move.score_summary;
                    // Force immediate HUD update
                    const scoreEl = document.getElementById("hud-score");
                    if (scoreEl) {
                        scoreEl.innerText = `${lastServerScore.my} - ${lastServerScore.opp}`;
                        scoreEl.title = lastServerScore.details;
                        scoreEl.style.color = "#0ff";
                    }
                }

                playMove(move);
            }, thinkTime);
        } else {
            if (msgEl) {
                msgEl.innerText = "Server Error";
                msgEl.style.color = "red";
            }
        }
    });
}

function playMove(move) {
    let targetDiv = null;
    document.querySelectorAll(`div[data-scopabot-code='${move.card_played}']`).forEach(div => {
        const topVal = parseInt(div.style.top);
        if (topVal > 450) targetDiv = div;
    });

    if (targetDiv) {
        // SUGGEST-ONLY MODE: Highlight the card, don't click it
        // User will click it themselves

        // Remove any previous highlights
        document.querySelectorAll('.scopabot-highlight').forEach(el => {
            el.classList.remove('scopabot-highlight');
            el.style.border = '';
            el.style.boxShadow = '';
            el.style.animation = '';
        });

        // Add highlight style
        targetDiv.classList.add('scopabot-highlight');
        targetDiv.style.border = '4px solid #00ff00';
        targetDiv.style.boxShadow = '0 0 20px #00ff00, 0 0 40px #00ff00';
        targetDiv.style.animation = 'scopabot-pulse 1s infinite';
        targetDiv.style.borderRadius = '8px';
        targetDiv.style.zIndex = '99999';

        // Add CSS animation if not already added
        if (!document.getElementById('scopabot-styles')) {
            const style = document.createElement('style');
            style.id = 'scopabot-styles';
            style.textContent = `
                @keyframes scopabot-pulse {
                    0%, 100% { box-shadow: 0 0 20px #00ff00, 0 0 40px #00ff00; }
                    50% { box-shadow: 0 0 30px #00ff00, 0 0 60px #00ff00, 0 0 80px #00ff00; }
                }
            `;
            document.head.appendChild(style);
        }

        log('Suggested card:', move.card_played, '- CLICK IT TO PLAY');
    }
}

// ==================== INITIALIZATION ====================
function isGameDetected() {
    if (document.querySelectorAll('div[id^="carta_mazzo_"]').length > 0) return true;
    if (document.querySelector(".mazziere-me") || document.querySelector(".mazziere-opp")) return true;
    return false;
}

// STEALTH: Randomized polling interval
function getRandomInterval(base, variance) {
    return base + Math.floor(Math.random() * variance * 2 - variance);
}

let lastPollTime = 0;
const basePollInterval = 500;  // Reduced from 2000 for faster opponent tracking
const pollVariance = 100;

const initInterval = setInterval(() => {
    // Ghost killer
    if (!chrome.runtime?.id) {
        clearInterval(initInterval);
        return;
    }

    if (!document.body) return;

    // STEALTH: Add randomness to polling timing
    const now = Date.now();
    const targetInterval = getRandomInterval(basePollInterval, pollVariance);
    if (now - lastPollTime < targetInterval * 0.8) return;
    lastPollTime = now;

    if (!isGameDetected()) {
        const hud = document.getElementById("scopabot-hud");
        if (hud) hud.style.display = "none";
        return;
    }

    // Create HUD if needed (but keep it hidden if STEALTH.hudVisible is false)
    if (!hudElement) createHUD();

    // Only show if explicitly toggled
    if (hudElement && STEALTH.hudVisible) {
        hudElement.style.display = "block";
    }

    try {
        scanGame();
        updateHUD();
    } catch (e) {
        log("Scan Error:", e);
    }
}, 1000); // Faster base, but randomized

// Memory sync interval (also randomized)
let lastMemTime = 0;
const baseMemInterval = 3000;

const memInterval = setInterval(() => {
    if (!chrome.runtime?.id) {
        clearInterval(memInterval);
        return;
    }

    // STEALTH: Randomize memory check timing
    const now = Date.now();
    const targetInterval = getRandomInterval(baseMemInterval, 1000);
    if (now - lastMemTime < targetInterval * 0.8) return;
    lastMemTime = now;

    if (typeof chrome === "undefined" || !chrome.runtime || !chrome.runtime.sendMessage) return;

    chrome.runtime.sendMessage({ action: "FETCH_MEMORY", sid: sessionId }, (res) => {
        if (chrome.runtime.lastError) {
            return;
        }
        if (res && res.status === "success") {
            const mem = res.data;
            const el = document.getElementById("hud-mem");
            if (el) el.innerText = `${mem.seen_count} / 40`;
        }
    });
}, 1500);

// Log stealth mode active (only if logs enabled)
log('STEALTH MODE ACTIVE - Press', STEALTH.toggleKey, 'to toggle HUD');
