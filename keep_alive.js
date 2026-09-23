const express = require('express');
const https = require('https');
const mongoose = require('mongoose');
const app = express();

let clientRef = null;
const recentLogs = [];

function addLog(type, msg) {
    recentLogs.unshift({
        time: new Date().toISOString(),
        type,
        msg: typeof msg === 'string' ? msg : (msg?.stack || JSON.stringify(msg))
    });
    if (recentLogs.length > 25) recentLogs.pop();
}

app.get('/health', (req, res) => {
    const wsStates = ['READY', 'CONNECTING', 'RECONNECTING', 'IDLE', 'NEARLY', 'DISCONNECTED', 'WAITING_FOR_GUILDS', 'IDENTIFYING', 'RESUMING'];
    const mongoStates = ['DISCONNECTED', 'CONNECTED', 'CONNECTING', 'DISCONNECTING'];

    res.json({
        status: 'ok',
        uptime: Math.floor(process.uptime()),
        deployedCommit: process.env.RENDER_GIT_COMMIT || 'unknown',
        discord: {
            ready: clientRef?.isReady?.() || false,
            status: wsStates[clientRef?.ws?.status] || clientRef?.ws?.status,
            ping: clientRef?.ws?.ping ?? -1,
            user: clientRef?.user?.tag || null,
            guildCount: clientRef?.guilds?.cache?.size || 0,
            commandsCount: clientRef?.commands?.size || 0
        },
        mongodb: {
            readyState: mongoStates[mongoose.connection.readyState] || mongoose.connection.readyState
        },
        recentLogs
    });
});

app.use((req, res) => {
    res.send('Bot is running!');
});

function keepAlive(client) {
    if (client) clientRef = client;
    const port = process.env.PORT || 3000;
    app.listen(port, () => {
        console.log(`Server is ready on port ${port}. Keep-alive active.`);
        
        // The bot pings itself every 10 minutes (600,000 ms) with a 5-minute safety margin
        setInterval(() => {
            const renderUrl = process.env.RENDER_URL;
            if (renderUrl) {
                const req = https.get(renderUrl, (resp) => {
                    resp.resume(); // Consume response stream to free socket memory
                    console.log(`[Self-Ping] Woke up successfully! Status: ${resp.statusCode}`);
                });
                req.setTimeout(10000, () => {
                    req.destroy();
                    console.log('[Self-Ping]: Request timed out after 10s, connection reset.');
                });
                req.on("error", (err) => {
                    console.log(`[Self-Ping Error]: ${err.message}`);
                    addLog('SELF_PING_ERROR', err.message);
                });
            }
        }, 10 * 60 * 1000);
    });
}

module.exports = { keepAlive, addLog };
