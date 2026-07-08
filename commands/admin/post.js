const { SlashCommandBuilder, PermissionFlagsBits, EmbedBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle } = require('discord.js');
const { Models } = require('../../database/mongoose');
const fs = require('fs');
const path = require('path');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('post')
        .setDescription('Post or schedule a challenge')
        .addStringOption(option => option.setName('challenge_id').setDescription('ID of the challenge to post').setRequired(true))
        .addStringOption(option => option.setName('start_time').setDescription('When to post (DD/MM HH:MM)').setRequired(true))
        .addStringOption(option => option.setName('end_time').setDescription('When it expires (DD/MM HH:MM)').setRequired(true))
        .addChannelOption(option => option.setName('channel').setDescription('Target channel').setRequired(false))
        .addStringOption(option => option.setName('description').setDescription('Brief objective').setRequired(false))
        .addStringOption(option => option.setName('connection_info').setDescription('Optional connection string').setRequired(false))
        .addAttachmentOption(option => option.setName('file').setDescription('Upload a file to attach').setRequired(false))
        .setDefaultMemberPermissions(PermissionFlagsBits.Administrator),

    async execute(interaction) {
        await interaction.deferReply({ flags: 64 });

        const challenge_id = interaction.options.getString('challenge_id');
        const targetChannel = interaction.options.getChannel('channel') || interaction.channel;
        const description = interaction.options.getString('description') || "No description provided.";
        const connection_info = interaction.options.getString('connection_info') || "";
        const fileAttachment = interaction.options.getAttachment('file');
        
        const start_time_str = interaction.options.getString('start_time');
        const end_time_str = interaction.options.getString('end_time');

        let start_time, end_time;
        try {
            const currentYear = new Date().getFullYear();
            const parseDateStr = (str) => {
                const [datePart, timePart] = str.split(' ');
                const [day, month] = datePart.split('/');
                const [hour, minute] = timePart.split(':');
                return Math.floor(new Date(currentYear, parseInt(month) - 1, parseInt(day), parseInt(hour), parseInt(minute)).getTime() / 1000);
            };
            start_time = parseDateStr(start_time_str);
            end_time = parseDateStr(end_time_str);
            if (isNaN(start_time) || isNaN(end_time)) throw new Error("Invalid");
        } catch (e) {
            return interaction.editReply({ content: "❌ **Invalid time format!** Use `DD/MM HH:MM` (e.g. `25/12 14:00`)." });
        }

        try {
            const flagData = await Models.Flag.findOne({ challenge_id });
            if (!flagData) {
                return interaction.editReply({ content: `❌ Challenge \`${challenge_id}\` not found in database.` });
            }

            let file_url = null;
            if (fileAttachment) {
                file_url = fileAttachment.url;
            }

            const current_time = Math.floor(Date.now() / 1000);
            
            // Save to database
            await Models.Flag.updateOne({ challenge_id }, {
                start_time, end_time, description, connection_info, file_url, channel_id: targetChannel.id, msg_id: null
            });

            if (start_time > current_time) {
                return interaction.editReply({ content: `📅 **Scheduled!** **${challenge_id}** will be posted to <#${targetChannel.id}> at <t:${start_time}:F>.` });
            }

            // Immediate Post
            let finalDesc = `**Objective:**\n\`\`\`text\n${description}\n\`\`\``;
            if (connection_info) finalDesc += `\n**📡 Connection:**\n\`\`\`text\n${connection_info}\n\`\`\``;

            const embed = new EmbedBuilder()
                .setTitle(`🛡️ MISSION: ${challenge_id}`)
                .setDescription(finalDesc)
                .setColor(0xff0000)
                .addFields(
                    { name: '💰 Bounty', value: `**${flagData.points} Points**`, inline: true },
                    { name: '📂 Category', value: `**${flagData.category || "General"}**`, inline: true },
                    { name: '⏳ Time Left', value: `<t:${end_time}:R>`, inline: true },
                    { name: '🩸 First Blood', value: '*Waiting...*', inline: false }
                );
            if (flagData.image_url) embed.setImage(flagData.image_url);
            if (file_url) embed.setFooter({ text: "📁 See attached file below" });

            const has_hints = await Models.Hint.countDocuments({ challenge_id }) > 0;
            const btnSubmit = new ButtonBuilder().setCustomId(`submit:${challenge_id}`).setLabel("Submit Flag").setStyle(ButtonStyle.Success).setEmoji("🚩");
            const btnHint = new ButtonBuilder().setCustomId(`hints:${challenge_id}`).setLabel("Hints").setStyle(ButtonStyle.Secondary).setEmoji("💡");

            const row = new ActionRowBuilder().addComponents(btnSubmit);
            if (has_hints) row.addComponents(btnHint);

            const postMsg = await targetChannel.send({ embeds: [embed], components: [row] });
            let fMsg = null;
            if (fileAttachment) fMsg = await targetChannel.send({ files: [fileAttachment.url] });

            await Models.Flag.updateOne({ challenge_id }, { msg_id: postMsg.id, file_msg_id: fMsg ? fMsg.id : null, posted_at: current_time });
            await interaction.editReply({ content: `✅ Posted **${challenge_id}** immediately!` });
        } catch (error) {
            console.error(error);
            await interaction.editReply({ content: `❌ Error posting challenge: ${error.message}` });
        }
    }
};
