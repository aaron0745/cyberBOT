const { SlashCommandBuilder, PermissionFlagsBits } = require('discord.js');
const { Models } = require('../../database/mongoose');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('set_rank_role')
        .setDescription('Set a role reward for reaching a point threshold')
        .addRoleOption(option => option.setName('role').setDescription('The role to give').setRequired(true))
        .addIntegerOption(option => option.setName('points').setDescription('Points required').setRequired(true))
        .setDefaultMemberPermissions(PermissionFlagsBits.Administrator),
    async execute(interaction) {
        const role = interaction.options.getRole('role');
        const points = interaction.options.getInteger('points');
        try {
            await Models.RoleReward.findOneAndUpdate(
                { role_id: role.id },
                { points: points },
                { upsert: true }
            );
            await interaction.reply({ content: `✅ Set rank role <@&${role.id}> for ${points} points.`, flags: 64 });
        } catch (error) {
            console.error(error);
            await interaction.reply({ content: '❌ Error setting rank role.', flags: 64 });
        }
    }
};
