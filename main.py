import discord
import os
import sqlite3
import asyncio
from discord.ext import commands, tasks
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
    
    # Flags Table (Updated with location data for First Blood updates)
    c.execute('''CREATE TABLE IF NOT EXISTS flags
                 (challenge_id TEXT PRIMARY KEY, flag_text TEXT, points INTEGER, category TEXT,
                  msg_id INTEGER, channel_id INTEGER)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS scores
                 (user_id INTEGER PRIMARY KEY, username TEXT, points INTEGER)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS solves
                 (user_id INTEGER, challenge_id TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                 PRIMARY KEY (user_id, challenge_id))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS config
                 (key TEXT PRIMARY KEY, value INTEGER)''')
    
    conn.commit()
    conn.close()

# --- 3. TASKS ---
@tasks.loop(seconds=10)
async def status_task():
    await bot.change_presence(activity=discord.Game(name="Capture The Flag"))

# --- 4. EVENTS ---
@bot.event
async def on_ready():
    init_db()
    print("---------------------------------")
    print(f'✅ Logged in as: {bot.user}')
    print("---------------------------------")
    
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            try:
                await bot.load_extension(f'cogs.{filename[:-3]}')
                print(f"📦 Loaded: {filename}")
            except Exception as e:
                print(f"❌ FAILED to load {filename}: {e}")

    if not status_task.is_running():
        status_task.start()

# --- 5. COMMANDS ---
@bot.command()
@commands.has_permissions(administrator=True)
async def upload(ctx):
    """Pushes commands to the server"""
    await ctx.send("🚀 **Uploading commands...**")
    bot.tree.copy_global_to(guild=ctx.guild)
    await bot.tree.sync(guild=ctx.guild)
    await ctx.send("✅ **Done!** Press `Ctrl + R` to refresh.")

@bot.command()
@commands.has_permissions(administrator=True)
async def fix_commands(ctx):
    """Wipes and re-uploads commands"""
    msg = await ctx.send("🧹 Wiping old commands...")
    bot.tree.clear_commands(guild=None)
    await bot.tree.sync(guild=None)
    bot.tree.clear_commands(guild=ctx.guild)
    await bot.tree.sync(guild=ctx.guild)
    
    await msg.edit(content="🔄 Re-uploading...")
    bot.tree.copy_global_to(guild=ctx.guild)
    await bot.tree.sync(guild=ctx.guild)
    
    await msg.edit(content="✅ **FIXED!** Press `Ctrl + R` now.")

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    if not interaction.response.is_done():
        await interaction.response.send_message(f"⚠️ Error: {error}", ephemeral=True)

if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ ERROR: DISCORD_TOKEN missing in .env")
