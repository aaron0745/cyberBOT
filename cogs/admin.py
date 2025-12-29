import discord
from discord import app_commands
from discord.ext import commands
from discord.ext import tasks
import sqlite3
import os
import time


# Must match the bonuses in player.py
BONUSES = {0: 50, 1: 25, 2: 10}

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_expiry.start() # <--- NEW: Starts the timer watcher

    def cog_unload(self):
        self.check_expiry.cancel()

# --- BACKGROUND TASK: EXPIRES CHALLENGES ---
    @tasks.loop(seconds=10)
    async def check_expiry(self):
        conn = sqlite3.connect('ctf_data.db')
        c = conn.cursor()
        
        # Get active challenges
        c.execute("SELECT challenge_id, channel_id, msg_id, posted_at FROM flags WHERE msg_id IS NOT NULL")
        active_challenges = c.fetchall()
        
        current_time = int(time.time())
        # --- SET THIS TO YOUR DESIRED DURATION (e.g., 2 mins = 120 seconds) ---
        duration = 1440 * 60 # Change the time to 24hrs

        for challenge_id, channel_id, msg_id, posted_at in active_challenges:
            if not posted_at: continue

            # If time is up
            if current_time > (posted_at + duration):
                try:
                    channel = self.bot.get_channel(channel_id)
                    if channel:
                        msg = await channel.fetch_message(msg_id)
                        embed = msg.embeds[0]

                        # --- SMART FIELD FINDER ---
                        # We search for the field named "Time Left"
                        time_field_index = -1
                        for i, field in enumerate(embed.fields):
                            if "Time Left" in field.name:
                                time_field_index = i
                                break
                        
                        # Case 1: Field exists, check if already expired
                        if time_field_index != -1:
                            if "🔴 Expired" in embed.fields[time_field_index].value:
                                continue # Already updated, skip
                            
                            # Update existing field
                            embed.set_field_at(time_field_index, name="⏳ Time Left", value="**🔴 Expired**", inline=True)

                        # Case 2: Field is MISSING (safe fallback). 
                        # Insert at index 2 (after Bounty and Category)
                        else:
                            embed.insert_field_at(2, name="⏳ Time Left", value="**🔴 Expired**", inline=True)

                        # --- DISABLE BUTTONS ---
                        view = discord.ui.View.from_message(msg)
                        for child in view.children:
                            if hasattr(child, "label") and child.label == "Submit Flag":
                                child.disabled = True
                                child.style = discord.ButtonStyle.danger
                                child.label = "Closed"
                        
                        await msg.edit(embed=embed, view=view)
                        print(f"🚨 Expired challenge: {challenge_id}")

                except Exception as e:
                    # Fails silently if message was deleted
                    pass
        
        conn.close()

    @check_expiry.before_loop
    async def before_check_expiry(self):
        await self.bot.wait_until_ready()

    # --- 0. SETUP COMMANDS ---
    
    @app_commands.command(name="setup", description="Configure channels and roles for the CTF")
    @app_commands.describe(
        leaderboard_channel="Where the leaderboard updates",
        log_channel="Where solves are logged",
        general_channel="Where main chat happens (for announcements)",
        champion_role="The role given to the #1 player",
        rank_1_role="Role for 2500 pts",
        rank_2_role="Role for 6000 pts",
        rank_3_role="Role for 9000 pts"
    )
    @app_commands.default_permissions(administrator=True)
    async def setup(self, interaction: discord.Interaction, 
                    leaderboard_channel: discord.TextChannel = None,
                    log_channel: discord.TextChannel = None,
                    general_channel: discord.TextChannel = None,
                    champion_role: discord.Role = None,
                    rank_1_role: discord.Role = None,
                    rank_2_role: discord.Role = None,
                    rank_3_role: discord.Role = None):
        
        await interaction.response.defer(ephemeral=True)
        conn = sqlite3.connect('ctf_data.db')
        c = conn.cursor()
        
        updates = []
        if leaderboard_channel: 
            c.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('channel_leaderboard', ?)", (leaderboard_channel.id,))
            updates.append(f"✅ Leaderboard Channel: {leaderboard_channel.mention}")
        
        if log_channel:
            c.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('channel_log', ?)", (log_channel.id,))
            updates.append(f"✅ Log Channel: {log_channel.mention}")

        if general_channel:
            c.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('channel_general', ?)", (general_channel.id,))
            updates.append(f"✅ General Channel: {general_channel.mention}")

        if champion_role:
            c.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('role_champion', ?)", (champion_role.id,))
            updates.append(f"👑 Champion Role: **{champion_role.name}**")

        if rank_1_role:
            c.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('role_rank_1', ?)", (rank_1_role.id,))
            updates.append(f"⭐ Rank 1 Role: **{rank_1_role.name}**")

        if rank_2_role:
            c.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('role_rank_2', ?)", (rank_2_role.id,))
            updates.append(f"⭐ Rank 2 Role: **{rank_2_role.name}**")

        if rank_3_role:
            c.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('role_rank_3', ?)", (rank_3_role.id,))
            updates.append(f"⭐ Rank 3 Role: **{rank_3_role.name}**")

        conn.commit()
        conn.close()

        if not updates:
            await interaction.followup.send("⚠️ No settings changed. Please select options to configure.")
        else:
            await interaction.followup.send("⚙️ **Configuration Updated:**\n" + "\n".join(updates))

    @app_commands.command(name="reset_config", description="Wipe all channel/role configurations")
    @app_commands.default_permissions(administrator=True)
    async def reset_config(self, interaction: discord.Interaction):
        conn = sqlite3.connect('ctf_data.db')
        c = conn.cursor()
        c.execute("DELETE FROM config")
        conn.commit()
        conn.close()
        await interaction.response.send_message("🔄 **Config Reset!** Run `/setup` to re-configure.", ephemeral=True)

    @app_commands.command(name="wipe_all", description="⚠️ NUCLEAR: Delete EVERYTHING (Players, Flags, Solves)")
    @app_commands.default_permissions(administrator=True)
    async def wipe_all(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        conn = sqlite3.connect('ctf_data.db')
        c = conn.cursor()
        
        # Delete data from all tables
        c.execute("DELETE FROM flags")
        c.execute("DELETE FROM scores")
        c.execute("DELETE FROM solves")
        c.execute("DELETE FROM banlist")
        c.execute("DELETE FROM hints")
        c.execute("DELETE FROM unlocked_hints")
        c.execute("DELETE FROM config")
        
        conn.commit()
        conn.close()
        
        await interaction.followup.send("☢️ **NUCLEAR WIPEOUT COMPLETE.**\nThe database is empty. You have a clean slate.")

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
        
        # Check if challenge exists and get post info
        c.execute("SELECT challenge_id, channel_id, msg_id FROM flags WHERE challenge_id = ?", (challenge_id,))
        row = c.fetchone()
        
        if not row:
            conn.close()
            await interaction.response.send_message(f"❌ Challenge **{challenge_id}** does not exist.", ephemeral=True)
            return

        cid, channel_id, msg_id = row

        # Insert the hint
        c.execute("INSERT INTO hints (challenge_id, hint_text, cost) VALUES (?, ?, ?)", (challenge_id, text, cost))
        conn.commit()
        conn.close()
        
        # --- UPDATE DISCORD MESSAGE IF IT EXISTS ---
        update_status = ""
        if channel_id and msg_id:
            try:
                ch = self.bot.get_channel(channel_id)
                if ch:
                    msg = await ch.fetch_message(msg_id)
                    
                    # Get existing view (buttons)
                    view = discord.ui.View.from_message(msg)
                    
                    # Check if hint button is already there
                    has_hint_btn = any(child.custom_id == f"hints:{challenge_id}" for child in view.children if hasattr(child, "custom_id"))
                    
                    if not has_hint_btn:
                        # Add the button dynamically
                        btn_hint = discord.ui.Button(label="Hints", style=discord.ButtonStyle.gray, emoji="💡", custom_id=f"hints:{challenge_id}")
                        view.add_item(btn_hint)
                        await msg.edit(view=view)
                        update_status = "\n💡 **Button added to live post!**"
            except Exception as e:
                update_status = f"\n⚠️ Could not update live post: {e}"
        # -------------------------------------------

        await interaction.response.send_message(f"✅ Added hint for **{challenge_id}** (Cost: {cost} pts).{update_status}", ephemeral=True)

# --- 3. POST CHALLENGE ---
    @app_commands.command(name="post", description="Post a challenge (Starts 2m Timer)")
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

        current_time = int(time.time())
        end_time = current_time + (1440 * 60) # Change the time here to 24hrs 

        embed = discord.Embed(
            title=f"🛡️ MISSION: {challenge_id}",
            description=final_desc,
            color=discord.Color.red()
        )
        embed.add_field(name="💰 Bounty", value=f"**{points} Points**", inline=True)
        embed.add_field(name="📂 Category", value=f"**{category}**", inline=True)
        embed.add_field(name="⏳ Time Left", value=f"<t:{end_time}:R>", inline=True)
        embed.add_field(name="🩸 First Blood", value="*Waiting...*", inline=False) 

        if image_url:
            embed.set_image(url=image_url)
        if file:
            embed.set_footer(text="📁 See attached file below")
        
        # --- LOGIC TO CHECK IF HINTS EXIST ---
        c.execute("SELECT COUNT(*) FROM hints WHERE challenge_id = ?", (challenge_id,))
        has_hints = c.fetchone()[0] > 0

        # BUTTONS
        view = discord.ui.View(timeout=None)
        btn_flag = discord.ui.Button(label="Submit Flag", style=discord.ButtonStyle.green, emoji="🚩", custom_id=f"submit:{challenge_id}")
        btn_hint = discord.ui.Button(label="Hints", style=discord.ButtonStyle.gray, emoji="💡", custom_id=f"hints:{challenge_id}")
        
        view.add_item(btn_flag)
        
        # ONLY ADD HINT BUTTON IF HINTS EXIST
        if has_hints:
            view.add_item(btn_hint)
        # -------------------------------------

        try:
            msg = await target_channel.send(embed=embed, view=view)

            if file:
                f = await file.to_file()
                await target_channel.send(file=f)

            c.execute("UPDATE flags SET msg_id = ?, channel_id = ?, posted_at = ? WHERE challenge_id = ?", 
                      (msg.id, target_channel.id, current_time, challenge_id))
            conn.commit()
            
            hint_status = " (Hints available)" if has_hints else " (No hints yet)"
            await interaction.followup.send(f"✅ Posted **{challenge_id}**!{hint_status}")
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

    # --- 6. DELETE CHALLENGE ---
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
    @app_commands.command(name="revoke", description="Remove a solve and its specific points (including bonuses)")
    @app_commands.default_permissions(administrator=True)
    async def revoke(self, interaction: discord.Interaction, member: discord.Member, challenge_id: str):
        conn = sqlite3.connect('ctf_data.db')
        c = conn.cursor()
        
        # 1. Check if the solve exists
        c.execute("SELECT timestamp FROM solves WHERE user_id = ? AND challenge_id = ?", (member.id, challenge_id))
        solve_data = c.fetchone()
        
        if not solve_data:
            conn.close()
            await interaction.response.send_message(f"❌ {member.mention} has not solved **{challenge_id}**.", ephemeral=True)
            return
            
        timestamp = solve_data[0]
        
        # 2. Get Challenge Points
        c.execute("SELECT points FROM flags WHERE challenge_id = ?", (challenge_id,))
        flag_data = c.fetchone()
        if not flag_data:
            conn.close()
            await interaction.response.send_message(f"❌ Challenge **{challenge_id}** not found.", ephemeral=True)
            return
            
        base_points = flag_data[0]
        
        # 3. Calculate Rank
        c.execute("SELECT COUNT(*) FROM solves WHERE challenge_id = ? AND timestamp < ?", (challenge_id, timestamp))
        rank = c.fetchone()[0]
        
        bonus = BONUSES.get(rank, 0)
        deduction = base_points + bonus
        
        # 4. Remove Solve and Deduct Points
        c.execute("DELETE FROM solves WHERE user_id = ? AND challenge_id = ?", (member.id, challenge_id))
        c.execute("UPDATE scores SET points = points - ? WHERE user_id = ?", (deduction, member.id))
        
        conn.commit()
        conn.close()

        # Update visuals
        cog = self.bot.get_cog('Player')
        if cog:
            await cog.update_leaderboard()
            await cog.update_challenge_card(challenge_id)

        await interaction.response.send_message(f"🚨 **REVOKED!** Removed solve for **{challenge_id}** from {member.mention}.\n🔻 Deducted **{deduction} points** (Base: {base_points} + Bonus: {bonus}).", ephemeral=True)

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

    # --- 11. EXPORT DATABASE ---
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

    # --- 12. IMPORT DATABASE ---
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
