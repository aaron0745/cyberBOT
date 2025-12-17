import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import os

# Must match the bonuses in player.py
BONUSES = {0: 50, 1: 25, 2: 10}

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # --- 1. CREATE CHALLENGE ---
    @app_commands.command(name="create", description="Add a new challenge to the database")
    @app_commands.describe(challenge_id="Unique ID (e.g. web1)", points="Base points", flag="The answer flag", category="e.g. Crypto", image_url="Optional image link")
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
        except sqlite3.IntegrityError:
            msg = f"⚠️ Challenge **{challenge_id}** already exists!"
        except Exception as e:
            msg = f"⚠️ Database Error: {e}"
        finally:
            conn.close()
        
        await interaction.followup.send(msg)

    # --- 2. ADD HINT ---
    @app_commands.command(name="add_hint", description="Add a purchasable hint to a challenge")
    @app_commands.describe(challenge_id="The challenge ID", text="The hint message", cost="Cost in points")
    @app_commands.default_permissions(administrator=True)
    async def add_hint(self, interaction: discord.Interaction, challenge_id: str, text: str, cost: int):
        conn = sqlite3.connect('ctf_data.db')
        c = conn.cursor()
        
        # Check if challenge exists
        c.execute("SELECT challenge_id FROM flags WHERE challenge_id = ?", (challenge_id,))
        if not c.fetchone():
            conn.close()
            await interaction.response.send_message(f"❌ Challenge **{challenge_id}** does not exist.", ephemeral=True)
            return

        c.execute("INSERT INTO hints (challenge_id, hint_text, cost) VALUES (?, ?, ?)", (challenge_id, text, cost))
        conn.commit()
        conn.close()
        
        await interaction.response.send_message(f"✅ Added hint for **{challenge_id}** (Cost: {cost} pts).", ephemeral=True)

    # --- 3. POST CHALLENGE ---
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
        
        c.execute("SELECT points, image_url, category FROM flags WHERE challenge_id = ?", (challenge_id,))
        data = c.fetchone()
        
        if not data:
            conn.close()
            await interaction.followup.send(f"❌ Challenge **{challenge_id}** not found.", ephemeral=True)
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
        
        # BUTTONS
        view = discord.ui.View(timeout=None)
        btn_flag = discord.ui.Button(label="Submit Flag", style=discord.ButtonStyle.green, emoji="🚩", custom_id=f"submit:{challenge_id}")
        btn_hint = discord.ui.Button(label="Hints", style=discord.ButtonStyle.gray, emoji="💡", custom_id=f"hints:{challenge_id}")
        view.add_item(btn_flag)
        view.add_item(btn_hint)

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

    # --- 4. LIST CHALLENGES ---
    @app_commands.command(name="list", description="List all created challenges")
    @app_commands.default_permissions(administrator=True)
    async def list_challenges(self, interaction: discord.Interaction):
        conn = sqlite3.connect('ctf_data.db')
        c = conn.cursor()
        c.execute("SELECT challenge_id, category, points, msg_id FROM flags")
        challenges = c.fetchall()
        conn.close()

        if not challenges:
            await interaction.response.send_message("📭 No challenges created yet.", ephemeral=True)
            return

        desc = ""
        for cid, cat, pts, mid in challenges:
            status = "✅ Posted" if mid else "📝 Draft"
            desc += f"• **{cid}** ({cat}) - {pts} pts [{status}]\n"

        embed = discord.Embed(title="📋 Challenge List", description=desc, color=discord.Color.blue())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # --- 5. SHOW DETAILS ---
    @app_commands.command(name="show", description="Reveal flag and details for a challenge")
    @app_commands.default_permissions(administrator=True)
    async def show(self, interaction: discord.Interaction, challenge_id: str):
        conn = sqlite3.connect('ctf_data.db')
        c = conn.cursor()
        c.execute("SELECT * FROM flags WHERE challenge_id = ?", (challenge_id,))
        data = c.fetchone()
        conn.close()

        if not data:
            await interaction.response.send_message(f"❌ Challenge **{challenge_id}** not found.", ephemeral=True)
            return

        flag = data[1]
        
        embed = discord.Embed(title=f"🔐 Details: {challenge_id}", color=discord.Color.gold())
        embed.add_field(name="🚩 Flag", value=f"`{flag}`", inline=False)
        embed.add_field(name="💰 Points", value=str(data[2]), inline=True)
        embed.add_field(name="📂 Category", value=data[3], inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # --- 6. DELETE CHALLENGE (CORRECTED) ---
    @app_commands.command(name="delete", description="Delete a challenge and remove points from solvers")
    @app_commands.default_permissions(administrator=True)
    async def delete(self, interaction: discord.Interaction, challenge_id: str):
        await interaction.response.defer(ephemeral=True)
        conn = sqlite3.connect('ctf_data.db')
        c = conn.cursor()
        
        # 1. Get Challenge Data
        c.execute("SELECT points, channel_id, msg_id FROM flags WHERE challenge_id = ?", (challenge_id,))
        flag_data = c.fetchone()
        
        if not flag_data:
            conn.close()
            await interaction.followup.send(f"❌ Challenge **{challenge_id}** not found.")
            return

        base_points = flag_data[0]
        channel_id = flag_data[1]
        msg_id = flag_data[2]

        # 2. Deduct Points from Solvers
        # We must replay the history to see who got bonuses
        c.execute("SELECT user_id FROM solves WHERE challenge_id = ? ORDER BY timestamp ASC", (challenge_id,))
        solvers = c.fetchall()
        
        deducted_count = 0
        for i, (user_id,) in enumerate(solvers):
            bonus = BONUSES.get(i, 0)
            total_deduction = base_points + bonus
            c.execute("UPDATE scores SET points = points - ? WHERE user_id = ?", (total_deduction, user_id))
            deducted_count += 1

        # 3. Delete Data
        c.execute("DELETE FROM flags WHERE challenge_id = ?", (challenge_id,))
        c.execute("DELETE FROM solves WHERE challenge_id = ?", (challenge_id,))
        c.execute("DELETE FROM hints WHERE challenge_id = ?", (challenge_id,))
        
        # 4. Delete Discord Post
        post_status = ""
        if channel_id and msg_id:
            try:
                ch = self.bot.get_channel(channel_id)
                msg = await ch.fetch_message(msg_id)
                await msg.delete()
                post_status = " (Post deleted)"
            except:
                post_status = " (Post not found/already deleted)"

        conn.commit()
        conn.close()

        # 5. Refresh Leaderboard
        cog = self.bot.get_cog('Player')
        if cog: await cog.update_leaderboard()

        await interaction.followup.send(f"🗑️ **Deleted {challenge_id}**\n🔻 Points removed from {deducted_count} players.\n{post_status}")

    # --- 7. EDIT CHALLENGE ---
    @app_commands.command(name="edit", description="Edit a challenge")
    @app_commands.default_permissions(administrator=True)
    async def edit(self, interaction: discord.Interaction, challenge_id: str, points: int = None, flag: str = None, category: str = None, image_url: str = None):
        await interaction.response.defer(ephemeral=True)
        conn = sqlite3.connect('ctf_data.db')
        c = conn.cursor()
        
        updates = []
        params = []
        if points is not None: updates.append("points = ?"); params.append(points)
        if flag is not None: updates.append("flag_text = ?"); params.append(flag)
        if category is not None: updates.append("category = ?"); params.append(category)
        if image_url is not None: updates.append("image_url = ?"); params.append(image_url)

        if not updates:
            conn.close()
            await interaction.followup.send("⚠️ No changes provided.")
            return

        params.append(challenge_id)
        try:
            c.execute(f"UPDATE flags SET {', '.join(updates)} WHERE challenge_id = ?", tuple(params))
            conn.commit()
            await interaction.followup.send(f"✅ Updated **{challenge_id}**.")
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {e}")
        finally:
            conn.close()

    # --- 8. REVOKE SOLVE ---
    @app_commands.command(name="revoke", description="Remove a solve from a player")
    @app_commands.default_permissions(administrator=True)
    async def revoke(self, interaction: discord.Interaction, member: discord.Member, challenge_id: str):
        conn = sqlite3.connect('ctf_data.db')
        c = conn.cursor()
        c.execute("DELETE FROM solves WHERE user_id = ? AND challenge_id = ?", (member.id, challenge_id))
        
        # Recalculate Score
        c.execute("SELECT SUM(f.points) FROM solves s JOIN flags f ON s.challenge_id = f.challenge_id WHERE s.user_id = ?", (member.id,))
        new_score = c.fetchone()[0] or 0
        c.execute("UPDATE scores SET points = ? WHERE user_id = ?", (new_score, member.id))
        conn.commit()
        conn.close()

        # Update visuals
        cog = self.bot.get_cog('Player')
        if cog:
            await cog.update_leaderboard()
            await cog.update_challenge_card(challenge_id)

        await interaction.response.send_message(f"🚨 **REVOKED!** Removed solve for **{challenge_id}** from {member.mention}.", ephemeral=True)

    # --- 9. BAN USER ---
    @app_commands.command(name="ban_user", description="Ban a user from submitting flags")
    @app_commands.default_permissions(administrator=True)
    async def ban_user(self, interaction: discord.Interaction, member: discord.Member):
        conn = sqlite3.connect('ctf_data.db')
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO banlist (user_id) VALUES (?)", (member.id,))
        conn.commit()
        conn.close()
        await interaction.response.send_message(f"🚫 **BANNED!** {member.mention} has been disqualified from the CTF.", ephemeral=True)

    # --- 10. UNBAN USER ---
    @app_commands.command(name="unban_user", description="Re-enable a user to submit flags")
    @app_commands.default_permissions(administrator=True)
    async def unban_user(self, interaction: discord.Interaction, member: discord.Member):
        conn = sqlite3.connect('ctf_data.db')
        c = conn.cursor()
        c.execute("DELETE FROM banlist WHERE user_id = ?", (member.id,))
        rows = c.rowcount
        conn.commit()
        conn.close()
        
        if rows > 0:
            await interaction.response.send_message(f"✅ **UNBANNED!** {member.mention} can now submit flags again.", ephemeral=True)
        else:
            await interaction.response.send_message(f"⚠️ {member.mention} was not banned.", ephemeral=True)

    # --- 11. EXPORT DATABASE (BACKUP) ---
    @app_commands.command(name="export", description="Download the current database backup")
    @app_commands.default_permissions(administrator=True)
    async def export_db(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        if os.path.exists('ctf_data.db'):
            try:
                await interaction.followup.send(
                    content="📦 **Database Backup:**\nSave this file to your computer to prevent data loss.",
                    file=discord.File('ctf_data.db')
                )
            except Exception as e:
                await interaction.followup.send(f"❌ Upload failed: {e}")
        else:
            await interaction.followup.send("❌ Database file 'ctf_data.db' not found.")

    # --- 12. IMPORT DATABASE (RESTORE) ---
    @app_commands.command(name="import", description="⚠️ Overwrite the database with a backup file")
    @app_commands.describe(file="Upload the ctf_data.db file here")
    @app_commands.default_permissions(administrator=True)
    async def import_db(self, interaction: discord.Interaction, file: discord.Attachment):
        await interaction.response.defer(ephemeral=True)
        
        if not file.filename.endswith(".db"):
            await interaction.followup.send("❌ Invalid file. Please upload a `.db` file.")
            return
        
        try:
            # Overwrite the existing file
            await file.save("ctf_data.db")
            
            # Force leaderboard refresh if possible
            cog = self.bot.get_cog('Player')
            if cog: await cog.update_leaderboard()

            await interaction.followup.send("✅ **Database Restored!**\nAll scores, challenges, and solves have been updated to match the file.")
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to import: {e}")

async def setup(bot):
    await bot.add_cog(Admin(bot))
