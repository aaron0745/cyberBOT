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

            await interaction.editReply({
                embeds: [generateLeaderboardEmbed(allScores, currentPage)],
                components: [getLeaderboardButtons(currentPage, maxPages, 'lb_ephem')]
            });
        } catch (error) {
            console.error(error);
            await interaction.editReply({ content: '❌ An error occurred.' });
        }
    },
};
