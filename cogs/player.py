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
        conn = sqlite3.connect('ctf_data.db', timeout=10)
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
        conn = sqlite3.connect('ctf_data.db', timeout=10)
        c = conn.cursor()
        
        # Verify Hint Exists
        c.execute("SELECT cost, hint_text FROM hints WHERE id = ?", (hint_id,))
        res = c.fetchone()
        if not res:
            conn.close()
            await interaction.response.send_message("❌ Error: Hint not found.", ephemeral=True)
            return
        
        cost, text = res
        user_id = interaction.user.id

        # Check if already bought
        c.execute("SELECT * FROM unlocked_hints WHERE user_id = ? AND hint_id = ?", (user_id, hint_id))
        if c.fetchone():
            conn.close()
            await interaction.response.send_message(f"🔓 **Hint #{hint_id}:**\n||{text}||", ephemeral=True)
            return

        # Check Balance
        c.execute("SELECT points FROM scores WHERE user_id = ?", (user_id,))
        score_res = c.fetchone()
        current_points = score_res[0] if score_res else 0

        if current_points < cost:
            conn.close()
            await interaction.response.send_message(f"❌ You need {cost} pts (You have {current_points})", ephemeral=True)
            return

        # Deduct Points & Unlock
        c.execute("UPDATE scores SET points = points - ? WHERE user_id = ?", (cost, user_id))
        c.execute("INSERT INTO unlocked_hints VALUES (?, ?)", (user_id, hint_id))
        conn.commit()
        conn.close()

        # Update Leaderboard
        cog = self.bot.get_cog('Player')
        if cog: await cog.update_leaderboard()

        await interaction.response.send_message(f"🔓 **Hint Unlocked!** (-{cost} pts)\n\n||{text}||", ephemeral=True)

class HintView(discord.ui.View):
    def __init__(self, hints, bot, user_id):
        super().__init__(timeout=60)
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

        conn = sqlite3.connect('ctf_data.db', timeout=10)
        c = conn.cursor()
        
        # 0. Check Banlist
        c.execute("SELECT * FROM banlist WHERE user_id = ?", (user_id,))
        if c.fetchone():
            conn.close()
            await interaction.response.send_message("🚫 **ACCESS DENIED.** You have been disqualified.", ephemeral=True)
            return

        # 0.1 Check Time Limit
        c.execute("SELECT posted_at FROM flags WHERE challenge_id = ?", (self.challenge_id,))
        data = c.fetchone()
        if data and data[0]:
            if current_time > (data[0] + 86400): # 24 Hours
                conn.close()
                await interaction.response.send_message("⏳ **Time limit exceeded**", ephemeral=True)
                return

        # 1. Cooldown & Duplicate Check
        if user_id in COOLDOWNS and current_time - COOLDOWNS[user_id] < 2:
            conn.close()
            await interaction.response.send_message("⏳ Too fast! Wait a second.", ephemeral=True)
            return
        COOLDOWNS[user_id] = current_time

        c.execute("SELECT * FROM solves WHERE user_id = ? AND challenge_id = ?", (user_id, self.challenge_id))
        if c.fetchone():
            conn.close()
            await interaction.response.send_message("⚠️ You already solved this!", ephemeral=True)
            return

        # 2. Verify Flag
        c.execute("SELECT flag_text, points FROM flags WHERE challenge_id = ?", (self.challenge_id,))
        result = c.fetchone()

        if not result:
            conn.close()
            await interaction.response.send_message("❌ Error: Challenge not found.", ephemeral=True)
            return

        correct_flag, base_points = result

        if user_flag == correct_flag:
            c.execute("SELECT COUNT(*) FROM solves WHERE challenge_id = ?", (self.challenge_id,))
            solve_index = c.fetchone()[0]
            bonus = BONUSES.get(solve_index, 0)
            total_points = base_points + bonus

            # Insert Solve
            c.execute("INSERT INTO solves (user_id, challenge_id, timestamp) VALUES (?, ?, ?)", (user_id, self.challenge_id, current_time))
            
            # Update Score & Last Solve Time
            c.execute("INSERT OR IGNORE INTO scores (user_id, username, points, last_solve_time) VALUES (?, ?, 0, ?)", (user_id, interaction.user.name, current_time))
            c.execute("UPDATE scores SET points = points + ?, last_solve_time = ? WHERE user_id = ?", (total_points, current_time, user_id))
            
            c.execute("SELECT points FROM scores WHERE user_id = ?", (user_id,))
            new_total_score = c.fetchone()[0]
            conn.commit()
            conn.close()

            # Dynamic Roles
            role_msg = ""
            if interaction.guild:
                member = interaction.guild.get_member(user_id)
                rank_map = {2500: 'role_rank_1', 6000: 'role_rank_2', 9000: 'role_rank_3'}
                assigned = []
                for thres, key in rank_map.items():
                    rid = get_config_id(key)
                    if rid and new_total_score >= thres:
                        r = interaction.guild.get_role(rid)
                        if r and r not in member.roles:
                            await member.add_roles(r)
                            assigned.append(r.name)
                if assigned: role_msg = f"\n🆙 **Promoted:** {', '.join(assigned)}"

            msg = f"🎉 **Correct!** +{total_points} pts"
            if bonus > 0: msg += f" (First Blood Bonus: +{bonus}!)"
            msg += role_msg
            await interaction.response.send_message(msg, ephemeral=True)

            # LOGGING TO CHANNEL
            log_cid = get_config_id('channel_log')
            if log_cid:
                log_chan = self.bot.get_channel(log_cid)
                if log_chan:
                    embed = discord.Embed(title="✅ Flag Captured", color=discord.Color.green(), timestamp=discord.utils.utcnow())
                    embed.add_field(name="User", value=interaction.user.mention, inline=True)
                    embed.add_field(name="Challenge", value=self.challenge_id, inline=True)
                    embed.add_field(name="Points", value=f"{total_points} (Total: {new_total_score})", inline=True)
                    await log_chan.send(embed=embed)
            
            cog = self.bot.get_cog('Player')
            if cog: 
                await cog.update_leaderboard()
                await cog.update_challenge_card(self.challenge_id)
        else:
            conn.close()
            await interaction.response.send_message("❌ **Wrong Flag!**", ephemeral=True)

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
            cid = interaction.data.get("custom_id", "")
            
            if cid.startswith("submit:"):
                await interaction.response.send_modal(SubmissionModal(cid.split(":")[1], self.bot))
            
            elif cid.startswith("hint_menu:"):
                chall_id = cid.split(":")[1]
                conn = sqlite3.connect('ctf_data.db', timeout=10)
                c = conn.cursor()
                c.execute("SELECT id, hint_text, cost FROM hints WHERE challenge_id = ?", (chall_id,))
                hints = c.fetchall()
                conn.close()
                
                if not hints:
                    await interaction.response.send_message("🤷 No hints available for this challenge.", ephemeral=True)
                    return
                
                await interaction.response.send_message("🛒 **Buy a Hint:**", view=HintView(hints, self.bot, interaction.user.id), ephemeral=True)

    # --- RAM OPTIMIZED PROFILE DRAWING ---
    def draw_profile_card(self, user_name, rank, points, solves, avatar_bytes, is_champion):
        width, height = 900, 350
        bg_color = (15, 15, 20)
        
        primary = (255, 215, 0) if is_champion else (0, 255, 230)
        
        card = Image.new("RGBA", (width, height), bg_color)
        draw = ImageDraw.Draw(card)

        for x in range(0, width, 40): draw.line([(x, 0), (x, height)], fill=(25, 30, 35))
        for y in range(0, height, 40): draw.line([(0, y), (width, y)], fill=(25, 30, 35))

        if avatar_bytes:
            try:
                with Image.open(BytesIO(avatar_bytes)) as av:
                    av.thumbnail((200, 200), Image.Resampling.LANCZOS)
                    avatar = av.convert("RGBA")
                    mask = Image.new("L", avatar.size, 0)
                    ImageDraw.Draw(mask).ellipse((0, 0) + avatar.size, fill=255)
                    avatar.putalpha(mask)
                    card.paste(avatar, (50, 75), avatar)
            except Exception: pass

        draw.text((300, 40), user_name.upper(), fill="white", font=self.title_font)
        
        def draw_box(x, y, label, val):
            draw.rectangle([x, y, x+170, y+110], outline=primary, width=2)
            draw.text((x+15, y+10), label, fill=primary, font=self.label_font)
            draw.text((x+15, y+45), str(val), fill="white", font=self.value_font)

        draw_box(300, 190, "RANK", rank)
        draw_box(490, 190, "SCORE", points)
        draw_box(680, 190, "FLAGS", solves)

        buffer = BytesIO()
        card.save(buffer, format="PNG", optimize=True)
        buffer.seek(0)
        
        card.close()
        gc.collect()
        return buffer

    @app_commands.command(name="profile", description="View agent ID card")
    async def profile(self, interaction: discord.Interaction, member: discord.Member = None):
        await interaction.response.defer()
        target = member or interaction.user
        
        champ_id = get_config_id('role_champion')
        is_champion = champ_id and any(r.id == champ_id for r in target.roles)

        conn = sqlite3.connect('ctf_data.db', timeout=10)
        c = conn.cursor()
        
        c.execute("SELECT points, last_solve_time FROM scores WHERE user_id = ?", (target.id,))
        data = c.fetchone()
        
        if data:
            points, my_time = data
            c.execute("""
                SELECT COUNT(*) FROM scores 
                WHERE points > ? OR (points = ? AND last_solve_time < ?)
            """, (points, points, my_time))
            rank = f"#{c.fetchone()[0] + 1}"
        else:
            points = 0
            rank = "N/A"

        c.execute("SELECT COUNT(*) FROM solves WHERE user_id = ?", (target.id,))
        solves = c.fetchone()[0]
        conn.close()

        avatar_bytes = None
        if target.avatar:
            try: avatar_bytes = await target.avatar.read()
            except: pass

        func = functools.partial(self.draw_profile_card, target.display_name, rank, points, solves, avatar_bytes, is_champion)
        buffer = await self.bot.loop.run_in_executor(None, func)
        
        await interaction.followup.send(file=discord.File(fp=buffer, filename="profile.png"))
        buffer.close()

    @tasks.loop(minutes=2)
    async def leaderboard_task(self):
        await self.update_leaderboard()

    # --- LEADERBOARD UPDATE ---
    async def update_leaderboard(self):
        lb_cid = get_config_id('channel_leaderboard')
        if not lb_cid: return
        channel = self.bot.get_channel(lb_cid)
        if not channel: return

        conn = sqlite3.connect('ctf_data.db', timeout=10)
        c = conn.cursor()
        c.execute("SELECT user_id, points, username FROM scores ORDER BY points DESC, last_solve_time ASC LIMIT 15")
        top_players = c.fetchall()
        
        c.execute("SELECT challenge_id, user_id FROM solves GROUP BY challenge_id HAVING MIN(timestamp)")
        first_bloods = c.fetchall()
        conn.close()

        embed = discord.Embed(title="🏆 MASTER AGENT STANDINGS", color=0xFFD700)
        embed.set_footer(text="Updates every 2 mins • Tie-breaker: Speed")

        desc = ""
        for i, (uid, points, db_username) in enumerate(top_players, 1):
            member = channel.guild.get_member(uid)
            if member:
                display_name = member.display_name
            else:
                display_name = db_username if db_username else f"Agent-{uid}"
            
            icon = "👑" if i==1 else "🥈" if i==2 else "🥉" if i==3 else f"**#{i}**"
            desc += f"{icon} • **{display_name}** — `{points} pts`\n"
        
        embed.description = desc if desc else "No solves yet."

        if first_bloods:
            fb_text = ""
            for chall, uid in first_bloods[-5:]:
                member = channel.guild.get_member(uid)
                name = member.display_name if member else "Unknown Agent"
                fb_text += f"🩸 **{chall}** — {name}\n"
            embed.add_field(name="Recent First Bloods", value=fb_text, inline=False)

        lid = get_config_id('lb_msg_id')
        try:
            if lid:
                msg = await channel.fetch_message(lid)
                await msg.edit(embed=embed)
            else:
                msg = await channel.send(embed=embed)
                conn = sqlite3.connect('ctf_data.db', timeout=10)
                conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('lb_msg_id', ?)", (msg.id,))
                conn.commit()
                conn.close()
        except: pass

    # --- CHALLENGE CARD UPDATE (FIXED: Dynamic Timer + Single Page) ---
    async def update_challenge_card(self, challenge_id):
        conn = sqlite3.connect('ctf_data.db', timeout=10)
        c = conn.cursor()
        
        # 1. Fetch posted_at
        c.execute("SELECT msg_id, channel_id, points, category, image_url, flag_text, posted_at FROM flags WHERE challenge_id = ?", (challenge_id,))
        res = c.fetchone()
        
        if not res: 
            conn.close()
            return
            
        mid, cid, base_pts, cat, img, flag_text, posted_at = res
        
        c.execute("SELECT user_id FROM solves WHERE challenge_id = ? ORDER BY timestamp ASC", (challenge_id,))
        solves = c.fetchall()
        conn.close()

        ch = self.bot.get_channel(cid)
        if not ch: return
        
        try:
            msg = await ch.fetch_message(mid)
        except:
            return

        # 2. Dynamic Timer Logic
        if posted_at:
            end_time = posted_at + 86400 # 24 Hours
            current_time = int(time.time())
            
            if current_time > end_time:
                time_status = "🔴 **EXPIRED** (Points Valid, No Leaderboard Movement)"
            else:
                # This <t:TIMESTAMP:R> is the key part that makes it count down
                time_status = f"⏳ **Time Left:** <t:{end_time}:R>"
        else:
            time_status = "♾️ **No Time Limit**"

        desc_text = f"**Category:** {cat}\n**Points:** {base_pts}\n{time_status}"
        
        embed = discord.Embed(title=f"🚩 {challenge_id}", description=desc_text, color=0x00ff00)
        if img and img != "None": 
            embed.set_image(url=img)
        embed.set_footer(text=f"Solves: {len(solves)}")

        # 3. Solver List
        if solves:
            # First Blood
            first_uid = solves[0][0]
            u = ch.guild.get_member(first_uid)
            if not u:
                conn = sqlite3.connect('ctf_data.db', timeout=10)
                cur = conn.cursor()
                cur.execute("SELECT username FROM scores WHERE user_id=?", (first_uid,))
                row = cur.fetchone()
                name = row[0] if row else "Agent"
                conn.close()
            else:
                name = u.display_name

            fb_bonus = BONUSES.get(0, 0)
            embed.add_field(name="🩸 First Blood", value=f"🥇 **{name}** (+{base_pts + fb_bonus})", inline=False)

            # Others (Single List)
            if len(solves) > 1:
                others = solves[1:]
                solver_list = ""
                
                for i, (uid,) in enumerate(others):
                    real_index = i + 1 
                    u = ch.guild.get_member(uid)
                    if not u:
                        conn = sqlite3.connect('ctf_data.db', timeout=10)
                        cur = conn.cursor()
                        cur.execute("SELECT username FROM scores WHERE user_id=?", (uid,))
                        row = cur.fetchone()
                        name = row[0] if row else "Agent"
                        conn.close()
                    else:
                        name = u.display_name

                    bonus = BONUSES.get(real_index, 0)
                    icon = "🥈" if real_index == 1 else "🥉" if real_index == 2 else "✅"
                    
                    line = f"{icon} **{name}** (+{base_pts+bonus})\n"
                    
                    if len(solver_list) + len(line) > 1000:
                        solver_list += "...and others"
                        break
                    
                    solver_list += line

                if solver_list:
                    embed.add_field(name="📜 Solvers", value=solver_list, inline=False)

        view = discord.ui.View(timeout=None)
        view.add_item(discord.ui.Button(style=discord.ButtonStyle.green, label="Submit Flag", custom_id=f"submit:{challenge_id}"))
        
        conn = sqlite3.connect('ctf_data.db', timeout=10)
        curr = conn.cursor()
        curr.execute("SELECT COUNT(*) FROM hints WHERE challenge_id = ?", (challenge_id,))
        has_hints = curr.fetchone()[0] > 0
        conn.close()
        
        if has_hints:
            view.add_item(discord.ui.Button(style=discord.ButtonStyle.blurple, label="💡 Hints", custom_id=f"hint_menu:{challenge_id}"))

        await msg.edit(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(Player(bot))
