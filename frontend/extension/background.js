// Proxy Server for Mixed Content (HTTPS -> HTTP)
// Server IP configuration - can be changed via chrome.storage.local
// To change: chrome.storage.local.set({serverIP: "192.168.x.x"})
const DEFAULT_SERVER_IP = "192.168.0.138";
let SERVER_IP = DEFAULT_SERVER_IP;

// Load server IP from storage (if configured)
chrome.storage.local.get(['serverIP'], (result) => {
    if (result.serverIP) {
        SERVER_IP = result.serverIP;
        console.log('[ScopaBot] Server IP loaded from storage:', SERVER_IP);
    } else {
        console.log('[ScopaBot] Using default server IP:', SERVER_IP);
    }
});

// Listen for storage changes to update IP dynamically
chrome.storage.onChanged.addListener((changes, namespace) => {
    if (namespace === 'local' && changes.serverIP) {
        SERVER_IP = changes.serverIP.newValue || DEFAULT_SERVER_IP;
        console.log('[ScopaBot] Server IP updated:', SERVER_IP);
    }
});

// Retry with Exponential Backoff
async function fetchWithRetry(url, options, maxRetries = 3) {
    for (let attempt = 0; attempt < maxRetries; attempt++) {
        try {
            const res = await fetch(url, options);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            return await res.json();
        } catch (err) {
            if (attempt === maxRetries - 1) throw err;
            // Exponential backoff: 1s, 2s, 4s
            await new Promise(r => setTimeout(r, Math.pow(2, attempt) * 1000));
        }
    }
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {

    const endpoints = {
        "FETCH_MOVE": `http://${SERVER_IP}:8000/next_move`,
        "FETCH_RESET": `http://${SERVER_IP}:8000/reset`,
        "FETCH_MEMORY": `http://${SERVER_IP}:8000/memory_state`
    };

    if (endpoints[request.action]) {
        let url = endpoints[request.action];

        // Add session_id as query param for memory requests
        if (request.action === "FETCH_MEMORY" && request.sid) {
            url += `?sid=${encodeURIComponent(request.sid)}`;
        }

        const options = {
            method: request.action === "FETCH_MEMORY" ? "GET" : "POST",
            headers: { "Content-Type": "application/json" }
        };

        if (request.action === "FETCH_MOVE" || request.action === "FETCH_RESET") {
            options.body = JSON.stringify(request.state);
        }

        // Use retry logic for FETCH_MOVE (critical), simple fetch for others
        if (request.action === "FETCH_MOVE") {
            fetchWithRetry(url, options)
                .then(data => sendResponse({ status: "success", data: data }))
                .catch(err => sendResponse({ status: "error", message: err.toString() }));
        } else {
            fetch(url, options)
                .then(res => res.json())
                .then(data => sendResponse({ status: "success", data: data }))
                .catch(err => sendResponse({ status: "error", message: err.toString() }));
        }

        return true;
    }
});
