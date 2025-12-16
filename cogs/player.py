import discord
from discord import app_commands
from discord.ext import commands, tasks
import sqlite3
import time

# --- CONFIGURATION ---
LEADERBOARD_CHANNEL_ID = 1449791275720245460 
LOG_CHANNEL_ID = 1450450923255103548 # <--- PASTE YOUR ADMIN LOG CHANNEL ID HERE

BONUSES = {0: 50, 1: 25, 2: 10}
COOLDOWNS = {} 

# --- HINT SELECT MENU ---
class HintSelect(discord.ui.Select):
    def __init__(self, hints, bot, user_id):
        self.bot = bot
        self.user_id = user_id
        options = []
        for h_id, text, cost in hints:
            options.append(discord.SelectOption(label=f"Hint #{h_id} ({cost} pts)", value=f"{h_id}", description="Click to buy/view"))
        
        super().__init__(placeholder="💡 Select a hint to buy...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        hint_id = int(self.values[0])
        
        conn = sqlite3.connect('ctf_data.db')
        c = conn.cursor()
        
        # 1. Check if already bought
        c.execute("SELECT * FROM unlocked_hints WHERE user_id = ? AND hint_id = ?", (self.user_id, hint_id))
        if c.fetchone():
            c.execute("SELECT hint_text FROM hints WHERE id = ?", (hint_id,))
            text = c.fetchone()[0]
            conn.close()
            await interaction.response.send_message(f"🔓 **Already Unlocked:**\n||{text}||", ephemeral=True)
            return

        # 2. Check points
        c.execute("SELECT points FROM scores WHERE user_id = ?", (self.user_id,))
        res = c.fetchone()
        current_points = res[0] if res else 0
        
        c.execute("SELECT cost, hint_text, challenge_id FROM hints WHERE id = ?", (hint_id,))
        cost, text, challenge_id = c.fetchone()
        
        if current_points < cost:
            conn.close()
            await interaction.response.send_message(f"🚫 **Insufficient Funds!** You have {current_points} pts, but need {cost}.", ephemeral=True)
            return

        # 3. Process Transaction
        c.execute("UPDATE scores SET points = points - ? WHERE user_id = ?", (cost, self.user_id))
        c.execute("INSERT INTO unlocked_hints (user_id, hint_id) VALUES (?, ?)", (self.user_id, hint_id))
        conn.commit()
        conn.close()
        
        # 4. Show Hint
        await interaction.response.send_message(f"💸 **Purchased!** (-{cost} pts)\n\n💡 **HINT:**\n||{text}||", ephemeral=True)
        
        # 5. Log it
        cog = self.bot.get_cog('Player')
        if cog:
            await cog.update_leaderboard()
            await cog.send_log("💡 Hint Purchased", f"Bought Hint #{hint_id} for **{challenge_id}**\nCost: {cost}", discord.Color.gold(), interaction.user, challenge_id)

class HintView(discord.ui.View):
    def __init__(self, hints, bot, user_id):
        super().__init__()
        self.add_item(HintSelect(hints, bot, user_id))

# --- SUBMISSION MODAL ---
class SubmissionModal(discord.ui.Modal):
    def __init__(self, challenge_id, bot):
        super().__init__(title=f'Submit: {challenge_id}')
        self.challenge_id = challenge_id
        self.bot = bot

    flag_input = discord.ui.TextInput(
        label='Flag', placeholder='SGCTF{...}', style=discord.TextStyle.short, required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        user_flag = self.flag_input.value.strip()
        current_time = time.time()
        
        conn = sqlite3.connect('ctf_data.db')
        c = conn.cursor()
        
        # BAN CHECK
        c.execute("SELECT * FROM banlist WHERE user_id = ?", (user_id,))
        if c.fetchone():
            conn.close()
            await interaction.response.send_message("🚫 **ACCESS DENIED.** You have been disqualified.", ephemeral=True)
            return

        # COOLDOWN CHECK
        last_try = COOLDOWNS.get(user_id, 0)
        if current_time - last_try < 5: 
            remaining = int(5 - (current_time - last_try))
            await interaction.response.send_message(f"⏳ **Cooldown!** Wait {remaining}s.", ephemeral=True)
            cog = self.bot.get_cog('Player')
            if cog: await cog.send_log("⚠️ Spam Detected", f"Input: ||{user_flag}||", discord.Color.orange(), interaction.user, self.challenge_id)
            conn.close()
            return
        COOLDOWNS[user_id] = current_time

        # GET DATA
        c.execute("SELECT points, flag_text FROM flags WHERE challenge_id = ?", (self.challenge_id,))
        data = c.fetchone()
        if not data:
            await interaction.response.send_message("❌ Error: Challenge data missing.", ephemeral=True)
            conn.close()
            return
        base_points, real_flag = data

        # VERIFY FLAG
        if user_flag != real_flag:
            await interaction.response.send_message("❌ **Incorrect Flag.**", ephemeral=True)
            cog = self.bot.get_cog('Player')
            if cog: await cog.send_log("❌ Failed Attempt", f"Input: `{user_flag}`", discord.Color.red(), interaction.user, self.challenge_id)
            conn.close()
            return

        # DUPLICATE CHECK
        c.execute("SELECT * FROM solves WHERE user_id = ? AND challenge_id = ?", (user_id, self.challenge_id))
        if c.fetchone():
            await interaction.response.send_message("⚠️ **You already solved this!**", ephemeral=True)
            conn.close()
            return

        # ANTI-CHEAT (Sherlock)
        time_window = 60 
        check_time = current_time - time_window
        c.execute("SELECT user_id, timestamp FROM solves WHERE challenge_id = ? AND timestamp > ? AND user_id != ?", (self.challenge_id, check_time, user_id))
        recent_solves = c.fetchall()
        
        if recent_solves:
            cog = self.bot.get_cog('Player')
            if cog:
                suspects = []
                for sus_uid, sus_time in recent_solves:
                    diff = int(current_time - sus_time)
                    suspect_user = interaction.guild.get_member(sus_uid)
                    name = suspect_user.name if suspect_user else f"ID:{sus_uid}"
                    suspects.append(f"• **{name}** (Solved {diff}s ago)")
                await cog.send_log("🕵️ SUSPECTED FLAG SHARING", f"**Player:** {interaction.user.mention}\n**Challenge:** {self.challenge_id}\n⚠️ **Close solves:**\n" + "\n".join(suspects), discord.Color.dark_magenta(), interaction.user, self.challenge_id)

        # SUCCESS
        c.execute("SELECT COUNT(*) FROM solves WHERE challenge_id = ?", (self.challenge_id,))
        solve_count = c.fetchone()[0]
        bonus = BONUSES.get(solve_count, 0)
        total_points = base_points + bonus
        
        c.execute("INSERT INTO solves (user_id, challenge_id, timestamp) VALUES (?, ?, ?)", (user_id, self.challenge_id, current_time))
        c.execute("INSERT OR IGNORE INTO scores (user_id, username, points) VALUES (?, ?, 0)", (user_id, interaction.user.name))
        c.execute("UPDATE scores SET points = points + ? WHERE user_id = ?", (total_points, user_id))
        conn.commit()
        conn.close()

        msg = f"🎉 **Correct!** +{total_points} pts"
        if bonus > 0: msg += f" (First Blood: +{bonus}!)"
        await interaction.response.send_message(msg, ephemeral=True)
        
        cog = self.bot.get_cog('Player')
        if cog:
            await cog.update_leaderboard()
            await cog.update_challenge_card(self.challenge_id)
            await cog.send_log("✅ Flag Captured", f"**Points:** {total_points}", discord.Color.green(), interaction.user, self.challenge_id)

# --- PLAYER COG ---
class Player(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.leaderboard_loop.start()

    def cog_unload(self):
        self.leaderboard_loop.cancel()

    async def send_log(self, title, description, color, user, challenge_id):
        channel = self.bot.get_channel(LOG_CHANNEL_ID)
        if not channel: return
        embed = discord.Embed(title=title, description=description, color=color, timestamp=discord.utils.utcnow())
        embed.set_author(name=f"{user.name} ({user.id})", icon_url=user.avatar.url if user.avatar else None)
        embed.set_footer(text=f"Challenge: {challenge_id}")
        try: await channel.send(embed=embed)
        except: pass

    # --- LISTENER FOR BUTTONS ---
    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type == discord.InteractionType.component:
            custom_id = interaction.data.get("custom_id", "")
            
            # SUBMIT FLAG BUTTON
            if custom_id.startswith("submit:"):
                challenge_id = custom_id.split(":")[1]
                await interaction.response.send_modal(SubmissionModal(challenge_id, self.bot))
            
            # HINT BUTTON
            elif custom_id.startswith("hints:"):
                challenge_id = custom_id.split(":")[1]
                conn = sqlite3.connect('ctf_data.db')
                c = conn.cursor()
                c.execute("SELECT id, hint_text, cost FROM hints WHERE challenge_id = ?", (challenge_id,))
                hints = c.fetchall()
                conn.close()
                
                if not hints:
                    await interaction.response.send_message("🤷♂️ **No hints available** for this challenge.", ephemeral=True)
                else:
                    await interaction.response.send_message(view=HintView(hints, self.bot, interaction.user.id), ephemeral=True)

    # --- HELP COMMAND (UPDATED) ---
    @app_commands.command(name="help", description="Show mission instructions and commands")
    async def help(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        player_desc = (
            "**`/profile`**\n"
            "View Rank, Score, and Solves.\n\n"
            "**How to Play:**\n"
            "1. Go to a challenge channel.\n"
            "2. Click **Submit Flag** to guess.\n"
            "3. Click **Hints** to buy clues (costs points!).\n"
            "4. Top agents are tracked on the Leaderboard."
        )

        embed = discord.Embed(title="📚 Agent Field Manual", description="Operate the CTF system.", color=discord.Color.teal())
        embed.add_field(name="🕵️ Agent Protocols", value=player_desc, inline=False)

        if interaction.user.guild_permissions.administrator:
            admin_desc = (
                "**`Lifecycle`**\n"
                "`/create` - Add challenge.\n"
                "`/add_hint` - Add clues to buy.\n"
                "`/post` - Publish challenge (with buttons).\n"
                "`/edit` - Fix details.\n"
                "`/delete` - Remove challenge.\n\n"
                "**`Management`**\n"
                "`/list` - See status.\n"
                "`/show` - Reveal flag/info.\n\n"
                "**`Judge`**\n"
                "`/revoke` - Remove solve.\n"
                "`/ban_user` - Disqualify player.\n\n"
                "**`System`**\n"
                "`/export` - Download Database Backup.\n"
                "`/import` - Upload Database Backup."
            )
            embed.add_field(name="🛡️ Admin Control Panel", value=admin_desc, inline=False)

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="profile", description="View agent stats")
    async def profile(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        conn = sqlite3.connect('ctf_data.db')
        c = conn.cursor()
        c.execute("SELECT user_id, points FROM scores ORDER BY points DESC")
        all_players = c.fetchall()
        
        rank = "Unranked"
        points = 0
        for i, (uid, pts) in enumerate(all_players, 1):
            if uid == target.id:
                rank = f"#{i}"
                points = pts
                break
        
        c.execute("SELECT COUNT(*) FROM solves WHERE user_id = ?", (target.id,))
        solve_count = c.fetchone()[0]
        conn.close()

        embed = discord.Embed(title=f"📁 AGENT DOSSIER: {target.display_name}", color=target.color)
        embed.set_thumbnail(url=target.avatar.url if target.avatar else None)
        embed.add_field(name="🏆 Rank", value=f"**{rank}**", inline=True)
        embed.add_field(name="💰 Score", value=f"**{points}**", inline=True)
        embed.add_field(name="🚩 Flags Captured", value=f"**{solve_count}**", inline=True)
        await interaction.response.send_message(embed=embed)

    @tasks.loop(minutes=1)
    async def leaderboard_loop(self):
        await self.update_leaderboard()

    @leaderboard_loop.before_loop
    async def before_lb_loop(self):
        await self.bot.wait_until_ready()

    async def update_leaderboard(self):
        channel = self.bot.get_channel(LEADERBOARD_CHANNEL_ID)
        if not channel: return

        conn = sqlite3.connect('ctf_data.db')
        c = conn.cursor()
        c.execute("SELECT username, points FROM scores ORDER BY points DESC LIMIT 15")
        top_players = c.fetchall()
        c.execute("SELECT value FROM config WHERE key = 'lb_msg_id'")
        row = c.fetchone()
        conn.close()

        embed = discord.Embed(title="🏆 MASTER AGENT STANDINGS", color=0xFFD700)
        desc = ""
        for i, (user, points) in enumerate(top_players, 1):
            icon = "👑" if i==1 else "🥈" if i==2 else "🥉" if i==3 else f"**#{i}**"
            desc += f"{icon} • **{user}** — `{points} pts`\n"
        embed.description = desc if desc else "Waiting for data..."
        embed.set_footer(text="Updates live • Global Rankings")
        
        if row:
            try:
                msg = await channel.fetch_message(row[0])
                await msg.edit(embed=embed)
                return
            except: pass

        msg = await channel.send(embed=embed)
        conn = sqlite3.connect('ctf_data.db')
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('lb_msg_id', ?)", (msg.id,))
        conn.commit()
        conn.close()

    async def update_challenge_card(self, challenge_id):
        conn = sqlite3.connect('ctf_data.db')
        c = conn.cursor()
        c.execute("SELECT msg_id, channel_id, points FROM flags WHERE challenge_id = ?", (challenge_id,))
        data = c.fetchone()
        if not data: conn.close(); return
        mid, cid, base_pts = data
        c.execute("SELECT user_id FROM solves WHERE challenge_id = ? ORDER BY timestamp ASC", (challenge_id,))
        solves = c.fetchall()
        conn.close()

        try:
            channel = self.bot.get_channel(cid)
            if not channel: return
            msg = await channel.fetch_message(mid)
            embed = msg.embeds[0]

            saved_fields = []
            for f in embed.fields:
                if "Bounty" in f.name or "Category" in f.name:
                    saved_fields.append(f)
            embed.clear_fields()
            for f in saved_fields:
                embed.add_field(name=f.name, value=f.value, inline=f.inline)

            fb_value = "*Waiting...*"
            if len(solves) > 0:
                first_uid = solves[0][0]
                u = channel.guild.get_member(first_uid)
                name = u.display_name if u else "Agent"
                fb_value = f"🥇 **{name}** (+{base_pts + BONUSES.get(0, 0)})"
            embed.add_field(name="🩸 First Blood", value=fb_value, inline=False)

            if len(solves) > 1:
                others = solves[1:]
                current_chunk = ""
                page_number = 1
                for i, (uid,) in enumerate(others):
                    real_index = i + 1
                    if i > 0 and i % 10 == 0:
                        title = "📜 Solvers" if page_number == 1 else f"📜 Solvers (Page {page_number})"
                        embed.add_field(name=title, value=current_chunk, inline=False)
                        current_chunk = ""
                        page_number += 1
                    u = channel.guild.get_member(uid)
                    name = u.display_name if u else "Agent"
                    bonus = BONUSES.get(real_index, 0)
                    icon = "🥈" if real_index==1 else "🥉" if real_index==2 else "✅"
                    current_chunk += f"{icon} **{name}** (+{base_pts+bonus})\n"

                if current_chunk:
                    title = "📜 Solvers" if page_number == 1 else f"📜 Solvers (Page {page_number})"
                    embed.add_field(name=title, value=current_chunk, inline=False)

            await msg.edit(embed=embed)
        except: pass

async def setup(bot):
    await bot.add_cog(Player(bot))
