Here is your **complete Master Documentation** for the CTF Bot.
-----

# 📘 CTF Bot - Master Operation Manual

## 1\. Installation & Setup

### A. Prerequisites

Before running the code, ensure you have:

1.  **Python 3.9+** installed.
2.  A **Discord Bot Token** (From the [Discord Developer Portal](https://www.google.com/search?q=https://discord.com/developers/applications)).
      * *Note:* Ensure "Message Content Intent", "Server Members Intent", and "Presence Intent" are **ON**.

### B. Folder Structure

Your project folder **must** look exactly like this for the bot to find the files.

```text
CTF_Bot/
├── .env                 <-- Security file for your Token
├── .discloudignore      <-- Prevents data overwrites (See Section 4)
├── requirements.txt     <-- List of libraries needed
├── main.py              <-- The brain of the bot
└── cogs/                <-- Folder for bot modules
    ├── admin.py         <-- Admin commands
    └── player.py        <-- Player commands & Leaderboard
```

### C. File Setup

**1. Create `requirements.txt`** (Required for Discloud/Hosting)
Create a file named `requirements.txt` and paste this inside:

```text
discord.py
python-dotenv
aiosqlite
```

**2. Create `.env`**
Create a file named `.env` and paste your bot token:

```env
DISCORD_TOKEN=your_actual_token_here_do_not_share
```

**3. Configure the Leaderboard Channel**
The bot needs to know exactly where to print the "Master Leaderboard".

1.  Enable **Developer Mode** in Discord (User Settings \> Advanced).
2.  Right-click your desired leaderboard channel $\rightarrow$ **Copy Channel ID**.
3.  Open `cogs/player.py`.
4.  Edit **Line 8-9**:
    ```python
    # REPLACE THIS WITH YOUR ACTUAL LEADERBOARD CHANNEL ID
    LEADERBOARD_CHANNEL_ID = 123456789012345678  <-- Paste ID here
    ```

-----

## 2\. Bot Features & Capabilities

### 🏆 The "Master" Live Leaderboard

  * **Hardcoded Stability:** The leaderboard lives in *one specific channel*. It updates every **60 seconds** automatically.
  * **Self-Healing:** If someone accidentally deletes the leaderboard message, the bot detects it and sends a new one instantly.
  * **Top 15 Display:** Shows the top agents with medals (🥇 🥈 🥉) and scores.

### 🎮 The "Mission Card" System

Challenges are not just text; they are interactive **Mission Cards**.

  * **Interactive:** Every challenge post has a 🟢 **Submit Flag** button.
  * **Live Updates:** When a player gets "First Blood" (first solve), the message updates *instantly* to show their name on the card for everyone to see.
  * **Attachments:** You can attach zip files, images, or PDFs to challenges.

### 🩸 Scoring Logic

  * **First Blood Bonuses:**
      * 🩸 **1st Place:** +50 pts
      * 🥈 **2nd Place:** +25 pts
      * 🥉 **3rd Place:** +10 pts
  * **Anti-Bruteforce:** Players have a **5-second global cooldown** between flag attempts to prevent spamming.

-----

## 3\. Command Reference

### 🛡️ Admin Commands (Managers Only)

*All admin commands are Slash Commands (`/`).*

| Command | Usage | Description |
| :--- | :--- | :--- |
| **/create** | `/create [id] [points] [flag] [cat]` | Adds a challenge to the database. (Status: Unposted) |
| **/post** | `/post [id] [channel]` | Publishes a created challenge to a Discord channel. |
| **/edit** | `/edit [id] [points/flag]` | Fixes typos or values. **Only works if not posted yet.** |
| **/delete** | `/delete [id]` | **DANGER:** Deletes a challenge and **removes points** from everyone who solved it. |
| **/list** | `/list` | Shows a list of all challenges and their status (🟢 Posted / 🔴 Unposted). |
| **/show** | `/show [id]` | Reveals hidden details (flag, image URL) for a specific challenge. |
| **/export** | `/export` | Downloads the full `ctf_data.db` database (Backups). |
| **/import\_db** | `/import_db [file]` | Uploads a `.db` file to **restore** the entire event state (Emergency only). |

### 🕵️ Agent Commands (Players)

| Command | Description |
| :--- | :--- |
| **/profile** | View personal Rank, Score, and Flag Count. |
| **/help** | Shows the "Agent Field Manual" (Instructions). |
| **[Button]** | Players click "Submit Flag" on mission cards to play. |

-----

## 4\. Hosting & Data Safety (Crucial)

Since you are hosting on **Discloud** (or any cloud VPS), you must protect your database (`ctf_data.db`) from being overwritten.

### A. The `.discloudignore` File

Create a file named `.discloudignore` in your main folder and add this line:

```text
ctf_data.db
```

**Why?** This tells Discloud: "When I upload new code, **DO NOT** replace the live database with the empty one on my computer."

### B. The Update Workflow (How to restart safely)

When you need to update the bot's code:

1.  **Backup First:** Run `/export` in Discord and save the file.
2.  **Upload Code:** Upload your changes to Discloud (ensure `.discloudignore` is present).
3.  **Restart:** Restart the bot via the dashboard.
4.  **Restore (If needed):** If the database happens to be empty after restart, run `/import_db` and upload your backup file.

-----

## 5\. Troubleshooting

**Q: The Leaderboard isn't appearing?**

  * Check the `LEADERBOARD_CHANNEL_ID` in `player.py`. It must match the ID of the channel exactly.
  * Make sure the bot has permission to **Send Messages** and **Embed Links** in that channel.
  * Wait 60 seconds; it runs on a 1-minute loop.

**Q: "Application Command failed" error?**

  * Run the manual command `!fix_commands` in the server (not a slash command, just type it in chat).
  * Wait 10 seconds, then refresh your Discord (`Ctrl + R`).

**Q: Commands not appearing after inviting bot to server?**

  * Run the manual command `!upload` in the server (not a slash command, just it in chat).
  * Wait till it says DONE, then refresh your Discord (`Ctrl + R`).

**Q: Images aren't showing on challenges?**

  * Ensure the `image_url` you provided ends in `.png`, `.jpg`, or `.gif`. Discord cannot embed generic website links as images.
