const { SlashCommandBuilder, PermissionFlagsBits } = require('discord.js');
const { Models } = require('../../database/mongoose');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('reset_config')
        .setDescription('Wipe all channel/role configurations')
        .setDefaultMemberPermissions(PermissionFlagsBits.Administrator),
    async execute(interaction) {
        try {
            await Models.Config.deleteMany({ key: { $in: ['channel_general', 'role_champion'] } });
            await interaction.reply({ content: '✅ Channel and Role configurations have been reset.', flags: 64 });
        } catch (error) {
            console.error(error);
            await interaction.reply({ content: '❌ Error resetting configurations.', flags: 64 });
        }
    }
};
