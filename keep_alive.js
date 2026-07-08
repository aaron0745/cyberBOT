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
        
        // The bot pings itself every 14 minutes (840,000 ms) to prevent Render from sleeping
        setInterval(() => {
            // Replace with the actual Render URL once deployed
            const renderUrl = process.env.RENDER_URL;
            if (renderUrl) {
                https.get(renderUrl, (resp) => {
                    console.log(`[Self-Ping] Woke up successfully! Status: ${resp.statusCode}`);
                }).on("error", (err) => {
                    console.log(`[Self-Ping Error]: ${err.message}`);
                });
            }
        }, 14 * 60 * 1000);
    });
}

module.exports = keepAlive;
