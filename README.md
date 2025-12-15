# 🛡️ CTF Bot: Feature Documentation

## 1. 👮 Administrator Control (Mission Control)

Authorized personnel only. Used to manage the warfare infrastructure.

### Challenge Management

#### Create Missions (`/create`)

Define a unique Challenge ID (e.g., `WEB-01`), set Base Points (e.g., 100), set the Category (Web, Crypto, Pwn, etc.), set the secret Flag, and optionally add a Banner Image URL for visual flair.

#### Post Missions (`/post`)

- **Target Channel**: Choose exactly where the challenge appears (or default to current).
- **Dual Descriptions**:
  - **Objective**: The story/task explanation.
  - **Connection Info**: (Optional) A separate, copyable box for IPs, ports, or links.
- **File Attachments**: Upload binaries or zips. These are sent as standalone messages immediately after the mission card for easy downloading.
- **Smart Embeds**: Uses copy-friendly code blocks (\`\`\`\`text\`) for descriptions.

#### List Missions (`/list`)

- View all configured challenges.
- See status indicators: 🟢 Posted (Live) or 🔴 Unposted (Hidden).

#### Delete Missions (`/delete`)

- **Nuclear Option**: Deletes the challenge from the database.
- **Clean Up**: Automatically deletes the mission message from the channel.
- **Economy Balancing**: Automatically deducts points (Base + Bonus) from every user who solved it, keeping the scoreboard fair.

## 2. 🕵️ Player Experience (Agent Interface)

Features available to all participants.

### Submission System

- **One-Click Entry**: Users click a generic green "🚩 Submit Flag" button.
- **Private Modals**: A pop-up form appears to enter the flag (prevents others from seeing the answer).
- **Instant Feedback**:
  - 🎉 **Success**: Shows points earned and bonus details.
  - ❌ **Fail**: "Incorrect Flag" warning.
  - ⚠️ **Duplicate**: Prevents re-submitting solved challenges.
- **Anti-Brute Force**: A 5-second cooldown prevents spamming guesses.

### Live Intel (Leaderboards)

#### Global Standings

- A "Master Leaderboard" that auto-updates every 1 minute.
- Displays the Top 15 Agents.
- Rank icons: 👑 (1st), 🥈 (2nd), 🥉 (3rd).

#### Mission Specific Intel (The Challenge Card)

- **🩸 First Blood**: A prestigious field on the card showing the very first solver.
- **📜 Live Solvers List**: As more people solve it, their names appear in a list below the First Blood.
- **Pagination**: Automatically creates new "pages" in the embed if many users solve a challenge.

### Agent Dossier

#### Profile Command (`/profile`)

- View your own (or another agent's) stats.
- Displays: Rank (e.g., #5), Total Score, and Flags Captured.
- Personalized with the user's avatar and color.

## 3. 💰 Scoring & Economy

How the points are calculated.

- **Base Score**: The fixed value of the challenge (e.g., 100 pts).
- **First Blood Bonuses**: Dynamic rewards for speed.
  - 🥇 **1st Place**: +50 Points
  - 🥈 **2nd Place**: +25 Points
  - 🥉 **3rd Place**: +10 Points
- **Smart Updates**: If a challenge card is updated (e.g., a new solver), the bot smartly preserves the original "Bounty" and "Category" fields while updating the solver list.

## 4. ⚙️ Technical Specifications

- **Database**: SQLite (`ctf_data.db`) for lightweight, reliable data storage.
- **Persistence**: Leaderboard message IDs and Challenge message IDs are stored, allowing the bot to resume updates even after a restart.
- **Language**: Python 3 (using `discord.py`).
- **UI**: Uses Discord's modern Embeds, Buttons, Modals, and Slash Commands.
