import discord
from discord import app_commands
from discord.ext import commands, tasks
import aiosqlite
import os
import time
import functools
from PIL import Image, ImageDraw, ImageFont, ImageOps
from io import BytesIO

# --- CONFIGURATION & CONSTANTS ---
BONUSES = {0: 50, 1: 25, 2: 10}
COOLDOWNS = {} 

async def get_config_id(db, key):
    """Helper to fetch channel/role IDs from the persistent database."""
    try:
        async with db.execute("SELECT value FROM config WHERE key = ?", (key,)) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else None
    except Exception:
        return None

# --- SOLVERS LIST PAGINATION VIEW ---
class SolversView(discord.ui.View):
    def __init__(self, challenge_id, guild, base_points, db, page=0):
        super().__init__(timeout=300)
        self.challenge_id = challenge_id
        self.guild = guild
        self.base_points = base_points
        self.db = db
        self.page = page
    
    async def get_solvers_data(self):
        async with self.db.execute("SELECT user_id FROM solves WHERE challenge_id = ? ORDER BY timestamp ASC", (self.challenge_id,)) as cursor:
            return await cursor.fetchall()
    
    async def create_embed(self, solvers=None):
        if solvers is None:
            solvers = await self.get_solvers_data()
        total_solvers = len(solvers)
        per_page = 10
        start_idx = self.page * per_page
        end_idx = start_idx + per_page
        page_solvers = solvers[start_idx:end_idx]
        
        embed = discord.Embed(
            title=f"🏆 Solvers List: {self.challenge_id}",
            description=f"**Total Solves:** {total_solvers}\n**Page:** {self.page + 1}/{max(1, (total_solvers + per_page - 1) // per_page)}",
            color=discord.Color.blue()
        )
        
        if not page_solvers:
            embed.add_field(name="No Solvers", value="No one has solved this challenge yet.", inline=False)
            return embed
        
        solvers_text = ""
        for i, (user_id,) in enumerate(page_solvers):
            actual_rank = start_idx + i
            member = self.guild.get_member(user_id)
            name = member.display_name if member else "Unknown Agent"
            bonus = BONUSES.get(actual_rank, 0)
            total_pts = self.base_points + bonus
            
            if actual_rank == 0:
                icon = "🩸"
            elif actual_rank == 1:
                icon = "🥈"
            elif actual_rank == 2:
                icon = "🥉"
            else:
                icon = f"#{actual_rank + 1}"
            
            solvers_text += f"{icon} **{name}** — +{total_pts} pts"
            if bonus > 0:
                solvers_text += f" *(+{bonus} bonus)*"
            solvers_text += "\n"
        
        embed.add_field(name="👥 Solvers", value=solvers_text, inline=False)
        embed.set_footer(text="Message expires in 5 minutes")
        return embed
    
    def update_buttons(self, total_pages):
        self.children[0].disabled = (self.page == 0)
        self.children[1].disabled = (self.page >= total_pages - 1)

    async def update_view(self, interaction: discord.Interaction):
        solvers = await self.get_solvers_data()
        total_pages = max(1, (len(solvers) + 9) // 10)
        self.children[0].disabled = (self.page == 0)
        self.children[1].disabled = (self.page >= total_pages - 1)
        embed = await self.create_embed(solvers)
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.gray, disabled=True)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page -= 1
        await self.update_view(interaction)
    
    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.gray)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page += 1
        await self.update_view(interaction)
    
    @discord.ui.button(label="🔄 Refresh", style=discord.ButtonStyle.green)
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update_view(interaction)

# --- HINT SYSTEM ---
class HintSelect(discord.ui.Select):
    def __init__(self, hints, bot, user_id):
        self.bot = bot
        self.db = bot.db
        self.user_id = user_id
        options = [
            discord.SelectOption(label=f"Hint #{h_id} ({cost} pts)", value=str(h_id), description="Unlock/view hint")
            for h_id, text, cost in hints
        ]
        super().__init__(placeholder="💡 Select a hint...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        hint_id = int(self.values[0])
        async with self.db.execute("SELECT * FROM unlocked_hints WHERE user_id = ? AND hint_id = ?", (self.user_id, hint_id)) as cursor:
            if await cursor.fetchone():
                async with self.db.execute("SELECT hint_text FROM hints WHERE id = ?", (hint_id,)) as cursor_hint:
                    res = await cursor_hint.fetchone()
                    text = res[0]
                    await interaction.response.send_message(f"🔓 **Hint:** ||{text}||", ephemeral=True)
                    return

        async with self.db.execute("SELECT points FROM scores WHERE user_id = ?", (self.user_id,)) as cursor:
            res = await cursor.fetchone()
            current_points = res[0] if res else 0
        
        async with self.db.execute("SELECT cost, hint_text FROM hints WHERE id = ?", (hint_id,)) as cursor:
            hint_data = await cursor.fetchone()
        
        if not hint_data:
            await interaction.response.send_message("❌ Error: Hint not found.", ephemeral=True)
            return
            
        cost, text = hint_data
        
        if current_points < cost:
            await interaction.response.send_message(f"❌ You need {cost} pts (Balance: {current_points})", ephemeral=True)
            return

        try:
            await self.db.execute("INSERT INTO unlocked_hints (user_id, hint_id) VALUES (?, ?)", (self.user_id, hint_id))
            await self.db.execute("UPDATE scores SET points = points - ? WHERE user_id = ?", (cost, self.user_id))
            await self.db.commit()
        except aiosqlite.IntegrityError:
            await interaction.response.send_message("⚠️ You already unlocked this hint!", ephemeral=True)
            return

        cog = self.bot.get_cog('Player')
        if cog: await cog.update_leaderboard()
        
        await interaction.response.send_message(f"✅ **Purchased!** (-{cost} pts)\n🔓 **Hint:** ||{text}||", ephemeral=True)

class HintView(discord.ui.View):
    def __init__(self, hints, bot, user_id):
        super().__init__()
        self.add_item(HintSelect(hints, bot, user_id))

# --- SUBMISSION SYSTEM ---
class SubmissionModal(discord.ui.Modal, title="cyberBOT: Flag Submission"):
    flag_input = discord.ui.TextInput(label="Enter Flag", placeholder="SGCTF{...}")

    def __init__(self, challenge_id, bot):
        super().__init__()
        self.challenge_id = challenge_id
        self.bot = bot
        self.db = bot.db

    async def on_submit(self, interaction: discord.Interaction):
        user_flag = self.flag_input.value.strip()
        user_id = interaction.user.id
        current_time = time.time()

        # 0. Check Banlist
        async with self.db.execute("SELECT * FROM banlist WHERE user_id = ?", (user_id,)) as cursor:
            if await cursor.fetchone():
                await interaction.response.send_message("🚫 **ACCESS DENIED.** You have been disqualified.", ephemeral=True)
                return

        # 0.1 Check Time Limit
        async with self.db.execute("SELECT end_time FROM flags WHERE challenge_id = ?", (self.challenge_id,)) as cursor:
            data = await cursor.fetchone()
            if data and data[0] and int(current_time) > data[0]:
                await interaction.response.send_message("⏳ **Time limit exceeded.** Challenge closed.", ephemeral=True)
                return

        # 1. Cooldown Check
        if user_id in COOLDOWNS and current_time - COOLDOWNS[user_id] < 2:
            await interaction.response.send_message("⏳ Too fast! System cooling down.", ephemeral=True)
            return
        COOLDOWNS[user_id] = current_time

        # 2. Duplicate Solve Check
        async with self.db.execute("SELECT * FROM solves WHERE user_id = ? AND challenge_id = ?", (user_id, self.challenge_id)) as cursor:
            if await cursor.fetchone():
                await interaction.response.send_message("⚠️ Protocol error: Challenge already solved.", ephemeral=True)
                return

        async with self.db.execute("SELECT flag_text, points FROM flags WHERE challenge_id = ?", (self.challenge_id,)) as cursor:
            result = await cursor.fetchone()

        if not result:
            await interaction.response.send_message("❌ Error: Mission ID not found.", ephemeral=True)
            return

        correct_flag, base_points = result

        if user_flag == correct_flag:
            # COLLUSION CHECK
            async with self.db.execute("SELECT user_id, timestamp FROM solves WHERE challenge_id = ? ORDER BY timestamp DESC LIMIT 1", (self.challenge_id,)) as cursor:
                last_solve = await cursor.fetchone()
            
            suspicion_msg = None
            if last_solve:
                last_solver_id, last_ts = last_solve
                time_diff = current_time - last_ts
                if last_solver_id != user_id and time_diff <= 60:
                    suspicion_msg = f"🚨 **COLLUSION DETECTED**\nSolved **{self.challenge_id}** within **{time_diff:.1f}s** of <@{last_solver_id}>."

            try:
                await self.db.execute("INSERT INTO solves (user_id, challenge_id, timestamp) VALUES (?, ?, ?)", (user_id, self.challenge_id, current_time))
                async with self.db.execute("SELECT COUNT(*) FROM solves WHERE challenge_id = ?", (self.challenge_id,)) as cursor:
                    res = await cursor.fetchone()
                    solve_index = res[0] - 1 
                
                bonus = BONUSES.get(solve_index, 0)
                total_points = base_points + bonus

                await self.db.execute("INSERT OR IGNORE INTO scores (user_id, username, points) VALUES (?, ?, 0)", (user_id, interaction.user.name))
                await self.db.execute("UPDATE scores SET points = points + ? WHERE user_id = ?", (total_points, user_id))
                
                async with self.db.execute("SELECT points FROM scores WHERE user_id = ?", (user_id,)) as cursor:
                    res = await cursor.fetchone()
                    new_total_score = res[0]
                
                # ROLE UPDATES
                role_msg = ""
                if interaction.guild:
                    member = interaction.guild.get_member(user_id)
                    if member:
                        rank_map = {}
                        async with self.db.execute("SELECT role_id, points FROM role_rewards") as cursor:
                            async for row in cursor: rank_map[row[1]] = row[0]

                        assigned_roles = []
                        for threshold, role_id in rank_map.items():
                            if new_total_score >= threshold:
                                role = interaction.guild.get_role(role_id)
                                if role and role not in member.roles:
                                    try:
                                        await member.add_roles(role)
                                        assigned_roles.append(role.name)
                                    except Exception:
                                        pass
                        if assigned_roles:
                            role_msg = f"\n🆙 **Promoted!** New clearance: {', '.join(assigned_roles)}"

                await self.db.commit()

                msg = f"🎉 **Correct!** +{total_points} pts"
                if bonus > 0: msg += f" (First Blood: +{bonus}!)"
                msg += role_msg
                await interaction.response.send_message(msg, ephemeral=True)

                # LOGGING SUCCESSFUL SUBMISSION
                log_channel_id = await get_config_id(self.db, "channel_challenge_logs")
                if log_channel_id:
                    log_channel = self.bot.get_channel(int(log_channel_id))
                    if log_channel:
                        desc = f"**User:** {interaction.user.mention}\n**Challenge:** {self.challenge_id}\n**Points:** {total_points}"
                        color = discord.Color.green()
                        if suspicion_msg:
                            desc += f"\n\n{suspicion_msg}"
                            color = discord.Color.orange()
                        embed = discord.Embed(title="✅ Flag Captured", description=desc, color=color)
                        await log_channel.send(embed=embed)
                
                cog = self.bot.get_cog('Player')
                if cog: 
                    await cog.update_leaderboard()
                    await cog.update_challenge_card(self.challenge_id)
            except aiosqlite.IntegrityError:
                await interaction.response.send_message("⚠️ Duplicate solve detected.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ **Wrong Flag!** Access denied.", ephemeral=True)

            # LOGGING FAILED SUBMISSION
            wrong_log_id = await get_config_id(self.db, "channel_wrong_submissions")
            if wrong_log_id:
                wrong_channel = self.bot.get_channel(int(wrong_log_id))
                if wrong_channel:
                    desc = f"**User:** {interaction.user.mention}\n**Challenge:** {self.challenge_id}\n**Input:** `{user_flag}`"
                    embed = discord.Embed(title="❌ Wrong Flag Submission", description=desc, color=discord.Color.red())
                    await wrong_channel.send(embed=embed)

# --- LEADERBOARD PAGINATION VIEW ---
class LeaderboardView(discord.ui.View):
    def __init__(self, bot, db, page=0):
        super().__init__(timeout=None)
        self.bot = bot
        self.db = db
        self.page = page

    async def create_embed(self):
        # MILLISECOND TIE-BREAKING: ORDER BY points DESC, then achievement time ASC (NULLS LAST)
        async with self.db.execute("""
            SELECT s.user_id, s.username, s.points 
            FROM scores s
            LEFT JOIN (
                SELECT user_id, MAX(timestamp) as last_ts 
                FROM solves 
                GROUP BY user_id
            ) t ON s.user_id = t.user_id
            ORDER BY s.points DESC, (t.last_ts IS NULL) ASC, t.last_ts ASC
        """) as cursor:
            all_players = await cursor.fetchall()

        per_page = 10
        total_players = len(all_players)
        total_pages = max(1, (total_players + per_page - 1) // per_page)
        self.page = max(0, min(self.page, total_pages - 1))
        
        start_idx = self.page * per_page
        page_players = all_players[start_idx : start_idx + per_page]

        embed = discord.Embed(title="🏆 cyberBOT GLOBAL STANDINGS", color=0xFFD700)
        embed.set_footer(text=f"Page {self.page + 1}/{total_pages} • Refreshes periodically")

        desc = ""
        guild_id_env = os.getenv('GUILD_ID')
        guild = self.bot.get_guild(int(guild_id_env)) if guild_id_env else None

        for i, (uid, db_username, points) in enumerate(page_players, 1):
            actual_rank = start_idx + i
            member = guild.get_member(uid) if guild else None
            final_name = member.display_name if member else db_username
            
            if actual_rank == 1: icon = "👑"
            elif actual_rank == 2: icon = "🥈"
            elif actual_rank == 3: icon = "🥉"
            else: icon = f"**#{actual_rank}**"
            
            desc += f"{icon} • **{final_name}** — `{points} pts`\n"

        embed.description = desc if desc else "No operational data available."
        return embed, total_pages

    def update_buttons(self, total_pages):
        self.children[0].disabled = (self.page == 0)
        self.children[1].disabled = (self.page >= total_pages - 1)

    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.gray)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page -= 1
        embed, total_pages = await self.create_embed()
        self.update_buttons(total_pages)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.gray)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page += 1
        embed, total_pages = await self.create_embed()
        self.update_buttons(total_pages)
        await interaction.response.edit_message(embed=embed, view=self)

# --- PLAYER COG ---
class Player(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.leaderboard_refresh.start()
        
        try:
            self.title_font = ImageFont.truetype("font.ttf", 65)
            self.badge_font = ImageFont.truetype("font.ttf", 30)
            self.label_font = ImageFont.truetype("font.ttf", 25)
            self.value_font = ImageFont.truetype("font.ttf", 55)
        except Exception:
            self.title_font = self.badge_font = self.label_font = self.value_font = ImageFont.load_default()

    def cog_unload(self):
        self.leaderboard_refresh.cancel()

    @tasks.loop(minutes=2)
    async def leaderboard_refresh(self):
        await self.update_leaderboard()

    @leaderboard_refresh.before_loop
    async def before_leaderboard_refresh(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type == discord.InteractionType.component:
            custom_id = interaction.data.get("custom_id", "")
            if custom_id.startswith("submit:"):
                cid = custom_id.split(":")[1]
                await interaction.response.send_modal(SubmissionModal(cid, self.bot))
            elif custom_id.startswith("hints:"):
                cid = custom_id.split(":")[1]
                async with self.db.execute("SELECT id, hint_text, cost FROM hints WHERE challenge_id = ?", (cid,)) as cursor:
                    hints = await cursor.fetchall()
                if not hints: await interaction.response.send_message("🤷‍♂️ No hints available for this mission.", ephemeral=True)
                else: await interaction.response.send_message(view=HintView(hints, self.bot, interaction.user.id), ephemeral=True)
            elif custom_id.startswith("solvers:"):
                cid = custom_id.split(":")[1]
                async with self.db.execute("SELECT points FROM flags WHERE challenge_id = ?", (cid,)) as cursor:
                    res = await cursor.fetchone()
                if not res: return
                view = SolversView(cid, interaction.guild, res[0], self.db)
                solvers = await view.get_solvers_data()
                embed = await view.create_embed(solvers)
                view.update_buttons(max(1, (len(solvers) + 9) // 10))
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    def draw_profile_card(self, user, rank, points, solves, avatar_bytes):
        width, height = 900, 350
        bg_color = (15, 15, 20)  
        try:
            rank_num = int(rank.replace("#", ""))
        except:
            rank_num = 999 

        primary = (0, 255, 230); fill_color = (0, 40, 40); b_text = (200, 255, 255); role = "OPERATIVE"
        if rank_num == 1: primary = (255, 215, 0); fill_color = (40, 30, 0); b_text = (255, 230, 150); role = "CHAMPION"
        elif rank_num == 2: primary = (229, 228, 226); fill_color = (45, 45, 50); b_text = (255, 255, 255); role = "VANGUARD"
        elif rank_num == 3: primary = (205, 127, 50); fill_color = (40, 20, 10); b_text = (255, 200, 180); role = "CHALLENGER"
        elif 4 <= rank_num <= 10: primary = (220, 20, 60); fill_color = (50, 10, 15); b_text = (255, 200, 200); role = "SENTINEL"
        elif points == 0: primary = (100, 100, 100); fill_color = (30, 30, 35); b_text = (200, 200, 200); role = "RECRUIT"

        with Image.new("RGBA", (width, height), bg_color) as card:
            draw = ImageDraw.Draw(card)
            for x in range(0, width, 40): draw.line([(x, 0), (x, height)], fill=(25, 30, 35), width=1)
            for y in range(0, height, 40): draw.line([(0, y), (width, y)], fill=(25, 30, 35), width=1)
            blen, bw = 100, 6
            draw.line([(0, 0), (blen, 0)], fill=primary, width=bw); draw.line([(0, 0), (0, blen)], fill=primary, width=bw)
            draw.line([(width, height), (width-blen, height)], fill=primary, width=bw); draw.line([(width, height), (width, height-blen)], fill=primary, width=bw)

            if avatar_bytes:
                try:
                    with BytesIO(avatar_bytes) as av_buf:
                        with Image.open(av_buf) as av_raw:
                            av_raw.thumbnail((200, 200), Image.Resampling.LANCZOS) 
                            with av_raw.convert("RGBA") as avatar:
                                with Image.new("L", avatar.size, 0) as mask:
                                    ImageDraw.Draw(mask).ellipse((0, 0, avatar.size[0], avatar.size[1]), fill=255)
                                    with ImageOps.fit(avatar, mask.size, centering=(0.5, 0.5)) as output:
                                        output.putalpha(mask); card.paste(output, (50, 75), output)
                except Exception:
                    pass
            
            draw.ellipse((50, 75, 250, 275), outline=primary, width=4)
            name_text = user.display_name.upper()
            draw.text((300, 40), name_text, fill="white", font=self.title_font)
            
            bx, by, bh, cut = 300, 120, 45, 12
            bw_val = draw.textbbox((0, 0), role, font=self.badge_font)[2] + 70
            poly = [(bx+cut, by), (bx+bw_val-cut, by), (bx+bw_val, by+cut), (bx+bw_val, by+bh-cut), (bx+bw_val-cut, by+bh), (bx+cut, by+bh), (bx, by+bh-cut), (bx, by+cut)]
            draw.polygon(poly, fill=fill_color, outline=primary, width=2)
            draw.text((bx+50, by+4), role, fill=b_text, font=self.badge_font)

            def d_stat(x, y, lab, val):
                sw, sh, c = 170, 110, 10
                p = [(x+c, y), (x+sw-c, y), (x+sw, y+c), (x+sw, y+sh-c), (x+sw-c, y+sh), (x+c, y+sh), (x, y+sh-c), (x, y+c)]
                draw.polygon(p, fill=(20, 25, 30), outline=primary, width=2)
                draw.text((x+15, y+10), lab, fill=primary, font=self.label_font)
                draw.text((x+15, y+45), str(val), fill="white", font=self.value_font)

            d_stat(300, 190, "RANK", rank); d_stat(490, 190, "SCORE", points); d_stat(680, 190, "FLAGS", solves)
            buf = BytesIO(); card.save(buf, format="PNG", optimize=True); buf.seek(0); return buf

    @app_commands.command(name="help", description="Protocol manual for Agents and Admins")
    async def help(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        # --- AGENT COMMANDS ---
        agent_manual = (
            "🛡️ **`/profile [member]`**\n"
            "↳ Generates your high-res Agent ID card. Displays current Rank, total Score, and solve count. Mention another member to inspect their stats.\n\n"
            "🏆 **`/leaderboard`**\n"
            "↳ Opens the global standing interactive menu with ◀ ▶ buttons. Standings are sorted by points and millisecond-accurate solve times.\n\n"
            "📚 **`/help`**\n"
            "↳ Accesses this complete operational manual for all system protocols.\n\n"
            "🚩 **Flag Submission (Button)**\n"
            "↳ Click 'Submit Flag' on any active mission post to enter the capture string. (Case-sensitive, 2s anti-spam cooldown).\n\n"
            "💡 **Hint Acquisition (Button)**\n"
            "↳ Click 'Hints' on a mission. Unlocking costs points. Hints are permanently stored privately for you."
        )
        
        embed = discord.Embed(
            title="📚 cyberBOT: COMPLETE FIELD MANUAL", 
            description="Operational protocols for the high-performance CTF network.", 
            color=discord.Color.from_rgb(0, 71, 171)
        )
        embed.add_field(name="🕵️ AGENT OPERATIONS (Available to All)", value=agent_manual, inline=False)

        # --- ADMINISTRATOR COMMANDS ---
        if interaction.user.guild_permissions.administrator:
            setup_manual = (
                "⚙️ **`/setup`**\n↳ Links cyberBOT to your server channels (Leaderboard, Logs, General) and designates the Champion role.\n\n"
                "🆙 **`/set_rank_role [role] [pts]`**\n↳ Defines a dynamic point milestone. cyberBOT will auto-promote players as they reach these scores.\n\n"
                "❌ **`/remove_rank_role [role]`**\n↳ Deletes a specific rank milestone from the auto-promotion engine.\n\n"
                "📋 **`/list_rank_roles`**\n↳ Displays all currently configured point requirements and their associated roles.\n\n"
                "📦 **`/export`**\n↳ Generates and sends a downloadable `bot.db` file for local backup.\n\n"
                "📥 **`/import [file]`**\n↳ Live-swaps the current database with a backup file. Zero-downtime restoration.\n\n"
                "🔄 **`/reset_config`**\n↳ Wipes only the channel and role settings, leaving player data intact."
            )
            
            mission_manual = (
                "📝 **`/create`**\n↳ Registers a new mission ID, point value, flag, and category in draft mode (hidden from players).\n\n"
                "📅 **`/post`**\n↳ Publishes a mission immediately or schedules it. Supports file attachments and custom deadlines.\n\n"
                "🛠️ **`/edit`**\n↳ Modifies any mission attribute (Renaming ID, changing points, flag text, or updating scheduling times).\n\n"
                "🗑️ **`/delete`**\n↳ Purges a mission. **Recursive Logic:** Automatically refunds points to every player who bought hints for it.\n\n"
                "📋 **`/list`**\n↳ Displays a summary of all registered missions and their current status (Posted vs. Draft).\n\n"
                "🔐 **`/show [id]`**\n↳ Reveals all hidden data for a specific mission, including the plain-text capture flag."
            )
            
            maint_manual = (
                "🩸 **`/revoke [member] [id]`**\n↳ Removes a solve record. Deducts base points and any First Blood bonuses earned by the agent.\n\n"
                "💡 **`/add_hint [id] [text] [cost]`**\n↳ Attaches a purchaseable clue to a mission. Updates live Discord posts in real-time.\n\n"
                "❌ **`/remove_hint [hint_id]`**\n↳ Deletes a clue. **Economy Logic:** Instantly refunds the cost to every single player who bought it.\n\n"
                "🚫 **`/ban_user [member]`**\n↳ Blacklists an agent. Prevents all flag submissions and hint purchases.\n\n"
                "✅ **`/unban_user [member]`**\n↳ Restores full network access to a previously disqualified agent.\n\n"
                "☢️ **`/wipe_all`**\n↳ **NUCLEAR OPTION:** Wipes all players, scores, missions, and local file storage for a fresh season."
            )

            embed.add_field(name="⚙️ SYSTEM & RANK SETUP", value=setup_manual, inline=False)
            embed.add_field(name="🎯 MISSION CONTROL", value=mission_manual, inline=False)
            embed.add_field(name="🔧 MAINTENANCE & RECOVERY", value=maint_manual, inline=False)
            embed.set_footer(text="Admin permissions detected. Control cyberBOT with extreme caution.")
        else:
            embed.set_footer(text="cyberBOT is monitoring the network. Capture the flag, Agent.")

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="profile", description="View agent ID card")
    async def profile(self, interaction: discord.Interaction, member: discord.Member = None):
        await interaction.response.defer()
        target = member or interaction.user
        async with self.db.execute("SELECT s.points, t.last_ts FROM scores s LEFT JOIN (SELECT user_id, MAX(timestamp) as last_ts FROM solves GROUP BY user_id) t ON s.user_id = t.user_id WHERE s.user_id = ?", (target.id,)) as cursor:
            row = await cursor.fetchone()
        
        if row:
            pts, lts = row
            async with self.db.execute("SELECT COUNT(*) FROM scores s LEFT JOIN (SELECT user_id, MAX(timestamp) as ts FROM solves GROUP BY user_id) t ON s.user_id = t.user_id WHERE s.points > ? OR (s.points = ? AND IFNULL(t.ts, 9999999999) < IFNULL(?, 9999999999))", (pts, pts, lts)) as cursor:
                res = await cursor.fetchone(); rank = f"#{res[0] + 1}"
        else: pts = 0; rank = "N/A"

        async with self.db.execute("SELECT COUNT(*) FROM solves WHERE user_id = ?", (target.id,)) as cursor:
            count = (await cursor.fetchone())[0]

        av_bytes = await target.avatar.read() if target.avatar else None
        func = functools.partial(self.draw_profile_card, target, rank, pts, count, av_bytes)
        buf = await self.bot.loop.run_in_executor(None, func)
        await interaction.followup.send(file=discord.File(fp=buf, filename="profile.png"))
        buf.close()

    @app_commands.command(name="leaderboard", description="View global standings")
    async def leaderboard(self, interaction: discord.Interaction):
        view = LeaderboardView(self.bot, self.db, 0)
        embed, total = await view.create_embed()
        view.update_buttons(total)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def update_leaderboard(self):
        lbc_id = await get_config_id(self.db, 'channel_leaderboard')
        if not lbc_id: return
        chan = self.bot.get_channel(lbc_id)
        if not chan: return

        async with self.db.execute("SELECT s.user_id FROM scores s LEFT JOIN (SELECT user_id, MAX(timestamp) as lts FROM solves GROUP BY user_id) t ON s.user_id = t.user_id ORDER BY s.points DESC, (t.lts IS NULL) ASC, t.lts ASC LIMIT 1") as cursor:
            top = await cursor.fetchone()

        champ_id = await get_config_id(self.db, 'role_champion')
        if top and champ_id:
            role = chan.guild.get_role(champ_id)
            if role:
                new_c = chan.guild.get_member(top[0])
                if new_c and role not in new_c.roles:
                    for old in role.members: await old.remove_roles(role)
                    await new_c.add_roles(role)

        view = LeaderboardView(self.bot, self.db, 0)
        embed, total = await view.create_embed()
        view.update_buttons(total)
        async with self.db.execute("SELECT value FROM config WHERE key = 'lb_msg_id'") as cursor:
            row = await cursor.fetchone()
        
        if row:
            try:
                msg = await chan.fetch_message(row[0])
                await msg.edit(embed=embed, view=view)
            except:
                row = None
        if not row:
            msg = await chan.send(embed=embed, view=view)
            await self.db.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('lb_msg_id', ?)", (msg.id,))
            await self.db.commit()

    async def update_challenge_card(self, cid):
        async with self.db.execute("SELECT * FROM flags WHERE challenge_id = ?", (cid,)) as cursor:
            d = await cursor.fetchone()
        if not d or not d['msg_id']: return
        
        async with self.db.execute("SELECT user_id FROM solves WHERE challenge_id = ? ORDER BY timestamp ASC", (cid,)) as cursor:
            solves = await cursor.fetchall()
        async with self.db.execute("SELECT COUNT(*) FROM hints WHERE challenge_id = ?", (cid,)) as cursor:
            h_count = (await cursor.fetchone())[0]

        try:
            chan = self.bot.get_channel(d['channel_id'])
            msg = await chan.fetch_message(d['msg_id'])
            desc = f"**Objective:**\n```text\n{d['description'] or 'Solve it.'}\n```"
            if d['connection_info']: desc += f"\n**📡 Connection:**\n```text\n{d['connection_info']}\n```"
            
            emb = discord.Embed(title=f"🛡️ MISSION: {cid}", description=desc, color=discord.Color.red())
            emb.add_field(name="💰 Bounty", value=f"**{d['points']} Pts**", inline=True)
            emb.add_field(name="📂 Category", value=f"**{d['category']}**", inline=True)
            if d['end_time'] and int(time.time()) >= d['end_time']: emb.add_field(name="⏳ Time Left", value="**🔴 Expired**", inline=True)
            elif d['end_time']: emb.add_field(name="⏳ Time Left", value=f"<t:{d['end_time']}:R>", inline=True)
            
            fb = "*Waiting...*"
            if solves:
                u = chan.guild.get_member(solves[0][0])
                fb = f"🥇 **{u.display_name if u else 'Agent'}** (+{d['points'] + BONUSES.get(0, 0)})"
            emb.add_field(name="🩸 First Blood", value=fb, inline=False)
            if d['image_url']: emb.set_image(url=d['image_url'])

            view = discord.ui.View(timeout=None)
            btn = discord.ui.Button(label="Submit Flag", style=discord.ButtonStyle.green, emoji="🚩", custom_id=f"submit:{cid}")
            if d['end_time'] and int(time.time()) >= d['end_time']: btn.disabled = True; btn.style = discord.ButtonStyle.danger; btn.label = "Closed"
            view.add_item(btn)
            if h_count: view.add_item(discord.ui.Button(label="Hints", style=discord.ButtonStyle.gray, emoji="💡", custom_id=f"hints:{cid}"))
            if solves: view.add_item(discord.ui.Button(label="Solvers", style=discord.ButtonStyle.blurple, emoji="👥", custom_id=f"solvers:{cid}"))
            await msg.edit(embed=emb, view=view)
        except Exception:
            pass

async def setup(bot):
    await bot.add_cog(Player(bot))
