import discord
import os
import aiosqlite
import asyncio
from discord.ext import commands, tasks
from discord import app_commands
from dotenv import load_dotenv

# --- 1. SETUP ---
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = os.getenv('GUILD_ID') 
PREFIX = os.getenv('PREFIX') or "/"

# First Blood bonus points (shared with cogs via import)
# 0 = 1st solver (+50), 1 = 2nd (+25), 2 = 3rd (+10)
BONUSES = {0: 50, 1: 25, 2: 10}

class CTFBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True          # Needed for member lookups, role assignment, display names
        intents.message_content = True  # Needed for prefix command fallback
        super().__init__(command_prefix=PREFIX, intents=intents, help_command=None)
        self.db = None

    async def setup_hook(self):
        # 0. Storage
        if not os.path.exists('uploads'):
            os.makedirs('uploads')

        # 1. Database
        self.db = await aiosqlite.connect('bot.db')
        self.db.row_factory = aiosqlite.Row 
        await self.init_db()
        
        # 2. Load Cogs
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py') and not filename.startswith('__'):
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    print(f"📦 Loaded: {filename}")
                except Exception as e:
                    print(f"❌ FAILED to load {filename}: {e}")

        # 3. Sync Logic
        if GUILD_ID:
            try:
                g_id = int(GUILD_ID)
                guild_obj = discord.Object(id=g_id)
                self.tree.copy_global_to(guild=guild_obj)
                synced = await self.tree.sync(guild=guild_obj)
                print(f"⚡ cyberBOT: {len(synced)} commands active on Guild {GUILD_ID}")
            except (ValueError, TypeError):
                print(f"⚠️ Invalid GUILD_ID in .env: '{GUILD_ID}'. Defaulting to global sync.")
                try:
                    synced = await self.tree.sync()
                    print(f"🌍 cyberBOT: {len(synced)} commands active globally.")
                except Exception as e:
                    print(f"⚠️ Global Sync Error: {e}")
            except Exception as e:
                print(f"⚠️ Sync Error: {e}")
        else:
            try:
                synced = await self.tree.sync()
                print(f"🌍 cyberBOT: {len(synced)} commands active globally.")
            except Exception as e:
                print(f"⚠️ Global Sync Error: {e}")

    async def init_db(self):
        await self.db.execute("PRAGMA journal_mode=WAL;")
        
        # Comprehensive flags table
        await self.db.execute('''CREATE TABLE IF NOT EXISTS flags
                     (challenge_id TEXT PRIMARY KEY, flag_text TEXT, points INTEGER, category TEXT,
                      msg_id INTEGER, file_msg_id INTEGER, channel_id INTEGER, image_url TEXT, posted_at INTEGER,
                      start_time INTEGER, end_time INTEGER, description TEXT, 
                      connection_info TEXT, file_path TEXT)''')

        # Multi-column Migration
        try:
            await self.db.execute("SELECT file_msg_id FROM flags LIMIT 1")
        except aiosqlite.OperationalError:
            print("🛠️ Migrating database: Adding missing columns...")
            migration_cmds = [
                "ALTER TABLE flags ADD COLUMN start_time INTEGER",
                "ALTER TABLE flags ADD COLUMN end_time INTEGER",
                "ALTER TABLE flags ADD COLUMN description TEXT",
                "ALTER TABLE flags ADD COLUMN connection_info TEXT",
                "ALTER TABLE flags ADD COLUMN file_path TEXT",
                "ALTER TABLE flags ADD COLUMN file_msg_id INTEGER"
            ]
            for cmd in migration_cmds:
                try: await self.db.execute(cmd)
                except: pass
        
        await self.db.execute('''CREATE TABLE IF NOT EXISTS role_rewards (role_id INTEGER PRIMARY KEY, points INTEGER)''')
        await self.db.execute('''CREATE TABLE IF NOT EXISTS scores (user_id INTEGER PRIMARY KEY, username TEXT, points INTEGER)''')
        await self.db.execute('''CREATE TABLE IF NOT EXISTS solves (user_id INTEGER, challenge_id TEXT, timestamp REAL, PRIMARY KEY (user_id, challenge_id))''')
        await self.db.execute('''CREATE TABLE IF NOT EXISTS banlist (user_id INTEGER PRIMARY KEY)''')
        await self.db.execute('''CREATE TABLE IF NOT EXISTS hints (id INTEGER PRIMARY KEY AUTOINCREMENT, challenge_id TEXT, hint_text TEXT, cost INTEGER)''')
        await self.db.execute('''CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value INTEGER)''')
        await self.db.execute('''CREATE TABLE IF NOT EXISTS unlocked_hints (user_id INTEGER, hint_id INTEGER, PRIMARY KEY (user_id, hint_id))''')
        await self.db.commit()
        print("📂 bot.db initialized.")

    async def close(self):
        if self.db: await self.db.close()
        await super().close()

bot = CTFBot()

@tasks.loop(minutes=5)
async def status_task():
    await bot.change_presence(activity=discord.Game(name="Capture The Flag 🚩"))
    await asyncio.sleep(150)
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="for Solves 👀"))

@bot.event
async def on_ready():
    if not status_task.is_running(): status_task.start()
    print(f'✅ Logged in as {bot.user}')
    print('🚀 cyberBOT operational.')

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    if isinstance(error, discord.app_commands.MissingPermissions):
        if interaction.response.is_done():
            await interaction.followup.send("⛔ Administrator permissions required.", ephemeral=True)
        else:
            await interaction.response.send_message("⛔ Administrator permissions required.", ephemeral=True)
    elif isinstance(error, discord.app_commands.CommandOnCooldown):
        if interaction.response.is_done():
            await interaction.followup.send(f"⏳ Cooldown! Try again in {error.retry_after:.1f}s", ephemeral=True)
        else:
            await interaction.response.send_message(f"⏳ Cooldown! Try again in {error.retry_after:.1f}s", ephemeral=True)
    else:
        print(f"❌ Command Error: {error}")
        if interaction.response.is_done():
            try: await interaction.followup.send("⚠️ An internal system error occurred.", ephemeral=True)
            except: pass
        else:
            try: await interaction.response.send_message("⚠️ An internal system error occurred.", ephemeral=True)
            except: pass

if __name__ == '__main__':
    if not TOKEN: print("❌ Error: DISCORD_TOKEN not found in .env")
    else: bot.run(TOKEN)
