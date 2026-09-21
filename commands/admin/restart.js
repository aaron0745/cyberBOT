const { SlashCommandBuilder, PermissionFlagsBits, EmbedBuilder } = require('discord.js');
const { Models } = require('../../database/mongoose');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('restart')
        .setDescription('Restart the CyberBOT process (Render supervisor reboots in ~5s)')
        .setDefaultMemberPermissions(PermissionFlagsBits.Administrator),
    async execute(interaction) {
        await interaction.deferReply({ flags: 64 });

        try {
            // Log to Admin Logs Channel if configured
            const adminLogConfig = await Models.Config.findOne({ key: 'channel_admin_logs' });
            if (adminLogConfig && adminLogConfig.value) {
                try {
                    const logChannel = await interaction.client.channels.fetch(adminLogConfig.value).catch(() => null);
                    if (logChannel) {
                        const logEmbed = new EmbedBuilder()
                            .setTitle('🔄 Restart Triggered')
                            .setDescription(`Admin <@${interaction.user.id}> initiated a bot process restart via \`/restart\`.`)
                            .setColor(0xFFA500)
                            .setTimestamp();
                        await logChannel.send({ embeds: [logEmbed] });
                    }
                } catch (e) {
                    console.error('Error logging restart:', e);
                }
            }

            const embed = new EmbedBuilder()
                .setTitle('🔄 Restarting CyberBOT...')
                .setDescription('The process is shutting down. Render container supervisor will reboot the service in ~5–10 seconds.')
                .setColor(0xFFA500);

            await interaction.editReply({ embeds: [embed] });

            // Allow Discord time to deliver the reply before exiting
            setTimeout(() => {
                process.exit(0);
            }, 1000);
        } catch (error) {
            console.error('Error executing restart command:', error);
            await interaction.editReply({ content: '❌ Error initiating restart.' });
        }
    }
};
