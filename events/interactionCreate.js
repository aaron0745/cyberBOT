const { Events, ModalBuilder, TextInputBuilder, TextInputStyle, ActionRowBuilder, EmbedBuilder, ButtonBuilder, ButtonStyle } = require('discord.js');
const { Models } = require('../database/mongoose');
const { updateLeaderboard, updateChallengePost } = require('../utils');

const cooldowns = new Map();

// Prune cooldowns every 10 minutes to prevent memory leaks
setInterval(() => {
    const now = Date.now();
    for (const [key, timestamp] of cooldowns.entries()) {
        if (now - timestamp > 60000) { // Anything older than 60s is stale
            cooldowns.delete(key);
        }
    }
}, 10 * 60 * 1000);

module.exports = {
    name: Events.InteractionCreate,
    async execute(interaction, client) {
        // --- SLASH COMMANDS ---
        if (interaction.isChatInputCommand()) {
            // Check banlist
            const isBanned = await Models.Banlist.findOne({ user_id: interaction.user.id });
            if (isBanned) {
                return interaction.reply({ content: '⛔ You have been banned from using this bot.', flags: 64 });
            }

            if (interaction.commandName === 'leaderboard') {
                const cdKey = `lb_${interaction.user.id}`;
                if (cooldowns.has(cdKey)) {
                    const diff = Date.now() - cooldowns.get(cdKey);
                    if (diff < 30000) {
                        return interaction.reply({ content: `⏳ Please wait ${Math.ceil((30000 - diff)/1000)}s before checking the leaderboard again.`, flags: 64 });
                    }
                }
                cooldowns.set(cdKey, Date.now());
            }

            const command = client.commands.get(interaction.commandName);
            if (!command) return;

            try {
                await command.execute(interaction);
            } catch (error) {
                console.error(`Error executing ${interaction.commandName}:`, error);
                if (interaction.replied || interaction.deferred) {
                    await interaction.followUp({ content: 'There was an error while executing this command!', flags: 64 });
                } else {
                    await interaction.reply({ content: 'There was an error while executing this command!', flags: 64 });
                }
            }
            return;
        }

        // --- BUTTON CLICKS ---
        if (interaction.isButton()) {
            const [action, challenge_id] = interaction.customId.split(':');

            if (action === 'submit') {
                // Check banlist
                const isBanned = await Models.Banlist.findOne({ user_id: interaction.user.id });
                if (isBanned) {
                    return interaction.reply({ content: '⛔ You have been banned from submitting flags.', flags: 64 });
                }

                // Create modal
                const modal = new ModalBuilder()
                    .setCustomId(`modal_submit:${challenge_id}`)
                    .setTitle(`Submit Flag for ${challenge_id}`);

                const flagInput = new TextInputBuilder()
                    .setCustomId('flagInput')
                    .setLabel("Enter the flag")
                    .setStyle(TextInputStyle.Short)
                    .setPlaceholder("SGCTF{...}")
                    .setRequired(true);

                const row = new ActionRowBuilder().addComponents(flagInput);
                modal.addComponents(row);

                await interaction.showModal(modal);
            }

            if (action === 'hints') {
                await interaction.deferReply({ flags: 64 });
                const hints = await Models.Hint.find({ challenge_id }).sort({ _id: 1 });
                if (hints.length === 0) {
                    return interaction.editReply({ content: 'No hints available for this challenge.' });
                }

                let response = `**Hints for ${challenge_id}:**\n\n`;
                const buttons = [];
                for (let i = 0; i < hints.length; i++) {
                    const hint = hints[i];
                    const isUnlocked = await Models.UnlockedHint.findOne({ user_id: interaction.user.id, hint_id: hint._id.toString() });
                    if (isUnlocked || hint.cost === 0) {
                        response += `**Hint ${i+1}:** ${hint.hint_text}\n`;
                    } else {
                        response += `**Hint ${i+1}:** 🔒 *Locked* (Cost: ${hint.cost} points)\n`;
                        buttons.push(
                            new ButtonBuilder()
                                .setCustomId(`buy_hint:${hint._id.toString()}`)
                                .setLabel(`Buy Hint ${i+1} (${hint.cost} pts)`)
                                .setStyle(ButtonStyle.Primary)
                        );
                    }
                }
                
                const components = [];
                if (buttons.length > 0) {
                    // ActionRow can hold up to 5 buttons max
                    for (let i = 0; i < buttons.length; i += 5) {
                        components.push(new ActionRowBuilder().addComponents(buttons.slice(i, i + 5)));
                    }
                }
                
                await interaction.editReply({ content: response, components });
                return;
            }

            if (action === 'buy_hint') {
                const hint_id = challenge_id; // because split(':') put the second part into challenge_id var
                await interaction.deferReply({ flags: 64 });
                const hint = await Models.Hint.findById(hint_id);
                if (!hint) return interaction.editReply({ content: '❌ Hint not found.' });

                const isUnlocked = await Models.UnlockedHint.findOne({ user_id: interaction.user.id, hint_id });
                if (isUnlocked) return interaction.editReply({ content: `✅ You already bought this hint:\n\n${hint.hint_text}` });

                const score = await Models.Score.findOne({ user_id: interaction.user.id });
                if (!score || score.points < hint.cost) {
                    return interaction.editReply({ content: `❌ Not enough points! You need ${hint.cost} but have ${score ? score.points : 0}.` });
                }

                // Deduct points
                await Models.Score.updateOne({ user_id: interaction.user.id }, { $inc: { points: -hint.cost } });
                await Models.UnlockedHint.create({ user_id: interaction.user.id, hint_id: hint_id });
                
                await updateLeaderboard(client);
                
                await interaction.editReply({ content: `🔓 **Hint Unlocked!**\n\n${hint.hint_text}` });
                return;
            }

            if (action === 'view_solves' || action === 'solve_prev' || action === 'solve_next') {
                let currentPage = 0;

                if (action !== 'view_solves') {
                    const embed = interaction.message.embeds[0];
                    if (embed && embed.footer && embed.footer.text) {
                        const match = embed.footer.text.match(/Page (\d+)/);
                        if (match) currentPage = parseInt(match[1]) - 1;
                    }
                    if (action === 'solve_prev') currentPage--;
                    if (action === 'solve_next') currentPage++;
                }

                const allSolves = await Models.Solve.find({ challenge_id }).sort({ timestamp: 1 });
                if (allSolves.length === 0) {
                    if (action === 'view_solves') return interaction.reply({ content: 'No solves yet.', flags: 64 });
                    return;
                }

                const maxPages = Math.ceil(allSolves.length / 10) || 1;
                if (currentPage < 0) currentPage = 0;
                if (currentPage >= maxPages) currentPage = maxPages - 1;

                const start = currentPage * 10;
                const pageSolves = allSolves.slice(start, start + 10);
                
                let desc = '';
                pageSolves.forEach((solve, index) => {
                    const rank = start + index + 1;
                    let icon = `**#${rank}**`;
                    if (rank === 1) icon = '🩸';
                    else if (rank === 2) icon = '🥈';
                    else if (rank === 3) icon = '🥉';
                    desc += `${icon} • <@${solve.user_id}> — <t:${solve.timestamp}:R>\n`;
                });

                const embed = new EmbedBuilder()
                    .setTitle(`📜 Solvers: ${challenge_id}`)
                    .setDescription(desc)
                    .setColor(0x00FF00)
                    .setFooter({ text: `Page ${currentPage + 1} of ${maxPages}` });

                const row = new ActionRowBuilder().addComponents(
                    new ButtonBuilder()
                        .setCustomId(`solve_prev:${challenge_id}`)
                        .setLabel('◄ Prev')
                        .setStyle(ButtonStyle.Secondary)
                        .setDisabled(currentPage === 0),
                    new ButtonBuilder()
                        .setCustomId(`solve_next:${challenge_id}`)
                        .setLabel('Next ►')
                        .setStyle(ButtonStyle.Secondary)
                        .setDisabled(currentPage >= maxPages - 1 || maxPages === 0)
                );

                if (action === 'view_solves') {
                    await interaction.reply({ embeds: [embed], components: [row], flags: 64 });
                } else {
                    await interaction.update({ embeds: [embed], components: [row] });
                }
                return;
            }
            if (action === 'lb_main_prev' || action === 'lb_main_next') {
                await interaction.deferUpdate();
                
                const { generateLeaderboardEmbed, getLeaderboardButtons } = require('../utils');
                const allScores = await Models.Score.aggregate([
                    { $lookup: { from: 'solves', localField: 'user_id', foreignField: 'user_id', as: 'user_solves' } },
                    { $addFields: { latest_solve: { $ifNull: [{ $max: "$user_solves.timestamp" }, 9999999999999] } } },
                    { $sort: { points: -1, latest_solve: 1 } }
                ]);

                const embed = interaction.message.embeds[0];
                let currentPage = 0;
                if (embed && embed.footer && embed.footer.text) {
                    const match = embed.footer.text.match(/Page (\d+)/);
                    if (match) {
                        currentPage = parseInt(match[1]) - 1;
                    }
                }

                if (action === 'lb_main_prev') currentPage--;
                else if (action === 'lb_main_next') currentPage++;

                const maxPages = Math.ceil(allScores.length / 10) || 1;
                if (currentPage < 0) currentPage = 0;
                if (currentPage >= maxPages) currentPage = maxPages - 1;

                const newEmbed = generateLeaderboardEmbed(allScores, currentPage);
                const newButtons = getLeaderboardButtons(currentPage, maxPages);

                await interaction.editReply({ embeds: [newEmbed], components: [newButtons] });
                return;
            }
            
            return;
        }

        // --- MODAL SUBMISSIONS ---
        if (interaction.isModalSubmit()) {
            const [action, challenge_id] = interaction.customId.split(':');

            if (action === 'modal_submit') {
                // Submit Cooldown Check
                const cdKey = `sub_${interaction.user.id}`;
                if (cooldowns.has(cdKey)) {
                    if (Date.now() - cooldowns.get(cdKey) < 2000) {
                        return interaction.reply({ content: '⏳ You are submitting flags too quickly. Please wait.', flags: 64 });
                    }
                }
                cooldowns.set(cdKey, Date.now());

                await interaction.deferReply({ flags: 64 });
                const submittedFlag = interaction.fields.getTextInputValue('flagInput').trim();

                const challenge = await Models.Flag.findOne({ challenge_id });
                if (!challenge) {
                    return interaction.editReply({ content: '❌ Challenge no longer exists.' });
                }

                const current_time = Math.floor(Date.now() / 1000);
                if (challenge.end_time && current_time > challenge.end_time) {
                    return interaction.editReply({ content: '⏳ This challenge has expired and is no longer accepting submissions.' });
                }

                // Check Logging Channels
                const logChanConf = await Models.Config.findOne({ key: 'channel_challenge_logs' });
                const wrongChanConf = await Models.Config.findOne({ key: 'channel_wrong_submissions' });
                let logChan = null;
                let wrongChan = null;
                try {
                    if (logChanConf) logChan = await client.channels.fetch(logChanConf.value);
                    if (wrongChanConf) wrongChan = await client.channels.fetch(wrongChanConf.value);
                } catch (e) {
                    console.error('Error fetching log channels:', e);
                }

                if (submittedFlag === challenge.flag_text) {
                    // Check if already solved
                    const alreadySolved = await Models.Solve.findOne({ user_id: interaction.user.id, challenge_id });
                    if (alreadySolved) {
                        return interaction.editReply({ content: '⚠️ You have already solved this challenge!' });
                    }

                    // Collusion check (someone else solved it in the last 60s)
                    const lastSolve = await Models.Solve.findOne({ challenge_id }).sort({ timestamp: -1 });
                    if (lastSolve && (current_time - lastSolve.timestamp <= 60) && lastSolve.user_id !== interaction.user.id) {
                        if (logChan) {
                            logChan.send(`🚨 **POSSIBLE COLLUSION ALERT!**\n<@${interaction.user.id}> and <@${lastSolve.user_id}> both solved **${challenge_id}** within 60 seconds of each other!`);
                        }
                    }

                    // Check rank for bonuses
                    const previousSolves = await Models.Solve.countDocuments({ challenge_id });
                    
                    let bonus = 0;
                    if (previousSolves === 0) bonus = 50;
                    else if (previousSolves === 1) bonus = 25;
                    else if (previousSolves === 2) bonus = 10;

                    // Record solve
                    const totalAward = challenge.points + bonus;

                    await Models.Solve.create({
                        user_id: interaction.user.id,
                        challenge_id: challenge_id,
                        timestamp: current_time,
                        points_awarded: totalAward
                    });

                    // Update score
                    await Models.Score.updateOne(
                        { user_id: interaction.user.id },
                        { 
                            $set: { username: interaction.user.username },
                            $inc: { points: totalAward } 
                        },
                        { upsert: true }
                    );

                    const updatedScore = await Models.Score.findOne({ user_id: interaction.user.id });
                    
                    // Check RoleRewards
                    try {
                        const roles = await Models.RoleReward.find({});
                        for (const roleConf of roles) {
                            if (updatedScore.points >= roleConf.points) {
                                const roleId = roleConf.role_id;
                                if (interaction.member && !interaction.member.roles.cache.has(roleId)) {
                                    await interaction.member.roles.add(roleId).catch(()=>null);
                                }
                            }
                        }
                    } catch (e) {
                        console.error('Error assigning role rewards:', e);
                    }

                    let msg = `🎉 **CORRECT!** You have been awarded ${challenge.points} points!`;
                    if (bonus > 0) {
                        msg += `\n🔥 **Bonus:** +${bonus} points for being solver #${previousSolves + 1}!`;
                    }
                    
                    if (logChan) {
                        logChan.send(`✅ <@${interaction.user.id}> successfully solved **${challenge_id}** for ${totalAward} points!`);
                    }

                    await updateLeaderboard(client);
                    await updateChallengePost(client, challenge_id);

                    await interaction.editReply({ content: msg });
                } else {
                    if (wrongChan) {
                        wrongChan.send(`❌ <@${interaction.user.id}> failed **${challenge_id}** with guess: \`${submittedFlag}\``);
                    }
                    await interaction.editReply({ content: '❌ Incorrect flag. Try again!' });
                }
            }
        }
    }
};
