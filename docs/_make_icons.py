"""One-shot icon generator for the Jarvis PWA."""
import math, os
from PIL import Image, ImageDraw, ImageFilter

OUT = os.path.dirname(os.path.abspath(__file__))
BG = (2, 6, 17, 255)
CYAN = (56, 232, 255, 255)
CYAN_DIM = (26, 122, 140, 255)


def render(size: int, maskable: bool = False) -> Image.Image:
    img = Image.new("RGBA", (size, size), BG)
    d = ImageDraw.Draw(img, "RGBA")
    cx = cy = size / 2
    # safe area for maskable: keep main content within central 80%
    safe_r = (size * 0.40) if maskable else (size * 0.46)

    # outer faint glow ring
    for i, alpha in enumerate([28, 60, 110]):
        r = safe_r * (0.95 - i * 0.05)
        bbox = (cx - r, cy - r, cx + r, cy + r)
        d.ellipse(bbox, outline=(56, 232, 255, alpha), width=max(1, size // 200))

    # solid bright ring
    r = safe_r * 0.78
    d.ellipse((cx - r, cy - r, cx + r, cy + r),
              outline=CYAN, width=max(2, size // 80))

    # inner blades (8-spoke)
    for k in range(8):
        a = math.radians(k * 45)
        r_in = safe_r * 0.30
        r_out = safe_r * 0.62
        p1 = (cx + math.cos(a) * r_in, cy + math.sin(a) * r_in)
        p2 = (cx + math.cos(a + 0.22) * r_out, cy + math.sin(a + 0.22) * r_out)
        p3 = (cx + math.cos(a - 0.22) * r_out, cy + math.sin(a - 0.22) * r_out)
        d.polygon([p1, p2, p3], fill=(56, 232, 255, 90), outline=CYAN)

    # bright glowing core
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    cr = safe_r * 0.32
    gd.ellipse((cx - cr, cy - cr, cx + cr, cy + cr), fill=(120, 240, 255, 220))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=size * 0.04))
    img.alpha_composite(glow)

    # core white center
    cr2 = safe_r * 0.16
    d.ellipse((cx - cr2, cy - cr2, cx + cr2, cy + cr2), fill=(245, 255, 255, 255))

    return img


for sz, name, mask in [
    (192, "icon-192.png", False),
    (512, "icon-512.png", False),
    (512, "icon-maskable-512.png", True),
    (180, "apple-touch-icon.png", False),
    (32,  "favicon-32.png", False),
]:
    render(sz, mask).save(os.path.join(OUT, name), "PNG")
    print("wrote", name)
print("done")
