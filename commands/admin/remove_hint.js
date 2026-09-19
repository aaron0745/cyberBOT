const { SlashCommandBuilder, PermissionFlagsBits } = require('discord.js');
const { Models } = require('../../database/mongoose');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('remove_hint')
        .setDescription('Remove a hint')
        .addStringOption(option => option.setName('challenge_id').setDescription('The challenge ID').setRequired(true).setAutocomplete(true))
        .addIntegerOption(option => option.setName('hint_index').setDescription('The index of the hint to remove (1-based)').setRequired(true))
        .setDefaultMemberPermissions(PermissionFlagsBits.Administrator),
    async execute(interaction) {
        const challenge_id = interaction.options.getString('challenge_id');
        const index = interaction.options.getInteger('hint_index') - 1;
        
        try {
            const hints = await Models.Hint.find({ challenge_id });
            if (index < 0 || index >= hints.length) {
                return await interaction.reply({ content: `❌ Invalid hint index for \`${challenge_id}\`.`, flags: 64 });
            }
            
            const hintToRemove = hints[index];
            
            // Refund points to users who bought the hint
            const unlockedHints = await Models.UnlockedHint.find({ hint_id: hintToRemove._id.toString() });
            let anyRefunded = false;
            for (const unlocked of unlockedHints) {
                const refundAmount = unlocked.cost_paid !== undefined ? unlocked.cost_paid : hintToRemove.cost;
                if (refundAmount > 0) {
                    await Models.Score.updateOne(
                        { user_id: unlocked.user_id },
                        { $inc: { points: refundAmount } }
                    );
                    anyRefunded = true;
                }
            }
            // Delete all UnlockedHint records for this hint
            await Models.UnlockedHint.deleteMany({ hint_id: hintToRemove._id.toString() });

            await Models.Hint.deleteOne({ _id: hintToRemove._id });
            
            const { updateChallengePost, updateLeaderboard } = require('../../utils');
            await updateChallengePost(interaction.client, challenge_id);
            if (anyRefunded) {
                await updateLeaderboard(interaction.client);
            }
            
            await interaction.reply({ content: `✅ Hint ${index + 1} removed from \`${challenge_id}\` and points refunded if applicable.`, flags: 64 });
        } catch (error) {
            console.error(error);
            await interaction.reply({ content: '❌ Error removing hint.', flags: 64 });
        }
    }
};
