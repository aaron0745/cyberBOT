const { SlashCommandBuilder, PermissionFlagsBits } = require('discord.js');
const { Models } = require('../../database/mongoose');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('revoke')
        .setDescription('Remove a solve and deduct points')
        .addUserOption(option => option.setName('user').setDescription('The user').setRequired(true))
        .addStringOption(option => option.setName('challenge_id').setDescription('The challenge ID').setRequired(true))
        .addStringOption(option => option.setName('confirm').setDescription("Type 'YES' to confirm").setRequired(true))
        .setDefaultMemberPermissions(PermissionFlagsBits.Administrator),
    async execute(interaction) {
        const user = interaction.options.getUser('user');
        const challenge_id = interaction.options.getString('challenge_id');
        const confirm = interaction.options.getString('confirm');
        
        if (confirm !== 'YES') {
            return await interaction.reply({ content: '❌ Confirmation failed. Type YES to confirm.', flags: 64 });
        }
        
        try {
            const flag = await Models.Flag.findOne({ challenge_id });
            if (!flag) {
                return await interaction.reply({ content: `❌ Challenge ${challenge_id} not found.`, flags: 64 });
            }
            
            // Get all solvers sorted by time
            const solvers = await Models.Solve.find({ challenge_id }).sort({ timestamp: 1 });
            const targetIndex = solvers.findIndex(s => s.user_id === user.id);

            if (targetIndex === -1) {
                return await interaction.reply({ content: `❌ User ${user.tag} has not solved \`${challenge_id}\`.`, flags: 64 });
            }

            const getBonus = (idx) => {
                if (idx === 0) return 50;
                if (idx === 1) return 25;
                if (idx === 2) return 10;
                return 0;
            };

            const userBonus = getBonus(targetIndex);
            
            let totalDeduction = 0;
            if (solvers[targetIndex].points_awarded !== undefined && solvers[targetIndex].points_awarded !== null) {
                totalDeduction = solvers[targetIndex].points_awarded;
            } else {
                totalDeduction = flag.points + userBonus;
            }

            // Delete solve
            await Models.Solve.deleteOne({ user_id: user.id, challenge_id });
            
            // Deduct from revoked user
            await Models.Score.updateOne(
                { user_id: user.id },
                { $inc: { points: -totalDeduction } }
            );

            // Shift bonuses for subsequent solvers
            for (let i = targetIndex + 1; i < solvers.length; i++) {
                const shiftUser = solvers[i].user_id;
                const oldBonus = getBonus(i);
                const newBonus = getBonus(i - 1);
                const diff = newBonus - oldBonus;
                
                if (diff > 0) {
                    await Models.Score.updateOne(
                        { user_id: shiftUser },
                        { $inc: { points: diff } }
                    );
                    if (solvers[i].points_awarded !== undefined && solvers[i].points_awarded !== null) {
                        await Models.Solve.updateOne(
                            { _id: solvers[i]._id },
                            { $inc: { points_awarded: diff } }
                        );
                    }
                }
            }

            const { updateLeaderboard, updateChallengePost } = require('../../utils');
            await updateLeaderboard(interaction.client);
            await updateChallengePost(interaction.client, challenge_id);
 
            await interaction.reply({ content: `🚨 **REVOKED!** Removed solve for **${challenge_id}** from ${user.tag}.\n🔻 Deducted **${totalDeduction} points** (Base: ${flag.points} + Bonus: ${userBonus}).\n⬆️ System auto-shifted bonuses to subsequent solvers.`, flags: 64 });

            const adminLogConfig = await Models.Config.findOne({ key: 'channel_admin_logs' });
            if (adminLogConfig) {
                try {
                    const logChannel = await interaction.client.channels.fetch(adminLogConfig.value);
                    if (logChannel) {
                        await logChannel.send(`🛡️ Admin <@${interaction.user.id}> ran \`/revoke\` on <@${user.id}> for **${challenge_id}**.`);
                    }
                } catch (e) {
                    console.error('Error sending admin log:', e);
                }
            }
        } catch (error) {
            console.error(error);
            await interaction.reply({ content: '❌ Error revoking solve.', flags: 64 });
        }
    }
};
