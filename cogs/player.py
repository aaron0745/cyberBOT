import discord
from discord import app_commands
from discord.ext import commands, tasks
import sqlite3

LEADERBOARD_CHANNEL_ID = 1449791275720245460
BONUSES = {0: 50, 1: 25, 2: 10}

class SubmissionModal(discord.ui.Modal):
    def __init__(self, challenge_id, bot):
        super().__init__(title=f'Submit Flag: {challenge_id}')
        self.challenge_id = challenge_id
        self.bot = bot

    flag_input = discord.ui.TextInput(label='Flag', placeholder='SGCTF{...}', style=discord.TextStyle.short, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        user_flag = self.flag_input.value.strip()
        user_id = interaction.user.id
        username = interaction.user.name

        conn = sqlite3.connect('ctf_data.db')
        c = conn.cursor()
        
        # Get Challenge Data
        c.execute("SELECT points, flag_text, msg_id, channel_id FROM flags WHERE challenge_id = ?", (self.challenge_id,))
        chal_data = c.fetchone()
        
        if not chal_data:
            await interaction.response.send_message("❌ Error: Challenge missing.", ephemeral=True)
            conn.close(); return

        base_points, real_flag, msg_id, channel_id = chal_data

        if user_flag != real_flag:
            await interaction.response.send_message("❌ Incorrect flag.", ephemeral=True)
            conn.close(); return

        # Check Duplicates
        c.execute("SELECT * FROM solves WHERE user_id = ? AND challenge_id = ?", (user_id, self.challenge_id))
        if c.fetchone():
            await interaction.response.send_message("⚠️ You already solved this!", ephemeral=True)
            conn.close(); return

        # Check First Blood (Is this the first solve?)
        c.execute("SELECT COUNT(*) FROM solves WHERE challenge_id = ?", (self.challenge_id,))
        solve_count = c.fetchone()[0]
        
        is_first_blood = (solve_count == 0)
        bonus = BONUSES.get(solve_count, 0)
        
        # Save Solve
        c.execute("INSERT INTO solves (user_id, challenge_id) VALUES (?, ?)", (user_id, self.challenge_id))
        c.execute("INSERT OR IGNORE INTO scores (user_id, username, points) VALUES (?, ?, 0)", (user_id, username))
        c.execute("UPDATE scores SET points = points + ? WHERE user_id = ?", (base_points + bonus, user_id))
        conn.commit()
        conn.close()

        # Reply to User
        if is_first_blood:
            await interaction.response.send_message(f"🩸 **FIRST BLOOD!** You earned {base_points} + {bonus} bonus pts!", ephemeral=True)
            # TRIGGER THE EDIT
            await self.update_first_blood_display(msg_id, channel_id, interaction.user)
        else:
            await interaction.response.send_message(f"🎉 **Correct!** +{base_points+bonus} pts.", ephemeral=True)
        
        await self.bot.get_cog('Player').update_leaderboard()

    async def update_first_blood_display(self, msg_id, channel_id, user):
        """Finds the challenge message and edits the embed"""
        if not msg_id or not channel_id:
            return # Old challenge or no saved location

        try:
            channel = self.bot.get_channel(channel_id)
            if channel:
                msg = await channel.fetch_message(msg_id)
                embed = msg.embeds[0]
                
                # Edit Field Index 2 (First Blood)
                # We reconstruct the fields because Embeds are immutable-ish
                embed.set_field_at(2, name="🩸 First Blood", value=f"**{user.mention}**", inline=True)
                
                await msg.edit(embed=embed)
        except Exception as e:
            print(f"Failed to update First Blood: {e}")

class Player(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.leaderboard_loop.start()

    def cog_unload(self):
        self.leaderboard_loop.cancel()

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

        embed = discord.Embed(title="🏆 CTF Live Standings", color=0xFFD700)
        desc = ""
        for i, (user, points) in enumerate(top_players, 1):
            icon = "👑" if i==1 else "🥈" if i==2 else "🥉" if i==3 else f"**#{i}**"
            desc += f"{icon} • **{user}** — `{points} pts`\n"
        
        embed.description = desc if desc else "Waiting for first blood..."
        embed.set_footer(text="Updates automatically every 60s")
        embed.set_thumbnail(url=self.bot.user.avatar.url if self.bot.user.avatar else None)

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

async def setup(bot):
    await bot.add_cog(Player(bot))
