import discord
from discord import app_commands
from discord.ext import commands
import sqlite3

# Must match the bonuses in player.py to deduct correctly
BONUSES = {0: 50, 1: 25, 2: 10}

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # --- CREATE CHALLENGE ---
    @app_commands.command(name="create", description="Add a new challenge")
    @app_commands.default_permissions(administrator=True) 
    async def create(self, interaction: discord.Interaction, challenge_id: str, points: int, flag: str, category: str, image_url: str = None):
        await interaction.response.defer(ephemeral=True)

        conn = sqlite3.connect('ctf_data.db')
        c = conn.cursor()
        
        try:
            c.execute("INSERT INTO flags (challenge_id, points, flag_text, category, image_url) VALUES (?, ?, ?, ?, ?)", 
                      (challenge_id, points, flag, category, image_url))
            conn.commit()
            
            msg = f"✅ Created **{category}** challenge **{challenge_id}** ({points} pts)"
            if image_url:
                msg += " with 🖼️ Banner!"
        except sqlite3.IntegrityError:
            msg = f"⚠️ Challenge **{challenge_id}** already exists!"
        except Exception as e:
            msg = f"⚠️ Database Error: {e}"
        finally:
            conn.close()
        
        await interaction.followup.send(msg)

    # --- DELETE CHALLENGE ---
    @app_commands.command(name="delete", description="Remove a challenge and deduct points")
    @app_commands.default_permissions(administrator=True)
    async def delete(self, interaction: discord.Interaction, challenge_id: str):
        await interaction.response.defer(ephemeral=True)

        conn = sqlite3.connect('ctf_data.db')
        c = conn.cursor()
        
        c.execute("SELECT points, msg_id, channel_id FROM flags WHERE challenge_id = ?", (challenge_id,))
        data = c.fetchone()
        
        if not data:
            conn.close()
            await interaction.followup.send(f"❌ Challenge **{challenge_id}** not found.")
            return

        base_points, msg_id, channel_id = data

        # Deduct points
        c.execute("SELECT user_id FROM solves WHERE challenge_id = ? ORDER BY timestamp ASC", (challenge_id,))
        solvers = c.fetchall()

        affected_users = 0
        for i, (uid,) in enumerate(solvers):
            bonus = BONUSES.get(i, 0)
            deduction = base_points + bonus
            c.execute("UPDATE scores SET points = points - ? WHERE user_id = ?", (deduction, uid))
            affected_users += 1

        # Delete Message
        if msg_id and channel_id:
            try:
                channel = self.bot.get_channel(channel_id)
                if channel:
                    msg = await channel.fetch_message(msg_id)
                    await msg.delete()
            except:
                pass 

        c.execute("DELETE FROM flags WHERE challenge_id = ?", (challenge_id,))
        c.execute("DELETE FROM solves WHERE challenge_id = ?", (challenge_id,))
        conn.commit()
        conn.close()
        
        response = f"🗑️ Deleted challenge **{challenge_id}**.\n📉 Deducted points from **{affected_users}** agents."
        await interaction.followup.send(response)

    # --- POST CHALLENGE (Now with Extra Connection Info) ---
    @app_commands.command(name="post", description="Post a challenge to a specific channel")
    @app_commands.default_permissions(administrator=True)
    async def post(self, 
                   interaction: discord.Interaction, 
                   challenge_id: str, 
                   channel: discord.TextChannel = None, 
                   description: str = None, 
                   connection_info: str = None,  # <--- NEW OPTIONAL INPUT
                   file: discord.Attachment = None):
        
        await interaction.response.defer(ephemeral=True)

        target_channel = channel or interaction.channel

        conn = sqlite3.connect('ctf_data.db')
        c = conn.cursor()
        
        try:
            c.execute("SELECT points, image_url, category FROM flags WHERE challenge_id = ?", (challenge_id,))
            data = c.fetchone()
        except sqlite3.OperationalError:
             await interaction.followup.send("⚠️ **Database Error:** Please delete 'ctf_data.db' and restart.", ephemeral=True)
             conn.close()
             return
        
        if not data:
            conn.close()
            await interaction.followup.send(f"❌ Challenge **{challenge_id}** not found in DB.", ephemeral=True)
            return

        points, image_url, category = data
        
        if not category: category = "General"
        if not description: description = "Solve it."
        
        # --- BUILD DESCRIPTION ---
        # 1. Main Objective
        final_desc = f"**Objective:**\n```text\n{description}\n```"
        
        # 2. Connection Info (if provided)
        if connection_info:
            final_desc += f"\n**📡 Connection:**\n```text\n{connection_info}\n```"

        # Embed
        embed = discord.Embed(
            title=f"🛡️ MISSION: {challenge_id}",
            description=final_desc,
            color=discord.Color.red()
        )
        embed.add_field(name="💰 Bounty", value=f"**{points} Points**", inline=True)
        embed.add_field(name="📂 Category", value=f"**{category}**", inline=True)
        embed.add_field(name="🩸 First Blood", value="*Waiting...*", inline=False) 

        if image_url:
            embed.set_image(url=image_url)

        if file:
            embed.set_footer(text="📁 See attached file below")
        
        view = discord.ui.View(timeout=None)
        button = discord.ui.Button(
            label="Submit Flag", 
            style=discord.ButtonStyle.green, 
            emoji="🚩", 
            custom_id=f"submit:{challenge_id}"
        )
        view.add_item(button)

        try:
            # Send to TARGET Channel
            msg = await target_channel.send(embed=embed, view=view)

            if file:
                f = await file.to_file()
                await target_channel.send(file=f)

            c.execute("UPDATE flags SET msg_id = ?, channel_id = ? WHERE challenge_id = ?", (msg.id, target_channel.id, challenge_id))
            conn.commit()
            
            await interaction.followup.send(f"✅ Posted **{challenge_id}** in {target_channel.mention}!")
        except Exception as e:
            await interaction.followup.send(f"⚠️ Failed to post: {e}")
        
        conn.close()

    # --- LIST CHALLENGES ---
    @app_commands.command(name="list", description="List all challenges")
    @app_commands.default_permissions(administrator=True)
    async def list_challenges(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        conn = sqlite3.connect('ctf_data.db')
        c = conn.cursor()
        c.execute("SELECT challenge_id, points, msg_id FROM flags")
        challenges = c.fetchall()
        conn.close()
        
        if not challenges:
            await interaction.followup.send("No challenges created yet.")
            return
            
        desc = ""
        for cid, pts, mid in challenges:
            status = "🟢 Posted" if mid else "🔴 Unposted"
            desc += f"`{cid}` : {pts} pts ({status})\n"
            
        embed = discord.Embed(title="📋 Challenge List", description=desc, color=discord.Color.blue())
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Admin(bot))
