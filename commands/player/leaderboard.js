const { SlashCommandBuilder } = require('discord.js');
const { updateLeaderboard, generateLeaderboardEmbed, getLeaderboardButtons } = require('../../utils');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('leaderboard')
        .setDescription('Displays the global standings'),
    async execute(interaction) {
        try {
            await interaction.deferReply({ flags: 64 });

            // Fetch latest DB data and update persistent leaderboard card
            const allScores = await updateLeaderboard(interaction.client);

            if (!allScores || allScores.length === 0) {
                const emptyEmbed = generateLeaderboardEmbed([], 0);
                return await interaction.editReply({ embeds: [emptyEmbed], components: [] });
            }

            const maxPages = Math.ceil(allScores.length / 10) || 1;
            let currentPage = 0;

            const replyMessage = await interaction.editReply({
                embeds: [generateLeaderboardEmbed(allScores, currentPage)],
                components: [getLeaderboardButtons(currentPage, maxPages, 'lb_ephem')]
            });

            if (maxPages > 1) {
                const collector = replyMessage.createMessageComponentCollector({
                    filter: i => i.user.id === interaction.user.id && (i.customId === 'lb_ephem_prev' || i.customId === 'lb_ephem_next'),
                    time: 300000 // 5 minutes
                });
                collector.on('collect', async i => {
                    if (i.customId === 'lb_ephem_prev') currentPage--;
                    else if (i.customId === 'lb_ephem_next') currentPage++;
                    
                    if (currentPage < 0) currentPage = 0;
                    if (currentPage >= maxPages) currentPage = maxPages - 1;

                    await i.update({
                        embeds: [generateLeaderboardEmbed(allScores, currentPage)],
                        components: [getLeaderboardButtons(currentPage, maxPages, 'lb_ephem')]
                    });
                });
                collector.on('end', () => {
                    interaction.editReply({ components: [] }).catch(() => null);
                });
            }
        } catch (error) {
            console.error(error);
            await interaction.editReply({ content: '❌ An error occurred.' });
        }
    },
};
