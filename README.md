# 🚩 CyberBOT: Discord CTF Manager
> *A robust, database-driven Discord bot for hosting Capture The Flag competitions.*

CyberBOT simplifies managing CTF events directly within Discord. It features automated scoring, dynamic leaderboards, category management, and a file-based challenge system.

---

## 🛠️ Installation & Setup

### **1. Create the Application**
1.  Go to the [Discord Developer Portal](https://discord.com/developers/applications).
2.  Click **New Application** and give your bot a name (e.g., `CyberBOT`).
3.  Navigate to **Settings > Bot** in the sidebar.
4.  Click **Reset Token** (or Generate Token) and **COPY IT immediately**. You will not see it again.

### **2. Configure Permissions (Important!)**
While still in the **Bot** tab, scroll down to **Privileged Gateway Intents** and enable these three:
* ✅ **Presence Intent**
* ✅ **Server Members Intent**
* ✅ **Message Content Intent**

Save your changes.

### **3. Invite the Bot**
1.  Navigate to **OAuth2 > URL Generator**.
2.  **Scopes:** Select `bot` and `applications.commands`.
3.  **Bot Permissions:** Select `Administrator`.
4.  Copy the generated URL at the bottom and paste it into your browser to invite the bot to your server.

---

## ⚙️ Local Configuration

### **1. Set the Token**
Create a file named `.env` in the root folder (same folder as `main.py`) and paste your token:

```ini
DISCORD_TOKEN=paste_your_long_token_here
```
### **2. Customization (Optional)**

**📍 Set Leaderboard Channel:**
Open `cogs/player.py` and find `LEADERBOARD_CHANNEL_ID`.
* Replace the ID with the Channel ID where you want the live scoreboard to appear.
* *Note: Right-click a channel in Discord > Copy ID (Developer Mode must be on).*

**🖼️ Set Banner Image:**
Open `cogs/admin.py` and find `BANNER_URL`.
* Upload your banner image to a private Discord channel.
* Right-click the image > **Copy Link**.
* Paste the URL inside the quotes.

---

## 🚀 Running the Bot

### **1. Install Dependencies**
Open your terminal in the bot folder and install the required libraries (if you haven't already):
```bash
pip install -r requirements.txt
```
(Ensure discord.py and python-dotenv are installed).

### **2. Launch**
Run the bot using Python:
```bash
python main.py
```
If successful, you will see:

```text
---------------------------------
✅ Logged in as: CyberBOT#8317
---------------------------------
📦 Loaded: player.py
📦 Loaded: admin.py
```


### **3. Sync Commands (First Run Only)**
Go to your Discord server and type this command to initialize the menu:
`!upload`

*Press `Ctrl + R` (Windows) or `Cmd + R` (Mac) to refresh your Discord client if commands don't appear immediately.*

---

## 🎮 Command Usage

### **Admin Commands**
*(Only accessible to Administrators)*

| Command | Description |
| :--- | :--- |
| `/create` | **Create a new challenge** in the database.<br>Inputs: `id`, `flag`, `points`, `category`. |
| `/list` | **View all challenges** currently in the database. |
| `/post` | **Publish a challenge** to a channel for players to see.<br>Inputs: `channel`, `id`, `description`, `file` (optional). |

### **Player Features**
* **🚩 Submit Flag:** Click the green button on any challenge post to open the submission box.
* **🏆 Live Leaderboard:** Automatically updates every 60 seconds in the configured channel.
* **🩸 First Blood:** The challenge post updates automatically to honor the first solver.

---

## ⚠️ Troubleshooting
* **"Application did not respond"**: The bot might have crashed. Check your terminal for errors.
* **Commands not showing up**: Run `!upload` again and refresh your Discord app (`Ctrl + R`).
* **Database Errors**: If you change the code structure significantly, delete `ctf_data.db` and restart to rebuild the database.
