const { EmbedBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle } = require('discord.js');
const { Models } = require('./database/mongoose');

function generateLeaderboardEmbed(allScores, page) {
    const itemsPerPage = 10;
    const maxPages = Math.ceil(allScores.length / itemsPerPage) || 1;
    const start = page * itemsPerPage;
    const currentScores = allScores.slice(start, start + itemsPerPage);
    let desc = '';
    currentScores.forEach((score, index) => {
        let icon = '';
        const rank = start + index + 1;
        if (rank === 1) icon = '👑';
        else if (rank === 2) icon = '🥈';
        else if (rank === 3) icon = '🥉';
        else icon = `**#${rank}**`;
        
        desc += `${icon} • <@${score.user_id}> — \`${score.points || 0} pts\`\n`;
    });
    return new EmbedBuilder()
        .setTitle('🏆 CyberBOT GLOBAL STANDINGS')
        .setDescription(desc || "No operational data available.")
        .setColor(0xFFD700)
        .setFooter({ text: `Page ${page + 1} of ${maxPages} • Refreshes periodically` });
}

function getLeaderboardButtons(page, maxPages) {
    return new ActionRowBuilder().addComponents(
        new ButtonBuilder()
            .setCustomId('lb_main_prev')
            .setLabel('◄ Prev')
            .setStyle(ButtonStyle.Secondary)
            .setDisabled(page === 0),
        new ButtonBuilder()
            .setCustomId('lb_main_next')
            .setLabel('Next ►')
            .setStyle(ButtonStyle.Secondary)
            .setDisabled(page >= maxPages - 1 || maxPages === 0)
    );
}

async function updateLeaderboard(client) {
    try {
        const allScores = await Models.Score.aggregate([
            { $lookup: { from: 'solves', localField: 'user_id', foreignField: 'user_id', as: 'user_solves' } },
            { $addFields: { latest_solve: { $ifNull: [{ $max: "$user_solves.timestamp" }, 9999999999999] } } },
            { $sort: { points: -1, latest_solve: 1 } }
        ]);

        // Auto-post persistent
        const lbChannelConf = await Models.Config.findOne({ key: 'channel_leaderboard' });
        const lbMsgConf = await Models.Config.findOne({ key: 'msg_leaderboard' });
        
        if (lbChannelConf && lbChannelConf.value) {
            try {
                const lbChannel = await client.channels.fetch(lbChannelConf.value);
                if (lbChannel) {
                    const maxPages = Math.ceil(allScores.length / 10) || 1;
                    const top10Embed = generateLeaderboardEmbed(allScores, 0);
                    const buttons = getLeaderboardButtons(0, maxPages);

                    let msg;
                    if (lbMsgConf && lbMsgConf.value) {
                        try { msg = await lbChannel.messages.fetch(lbMsgConf.value); } catch(e){}
                    }
                    if (msg) {
                        await msg.edit({ embeds: [top10Embed], components: [buttons] });
                    } else {
                        msg = await lbChannel.send({ embeds: [top10Embed], components: [buttons] });
                        await Models.Config.updateOne({ key: 'msg_leaderboard' }, { $set: { value: msg.id } }, { upsert: true });
                    }
                }
            } catch(e){}
        }

        // Champion handoff
        const roleChampionConf = await Models.Config.findOne({ key: 'role_champion' });
        if (roleChampionConf && roleChampionConf.value && allScores.length > 0) {
            const championId = allScores[0].user_id;
            const prevChampionConf = await Models.Config.findOne({ key: 'current_champion_id' });
            
            if (!prevChampionConf || prevChampionConf.value !== championId) {
                // Announce new king
                await Models.Config.updateOne({ key: 'current_champion_id' }, { value: championId }, { upsert: true });
                
                const genChannelConf = await Models.Config.findOne({ key: 'channel_general' });
                if (genChannelConf && genChannelConf.value) {
                    try {
                        const genChannel = await client.channels.fetch(genChannelConf.value);
                        if (genChannel) {
                            genChannel.send(`👑 **NEW KING!** <@${championId}> has taken the #1 spot on the leaderboard!`);
                        }
                    } catch(e){}
                }

                // Actually swap the roles across the guild
                client.guilds.cache.forEach(async guild => {
                    try {
                        const role = await guild.roles.fetch(roleChampionConf.value);
                        if (role) {
                            await guild.members.fetch();
                            role.members.forEach(async (member) => {
                                if (member.id !== championId) {
                                    try { await member.roles.remove(role); } catch(e){}
                                }
                            });
                            const newChamp = await guild.members.fetch(championId).catch(()=>null);
                            if (newChamp) await newChamp.roles.add(role).catch(()=>null);
                        }
                    } catch(e){}
                });
            }
        }
    } catch (e) {
        console.error("updateLeaderboard error:", e);
    }
}

async function updateChallengePost(client, challenge_id) {
    try {
        const flag = await Models.Flag.findOne({ challenge_id });
        if (!flag || !flag.msg_id || !flag.channel_id) return;
        
        const channel = await client.channels.fetch(flag.channel_id).catch(()=>null);
        if (!channel) return;
        
        const existingMsg = await channel.messages.fetch(flag.msg_id).catch(()=>null);
        if (!existingMsg) return;

        const now = Math.floor(Date.now() / 1000);
        const isExpired = flag.end_time && now > flag.end_time;

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
        
        if (!isExpired) {
            const btnSubmit = new ButtonBuilder().setCustomId(`submit:${flag.challenge_id}`).setLabel("Submit Flag").setStyle(ButtonStyle.Success).setEmoji("🚩");
            const btnHint = new ButtonBuilder().setCustomId(`hints:${flag.challenge_id}`).setLabel("Hints").setStyle(ButtonStyle.Secondary).setEmoji("💡");
            const row = new ActionRowBuilder().addComponents(btnSubmit);
            if (has_hints) row.addComponents(btnHint);
            components.push(row);
        } else {
            const btnExpired = new ButtonBuilder().setCustomId(`expired:${flag.challenge_id}`).setLabel("Time Expired").setStyle(ButtonStyle.Danger).setEmoji("⏳").setDisabled(true);
            const row = new ActionRowBuilder().addComponents(btnExpired);
            components.push(row);
        }
        
        if (totalSolves > 0) {
            const btnSolvers = new ButtonBuilder().setCustomId(`view_solves:${flag.challenge_id}`).setLabel(`${totalSolves} Solves`).setStyle(ButtonStyle.Primary).setEmoji("📜");
            if (components.length > 0) {
                components[0].addComponents(btnSolvers);
            } else {
                components.push(new ActionRowBuilder().addComponents(btnSolvers));
            }
        }

        await existingMsg.edit({ embeds: [embed], components });
    } catch(e) { console.error("updateChallengePost error:", e); }
}

module.exports = {
    updateLeaderboard,
    updateChallengePost,
    generateLeaderboardEmbed,
    getLeaderboardButtons
};
