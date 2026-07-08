const { Events } = require('discord.js');

module.exports = {
    name: Events.GuildCreate,
    async execute(guild, client) {
        // Only allow the bot to stay in the authorized server
        const authorizedGuildId = process.env.GUILD_ID;
        
        if (guild.id !== authorizedGuildId) {
            console.log(`[SECURITY] Bot was added to an unauthorized server: ${guild.name} (${guild.id}). Leaving automatically.`);
            try {
                const owner = await guild.fetchOwner();
                if (owner) {
                    await owner.send('⛔ This bot is private and locked to a specific server. It has automatically left your server.');
                }
            } catch (err) {
                console.error('Could not send DM to unauthorized server owner.');
            }
            
            // Leave the server
            await guild.leave();
        } else {
            console.log(`[JOIN] Successfully joined the authorized server: ${guild.name}`);
        }
    },
};
