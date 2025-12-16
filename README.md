# 📘 Discord CTF Bot: Operator's Manual

## Part 1: Discord Developer Setup

Before running the code, you must create the "Bot User" on Discord and get the keys.

### 1. Create the Application

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications).
2. Click **"New Application"** (Top Right).
3. Name it (e.g., "CTF Commander") and click **Create**.

### 2. Configure the Bot & Intents (Critical!)

1. Click the **Bot** tab in the left menu.
2. **Username:** Set the name users will see.
3. **Privileged Gateway Intents:** Scroll down to this section. You **MUST** enable these three switches for the bot to work:
   * ✅ **Presence Intent** (To set status like "Playing Capture The Flag")
   * ✅ **Server Members Intent** (To track user leaderboards and bans)
   * ✅ **Message Content Intent** (To read `!upload` commands)
4. Click **Save Changes**.

### 3. Get the Token

1. On the **Bot** page, look for the **"Token"** section.
2. Click **Reset Token**, then **Copy**.
3. *Paste this into your `.env` file immediately (see Part 2).*

### 4. Invite to Server

1. Click **OAuth2** -> **URL Generator** in the left menu.
2. **Scopes:** Check these two boxes:
   * ✅ `bot`
   * ✅ `applications.commands` (Required for Slash Commands)
3. **Bot Permissions:**
   * The easiest option is to check **Administrator**.
   * *If you want restricted permissions, it needs:* `Send Messages`, `Embed Links`, `Attach Files`, `Manage Messages` (to delete older posts), `Read Message History`.
4. Copy the **Generated URL** at the bottom and paste it into your browser to invite the bot.

---

## Part 2: Installation & Configuration

### 1. Folder Structure

Ensure your project folder looks exactly like this:

```text
/CTF-Bot
  ├── .env                 # Stores your Token
  ├── main.py              # The brain (Database & Sync)
  ├── cogs/
  │   ├── admin.py         # Admin commands
  │   └── player.py        # Player commands & Logic
```

### 2. The `.env` File

Create a file named `.env` and paste your token inside:

```ini
DISCORD_TOKEN=MTE2Nz... (your token here) ...
```

### 3. Install Requirements

Open your terminal/command prompt and install the library:

```bash
pip install discord.py python-dotenv
```

### 4. Launch

Run the bot:

```bash
python main.py
```

*You should see:* `✅ Logged in as: CTF Commander`

---

## Part 3: Maintenance Commands (Prefix)

These commands use the `!` prefix and are used to "wake up" the bot if Slash Commands (`/`) are not appearing.

| Command | Usage | Description |
| --- | --- | --- |
| **`!upload`** | `!upload` | **Quick Sync.** Pushes the latest slash commands to the current server. Use this if you just started the bot and don't see `/create`. |
| **`!fix_commands`** | `!fix_commands` | **Nuclear Option.** Wipes all commands globally and re-uploads them. Use this if commands are "doubled" or refusing to update. |

> **Note:** These commands are restricted to Administrators only in the code.

---

## Part 4: Admin Commands (Slash)

These commands are only visible to users with **Administrator** permissions.

### Challenge Management

* **/create**
  * Creates a challenge in the database.
  * *Inputs:* `id` (unique name), `points`, `flag`, `category`.

* **/add_hint**
  * Adds a clue that players can buy.
  * *Inputs:* `challenge_id`, `text`, `cost`.

* **/post**
  * **The most important command.** Publishes the challenge to a Discord channel with the "Submit" and "Hint" buttons.
  * *Inputs:* `challenge_id`, `description`, `file` (optional).

* **/edit**
  * Updates a challenge (points, flag, etc.) without deleting it.

* **/delete**
  * Permanently deletes a challenge and its logs from the database.

* **/list**
  * Shows all created challenges and their status (Posted vs Draft).

* **/show**
  * Reveals the secret flag and details of a specific challenge (Admin eyes only).

### Judge / Moderation

* **/revoke** `user` `challenge_id`
  * Removes a specific solve from a player (e.g., if they cheated). Recalculates their score immediately.

* **/ban_user** `user`
  * Blacklists a user. They can no longer submit flags, even if they click the button.

### System / Backup (New)

* **/export**
  * **Backup Command.** Generates and sends a downloadable copy of the database (`ctf_data.db`).
  * *Use Case:* Run this regularly to save your scoreboard and challenges.

* **/import** `file`
  * **Restore Command.** Uploads a `.db` file to **overwrite** the current database.
  * *Warning:* This wipes the current live data and replaces it with the backup file.
  * *Use Case:* Restoring data after a crash or moving the bot to a new server.

---

## Part 5: Player Commands & Features

These are visible to everyone.

* **/help**
  * Shows the manual. (Admins see extra controls; Players only see instructions).

* **/profile** `user` (optional)
  * Shows Rank, Score, and Solve count.

### Interactive Features (Buttons)

Players interact via buttons on the challenge posts, not commands.

1. **[ 🚩 Submit Flag ]**
   * Opens a popup text box (Modal).
   * Verifies flag instantly.
   * **Cooldown:** 5 seconds between guesses (Anti-Spam).
   * **Logic:** Preventing duplicate solves.

2. **[ 💡 Hints ]**
   * Shows a menu of hints for that challenge.
   * Buying a hint deducts points from the user's profile immediately.

---

## Part 6: Scoring Mechanics

This bot uses a **Fixed Base + First Blood Bonus** system.

* **Base Points:** Determined by you when you `/create` (e.g., 500 pts).
* **Bonuses:**
  * 🥇 **1st Solver:** Base + **50** pts
  * 🥈 **2nd Solver:** Base + **25** pts
  * 🥉 **3rd Solver:** Base + **10** pts
  * All subsequent solvers get Base points only.

* **Audit Logging:**
  * The bot logs every Flag Capture, Hint Purchase, and Failed Attempt to your configured `LOG_CHANNEL_ID`.
  * **Anti-Cheat Logic:** If Player A and Player B solve the same hard challenge within 60 seconds of each other, the bot flags it as "Suspected Flag Sharing" in the logs.
