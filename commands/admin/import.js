const { SlashCommandBuilder, PermissionFlagsBits } = require('discord.js');
const { Models } = require('../../database/mongoose');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('import')
        .setDescription('⚠️ Overwrite the database with a backup file')
        .addAttachmentOption(option => 
            option.setName('backup_file')
                .setDescription('The JSON backup file to import')
                .setRequired(true)
        )
        .setDefaultMemberPermissions(PermissionFlagsBits.Administrator),

    async execute(interaction) {
        await interaction.deferReply({ flags: 64 });

        const attachment = interaction.options.getAttachment('backup_file');
        
        if (!attachment.name.endsWith('.json')) {
            return interaction.editReply({ content: '❌ Invalid file type. Please upload a .json backup file.' });
        }

        try {
            // Fetch the JSON file from Discord's CDN
            const response = await fetch(attachment.url);
            const data = await response.json();

            // Wipe existing data and import the new data
            if (data.flags) {
                await Models.Flag.deleteMany({});
                if (data.flags.length > 0) await Models.Flag.insertMany(data.flags);
            }
            if (data.roleRewards) {
                await Models.RoleReward.deleteMany({});
                if (data.roleRewards.length > 0) await Models.RoleReward.insertMany(data.roleRewards);
            }
            if (data.scores) {
                await Models.Score.deleteMany({});
                if (data.scores.length > 0) await Models.Score.insertMany(data.scores);
            }
            if (data.solves) {
                await Models.Solve.deleteMany({});
                if (data.solves.length > 0) await Models.Solve.insertMany(data.solves);
            }
            if (data.banlists) {
                await Models.Banlist.deleteMany({});
                if (data.banlists.length > 0) await Models.Banlist.insertMany(data.banlists);
            }
            if (data.hints) {
                await Models.Hint.deleteMany({});
                if (data.hints.length > 0) await Models.Hint.insertMany(data.hints);
            }
            if (data.configs) {
                await Models.Config.deleteMany({});
                if (data.configs.length > 0) await Models.Config.insertMany(data.configs);
            }
            if (data.unlockedHints) {
                await Models.UnlockedHint.deleteMany({});
                if (data.unlockedHints.length > 0) await Models.UnlockedHint.insertMany(data.unlockedHints);
            }

            await interaction.editReply({ content: '✅ Database successfully overwritten and imported from backup!' });
        } catch (error) {
            console.error('Import error:', error);
            await interaction.editReply({ content: '❌ An error occurred during import. Ensure the JSON is valid.' });
        }
    },
};
