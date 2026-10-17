#!/usr/bin/env python3
"""
Generate official-fidelity high-resolution and icon-sized assets for Claude Usage Widget extension.
Outputs:
- icons/icon.svg
- icons/icon512.png
- icons/icon128.png
- icons/icon48.png
- icons/icon32.png
- icons/icon16.png
"""

import math
import os
import re
from PIL import Image, ImageDraw, ImageFilter

SIZE = 1024
CENTER_X = SIZE // 2
CENTER_Y = (SIZE // 2) - 15  # Visual center adjusted for gauge arc opening

def get_claude_polygon():
    # Read the official Claude AI SVG path
    with open('claude_official.svg', encoding='utf-8') as f:
        path_data = f.read()

    d = re.search(r'd="([^"]+)"', path_data).group(1)
    tokens = re.findall(r'([a-zA-Z]|[-+]?[0-9]*\.?[0-9]+)', d)

    points = []
    cur_x = 0.0
    cur_y = 0.0

    i = 0
    cmd = ''
    while i < len(tokens):
        t = tokens[i]
        if t.isalpha():
            cmd = t
            i += 1
        
        if cmd == 'm' or cmd == 'l':
            cur_x += float(tokens[i])
            cur_y += float(tokens[i+1])
            points.append((cur_x, cur_y))
            i += 2
            cmd = 'l'
        elif cmd == 'L':
            cur_x = float(tokens[i])
            cur_y = float(tokens[i+1])
            points.append((cur_x, cur_y))
            i += 2
        elif cmd == 'h':
            cur_x += float(tokens[i])
            points.append((cur_x, cur_y))
            i += 1
        elif cmd == 'H':
            cur_x = float(tokens[i])
            points.append((cur_x, cur_y))
            i += 1
        elif cmd == 'v':
            cur_y += float(tokens[i])
            points.append((cur_x, cur_y))
            i += 1
        elif cmd == 'V':
            cur_y = float(tokens[i])
            points.append((cur_x, cur_y))
            i += 1
        elif cmd == 'c':
            dx1 = float(tokens[i])
            dy1 = float(tokens[i+1])
            dx2 = float(tokens[i+2])
            dy2 = float(tokens[i+3])
            dx = float(tokens[i+4])
            dy = float(tokens[i+5])
            p0 = (cur_x, cur_y)
            p1 = (cur_x + dx1, cur_y + dy1)
            p2 = (cur_x + dx2, cur_y + dy2)
            p3 = (cur_x + dx, cur_y + dy)
            for step in range(1, 9):
                t = step / 8.0
                bx = (1-t)**3 * p0[0] + 3*(1-t)**2*t * p1[0] + 3*(1-t)*t**2 * p2[0] + t**3 * p3[0]
                by = (1-t)**3 * p0[1] + 3*(1-t)**2*t * p1[1] + 3*(1-t)*t**2 * p2[1] + t**3 * p3[1]
                points.append((bx, by))
            cur_x += dx
            cur_y += dy
            i += 6
        elif cmd.lower() == 'z':
            break
        else:
            i += 1

    return points, d

def create_master_icon():
    points, raw_d = get_claude_polygon()

    # 1. Base Canvas
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))

    # 2. Background Rounded Squircle
    p = 28
    r = 215
    rect = [p, p, SIZE - p, SIZE - p]

    bg_tile = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    bg_draw = ImageDraw.Draw(bg_tile)

    bg_mask = Image.new("L", (SIZE, SIZE), 0)
    mask_draw = ImageDraw.Draw(bg_mask)
    mask_draw.rounded_rectangle(rect, radius=r, fill=255)

    # Dark gradient background: #1C1F26 to #101114
    for y in range(p, SIZE - p):
        factor = (y - p) / (SIZE - 2 * p)
        r_c = int(28 * (1 - factor) + 16 * factor)
        g_c = int(31 * (1 - factor) + 17 * factor)
        b_c = int(38 * (1 - factor) + 20 * factor)
        bg_draw.line([(p, y), (SIZE - p, y)], fill=(r_c, g_c, b_c, 255))

    bg_final = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    bg_final.paste(bg_tile, (0, 0), bg_mask)
    img = Image.alpha_composite(img, bg_final)
    draw = ImageDraw.Draw(img)

    # Subtle ambient inner glow
    inner_glow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ig_draw = ImageDraw.Draw(inner_glow)
    ig_draw.rounded_rectangle([p + 4, p + 4, SIZE - p - 4, SIZE - p - 4], radius=r - 4,
                             outline=(232, 113, 74, 18), width=8)
    inner_glow = inner_glow.filter(ImageFilter.GaussianBlur(8))
    img = Image.alpha_composite(img, inner_glow)
    draw = ImageDraw.Draw(img)

    # Squircle border stroke
    draw.rounded_rectangle(rect, radius=r, outline=(60, 68, 80, 220), width=4)
    draw.rounded_rectangle([p + 2, p + 2, SIZE - p - 2, SIZE - p - 2], radius=r - 2,
                           outline=(255, 255, 255, 24), width=2)

    # 3. Ambient Glow behind Claude Spark
    ambient_spark_glow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    asg_draw = ImageDraw.Draw(ambient_spark_glow)
    asg_draw.ellipse([CENTER_X - 220, CENTER_Y - 220, CENTER_X + 220, CENTER_Y + 220],
                     fill=(232, 113, 74, 30))
    ambient_spark_glow = ambient_spark_glow.filter(ImageFilter.GaussianBlur(50))
    img = Image.alpha_composite(img, ambient_spark_glow)
    draw = ImageDraw.Draw(img)

    # 4. Usage Meter Circular Gauge
    gauge_center = (CENTER_X, CENTER_Y)
    gauge_radius = 355
    gauge_thickness = 46

    start_angle = 135
    end_angle = 405
    total_sweep = 270

    track_bbox = [
        gauge_center[0] - gauge_radius,
        gauge_center[1] - gauge_radius,
        gauge_center[0] + gauge_radius,
        gauge_center[1] + gauge_radius
    ]

    # Background Track
    draw.arc(track_bbox, start=start_angle, end=end_angle, fill=(36, 42, 52, 255), width=gauge_thickness)

    # Track rounded caps
    for ang in [start_angle, end_angle]:
        rad = math.radians(ang)
        cx = gauge_center[0] + gauge_radius * math.cos(rad)
        cy = gauge_center[1] + gauge_radius * math.sin(rad)
        cr = gauge_thickness / 2
        draw.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=(36, 42, 52, 255))

    # Active Progress Arc (~70% filled)
    usage_pct = 0.70
    active_sweep = total_sweep * usage_pct
    active_end = start_angle + active_sweep

    color_start = (226, 92, 58)    # Claude coral #E25C3A
    color_mid   = (234, 115, 76)   # Claude terracotta #EA734C
    color_end   = (248, 166, 18)   # Bright amber #F8A612

    def lerp(c1, c2, t):
        return int(c1 + (c2 - c1) * t)

    def get_color(t):
        if t < 0.5:
            st = t / 0.5
            return (lerp(color_start[0], color_mid[0], st),
                    lerp(color_start[1], color_mid[1], st),
                    lerp(color_start[2], color_mid[2], st))
        else:
            st = (t - 0.5) / 0.5
            return (lerp(color_mid[0], color_end[0], st),
                    lerp(color_mid[1], color_end[1], st),
                    lerp(color_mid[2], color_end[2], st))

    steps = 200
    for i in range(steps):
        t1 = i / steps
        t2 = (i + 1.2) / steps
        a1 = start_angle + active_sweep * t1
        a2 = start_angle + active_sweep * t2
        col = get_color(t1)
        draw.arc(track_bbox, start=a1, end=a2, fill=(*col, 255), width=gauge_thickness)

    # Start cap
    rad_start = math.radians(start_angle)
    cap_sx = gauge_center[0] + gauge_radius * math.cos(rad_start)
    cap_sy = gauge_center[1] + gauge_radius * math.sin(rad_start)
    cr = gauge_thickness / 2
    draw.ellipse([cap_sx - cr, cap_sy - cr, cap_sx + cr, cap_sy + cr], fill=(*color_start, 255))

    # Glowing end cap
    rad_end = math.radians(active_end)
    cap_ex = gauge_center[0] + gauge_radius * math.cos(rad_end)
    cap_ey = gauge_center[1] + gauge_radius * math.sin(rad_end)
    draw.ellipse([cap_ex - cr, cap_ey - cr, cap_ex + cr, cap_ey + cr], fill=(*color_end, 255))

    # Glow layer for end cap
    glow_layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_layer)
    glow_draw.ellipse([cap_ex - cr - 10, cap_ey - cr - 10, cap_ex + cr + 10, cap_ey + cr + 10],
                      fill=(248, 166, 18, 160))
    glow_draw.ellipse([cap_ex - cr - 22, cap_ey - cr - 22, cap_ex + cr + 22, cap_ey + cr + 22],
                      fill=(232, 113, 74, 90))
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(14))
    img = Image.alpha_composite(img, glow_layer)
    draw = ImageDraw.Draw(img)

    # 5. Official Claude Spark Symbol in Center
    spark_scale = 4.8
    transformed_points = [
        (CENTER_X + (pt[0] - 49.95) * spark_scale,
         CENTER_Y + (pt[1] - 50.0) * spark_scale)
        for pt in points
    ]

    # Create spark with smooth vertical terracotta gradient
    spark_tile = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    st_draw = ImageDraw.Draw(spark_tile)

    spark_mask = Image.new("L", (SIZE, SIZE), 0)
    sm_draw = ImageDraw.Draw(spark_mask)
    sm_draw.polygon(transformed_points, fill=255)

    # Gradient fill for spark: #F58666 (top) to #D36443 (bottom)
    min_sy = int(min(p[1] for p in transformed_points))
    max_sy = int(max(p[1] for p in transformed_points))
    for y in range(min_sy, max_sy + 1):
        f = (y - min_sy) / max(1, (max_sy - min_sy))
        r_sp = int(246 * (1 - f) + 210 * f)
        g_sp = int(134 * (1 - f) + 100 * f)
        b_sp = int(102 * (1 - f) + 67 * f)
        st_draw.line([(0, y), (SIZE, y)], fill=(r_sp, g_sp, b_sp, 255))

    spark_final = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    spark_final.paste(spark_tile, (0, 0), spark_mask)

    # Subtle ambient drop shadow under spark
    shadow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    sh_draw = ImageDraw.Draw(shadow)
    sh_points = [(p[0], p[1] + 8) for p in transformed_points]
    sh_draw.polygon(sh_points, fill=(0, 0, 0, 110))
    shadow = shadow.filter(ImageFilter.GaussianBlur(10))
    img = Image.alpha_composite(img, shadow)

    # Composite spark onto canvas
    img = Image.alpha_composite(img, spark_final)

    return img, raw_d

def export_all():
    os.makedirs("icons", exist_ok=True)
    master, raw_d = create_master_icon()

    sizes = [
        (512, "icons/icon512.png"),
        (128, "icons/icon128.png"),
        (48,  "icons/icon48.png"),
        (32,  "icons/icon32.png"),
        (16,  "icons/icon16.png"),
    ]

    for sz, path in sizes:
        resized = master.resize((sz, sz), Image.Resampling.LANCZOS)
        resized.save(path, format="PNG", optimize=True)
        print(f"Generated {path} ({sz}x{sz})")

    generate_svg("icons/icon.svg", raw_d)
    print("Generated icons/icon.svg")

def generate_svg(path, raw_d):
    svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="100%" height="100%">
  <defs>
    <!-- Background Gradient -->
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#1C1F26" />
      <stop offset="100%" stop-color="#101114" />
    </linearGradient>

    <!-- Usage Gauge Gradient -->
    <linearGradient id="gaugeGrad" x1="0%" y1="100%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#E25C3A" />
      <stop offset="50%" stop-color="#EA734C" />
      <stop offset="100%" stop-color="#F8A612" />
    </linearGradient>

    <!-- Spark Vertical Gradient -->
    <linearGradient id="sparkGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#F58666" />
      <stop offset="100%" stop-color="#D36443" />
    </linearGradient>

    <!-- End Cap Glow Filter -->
    <filter id="glow" x="-30%" y="-30%" width="160%" height="160%">
      <feGaussianBlur stdDeviation="6" result="blur" />
      <feComposite in="SourceGraphic" in2="blur" operator="over" />
    </filter>
  </defs>

  <!-- Background Squircle -->
  <rect x="14" y="14" width="484" height="484" rx="108" ry="108" fill="url(#bgGrad)" stroke="#3C4450" stroke-width="2" />
  <rect x="16" y="16" width="480" height="480" rx="106" ry="106" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="1.5" />

  <!-- Background Gauge Track (270 deg arc from 135 deg to 405 deg, r=178, center=(256, 248.5)) -->
  <path d="M 130.13 374.37 A 178 178 0 1 1 381.87 374.37"
        fill="none" stroke="#242A34" stroke-width="23" stroke-linecap="round" />

  <!-- Active Usage Gauge Arc (~70% progress, angle 135 to 324 deg) -->
  <!-- End: x = 256 + 178 * cos(324 deg) = 400.01, y = 248.5 + 178 * sin(324 deg) = 143.86 -->
  <path d="M 130.13 374.37 A 178 178 0 1 1 400.01 143.86"
        fill="none" stroke="url(#gaugeGrad)" stroke-width="23" stroke-linecap="round" />

  <!-- Glowing Head Tip Indicator -->
  <circle cx="400.01" cy="143.86" r="14" fill="#F8A612" filter="url(#glow)" opacity="0.6" />
  <circle cx="400.01" cy="143.86" r="11.5" fill="#FDE047" />

  <!-- Official Claude Spark Symbol in Center (Scaled and Centered) -->
  <!-- Scaled by 2.4x (from 100x100 to 240x240), Center at (256, 248.5) -->
  <g transform="translate(136.12, 128.5) scale(2.4)">
    <!-- Drop shadow -->
    <path d="{raw_d}" fill="#000000" opacity="0.3" transform="translate(0, 2)" />
    <!-- Spark Body -->
    <path d="{raw_d}" fill="url(#sparkGrad)" />
  </g>
</svg>
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg_content)

if __name__ == "__main__":
    export_all()
