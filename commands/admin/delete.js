const { SlashCommandBuilder, PermissionFlagsBits } = require('discord.js');
const { Models } = require('../../database/mongoose');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('delete')
        .setDescription('Deletes a challenge by challenge_id')
        .addStringOption(option =>
            option.setName('challenge_id')
                .setDescription('The ID of the challenge to delete')
                .setRequired(true))
        .addStringOption(option => option.setName('confirm').setDescription("Type 'YES' to confirm").setRequired(true))
        .setDefaultMemberPermissions(PermissionFlagsBits.Administrator),
    async execute(interaction) {
        await interaction.deferReply({ flags: 64 });
        const challengeId = interaction.options.getString('challenge_id');
        const confirm = interaction.options.getString('confirm');
        
        if (confirm !== 'YES') {
            return interaction.editReply({ content: '❌ Confirmation failed. Type YES to confirm.' });
        }
        
        try {
            const challenge = await Models.Flag.findOne({ challenge_id: challengeId });
            
            if (!challenge) {
                return interaction.editReply({ content: `❌ Challenge \`${challengeId}\` not found.` });
            }

            // Deduct points+bonuses from all solvers
            const solves = await Models.Solve.find({ challenge_id: challengeId }).sort({ timestamp: 1 });
            for (let i = 0; i < solves.length; i++) {
                const solve = solves[i];
                let pointsToDeduct = 0;
                if (solve.points_awarded !== undefined && solve.points_awarded !== null) {
                    pointsToDeduct = solve.points_awarded;
                } else {
                    let bonus = 0;
                    if (i === 0) bonus = 50;
                    else if (i === 1) bonus = 25;
                    else if (i === 2) bonus = 10;
                    pointsToDeduct = challenge.points + bonus;
                }
                await Models.Score.updateOne({ user_id: solve.user_id }, { $inc: { points: -pointsToDeduct } });
            }
            await Models.Solve.deleteMany({ challenge_id: challengeId });

            // Refund hint purchases
            const hints = await Models.Hint.find({ challenge_id: challengeId });
            for (const hint of hints) {
                if (hint.cost > 0) {
                    const unlockedHints = await Models.UnlockedHint.find({ hint_id: hint._id.toString() });
                    for (const unlocked of unlockedHints) {
                        await Models.Score.updateOne({ user_id: unlocked.user_id }, { $inc: { points: hint.cost } });
                    }
                    await Models.UnlockedHint.deleteMany({ hint_id: hint._id.toString() });
                }
            }
            await Models.Hint.deleteMany({ challenge_id: challengeId });

            // Physically delete the live Discord post/message if it exists using channel_id and msg_id
            if (challenge.channel_id) {
                try {
                    const channel = await interaction.client.channels.fetch(challenge.channel_id);
                    if (channel) {
                        if (challenge.msg_id) {
                            try {
                                const msg = await channel.messages.fetch(challenge.msg_id);
                                if (msg) await msg.delete();
                            } catch (e) {
                                console.error('Error deleting msg_id:', e);
                            }
                        }
                        if (challenge.file_msg_id) {
                            try {
                                const fileMsg = await channel.messages.fetch(challenge.file_msg_id);
                                if (fileMsg) await fileMsg.delete();
                            } catch (e) {
                                console.error('Error deleting file_msg_id:', e);
                            }
                        }
                    }
                } catch (e) {
                    console.error('Error fetching channel for deletion:', e);
                }
            }

            // Finally, delete the challenge itself
            await Models.Flag.deleteOne({ challenge_id: challengeId });
            
            const adminLogConfig = await Models.Config.findOne({ key: 'channel_admin_logs' });
            if (adminLogConfig) {
                try {
                    const logChannel = await interaction.client.channels.fetch(adminLogConfig.value);
                    if (logChannel) {
                        await logChannel.send(`🛡️ Admin <@${interaction.user.id}> ran \`/delete\` on **${challengeId}**.`);
                    }
                } catch (e) {
                    console.error('Error sending admin log:', e);
                }
            }

            const { updateLeaderboard } = require('../../utils');
            await updateLeaderboard(interaction.client);
 
            await interaction.editReply({ content: `✅ Challenge \`${challengeId}\` has been deleted successfully. Points and hints refunded.` });
        } catch (error) {
            console.error(error);
            await interaction.editReply({ content: '❌ An error occurred while deleting the challenge.' });
        }
    },
};
