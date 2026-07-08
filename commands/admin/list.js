const { SlashCommandBuilder, PermissionFlagsBits, EmbedBuilder } = require('discord.js');
const { Models } = require('../../database/mongoose');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('list')
        .setDescription('Lists all created challenges')
        .setDefaultMemberPermissions(PermissionFlagsBits.Administrator),
    async execute(interaction) {
        try {
            const challenges = await Models.Flag.find({});
            
            if (challenges.length === 0) {
                return await interaction.reply({ content: 'No challenges found.', flags: 64 });
            }

            let listString = '';
            for (const challenge of challenges) {
                listString += `**ID:** ${challenge.challenge_id} | **Points:** ${challenge.points || 0} | **Category:** ${challenge.category || 'N/A'}\n`;
            }

            const embed = new EmbedBuilder()
                .setTitle('Challenges List')
                .setDescription(listString.slice(0, 4096))
                .setColor(0x0099FF);

            await interaction.reply({ embeds: [embed], flags: 64 });
        } catch (error) {
            console.error(error);
            await interaction.reply({ content: '❌ An error occurred while fetching challenges.', flags: 64 });
        }
    },
};
