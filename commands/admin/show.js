const { SlashCommandBuilder, PermissionFlagsBits, EmbedBuilder } = require('discord.js');
const { Models } = require('../../database/mongoose');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('show')
        .setDescription('Show details for a specific challenge')
        .addStringOption(option => option.setName('challenge_id').setDescription('The challenge ID').setRequired(true).setAutocomplete(true))
        .setDefaultMemberPermissions(PermissionFlagsBits.Administrator),
    async execute(interaction) {
        const challenge_id = interaction.options.getString('challenge_id');
        try {
            const flag = await Models.Flag.findOne({ challenge_id });
            if (!flag) {
                return await interaction.reply({ content: `❌ Challenge ${challenge_id} not found.`, flags: 64 });
            }
            
            const embed = new EmbedBuilder()
                .setTitle(`🔐 Details: ${flag.challenge_id}`)
                .addFields(
                    { name: '🚩 Flag', value: `\`${flag.flag_text}\``, inline: false },
                    { name: '💰 Points', value: flag.points.toString(), inline: true },
                    { name: '📂 Category', value: flag.category || 'General', inline: true },
                    { name: '🖼️ Image URL', value: flag.image_url ? `[Link](${flag.image_url})` : 'None', inline: true }
                )
                .setColor('#ffcc00');
                
            if (flag.description) {
                embed.addFields({ name: '📝 Description', value: `\`\`\`text\n${flag.description}\n\`\`\``, inline: false });
            }
            if (flag.connection_info) {
                embed.addFields({ name: '📡 Connection Info', value: `\`\`\`text\n${flag.connection_info}\n\`\`\``, inline: false });
            }
            
            const timeInfo = [];
            timeInfo.push(`Posted: ${flag.posted_at ? `<t:${flag.posted_at}:F>` : 'Not Posted'}`);
            timeInfo.push(`Start: ${flag.start_time ? `<t:${flag.start_time}:F>` : 'None'}`);
            timeInfo.push(`End: ${flag.end_time ? `<t:${flag.end_time}:F>` : 'None'}`);
            embed.addFields({ name: '⏳ Schedule Info', value: timeInfo.join('\n'), inline: false });
            
            embed.addFields(
                { name: '📍 Channel ID', value: flag.channel_id ? `\`${flag.channel_id}\`` : 'None', inline: true },
                { name: '✉️ Message ID', value: flag.msg_id ? `\`${flag.msg_id}\`` : 'None', inline: true },
                { name: '📎 File Upload', value: flag.file_url ? `[Link](${flag.file_url})` : (flag.file_msg_id ? `Msg ID: \`${flag.file_msg_id}\`` : 'None'), inline: true }
            );
                
            await interaction.reply({ embeds: [embed], flags: 64 });
        } catch (error) {
            console.error(error);
            await interaction.reply({ content: '❌ Error showing challenge.', flags: 64 });
        }
    }
};
