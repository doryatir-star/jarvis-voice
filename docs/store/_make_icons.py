"""One-shot icon generator for the store PWA — a shopping bag on a pink/purple gradient."""
import os
from PIL import Image, ImageDraw, ImageFilter

OUT = os.path.dirname(os.path.abspath(__file__))
PINK = (255, 92, 168, 255)
PURPLE = (123, 92, 255, 255)
WHITE = (255, 255, 255, 255)


def gradient(size):
    """Diagonal pink -> purple background."""
    img = Image.new("RGBA", (size, size))
    px = img.load()
    for y in range(size):
        for x in range(size):
            t = (x + y) / (2 * size)
            r = int(PINK[0] * (1 - t) + PURPLE[0] * t)
            g = int(PINK[1] * (1 - t) + PURPLE[1] * t)
            b = int(PINK[2] * (1 - t) + PURPLE[2] * t)
            px[x, y] = (r, g, b, 255)
    return img


def render(size: int, maskable: bool = False) -> Image.Image:
    img = gradient(size)
    d = ImageDraw.Draw(img, "RGBA")
    scale = 0.62 if maskable else 0.74          # keep content inside maskable safe area
    s = size * scale
    cx, cy = size / 2, size / 2
    left, top = cx - s / 2, cy - s / 2

    # soft drop shadow
    shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    bag_top = top + s * 0.26
    sd.rounded_rectangle([left, bag_top, left + s, top + s],
                         radius=s * 0.14, fill=(60, 20, 70, 110))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=size * 0.02))
    img.alpha_composite(shadow)

    # bag body
    d.rounded_rectangle([left, bag_top, left + s, top + s],
                        radius=s * 0.14, fill=WHITE)

    # bag handle (arc)
    hw = s * 0.34
    hx0, hx1 = cx - hw / 2, cx + hw / 2
    hy0 = top + s * 0.02
    hy1 = bag_top + s * 0.16
    d.arc([hx0, hy0, hx1, hy1], start=180, end=360,
          fill=WHITE, width=max(3, int(s * 0.07)))

    # heart on the bag
    hs = s * 0.30
    hcx, hcy = cx, bag_top + s * 0.40
    r = hs / 2
    d.ellipse([hcx - r, hcy - r * 0.6, hcx, hcy + r * 0.4], fill=PINK)
    d.ellipse([hcx, hcy - r * 0.6, hcx + r, hcy + r * 0.4], fill=PINK)
    d.polygon([(hcx - r, hcy + r * 0.0), (hcx + r, hcy + r * 0.0),
               (hcx, hcy + r * 0.85)], fill=PINK)

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
