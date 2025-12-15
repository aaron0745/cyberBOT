import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import os
import shutil

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

    # --- EDIT CHALLENGE ---
    @app_commands.command(name="edit", description="Edit a challenge (Only works if NOT posted yet)")
    @app_commands.default_permissions(administrator=True)
    async def edit(self, interaction: discord.Interaction, challenge_id: str, points: int = None, flag: str = None, category: str = None, image_url: str = None):
        await interaction.response.defer(ephemeral=True)

        conn = sqlite3.connect('ctf_data.db')
        c = conn.cursor()

        # 1. Check if challenge exists and if it is already posted
        c.execute("SELECT msg_id FROM flags WHERE challenge_id = ?", (challenge_id,))
        data = c.fetchone()

        if not data:
            conn.close()
            await interaction.followup.send(f"❌ Challenge **{challenge_id}** not found.")
            return

        msg_id = data[0]
        if msg_id is not None:
            conn.close()
            await interaction.followup.send(f"⚠️ Challenge **{challenge_id}** is already posted (ID: {msg_id}).\nYou must `/delete` and re-create it to avoid breaking the scoreboard.")
            return

        # 2. Build the update query dynamically
        updates = []
        params = []

        if points is not None:
            updates.append("points = ?")
            params.append(points)
        if flag is not None:
            updates.append("flag_text = ?")
            params.append(flag)
        if category is not None:
            updates.append("category = ?")
            params.append(category)
        if image_url is not None:
            updates.append("image_url = ?")
            params.append(image_url)

        if not updates:
            conn.close()
            await interaction.followup.send("⚠️ No changes provided.")
            return

        params.append(challenge_id)
        
        try:
            sql = f"UPDATE flags SET {', '.join(updates)} WHERE challenge_id = ?"
            c.execute(sql, tuple(params))
            conn.commit()
            await interaction.followup.send(f"✅ Successfully updated **{challenge_id}**.")
        except Exception as e:
            await interaction.followup.send(f"❌ Database Error: {e}")
        finally:
            conn.close()

    # --- SHOW CHALLENGE DETAILS ---
    @app_commands.command(name="show", description="Show all details about a challenge")
    @app_commands.default_permissions(administrator=True)
    async def show(self, interaction: discord.Interaction, challenge_id: str):
        await interaction.response.defer(ephemeral=True)

        conn = sqlite3.connect('ctf_data.db')
        c = conn.cursor()
        
        c.execute("SELECT points, category, flag_text, image_url, msg_id, channel_id FROM flags WHERE challenge_id = ?", (challenge_id,))
        data = c.fetchone()
        conn.close()

        if not data:
            await interaction.followup.send(f"❌ Challenge **{challenge_id}** not found.")
            return

        points, category, flag_text, image_url, msg_id, channel_id = data
        
        status = "🟢 Posted" if msg_id else "🔴 Unposted"

        embed = discord.Embed(title=f"🔍 Details: {challenge_id}", color=discord.Color.gold())
        embed.add_field(name="Status", value=status, inline=True)
        embed.add_field(name="Category", value=category, inline=True)
        embed.add_field(name="Points", value=str(points), inline=True)
        embed.add_field(name="🚩 Flag (Hidden)", value=f"`{flag_text}`", inline=False)
        
        if msg_id:
            embed.add_field(name="Post Info", value=f"Msg ID: {msg_id}\nChannel: <#{channel_id}>", inline=False)

        if image_url:
            embed.set_thumbnail(url=image_url)
            embed.add_field(name="🖼️ Banner URL", value=f"[Link]({image_url})", inline=False)

        await interaction.followup.send(embed=embed)

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

        c.execute("SELECT user_id FROM solves WHERE challenge_id = ? ORDER BY timestamp ASC", (challenge_id,))
        solvers = c.fetchall()

        affected_users = 0
        for i, (uid,) in enumerate(solvers):
            bonus = BONUSES.get(i, 0)
            deduction = base_points + bonus
            c.execute("UPDATE scores SET points = points - ? WHERE user_id = ?", (deduction, uid))
            affected_users += 1

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

    # --- POST CHALLENGE ---
    @app_commands.command(name="post", description="Post a challenge to a specific channel")
    @app_commands.default_permissions(administrator=True)
    async def post(self, 
                   interaction: discord.Interaction, 
                   challenge_id: str, 
                   channel: discord.TextChannel = None, 
                   description: str = None, 
                   connection_info: str = None, 
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
        
        final_desc = f"**Objective:**\n```text\n{description}\n```"
        
        if connection_info:
            final_desc += f"\n**📡 Connection:**\n```text\n{connection_info}\n```"

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

    # --- EXPORT DATABASE ---
    @app_commands.command(name="export", description="Download the database backup")
    @app_commands.default_permissions(administrator=True)
    async def export_db(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        if os.path.exists('ctf_data.db'):
            try:
                await interaction.followup.send(
                    content="📦 **Here is your database backup:**",
                    file=discord.File('ctf_data.db')
                )
            except Exception as e:
                await interaction.followup.send(f"❌ Upload failed: {e}")
        else:
            await interaction.followup.send("❌ Error: 'ctf_data.db' not found.")

    # --- IMPORT DATABASE (NEW) ---
    @app_commands.command(name="import_db", description="Upload a .db file to restore data (Overwrites current DB!)")
    @app_commands.default_permissions(administrator=True)
    async def import_db(self, interaction: discord.Interaction, file: discord.Attachment):
        await interaction.response.defer(ephemeral=True)

        if not file.filename.endswith(".db"):
             await interaction.followup.send("❌ File must be a `.db` file (e.g., `ctf_data.db`)")
             return

        # Backup existing just in case
        if os.path.exists('ctf_data.db'):
            try:
                shutil.copy('ctf_data.db', 'ctf_data.db.bak')
            except:
                pass

        try:
            await file.save('ctf_data.db')
            await interaction.followup.send("✅ **Database restored!**\nPrevious DB backed up to `ctf_data.db.bak`.")
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to save file: {e}")
            # Try to restore backup if it failed
            if os.path.exists('ctf_data.db.bak'):
                shutil.copy('ctf_data.db.bak', 'ctf_data.db')

async def setup(bot):
    await bot.add_cog(Admin(bot))
