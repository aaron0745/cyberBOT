# 🚩 Discord CTF Manager Bot - Documentation

## 🔍 System Analysis & Features

### 1. 👮 Administrator Control (Mission Control)

#### Challenge Management:
- **Creation (/create)**: Add challenges with a unique ID, point value, secret flag, category, and an optional Banner Image URL.
- **Smart Posting (/post)**: Deploy challenges to a specific channel.
- **Connection Info**: Supports a separate, copy-paste friendly field for IPs/Ports.
- **File Attachments**: You can attach binaries or ZIP files directly to the command, and the bot will upload them with the challenge card.
- **Inventory (/list)**: View all challenges and their status (🟢 Posted or 🔴 Unposted).

#### Economy Integrity (/delete):
- When a challenge is deleted, the bot automatically calculates and deducts points from every user who solved it.
- It removes the challenge from the database and deletes the message from the Discord channel.

#### Command Management:
- **!upload**: Instantly syncs Slash Commands to the current server (Guild) for immediate testing.
- **!fix_commands**: A troubleshooting tool that wipes and re-uploads commands if they get stuck.

### 2. 🕵️ Player Experience (Agent Interface)

#### Secure Submission:
- Users click a "🚩 Submit Flag" button.
- A Modal (Pop-up) appears for private input (prevents flag leaking).

#### Anti-Cheat & Fairness:
- **Cooldown**: A 5-second cooldown per user to prevent brute-force attacks.
- **Duplicate Check**: Prevents users from submitting the same flag twice.

#### Agent Dossier (/profile):
- Generates a dynamic Embed showing the user's Rank, Total Score, and Flags Captured.
- Uses the user's avatar and profile color.

### 3. 💰 Scoring & Bonuses

- **Base Score**: The fixed points assigned to the challenge.

#### First Blood System:
- 🥇 **1st Solver**: +50 Bonus Points.
- 🥈 **2nd Solver**: +25 Bonus Points.
- 🥉 **3rd Solver**: +10 Bonus Points.

### 4. 📊 Live Intelligence (Real-time UI)

#### Global Leaderboard:
- A dedicated message that updates every 1 minute.
- Shows the Top 15 players with medals (👑, 🥈, 🥉).

#### Dynamic Challenge Cards:
- When a user solves a challenge, the original post updates automatically.
- **First Blood Field**: Displays the name of the very first solver.
- **Solvers List**: Lists subsequent solvers, paginated (creates new pages if the list gets long).

## 🛠️ Installation & Setup Guide

### Step 1: Prerequisites
- Python 3.8+ installed.
- A Discord Bot Token from the Developer Portal.
- Paste the Token inside a .env file(as DISCORD_TOKEN=your_token)
- Enable Message Content Intent and Server Members Intent in the portal.

### Step 2: Project Structure
Ensure your folder looks exactly like this:

```
project/
├── cogs
│   ├── admin.py
│   └── player.py
├── .env
├── main.py
└── requirements.txt
```
