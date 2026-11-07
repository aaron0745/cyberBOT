// profileCard.js
// Draws the agent ID card with @napi-rs/canvas (replaces python_scripts/draw_profile.py).
// Usage: const buffer = await renderProfileCard(data);  // PNG Buffer, 1800x700
const path = require('path');
const { createCanvas, loadImage, GlobalFonts } = require('@napi-rs/canvas');

const FONT_PATH = path.join(__dirname, '..', '..', 'font.ttf');
const FONT = 'CyberFont';
const W = 1800;
const H = 700;

if (!GlobalFonts.registerFromPath(FONT_PATH, FONT)) {
    throw new Error(`profileCard: could not load font at ${FONT_PATH}`);
}

// ---------- small helpers ----------
const rgba = (c, a = 1) => `rgba(${c[0]},${c[1]},${c[2]},${a})`;
const setFont = (ctx, size) => { ctx.font = `${size}px ${FONT}`; };

function chamfer(ctx, x, y, w, h, c) {
    ctx.beginPath();
    ctx.moveTo(x + c, y);
    ctx.lineTo(x + w - c, y);
    ctx.lineTo(x + w, y + c);
    ctx.lineTo(x + w, y + h - c);
    ctx.lineTo(x + w - c, y + h);
    ctx.lineTo(x + c, y + h);
    ctx.lineTo(x, y + h - c);
    ctx.lineTo(x, y + c);
    ctx.closePath();
}

function glowStroke(ctx, color, width, blur, alpha = 1) {
    ctx.save();
    ctx.shadowColor = rgba(color, 0.9);
    ctx.shadowBlur = blur;
    ctx.strokeStyle = rgba(color, alpha);
    ctx.lineWidth = width;
    ctx.stroke();
    ctx.restore();
}

// Text with optional letter spacing, glow, alignment. Baseline = alphabetic.
function text(ctx, str, x, y, { size, color = '#fff', align = 'left', spacing = 0, glow = null, blur = 18 }) {
    ctx.save();
    setFont(ctx, size);
    ctx.letterSpacing = `${spacing}px`;
    ctx.textAlign = align;
    ctx.textBaseline = 'alphabetic';
    if (glow) { ctx.shadowColor = rgba(glow, 0.85); ctx.shadowBlur = blur; }
    ctx.fillStyle = color;
    ctx.fillText(str, x, y);
    ctx.restore();
}

function measure(ctx, str, size, spacing = 0) {
    ctx.save();
    setFont(ctx, size);
    ctx.letterSpacing = `${spacing}px`;
    const w = ctx.measureText(str).width;
    ctx.restore();
    return w;
}

// ---------- theme (same rules as the Python version) ----------
function getTheme(rank, points) {
    const n = parseInt(String(rank).replace('#', ''), 10);
    const rankNum = Number.isNaN(n) ? 999 : n;
    let t = { bg: [14, 17, 21], primary: [0, 255, 230], fill: [0, 40, 40], badgeText: [200, 255, 255], role: 'OPERATIVE' };

    if (points === 999999) t = { bg: [0, 8, 26], primary: [0, 255, 120], fill: [0, 40, 20], badgeText: [150, 255, 200], role: 'SYSTEM CORE' };
    else if (rankNum === 1) t = { ...t, primary: [255, 215, 0], fill: [40, 30, 0], badgeText: [255, 230, 150], role: 'CHAMPION' };
    else if (rankNum === 2) t = { ...t, primary: [229, 228, 226], fill: [45, 45, 50], badgeText: [255, 255, 255], role: 'VANGUARD' };
    else if (rankNum === 3) t = { ...t, primary: [205, 127, 50], fill: [40, 20, 10], badgeText: [255, 200, 180], role: 'CHALLENGER' };
    else if (rankNum >= 4 && rankNum <= 10) t = { ...t, primary: [220, 20, 60], fill: [50, 10, 15], badgeText: [255, 200, 200], role: 'SENTINEL' };
    else if (points === 0) t = { ...t, primary: [120, 120, 125], fill: [30, 30, 35], badgeText: [200, 200, 200], role: 'RECRUIT' };
    return t;
}

const CATEGORIES = {
    WEB: ['WEB', [0, 255, 230]], CRYPTO: ['CRY', [255, 230, 0]], PWN: ['PWN', [255, 0, 80]],
    REV: ['REV', [180, 0, 255]], FORENSICS: ['FOR', [0, 255, 100]], OSINT: ['OSI', [255, 150, 0]],
    MISC: ['MSC', [180, 180, 180]],
};

// ---------- avatar loading ----------
async function getAvatar(url, buffer) {
    try {
        if (buffer) return await loadImage(buffer);
        if (!url) return null;
        const res = await fetch(url, { headers: { 'User-Agent': 'Mozilla/5.0' }, signal: AbortSignal.timeout(5000) });
        if (!res.ok) return null;
        return await loadImage(Buffer.from(await res.arrayBuffer()));
    } catch {
        return null;
    }
}

// ---------- layers ----------
function drawBackground(ctx, t) {
    const { bg, primary } = t;
    ctx.fillStyle = rgba(bg);
    ctx.fillRect(0, 0, W, H);

    // soft colour wash behind avatar + top-right
    let g = ctx.createRadialGradient(300, 335, 20, 300, 335, 700);
    g.addColorStop(0, rgba(primary, 0.16));
    g.addColorStop(1, rgba(primary, 0));
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);

    g = ctx.createRadialGradient(1700, 40, 10, 1700, 40, 600);
    g.addColorStop(0, rgba(primary, 0.07));
    g.addColorStop(1, rgba(primary, 0));
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);

    // grid
    ctx.lineWidth = 2;
    ctx.strokeStyle = 'rgba(120,140,160,0.10)';
    ctx.beginPath();
    for (let x = 0; x <= W; x += 80) { ctx.moveTo(x, 0); ctx.lineTo(x, H); }
    for (let y = 0; y <= H; y += 80) { ctx.moveTo(0, y); ctx.lineTo(W, y); }
    ctx.stroke();

    // grid intersections
    ctx.fillStyle = rgba(primary, 0.22);
    for (let x = 0; x <= W; x += 80) for (let y = 0; y <= H; y += 80) ctx.fillRect(x - 2, y - 2, 4, 4);

    // vignette
    g = ctx.createRadialGradient(W / 2, H / 2, 350, W / 2, H / 2, 1100);
    g.addColorStop(0, 'rgba(0,0,0,0)');
    g.addColorStop(1, 'rgba(0,0,0,0.55)');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);
}

function drawStamp(ctx) {
    ctx.save();
    ctx.translate(1010, 440);
    ctx.rotate((-8 * Math.PI) / 180);
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    setFont(ctx, 210);
    ctx.letterSpacing = '6px';
    ctx.strokeStyle = 'rgba(255,60,60,0.24)';
    ctx.lineWidth = 3;
    ctx.strokeText('CLASSIFIED', 0, 0);
    ctx.fillStyle = 'rgba(255,40,40,0.07)';
    ctx.fillText('CLASSIFIED', 0, 0);
    ctx.lineWidth = 4;
    ctx.strokeStyle = 'rgba(255,60,60,0.18)';
    ctx.strokeRect(-640, -150, 1280, 300);
    ctx.restore();
}

function drawFrame(ctx, t) {
    const p = t.primary;
    // thin inner frame
    ctx.beginPath();
    ctx.rect(20, 20, W - 40, H - 40);
    glowStroke(ctx, p, 2, 12, 0.28);

    // corner brackets (top-left, bottom-right) with glow
    const L = 200;
    ctx.lineWidth = 12;
    ctx.lineCap = 'butt';
    ctx.lineJoin = 'miter';
    ctx.beginPath();
    ctx.moveTo(6, L); ctx.lineTo(6, 6); ctx.lineTo(L, 6);
    glowStroke(ctx, p, 12, 22, 1);
    ctx.beginPath();
    ctx.moveTo(W - 6, H - L); ctx.lineTo(W - 6, H - 6); ctx.lineTo(W - L, H - 6);
    glowStroke(ctx, p, 12, 22, 1);

    // small secondary brackets (top-right, bottom-left)
    ctx.beginPath();
    ctx.moveTo(W - 90, 6); ctx.lineTo(W - 6, 6); ctx.lineTo(W - 6, 90);
    glowStroke(ctx, p, 4, 10, 0.5);
    ctx.beginPath();
    ctx.moveTo(6, H - 90); ctx.lineTo(6, H - 6); ctx.lineTo(90, H - 6);
    glowStroke(ctx, p, 4, 10, 0.5);
}

function drawHeader(ctx, t, userId) {
    const p = t.primary;
    // twin grey bars
    ctx.fillStyle = 'rgba(110,116,122,0.9)';
    ctx.fillRect(40, 34, 10, 66);
    ctx.fillRect(62, 34, 10, 66);

    text(ctx, `ID_REF: ${userId}`, 100, 54, { size: 24, color: rgba(p, 0.6), spacing: 1 });
    text(ctx, 'STATUS: ACTIVE_OPERATIVE', 124, 88, { size: 24, color: rgba(p, 1), spacing: 1 });

    // status dot (the font has no dot glyph)
    ctx.save();
    ctx.shadowColor = 'rgba(0,255,120,0.9)';
    ctx.shadowBlur = 14;
    ctx.fillStyle = 'rgb(0,255,120)';
    ctx.beginPath(); ctx.arc(108, 80, 7, 0, Math.PI * 2); ctx.fill();
    ctx.restore();
}

// Deterministic barcode from the user id, purely decorative
function drawBarcode(ctx, t, userId) {
    const digits = String(userId).replace(/\D/g, '').padEnd(12, '7');
    let x = 490;
    ctx.fillStyle = rgba(t.primary, 0.55);
    for (const ch of digits.slice(0, 14)) {
        const d = Number(ch);
        const bw = 2 + (d % 4);
        ctx.fillRect(x, 40, bw, 50);
        x += bw + 2 + (d % 3);
        if (x > 582) break;
    }
}

function drawAvatar(ctx, t, avatar, displayName) {
    const cx = 300, cy = 335, r = 196;
    const p = t.primary;

    // outer glow disc
    ctx.save();
    ctx.shadowColor = rgba(p, 0.9);
    ctx.shadowBlur = 50;
    ctx.fillStyle = rgba(t.fill);
    ctx.beginPath(); ctx.arc(cx, cy, r + 4, 0, Math.PI * 2); ctx.fill();
    ctx.restore();

    ctx.save();
    ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.clip();
    if (avatar) {
        // cover-fit
        const s = Math.max((r * 2) / avatar.width, (r * 2) / avatar.height);
        const dw = avatar.width * s, dh = avatar.height * s;
        ctx.drawImage(avatar, cx - dw / 2, cy - dh / 2, dw, dh);
        // subtle tint + vignette so any avatar sits in the theme
        const g = ctx.createRadialGradient(cx, cy, r * 0.55, cx, cy, r);
        g.addColorStop(0, 'rgba(0,0,0,0)');
        g.addColorStop(1, 'rgba(0,0,0,0.45)');
        ctx.fillStyle = g; ctx.fillRect(cx - r, cy - r, r * 2, r * 2);
        ctx.fillStyle = rgba(p, 0.07); ctx.fillRect(cx - r, cy - r, r * 2, r * 2);
    } else {
        const g = ctx.createRadialGradient(cx, cy - 40, 10, cx, cy, r);
        g.addColorStop(0, rgba(p, 0.22));
        g.addColorStop(1, rgba(t.fill));
        ctx.fillStyle = g; ctx.fillRect(cx - r, cy - r, r * 2, r * 2);
        const initial = displayName ? displayName[0].toUpperCase() : '?';
        text(ctx, initial, cx, cy + 90, { size: 270, color: rgba(p), align: 'center', glow: p, blur: 30 });
    }
    ctx.restore();

    // solid ring
    ctx.beginPath(); ctx.arc(cx, cy, r + 8, 0, Math.PI * 2);
    glowStroke(ctx, p, 5, 18, 1);

    // dashed outer ring
    ctx.save();
    ctx.setLineDash([70, 24]);
    ctx.beginPath(); ctx.arc(cx, cy, r + 26, 0, Math.PI * 2);
    ctx.strokeStyle = rgba(p, 0.55); ctx.lineWidth = 3; ctx.stroke();
    ctx.restore();

    // compass ticks
    ctx.strokeStyle = rgba(p, 1); ctx.lineWidth = 5;
    for (let a = 0; a < 4; a++) {
        const ang = (a * Math.PI) / 2;
        ctx.beginPath();
        ctx.moveTo(cx + Math.cos(ang) * (r + 18), cy + Math.sin(ang) * (r + 18));
        ctx.lineTo(cx + Math.cos(ang) * (r + 40), cy + Math.sin(ang) * (r + 40));
        ctx.stroke();
    }
}

function drawRolePlate(ctx, t, earnedRole) {
    const x = 100, y = 586, w = 400, h = 66, p = t.primary;
    chamfer(ctx, x, y, w, h, 12);
    const g = ctx.createLinearGradient(x, y, x + w, y);
    g.addColorStop(0, rgba(t.fill, 1));
    g.addColorStop(1, rgba(t.fill, 0.55));
    ctx.fillStyle = g; ctx.fill();
    glowStroke(ctx, p, 3, 10, 0.9);

    let size = 36;
    while (measure(ctx, earnedRole, size, 3) > w - 60 && size > 18) size -= 2;
    text(ctx, earnedRole, x + w / 2, y + h / 2 + size * 0.32, { size, color: rgba(p), align: 'center', spacing: 3 });
}

function drawName(ctx, t, displayName) {
    const name = (displayName || 'UNKNOWN').toUpperCase();
    let size = 130;
    while (measure(ctx, name, size, 2) > 1100 && size > 30) size -= 4;
    text(ctx, name, 600, 150 - (130 - size) * 0.2, { size, color: '#ffffff', spacing: 2, glow: t.primary, blur: 22 });

    // accent underline
    ctx.fillStyle = rgba(t.primary, 0.9);
    ctx.fillRect(600, 164, 90, 5);
    ctx.fillStyle = rgba(t.primary, 0.3);
    ctx.fillRect(698, 165, 1002, 2); // thin trailing rule
}

function drawBadge(ctx, t) {
    const x = 600, y = 190, h = 82, p = t.primary;
    const w = measure(ctx, t.role, 56, 4) + 150;
    chamfer(ctx, x, y, w, h, 22);
    const g = ctx.createLinearGradient(x, y, x + w, y);
    g.addColorStop(0, rgba(t.fill, 1));
    g.addColorStop(1, rgba(t.fill, 0.5));
    ctx.fillStyle = g; ctx.fill();
    glowStroke(ctx, p, 4, 14, 1);

    // diamond marker
    const dx = x + 50, dy = y + h / 2, d = 18;
    ctx.save();
    ctx.shadowColor = rgba(p, 1); ctx.shadowBlur = 16;
    ctx.fillStyle = rgba(p);
    ctx.beginPath(); ctx.moveTo(dx, dy - d); ctx.lineTo(dx + d, dy); ctx.lineTo(dx, dy + d); ctx.lineTo(dx - d, dy); ctx.closePath(); ctx.fill();
    ctx.restore();

    text(ctx, t.role, x + 90, y + h / 2 + 18, { size: 56, color: rgba(t.badgeText), spacing: 4 });
}

function drawCategoryChips(ctx, t, lastCats, points) {
    if (!lastCats || lastCats.length === 0) return;
    const tw = 150, th = 66, tc = 10, gap = 18;
    const total = lastCats.length * tw + (lastCats.length - 1) * gap;
    let x = W - 100 - total;
    const y = 206;

    text(ctx, 'RECENT SOLVES', W - 100, y - 14, { size: 20, color: rgba(t.primary, 0.6), align: 'right', spacing: 3 });

    for (const cat of lastCats) {
        let [label, clr] = CATEGORIES[cat] || [String(cat).slice(0, 3).toUpperCase(), [200, 200, 200]];
        if (points === 999999) {
            if (label === 'SYS') clr = [255, 50, 50];
            else if (label === 'SQL') clr = [50, 255, 50];
            else if (label === 'ENC') clr = [50, 100, 255];
        }
        chamfer(ctx, x, y, tw, th, tc);
        const g = ctx.createLinearGradient(x, y, x, y + th);
        g.addColorStop(0, rgba(clr, 0.18));
        g.addColorStop(1, 'rgba(20,25,30,0.9)');
        ctx.fillStyle = g; ctx.fill();
        glowStroke(ctx, clr, 3, 12, 1);
        text(ctx, label, x + tw / 2, y + th / 2 + 12, { size: 36, color: rgba(clr), align: 'center', spacing: 2 });
        x += tw + gap;
    }
}

// The font's infinity glyph is tiny, so draw a lemniscate as a path instead.
function drawInfinity(ctx, cx, cy, a, p) {
    ctx.beginPath();
    for (let i = 0; i <= 200; i++) {
        const th = (i / 200) * Math.PI * 2;
        const d = 1 + Math.sin(th) ** 2;
        const px = cx + (a * Math.cos(th)) / d;
        const py = cy + (a * Math.sin(th) * Math.cos(th)) / d;
        if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
    }
    ctx.closePath();
    ctx.lineJoin = 'round';
    glowStroke(ctx, [255, 255, 255], 13, 12, 1);
    // soft theme-coloured halo
    ctx.save(); ctx.shadowColor = rgba(p, 0.9); ctx.shadowBlur = 22; ctx.strokeStyle = 'rgba(255,255,255,0.01)'; ctx.lineWidth = 13; ctx.stroke(); ctx.restore();
}

function drawStat(ctx, t, x, y, label, value, points) {
    const w = 340, h = 220, c = 20, p = t.primary;
    chamfer(ctx, x, y, w, h, c);
    const g = ctx.createLinearGradient(x, y, x, y + h);
    g.addColorStop(0, 'rgba(26,32,40,0.92)');
    g.addColorStop(1, 'rgba(12,15,19,0.95)');
    ctx.fillStyle = g; ctx.fill();
    // tint along the top edge
    ctx.save();
    chamfer(ctx, x, y, w, h, c); ctx.clip();
    const tg = ctx.createLinearGradient(x, y, x, y + 70);
    tg.addColorStop(0, rgba(p, 0.18)); tg.addColorStop(1, rgba(p, 0));
    ctx.fillStyle = tg; ctx.fillRect(x, y, w, 70);
    ctx.restore();
    chamfer(ctx, x, y, w, h, c);
    glowStroke(ctx, p, 4, 14, 1);

    text(ctx, label, x + 30, y + 62, { size: 44, color: rgba(p), spacing: 3 });
    ctx.fillStyle = rgba(p, 0.35);
    ctx.fillRect(x + 30, y + 78, w - 60, 2);

    let display = String(value);
    if (points === 999999) {
        if (label === 'RANK') display = '[ROOT]';
        else if (label === 'SCORE') display = '\u221E';
        else if (label === 'FLAGS') display = 'KERNEL';
    }
    if (display === '\u221E') {
        drawInfinity(ctx, x + 30 + 85, y + 150, 85, p);
    } else {
        let size = 112;
        while (measure(ctx, display, size, 1) > w - 60 && size > 30) size -= 4;
        text(ctx, display, x + 30, y + 185 - (112 - size) * 0.25, { size, color: '#ffffff', spacing: 1, glow: p, blur: 10 });
    }

    // little footer pips
    ctx.fillStyle = rgba(p, 0.5);
    for (let i = 0; i < 3; i++) ctx.fillRect(x + w - 30 - i * 14, y + h - 18, 8, 4);
}

function drawProgress(ctx, t, points, nextGoal) {
    const p = t.primary, x = 600, y = 640, w = 1100, h = 22;

    if (!nextGoal) {
        const msg = points === 999999 ? 'ARCHITECT OF THE SIMULATION' : 'MAX CLEARANCE LEVEL ATTAINED';
        const mw = measure(ctx, msg, 46, 4);
        const bx = x + (w - mw) / 2;
        text(ctx, msg, x + w / 2, y + 10, { size: 46, color: rgba(p), align: 'center', spacing: 4, glow: p, blur: 20 });
        ctx.fillStyle = rgba(p, 0.5);
        ctx.fillRect(x, y - 22, (w - mw) / 2 - 24, 3); ctx.fillRect(bx + mw + 24, y - 22, (w - mw) / 2 - 24, 3);
        return;
    }

    const percent = Math.max(0, Math.min(1, points / nextGoal));
    text(ctx, `CLEARANCE PROGRESS: ${Math.floor(percent * 100)}%`, x, y - 18, { size: 32, color: rgba(p), spacing: 2 });
    text(ctx, `${nextGoal} PTS GOAL`, x + w, y - 18, { size: 32, color: rgba(p, 0.8), align: 'right', spacing: 2 });

    // track
    ctx.beginPath(); ctx.roundRect(x, y, w, h, 4);
    ctx.fillStyle = 'rgba(30,34,40,0.95)'; ctx.fill();
    ctx.lineWidth = 2; ctx.strokeStyle = rgba(p, 0.35); ctx.stroke();

    // fill with glow
    const fw = Math.max(0, Math.round(w * percent));
    if (fw > 0) {
        ctx.save();
        ctx.beginPath(); ctx.roundRect(x, y, w, h, 4); ctx.clip();
        const g = ctx.createLinearGradient(x, y, x + w, y);
        g.addColorStop(0, rgba(p, 0.55));
        g.addColorStop(1, rgba(p, 1));
        ctx.shadowColor = rgba(p, 0.9); ctx.shadowBlur = 20;
        ctx.fillStyle = g;
        ctx.fillRect(x, y, fw, h);
        ctx.restore();
        // bright head
        ctx.fillStyle = '#ffffff';
        ctx.globalAlpha = 0.85;
        ctx.fillRect(x + fw - 4, y, 4, h);
        ctx.globalAlpha = 1;
    }

    // segment ticks (every 10%)
    ctx.fillStyle = 'rgba(14,17,21,0.9)';
    for (let i = 1; i < 10; i++) ctx.fillRect(x + (w * i) / 10 - 1.5, y, 3, h);
}

function drawScanlines(ctx) {
    ctx.fillStyle = 'rgba(0,0,0,0.10)';
    for (let y = 0; y < H; y += 4) ctx.fillRect(0, y, W, 1);
}

// ---------- main ----------
/**
 * @param {object} data { user_id, display_name, rank, points, solves, avatar_url,
 *                        next_goal, last_cats, earned_role }
 * @param {object} [opts] { avatarBuffer } - supply a Buffer instead of downloading (tests)
 * @returns {Promise<Buffer>} PNG
 */
async function renderProfileCard(data, opts = {}) {
    const {
        user_id = '0', display_name = 'UNKNOWN', rank = 'N/A', points = 0, solves = 0,
        avatar_url = null, next_goal = null, last_cats = [], earned_role = 'RECRUIT',
    } = data;

    const t = getTheme(rank, points);
    const canvas = createCanvas(W, H);
    const ctx = canvas.getContext('2d');
    const avatar = await getAvatar(avatar_url, opts.avatarBuffer);

    drawBackground(ctx, t);
    drawStamp(ctx);
    drawFrame(ctx, t);
    drawHeader(ctx, t, user_id);
    drawBarcode(ctx, t, user_id);
    drawAvatar(ctx, t, avatar, display_name);
    drawRolePlate(ctx, t, String(earned_role));
    drawName(ctx, t, display_name);
    drawBadge(ctx, t);
    drawCategoryChips(ctx, t, last_cats, points);
    drawStat(ctx, t, 600, 310, 'RANK', rank, points);
    drawStat(ctx, t, 980, 310, 'SCORE', points, points);
    drawStat(ctx, t, 1360, 310, 'FLAGS', solves, points);
    drawProgress(ctx, t, points, next_goal);
    drawScanlines(ctx);

    return canvas.encode('png');
}

module.exports = { renderProfileCard };