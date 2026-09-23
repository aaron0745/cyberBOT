const { keepAlive, addLog } = require('./keep_alive');
const { connectDB } = require('./database/mongoose');

process.env.TZ = 'Asia/Kolkata';

// Prevent unhandled errors or rejected promises from crashing the bot process
process.on('unhandledRejection', (reason, promise) => {
    console.error('⚠️ Unhandled Rejection at:', promise, 'reason:', reason);
    addLog('UNHANDLED_REJECTION', reason?.stack || reason);
});

process.on('uncaughtException', (err) => {
    console.error('⚠️ Uncaught Exception thrown:', err);
    addLog('UNCAUGHT_EXCEPTION', err?.stack || err);
});
const fs = require('node:fs');
const path = require('node:path');
const { Client, Collection, GatewayIntentBits } = require('discord.js');
require('dotenv').config();

const client = new Client({ 
    intents: [
        GatewayIntentBits.Guilds, 
        GatewayIntentBits.GuildMessages, 
        GatewayIntentBits.MessageContent,
        GatewayIntentBits.GuildMembers
    ] 
});

client.commands = new Collection();
const commandsPath = path.join(__dirname, 'commands');

function loadCommands(dir) {
    if (!fs.existsSync(dir)) return;
    const files = fs.readdirSync(dir);
    for (const file of files) {
        const fullPath = path.join(dir, file);
        if (fs.statSync(fullPath).isDirectory()) {
            loadCommands(fullPath);
        } else if (file.endsWith('.js')) {
            const command = require(fullPath);
            if ('data' in command && 'execute' in command) {
                client.commands.set(command.data.name, command);
            }
        }
    }
}

loadCommands(commandsPath);

const eventsPath = path.join(__dirname, 'events');
if (fs.existsSync(eventsPath)) {
    const eventFiles = fs.readdirSync(eventsPath).filter(file => file.endsWith('.js'));
    for (const file of eventFiles) {
        const filePath = path.join(eventsPath, file);
        const event = require(filePath);
        if (event.once) {
            client.once(event.name, (...args) => event.execute(...args, client));
        } else {
            client.on(event.name, (...args) => event.execute(...args, client));
        }
    }
}

// Client connection diagnostics
client.on('error', (err) => {
    console.error('❌ Discord Client Error:', err);
    addLog('DISCORD_CLIENT_ERROR', err?.message || err);
});
client.on('shardError', (err) => {
    console.error('❌ Discord Shard Error:', err);
    addLog('DISCORD_SHARD_ERROR', err?.message || err);
});
client.on('shardDisconnect', (event, id) => {
    console.warn(`🔌 Discord Shard ${id} disconnected (code: ${event.code}, reason: ${event.reason})`);
    addLog('DISCORD_DISCONNECT', `Shard ${id} disconnected code=${event.code} reason=${event.reason}`);
});

keepAlive(client);

// Connect to MongoDB before logging in
connectDB()
    .then(async () => {
        console.log('🔄 Connecting to Discord Gateway...');
        await client.login(process.env.DISCORD_TOKEN);
    })
    .catch((err) => {
        console.error('❌ Fatal Startup Error:', err);
        addLog('FATAL_STARTUP', err?.stack || err?.message || err);
        process.exit(1);
    });
