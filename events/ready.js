const { Events, ActivityType, EmbedBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle } = require('discord.js');
const { Models } = require('../database/mongoose');

module.exports = {
    name: Events.ClientReady,
    once: true,
    execute(client) {
        console.log(`✅ Logged in as ${client.user.tag}`);
        console.log('🚀 CyberBOT Node.js migration operational.');

        // Set initial activity
        client.user.setPresence({
            activities: [{ name: 'Capture The Flag 🚩', type: ActivityType.Playing }],
            status: 'online',
        });
        
        // Rotating presence
        const activities = [
            { name: 'Capture The Flag 🚩', type: ActivityType.Playing },
            { name: 'for Solves 👀', type: ActivityType.Watching }
        ];
        
        let i = 0;
        setInterval(() => {
            i = (i + 1) % activities.length;
            client.user.setActivity(activities[i]);
        }, 150000);

        // --- BACKGROUND WATCHDOG ---
        setInterval(async () => {
            try {
                const now = Math.floor(Date.now() / 1000);
                
                // 1. Scheduled Posts
                const scheduled = await Models.Flag.find({ start_time: { $lte: now }, msg_id: null, channel_id: { $ne: null } });
                for (const flag of scheduled) {
                    const channel = client.channels.cache.get(flag.channel_id);
                    if (!channel) continue;

                    let finalDesc = `**Objective:**\n\`\`\`text\n${flag.description}\n\`\`\``;
                    if (flag.connection_info) finalDesc += `\n**📡 Connection:**\n\`\`\`text\n${flag.connection_info}\n\`\`\``;

                    const embed = new EmbedBuilder()
                        .setTitle(`🛡️ MISSION: ${flag.challenge_id}`)
                        .setDescription(finalDesc)
                        .setColor(0xff0000)
                        .addFields(
                            { name: '💰 Bounty', value: `**${flag.points} Points**`, inline: true },
                            { name: '📂 Category', value: `**${flag.category || "General"}**`, inline: true },
                            { name: '⏳ Time Left', value: `<t:${flag.end_time}:R>`, inline: true },
                            { name: '🩸 First Blood', value: '*Waiting...*', inline: false }
                        );
                    
                    if (flag.image_url) embed.setImage(flag.image_url);
                    if (flag.file_url) embed.setFooter({ text: "📁 See attached file below" });

                    const has_hints = await Models.Hint.countDocuments({ challenge_id: flag.challenge_id }) > 0;
                    const btnSubmit = new ButtonBuilder().setCustomId(`submit:${flag.challenge_id}`).setLabel("Submit Flag").setStyle(ButtonStyle.Success).setEmoji("🚩");
                    const btnHint = new ButtonBuilder().setCustomId(`hints:${flag.challenge_id}`).setLabel("Hints").setStyle(ButtonStyle.Secondary).setEmoji("💡");

                    const row = new ActionRowBuilder().addComponents(btnSubmit);
                    if (has_hints) row.addComponents(btnHint);

                    const postMsg = await channel.send({ embeds: [embed], components: [row] });
                    let fMsg = null;
                    if (flag.file_url) fMsg = await channel.send({ files: [flag.file_url] });

                    await Models.Flag.updateOne({ challenge_id: flag.challenge_id }, { msg_id: postMsg.id, file_msg_id: fMsg ? fMsg.id : null, posted_at: now });
                }

                // 2. Anti-Deletion Watchdog & Expiry Checker
                const active = await Models.Flag.find({ msg_id: { $ne: null }, channel_id: { $ne: null } });
                for (const flag of active) {
                    const channel = client.channels.cache.get(flag.channel_id);
                    if (!channel) continue;

                    const isExpired = flag.end_time && now > flag.end_time;
                    let existingMsg = null;
                    try {
                        existingMsg = await channel.messages.fetch(flag.msg_id);
                    } catch(e) {}

                    let existingFileMsg = null;
                    if (flag.file_url && flag.file_msg_id) {
                        try {
                            existingFileMsg = await channel.messages.fetch(flag.file_msg_id);
                        } catch(e) {}
                    }

                    let finalDesc = `**Objective:**\n\`\`\`text\n${flag.description}\n\`\`\``;
                    if (flag.connection_info) finalDesc += `\n**📡 Connection:**\n\`\`\`text\n${flag.connection_info}\n\`\`\``;

                    const embed = new EmbedBuilder()
                        .setTitle(`🛡️ MISSION: ${flag.challenge_id}`)
                        .setDescription(finalDesc)
                        .setColor(isExpired ? 0x555555 : 0xff0000)
                        .addFields(
                            { name: '💰 Bounty', value: `**${flag.points} Points**`, inline: true },
                            { name: '📂 Category', value: `**${flag.category || "General"}**`, inline: true },
                            { name: '⏳ Time Left', value: isExpired ? 'EXPIRED' : `<t:${flag.end_time}:R>`, inline: true },
                        );

                    const solves = await Models.Solve.find({ challenge_id: flag.challenge_id }).sort({ timestamp: 1 }).limit(1);
                    if (solves.length > 0) {
                        embed.addFields({ name: '🩸 First Blood', value: `<@${solves[0].user_id}>`, inline: false });
                    } else {
                        embed.addFields({ name: '🩸 First Blood', value: '*Waiting...*', inline: false });
                    }

                    if (flag.image_url) embed.setImage(flag.image_url);
                    if (flag.file_url) embed.setFooter({ text: "📁 See attached file below" });

                    const totalSolves = await Models.Solve.countDocuments({ challenge_id: flag.challenge_id });
                    const components = [];
                    const has_hints = await Models.Hint.countDocuments({ challenge_id: flag.challenge_id }) > 0;

                    const row = new ActionRowBuilder();
                    if (!isExpired) {
                        const btnSubmit = new ButtonBuilder().setCustomId(`submit:${flag.challenge_id}`).setLabel("Submit Flag").setStyle(ButtonStyle.Success).setEmoji("🚩");
                        row.addComponents(btnSubmit);
                    } else {
                        const btnExpired = new ButtonBuilder().setCustomId(`expired:${flag.challenge_id}`).setLabel("Time Expired").setStyle(ButtonStyle.Danger).setEmoji("⏳").setDisabled(true);
                        row.addComponents(btnExpired);
                    }

                    if (has_hints) {
                        const btnHint = new ButtonBuilder().setCustomId(`hints:${flag.challenge_id}`).setLabel("Hints").setStyle(ButtonStyle.Secondary).setEmoji("💡");
                        row.addComponents(btnHint);
                    }

                    components.push(row);

                    if (totalSolves > 0) {
                        const btnSolvers = new ButtonBuilder().setCustomId(`view_solves:${flag.challenge_id}`).setLabel(`${totalSolves} Solves`).setStyle(ButtonStyle.Primary).setEmoji("📜");
                        components[0].addComponents(btnSolvers);
                    }

                   if (!existingMsg) {
                        // Card was deleted. Nuke any orphaned file message first, then re-post both fresh.
                        if (existingFileMsg) {
                            try { await existingFileMsg.delete(); } catch(e) {}
                        }
                        const postMsg = await channel.send({ embeds: [embed], components });
                        let fMsg = null;
                        if (flag.file_url) fMsg = await channel.send({ files: [flag.file_url] });
                        await Models.Flag.updateOne({ challenge_id: flag.challenge_id }, { msg_id: postMsg.id, file_msg_id: fMsg ? fMsg.id : null });
                    } else {
                        const hasSubmit = existingMsg.components.some(r => r.components.some(btn => btn.customId && btn.customId.startsWith('submit')));
                        const hasExpired = existingMsg.components.some(r => r.components.some(btn => btn.customId && btn.customId.startsWith('expired')));
                        if (isExpired && (hasSubmit || !hasExpired)) {
                            // Update buttons to expired state while preserving hints/solves
                            await existingMsg.edit({ embeds: [embed], components });
                        }
                        if (flag.file_url && !existingFileMsg) {
                            // Card is fine but the file message was deleted independently. Re-post file only.
                            const fMsg = await channel.send({ files: [flag.file_url] });
                            await Models.Flag.updateOne({ challenge_id: flag.challenge_id }, { file_msg_id: fMsg.id });
                        }
                    }
                }
            } catch (err) {
                console.error("Watchdog loop error:", err);
            }
        }, 30000); // Check every 30 seconds
    },
};
