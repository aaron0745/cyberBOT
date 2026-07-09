const { SlashCommandBuilder, PermissionFlagsBits } = require('discord.js');
const { Models } = require('../../database/mongoose');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('unhide_user')
        .setDescription('Unhide an agent (tester/admin), restoring normal scoring and logging')
        .addUserOption(option => 
            option.setName('user')
                .setDescription('The user to unhide')
                .setRequired(true)
        )
        .setDefaultMemberPermissions(PermissionFlagsBits.Administrator),

    async execute(interaction) {
        await interaction.deferReply({ flags: 64 });
        const user = interaction.options.getUser('user');

        try {
            let configDoc = await Models.Config.findOne({ key: 'hidden_users' });
            let hiddenList = [];

            if (configDoc && Array.isArray(configDoc.value)) {
                hiddenList = configDoc.value;
            }

            if (!hiddenList.includes(user.id)) {
                return await interaction.editReply({ content: `⚠️ User ${user.tag} is not hidden.` });
            }

            hiddenList = hiddenList.filter(id => id !== user.id);

            await Models.Config.findOneAndUpdate(
                { key: 'hidden_users' },
                { value: hiddenList },
                { upsert: true }
            );

            await interaction.editReply({ content: `✅ User **${user.tag}** has been unhidden. Normal scoring and logging have been restored for them.` });

            // Admin Logs channel notify
            const adminLogConfig = await Models.Config.findOne({ key: 'channel_admin_logs' });
            if (adminLogConfig) {
                try {
                    const logChannel = await interaction.client.channels.fetch(adminLogConfig.value);
                    if (logChannel) {
                        await logChannel.send(`👁️ Admin <@${interaction.user.id}> ran \`/unhide_user\` on <@${user.id}>.`);
                    }
                } catch (e) {
                    console.error('Error sending admin log:', e);
                }
            }

        } catch (error) {
            console.error('Error unhiding user:', error);
            await interaction.editReply({ content: '❌ An error occurred while unhiding the user.' });
        }
    }
};
