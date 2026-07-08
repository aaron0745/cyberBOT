const { SlashCommandBuilder, PermissionFlagsBits } = require('discord.js');
const { Models } = require('../../database/mongoose');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('ban_user')
        .setDescription('Bans a user from participating')
        .addUserOption(option =>
            option.setName('user')
                .setDescription('The user to ban')
                .setRequired(true))
        .setDefaultMemberPermissions(PermissionFlagsBits.Administrator),
    async execute(interaction) {
        const user = interaction.options.getUser('user');
        
        try {
            const existingBan = await Models.Banlist.findOne({ user_id: user.id });
            
            if (existingBan) {
                return await interaction.reply({ content: `User ${user.tag} is already banned.`, flags: 64 });
            }
            
            await Models.Banlist.create({ user_id: user.id });
            await interaction.reply({ content: `✅ User ${user.tag} has been banned successfully.`, flags: 64 });

            const adminLogConfig = await Models.Config.findOne({ key: 'channel_admin_logs' });
            if (adminLogConfig) {
                try {
                    const logChannel = await interaction.client.channels.fetch(adminLogConfig.value);
                    if (logChannel) {
                        await logChannel.send(`🔨 Admin <@${interaction.user.id}> ran \`/ban_user\` on <@${user.id}>.`);
                    }
                } catch (e) {
                    console.error('Error sending admin log:', e);
                }
            }
        } catch (error) {
            console.error(error);
            await interaction.reply({ content: '❌ An error occurred while banning the user.', flags: 64 });
        }
    },
};
