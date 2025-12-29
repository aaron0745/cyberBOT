import discord
import os
import sqlite3
import asyncio
from discord.ext import commands, tasks
from discord import app_commands
from dotenv import load_dotenv

# --- 1. SETUP ---
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# --- 2. DATABASE ---
def init_db():
    conn = sqlite3.connect('ctf_data.db')
    c = conn.cursor()
    
    # Flags Table (Updated with posted_at)
    c.execute('''CREATE TABLE IF NOT EXISTS flags
                 (challenge_id TEXT PRIMARY KEY, flag_text TEXT, points INTEGER, category TEXT,
                  msg_id INTEGER, channel_id INTEGER, image_url TEXT, posted_at INTEGER)''')
    
    # --- MIGRATION: Check if posted_at exists (for older DBs) ---
    try:
        c.execute("SELECT posted_at FROM flags LIMIT 1")
    except sqlite3.OperationalError:
        print("⚠️ Migrating Database: Adding 'posted_at' column to flags table...")
        c.execute("ALTER TABLE flags ADD COLUMN posted_at INTEGER")
    # -------------------------------------------------------------

    # Scores Table
    c.execute('''CREATE TABLE IF NOT EXISTS scores
                 (user_id INTEGER PRIMARY KEY, username TEXT, points INTEGER)''')
    
    # Solves Table
    c.execute('''CREATE TABLE IF NOT EXISTS solves
                 (user_id INTEGER, challenge_id TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                 PRIMARY KEY (user_id, challenge_id))''')
    
    # Banlist Table
    c.execute('''CREATE TABLE IF NOT EXISTS banlist 
                 (user_id INTEGER PRIMARY KEY)''')

    # Hints Table
    c.execute('''CREATE TABLE IF NOT EXISTS hints
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, challenge_id TEXT, hint_text TEXT, cost INTEGER)''')

    # Config Table
    c.execute('''CREATE TABLE IF NOT EXISTS config
                 (key TEXT PRIMARY KEY, value INTEGER)''')

    # Unlocked Hints
    c.execute('''CREATE TABLE IF NOT EXISTS unlocked_hints
                 (user_id INTEGER, hint_id INTEGER, PRIMARY KEY (user_id, hint_id))''')

    conn.commit()
    conn.close()
    print("📂 Database initialized successfully.")

# --- 3. STATUS TASK ---
@tasks.loop(minutes=5)
async def status_task():
    # Rotates status to show activity
    await bot.change_presence(activity=discord.Game(name="Capture The Flag 🚩"))
    await asyncio.sleep(150)
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="for Solves 👀"))

# --- 4. BOT EVENTS ---
@bot.event
async def on_ready():
    init_db()
    print(f'✅ Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')
    
    # Load Cogs
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            try:
                await bot.load_extension(f'cogs.{filename[:-3]}')
                print(f"📦 Loaded: {filename}")
            except Exception as e:
                print(f"❌ FAILED to load {filename}: {e}")

    # Start Status Task if not running
    if not status_task.is_running():
        status_task.start()

    # Attempt automatic global sync
    try:
        synced = await bot.tree.sync()
        print(f"🔁 Auto-Synced {len(synced)} slash commands globally.")
    except Exception as e:
        print(f"⚠️ Auto-Sync failed: {e}")

# --- 5. UTILITY COMMANDS ---

@bot.command()
@commands.has_permissions(administrator=True)
async def upload(ctx):
    """Pushes commands to the current server immediately"""
    await ctx.send("🚀 **Uploading commands to this guild...**")
    bot.tree.copy_global_to(guild=ctx.guild)
    await bot.tree.sync(guild=ctx.guild)
    await ctx.send("✅ **Done!** Press `Ctrl + R` (or restart Discord) to see them.")

@bot.command()
@commands.has_permissions(administrator=True)
async def fix_commands(ctx):
    """Wipes and re-uploads commands (Use if commands duplicate or won't show)"""
    msg = await ctx.send("🧹 **Wiping old commands...**")
    
    # Clear Global and Guild commands
    bot.tree.clear_commands(guild=None)
    await bot.tree.sync(guild=None)
    bot.tree.clear_commands(guild=ctx.guild)
    await bot.tree.sync(guild=ctx.guild)
    
    await msg.edit(content="🔄 **Re-uploading clean list...**")
    
    # Re-sync
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            try:
                await bot.reload_extension(f'cogs.{filename[:-3]}')
            except: 
                pass 
                
    await bot.tree.sync()
    await msg.edit(content="✅ **FIXED!** All commands reset. Please restart your Discord client.")

# --- 6. ERROR HANDLING ---
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    if isinstance(error, discord.app_commands.MissingPermissions):
        await interaction.response.send_message("⛔ You don't have permission to do that.", ephemeral=True)
    elif isinstance(error, discord.app_commands.CommandOnCooldown):
        await interaction.response.send_message(f"⏳ Cooldown! Try again in {error.retry_after:.1f}s", ephemeral=True)
    else:
        print(f"❌ Command Error: {error}")
        if not interaction.response.is_done():
            await interaction.response.send_message("⚠️ An internal error occurred.", ephemeral=True)

if __name__ == '__main__':
    if not TOKEN:
        print("❌ Error: DISCORD_TOKEN not found in .env")
    else:
        bot.run(TOKEN)
