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

app.get('/debug-auth', (req, res) => {
    const rawToken = process.env.DISCORD_TOKEN;
    const token = rawToken ? rawToken.trim() : null;
    const tokenLength = token ? token.length : 0;
    const tokenPrefix = token ? token.substring(0, 10) + '...' : null;

    const testDiscordAPI = (path, authHeader) => {
        return new Promise((resolve) => {
            const options = {
                hostname: 'discord.com',
                path: `/api/v10${path}`,
                method: 'GET',
                headers: {
                    'User-Agent': 'DiscordBot (https://github.com/aaron0745/cyberBOT, 1.0.0)'
                }
            };
            if (authHeader) options.headers['Authorization'] = authHeader;

            const r = https.request(options, (resp) => {
                let body = '';
                resp.on('data', chunk => body += chunk);
                resp.on('end', () => {
                    resolve({
                        statusCode: resp.statusCode,
                        headers: {
                            'content-type': resp.headers['content-type'],
                            'retry-after': resp.headers['retry-after'],
                            'cf-ray': resp.headers['cf-ray']
                        },
                        body: body.substring(0, 500)
                    });
                });
            });
            r.on('error', (err) => resolve({ error: err.message }));
            r.setTimeout(6000, () => {
                r.destroy();
                resolve({ error: 'Request timed out after 6s' });
            });
            r.end();
        });
    };

    Promise.all([
        testDiscordAPI('/gateway'),
        token ? testDiscordAPI('/users/@me', `Bot ${token}`) : Promise.resolve({ error: 'No token' })
    ]).then(([gatewayRes, userRes]) => {
        res.json({
            tokenConfigured: Boolean(token),
            tokenLength,
            tokenPrefix,
            gatewayEndpoint: gatewayRes,
            userMeEndpoint: userRes,
            discordClient: {
                ready: clientRef?.isReady?.() || false,
                status: clientRef?.ws?.status,
                user: clientRef?.user?.tag || null
            }
        });
    }).catch(err => {
        res.status(500).json({ error: err.message });
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
