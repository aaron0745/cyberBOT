import discord
from discord import app_commands
from discord.ext import commands
import sqlite3

# Your Banner Image
BANNER_URL = "https://cdn.discordapp.com/attachments/1449701392007827527/1449795213143834676/IMG_20251214_213716.jpg?ex=69403282&is=693ee102&hm=eb1bf3dc6a86622c7f501fa5c06388435f84fbf1553f92e7367ef57acfa4a2a2&" 

class SubmitButton(discord.ui.View):
    def __init__(self, challenge_id, bot):
        super().__init__(timeout=None)
        self.challenge_id = challenge_id
        self.bot = bot

    @discord.ui.button(label="🚩 Submit Flag", style=discord.ButtonStyle.green, custom_id="submit_btn")
    async def open_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        from cogs.player import SubmissionModal
        await interaction.response.send_modal(SubmissionModal(self.challenge_id, self.bot))

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # --- COMMAND: LIST CHALLENGES ---
    @app_commands.command(name="list", description="Show all created challenges")
    async def list_challenges(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Admin only.", ephemeral=True)

        conn = sqlite3.connect('ctf_data.db')
        c = conn.cursor()
        c.execute("SELECT challenge_id, category, points, flag_text FROM flags")
        rows = c.fetchall()
        conn.close()

        if not rows:
            return await interaction.response.send_message("📂 Database is empty.", ephemeral=True)

        # Build a nice table
        desc = "```ini\n[ID]           [PTS]   [CATEGORY]\n"
        for row in rows:
            # Formatting for clean columns
            c_id = f"{row[0]:<14}" # Left align, 14 chars
            pts = f"{row[2]:<7}"   # Left align, 7 chars
            cat = f"{row[1]}"
            desc += f"{c_id} {pts} {cat}\n"
        desc += "```"
        
        embed = discord.Embed(title="📂 Challenge Database", description=desc, color=0x00AAFF)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # --- COMMAND: CREATE ---
    @app_commands.command(name="create", description="Add a new challenge")
    @app_commands.describe(
        challenge_id="Unique name (e.g., web-01)",
        flag="The secret answer",
        points="Points value",
        category="Type (Web, Crypto, Pwn, etc.)"
    )
    async def create(self, interaction: discord.Interaction, challenge_id: str, flag: str, points: int, category: str):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Admin only.", ephemeral=True)

        conn = sqlite3.connect('ctf_data.db')
        c = conn.cursor()
        try:
            # Note: msg_id and channel_id are NULL until posted
            c.execute("INSERT INTO flags (challenge_id, flag_text, points, category, msg_id, channel_id) VALUES (?, ?, ?, ?, NULL, NULL)", 
                      (challenge_id, flag, points, category))
            conn.commit()
            await interaction.response.send_message(f"✅ Created **{category}** challenge `{challenge_id}` ({points} pts).", ephemeral=True)
        except sqlite3.IntegrityError:
            await interaction.response.send_message(f"⚠️ Challenge ID `{challenge_id}` already exists!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ DB Error: {e}", ephemeral=True)
        finally:
            conn.close()

    # --- COMMAND: POST (Updated to save location) ---
    @app_commands.command(name="post", description="Post a challenge embed with a file")
    async def post(self, interaction: discord.Interaction, target_channel: discord.TextChannel, challenge_id: str, description: str, file: discord.Attachment = None):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Admin only.", ephemeral=True)

        conn = sqlite3.connect('ctf_data.db')
        c = conn.cursor()
        c.execute("SELECT points, category FROM flags WHERE challenge_id = ?", (challenge_id,))
        res = c.fetchone()

        if not res:
            conn.close()
            return await interaction.response.send_message(f"❌ Challenge `{challenge_id}` not found.", ephemeral=True)

        await interaction.response.send_message(f"✅ Posting to {target_channel.mention}...", ephemeral=True)
        
        points_val = res[0]
        category_val = res[1] if res[1] else "General"

        embed = discord.Embed(
            title=f"🛡️ MISSION: {challenge_id.upper()}",
            description=f"**Objective:**\n```yaml\n{description}\n```",
            color=0x00ff00 
        )
        embed.add_field(name="💰 Bounty", value=f"**{points_val} Points**", inline=True)
        embed.add_field(name="📂 Category", value=f"**{category_val}**", inline=True)
        # Field Index 2 is First Blood (We will edit this later!)
        embed.add_field(name="🩸 First Blood", value="*Waiting...*", inline=True)
        
        embed.set_thumbnail(url=self.bot.user.avatar.url if self.bot.user.avatar else None)
        if "http" in BANNER_URL:
            embed.set_image(url=BANNER_URL)
        embed.set_footer(text="Download the file below • Good luck, Agent.")

        files_to_send = []
        if file:
            f = await file.to_file()
            files_to_send.append(f)

        # Send the message
        msg = await target_channel.send(embed=embed, files=files_to_send, view=SubmitButton(challenge_id, self.bot))
        
        # SAVE THE LOCATION! (So we can edit First Blood later)
        c.execute("UPDATE flags SET msg_id = ?, channel_id = ? WHERE challenge_id = ?", 
                  (msg.id, msg.channel.id, challenge_id))
        conn.commit()
        conn.close()

async def setup(bot):
    await bot.add_cog(Admin(bot))
