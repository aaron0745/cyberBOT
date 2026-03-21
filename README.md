# 🤖 cyberBOT: High-Performance Discord CTF Engine

**cyberBOT** is a professional-grade, asynchronous Capture The Flag (CTF) engine designed for Discord. Engineered for maximum performance on mobile (Termux) and desktop (Kali Linux) environments, it features automated scheduling, persistent watchdogs, and millisecond-accurate tie-breaking.

---

## 🚀 Key Features

*   **Set & Forget Scheduling:** Queue missions and file uploads weeks in advance. Automated deployment at the exact `start_time`.
*   **Anti-Deletion Watchdog:** If a mission post is deleted, cyberBOT detects it and re-posts it instantly, preserving the original deadline.
*   **Dynamic Rank Roles:** Configure unlimited point-based milestones via commands (e.g., *Novice* @ 100, *Expert* @ 1000).
*   **Fair Economics:** Recursive refund system. Deleting a mission or a hint automatically restores points to all affected players.
*   **Millisecond Precision:** Powered by asynchronous SQLite with `REAL` timestamps for mathematically perfect "First Blood" tie-breaking.
*   **Dual-Stream Logging:** Advanced operational visibility. Correct solves and collusion warnings go to a dedicated channel, while every failed attempt (including the user and the exact wrong flag submitted) is logged to another.
*   **Persistent Architecture:** Optimized with **WAL Mode** and persistent connections to prevent database lag on ARM/mobile hardware.
*   **Live-Swap Restorations:** Import database backups via Discord without rebooting the engine.

---

## 🛠️ Installation & Setup

### 1. Prerequisites
Ensure you have Python 3.9+ and Pip installed.

**Kali / Debian / Linux:**
```bash
sudo apt update && sudo apt install python3 python3-pip python3-venv -y
```

**Termux (Android):**
```bash
pkg update && pkg upgrade
pkg install python python-pip
```

### 2. Deployment
```bash
# Clone the repository and enter the directory
cd cyberBOT

# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 3. Configuration (.env)
Create a `.env` file in the root directory (see `.env.example`):
```ini
DISCORD_TOKEN=your_bot_token_here
GUILD_ID=your_server_id_here
```
*   **Note:** The `GUILD_ID` is required for **Instant Guild Sync**, bypassing Discord's 1-hour global command cache delay.

---

## 🎮 Operational Protocols

### Administrator Commands (Operational Control)
*   **/setup:** Link leaderboard, challenge logs, wrong submissions, and general channels.
*   **/set_rank_role:** Define a custom point threshold for any role.
*   **/post:** Schedule a mission with files (Format: `DD/MM HH:MM`).
*   **/edit:** Comprehensive modification of any mission attribute (renaming IDs, changing points, updating deadlines).
*   **/delete:** Remove a mission and process recursive point refunds.
*   **/wipe_all:** **NUCLEAR**: Reset the entire database and local storage for a new season.

### Agent Commands (Player Operations)
*   **/help:** Detailed field manual for agents and admins.
*   **/profile:** View your procedurally generated Agent ID card and standings.
*   **/leaderboard:** Interactive, paginated global standings.

---

## 🧪 Scoring & Mechanics

*   **Fixed Base + First Blood:**
    *   🥇 **1st Solver:** Base + 50 pts
    *   🥈 **2nd Solver:** Base + 25 pts
    *   🥉 **3rd Solver:** Base + 10 pts
*   **Anti-Cheat:** Automatic collusion detection flags solvers who capture the same flag within 60 seconds of each other.
*   **High-Precision Standings:** Ties are decided by who reached the point total first, measured down to the millisecond.

---

## 📦 Database & Maintenance

cyberBOT uses **`bot.db`** (SQLite). 
*   **Export:** Use `/export` to download a full backup.
*   **Import:** Use `/import` to live-swap the database with a backup file.
*   **Hardware Optimization:** WAL (Write-Ahead Logging) is enabled by default for concurrent I/O stability on Android/Termux.

---

## 📚 Official Documentation
A complete distribution-ready LaTeX manual is available in the repository as **`CTF_Bot_Manual.tex`**. This document contains detailed TikZ diagrams, architectural schemas, and full deployment protocols.

---
**Developed for Peak Performance. Happy Hacking.**
