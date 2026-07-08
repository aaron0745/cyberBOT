const { SlashCommandBuilder, PermissionFlagsBits } = require('discord.js');
const { Models } = require('../../database/mongoose');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('remove_rank_role')
        .setDescription('Remove a role reward')
        .addRoleOption(option => option.setName('role').setDescription('The role to remove').setRequired(true))
        .setDefaultMemberPermissions(PermissionFlagsBits.Administrator),
    async execute(interaction) {
        const role = interaction.options.getRole('role');
        try {
            const result = await Models.RoleReward.deleteOne({ role_id: role.id });
            if (result.deletedCount > 0) {
                await interaction.reply({ content: `✅ Removed rank role <@&${role.id}>.`, flags: 64 });
            } else {
                await interaction.reply({ content: `❌ Rank role <@&${role.id}> not found in database.`, flags: 64 });
            }
        } catch (error) {
            console.error(error);
            await interaction.reply({ content: '❌ Error removing rank role.', flags: 64 });
        }
    }
};
