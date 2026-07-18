const { SlashCommandBuilder, PermissionFlagsBits } = require('discord.js');
const { Models } = require('../../database/mongoose');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('edit')
        .setDescription('Edit a challenge')
        .addStringOption(option => option.setName('challenge_id').setDescription('The challenge ID').setRequired(true).setAutocomplete(true))
        .addIntegerOption(option => option.setName('points').setDescription('New point value').setRequired(false).setMinValue(0))
        .addStringOption(option => option.setName('flag_text').setDescription('New flag text').setRequired(false))
        .addStringOption(option => option.setName('category').setDescription('New category').setRequired(false))
        .addStringOption(option => option.setName('image_url').setDescription('New image URL').setRequired(false))
        .addStringOption(option => option.setName('description').setDescription('New description').setRequired(false))
        .addStringOption(option => option.setName('connection_info').setDescription('New connection info').setRequired(false))
        .addStringOption(option => option.setName('start_time').setDescription('New start time (DD/MM HH:MM)').setRequired(false))
        .addStringOption(option => option.setName('end_time').setDescription('New end time (DD/MM HH:MM)').setRequired(false))
        .setDefaultMemberPermissions(PermissionFlagsBits.Administrator),
    async execute(interaction) {
        await interaction.deferReply({ flags: 64 });
        const challenge_id = interaction.options.getString('challenge_id');
        const points = interaction.options.getInteger('points');
        const flag_text = interaction.options.getString('flag_text');
        const category = interaction.options.getString('category');
        const image_url = interaction.options.getString('image_url');
        const description = interaction.options.getString('description');
        const connection_info = interaction.options.getString('connection_info');
        const start_time_str = interaction.options.getString('start_time');
        const end_time_str = interaction.options.getString('end_time');

        function parseDateStr(str) {
            if (!str) return null;
            try {
                const now = new Date();
                const [datePart, timePart] = str.split(' ');
                const [day, month] = datePart.split('/');
                const [hour, minute] = timePart.split(':');
                const d = new Date(now.getFullYear(), parseInt(month)-1, parseInt(day), parseInt(hour), parseInt(minute));
                const unix = Math.floor(d.getTime() / 1000);
                if (isNaN(unix)) return null;
                return unix;
            } catch (e) {
                return null;
            }
        }
        
        let start_time = null;
        let end_time = null;

        if (start_time_str) {
            start_time = parseDateStr(start_time_str);
            if (!start_time) return interaction.editReply({ content: "❌ **Invalid start_time format!** Use `DD/MM HH:MM` (e.g. `25/12 14:00`)." });
        }
        if (end_time_str) {
            end_time = parseDateStr(end_time_str);
            if (!end_time) return interaction.editReply({ content: "❌ **Invalid end_time format!** Use `DD/MM HH:MM` (e.g. `25/12 14:00`)." });
        }
        
        try {
            const flag = await Models.Flag.findOne({ challenge_id });
            if (!flag) {
                return await interaction.editReply({ content: `❌ Challenge ${challenge_id} not found.` });
            }
            
            const oldPoints = flag.points;
            const oldFlagText = flag.flag_text;
            const oldCategory = flag.category;
            const oldImageUrl = flag.image_url;
            const oldDescription = flag.description;
            const oldConnectionInfo = flag.connection_info;
            const oldStartTime = flag.start_time;
            const oldEndTime = flag.end_time;

            let updated = false;
            const diff = [];

            if (points !== null && points !== oldPoints) { flag.points = points; diff.push(`- **Points:** \`${oldPoints}\` ➡️ \`${points}\``); updated = true; }
            if (flag_text !== null && flag_text !== oldFlagText) { flag.flag_text = flag_text; diff.push(`- **Flag:** \`[REDACTED]\` ➡️ \`[REDACTED]\``); updated = true; }
            if (category !== null && category !== oldCategory) { flag.category = category; diff.push(`- **Category:** \`${oldCategory || 'None'}\` ➡️ \`${category}\``); updated = true; }
            if (image_url !== null && image_url !== oldImageUrl) { flag.image_url = image_url; diff.push(`- **Image URL:** \`${oldImageUrl || 'None'}\` ➡️ \`${image_url}\``); updated = true; }
            if (description !== null && description !== oldDescription) { flag.description = description; diff.push(`- **Description:** Updated`); updated = true; }
            if (connection_info !== null && connection_info !== oldConnectionInfo) { flag.connection_info = connection_info; diff.push(`- **Connection Info:** Updated`); updated = true; }
            if (start_time !== null && start_time !== oldStartTime) { flag.start_time = start_time; diff.push(`- **Start Time:** ${oldStartTime ? `<t:${oldStartTime}:F>` : '`None`'} ➡️ <t:${start_time}:F>`); updated = true; }
            if (end_time !== null && end_time !== oldEndTime) { flag.end_time = end_time; diff.push(`- **End Time:** ${oldEndTime ? `<t:${oldEndTime}:F>` : '`None`'} ➡️ <t:${end_time}:F>`); updated = true; }
            
            if (updated) {
                await flag.save();

                // If live message exists, edit the embed
                if (flag.channel_id && flag.msg_id) {
                    try {
                        const channel = await interaction.client.channels.fetch(flag.channel_id);
                        if (channel) {
                            const msg = await channel.messages.fetch(flag.msg_id);
                            if (msg && msg.embeds.length > 0) {
                                const oldEmbed = msg.embeds[0];
                                
                                let finalDesc = `**Objective:**\n\`\`\`text\n${flag.description || 'N/A'}\n\`\`\``;
                                if (flag.connection_info) {
                                    finalDesc += `\n**📡 Connection:**\n\`\`\`text\n${flag.connection_info}\n\`\`\``;
                                }

                                const { EmbedBuilder } = require('discord.js');
                                const newEmbed = new EmbedBuilder(oldEmbed.toJSON())
                                    .setDescription(finalDesc);

                                // Replace fields keeping First Blood intact if it exists
                                const fields = [];
                                fields.push({ name: '💰 Bounty', value: `**${flag.points} Points**`, inline: true });
                                fields.push({ name: '📂 Category', value: `**${flag.category}**`, inline: true });
                                if (flag.end_time) {
                                    fields.push({ name: '⏳ Time Left', value: `<t:${flag.end_time}:R>`, inline: true });
                                }
                                
                                const firstBloodField = oldEmbed.fields.find(f => f.name === '🩸 First Blood');
                                if (firstBloodField) {
                                    fields.push(firstBloodField);
                                } else {
                                    fields.push({ name: '🩸 First Blood', value: '*Waiting...*', inline: false });
                                }
                                
                                newEmbed.setFields(fields);
                                
                                if (flag.image_url) {
                                    newEmbed.setImage(flag.image_url);
                                } else {
                                    newEmbed.setImage(null);
                                }

                                await msg.edit({ embeds: [newEmbed] });
                            }
                        }
                    } catch (e) {
                        console.error('Failed to update live Discord message for challenge:', e);
                    }
                }

                // Send log to channel_admin_logs
                const adminLogConfig = await Models.Config.findOne({ key: 'channel_admin_logs' });
                if (adminLogConfig && diff.length > 0) {
                    try {
                        const logChannel = await interaction.client.channels.fetch(adminLogConfig.value);
                        if (logChannel) {
                            const { EmbedBuilder } = require('discord.js');
                            const embed = new EmbedBuilder()
                                .setTitle(`📝 Challenge Edited: ${challenge_id}`)
                                .setDescription(`Admin <@${interaction.user.id}> modified the challenge:\n\n${diff.join('\n')}`)
                                .setColor(0xFFA500)
                                .setTimestamp();
                            await logChannel.send({ embeds: [embed] });
                        }
                    } catch (e) {
                        console.error('Error sending edit admin log:', e);
                    }
                }

                await interaction.editReply({ content: `✅ Challenge ${challenge_id} updated successfully.` });
            } else {
                await interaction.editReply({ content: '⚠️ No changes provided.' });
            }
        } catch (error) {
            console.error(error);
            await interaction.editReply({ content: '❌ Error editing challenge.' });
        }
    }
};
