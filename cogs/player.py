import discord
from discord import app_commands
from discord.ext import commands, tasks
import sqlite3
import time
import gc
import functools
from PIL import Image, ImageDraw, ImageFont, ImageOps
from io import BytesIO

BONUSES = {0: 50, 1: 25, 2: 10}
COOLDOWNS = {} 

def get_config_id(key):
    """Helper to fetch channel/role IDs from DB"""
    try:
        conn = sqlite3.connect('ctf_data.db')
        c = conn.cursor()
        c.execute("SELECT value FROM config WHERE key = ?", (key,))
        result = c.fetchone()
        conn.close()
        return result[0] if result else None
    except:
        return None

# --- HINT SYSTEM ---
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
        
        c.execute("SELECT * FROM unlocked_hints WHERE user_id = ? AND hint_id = ?", (self.user_id, hint_id))
        if c.fetchone():
            c.execute("SELECT hint_text FROM hints WHERE id = ?", (hint_id,))
            text = c.fetchone()[0]
            await interaction.response.send_message(f"🔓 **Hint:** ||{text}||", ephemeral=True)
            conn.close()
            return

        c.execute("SELECT points FROM scores WHERE user_id = ?", (self.user_id,))
        res = c.fetchone()
        current_points = res[0] if res else 0
        
        c.execute("SELECT cost, hint_text FROM hints WHERE id = ?", (hint_id,))
        hint_data = c.fetchone()
        
        if not hint_data:
            await interaction.response.send_message("❌ Error: Hint not found.", ephemeral=True)
            conn.close()
            return
            
        cost, text = hint_data
        
        try:
            c.execute("INSERT INTO unlocked_hints (user_id, hint_id) VALUES (?, ?)", (self.user_id, hint_id))
        except sqlite3.IntegrityError:
            conn.close()
            await interaction.response.send_message("⚠️ You already unlocked this hint!", ephemeral=True)
            return

        c.execute("UPDATE scores SET points = points - ? WHERE user_id = ? AND points >= ?", (cost, self.user_id, cost))
        
        if c.rowcount == 0:
            conn.rollback()
            conn.close()
            await interaction.response.send_message(f"❌ You need {cost} pts (Balance too low)", ephemeral=True)
            return

        conn.commit()
        conn.close()
        
        cog = self.bot.get_cog('Player')
        if cog: await cog.update_leaderboard()
        
        await interaction.response.send_message(f"✅ **Purchased!** (-{cost} pts)\n🔓 **Hint:** ||{text}||", ephemeral=True)

class HintView(discord.ui.View):
    def __init__(self, hints, bot, user_id):
        super().__init__()
        self.add_item(HintSelect(hints, bot, user_id))

# --- SUBMISSION SYSTEM ---
class SubmissionModal(discord.ui.Modal, title="Submit Flag"):
    flag_input = discord.ui.TextInput(label="Enter Flag", placeholder="SGCTF{...}")

    def __init__(self, challenge_id, bot):
        super().__init__()
        self.challenge_id = challenge_id
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        user_flag = self.flag_input.value.strip()
        user_id = interaction.user.id
        current_time = int(time.time())

        conn = sqlite3.connect('ctf_data.db')
        c = conn.cursor()
        
        # 0. Check Banlist
        c.execute("SELECT * FROM banlist WHERE user_id = ?", (user_id,))
        if c.fetchone():
            conn.close()
            await interaction.response.send_message("🚫 **ACCESS DENIED.** You have been disqualified.", ephemeral=True)
            return

        # 0.1 Check Time Limit (24 Hours)
        c.execute("SELECT posted_at FROM flags WHERE challenge_id = ?", (self.challenge_id,))
        data = c.fetchone()
        if data and data[0]:
            posted_at = data[0]
            # 24 hours in seconds = 86400
            if current_time > (posted_at + 86400):
                conn.close()
                await interaction.response.send_message("⏳ **Time limit exceeded**", ephemeral=True)
                return

        # 1. Cooldown Check
        if user_id in COOLDOWNS and current_time - COOLDOWNS[user_id] < 2:
            conn.close()
            await interaction.response.send_message("⏳ Too fast! Wait a second.", ephemeral=True)
            return
        COOLDOWNS[user_id] = current_time

        # 2. Duplicate Solve Check
        c.execute("SELECT * FROM solves WHERE user_id = ? AND challenge_id = ?", (user_id, self.challenge_id))
        if c.fetchone():
            conn.close()
            await interaction.response.send_message("⚠️ You already solved this!", ephemeral=True)
            return

        c.execute("SELECT flag_text, points FROM flags WHERE challenge_id = ?", (self.challenge_id,))
        result = c.fetchone()

        if not result:
            conn.close()
            await interaction.response.send_message("❌ Error: Challenge not found.", ephemeral=True)
            return

        correct_flag, base_points = result

        if user_flag == correct_flag:
            
            # --- 🕵️ FLAG SHARING SUSPICION CHECK ---
            c.execute("SELECT user_id, timestamp FROM solves WHERE challenge_id = ? ORDER BY timestamp DESC LIMIT 1", (self.challenge_id,))
            last_solve = c.fetchone()
            
            suspicion_msg = None
            if last_solve:
                last_solver_id, last_ts = last_solve
                try: last_ts = int(last_ts) 
                except: last_ts = 0

                time_diff = current_time - last_ts
                if last_solver_id != user_id and time_diff <= 60:
                     suspicion_msg = f"🚨 **POSSIBLE COLLUSION**\nUser solved **{self.challenge_id}** only **{time_diff}s** after <@{last_solver_id}>."
            # ---------------------------------------

            try:
                c.execute("INSERT INTO solves (user_id, challenge_id, timestamp) VALUES (?, ?, ?)", (user_id, self.challenge_id, current_time))
            except sqlite3.IntegrityError:
                conn.close()
                await interaction.response.send_message("⚠️ You already solved this!", ephemeral=True)
                return

            c.execute("SELECT COUNT(*) FROM solves WHERE challenge_id = ?", (self.challenge_id,))
            solve_index = c.fetchone()[0] - 1 
            bonus = BONUSES.get(solve_index, 0)
            total_points = base_points + bonus

            c.execute("INSERT OR IGNORE INTO scores (user_id, username, points) VALUES (?, ?, 0)", (user_id, interaction.user.name))
            c.execute("UPDATE scores SET points = points + ? WHERE user_id = ?", (total_points, user_id))
            
            c.execute("SELECT points FROM scores WHERE user_id = ?", (user_id,))
            new_total_score = c.fetchone()[0]
            
            # DYNAMIC ROLE ASSIGNMENT
            role_msg = ""
            if interaction.guild:
                member = interaction.guild.get_member(user_id)
                if member:
                    # Fetch Role IDs from Config
                    rank_1 = get_config_id('role_rank_1')
                    rank_2 = get_config_id('role_rank_2')
                    rank_3 = get_config_id('role_rank_3')

                    rank_map = {}
                    if rank_1: rank_map[2500] = rank_1
                    if rank_2: rank_map[6000] = rank_2
                    if rank_3: rank_map[9000] = rank_3

                    assigned_roles = []
                    for threshold, role_id in rank_map.items():
                        if new_total_score >= threshold:
                            role = interaction.guild.get_role(role_id)
                            if role and role not in member.roles:
                                try:
                                    await member.add_roles(role)
                                    assigned_roles.append(role.name)
                                except Exception as e:
                                    print(f"Failed to add role {role.name}: {e}")
                    
                    if assigned_roles:
                        role_msg = f"\n🆙 **Promoted!** You are now: {', '.join(assigned_roles)}"

            conn.commit()
            conn.close()

            msg = f"🎉 **Correct!** +{total_points} pts"
            if bonus > 0: msg += f" (First Blood: +{bonus}!)"
            msg += role_msg
            await interaction.response.send_message(msg, ephemeral=True)

            # LOGGING
            log_channel_id = get_config_id('channel_log')
            if log_channel_id:
                log_channel = self.bot.get_channel(log_channel_id)
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
        else:
            conn.close()
            await interaction.response.send_message("❌ **Wrong Flag!** Try again.", ephemeral=True)

# --- PLAYER COG ---
class Player(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.leaderboard_task.start()
        
        try:
            self.title_font = ImageFont.truetype("font.ttf", 65)
            self.badge_font = ImageFont.truetype("font.ttf", 30)
            self.label_font = ImageFont.truetype("font.ttf", 25)
            self.value_font = ImageFont.truetype("font.ttf", 55)
        except:
            self.title_font = ImageFont.load_default()
            self.badge_font = ImageFont.load_default()
            self.label_font = ImageFont.load_default()
            self.value_font = ImageFont.load_default()

    def cog_unload(self):
        self.leaderboard_task.cancel()

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type == discord.InteractionType.component:
            custom_id = interaction.data.get("custom_id", "")
            
            if custom_id.startswith("submit:"):
                challenge_id = custom_id.split(":")[1]
                await interaction.response.send_modal(SubmissionModal(challenge_id, self.bot))
            
            elif custom_id.startswith("hints:"):
                challenge_id = custom_id.split(":")[1]
                conn = sqlite3.connect('ctf_data.db')
                c = conn.cursor()
                c.execute("SELECT id, hint_text, cost FROM hints WHERE challenge_id = ?", (challenge_id,))
                hints = c.fetchall()
                conn.close()
                
                if not hints:
                    await interaction.response.send_message("🤷‍♂️ **No hints available** for this challenge.", ephemeral=True)
                else:
                    await interaction.response.send_message(view=HintView(hints, self.bot, interaction.user.id), ephemeral=True)

    def draw_profile_card(self, user, rank, points, solves, avatar_bytes, is_champion):
        width, height = 900, 350
        bg_color = (15, 15, 20)  
        
        if is_champion:
            primary = (255, 215, 0)     
            fill_color = (40, 30, 0)    
            text_color = "white"
            badge_text_color = (255, 230, 150) 
            role_name = "CHAMPION"
        else:
            primary = (0, 255, 230)     
            fill_color = (0, 40, 40)    
            text_color = "white"
            badge_text_color = (200, 255, 255) 
            role_name = "OPERATIVE"

        card = Image.new("RGBA", (width, height), bg_color)
        draw = ImageDraw.Draw(card)

        for x in range(0, width, 40):
            draw.line([(x, 0), (x, height)], fill=(25, 30, 35), width=1)
        for y in range(0, height, 40):
            draw.line([(0, y), (width, y)], fill=(25, 30, 35), width=1)

        border_len = 100
        border_width = 6
        draw.line([(0, 0), (border_len, 0)], fill=primary, width=border_width)
        draw.line([(0, 0), (0, border_len)], fill=primary, width=border_width)
        draw.line([(width, height), (width-border_len, height)], fill=primary, width=border_width)
        draw.line([(width, height), (width, height-border_len)], fill=primary, width=border_width)

        # --- RAM OPTIMIZATION: Handle Avatar Efficiently ---
        if avatar_bytes:
            try:
                # Use 'with' to ensure the raw file is closed immediately
                with Image.open(BytesIO(avatar_bytes)) as avatar_raw:
                    # 1. Resize immediately to 200x200 BEFORE converting colors
                    avatar_raw.thumbnail((200, 200), Image.Resampling.LANCZOS) 
                    
                    avatar = avatar_raw.convert("RGBA")
                    mask = Image.new("L", avatar.size, 0)
                    draw_mask = ImageDraw.Draw(mask)
                    draw_mask.ellipse((0, 0, avatar.size[0], avatar.size[1]), fill=255)
                    
                    output = ImageOps.fit(avatar, mask.size, centering=(0.5, 0.5))
                    output.putalpha(mask)
                    card.paste(output, (50, 75), output)
                
                draw.ellipse((50, 75, 250, 275), outline=primary, width=4)
                draw.arc((35, 60, 265, 290), start=140, end=220, fill=primary, width=2)
                draw.arc((35, 60, 265, 290), start=320, end=40, fill=primary, width=2)
            except Exception: pass
        # ---------------------------------------------------

        title_font = self.title_font
        badge_font = self.badge_font
        label_font = self.label_font
        value_font = self.value_font

        text_x = 300
        draw.text((text_x, 40), user.name.upper(), fill=text_color, font=title_font)
        
        badge_y = 120
        bbox = draw.textbbox((0, 0), role_name, font=badge_font)
        text_w = bbox[2] - bbox[0]
        badge_h = 45
        badge_w = text_w + 70 
        
        cut = 12
        bx, by = text_x, badge_y
        poly_points = [
            (bx + cut, by), (bx + badge_w - cut, by),
            (bx + badge_w, by + cut), (bx + badge_w, by + badge_h - cut),
            (bx + badge_w - cut, by + badge_h), (bx + cut, by + badge_h),
            (bx, by + badge_h - cut), (bx, by + cut)
        ]
        
        draw.polygon(poly_points, fill=fill_color, outline=primary, width=2)
        
        icon_x = bx + 25
        icon_y = by + (badge_h / 2)
        
        if is_champion:
            r = 7
            diamond = [
                (icon_x, icon_y - r - 2), 
                (icon_x + r + 2, icon_y), 
                (icon_x, icon_y + r + 2), 
                (icon_x - r - 2, icon_y)  
            ]
            draw.polygon(diamond, fill=primary)
        else:
            r = 6
            draw.ellipse((icon_x - r, icon_y - r, icon_x + r, icon_y + r), fill=primary)

        draw.text((bx + 50, by + 4), role_name, fill=badge_text_color, font=badge_font)

        def draw_stat_box(x, y, label, value):
            box_w, box_h = 170, 110
            bx, by = x, y
            cut = 10
            points = [
                (bx + cut, by), (bx + box_w - cut, by),
                (bx + box_w, by + cut), (bx + box_w, by + box_h - cut),
                (bx + box_w - cut, by + box_h), (bx + cut, by + box_h),
                (bx, by + box_h - cut), (bx, by + cut)
            ]
            draw.polygon(points, fill=(20, 25, 30), outline=primary, width=2)
            
            draw.text((x + 15, y + 10), label, fill=primary, font=label_font)
            draw.text((x + 15, y + 45), str(value), fill="white", font=value_font)

        draw_stat_box(300, 190, "RANK", rank)
        draw_stat_box(490, 190, "SCORE", points)
        draw_stat_box(680, 190, "FLAGS", solves)

        # --- RAM OPTIMIZATION: Clean up immediately ---
        buffer = BytesIO()
        card.save(buffer, format="PNG", optimize=True) # Optimize compression
        buffer.seek(0)
        
        # Close objects and Force Garbage Collection
        card.close()
        gc.collect() 
        # ---------------------------------------------
        
        return buffer

    # --- COMMANDS ---

    @app_commands.command(name="help", description="Show mission instructions")
    async def help(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        # 1. PLAYER COMMANDS
        player_desc = (
            "**`/profile`** - View Agent ID & Stats\n"
            "**`/help`** - View this Menu\n"
            "**Submit Flag** - Click 'Submit Flag' on challenge posts\n"
            "**Get Hint** - Click 'Get Hint' to buy clues\n"
        )
        embed = discord.Embed(title="📚 Field Manual", description="CTF Protocols", color=discord.Color.teal())
        embed.add_field(name="🕵️ Agent", value=player_desc, inline=False)

        # 2. ADMIN COMMANDS (Explicit Check)
        if interaction.user.guild_permissions.administrator:
            admin_desc = (
                "**`/setup`** - Configure Channels & Roles\n"
                "**`/reset_config`** - Wipe Configuration\n"
                "**`/create`** - Create new Challenge\n"
                "**`/edit`** - Modify existing Challenge\n"
                "**`/post`** - Publish Challenge to Channel\n"
                "**`/delete`** - Delete exsiting Challenge\n"
                "**`/list`** - List created and posted Challenges\n"
                "**`/revoke`** - Remove a solve of player (points)\n"
                "**`/show`** - Show all details of a Challenge\n"
                "**`/add_hint`** - Add/Edit Hints\n"
                "**`/leaderboard`** - Force Update Board\n"
                "**`/ban_user`** - Disqualify User\n"
                "**`/unban_user`** - Remove a player from Banlist\n"
                "**`/export`** - Download Database\n"
                "**`/import`** - Restore Database\n"
                "**`/wipe_all`** - RESET EVERYTHING\n"
            )
            embed.add_field(name="🛡️ Admin Controls", value=admin_desc, inline=False)
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="profile", description="View agent ID card")
    @app_commands.checks.cooldown(1, 60.0, key=lambda i: (i.guild_id, i.user.id))
    async def profile(self, interaction: discord.Interaction, member: discord.Member = None):
        await interaction.response.defer()
        target = member or interaction.user
        
        # 1. Check Champion Role dynamically
        is_champion = False
        champ_role_id = get_config_id('role_champion')
        if champ_role_id and any(r.id == champ_role_id for r in target.roles): 
            is_champion = True

        conn = sqlite3.connect('ctf_data.db')
        c = conn.cursor() 
        
        # 2. OPTIMIZED SQL: Get points only for the target
        c.execute("SELECT points FROM scores WHERE user_id = ?", (target.id,))
        data = c.fetchone()
        
        if data:
            points = data[0]
            # RAM SAVER: Count how many people have MORE points than user
            # This returns 1 integer instead of loading 1000 users
            c.execute("SELECT COUNT(*) FROM scores WHERE points > ?", (points,))
            rank_pos = c.fetchone()[0] + 1
            rank = f"#{rank_pos}"
        else:
            points = 0
            rank = "N/A"

        # 3. Get Solve Count
        c.execute("SELECT COUNT(*) FROM solves WHERE user_id = ?", (target.id,))
        solve_count = c.fetchone()[0]
        conn.close()

        # 4. Fetch Avatar (Network)
        avatar_bytes = None
        if target.avatar: 
            try:
                avatar_bytes = await target.avatar.read()
            except: pass

        # 5. EXECUTOR: Run the heavy image drawing in background thread
        # We use functools.partial to pass the arguments safely
        func = functools.partial(
            self.draw_profile_card, 
            target, 
            rank, 
            points, 
            solve_count, 
            avatar_bytes,
            is_champion 
        )

        buffer = await self.bot.loop.run_in_executor(None, func)
        
        file = discord.File(fp=buffer, filename="profile.png")
        await interaction.followup.send(file=file)
        
        # Close buffer to free RAM
        buffer.close()

    @app_commands.command(name="leaderboard", description="Force update the leaderboard (Admin Only)")
    @app_commands.default_permissions(administrator=True) 
    async def leaderboard(self, interaction: discord.Interaction):
        await self.update_leaderboard()
        await interaction.response.send_message("✅ Leaderboard updated!", ephemeral=True)

    @tasks.loop(minutes=2)
    async def leaderboard_task(self):
        await self.update_leaderboard()

    async def update_leaderboard(self):
        lb_channel_id = get_config_id('channel_leaderboard')
        if not lb_channel_id: return
        
        channel = self.bot.get_channel(lb_channel_id)
        if not channel: return

        conn = sqlite3.connect('ctf_data.db')
        c = conn.cursor()
        c.execute("SELECT user_id, username, points FROM scores ORDER BY points DESC LIMIT 15")
        top_players = c.fetchall()
        c.execute("SELECT value FROM config WHERE key = 'lb_msg_id'")
        row = c.fetchone()
        conn.close()

        try:
            # Handle Champion Role Logic
            champ_role_id = get_config_id('role_champion')
            gen_channel_id = get_config_id('channel_general')
            
            if top_players and champ_role_id and gen_channel_id:
                guild = channel.guild
                champion_role = guild.get_role(champ_role_id)
                general_channel = self.bot.get_channel(gen_channel_id)

                if champion_role:
                    top_user_id = top_players[0][0]
                    new_champ = guild.get_member(top_user_id)
                    current_champs = champion_role.members

                    if new_champ and (new_champ not in current_champs):
                        for old_champ in current_champs:
                            await old_champ.remove_roles(champion_role)
                            if general_channel:
                                await general_channel.send(f"👑 **NEW KING!** {new_champ.mention} has stolen the **Champion's Belt** from {old_champ.mention}! 🥊")

                        await new_champ.add_roles(champion_role)
                        if not current_champs and general_channel: 
                            await general_channel.send(f"👑 **FIRST BLOOD!** {new_champ.mention} has claimed the **Champion's Belt**!")
        except Exception as e: print(f"Role Sync Error: {e}")

        embed = discord.Embed(title="🏆 MASTER AGENT STANDINGS", color=0xFFD700)
        embed.set_footer(text="Updates every 2 mins")
        
        desc = ""
        for i, (uid, user, points) in enumerate(top_players, 1):
            icon = "👑" if i==1 else "🥈" if i==2 else "🥉" if i==3 else f"**#{i}**"
            desc += f"{icon} • **{user}** — `{points} pts`\n"
        embed.description = desc if desc else "No solves yet."
        
        conn = sqlite3.connect('ctf_data.db')
        c = conn.cursor()
        c.execute("SELECT challenge_id, user_id FROM solves GROUP BY challenge_id HAVING MIN(timestamp)")
        first_bloods = c.fetchall()
        conn.close()

        if first_bloods:
            fb_text = ""
            for chall, uid in first_bloods[-5:]: 
                u_name = "Unknown"
                if channel.guild:
                    mem = channel.guild.get_member(uid)
                    if mem: u_name = mem.display_name
                fb_text += f"🩸 **{chall}** — {u_name}\n"
            embed.add_field(name="Recent First Bloods", value=fb_text, inline=False)

        try:
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
        except Exception: pass

    async def update_challenge_card(self, challenge_id):
        conn = sqlite3.connect('ctf_data.db')
        c = conn.cursor()
        
        # 1. Get Challenge Info (Message ID, Channel ID, Points)
        c.execute("SELECT msg_id, channel_id, points FROM flags WHERE challenge_id = ?", (challenge_id,))
        data = c.fetchone()
        if not data: 
            conn.close()
            return
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

            # --- CRITICAL FIX START ---
            # We filter the fields we want to KEEP.
            # We MUST include "Time Left" here, otherwise it gets deleted when a user solves.
            saved_fields = []
            for f in embed.fields:
                if "Bounty" in f.name or "Category" in f.name or "Time Limit" in f.name or "Time Left" in f.name:
                    saved_fields.append(f)
            # --- CRITICAL FIX END ---

            # 3. Rebuild the Embed
            embed.clear_fields()
            
            # Add back the saved fields (Bounty, Category, Time Left)
            for f in saved_fields:
                embed.add_field(name=f.name, value=f.value, inline=f.inline)

            # 4. Update First Blood
            fb_value = "*Waiting...*"
            if len(solves) > 0:
                first_uid = solves[0][0]
                u = channel.guild.get_member(first_uid)
                name = u.display_name if u else "Agent"
                # BONUSES must be defined at the top of your file
                fb_value = f"🥇 **{name}** (+{base_pts + BONUSES.get(0, 0)})"
            
            embed.add_field(name="🩸 First Blood", value=fb_value, inline=False)

            # 5. Add List of Solvers (Paginated in chunks of 10)
            if len(solves) > 1:
                others = solves[1:201] # Limit to next 200 solvers to prevent limits
                current_chunk = ""
                page_number = 1
                
                for i, (uid,) in enumerate(others):
                    real_index = i + 1
                    
                    # Create a new field every 10 names
                    if i > 0 and i % 10 == 0:
                        title = "📜 Solvers" if page_number == 1 else f"📜 Solvers (Page {page_number})"
                        embed.add_field(name=title, value=current_chunk, inline=False)
                        current_chunk = ""
                        page_number += 1
                    
                    u = channel.guild.get_member(uid)
                    name = u.display_name if u else "Agent"
                    bonus = BONUSES.get(real_index, 0)
                    
                    # Icons for 2nd and 3rd place
                    icon = "🥈" if real_index==1 else "🥉" if real_index==2 else "✅"
                    current_chunk += f"{icon} **{name}** (+{base_pts+bonus})\n"

                # Add the final chunk
                if current_chunk:
                    title = "📜 Solvers" if page_number == 1 else f"📜 Solvers (Page {page_number})"
                    embed.add_field(name=title, value=current_chunk, inline=False)

            await msg.edit(embed=embed)
            
        except Exception as e:
            print(f"Error updating card for {challenge_id}: {e}")

async def setup(bot):
    await bot.add_cog(Player(bot))
