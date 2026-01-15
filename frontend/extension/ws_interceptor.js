/**
 * WebSocket Interceptor - Injected into page context
 * This script intercepts all WebSocket messages and forwards them to the content script
 */

(function () {
    'use strict';

    console.log('[WS-INTERCEPTOR] Initializing...');

    const OriginalWebSocket = window.WebSocket;

    window.WebSocket = function (url, protocols) {
        console.log('[WS-INTERCEPTOR] New connection:', url);

        const ws = protocols ? new OriginalWebSocket(url, protocols) : new OriginalWebSocket(url);

        // Intercept incoming messages
        ws.addEventListener('message', function (event) {
            try {
                // Forward to content script via custom event
                window.dispatchEvent(new CustomEvent('scopabot-ws-message', {
                    detail: {
                        type: 'received',
                        url: url,
                        data: event.data,
                        timestamp: Date.now()
                    }
                }));

                // Log to console for debugging
                if (event.data && typeof event.data === 'string') {
                    // Socket.IO format: "42[\"event\",{data}]"
                    if (event.data.startsWith('42[')) {
                        const payload = event.data.substring(2);
                        try {
                            const parsed = JSON.parse(payload);
                            console.log('[WS-RX]', parsed[0], parsed[1]);
                        } catch (e) {
                            console.log('[WS-RX] Raw:', event.data.substring(0, 200));
                        }
                    } else if (event.data.length > 5) {
                        console.log('[WS-RX] Other:', event.data.substring(0, 100));
                    }
                }
            } catch (e) {
                console.error('[WS-INTERCEPTOR] Error:', e);
            }
        });

        // Intercept outgoing messages
        const originalSend = ws.send.bind(ws);
        ws.send = function (data) {
            try {
                window.dispatchEvent(new CustomEvent('scopabot-ws-message', {
                    detail: {
                        type: 'sent',
                        url: url,
                        data: data,
                        timestamp: Date.now()
                    }
                }));

                if (typeof data === 'string' && data.startsWith('42[')) {
                    const payload = data.substring(2);
                    try {
                        const parsed = JSON.parse(payload);
                        console.log('[WS-TX]', parsed[0], parsed[1]);
                    } catch (e) {
                        console.log('[WS-TX] Raw:', data.substring(0, 100));
                    }
                }
            } catch (e) {
                console.error('[WS-INTERCEPTOR] Send error:', e);
            }
            return originalSend(data);
        };

        ws.addEventListener('open', function () {
            console.log('[WS-INTERCEPTOR] Connected:', url.substring(0, 80) + '...');
        });

        ws.addEventListener('close', function () {
            console.log('[WS-INTERCEPTOR] Disconnected');
        });

        return ws;
    };

    // Copy static properties
    window.WebSocket.CONNECTING = OriginalWebSocket.CONNECTING;
    window.WebSocket.OPEN = OriginalWebSocket.OPEN;
    window.WebSocket.CLOSING = OriginalWebSocket.CLOSING;
    window.WebSocket.CLOSED = OriginalWebSocket.CLOSED;
    window.WebSocket.prototype = OriginalWebSocket.prototype;

    console.log('[WS-INTERCEPTOR] Ready! WebSocket messages will be logged.');
})();
