const { SlashCommandBuilder, EmbedBuilder, PermissionFlagsBits } = require('discord.js');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('help')
        .setDescription('Accesses the complete operational manual for all system protocols'),
    async execute(interaction) {
        const agent_manual = 
            "🛡️ **`/profile [agent]`**\n" +
            "↳ Generates your high-res Agent ID card. Displays current Rank, total Score, and solve count. Mention another member to inspect their stats.\n\n" +
            "🏆 **`/leaderboard`**\n" +
            "↳ Opens the global standing interactive menu with ◀ ▶ buttons. Standings are sorted by points and millisecond-accurate solve times.\n\n" +
            "🛡️ **`/about`**\n" +
            "↳ Displays technical system specifications, real-time latency, and development credits.\n\n" +
            "📚 **`/help`**\n" +
            "↳ Accesses this complete operational manual for all system protocols.\n\n" +
            "🚩 **Flag Submission (Button)**\n" +
            "↳ Click 'Submit Flag' on any active mission post to enter the capture string. (Case-sensitive, 2s anti-spam cooldown).\n\n" +
            "💡 **Hint Acquisition (Button)**\n" +
            "↳ Click 'Hints' on a mission. Unlocking costs points. Hints are permanently stored privately for you.";

        const embed = new EmbedBuilder()
            .setTitle("📚 CyberBOT: COMPLETE FIELD MANUAL")
            .setDescription("Operational protocols for the high-performance CTF network.")
            .setColor(0x0047AB) // from_rgb(0, 71, 171)
            .addFields({ name: "🕵️ AGENT OPERATIONS (Available to All)", value: agent_manual, inline: false });

        if (interaction.member.permissions.has(PermissionFlagsBits.Administrator)) {
            const setup_manual = 
                "⚙️ **`/setup`**\n↳ Links CyberBOT to your server channels (Leaderboard, Logs, General) and designates the Champion role.\n\n" +
                "🆙 **`/set_rank_role [role] [pts]`**\n↳ Defines a dynamic point milestone. CyberBOT will auto-promote players as they reach these scores.\n\n" +
                "❌ **`/remove_rank_role [role]`**\n↳ Deletes a specific rank milestone from the auto-promotion engine.\n\n" +
                "📋 **`/list_rank_roles`**\n↳ Displays all currently configured point requirements and their associated roles.\n\n" +
                "📦 **`/export`**\n↳ Generates and sends a downloadable `CyberBOT_backup.json` file for local backup.\n\n" +
                "📥 **`/import [file]`**\n↳ Live-swaps the current database with a backup file. Zero-downtime restoration.\n\n" +
                "🔄 **`/reset_config`**\n↳ Wipes only the channel and role settings, leaving player data intact.";

            const mission_manual = 
                "📝 **`/create`**\n↳ Registers a new mission ID, point value, flag, and category in draft mode (hidden from players).\n\n" +
                "📅 **`/post`**\n↳ Publishes a mission immediately or schedules it. Supports file attachments and custom deadlines.\n\n" +
                "🛠️ **`/edit`**\n↳ Modifies any mission attribute (Renaming ID, changing points, flag text, or updating scheduling times).\n\n" +
                "🗑️ **`/delete`**\n↳ Purges a mission. **Recursive Logic:** Automatically refunds points to every player who bought hints for it.\n\n" +
                "📋 **`/list`**\n↳ Displays a summary of all registered missions and their current status (Posted vs. Draft).\n\n" +
                "🔐 **`/show [id]`**\n↳ Reveals all hidden data for a specific mission, including the plain-text capture flag.";

            const maint_manual = 
                "🩸 **`/revoke [member] [id]`**\n↳ Removes a solve record. Deducts base points and any First Blood bonuses earned by the agent.\n\n" +
                "💡 **`/add_hint [id] [text] [cost]`**\n↳ Attaches a purchaseable clue to a mission. Updates live Discord posts in real-time.\n\n" +
                "❌ **`/remove_hint [hint_id]`**\n↳ Deletes a clue. **Economy Logic:** Instantly refunds the cost to every single player who bought it.\n\n" +
                "🚫 **`/ban_user [member]`**\n↳ Blacklists an agent. Prevents all flag submissions and hint purchases.\n\n" +
                "✅ **`/unban_user [member]`**\n↳ Restores full network access to a previously disqualified agent.\n\n" +
                "👁️ **`/hide_user [member]`**\n↳ Hides an agent (tester/admin) from score logging, solves lists, and hint costs.\n\n" +
                "🔓 **`/unhide_user [member]`**\n↳ Unhides an agent, restoring normal scoring and logging.\n\n" +
                "☢️ **`/wipe_all`**\n↳ **NUCLEAR OPTION:** Wipes all players, scores, missions, and database storage for a fresh season.";

            embed.addFields(
                { name: "⚙️ SYSTEM & RANK SETUP", value: setup_manual, inline: false },
                { name: "🎯 MISSION CONTROL", value: mission_manual, inline: false },
                { name: "🔧 MAINTENANCE & RECOVERY", value: maint_manual, inline: false }
            );
            embed.setFooter({ text: "Admin permissions detected. Control CyberBOT with extreme caution." });
        } else {
            embed.setFooter({ text: "End of protocol list." });
        }
            
        await interaction.reply({ embeds: [embed], flags: 64 });
    }
};
