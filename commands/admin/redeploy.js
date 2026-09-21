const { SlashCommandBuilder, PermissionFlagsBits, EmbedBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle } = require('discord.js');
const { Models } = require('../../database/mongoose');
const https = require('https');

function fetchJson(url, options = {}) {
    return new Promise((resolve, reject) => {
        const parsedUrl = new URL(url);
        const reqOptions = {
            hostname: parsedUrl.hostname,
            path: parsedUrl.pathname + parsedUrl.search,
            method: options.method || 'GET',
            headers: {
                'User-Agent': 'CyberBOT-Deploy-Checker',
                'Accept': 'application/vnd.github.v3+json',
                ...(options.headers || {})
            }
        };

        const req = https.request(reqOptions, (res) => {
            let data = '';
            res.on('data', chunk => { data += chunk; });
            res.on('end', () => {
                if (res.statusCode >= 200 && res.statusCode < 300) {
                    try {
                        resolve(JSON.parse(data));
                    } catch (e) {
                        resolve(data);
                    }
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
                const { execSync } = require('child_process');
                currentCommit = execSync('git rev-parse HEAD').toString().trim();
                branch = execSync('git rev-parse --abbrev-ref HEAD').toString().trim();
            } catch (e) {}
        }

        // Check latest commit on GitHub
        let latestSha = null;
        let latestMessage = '';
        try {
            const githubData = await fetchJson(`https://api.github.com/repos/${repoSlug}/commits/${branch}`);
            if (githubData && githubData.sha) {
                latestSha = githubData.sha;
                latestMessage = githubData.commit?.message ? githubData.commit.message.split('\n')[0] : '';
            }
        } catch (apiErr) {
            console.warn('Could not query GitHub commit API:', apiErr.message);
        }

        // Check if there are no new commits
        const isSameCommit = currentCommit && latestSha && (currentCommit.toLowerCase() === latestSha.toLowerCase());

        if (isSameCommit) {
            const shortSha = currentCommit.substring(0, 7);
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
                content: `⚠️ **No new commits found on GitHub** (already running latest: [\`${shortSha}\`](https://github.com/${repoSlug}/commit/${currentCommit}) — *"${latestMessage}"*).\n\nDo you want to restart the service instead?`,
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

        // New commit exists (or could not verify) -> Trigger Render Deploy Hook
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
                                { name: '📦 New Commit', value: latestSha ? `[\`${latestSha.substring(0, 7)}\`](https://github.com/${repoSlug}/commit/${latestSha})` : '`Latest HEAD`', inline: true },
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
                    (latestSha ? `• **New Commit:** [\`${latestSha.substring(0, 7)}\`](https://github.com/${repoSlug}/commit/${latestSha})\n` : '') +
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
