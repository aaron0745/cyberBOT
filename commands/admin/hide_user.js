const { SlashCommandBuilder, PermissionFlagsBits } = require('discord.js');
const { Models } = require('../../database/mongoose');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('hide_user')
        .setDescription('Hide an agent (tester/admin) from score logging, solves lists, and hint costs')
        .addUserOption(option => 
            option.setName('user')
                .setDescription('The user to hide')
                .setRequired(true)
        )
        .setDefaultMemberPermissions(PermissionFlagsBits.Administrator),

    async execute(interaction) {
        await interaction.deferReply({ flags: 64 });
        const user = interaction.options.getUser('user');

        try {
            let configDoc = await Models.Config.findOne({ key: 'hidden_users' });
            let hiddenList = [];

            if (configDoc) {
                if (Array.isArray(configDoc.value)) {
                    hiddenList = configDoc.value;
                }
            }

            if (hiddenList.includes(user.id)) {
                return await interaction.editReply({ content: `⚠️ User ${user.tag} is already hidden.` });
            }

            hiddenList.push(user.id);

            await Models.Config.findOneAndUpdate(
                { key: 'hidden_users' },
                { value: hiddenList },
                { upsert: true }
            );

            await interaction.editReply({ content: `✅ User **${user.tag}** is now hidden. Their solves and purchases will not be recorded or logged.` });

            // Admin Logs channel notify
            const adminLogConfig = await Models.Config.findOne({ key: 'channel_admin_logs' });
            if (adminLogConfig) {
                try {
                    const logChannel = await interaction.client.channels.fetch(adminLogConfig.value);
                    if (logChannel) {
                        await logChannel.send(`👁️ Admin <@${interaction.user.id}> ran \`/hide_user\` on <@${user.id}>.`);
                    }
                } catch (e) {
                    console.error('Error sending admin log:', e);
                }
            }

        } catch (error) {
            console.error('Error hiding user:', error);
            await interaction.editReply({ content: '❌ An error occurred while hiding the user.' });
        }
    }
};
