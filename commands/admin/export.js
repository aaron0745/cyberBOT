const { SlashCommandBuilder, PermissionFlagsBits, AttachmentBuilder } = require('discord.js');
const { Models } = require('../../database/mongoose');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('export')
        .setDescription('Download the current database backup as a JSON file')
        .setDefaultMemberPermissions(PermissionFlagsBits.Administrator),

    async execute(interaction) {
        await interaction.deferReply({ flags: 64 });

        try {
            const backup = {
                flags: await Models.Flag.find({}),
                roleRewards: await Models.RoleReward.find({}),
                scores: await Models.Score.find({}),
                solves: await Models.Solve.find({}),
                banlists: await Models.Banlist.find({}),
                hints: await Models.Hint.find({}),
                configs: await Models.Config.find({}),
                unlockedHints: await Models.UnlockedHint.find({})
            };

            const jsonString = JSON.stringify(backup, null, 2);
            const buffer = Buffer.from(jsonString, 'utf-8');
            const attachment = new AttachmentBuilder(buffer, { name: `CyberBOT_backup_${Date.now()}.json` });

            await interaction.editReply({ 
                content: '✅ Database successfully exported.', 
                files: [attachment] 
            });
        } catch (error) {
            console.error('Export error:', error);
            await interaction.editReply({ content: '❌ An error occurred during export.' });
        }
    },
};
