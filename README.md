# 🛡️ cyberBOT: The Definitive CTF Engine

cyberBOT is a professional-grade, asynchronous Discord platform engineered for high-stakes Capture The Flag (CTF) competitions. It transforms a standard Discord server into an immersive, automated tactical environment where Agents compete for digital supremacy.

---

## 👁️ 1. Project Vision
The core philosophy of cyberBOT is **Immersion through Automation**. Unlike standard CTF bots, cyberBOT focuses on a "Game-Master" aesthetic, providing players with high-resolution visual identities and administrators with a self-healing mission infrastructure.

### **Core Pillars:**
*   **Visual Identity:** Dynamic, high-resolution Agent Dossiers that evolve with player progress.
*   **Operational Stability:** An asynchronous architecture built to handle high-concurrency submissions without lag.
*   **Autonomous Management:** Self-healing mission posts and automated role promotion engines.

---

## 🚀 2. System Capabilities

### **The Agent Experience**
*   **Dossier System:** Every player is assigned a unique, 1800x700 ID card (`/profile`) featuring their rank, specialty tags, and clearance progress.
*   **Real-time Intel:** Interactive, paginated leaderboards (`/leaderboard`) with millisecond-accurate tie-breaking.
*   **Specialization Tracking:** The system monitors recent solves to assign specialized HUD tags (WEB, CRYPTO, PWN, etc.) to Agent profiles.

### **Mission Control (Admin)**
*   **Dynamic Scheduling:** Missions can be posted instantly or scheduled for future deployment with automated start/end times.
*   **Asset Management:** Support for file attachments and external image URLs for every challenge.
*   **Recursive Economy:** A smart refund system that restores points to players automatically if a hint or mission is deleted.
*   **Anti-Deletion Protocol:** The bot monitors its own mission posts; if a challenge message is deleted, the bot immediately re-posts it to maintain competition integrity.

---

## ⚙️ 3. Technical Foundation
*   **Language:** JavaScript (Node.js v20+)
*   **Library:** Discord.js v14 (Slash Command Optimized)
*   **Database:** MongoDB via Mongoose
*   **Architecture:** Express.js keep-alive integration for 24/7 cloud hosting on platforms like Render.
*   **Imaging:** Python script (`draw_profile.py`) utilizing PIL for dynamic 1800x700 canvas rendering.

---

## 🛠️ 4. Operational Commands

### **Agent Protocols**
*   `/profile` - Generate high-res Agent ID card.
*   `/leaderboard` - View global standings.
*   `/about` - Display system specs and credits.
*   `/help` - Access the field manual.

### **Mission Protocols**
*   `/create` - Register a new mission in the database.
*   `/post` - Deploy a mission to a channel (Manual or Scheduled).
*   `/edit` - Modify mission parameters (Flag, Points, Category).
*   `/delete` - Remove a mission and process recursive refunds.
*   `/list` - View the status of all missions (Posted/Draft).
*   `/show` - Reveal the capture flag and internal mission data.

### **Network Protocols**
*   `/setup` - Configure system channels and the Champion role.
*   `/set_rank_role` - Define auto-promotion point milestones.
*   `/revoke` - Manually remove a solve and deduct points.
*   `/add_hint` / `/remove_hint` - Manage purchasable clues.
*   `/ban_user` / `/unban_user` - Manage network access.
*   `/export` / `/import` - Database JSON backup and zero-downtime recovery.
*   `/wipe_all` - Complete data purge (Nuclear Option).

---

## 📥 5. Installation & Setup
1.  **Environment:** Run `npm install` to install Node.js dependencies.
2.  **Configuration:** Rename `.env.example` to `.env` and fill in your `DISCORD_TOKEN`, `CLIENT_ID`, `GUILD_ID`, and `MONGODB_URI`.
3.  **Slash Commands:** Run `node deploy-commands.js` to register all slash commands globally.
4.  **Execution:** Run `npm start` to ignite the bot and activate the keep-alive server.

---
*Developed for SG-CTF. Managed by the ARCHITECT OF THE SIMULATION.*
