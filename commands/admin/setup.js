const { SlashCommandBuilder, PermissionFlagsBits } = require('discord.js');
const { Models } = require('../../database/mongoose');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('setup')
        .setDescription('Configure channels and roles for CyberBOT')
        .addChannelOption(option => option.setName('leaderboard_channel').setDescription('Where the leaderboard updates').setRequired(false))
        .addChannelOption(option => option.setName('challenge_logs').setDescription('Correct solves and collusion warnings').setRequired(false))
        .addChannelOption(option => option.setName('wrong_submissions').setDescription('Every failed flag attempt').setRequired(false))
        .addChannelOption(option => option.setName('general_channel').setDescription('Main chat for announcements').setRequired(false))
        .addRoleOption(option => option.setName('champion_role').setDescription('Role for the #1 player').setRequired(false))
        .addChannelOption(option => option.setName('channel_admin_logs').setDescription('Where admin actions are logged').setRequired(false))
        .setDefaultMemberPermissions(PermissionFlagsBits.Administrator),
    async execute(interaction) {
        const leaderboard_channel = interaction.options.getChannel('leaderboard_channel');
        const challenge_logs = interaction.options.getChannel('challenge_logs');
        const wrong_submissions = interaction.options.getChannel('wrong_submissions');
        const general_channel = interaction.options.getChannel('general_channel');
        const champion_role = interaction.options.getRole('champion_role');
        const channel_admin_logs = interaction.options.getChannel('channel_admin_logs');
        
        let updates = [];
        try {
            if (leaderboard_channel) {
                await Models.Config.findOneAndUpdate({ key: 'channel_leaderboard' }, { value: leaderboard_channel.id }, { upsert: true });
                updates.push(`✅ Leaderboard Channel: <#${leaderboard_channel.id}>`);
            }
            if (challenge_logs) {
                await Models.Config.findOneAndUpdate({ key: 'channel_challenge_logs' }, { value: challenge_logs.id }, { upsert: true });
                updates.push(`✅ Challenge Logs: <#${challenge_logs.id}>`);
            }
            if (wrong_submissions) {
                await Models.Config.findOneAndUpdate({ key: 'channel_wrong_submissions' }, { value: wrong_submissions.id }, { upsert: true });
                updates.push(`✅ Wrong Submissions: <#${wrong_submissions.id}>`);
            }
            if (general_channel) {
                await Models.Config.findOneAndUpdate({ key: 'channel_general' }, { value: general_channel.id }, { upsert: true });
                updates.push(`✅ General Channel: <#${general_channel.id}>`);
            }
            if (champion_role) {
                await Models.Config.findOneAndUpdate({ key: 'role_champion' }, { value: champion_role.id }, { upsert: true });
                updates.push(`👑 Champion Role: <@&${champion_role.id}>`);
            }
            if (channel_admin_logs) {
                await Models.Config.findOneAndUpdate({ key: 'channel_admin_logs' }, { value: channel_admin_logs.id }, { upsert: true });
                updates.push(`🛡️ Admin Logs Channel: <#${channel_admin_logs.id}>`);
            }
            
            if (updates.length > 0) {
                const { updateLeaderboard } = require('../../utils');
                await updateLeaderboard(interaction.client);
                await interaction.reply({ content: updates.join('\n'), flags: 64 });
            } else {
                await interaction.reply({ content: '⚠️ No configuration provided.', flags: 64 });
            }
        } catch (error) {
            console.error(error);
            await interaction.reply({ content: '❌ Error during setup.', flags: 64 });
        }
    }
};
