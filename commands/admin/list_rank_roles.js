const { SlashCommandBuilder, PermissionFlagsBits, EmbedBuilder } = require('discord.js');
const { Models } = require('../../database/mongoose');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('list_rank_roles')
        .setDescription('List all configured rank roles')
        .setDefaultMemberPermissions(PermissionFlagsBits.Administrator),
    async execute(interaction) {
        try {
            const roles = await Models.RoleReward.find().sort({ points: 1 });
            if (roles.length === 0) {
                return await interaction.reply({ content: 'No rank roles configured.', flags: 64 });
            }
            
            const embed = new EmbedBuilder()
                .setTitle('🏆 Rank Roles')
                .setColor('#0099ff');
            
            let description = '';
            for (const role of roles) {
                description += `<@&${role.role_id}>: ${role.points} points\n`;
            }
            embed.setDescription(description);
            
            await interaction.reply({ embeds: [embed], flags: 64 });
        } catch (error) {
            console.error(error);
            await interaction.reply({ content: '❌ Error listing rank roles.', flags: 64 });
        }
    }
};
