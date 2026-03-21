import discord
from discord import app_commands
from discord.ext import commands
from discord.ext import tasks
import aiosqlite
import os
import time
import shutil
from datetime import datetime


# Must match the bonuses in player.py
BONUSES = {0: 50, 1: 25, 2: 10}

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.check_expiry.start()
        self.check_pending_posts.start()

    def cog_unload(self):
        self.check_expiry.cancel()
        self.check_pending_posts.cancel()

# --- BACKGROUND TASK: EXPIRES & PERSISTENCE ---
    @tasks.loop(seconds=60)
    async def check_expiry(self):
        # Get active challenges (anything that has been posted)
        async with self.db.execute("SELECT challenge_id, channel_id, msg_id, file_msg_id, end_time, description, connection_info, file_path, posted_at FROM flags WHERE msg_id IS NOT NULL") as cursor:
            active_challenges = await cursor.fetchall()
        
        current_time = int(time.time())

        for challenge_id, channel_id, msg_id, file_msg_id, end_time, description, connection_info, file_path, posted_at in active_challenges:
            # 1. EXPIRY LOGIC
            if end_time and current_time >= end_time:
                # File Cleanup on Expiry
                if file_path and os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        print(f"🧹 Deleted file for expired challenge {challenge_id}")
                    except Exception as e:
                        print(f"⚠️ Error deleting {file_path}: {e}")

                try:
                    channel = self.bot.get_channel(channel_id)
                    if not channel: continue
                    
                    msg = await channel.fetch_message(msg_id)
                    embed = msg.embeds[0]

                    # Check if already marked as expired
                    is_expired = False
                    for field in embed.fields:
                        if "Time Left" in field.name and "🔴 Expired" in field.value:
                            is_expired = True
                            break
                    
                    if is_expired: continue

                    # Update via Player Cog helper
                    cog = self.bot.get_cog('Player')
                    if cog: await cog.update_challenge_card(challenge_id)
                    print(f"🚨 Expired challenge: {challenge_id}")
                except Exception:
                    pass
            
            # 2. PERSISTENCE LOGIC (Anti-Deletion)
            # If posted and NOT expired
            elif posted_at is not None and (not end_time or current_time < end_time):
                try:
                    channel = self.bot.get_channel(channel_id)
                    if not channel: continue
                    
                    missing = False
                    # Check Embed
                    try:
                        await channel.fetch_message(msg_id)
                    except discord.NotFound:
                        missing = True
                    
                    # Check File (if applicable)
                    if not missing and file_path and os.path.exists(file_path):
                        if file_msg_id:
                            try:
                                await channel.fetch_message(file_msg_id)
                            except discord.NotFound:
                                missing = True
                        else:
                            # File path exists but no file_msg_id recorded? Repost to be safe.
                            missing = True
                    
                    if missing:
                        # Message missing! Re-post immediately
                        print(f"🔄 Anti-Deletion: Re-posting challenge {challenge_id}...")
                        
                        # Full Clean Recovery: Attempt to delete remaining message
                        try:
                            old_msg = await channel.fetch_message(msg_id)
                            await old_msg.delete()
                        except: pass
                        
                        if file_msg_id:
                            try:
                                old_f_msg = await channel.fetch_message(file_msg_id)
                                await old_f_msg.delete()
                            except: pass

                        await self.perform_post(challenge_id, channel, description, connection_info, end_time, file_path=file_path)
                except Exception as e:
                    print(f"❌ Error in persistence check for {challenge_id}: {e}")

    @check_expiry.before_loop
    async def before_check_expiry(self):
        await self.bot.wait_until_ready()

# --- BACKGROUND TASK: CHECKS PENDING POSTS ---
    @tasks.loop(seconds=60)
    async def check_pending_posts(self):
        current_time = int(time.time())
        # Check for rows where posted_at is NULL and current_time >= start_time
        async with self.db.execute(
            "SELECT challenge_id, channel_id, description, connection_info, end_time, file_path FROM flags WHERE posted_at IS NULL AND start_time <= ?", 
            (current_time,)
        ) as cursor:
            pending = await cursor.fetchall()

        for row in pending:
            challenge_id, target_channel_id, description, connection_info, end_time, file_path = row
            try:
                target_channel = self.bot.get_channel(target_channel_id)
                if not target_channel:
                    print(f"⚠️ Scheduled post for {challenge_id} failed: Channel {target_channel_id} not found.")
                    continue

                await self.perform_post(challenge_id, target_channel, description, connection_info, end_time, file_path=file_path)
                print(f"📅 Automatically posted scheduled challenge: {challenge_id}")
            except Exception as e:
                print(f"❌ Error in check_pending_posts for {challenge_id}: {e}")

    @check_pending_posts.before_loop
    async def before_check_pending_posts(self):
        await self.bot.wait_until_ready()

    async def perform_post(self, challenge_id, target_channel, description, connection_info, end_time, file=None, file_path=None):
        """Logic to actually post the challenge to Discord and update DB"""
        async with self.db.execute("SELECT points, image_url, category FROM flags WHERE challenge_id = ?", (challenge_id,)) as cursor:
            data = await cursor.fetchone()
        
        if not data:
            return False

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
        embed.add_field(name="⏳ Time Left", value=f"<t:{end_time}:R>", inline=True)
        embed.add_field(name="🩸 First Blood", value="*Waiting...*", inline=False) 

        if image_url:
            embed.set_image(url=image_url)
        if file or file_path:
            embed.set_footer(text="📁 See attached file below")
        
        # --- LOGIC TO CHECK IF HINTS EXIST ---
        async with self.db.execute("SELECT COUNT(*) FROM hints WHERE challenge_id = ?", (challenge_id,)) as cursor:
            row = await cursor.fetchone()
            has_hints = row[0] > 0

        # BUTTONS
        view = discord.ui.View(timeout=None)
        btn_flag = discord.ui.Button(label="Submit Flag", style=discord.ButtonStyle.green, emoji="🚩", custom_id=f"submit:{challenge_id}")
        btn_hint = discord.ui.Button(label="Hints", style=discord.ButtonStyle.gray, emoji="💡", custom_id=f"hints:{challenge_id}")
        
        view.add_item(btn_flag)
        if has_hints:
            view.add_item(btn_hint)

        msg = await target_channel.send(embed=embed, view=view)

        file_msg = None
        # Handle file attachment (Embed first, File second)
        if file:
            f = await file.to_file()
            file_msg = await target_channel.send(file=f)
        # Handle scheduled local file
        elif file_path and os.path.exists(file_path):
            try:
                f = discord.File(file_path)
                file_msg = await target_channel.send(file=f)
                # DO NOT delete local file - it's needed for anti-deletion re-posts
            except Exception as e:
                print(f"⚠️ Error sending scheduled file {file_path}: {e}")

        current_time = int(time.time())
        file_msg_id = file_msg.id if file_msg else None
        await self.db.execute("UPDATE flags SET msg_id = ?, file_msg_id = ?, channel_id = ?, posted_at = ? WHERE challenge_id = ?", 
                (msg.id, file_msg_id, target_channel.id, current_time, challenge_id))
        await self.db.commit()
        return True

    # --- 0. SETUP COMMANDS ---
    
    @app_commands.command(name="setup", description="Configure channels and roles for cyberBOT")
    @app_commands.describe(
        leaderboard_channel="Where the leaderboard updates",
        challenge_logs="Correct solves and collusion warnings",
        wrong_submissions="Every failed flag attempt",
        general_channel="Main chat for announcements",
        champion_role="Role for the #1 player"
    )
    @app_commands.default_permissions(administrator=True)
    async def setup(self, interaction: discord.Interaction, 
                    leaderboard_channel: discord.TextChannel = None,
                    challenge_logs: discord.TextChannel = None,
                    wrong_submissions: discord.TextChannel = None,
                    general_channel: discord.TextChannel = None,
                    champion_role: discord.Role = None):
        
        await interaction.response.defer(ephemeral=True)
        
        updates = []
        if leaderboard_channel: 
            await self.db.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('channel_leaderboard', ?)", (leaderboard_channel.id,))
            updates.append(f"✅ Leaderboard Channel: {leaderboard_channel.mention}")
        
        if challenge_logs:
            await self.db.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('channel_challenge_logs', ?)", (challenge_logs.id,))
            updates.append(f"✅ Challenge Logs: {challenge_logs.mention}")

        if wrong_submissions:
            await self.db.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('channel_wrong_submissions', ?)", (wrong_submissions.id,))
            updates.append(f"✅ Wrong Submissions: {wrong_submissions.mention}")

        if general_channel:
            await self.db.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('channel_general', ?)", (general_channel.id,))
            updates.append(f"✅ General Channel: {general_channel.mention}")

        if champion_role:
            await self.db.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('role_champion', ?)", (champion_role.id,))
            updates.append(f"👑 Champion Role: **{champion_role.name}**")

        await self.db.commit()

        if not updates:
            await interaction.followup.send("⚠️ No settings changed. Please select options to configure.")
        else:
            await interaction.followup.send("⚙️ **Configuration Updated:**\n" + "\n".join(updates))

    @app_commands.command(name="set_rank_role", description="Add or update a role requirement")
    @app_commands.describe(role="The role to assign", points="Points required to earn this role")
    @app_commands.default_permissions(administrator=True)
    async def set_rank_role(self, interaction: discord.Interaction, role: discord.Role, points: int):
        await self.db.execute("INSERT OR REPLACE INTO role_rewards (role_id, points) VALUES (?, ?)", (role.id, points))
        await self.db.commit()
        await interaction.response.send_message(f"✅ **Rank Role Set:** {role.mention} now requires **{points} points**.", ephemeral=True)

    @app_commands.command(name="remove_rank_role", description="Deletes a role from the auto-assignment list")
    @app_commands.describe(role="The role to remove")
    @app_commands.default_permissions(administrator=True)
    async def remove_rank_role(self, interaction: discord.Interaction, role: discord.Role):
        async with self.db.execute("DELETE FROM role_rewards WHERE role_id = ?", (role.id,)) as cursor:
            if cursor.rowcount > 0:
                await self.db.commit()
                await interaction.response.send_message(f"🗑️ **Rank Role Removed:** {role.mention} has been deleted from rewards.", ephemeral=True)
            else:
                await interaction.response.send_message(f"⚠️ {role.mention} was not in the rank rewards list.", ephemeral=True)

    @app_commands.command(name="list_rank_roles", description="Lists all configured roles and their required points")
    @app_commands.default_permissions(administrator=True)
    async def list_rank_roles(self, interaction: discord.Interaction):
        async with self.db.execute("SELECT role_id, points FROM role_rewards ORDER BY points ASC") as cursor:
            roles = await cursor.fetchall()
        
        if not roles:
            await interaction.response.send_message("📭 No rank roles configured yet.", ephemeral=True)
            return
        
        desc = ""
        for rid, pts in roles:
            role = interaction.guild.get_role(rid)
            role_mention = role.mention if role else f"Unknown Role (`{rid}`)"
            desc += f"• {role_mention} — **{pts} points**\n"
        
        embed = discord.Embed(title="⭐ Rank Role Requirements", description=desc, color=discord.Color.blue())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="reset_config", description="Wipe all channel/role configurations")
    @app_commands.default_permissions(administrator=True)
    async def reset_config(self, interaction: discord.Interaction):
        await self.db.execute("DELETE FROM config")
        await self.db.execute("DELETE FROM role_rewards")
        await self.db.commit()
        await interaction.response.send_message("🔄 **Config & Rank Roles Reset!** Run `/setup` and `/set_rank_role` to re-configure.", ephemeral=True)

    @app_commands.command(name="wipe_all", description="⚠️ NUCLEAR: Delete EVERYTHING (Players, Flags, Solves)")
    @app_commands.default_permissions(administrator=True)
    async def wipe_all(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        # Delete data from all tables
        await self.db.execute("DELETE FROM flags")
        await self.db.execute("DELETE FROM scores")
        await self.db.execute("DELETE FROM solves")
        await self.db.execute("DELETE FROM banlist")
        await self.db.execute("DELETE FROM hints")
        await self.db.execute("DELETE FROM unlocked_hints")
        await self.db.execute("DELETE FROM config")
        await self.db.execute("DELETE FROM role_rewards")
        await self.db.commit()
        
        # Storage Cleanup: Wipe the uploads folder
        if os.path.exists('uploads'):
            try:
                shutil.rmtree('uploads')
                os.makedirs('uploads')
            except Exception as e:
                print(f"❌ Storage Wipe Error: {e}")
        
        cog = self.bot.get_cog('Player')
        if cog: await cog.update_leaderboard()

        await interaction.followup.send("☢️ **NUCLEAR WIPEOUT COMPLETE.**\nThe database and local storage are empty.")

    # --- 1. CREATE CHALLENGE ---
    @app_commands.command(name="create", description="Add a new challenge to the database")
    @app_commands.describe(challenge_id="Unique ID (e.g. web1)", points="Base points", flag="The answer flag", category="e.g. Crypto", image_url="Optional image link")
    @app_commands.default_permissions(administrator=True) 
    async def create(self, interaction: discord.Interaction, challenge_id: str, points: int, flag: str, category: str, image_url: str = None):
        await interaction.response.defer(ephemeral=True)

        try:
            await self.db.execute("INSERT INTO flags (challenge_id, points, flag_text, category, image_url) VALUES (?, ?, ?, ?, ?)", 
                    (challenge_id, points, flag, category, image_url))
            await self.db.commit()
            msg = f"✅ Created **{category}** challenge **{challenge_id}** ({points} pts)"
        except aiosqlite.IntegrityError:
            msg = f"⚠️ Challenge **{challenge_id}** already exists!"
        except Exception as e:
            msg = f"⚠️ Database Error: {e}"
        
        await interaction.followup.send(msg)

# --- 2. ADD HINT ---
    @app_commands.command(name="add_hint", description="Add a purchasable hint to a challenge")
    @app_commands.describe(challenge_id="The challenge ID", text="The hint message", cost="Cost in points")
    @app_commands.default_permissions(administrator=True)
    async def add_hint(self, interaction: discord.Interaction, challenge_id: str, text: str, cost: int):
        # Check if challenge exists and get post info
        async with self.db.execute("SELECT challenge_id, channel_id, msg_id FROM flags WHERE challenge_id = ?", (challenge_id,)) as cursor:
            row = await cursor.fetchone()
        
        if not row:
            await interaction.response.send_message(f"❌ Challenge **{challenge_id}** does not exist.", ephemeral=True)
            return

        cid, channel_id, msg_id = row

        # Insert the hint
        async with self.db.execute("INSERT INTO hints (challenge_id, hint_text, cost) VALUES (?, ?, ?)", (challenge_id, text, cost)) as cursor:
            hint_id = cursor.lastrowid
        await self.db.commit()
        
        # --- UPDATE DISCORD MESSAGE IF IT EXISTS ---
        update_status = ""
        if channel_id and msg_id:
            try:
                ch = self.bot.get_channel(channel_id)
                if ch:
                    msg = await ch.fetch_message(msg_id)
                    view = discord.ui.View.from_message(msg)
                    has_hint_btn = any(child.custom_id == f"hints:{challenge_id}" for child in view.children if hasattr(child, "custom_id"))
                    
                    if not has_hint_btn:
                        btn_hint = discord.ui.Button(label="Hints", style=discord.ButtonStyle.gray, emoji="💡", custom_id=f"hints:{challenge_id}")
                        view.add_item(btn_hint)
                        await msg.edit(view=view)
                        update_status = "\n💡 **Button added to live post!**"
            except Exception as e:
                update_status = f"\n⚠️ Could not update live post: {e}"

        await interaction.response.send_message(f"✅ Added **Hint #{hint_id}** for **{challenge_id}** (Cost: {cost} pts).{update_status}", ephemeral=True)

# --- 2.1 REMOVE HINT ---
    @app_commands.command(name="remove_hint", description="Remove a hint and refund points to buyers")
    @app_commands.describe(hint_id="The ID of the hint to remove")
    @app_commands.default_permissions(administrator=True)
    async def remove_hint(self, interaction: discord.Interaction, hint_id: int):
        await interaction.response.defer(ephemeral=True)

        # 1. Get hint details
        async with self.db.execute("SELECT challenge_id, cost FROM hints WHERE id = ?", (hint_id,)) as cursor:
            hint_row = await cursor.fetchone()
        
        if not hint_row:
            await interaction.followup.send(f"❌ Hint #{hint_id} not found.")
            return
        
        challenge_id, cost = hint_row

        # 2. Identify buyers for refund
        async with self.db.execute("SELECT user_id FROM unlocked_hints WHERE hint_id = ?", (hint_id,)) as cursor:
            buyers = await cursor.fetchall()
        
        # 3. Process Refunds
        if buyers:
            await self.db.executemany("UPDATE scores SET points = points + ? WHERE user_id = ?", 
                                     [(cost, uid[0]) for uid in buyers])
        
        # 4. Delete hint and unlock records
        await self.db.execute("DELETE FROM unlocked_hints WHERE hint_id = ?", (hint_id,))
        await self.db.execute("DELETE FROM hints WHERE id = ?", (hint_id,))
        await self.db.commit()

        # 5. Check if any hints remain for this challenge to update UI
        update_status = ""
        async with self.db.execute("SELECT COUNT(*) FROM hints WHERE challenge_id = ?", (challenge_id,)) as cursor:
            count_res = await cursor.fetchone()
            hints_remain = count_res[0] > 0
        
        if not hints_remain:
            async with self.db.execute("SELECT channel_id, msg_id FROM flags WHERE challenge_id = ?", (challenge_id,)) as cursor:
                flag_row = await cursor.fetchone()
            
            if flag_row and flag_row[0] and flag_row[1]:
                try:
                    ch = self.bot.get_channel(flag_row[0])
                    if ch:
                        msg = await ch.fetch_message(flag_row[1])
                        view = discord.ui.View.from_message(msg)
                        # Remove hint button
                        new_children = [c for c in view.children if not (hasattr(c, "custom_id") and c.custom_id == f"hints:{challenge_id}")]
                        if len(new_children) != len(view.children):
                            view.clear_items()
                            for child in new_children: view.add_item(child)
                            await msg.edit(view=view)
                            update_status = "\n🗑️ **Hints button removed from live post.**"
                except Exception:
                    pass

        # 6. Refresh Leaderboard
        cog = self.bot.get_cog('Player')
        if cog: await cog.update_leaderboard()

        await interaction.followup.send(f"🗑️ **Hint #{hint_id} removed.**\n💰 Refunded {cost} points to {len(buyers)} players.{update_status}")

# --- 3. POST CHALLENGE ---
    @app_commands.command(name="post", description="Post or schedule a challenge")
    @app_commands.describe(
        challenge_id="The ID of the challenge to post",
        start_time="When to post (DD/MM HH:MM)",
        end_time="When it expires (DD/MM HH:MM)",
        channel="Target channel (defaults to current)",
        description="Brief objective",
        connection_info="Connection details",
        file="Attachment file"
    )
    @app_commands.default_permissions(administrator=True)
    async def post(self, 
                   interaction: discord.Interaction, 
                   challenge_id: str, 
                   start_time: str,
                   end_time: str,
                   channel: discord.TextChannel = None, 
                   description: str = None, 
                   connection_info: str = None, 
                   file: discord.Attachment = None):
        
        try:
            now = datetime.now()
            start_dt = datetime.strptime(start_time, "%d/%m %H:%M").replace(year=now.year)
            end_dt = datetime.strptime(end_time, "%d/%m %H:%M").replace(year=now.year)
            
            start_ts = int(start_dt.timestamp())
            end_ts = int(end_dt.timestamp())
        except ValueError:
            await interaction.response.send_message("❌ **Invalid time format!** Use `DD/MM HH:MM` (e.g. `25/12 14:00`).", ephemeral=True)
            return

        target_channel = channel or interaction.channel
        current_ts = int(time.time())

        # Check if challenge exists
        async with self.db.execute("SELECT points FROM flags WHERE challenge_id = ?", (challenge_id,)) as cursor:
            if not await cursor.fetchone():
                await interaction.response.send_message(f"❌ Challenge **{challenge_id}** not found.", ephemeral=True)
                return

        if start_ts > current_ts:
            # Scheduled post
            file_path = None
            if file:
                if not os.path.exists('uploads'): os.makedirs('uploads')
                file_path = f"uploads/{challenge_id}_{file.filename}"
                await file.save(file_path)

            await self.db.execute(
                "UPDATE flags SET start_time = ?, end_time = ?, channel_id = ?, description = ?, connection_info = ?, posted_at = NULL, file_path = ? WHERE challenge_id = ?",
                (start_ts, end_ts, target_channel.id, description, connection_info, file_path, challenge_id)
            )
            await self.db.commit()
            await interaction.response.send_message(f"📅 **Scheduled!** **{challenge_id}** will be posted to {target_channel.mention} at <t:{start_ts}:F>.", ephemeral=True)
        else:
            # Immediate post
            await interaction.response.defer(ephemeral=True)
            
            file_path = None
            if file:
                if not os.path.exists('uploads'): os.makedirs('uploads')
                file_path = f"uploads/{challenge_id}_{file.filename}"
                await file.save(file_path)

            # Update DB with times and file_path
            await self.db.execute("UPDATE flags SET start_time = ?, end_time = ?, description = ?, connection_info = ?, file_path = ? WHERE challenge_id = ?",
                                 (start_ts, end_ts, description, connection_info, file_path, challenge_id))
            await self.db.commit()
            
            success = await self.perform_post(challenge_id, target_channel, description, connection_info, end_ts, file_path=file_path)
            if success:
                await interaction.followup.send(f"✅ Posted **{challenge_id}** immediately!")
            else:
                await interaction.followup.send(f"❌ Failed to post **{challenge_id}**.")

    # --- 4. LIST CHALLENGES ---
    @app_commands.command(name="list", description="List all created challenges")
    @app_commands.default_permissions(administrator=True)
    async def list_challenges(self, interaction: discord.Interaction):
        async with self.db.execute("SELECT challenge_id, category, points, msg_id FROM flags") as cursor:
            challenges = await cursor.fetchall()

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
        async with self.db.execute("SELECT flag_text, points, category FROM flags WHERE challenge_id = ?", (challenge_id,)) as cursor:
            data = await cursor.fetchone()

        if not data:
            await interaction.response.send_message(f"❌ Challenge **{challenge_id}** not found.", ephemeral=True)
            return

        flag, points, category = data
        
        embed = discord.Embed(title=f"🔐 Details: {challenge_id}", color=discord.Color.gold())
        embed.add_field(name="🚩 Flag", value=f"`{flag}`", inline=False)
        embed.add_field(name="💰 Points", value=str(points), inline=True)
        embed.add_field(name="📂 Category", value=category, inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # --- 6. DELETE CHALLENGE ---
    @app_commands.command(name="delete", description="Delete a challenge and remove points from solvers")
    @app_commands.default_permissions(administrator=True)
    async def delete(self, interaction: discord.Interaction, challenge_id: str):
        await interaction.response.defer(ephemeral=True)
        
        # 1. Get Challenge Data
        async with self.db.execute("SELECT points, channel_id, msg_id, file_msg_id, file_path FROM flags WHERE challenge_id = ?", (challenge_id,)) as cursor:
            flag_data = await cursor.fetchone()
        
        if not flag_data:
            await interaction.followup.send(f"❌ Challenge **{challenge_id}** not found.")
            return

        base_points, channel_id, msg_id, file_msg_id, file_path = flag_data

        # 2. Deduct Points from Solvers
        async with self.db.execute("SELECT user_id FROM solves WHERE challenge_id = ? ORDER BY timestamp ASC", (challenge_id,)) as cursor:
            solvers = await cursor.fetchall()
        
        deductions = []
        for i, (user_id,) in enumerate(solvers):
            bonus = BONUSES.get(i, 0)
            total_deduction = base_points + bonus
            deductions.append((total_deduction, user_id))

        if deductions:
            await self.db.executemany("UPDATE scores SET points = points - ? WHERE user_id = ?", deductions)
        
        # Refund Hints
        async with self.db.execute("""
            SELECT uh.user_id, h.cost 
            FROM unlocked_hints uh 
            JOIN hints h ON uh.hint_id = h.id 
            WHERE h.challenge_id = ?
        """, (challenge_id,)) as cursor:
            refunds = await cursor.fetchall()
        
        if refunds:
            await self.db.executemany("UPDATE scores SET points = points + ? WHERE user_id = ?", 
                                     [(cost, uid) for uid, cost in refunds])

        # 3. File Cleanup
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                print(f"⚠️ Failed to delete local file {file_path}: {e}")

        # 4. Delete Data
        await self.db.execute("DELETE FROM flags WHERE challenge_id = ?", (challenge_id,))
        await self.db.execute("DELETE FROM solves WHERE challenge_id = ?", (challenge_id,))
        await self.db.execute("DELETE FROM unlocked_hints WHERE hint_id IN (SELECT id FROM hints WHERE challenge_id = ?)", (challenge_id,))
        await self.db.execute("DELETE FROM hints WHERE challenge_id = ?", (challenge_id,))
        await self.db.commit()
        
        # 5. Delete Discord Post
        post_status = ""
        if channel_id:
            try:
                ch = self.bot.get_channel(channel_id)
                if ch:
                    if msg_id:
                        try:
                            m = await ch.fetch_message(msg_id)
                            await m.delete()
                            post_status += " (Embed deleted)"
                        except:
                            post_status += " (Embed not found)"
                    
                    if file_msg_id:
                        try:
                            fm = await ch.fetch_message(file_msg_id)
                            await fm.delete()
                            post_status += " (File deleted)"
                        except:
                            post_status += " (File not found)"
            except Exception as e:
                post_status = f" (Deletion error: {e})"
        
        if not post_status: post_status = " (No post to delete)"

        # 6. Refresh Leaderboard
        cog = self.bot.get_cog('Player')
        if cog: await cog.update_leaderboard()

        await interaction.followup.send(f"🗑️ **Deleted {challenge_id}**\n🔻 Points removed from {len(deductions)} players.\n💰 Refunds processed for {len(refunds)} hint unlocks.\n{post_status}")

    # --- 7. EDIT CHALLENGE ---
    @app_commands.command(name="edit", description="Comprehensive edit for any challenge attribute")
    @app_commands.describe(
        challenge_id="The current ID of the challenge",
        new_id="New unique ID (if renaming)",
        points="New base points",
        flag="New answer flag",
        category="New category",
        image_url="New image link",
        description="New objective",
        connection_info="New connection details",
        start_time="New start (DD/MM HH:MM)",
        end_time="New end (DD/MM HH:MM)"
    )
    @app_commands.default_permissions(administrator=True)
    async def edit(self, interaction: discord.Interaction, 
                   challenge_id: str, 
                   new_id: str = None,
                   points: int = None, 
                   flag: str = None, 
                   category: str = None, 
                   image_url: str = None,
                   description: str = None,
                   connection_info: str = None,
                   start_time: str = None,
                   end_time: str = None):
        await interaction.response.defer(ephemeral=True)
        
        async with self.db.execute("SELECT * FROM flags WHERE challenge_id = ?", (challenge_id,)) as cursor:
            row = await cursor.fetchone()
        
        if not row:
            await interaction.followup.send(f"❌ Challenge **{challenge_id}** not found.")
            return

        updates = []
        params = []
        
        if points is not None: updates.append("points = ?"); params.append(points)
        if flag is not None: updates.append("flag_text = ?"); params.append(flag)
        if category is not None: updates.append("category = ?"); params.append(category)
        if image_url is not None: updates.append("image_url = ?"); params.append(image_url)
        if description is not None: updates.append("description = ?"); params.append(description)
        if connection_info is not None: updates.append("connection_info = ?"); params.append(connection_info)
        
        now = datetime.now()
        if start_time:
            try:
                dt = datetime.strptime(start_time, "%d/%m %H:%M").replace(year=now.year)
                updates.append("start_time = ?"); params.append(int(dt.timestamp()))
            except ValueError:
                await interaction.followup.send("❌ Invalid `start_time` format! Use `DD/MM HH:MM`.")
                return

        if end_time:
            try:
                dt = datetime.strptime(end_time, "%d/%m %H:%M").replace(year=now.year)
                updates.append("end_time = ?"); params.append(int(dt.timestamp()))
            except ValueError:
                await interaction.followup.send("❌ Invalid `end_time` format! Use `DD/MM HH:MM`.")
                return

        if not updates and not new_id:
            await interaction.followup.send("⚠️ No changes provided.")
            return

        try:
            # 1. Handle Rename
            current_id = challenge_id
            if new_id and new_id != challenge_id:
                await self.db.execute("UPDATE flags SET challenge_id = ? WHERE challenge_id = ?", (new_id, challenge_id))
                await self.db.execute("UPDATE solves SET challenge_id = ? WHERE challenge_id = ?", (new_id, challenge_id))
                await self.db.execute("UPDATE hints SET challenge_id = ? WHERE challenge_id = ?", (new_id, challenge_id))
                current_id = new_id

            # 2. Apply Other Updates
            if updates:
                params.append(current_id)
                await self.db.execute(f"UPDATE flags SET {', '.join(updates)} WHERE challenge_id = ?", tuple(params))
            
            await self.db.commit()

            # 3. Synchronize Visuals
            cog_player = self.bot.get_cog('Player')
            if points is not None and cog_player:
                await cog_player.update_leaderboard()
            
            # Update Live Embed if posted
            if cog_player:
                await cog_player.update_challenge_card(current_id)

            await interaction.followup.send(f"✅ **{challenge_id}** updated successfully" + (f" (Renamed to **{new_id}**)" if new_id else "."))
        except aiosqlite.IntegrityError:
            await interaction.followup.send(f"❌ Error: ID **{new_id}** is already in use!")
        except Exception as e:
            await interaction.followup.send(f"❌ Database Error: {e}")

    # --- 8. REVOKE SOLVE ---
    @app_commands.command(name="revoke", description="Remove a solve and its specific points (including bonuses)")
    @app_commands.default_permissions(administrator=True)
    async def revoke(self, interaction: discord.Interaction, member: discord.Member, challenge_id: str):
        # 1. Check if the solve exists
        async with self.db.execute("SELECT timestamp FROM solves WHERE user_id = ? AND challenge_id = ?", (member.id, challenge_id)) as cursor:
            solve_data = await cursor.fetchone()
        
        if not solve_data:
            await interaction.response.send_message(f"❌ {member.mention} has not solved **{challenge_id}**.", ephemeral=True)
            return
            
        timestamp = solve_data[0]
        
        # 2. Get Challenge Points
        async with self.db.execute("SELECT points FROM flags WHERE challenge_id = ?", (challenge_id,)) as cursor:
            flag_data = await cursor.fetchone()
        
        if not flag_data:
            await interaction.response.send_message(f"❌ Challenge **{challenge_id}** not found.", ephemeral=True)
            return
            
        base_points = flag_data[0]
        
        # 3. Calculate Rank
        async with self.db.execute("SELECT COUNT(*) FROM solves WHERE challenge_id = ? AND timestamp < ?", (challenge_id, timestamp)) as cursor:
            row = await cursor.fetchone()
            rank = row[0]
        
        bonus = BONUSES.get(rank, 0)
        deduction = base_points + bonus
        
        # 4. Remove Solve and Deduct Points
        await self.db.execute("DELETE FROM solves WHERE user_id = ? AND challenge_id = ?", (member.id, challenge_id))
        await self.db.execute("UPDATE scores SET points = points - ? WHERE user_id = ?", (deduction, member.id))
        await self.db.commit()

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
        await self.db.execute("INSERT OR IGNORE INTO banlist (user_id) VALUES (?)", (member.id,))
        await self.db.commit()
        await interaction.response.send_message(f"🚫 **BANNED!** {member.mention} has been disqualified from the CTF.", ephemeral=True)

    # --- 10. UNBAN USER ---
    @app_commands.command(name="unban_user", description="Re-enable a user to submit flags")
    @app_commands.default_permissions(administrator=True)
    async def unban_user(self, interaction: discord.Interaction, member: discord.Member):
        async with self.db.execute("DELETE FROM banlist WHERE user_id = ?", (member.id,)) as cursor:
            rows = cursor.rowcount
        await self.db.commit()
        
        if rows > 0:
            await interaction.response.send_message(f"✅ **UNBANNED!** {member.mention} can now submit flags again.", ephemeral=True)
        else:
            await interaction.response.send_message(f"⚠️ {member.mention} was not banned.", ephemeral=True)

    # --- 11. EXPORT DATABASE ---
    @app_commands.command(name="export", description="Download the current database backup")
    @app_commands.default_permissions(administrator=True)
    async def export_db(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        if os.path.exists('bot.db'):
            try:
                await interaction.followup.send(
                    content="📦 **Database Backup:**\nSave this file to your computer to prevent data loss.",
                    file=discord.File('bot.db')
                )
            except Exception as e:
                await interaction.followup.send(f"❌ Upload failed: {e}")
        else:
            await interaction.followup.send("❌ Database file 'bot.db' not found.")

    # --- 12. IMPORT DATABASE ---
    @app_commands.command(name="import", description="⚠️ Overwrite the database with a backup file")
    @app_commands.describe(file="Upload the bot.db file here")
    @app_commands.default_permissions(administrator=True)
    async def import_db(self, interaction: discord.Interaction, file: discord.Attachment):
        await interaction.response.defer(ephemeral=True)
        
        if not file.filename.endswith(".db"):
            await interaction.followup.send("❌ Invalid file. Please upload a `.db` file.")
            return
        
        try:
            # 1. Close current connection
            await self.db.close()
            
            # 2. Overwrite the file
            await file.save("bot.db")
            
            # 3. Re-open connection
            self.bot.db = await aiosqlite.connect('bot.db')
            self.bot.db.row_factory = aiosqlite.Row
            await self.bot.db.execute("PRAGMA journal_mode=WAL;")
            
            # Sync self.db and other cogs
            self.db = self.bot.db
            for cog in self.bot.cogs.values():
                if hasattr(cog, 'db'):
                    cog.db = self.bot.db
            
            # 4. Force leaderboard refresh
            cog = self.bot.get_cog('Player')
            if cog: await cog.update_leaderboard()

            await interaction.followup.send("✅ **Database Restored!**\nConnection successfully swapped to the new backup.")
        except Exception as e:
            # Emergency recovery attempt
            try: 
                self.bot.db = await aiosqlite.connect('bot.db')
                self.bot.db.row_factory = aiosqlite.Row
                self.db = self.bot.db
            except:
                pass
            await interaction.followup.send(f"❌ Failed to import: {e}")

async def setup(bot):
    await bot.add_cog(Admin(bot))
