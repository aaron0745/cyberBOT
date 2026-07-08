const { SlashCommandBuilder, PermissionFlagsBits } = require('discord.js');
const { Models } = require('../../database/mongoose');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('unban_user')
        .setDescription('Unbans a user')
        .addUserOption(option =>
            option.setName('user')
                .setDescription('The user to unban')
                .setRequired(true))
        .setDefaultMemberPermissions(PermissionFlagsBits.Administrator),
    async execute(interaction) {
        const user = interaction.options.getUser('user');
        
        try {
            const deleted = await Models.Banlist.findOneAndDelete({ user_id: user.id });
            
            if (deleted) {
                await interaction.reply({ content: `✅ User ${user.tag} has been unbanned successfully.`, flags: 64 });
                
                const adminLogConfig = await Models.Config.findOne({ key: 'channel_admin_logs' });
                if (adminLogConfig) {
                    try {
                        const logChannel = await interaction.client.channels.fetch(adminLogConfig.value);
                        if (logChannel) {
                            await logChannel.send(`✅ Admin <@${interaction.user.id}> ran \`/unban_user\` on <@${user.id}>.`);
                        }
                    } catch (e) {
                        console.error('Error sending admin log:', e);
                    }
                }
            } else {
                await interaction.reply({ content: `❌ User ${user.tag} is not currently banned.`, flags: 64 });
            }
        } catch (error) {
            console.error(error);
            await interaction.reply({ content: '❌ An error occurred while unbanning the user.', flags: 64 });
        }
    },
};
