const { SlashCommandBuilder, PermissionFlagsBits } = require('discord.js');
const { Models } = require('../../database/mongoose');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('add_hint')
        .setDescription('Add a purchasable hint to a challenge')
        .addStringOption(option => option.setName('challenge_id').setDescription('The challenge ID').setRequired(true))
        .addStringOption(option => option.setName('hint_text').setDescription('The hint text').setRequired(true))
        .addIntegerOption(option => option.setName('cost').setDescription('Cost in points (0 for free)').setRequired(true).setMinValue(0))
        .setDefaultMemberPermissions(PermissionFlagsBits.Administrator),
    async execute(interaction) {
        const challenge_id = interaction.options.getString('challenge_id');
        const hint_text = interaction.options.getString('hint_text');
        const cost = interaction.options.getInteger('cost');
        
        try {
            const flag = await Models.Flag.findOne({ challenge_id });
            if (!flag) {
                return await interaction.reply({ content: `❌ Challenge ${challenge_id} not found.`, flags: 64 });
            }
            
            await Models.Hint.create({ challenge_id, hint_text, cost });
            const { updateChallengePost } = require('../../utils');
            await updateChallengePost(interaction.client, challenge_id);
            await interaction.reply({ content: `✅ Hint added to \`${challenge_id}\` for ${cost} points.`, flags: 64 });
        } catch (error) {
            console.error(error);
            await interaction.reply({ content: '❌ Error adding hint.', flags: 64 });
        }
    }
};
