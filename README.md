Here is a polished, professional version of your documentation, formatted in Markdown. You can copy this directly into a `README.md` file for your GitHub repository or project folder.

I have cleaned up the structure, added syntax highlighting, and clarified a few sections to make it easier for your team to read.

---

```markdown
# 📘 CTF Bot: Operator's Manual

This manual covers the installation, configuration, and operation of the Discord CTF Bot. It includes setup instructions for the Discord Developer Portal and a complete command reference for Admins and Players.

## 📋 Table of Contents
1. [Developer Setup](#part-1-discord-developer-setup)
2. [Installation](#part-2-installation--configuration)
3. [Maintenance Commands](#part-3-maintenance-commands)
4. [Admin Commands](#part-4-admin-commands)
5. [Player Features](#part-5-player-features)
6. [Scoring System](#part-6-scoring-mechanics)

---

## Part 1: Discord Developer Setup
*Before running the code, you must create the "Bot User" on Discord and generate credentials.*

### 1. Create the Application
1. Go to the [Discord Developer Portal](https://discord.com/developers/applications).
2. Click **"New Application"** (Top Right).
3. Name your application (e.g., `CTF Commander`) and click **Create**.

### 2. Configure Intents (Critical)
1. Click the **Bot** tab in the left menu.
2. Scroll down to **Privileged Gateway Intents**. You **MUST** enable these three switches:
    * ✅ **Presence Intent** (Sets status like "Playing CTF")
    * ✅ **Server Members Intent** (Tracks leaderboard and bans)
    * ✅ **Message Content Intent** (Reads prefix commands like `!upload`)
3. Click **Save Changes**.

### 3. Get the Token
1. On the **Bot** page, find the **"Token"** section.
2. Click **Reset Token**, then **Copy**.
3. *Save this token immediately—you will need it for the `.env` file.*

### 4. Invite to Server
1. Click **OAuth2** → **URL Generator** in the left menu.
2. **Scopes:** Check these two boxes:
    * `bot`
    * `applications.commands`
3. **Bot Permissions:**
    * Select **Administrator** (Recommended for easiest setup).
    * *Minimum Requirements:* Send Messages, Embed Links, Attach Files, Manage Messages, Read Message History.
4. Copy the **Generated URL** at the bottom and open it in your browser to invite the bot.

---

## Part 2: Installation & Configuration

### 1. Folder Structure
Ensure your project directory looks exactly like this:

```text
/CTF-Bot
  ├── .env                 # Stores your Bot Token
  ├── main.py              # Core logic (Database & Sync)
  ├── cogs/
  │    ├── admin.py        # Admin slash commands
  │    └── player.py       # Player commands & Logic

```

###2. The `.env` FileCreate a file named `.env` in the root folder and paste your token:

```ini
DISCORD_TOKEN=your_token_goes_here_no_quotes

```

###3. Install RequirementsOpen your terminal and install the required Python libraries:

```bash
pip install discord.py python-dotenv

```

###4. Launch the BotRun the main script:

```bash
python main.py

```

> **Success:** You should see `✅ Logged in as: CTF Commander` in your console.

---

##Part 3: Maintenance Commands*These commands use the `!` prefix. They are used to "wake up" the bot if Slash Commands (`/`) are not appearing.*

| Command | Usage | Description |
| --- | --- | --- |
| **Quick Sync** | `!upload` | Pushes the latest commands to the current server. Use this if you just started the bot and don't see `/create`. |
| **Full Reset** | `!fix_commands` | **Nuclear Option.** Wipes all commands globally and re-uploads them. Use this if commands are duplicated or refusing to update. |

> **Note:** These commands are restricted to **Administrators** only.

---

##Part 4: Admin Commands*Slash commands (`/`) visible only to users with Administrator permissions.*

###🛡️ Challenge Management* **/create**
* Creates a challenge entry in the database.
* *Inputs:* `id` (unique), `points`, `flag`, `category`.


* **/add_hint**
* Adds a clue that players can buy.
* *Inputs:* `challenge_id`, `text`, `cost`.


* **/post**
* **Primary Command:** Publishes the challenge to a Discord channel with interactive buttons.
* *Inputs:* `challenge_id`, `description`, `file` (optional).


* **/edit**
* Modifies challenge details (points, flag, etc.) without deleting it.


* **/delete**
* Permanently removes a challenge and its logs from the database.


* **/list**
* Displays a list of all challenges and their status (Posted vs Draft).


* **/show**
* Reveals the secret flag and details of a specific challenge (Admin eyes only).



###⚖️ Moderation* **/revoke** `user` `challenge_id`
* Removes a specific solve from a player. Recalculates their score immediately.


* **/ban_user** `user`
* Disqualifies a user. They will be blocked from submitting flags.



---

##Part 5: Player Features*Commands and interactions available to all users.*

###Commands* **/help**
* Displays the manual. (Admins see the Control Panel; Players see instructions).


* **/profile** `user` *(optional)*
* Displays Rank, Total Score, and Solve Count.



###Interactive ButtonsPlayers primarily interact via buttons on the challenge posts, not commands.

1. **[ 🚩 Submit Flag ]**
* Opens a popup text box (Modal) to enter the flag.
* **Instant Verification:** Checks flag immediately.
* **Cooldown:** 5 seconds between guesses to prevent spam.


2. **[ 💡 Hints ]**
* Displays available hints.
* **Cost:** Buying a hint automatically deducts points from the user's score.



---

##Part 6: Scoring MechanicsThe bot uses a **Fixed Base + First Blood Bonus** system.

###Point Structure* **Base Points:** Defined during `/create` (e.g., 500 pts).
* **Bonuses:**
* 🥇 **1st Solver:** Base + **100** pts
* 🥈 **2nd Solver:** Base + **50** pts
* 🥉 **3rd Solver:** Base + **25** pts
* *All others:* Base points only.



###Anti-Cheat & Logging* The bot logs every **Flag Capture**, **Hint Purchase**, and **Failed Attempt** to the console (or configured log channel).
* **Duplicate Prevention:** Users cannot solve the same challenge twice.

```

```
