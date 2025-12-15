import discord
from discord import app_commands
from discord.ext import commands, tasks
import sqlite3
import time

# --- CONFIGURATION ---
# REPLACE THIS WITH YOUR ACTUAL LEADERBOARD CHANNEL ID
LEADERBOARD_CHANNEL_ID = 1449791275720245460 

# First Blood Bonuses (0=1st place, 1=2nd place, etc.)
BONUSES = {0: 50, 1: 25, 2: 10}

# Global Cooldown Dictionary
COOLDOWNS = {} 

class SubmissionModal(discord.ui.Modal):
    def __init__(self, challenge_id, bot):
        super().__init__(title=f'Submit: {challenge_id}')
        self.challenge_id = challenge_id
        self.bot = bot

    flag_input = discord.ui.TextInput(
        label='Flag', 
        placeholder='SGCTF{...}', 
        style=discord.TextStyle.short, 
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        
        # 1. Cooldown
        last_try = COOLDOWNS.get(user_id, 0)
        if time.time() - last_try < 5: 
            remaining = int(5 - (time.time() - last_try))
            await interaction.response.send_message(f"⏳ **Cooldown!** Wait {remaining}s.", ephemeral=True)
            return
        
        COOLDOWNS[user_id] = time.time()
        
        user_flag = self.flag_input.value.strip()
        username = interaction.user.name

        conn = sqlite3.connect('ctf_data.db')
        c = conn.cursor()
        
        # 2. Get Challenge Data
        c.execute("SELECT points, flag_text FROM flags WHERE challenge_id = ?", (self.challenge_id,))
        data = c.fetchone()
        
        if not data:
            await interaction.response.send_message("❌ Error: Challenge data missing.", ephemeral=True)
            conn.close()
            return

        base_points, real_flag = data

        # 3. Verify Flag
        if user_flag != real_flag:
            await interaction.response.send_message("❌ **Incorrect Flag.** Try harder.", ephemeral=True)
            conn.close()
            return

        # 4. Check Duplicate
        c.execute("SELECT * FROM solves WHERE user_id = ? AND challenge_id = ?", (user_id, self.challenge_id))
        if c.fetchone():
            await interaction.response.send_message("⚠️ **You already solved this!**", ephemeral=True)
            conn.close()
            return

        # 5. Calculate Points
        c.execute("SELECT COUNT(*) FROM solves WHERE challenge_id = ?", (self.challenge_id,))
        solve_count = c.fetchone()[0]
        bonus = BONUSES.get(solve_count, 0)
        total_points = base_points + bonus
        
        # 6. Save
        c.execute("INSERT INTO solves (user_id, challenge_id, timestamp) VALUES (?, ?, ?)", (user_id, self.challenge_id, time.time()))
        c.execute("INSERT OR IGNORE INTO scores (user_id, username, points) VALUES (?, ?, 0)", (user_id, username))
        c.execute("UPDATE scores SET points = points + ? WHERE user_id = ?", (total_points, user_id))
        conn.commit()
        conn.close()

        # 7. Success Msg
        msg = f"🎉 **Correct!** +{total_points} pts"
        if bonus > 0:
            msg += f" (First Blood Bonus: +{bonus}!)"
        await interaction.response.send_message(msg, ephemeral=True)
        
        # 8. Updates
        await self.bot.get_cog('Player').update_leaderboard()
        await self.bot.get_cog('Player').update_challenge_card(self.challenge_id)


class Player(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.leaderboard_loop.start()

    def cog_unload(self):
        self.leaderboard_loop.cancel()

    # --- HELP COMMAND (NEW) ---
    @app_commands.command(name="help", description="Show mission instructions and commands")
    async def help(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        player_desc = (
            "**`/profile`**\n"
            "View your current Rank, Score, and Capture count.\n\n"
            "**How to Submit Flags:**\n"
            "Go to the challenge channel and click the 🟢 **Submit Flag** button attached to the mission card.\n\n"
            "**Leaderboard:**\n"
            "Top agents are tracked live in the designated scoreboard channel."
        )

        embed = discord.Embed(
            title="📚 Agent Field Manual", 
            description="Here is how to operate the CTF system.",
            color=discord.Color.teal()
        )
        embed.add_field(name="🕵️ Agent Protocols", value=player_desc, inline=False)

        if interaction.user.guild_permissions.administrator:
            admin_desc = (
                "**`Lifecycle`**\n"
                "`/create` - Add new challenge.\n"
                "`/post` - Publish challenge.\n"
                "`/edit` - Fix typos/points.\n"
                "`/delete` - Remove challenge (Auto-refunds points).\n\n"
                "**`Management`**\n"
                "`/list` - See status of all challenges.\n"
                "`/show` - Reveal hidden flag/details.\n\n"
                "**`Database`**\n"
                "`/export` - Download backup `.db` file.\n"
                "`/import_db` - Restore from backup."
            )
            embed.add_field(name="🛡️ Admin Control Panel", value=admin_desc, inline=False)

        await interaction.followup.send(embed=embed)

    # --- BUTTON LISTENER (This makes restarts safe) ---
    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type == discord.InteractionType.component:
            custom_id = interaction.data.get("custom_id", "")
            if custom_id.startswith("submit:"):
                challenge_id = custom_id.split(":")[1]
                await interaction.response.send_modal(SubmissionModal(challenge_id, self.bot))

    # --- PROFILE ---
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

    # --- LEADERBOARD ---
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
        if self.bot.user.avatar:
            embed.set_thumbnail(url=self.bot.user.avatar.url)

        if row:
            try:
                msg = await channel.fetch_message(row[0])
                await msg.edit(embed=embed)
                return
            except discord.NotFound: pass

        msg = await channel.send(embed=embed)
        conn = sqlite3.connect('ctf_data.db')
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('lb_msg_id', ?)", (msg.id,))
        conn.commit()
        conn.close()

    # --- CHALLENGE CARD UPDATER ---
    async def update_challenge_card(self, challenge_id):
        conn = sqlite3.connect('ctf_data.db')
        c = conn.cursor()
        
        # 1. Get Challenge Info
        c.execute("SELECT msg_id, channel_id, points FROM flags WHERE challenge_id = ?", (challenge_id,))
        data = c.fetchone()
        if not data: conn.close(); return
        mid, cid, base_pts = data
        
        # 2. Get Solvers
        c.execute("SELECT user_id FROM solves WHERE challenge_id = ? ORDER BY timestamp ASC", (challenge_id,))
        solves = c.fetchall()
        conn.close()

        try:
            channel = self.bot.get_channel(cid)
            if not channel: return
            msg = await channel.fetch_message(mid)
            embed = msg.embeds[0]

            # 3. SAVE EXISTING FIELDS (Bounty & Category)
            saved_fields = []
            for f in embed.fields:
                if "Bounty" in f.name or "Category" in f.name:
                    saved_fields.append(f)
            
            # 4. Clear and Restore
            embed.clear_fields()
            for f in saved_fields:
                embed.add_field(name=f.name, value=f.value, inline=f.inline)

            # 5. Handle FIRST BLOOD
            fb_value = "*Waiting...*"
            if len(solves) > 0:
                first_uid = solves[0][0]
                u = channel.guild.get_member(first_uid)
                name = u.display_name if u else "Agent"
                fb_value = f"🥇 **{name}** (+{base_pts + BONUSES.get(0, 0)})"
            
            embed.add_field(name="🩸 First Blood", value=fb_value, inline=False)

            # 6. Handle REMAINING Solvers (The Leaderboard)
            if len(solves) > 1:
                others = solves[1:] # Skip the first blood
                current_chunk = ""
                page_number = 1
                
                for i, (uid,) in enumerate(others):
                    # Actual index in the full list is i + 1
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
                    
                    line = f"{icon} **{name}** (+{base_pts+bonus})\n"
                    current_chunk += line

                if current_chunk:
                    title = "📜 Solvers" if page_number == 1 else f"📜 Solvers (Page {page_number})"
                    embed.add_field(name=title, value=current_chunk, inline=False)

            await msg.edit(embed=embed)

        except Exception as e:
            print(f"Failed to update challenge card: {e}")

async def setup(bot):
    await bot.add_cog(Player(bot))
