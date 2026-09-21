const express = require('express');
const https = require('https');
const app = express();

app.use((req, res) => {
    res.send('Bot is running!');
});

function keepAlive() {
    const port = process.env.PORT || 3000;
    app.listen(port, () => {
        console.log(`Server is ready on port ${port}. Keep-alive active.`);
        
        // The bot pings itself every 10 minutes (600,000 ms) with a 5-minute safety margin
        setInterval(() => {
            // Replace with the actual Render URL once deployed
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
                });
            }
        }, 10 * 60 * 1000);
    });
}

module.exports = keepAlive;
