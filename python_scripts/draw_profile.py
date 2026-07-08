import sys
import json
import urllib.request
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageOps

class ProfileRenderer:
    def __init__(self):
        font_path = "font.ttf"
        try:
            self.title_font = ImageFont.truetype(font_path, 130)
            self.badge_font = ImageFont.truetype(font_path, 60)
            self.label_font = ImageFont.truetype(font_path, 50)
            self.value_font = ImageFont.truetype(font_path, 110)
            self.small_font = ImageFont.truetype(font_path, 35)
            self.micro_font = ImageFont.truetype(font_path, 24)
        except IOError:
            print("❌ font.ttf not found in parent directory!")
            sys.exit(1)

    def draw_profile_card(self, user_id, display_name, rank, points, solves, avatar_url, next_goal=None, last_cats=None, earned_role="RECRUIT", output_path="profile.png"):
        width, height = 1800, 700
        bg_color = (20, 22, 25)  
        if points == 999999:
            bg_color = (0, 10, 30)

        try: rank_num = int(rank.replace("#", ""))
        except: rank_num = 999 

        primary = (0, 255, 230); fill_color = (0, 40, 40); b_text = (200, 255, 255); role = "OPERATIVE"
        
        if points == 999999:
            primary = (0, 255, 120); fill_color = (0, 40, 20); b_text = (150, 255, 200); role = "SYSTEM CORE"
        elif rank_num == 1: primary = (255, 215, 0); fill_color = (40, 30, 0); b_text = (255, 230, 150); role = "CHAMPION"
        elif rank_num == 2: primary = (229, 228, 226); fill_color = (45, 45, 50); b_text = (255, 255, 255); role = "VANGUARD"
        elif rank_num == 3: primary = (205, 127, 50); fill_color = (40, 20, 10); b_text = (255, 200, 180); role = "CHALLENGER"
        elif 4 <= rank_num <= 10: primary = (220, 20, 60); fill_color = (50, 10, 15); b_text = (255, 200, 200); role = "SENTINEL"
        elif points == 0: primary = (100, 100, 100); fill_color = (30, 30, 35); b_text = (200, 200, 200); role = "RECRUIT"

        with Image.new("RGBA", (width, height), bg_color) as card:
            draw = ImageDraw.Draw(card)
            
            for x in range(0, width, 80): draw.line([(x, 0), (x, height)], fill=(30, 35, 40), width=2)
            for y in range(0, height, 80): draw.line([(0, y), (width, y)], fill=(30, 35, 40), width=2)

            glow_color = primary + (50,)
            for i in range(1, 4):
                gw = 6 + (i * 4)
                draw.rectangle([0, 0, width, height], outline=glow_color, width=gw)
                draw.ellipse((100-i, 135-i, 500+i, 535+i), outline=glow_color, width=gw)

            try:
                stamp_font = ImageFont.truetype("font.ttf", 220)
                stamp_txt = "CLASSIFIED"
                stamp_img = Image.new("RGBA", (1300, 400), (0,0,0,0))
                s_draw = ImageDraw.Draw(stamp_img)
                s_draw.text((10, 10), stamp_txt, fill=(255, 40, 40, 45), font=stamp_font, stroke_width=2, stroke_fill=(255, 160, 160, 60))
                rotated_stamp = stamp_img.rotate(10, expand=1, resample=Image.Resampling.BICUBIC)
                card.paste(rotated_stamp, (400, 180), rotated_stamp)
            except: pass

            draw.line([(40, 30), (40, 110)], fill=(100, 105, 110), width=12)
            draw.line([(70, 30), (70, 110)], fill=(100, 105, 110), width=12)

            draw.text((110, 35), f"ID_REF: {user_id}", fill=(primary[0], primary[1], primary[2], 120), font=self.micro_font)
            draw.text((110, 65), "STATUS: ACTIVE_OPERATIVE", fill=primary, font=self.micro_font)

            blen, bw = 200, 12
            draw.line([(0, 0), (blen, 0)], fill=primary, width=bw); draw.line([(0, 0), (0, blen)], fill=primary, width=bw)
            draw.line([(width, height), (width-blen, height)], fill=primary, width=bw); draw.line([(width, height), (width, height-blen)], fill=primary, width=bw)

            ax, ay, asz = 100, 135, 400
            avatar_bytes = None
            if avatar_url:
                try:
                    req = urllib.request.Request(avatar_url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req) as response:
                        avatar_bytes = response.read()
                except Exception as e: pass

            if avatar_bytes:
                try:
                    with BytesIO(avatar_bytes) as av_buf:
                        with Image.open(av_buf) as av_raw:
                            av_raw.thumbnail((asz, asz), Image.Resampling.LANCZOS) 
                            with av_raw.convert("RGBA") as avatar:
                                with Image.new("L", avatar.size, 0) as mask:
                                    ImageDraw.Draw(mask).ellipse((0, 0, avatar.size[0], avatar.size[1]), fill=255)
                                    with ImageOps.fit(avatar, mask.size, centering=(0.5, 0.5)) as output:
                                        output.putalpha(mask); card.paste(output, (ax, ay), output)
                except Exception: avatar_bytes = None
            
            if not avatar_bytes:
                initial = display_name[0].upper() if display_name else "?"
                draw.ellipse((ax, ay, ax+asz, ay+asz), fill=fill_color, outline=primary, width=4)
                try: initial_font = ImageFont.truetype("font.ttf", 250)
                except: initial_font = self.title_font
                
                i_bbox = draw.textbbox((0, 0), initial, font=initial_font)
                i_w = i_bbox[2] - i_bbox[0]; i_h = i_bbox[3] - i_bbox[1]
                draw.text((ax + (asz - i_w)//2, ay + (asz - i_h)//2 - 30), initial, fill=primary, font=initial_font)
            
            draw.ellipse((ax, ay, ax+asz, ay+asz), outline=primary, width=4)
            disp_str = display_name.upper()
            font_size = 130
            try:
                d_font = ImageFont.truetype("font.ttf", font_size)
            except:
                d_font = self.title_font

            while True:
                bbox = draw.textbbox((0, 0), disp_str, font=d_font)
                if bbox[2] <= 1100 or font_size <= 30:
                    break
                font_size -= 4
                try:
                    d_font = ImageFont.truetype("font.ttf", font_size)
                except:
                    break
                    
            y_offset = 50 + (130 - font_size) // 2
            draw.text((600, y_offset), disp_str, fill="white", font=d_font)
            
            cr_x, cr_y, cr_w, cr_h = 100, 580, 400, 70
            cr_poly = [(cr_x+10, cr_y), (cr_x+cr_w-10, cr_y), (cr_x+cr_w, cr_y+10), (cr_x+cr_w, cr_y+cr_h-10), (cr_x+cr_w-10, cr_y+cr_h), (cr_x+10, cr_y+cr_h), (cr_x, cr_y+cr_h-10), (cr_x, cr_y+10)]
            draw.polygon(cr_poly, fill=fill_color, outline=primary, width=3)
            cr_bbox = draw.textbbox((0,0), earned_role, font=self.small_font)
            cr_tw = cr_bbox[2]-cr_bbox[0]; cr_th = cr_bbox[3]-cr_bbox[1]
            draw.text((cr_x+(cr_w-cr_tw)//2, cr_y+(cr_h-cr_th)//2-4), earned_role, fill=primary, font=self.small_font)

            bx, by, bh, cut = 600, 180, 90, 24
            bw_val = draw.textbbox((0, 0), role, font=self.badge_font)[2] + 140
            poly = [(bx+cut, by), (bx+bw_val-cut, by), (bx+bw_val, by+cut), (bx+bw_val, by+bh-cut), (bx+bw_val-cut, by+bh), (bx+cut, by+bh), (bx, by+bh-cut), (bx, by+cut)]
            draw.polygon(poly, fill=fill_color, outline=primary, width=4)
            ds, dcx, dcy = 20, bx + 50, by + 44
            draw.polygon([(dcx, dcy-ds), (dcx+ds, dcy), (dcx, dcy+ds), (dcx-ds, dcy)], fill=primary)
            draw.text((bx+100, by+8), role, fill=b_text, font=self.badge_font)

            if next_goal:
                bar_x, bar_y, bar_w, bar_h = 600, 650, 1100, 20
                percent = min(1.0, points / next_goal)
                draw.rectangle([bar_x, bar_y, bar_x+bar_w, bar_y+bar_h], fill=(30, 30, 35))
                draw.rectangle([bar_x, bar_y, bar_x+int(bar_w*percent), bar_y+bar_h], fill=primary)
                
                progress_text = f"CLEARANCE PROGRESS: {int(percent*100)}%"
                goal_text = f"{next_goal} PTS GOAL"
                
                goal_w = draw.textbbox((0, 0), goal_text, font=self.small_font)[2]
                draw.text((bar_x, bar_y-45), progress_text, fill=primary, font=self.small_font)
                draw.text((bar_x + bar_w - goal_w, bar_y-45), goal_text, fill=primary, font=self.small_font)
            else:
                m_text = "ARCHITECT OF THE SIMULATION" if points == 999999 else "MAX CLEARANCE LEVEL ATTAINED"
                m_bbox = draw.textbbox((0, 0), m_text, font=self.label_font)
                m_w = m_bbox[2] - m_bbox[0]
                draw.text((1150 - (m_w//2), 580), m_text, fill=primary, font=self.label_font)

            def d_stat(x, y, lab, val):
                sw, sh, c = 340, 220, 20
                p = [(x+c, y), (x+sw-c, y), (x+sw, y+c), (x+sw, y+sh-c), (x+sw-c, y+sh), (x+c, y+sh), (x, y+sh-c), (x, y+c)]
                draw.polygon(p, fill=(20, 25, 30), outline=primary, width=4)
                draw.text((x+30, y+20), lab, fill=primary, font=self.label_font)
                
                display_val = "∞" if points == 999999 and lab in ["RANK", "SCORE"] else str(val)
                if points == 999999:
                    if lab == "RANK": display_val = "[ROOT]"
                    if lab == "FLAGS": display_val = "KERNEL"
                
                v_font = self.value_font; v_y = y + 90
                if len(display_val) > 5:
                    v_font = self.badge_font; v_y = y + 115 
                
                draw.text((x+30, v_y), display_val, fill="white", font=v_font)

            d_stat(600, 310, "RANK", rank); d_stat(980, 310, "SCORE", points); d_stat(1360, 310, "FLAGS", solves)
            
            if last_cats:
                cat_info = {
                    "WEB": ("WEB", (0, 255, 230)), "CRYPTO": ("CRY", (255, 230, 0)), "PWN": ("PWN", (255, 0, 80)),
                    "REV": ("REV", (180, 0, 255)), "FORENSICS": ("FOR", (0, 255, 100)), "OSINT": ("OSI", (255, 150, 0)),
                    "MISC": ("MSC", (180, 180, 180))
                }
                
                tw, th, tc = 160, 70, 10; curr_x = width - 100 - tw; top_y = 190 
                
                for cat in reversed(last_cats):
                    label, clr = cat_info.get(cat, (cat[:3].upper(), (200, 200, 200)))
                    if points == 999999:
                        if label == "SYS": clr = (255, 50, 50)
                        elif label == "SQL": clr = (50, 255, 50)
                        elif label == "ENC": clr = (50, 100, 255)

                    tp = [(curr_x+tc, top_y), (curr_x+tw-tc, top_y), (curr_x+tw, top_y+tc), (curr_x+tw, top_y+th-tc), (curr_x+tw-tc, top_y+th), (curr_x+tc, top_y+th), (curr_x, top_y+th-tc), (curr_x, top_y+tc)]
                    draw.polygon(tp, fill=(20, 25, 30), outline=clr, width=3)
                    
                    glow = clr + (40,)
                    draw.polygon(tp, outline=glow, width=6)
                    
                    bbox = draw.textbbox((0, 0), label, font=self.small_font)
                    t_w = bbox[2] - bbox[0]; t_h = bbox[3] - bbox[1]
                    draw.text((curr_x + (tw - t_w)//2, top_y + (th - t_h)//2 - 4), label, fill=clr, font=self.small_font)
                    curr_x -= (tw + 20)

            # SAVE TO FILE
            card.save(output_path, format="PNG", optimize=True)

if __name__ == "__main__":
    input_data = sys.stdin.read()
    data = json.loads(input_data)
    
    renderer = ProfileRenderer()
    output_path = sys.argv[1] if len(sys.argv) > 1 else "profile.png"
    
    renderer.draw_profile_card(
        user_id=data.get('user_id'),
        display_name=data.get('display_name'),
        rank=data.get('rank', 'N/A'),
        points=data.get('points', 0),
        solves=data.get('solves', 0),
        avatar_url=data.get('avatar_url'),
        next_goal=data.get('next_goal'),
        last_cats=data.get('last_cats', []),
        earned_role=data.get('earned_role', 'RECRUIT'),
        output_path=output_path
    )
    print(output_path)
