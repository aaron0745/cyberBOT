const { SlashCommandBuilder, AttachmentBuilder } = require('discord.js');
const { Models } = require('../../database/mongoose');
const { renderProfileCard } = require('./profileCard');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('profile')
        .setDescription('View agent ID card')
        .addUserOption(option =>
            option.setName('agent')
                .setDescription('The agent to view (leave blank for yourself)')
                .setRequired(false)
        ),
    async execute(interaction) {
        await interaction.deferReply();
        const targetUser = interaction.options.getUser('agent') || interaction.user;

        try {
            // --- Easter Egg: Bot Profile ---
            let data = {};
            if (targetUser.id === interaction.client.user.id) {
                data = {
                    user_id: targetUser.id,
                    display_name: targetUser.displayName,
                    rank: 'OVERSEER',
                    points: 999999,
                    solves: 'KERNEL',
                    avatar_url: targetUser.displayAvatarURL({ extension: 'png', size: 512 }),
                    next_goal: null,
                    last_cats: ["SYS", "SQL", "ENC"],
                    earned_role: "SYSTEM OVERSEER"
                };
            } else {
                // Fetch actual player stats
                const scoreDoc = await Models.Score.findOne({ user_id: targetUser.id });
                const points = scoreDoc ? scoreDoc.points : 0;

                // Rank calculation
                let rankNum = 0;
                if (points > 0) {
                    const higherScores = await Models.Score.countDocuments({ points: { $gt: points } });
                    rankNum = higherScores + 1;
                }
                const rank = rankNum > 0 ? `#${rankNum}` : 'N/A';

                const solves = await Models.Solve.countDocuments({ user_id: targetUser.id });

                // Fetch next goal
                const nextReward = await Models.RoleReward.findOne({ points: { $gt: points } }).sort({ points: 1 });
                const next_goal = nextReward ? nextReward.points : null;

                // Fetch earned role
                const earnedReward = await Models.RoleReward.findOne({ points: { $lte: points } }).sort({ points: -1 });
                let earned_role = "RECRUIT";
                if (earnedReward && interaction.guild) {
                    const d_role = interaction.guild.roles.cache.get(earnedReward.role_id);
                    if (d_role) earned_role = d_role.name.toUpperCase();
                }

                // Fetch last 3 solved categories
                const lastSolves = await Models.Solve.find({ user_id: targetUser.id }).sort({ timestamp: -1 }).limit(3);
                const last_cats = [];
                for (const solve of lastSolves) {
                    const flag = await Models.Flag.findOne({ challenge_id: solve.challenge_id });
                    if (flag) last_cats.push(flag.category);
                }

                data = {
                    user_id: targetUser.id,
                    display_name: targetUser.displayName,
                    rank,
                    points,
                    solves,
                    avatar_url: targetUser.displayAvatarURL({ extension: 'png', size: 512 }),
                    next_goal,
                    last_cats,
                    earned_role
                };
            }

            // Render the card in-process (no Python needed)
            const buffer = await renderProfileCard(data);
            const attachment = new AttachmentBuilder(buffer, { name: 'profile.png' });
            await interaction.editReply({ files: [attachment] });

        } catch (error) {
            console.error(error);
            try { await interaction.editReply({ content: '❌ An error occurred while generating the profile.' }); } catch (e) {}
        }
    },
};
