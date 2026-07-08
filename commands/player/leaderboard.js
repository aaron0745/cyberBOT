const { SlashCommandBuilder, EmbedBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle } = require('discord.js');
const { Models } = require('../../database/mongoose');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('leaderboard')
        .setDescription('Displays the global standings'),
    async execute(interaction) {
        try {
            await interaction.deferReply({ flags: 64 });

            const allScores = await Models.Score.aggregate([
                { $lookup: { from: 'solves', localField: 'user_id', foreignField: 'user_id', as: 'user_solves' } },
                { $addFields: { latest_solve: { $ifNull: [{ $max: "$user_solves.timestamp" }, 9999999999999] } } },
                { $sort: { points: -1, latest_solve: 1 } }
            ]);

            if (allScores.length === 0) {
                return await interaction.editReply({ content: 'The leaderboard is currently empty.' });
            }

            const { generateLeaderboardEmbed, getLeaderboardButtons } = require('../../utils');

            const maxPages = Math.ceil(allScores.length / 10) || 1;
            let currentPage = 0;

            const replyMessage = await interaction.editReply({ embeds: [generateLeaderboardEmbed(allScores, currentPage)], components: [getLeaderboardButtons(currentPage, maxPages)] });

            if (maxPages > 1) {
                const collector = replyMessage.createMessageComponentCollector({ time: 300000 }); // 5 minutes
                collector.on('collect', async i => {
                    if (i.customId === 'lb_main_prev') currentPage--;
                    else if (i.customId === 'lb_main_next') currentPage++;
                    
                    if (currentPage < 0) currentPage = 0;
                    if (currentPage >= maxPages) currentPage = maxPages - 1;

                    await i.update({ embeds: [generateLeaderboardEmbed(allScores, currentPage)], components: [getLeaderboardButtons(currentPage, maxPages)] });
                });
                collector.on('end', () => {
                    interaction.editReply({ components: [] }).catch(() => null);
                });
            }

            // Auto-post persistent
            const lbChannelConf = await Models.Config.findOne({ key: 'channel_leaderboard' });
            const lbMsgConf = await Models.Config.findOne({ key: 'msg_leaderboard' });
            if (lbChannelConf && lbChannelConf.value) {
                try {
                    const lbChannel = await interaction.client.channels.fetch(lbChannelConf.value);
                    if (lbChannel) {
                        const top10Embed = generateEmbed(0).setFooter({ text: 'Auto-updating Top 10' });
                        let msg;
                        if (lbMsgConf && lbMsgConf.value) {
                            try { msg = await lbChannel.messages.fetch(lbMsgConf.value); } catch(e){}
                        }
                        if (msg) {
                            await msg.edit({ embeds: [top10Embed] });
                        } else {
                            msg = await lbChannel.send({ embeds: [top10Embed] });
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
                            const genChannel = await interaction.client.channels.fetch(genChannelConf.value);
                            if (genChannel) {
                                genChannel.send(`👑 **NEW KING!** <@${championId}> has taken the #1 spot on the leaderboard!`);
                            }
                        } catch(e){}
                    }

                    try {
                        const guild = interaction.guild;
                        if (guild) {
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
                        }
                    } catch(e){}
                }
            }

        } catch (error) {
            console.error(error);
            await interaction.editReply({ content: '❌ An error occurred.' });
        }
    },
};
