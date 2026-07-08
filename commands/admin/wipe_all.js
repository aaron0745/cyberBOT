const { SlashCommandBuilder, PermissionFlagsBits, ModalBuilder, TextInputBuilder, TextInputStyle, ActionRowBuilder } = require('discord.js');
const { Models } = require('../../database/mongoose');
const { updateLeaderboard } = require('../../utils');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('wipe_all')
        .setDescription('⚠️ NUCLEAR: Delete EVERYTHING (Players, Flags, Solves)')
        .setDefaultMemberPermissions(PermissionFlagsBits.Administrator),
    async execute(interaction) {
        const modal = new ModalBuilder()
            .setCustomId('wipe_modal')
            .setTitle('☢️  NUCLEAR WIPEOUT — CONFIRM');
            
        const confirmInput = new TextInputBuilder()
            .setCustomId('confirm_input')
            .setLabel('Type  CONFIRM WIPE  to erase all data')
            .setPlaceholder('CONFIRM WIPE')
            .setStyle(TextInputStyle.Short)
            .setMinLength(12)
            .setMaxLength(12)
            .setRequired(true);
            
        const row = new ActionRowBuilder().addComponents(confirmInput);
        modal.addComponents(row);
        
        await interaction.showModal(modal);
        
        try {
            const submitted = await interaction.awaitModalSubmit({
                time: 60000,
                filter: i => i.user.id === interaction.user.id && i.customId === 'wipe_modal',
            });
            
            const phrase = submitted.fields.getTextInputValue('confirm_input').trim().toUpperCase();
            if (phrase !== 'CONFIRM WIPE') {
                return await submitted.reply({ content: '❌ **Wrong phrase.** Wipe aborted — nothing was deleted.', flags: 64 });
            }
            
            await submitted.deferReply({ flags: 64 });
            
            const adminLogConfig = await Models.Config.findOne({ key: 'channel_admin_logs' });
            const adminLogChannelId = adminLogConfig ? adminLogConfig.value : null;

            await Models.Flag.deleteMany({});
            await Models.Score.deleteMany({});
            await Models.Solve.deleteMany({});
            await Models.Banlist.deleteMany({});
            await Models.RoleReward.deleteMany({});
            await Models.Config.deleteMany({});
            await Models.Hint.deleteMany({});
            await Models.UnlockedHint.deleteMany({});
            
            await updateLeaderboard(interaction.client);
            
            await submitted.editReply({ content: '☢️ **NUCLEAR WIPEOUT COMPLETE.**\nThe database is empty.' });
            
            if (adminLogChannelId) {
                try {
                    const logChan = await interaction.client.channels.fetch(adminLogChannelId);
                    if (logChan) logChan.send(`☢️ Admin <@${interaction.user.id}> ran \`/wipe_all\`.`);
                } catch(e){}
            }
            
        } catch (error) {
            // User probably closed modal or it timed out
        }
    }
};
