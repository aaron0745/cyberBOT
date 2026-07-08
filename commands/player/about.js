const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('about')
        .setDescription('View system specifications and development credits'),
    async execute(interaction) {
        // Hardcoded mentions using absolute User IDs
        const m1 = "<@758276303446343700>"; // doc_x_
        const m2 = "<@769098666732421141>"; // ashil4451

        const embed = new EmbedBuilder()
            .setTitle("🛡️ CyberBOT: SYSTEM SPECIFICATIONS")
            .setDescription(
                "**CyberBOT** is a next-generation CTF engine built for high-performance " +
                "digital competitions. It handles mission deployment, real-time leaderboards, " +
                "and Agent identification with military-grade precision."
            )
            .setColor(0x00FF78); // from_rgb(0, 255, 120)

        embed.addFields(
            {
                name: "🛠️ DEVELOPMENT",
                value: `**Built & Designed by:** ${m1}\n**Technical Assistance:** ${m2}`,
                inline: false
            },
            {
                name: "⚙️ CORE ENGINE",
                value: "```ini\n[ SYS ] CyberBOT\n[ KER ] Node.js v20\n[ DB  ] MongoDB\n[ API ] discord.js\n```",
                inline: true
            },
            {
                name: "🛰️ SATELLITE UPLINK",
                value: `\`\`\`ini\n[ STAT ] ONLINE\n[ PING ] ${Math.round(interaction.client.ws.ping)}ms\n[ ENC  ] AES-256\n[ LINK ] ESTABLISHED\n\`\`\``,
                inline: true
            }
        );

        embed.setFooter({ text: "Managed by the ARCHITECT OF THE SIMULATION" });

        // Use the bot's avatar as the thumbnail
        if (interaction.client.user.avatarURL()) {
            embed.setThumbnail(interaction.client.user.displayAvatarURL());
        }

        await interaction.reply({ embeds: [embed], flags: 64 });
    }
};
