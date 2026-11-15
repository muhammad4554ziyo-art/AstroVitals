#!/usr/bin/env python3
"""
AstroVitals Crew Avatar Artwork Generator.
Generates ultra-high fidelity 512x512 astronaut profile portraits
with role-specific color grading, space helmets, reflective visors,
HUD overlays, suit collars, and mission badges.
"""

import math
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

OUTPUT_DIR = "/home/kali/Projects/astronaut-health-monitor/static/img/crew"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Crew specifications
CREW_SPECS = [
    {
        "id": "ASTRO-ROZIMUROD",
        "filename": "rozimurod.png",
        "name": "ROZIMUROD",
        "callsign": "PHOENIX-ACTUAL",
        "role": "MISSION COMMANDER",
        "rank": "POLKOVNIK",
        "accent": (255, 179, 0),        # Amber Gold
        "accent_secondary": (255, 61, 0), # Crimson
        "visor_start": (255, 230, 140),
        "visor_mid": (255, 160, 0),
        "visor_end": (180, 80, 0),
        "hud_type": "COMMAND",
        "symbol": "✦ COMMANDER"
    },
    {
        "id": "ASTRO-MUHAMMADZIYO",
        "filename": "muhammadziyo.png",
        "name": "MUHAMMADZIYO",
        "callsign": "AURA-DOC",
        "role": "CHIEF MEDICAL OFFICER",
        "rank": "PODPOLKOVNIK",
        "accent": (0, 240, 255),        # Cyan
        "accent_secondary": (0, 255, 136), # Emerald
        "visor_start": (150, 255, 255),
        "visor_mid": (0, 200, 220),
        "visor_end": (0, 100, 140),
        "hud_type": "MEDICAL",
        "symbol": "✚ FLIGHT SURGEON"
    },
    {
        "id": "ASTRO-ELDOR",
        "filename": "eldor.png",
        "name": "ELDOR",
        "callsign": "TITAN-WRENCH",
        "role": "CHIEF ROBOTICS & EVA",
        "rank": "MAYOR",
        "accent": (255, 145, 0),        # Industrial Amber
        "accent_secondary": (255, 215, 0), # Gold
        "visor_start": (255, 210, 130),
        "visor_mid": (220, 120, 0),
        "visor_end": (120, 60, 0),
        "hud_type": "ENGINEERING",
        "symbol": "⚙ HEAVY ROBOTICS"
    },
    {
        "id": "ASTRO-JASUR",
        "filename": "jasur.png",
        "name": "JASUR",
        "callsign": "ARES-VANGUARD",
        "role": "LEAD EVA GEOLOGIST",
        "rank": "MAYOR",
        "accent": (255, 87, 34),        # Martian Red / Copper
        "accent_secondary": (255, 23, 68),
        "visor_start": (255, 170, 130),
        "visor_mid": (210, 70, 30),
        "visor_end": (120, 30, 20),
        "hud_type": "GEOLOGY",
        "symbol": "▲ ARES VANGUARD"
    },
    {
        "id": "ASTRO-SHOHRUXMIRZO",
        "filename": "shohruxmirzo.png",
        "name": "SHOHRUXMIRZO",
        "callsign": "FALCON-EYE",
        "role": "LANDER PILOT & NAV",
        "rank": "KAPITAN",
        "accent": (41, 121, 255),       # Electric Cobalt
        "accent_secondary": (0, 229, 255), # Neon Azure
        "visor_start": (160, 210, 255),
        "visor_mid": (30, 110, 240),
        "visor_end": (10, 40, 140),
        "hud_type": "PILOT",
        "symbol": "✈ LANDER PILOT"
    }
]

# Fonts setup
FONT_BOLD_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_MONO_PATH = "/usr/share/fonts/truetype/firacode/FiraCode-Bold.ttf"
if not os.path.exists(FONT_MONO_PATH):
    FONT_MONO_PATH = FONT_BOLD_PATH

# 2x Supersampling for ultra-crisp antialiasing
W, H = 1024, 1024

def lerp(c1, c2, t):
    return int(c1[0] + (c2[0] - c1[0]) * t), int(c1[1] + (c2[1] - c1[1]) * t), int(c1[2] + (c2[2] - c1[2]) * t)

def draw_stars(draw, count=80):
    import random
    rng = random.Random(42)
    for _ in range(count):
        x = rng.randint(40, W - 40)
        y = rng.randint(40, H - 40)
        brightness = rng.randint(80, 240)
        r = rng.choice([1, 1, 2, 3])
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(brightness, brightness, brightness, rng.randint(120, 240)))

def generate_avatar(spec):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)

    accent = spec["accent"]
    accent_sec = spec["accent_secondary"]

    # 1. Background Badge Geometry: Hexagonal Rounded Shield
    # Center (512, 512), radius ~460
    cx, cy = 512, 512
    r_outer = 480
    r_inner = 460

    def get_hex_points(c_x, c_y, radius):
        pts = []
        for i in range(6):
            # Pointy top hexagon
            angle = math.radians(60 * i - 30)
            pts.append((c_x + radius * math.cos(angle), c_y + radius * math.sin(angle)))
        return pts

    outer_hex = get_hex_points(cx, cy, r_outer)
    inner_hex = get_hex_points(cx, cy, r_inner)

    # Dark background fill
    bg_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bg_draw = ImageDraw.Draw(bg_layer)
    bg_draw.polygon(outer_hex, fill=(7, 12, 22, 255))
    im.alpha_composite(bg_layer)

    # Radial subtle atmospheric glow in center
    glow_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_layer)
    for rad in range(350, 50, -15):
        alpha = int(24 * (1.0 - rad / 350.0))
        glow_draw.ellipse([cx - rad, cy - rad - 30, cx + rad, cy + rad - 30],
                          fill=(accent[0], accent[1], accent[2], alpha))
    im.alpha_composite(glow_layer)

    # Stars
    stars_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    stars_draw = ImageDraw.Draw(stars_layer)
    draw_stars(stars_draw, 90)
    im.alpha_composite(stars_layer)

    # Tech grid lines in background
    grid_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    grid_draw = ImageDraw.Draw(grid_layer)
    for gx in range(120, W - 120, 60):
        grid_draw.line([(gx, 100), (gx, H - 100)], fill=(accent[0], accent[1], accent[2], 12), width=1)
    for gy in range(120, H - 120, 60):
        grid_draw.line([(100, gy), (W - 100, gy)], fill=(accent[0], accent[1], accent[2], 12), width=1)
    # Range circles
    grid_draw.ellipse([cx - 360, cy - 360, cx + 360, cy + 360], outline=(accent[0], accent[1], accent[2], 22), width=2)
    grid_draw.ellipse([cx - 280, cy - 280, cx + 280, cy + 280], outline=(accent[0], accent[1], accent[2], 18), width=1)
    im.alpha_composite(grid_layer)

    # 2. Spacesuit Torso & Shoulders (Bottom part)
    suit_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    suit_draw = ImageDraw.Draw(suit_layer)

    # Heavy EVA Shoulder Silhouette (trapezoid-curve down to bottom)
    # Shoulders base width 820px, neck ring at y=660
    suit_pts = [
        (cx - 180, 640),
        (cx - 380, 750),
        (cx - 430, 890),
        (cx - 410, 1000),
        (cx + 410, 1000),
        (cx + 430, 890),
        (cx + 380, 750),
        (cx + 180, 640),
    ]
    suit_draw.polygon(suit_pts, fill=(28, 34, 46, 255))
    # Chest Armor Plate (Center)
    chest_pts = [
        (cx - 150, 670),
        (cx - 260, 770),
        (cx - 240, 960),
        (cx + 240, 960),
        (cx + 260, 770),
        (cx + 150, 670),
    ]
    suit_draw.polygon(chest_pts, fill=(40, 48, 65, 255), outline=(65, 78, 105, 255), width=3)

    # Hard Upper Torso (HUT) Center Console
    center_console = [cx - 110, 780, cx + 110, 920]
    suit_draw.rectangle(center_console, fill=(18, 22, 32, 255), outline=(accent[0], accent[1], accent[2], 180), width=3)

    # ECLSS Umbilical Dual Valves (Left & Right chest connectors)
    for vx, vy in [(cx - 180, 810), (cx + 180, 810)]:
        suit_draw.ellipse([vx - 32, vy - 32, vx + 32, vy + 32], fill=(20, 25, 35, 255), outline=(120, 135, 160, 255), width=4)
        suit_draw.ellipse([vx - 20, vy - 20, vx + 20, vy + 20], fill=(50, 60, 75, 255), outline=(accent[0], accent[1], accent[2], 240), width=3)
        suit_draw.ellipse([vx - 8, vy - 8, vx + 8, vy + 8], fill=(accent[0], accent[1], accent[2], 255))

    # Console Status LEDs & Telemetry Bar
    for idx, lx in enumerate(range(cx - 80, cx + 90, 45)):
        led_col = (0, 255, 136) if idx < 3 else accent
        suit_draw.rectangle([lx - 12, 805, lx + 12, 820], fill=(*led_col, 255), outline=(255, 255, 255, 180), width=1)

    # Suit Chest Mission Patch Badge
    badge_rect = [cx - 75, 845, cx + 75, 895]
    suit_draw.rectangle(badge_rect, fill=(10, 15, 25, 255), outline=(accent[0], accent[1], accent[2], 200), width=2)
    # Badge text
    try:
        font_badge = ImageFont.truetype(FONT_MONO_PATH, 16)
        suit_draw.text((cx, 860), "ASTROVITALS", fill=(255, 255, 255), font=font_badge, anchor="mm")
        suit_draw.text((cx, 880), spec["callsign"][:12], fill=accent, font=font_badge, anchor="mm")
    except Exception:
        pass

    # Tactical harness straps & suit lines
    suit_draw.line([(cx - 240, 680), (cx - 210, 960)], fill=(accent[0], accent[1], accent[2], 90), width=5)
    suit_draw.line([(cx + 240, 680), (cx + 210, 960)], fill=(accent[0], accent[1], accent[2], 90), width=5)
    suit_draw.line([(cx - 320, 810), (cx - 150, 890)], fill=(55, 68, 90, 255), width=4)
    suit_draw.line([(cx + 320, 810), (cx + 150, 890)], fill=(55, 68, 90, 255), width=4)

    im.alpha_composite(suit_layer)

    # 3. Helmet Neck Collar Ring
    neck_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    neck_draw = ImageDraw.Draw(neck_layer)
    # Titanium locking collar
    collar_rect = [cx - 195, 610, cx + 195, 685]
    neck_draw.rounded_rectangle(collar_rect, radius=20, fill=(35, 42, 56, 255), outline=(90, 105, 130, 255), width=5)
    # Latch bolts
    for bx in range(cx - 160, cx + 170, 40):
        neck_draw.ellipse([bx - 6, 642, bx + 6, 654], fill=(180, 195, 215, 255), outline=(20, 25, 35, 255), width=2)
    # Center locking latch with role accent LED
    neck_draw.rectangle([cx - 25, 625, cx + 25, 670], fill=(20, 24, 32, 255), outline=(accent[0], accent[1], accent[2], 255), width=2)
    neck_draw.ellipse([cx - 8, 642, cx + 8, 654], fill=accent)
    im.alpha_composite(neck_layer)

    # 4. Helmet Shell Outer Structure
    helmet_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    h_draw = ImageDraw.Draw(helmet_layer)

    # Helmet dome coordinates
    # Center y around 380, width 440, height 440
    hd_bbox = [cx - 245, 170, cx + 245, 640]
    h_draw.ellipse(hd_bbox, fill=(24, 29, 40, 255), outline=(80, 95, 120, 255), width=6)

    # Outer sunshield rim
    rim_bbox = [cx - 255, 160, cx + 255, 620]
    h_draw.arc(rim_bbox, start=180, end=360, fill=(140, 160, 190, 255), width=8)

    # Side-mounted exploration lights & sensor pods
    for pod_x, align in [(cx - 270, -1), (cx + 270, 1)]:
        pod_rect = [pod_x - 30, 340, pod_x + 30, 440]
        h_draw.rounded_rectangle(pod_rect, radius=12, fill=(35, 42, 55, 255), outline=(90, 105, 130, 255), width=4)
        # Searchlight reflector
        lamp_rect = [pod_x - 18, 360, pod_x + 18, 420]
        h_draw.rounded_rectangle(lamp_rect, radius=8, fill=(210, 235, 255, 255), outline=accent, width=2)
        # Lens flare halo
        h_draw.ellipse([pod_x - 8, 380, pod_x + 8, 400], fill=(255, 255, 255, 255))

    # Top aerodynamic ridge / sensor spine
    spine_pts = [
        (cx - 35, 172),
        (cx - 20, 230),
        (cx + 20, 230),
        (cx + 35, 172),
    ]
    h_draw.polygon(spine_pts, fill=(45, 54, 72, 255), outline=(accent[0], accent[1], accent[2], 180), width=3)

    im.alpha_composite(helmet_layer)

    # 5. Visor (Spherical Polycarbonate Shield with Multi-layer Glow & Reflection)
    visor_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    v_draw = ImageDraw.Draw(visor_layer)

    # Visor bounds
    v_left, v_top, v_right, v_bottom = cx - 210, 215, cx + 210, 580
    v_bbox = [v_left, v_top, v_right, v_bottom]

    # Create mask for visor
    visor_mask = Image.new("L", (W, H), 0)
    vm_draw = ImageDraw.Draw(visor_mask)
    vm_draw.ellipse(v_bbox, fill=255)

    # Visor Gradient Fill inside mask
    visor_grad = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    vg_draw = ImageDraw.Draw(visor_grad)

    c_start = spec["visor_start"]
    c_mid = spec["visor_mid"]
    c_end = spec["visor_end"]

    for y in range(v_top, v_bottom):
        norm_y = (y - v_top) / float(v_bottom - v_top)
        if norm_y < 0.45:
            t = norm_y / 0.45
            c = lerp(c_start, c_mid, t)
        else:
            t = (norm_y - 0.45) / 0.55
            c = lerp(c_mid, c_end, t)
        vg_draw.line([(v_left, y), (v_right, y)], fill=(*c, 240))

    # Curved highlight horizon (Space planetary limb reflection)
    for rad_offset in range(0, 45, 5):
        alpha_val = int(220 * (1.0 - rad_offset / 45.0))
        vg_draw.arc([cx - 240, v_top - 60 + rad_offset, cx + 240, v_bottom - 120 + rad_offset],
                    start=20, end=160, fill=(255, 255, 255, alpha_val), width=4)

    # Glossy lens reflection specular slash (Top left)
    vg_draw.arc([cx - 180, v_top + 25, cx + 60, v_top + 160],
                start=130, end=230, fill=(255, 255, 255, 190), width=10)
    vg_draw.arc([cx - 170, v_top + 40, cx + 40, v_top + 150],
                start=140, end=220, fill=(255, 255, 255, 240), width=5)

    # Apply mask to visor
    visor_layer.paste(visor_grad, (0, 0), visor_mask)

    # Visor Outer Bezel Ring
    v_draw.ellipse(v_bbox, outline=(18, 22, 30, 255), width=7)
    v_draw.ellipse([v_left - 3, v_top - 3, v_right + 3, v_bottom + 3], outline=(accent[0], accent[1], accent[2], 120), width=2)

    im.alpha_composite(visor_layer)

    # 6. Specialized Visor HUD Graphics (Role-specific telemetry display on visor!)
    hud_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    h_draw = ImageDraw.Draw(hud_layer)

    # Common HUD framing inside visor
    hud_w = 300
    hud_x0, hud_x1 = cx - 150, cx + 150
    hud_y0, hud_y1 = 290, 510

    # Role specific graphics
    hud_type = spec["hud_type"]
    hud_col = (*accent, 220)
    hud_sec = (*accent_sec, 200)

    try:
        font_hud_title = ImageFont.truetype(FONT_MONO_PATH, 20)
        font_hud_sub = ImageFont.truetype(FONT_MONO_PATH, 16)
        font_hud_tiny = ImageFont.truetype(FONT_MONO_PATH, 13)
    except Exception:
        font_hud_title = None

    if hud_type == "COMMAND":
        # Rozimurod: Tactical Commander Crosshairs + Phoenix Crest
        h_draw.ellipse([cx - 50, 370 - 50, cx + 50, 370 + 50], outline=hud_col, width=2)
        h_draw.ellipse([cx - 30, 370 - 30, cx + 30, 370 + 30], outline=hud_sec, width=1)
        h_draw.line([(cx - 75, 370), (cx - 55, 370)], fill=hud_col, width=3)
        h_draw.line([(cx + 55, 370), (cx + 75, 370)], fill=hud_col, width=3)
        h_draw.line([(cx, 370 - 75), (cx, 370 - 55)], fill=hud_col, width=3)
        h_draw.line([(cx, 370 + 55), (cx, 370 + 75)], fill=hud_col, width=3)
        # Phoenix wings
        h_draw.arc([cx - 100, 340, cx, 400], start=200, end=330, fill=hud_col, width=3)
        h_draw.arc([cx, 340, cx + 100, 400], start=210, end=340, fill=hud_col, width=3)
        # Readout text
        if font_hud_title:
            h_draw.text((cx, 440), "SYS // CMD-ACTUAL", fill=(255, 255, 255, 230), font=font_hud_title, anchor="mm")
            h_draw.text((cx, 465), "ECLSS: NOMINAL 101.3 kPa", fill=hud_col, font=font_hud_sub, anchor="mm")
            h_draw.text((cx, 485), "G-LIMIT: 6.8G • TMR SYNC", fill=hud_sec, font=font_hud_tiny, anchor="mm")

    elif hud_type == "MEDICAL":
        # Muhammadziyo: Bio-Medical ECG Heartbeat wave + Caduceus Cross
        # Draw ECG line
        ecg_points = [
            (cx - 130, 380),
            (cx - 80, 380),
            (cx - 65, 365),
            (cx - 50, 400),
            (cx - 35, 320),  # R-peak
            (cx - 20, 410),  # S-wave
            (cx - 5, 380),
            (cx + 25, 365),  # T-wave
            (cx + 50, 380),
            (cx + 130, 380),
        ]
        for i in range(len(ecg_points) - 1):
            h_draw.line([ecg_points[i], ecg_points[i+1]], fill=(0, 255, 136, 240), width=4)
        # Medical Caduceus Cross in center top
        h_draw.rectangle([cx - 8, 305, cx + 8, 345], fill=hud_col)
        h_draw.rectangle([cx - 25, 317, cx + 25, 333], fill=hud_col)
        if font_hud_title:
            h_draw.text((cx, 435), "HR: 56 BPM • SPO2: 99%", fill=(255, 255, 255, 240), font=font_hud_title, anchor="mm")
            h_draw.text((cx, 462), "AUTONOMIC STRAIN: LOW", fill=hud_col, font=font_hud_sub, anchor="mm")
            h_draw.text((cx, 485), "BIO-SHIELD ACTIVE • CLASS-1", fill=hud_sec, font=font_hud_tiny, anchor="mm")

    elif hud_type == "ENGINEERING":
        # Eldor: Robotics Torque Brackets & Stress Analysis
        # Hexagonal targeting bracket
        h_draw.polygon([(cx - 70, 335), (cx + 70, 335), (cx + 90, 380), (cx + 70, 425), (cx - 70, 425), (cx - 90, 380)],
                       outline=hud_col, width=3)
        # Gear / Torque ticks
        for a_deg in range(0, 360, 45):
            rad = math.radians(a_deg)
            x1 = cx + 55 * math.cos(rad)
            y1 = 380 + 55 * math.sin(rad)
            x2 = cx + 70 * math.cos(rad)
            y2 = 380 + 70 * math.sin(rad)
            h_draw.line([(x1, y1), (x2, y2)], fill=hud_sec, width=2)
        if font_hud_title:
            h_draw.text((cx, 440), "SERVO TORQUE // 100%", fill=(255, 255, 255, 230), font=font_hud_title, anchor="mm")
            h_draw.text((cx, 465), "SUIT LOAD: 8.4G RATED", fill=hud_col, font=font_hud_sub, anchor="mm")
            h_draw.text((cx, 485), "DRILL BIT SPEED: 1200 RPM", fill=hud_sec, font=font_hud_tiny, anchor="mm")

    elif hud_type == "GEOLOGY":
        # Jasur: Planetary Topography Contours + Compass
        # Concentric contour curves simulating Mars crater ridges
        for c_rad in [40, 70, 100]:
            h_draw.arc([cx - c_rad, 360 - c_rad * 0.6, cx + c_rad, 360 + c_rad * 0.6],
                       start=0, end=360, fill=hud_col, width=2)
        # Geological elevation cross
        h_draw.line([(cx - 80, 360), (cx + 80, 360)], fill=hud_sec, width=1)
        h_draw.line([(cx, 310), (cx, 410)], fill=hud_sec, width=1)
        if font_hud_title:
            h_draw.text((cx, 440), "ELEV: -4200M // CANYON", fill=(255, 255, 255, 230), font=font_hud_title, anchor="mm")
            h_draw.text((cx, 465), "SURFACE REGOLITH DETECTED", fill=hud_col, font=font_hud_sub, anchor="mm")
            h_draw.text((cx, 485), "VO2 MAX: 59.5 (PEAK)", fill=hud_sec, font=font_hud_tiny, anchor="mm")

    elif hud_type == "PILOT":
        # Shohruxmirzo: Flight Horizon & Pitch Ladder
        # Pitch ladder rungs
        h_draw.line([(cx - 90, 350), (cx - 30, 350)], fill=hud_col, width=3)
        h_draw.line([(cx - 90, 350), (cx - 90, 360)], fill=hud_col, width=3)
        h_draw.line([(cx + 30, 350), (cx + 90, 350)], fill=hud_col, width=3)
        h_draw.line([(cx + 90, 350), (cx + 90, 360)], fill=hud_col, width=3)

        h_draw.line([(cx - 60, 380), (cx - 20, 380)], fill=hud_sec, width=2)
        h_draw.line([(cx + 20, 380), (cx + 60, 380)], fill=hud_sec, width=2)
        # Flight aircraft symbol
        h_draw.line([(cx - 35, 380), (cx + 35, 380)], fill=(255, 255, 255, 255), width=3)
        h_draw.line([(cx, 370), (cx, 390)], fill=(255, 255, 255, 255), width=3)
        h_draw.ellipse([cx - 4, 380 - 4, cx + 4, 380 + 4], fill=hud_col)
        if font_hud_title:
            h_draw.text((cx, 440), "VECTOR: 11.2 KM/S ORBIT", fill=(255, 255, 255, 230), font=font_hud_title, anchor="mm")
            h_draw.text((cx, 465), "ATTITUDE: +0.42° STABLE", fill=hud_col, font=font_hud_sub, anchor="mm")
            h_draw.text((cx, 485), "LANDER RCS: ARMED & READY", fill=hud_sec, font=font_hud_tiny, anchor="mm")

    im.alpha_composite(hud_layer)

    # 7. Lower Official Mission Card Banner (Sleek Dark Glass with Gold/Cyan Trim)
    banner_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    b_draw = ImageDraw.Draw(banner_layer)

    b_y0 = 890
    b_y1 = 980
    b_rect = [cx - 360, b_y0, cx + 360, b_y1]
    b_draw.rounded_rectangle(b_rect, radius=18, fill=(10, 15, 26, 245), outline=(accent[0], accent[1], accent[2], 230), width=4)

    # Mini corner brackets
    bracket_len = 24
    b_draw.line([(cx - 360, b_y0 + bracket_len), (cx - 360, b_y0), (cx - 360 + bracket_len, b_y0)], fill=(255, 255, 255, 240), width=3)
    b_draw.line([(cx + 360 - bracket_len, b_y0), (cx + 360, b_y0), (cx + 360, b_y0 + bracket_len)], fill=(255, 255, 255, 240), width=3)

    # Banner Typography
    try:
        font_name = ImageFont.truetype(FONT_BOLD_PATH, 30)
        font_meta = ImageFont.truetype(FONT_MONO_PATH, 17)

        # Name and Call Sign
        full_title = f"{spec['name']}  •  \"{spec['callsign']}\""
        b_draw.text((cx, b_y0 + 30), full_title, fill=(255, 255, 255, 255), font=font_name, anchor="mm")

        # Subtitle: Rank + Role + Specialty Symbol
        sub_title = f"{spec['rank']}  |  {spec['role']}  |  {spec['symbol']}"
        b_draw.text((cx, b_y0 + 62), sub_title, fill=accent, font=font_meta, anchor="mm")
    except Exception as e:
        print("Font error:", e)

    im.alpha_composite(banner_layer)

    # 8. Top Flight Header Crest (AstroVitals Star & Crown)
    top_crest_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    tc_draw = ImageDraw.Draw(top_crest_layer)
    # Orbit ring around top
    tc_draw.arc([cx - 300, 40, cx + 300, 160], start=190, end=350, fill=(accent[0], accent[1], accent[2], 180), width=4)
    # Top Glowing Star
    star_y = 65
    tc_draw.text((cx, star_y), "★", fill=(255, 255, 255, 255), anchor="mm")
    try:
        font_top_tag = ImageFont.truetype(FONT_MONO_PATH, 16)
        tc_draw.text((cx, 110), f"ASTROVITALS CREW // {spec['id']}", fill=(accent[0], accent[1], accent[2], 220), font=font_top_tag, anchor="mm")
    except Exception:
        pass
    im.alpha_composite(top_crest_layer)

    # 9. Outer Hexagonal Shield Border
    outer_border_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ob_draw = ImageDraw.Draw(outer_border_layer)
    ob_draw.polygon(outer_hex, outline=(accent[0], accent[1], accent[2], 240), width=6)
    ob_draw.polygon(inner_hex, outline=(40, 50, 70, 200), width=2)
    # Corner hazard notches
    for pt in outer_hex:
        ob_draw.ellipse([pt[0] - 8, pt[1] - 8, pt[0] + 8, pt[1] + 8], fill=accent, outline=(255, 255, 255, 255), width=2)
    im.alpha_composite(outer_border_layer)

    # Downsample from 1024x1024 to 512x512 with high-quality Lanczos filter
    final_im = im.resize((512, 512), Image.Resampling.LANCZOS)

    out_path = os.path.join(OUTPUT_DIR, spec["filename"])
    final_im.save(out_path, format="PNG", optimize=True)
    print(f"Generated: {out_path} ({final_im.size[0]}x{final_im.size[1]})")

if __name__ == "__main__":
    print("Generating 5 high-fidelity astronaut avatars for AstroVitals...")
    for spec in CREW_SPECS:
        generate_avatar(spec)
    print("All 5 crew avatars generated successfully!")
