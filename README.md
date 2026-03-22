# 🛡️ cyberBOT 2.0: The Ultimate CTF Engine

cyberBOT 2.0 is a high-performance, asynchronous Discord bot designed for hosting Capture The Flag (CTF) competitions. It features a modern dossier-style profile system, automated role progression, and a robust administrative suite.

---

## 🚀 1. Rapid Deployment Guide

### **System Requirements**
*   Python 3.10 or higher
*   A Discord Bot Token (via [Discord Developer Portal](https://discord.com/developers/applications))
*   `GUILD_ID` of your server (Enable Developer Mode in Discord to find this)

### **Installation**
1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/your-repo/cyberBOT.git
    cd cyberBOT
    ```
2.  **Initialize Environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```
3.  **Configure Environment:**
    Rename `.env.example` to `.env` and fill in:
    *   `DISCORD_TOKEN`: Your bot token.
    *   `GUILD_ID`: The server ID for instant command syncing.
4.  **Launch:**
    ```bash
    python3 main.py
    ```

---

## 📂 2. Project Architecture

### **Core Components**
*   `main.py`: The engine core. Handles event loops, database initialization (`aiosqlite`), and global error handling.
*   `cogs/admin.py`: Mission control. Handles challenge creation, scheduling, hint management, and backups.
*   `cogs/player.py`: The Agent interface. Handles profile generation, leaderboard logic, and flag submissions.
*   `bot.db`: SQLite database using WAL (Write-Ahead Logging) for high concurrency.

### **Database Schema**
*   `flags`: Stores challenge data (ID, Points, Flag, Category, Deadlines).
*   `solves`: Records every capture with millisecond timestamps for tie-breaking.
*   `scores`: Persistent player leaderboard data.
*   `role_rewards`: Mapping of point milestones to Discord roles.
*   `config`: Stores server-specific settings (Channel IDs, Leaderboard Message IDs).

---

## 🕵️ 3. Premium Features

### **Dossier Profile Cards**
Each Agent receives a high-resolution (**1800x700**) ID card via `/profile`.
*   **Aesthetic:** Dark Charcoal folder theme with a rotated "CLASSIFIED" stamp.
*   **Neon HUD:** Glowing borders and nodes that change color based on the Agent's Rank.
*   **Specialization Tags:** Top-right HUD boxes showing recent solve categories (`WEB`, `CRY`, `PWN`, etc.).
*   **Clearance Progression:** A progress bar at the bottom showing the journey to the next milestone.
*   **Easter Egg:** Inspecting the bot (`/profile @bot`) reveals the **[ROOT]** profile with `KERNEL` stats and an `ARCHITECT` signature.

### **Mission Control 2.0**
*   **Automated Posting:** Schedule missions to appear at a specific date/time.
*   **Recursive Refunds:** Deleting a mission or hint automatically restores spent points to all players.
*   **Anti-Deletion:** If a mission post is accidentally deleted, the bot will automatically re-post it.

---

## 🛠️ 4. Administrative Protocols

### **Setup Flow**
1.  Run `/setup` to link your **Leaderboard**, **Logs**, and **General** channels.
2.  Use `/set_rank_role` to define milestones (e.g., 500 pts = "Senior Agent").
3.  Create missions via `/create`. You must use the official dropdown categories.
4.  Post or schedule them using `/post`.

### **Backup & Recovery**
*   **`/export`**: Download the entire database as a `.db` file.
*   **`/import`**: Restore from a backup file with zero downtime.

---

## ⚠️ 5. Troubleshooting
*   **429 Rate Limit:** Normal during startup if you restart many times. Wait 15 seconds.
*   **Missing Fonts:** Ensure `font.ttf` is in the root directory for profile rendering.
*   **Invalid GUILD_ID:** The bot will warn you in the console. Ensure it's a pure number.

---
*Created for SG-CTF. Managed by the ARCHITECT.*
