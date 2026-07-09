const { SlashCommandBuilder, PermissionFlagsBits } = require('discord.js');
const { Models } = require('../../database/mongoose');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('reset_config')
        .setDescription('Wipe all channel/role configurations')
        .setDefaultMemberPermissions(PermissionFlagsBits.Administrator),
    async execute(interaction) {
        try {
            const adminLogConfig = await Models.Config.findOne({ key: 'channel_admin_logs' });
            if (adminLogConfig && adminLogConfig.value) {
                try {
                    const logChannel = await interaction.client.channels.fetch(adminLogConfig.value);
                    if (logChannel) {
                        await logChannel.send(`🛡️ Admin <@${interaction.user.id}> ran \`/reset_config\`. All configurations have been reset.`);
                    }
                } catch (e) {
                    console.error('Error logging reset_config:', e);
                }
            }

            await Models.Config.deleteMany({});
            await interaction.reply({ content: '✅ All channel and role configurations have been reset.', flags: 64 });
        } catch (error) {
            console.error(error);
            await interaction.reply({ content: '❌ Error resetting configurations.', flags: 64 });
        }
    }
};
