const { SlashCommandBuilder, PermissionFlagsBits, EmbedBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle } = require('discord.js');
const { Models } = require('../../database/mongoose');
const https = require('https');
const { execSync } = require('child_process');

function fetchText(url) {
    return new Promise((resolve, reject) => {
        const parsedUrl = new URL(url);
        const reqOptions = {
            hostname: parsedUrl.hostname,
            path: parsedUrl.pathname + parsedUrl.search,
            method: 'GET',
            headers: {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) CyberBOT/1.0',
                'Accept': 'text/html,application/xhtml+xml,application/xml,application/atom+xml;q=0.9,*/*;q=0.8'
            }
        };

        const req = https.request(reqOptions, (res) => {
            if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
                return fetchText(res.headers.location).then(resolve).catch(reject);
            }
            let data = '';
            res.on('data', chunk => { data += chunk; });
            res.on('end', () => {
                if (res.statusCode >= 200 && res.statusCode < 300) {
                    resolve(data);
                } else {
                    reject(new Error(`HTTP ${res.statusCode}: ${data}`));
                }
            });
        });

        req.on('error', reject);
        req.setTimeout(8000, () => {
            req.destroy();
            reject(new Error('Request timed out'));
        });
        req.end();
    });
}

function triggerDeployHook(url) {
    return new Promise((resolve, reject) => {
        const parsedUrl = new URL(url);
        const reqOptions = {
            hostname: parsedUrl.hostname,
            path: parsedUrl.pathname + parsedUrl.search,
            method: 'POST',
            headers: {
                'User-Agent': 'CyberBOT-Deployer'
            }
        };

        const req = https.request(reqOptions, (res) => {
            let data = '';
            res.on('data', chunk => { data += chunk; });
            res.on('end', () => {
                if (res.statusCode >= 200 && res.statusCode < 300) {
                    resolve(data);
                } else {
                    reject(new Error(`Deploy Hook HTTP ${res.statusCode}: ${data}`));
                }
            });
        });

        req.on('error', reject);
        req.setTimeout(10000, () => {
            req.destroy();
            reject(new Error('Deploy Hook request timed out'));
        });
        req.end();
    });
}

async function getLatestGitHubCommit(repoSlug, branch) {
    // 1. Try Git ls-remote (fast, zero rate limits, protocol-level)
    try {
        const stdout = execSync(`git ls-remote https://github.com/${repoSlug}.git refs/heads/${branch}`, { timeout: 6000 }).toString();
        const parts = stdout.trim().split(/\s+/);
        if (parts[0] && parts[0].length >= 7) {
            // Also try to get commit message from git log if local repo matches
            let msg = '';
            try {
                msg = execSync(`git log -1 --format="%s" ${parts[0]}`, { timeout: 2000 }).toString().trim();
            } catch (e) {}
            return { sha: parts[0], message: msg };
        }
    } catch (e) {}

    // 2. Try GitHub Atom feed (public web endpoint, bypasses REST API rate limit)
    try {
        const atomXml = await fetchText(`https://github.com/${repoSlug}/commits/${branch}.atom`);
        const match = atomXml.match(/<id>tag:github\.com,2008:Grit::Commit\/([a-f0-9]{40})<\/id>[\s\S]*?<title>\s*([\s\S]*?)\s*<\/title>/);
        if (match) {
            const cleanTitle = match[2]
                .replace(/&lt;/g, '<')
                .replace(/&gt;/g, '>')
                .replace(/&amp;/g, '&')
                .replace(/&quot;/g, '"')
                .trim();
            return { sha: match[1], message: cleanTitle };
        }
    } catch (e) {}

    return null;
}

module.exports = {
    data: new SlashCommandBuilder()
        .setName('redeploy')
        .setDescription('Trigger a full rebuild on Render (checks for new commits on GitHub first)')
        .setDefaultMemberPermissions(PermissionFlagsBits.Administrator),
    async execute(interaction) {
        await interaction.deferReply({ flags: 64 });

        const deployHook = process.env.RENDER_DEPLOY_HOOK;
        if (!deployHook) {
            return await interaction.editReply({
                content: '❌ **RENDER_DEPLOY_HOOK is not configured.**\nPlease add your Render Deploy Hook URL to your environment variables on Render as `RENDER_DEPLOY_HOOK`.'
            });
        }

        // Determine currently running commit
        let currentCommit = process.env.RENDER_GIT_COMMIT || '';
        let repoSlug = process.env.RENDER_GIT_REPO_SLUG || 'aaron0745/cyberBOT';
        let branch = process.env.RENDER_GIT_BRANCH || 'main';

        if (!currentCommit) {
            try {
                currentCommit = execSync('git rev-parse HEAD').toString().trim();
                branch = execSync('git rev-parse --abbrev-ref HEAD').toString().trim();
            } catch (e) {}
        }

        // Check latest commit on GitHub (using git ls-remote and atom feed without API rate limits)
        const latest = await getLatestGitHubCommit(repoSlug, branch);

        // Case A: Could not check GitHub -> Prompt the user instead of automatically deploying
        if (!latest || !latest.sha) {
            const row = new ActionRowBuilder().addComponents(
                new ButtonBuilder()
                    .setCustomId('redeploy_force')
                    .setLabel('Force Redeploy Anyway')
                    .setStyle(ButtonStyle.Primary)
                    .setEmoji('🚀'),
                new ButtonBuilder()
                    .setCustomId('redeploy_restart_yes')
                    .setLabel('Restart Service')
                    .setStyle(ButtonStyle.Success)
                    .setEmoji('🔄'),
                new ButtonBuilder()
                    .setCustomId('redeploy_restart_cancel')
                    .setLabel('Cancel')
                    .setStyle(ButtonStyle.Secondary)
                    .setEmoji('❌')
            );

            const promptMsg = await interaction.editReply({
                content: '⚠️ **Could not connect to GitHub to check for new commits.**\nWhat would you like to do?',
                components: [row]
            });

            try {
                const confirmation = await promptMsg.awaitMessageComponent({
                    filter: i => i.user.id === interaction.user.id,
                    time: 30000
                });

                if (confirmation.customId === 'redeploy_force') {
                    await confirmation.update({ content: '🚀 Triggering redeployment on Render...', components: [] });
                    await triggerDeployHook(deployHook);
                    return;
                } else if (confirmation.customId === 'redeploy_restart_yes') {
                    await confirmation.update({ content: '🔄 Restarting CyberBOT...', components: [] });
                    setTimeout(() => process.exit(0), 1000);
                    return;
                } else {
                    return await confirmation.update({ content: '❌ Action cancelled.', components: [] });
                }
            } catch (e) {
                return await interaction.editReply({ content: '⏱️ Prompt timed out. No action taken.', components: [] }).catch(() => null);
            }
        }

        const latestSha = latest.sha;
        const latestMessage = latest.message;

        // Check if there are no new commits
        const isSameCommit = currentCommit && (
            currentCommit.toLowerCase() === latestSha.toLowerCase() ||
            latestSha.toLowerCase().startsWith(currentCommit.toLowerCase()) ||
            currentCommit.toLowerCase().startsWith(latestSha.toLowerCase())
        );

        // Case B: No new commits -> Ask to restart or cancel
        if (isSameCommit) {
            const shortSha = currentCommit ? currentCommit.substring(0, 7) : latestSha.substring(0, 7);
            const row = new ActionRowBuilder().addComponents(
                new ButtonBuilder()
                    .setCustomId('redeploy_restart_yes')
                    .setLabel('Yes, Restart Service')
                    .setStyle(ButtonStyle.Success)
                    .setEmoji('🔄'),
                new ButtonBuilder()
                    .setCustomId('redeploy_restart_cancel')
                    .setLabel('Cancel')
                    .setStyle(ButtonStyle.Secondary)
                    .setEmoji('❌')
            );

            const promptMsg = await interaction.editReply({
                content: `⚠️ **No new commits found on GitHub** (already running latest: [\`${shortSha}\`](https://github.com/${repoSlug}/commit/${latestSha})${latestMessage ? ` — *"${latestMessage}"*` : ''}).\n\nDo you want to restart the service instead?`,
                components: [row]
            });

            try {
                const confirmation = await promptMsg.awaitMessageComponent({
                    filter: i => i.user.id === interaction.user.id,
                    time: 30000
                });

                if (confirmation.customId === 'redeploy_restart_yes') {
                    // Log to Admin Logs Channel if configured
                    try {
                        const adminLogConfig = await Models.Config.findOne({ key: 'channel_admin_logs' });
                        if (adminLogConfig && adminLogConfig.value) {
                            const logChannel = await interaction.client.channels.fetch(adminLogConfig.value).catch(() => null);
                            if (logChannel) {
                                const logEmbed = new EmbedBuilder()
                                    .setTitle('🔄 Restart Triggered')
                                    .setDescription(`Admin <@${interaction.user.id}> initiated a service restart via \`/redeploy\` prompt (no new commits).`)
                                    .setColor(0xFFA500)
                                    .setTimestamp();
                                await logChannel.send({ embeds: [logEmbed] });
                            }
                        }
                    } catch (e) {}

                    await confirmation.update({
                        content: '🔄 **Restarting CyberBOT...**\nProcess is shutting down. Render container supervisor will reboot the service in ~5–10 seconds.',
                        components: []
                    });

                    setTimeout(() => {
                        process.exit(0);
                    }, 1000);
                } else {
                    await confirmation.update({
                        content: '❌ Action cancelled. CyberBOT remains online without restarting.',
                        components: []
                    });
                }
            } catch (timeoutErr) {
                await interaction.editReply({
                    content: '⏱️ Prompt timed out. No action taken.',
                    components: []
                }).catch(() => null);
            }
            return;
        }

        // Case C: New commit exists -> Trigger Render Deploy Hook
        try {
            await triggerDeployHook(deployHook);

            // Log to Admin Logs Channel
            try {
                const adminLogConfig = await Models.Config.findOne({ key: 'channel_admin_logs' });
                if (adminLogConfig && adminLogConfig.value) {
                    const logChannel = await interaction.client.channels.fetch(adminLogConfig.value).catch(() => null);
                    if (logChannel) {
                        const logEmbed = new EmbedBuilder()
                            .setTitle('🚀 Redeployment Triggered')
                            .setDescription(`Admin <@${interaction.user.id}> triggered a rebuild & redeploy via \`/redeploy\`.`)
                            .addFields(
                                { name: '📦 New Commit', value: `[\`${latestSha.substring(0, 7)}\`](https://github.com/${repoSlug}/commit/${latestSha})`, inline: true },
                                { name: '💬 Message', value: latestMessage ? `\`${latestMessage}\`` : '`N/A`', inline: false }
                            )
                            .setColor(0x00FF78)
                            .setTimestamp();
                        await logChannel.send({ embeds: [logEmbed] });
                    }
                }
            } catch (e) {
                console.error('Error logging redeploy:', e);
            }

            const embed = new EmbedBuilder()
                .setTitle('🚀 Redeployment Initiated')
                .setDescription(
                    `Render has received the build trigger!\n\n` +
                    `• **New Commit:** [\`${latestSha.substring(0, 7)}\`](https://github.com/${repoSlug}/commit/${latestSha})\n` +
                    (latestMessage ? `• **Message:** *"${latestMessage}"*\n` : '') +
                    `\n⏱️ **Estimated build time:** 1–3 minutes\n` +
                    `🟢 CyberBOT will post an alert in the admin logs channel as soon as it boots the new deployment.`
                )
                .setColor(0x00FF78);

            await interaction.editReply({ embeds: [embed] });
        } catch (error) {
            console.error('Error triggering redeployment:', error);
            await interaction.editReply({ content: `❌ Failed to trigger redeployment: \`${error.message}\`` });
        }
    }
};
