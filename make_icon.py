"""Generates jarvis.ico — an arc-reactor style icon."""
import math
from PIL import Image, ImageDraw

SIZES = [16, 24, 32, 48, 64, 128, 256]
OUT = "jarvis.ico"


def draw(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = cy = size / 2
    R = size * 0.48

    # Dark disc background
    d.ellipse([cx - R, cy - R, cx + R, cy + R], fill=(5, 15, 25, 255))

    # Outer ring
    d.ellipse([cx - R, cy - R, cx + R, cy + R], outline=(0, 225, 255, 255), width=max(1, size // 48))

    # Inner ring
    r2 = R * 0.78
    d.ellipse([cx - r2, cy - r2, cx + r2, cy + r2], outline=(0, 200, 230, 200), width=max(1, size // 64))

    # Triangular blades
    r_in, r_out = R * 0.30, R * 0.60
    for k in range(6):
        a = math.radians(k * 60)
        p1 = (cx + math.cos(a) * r_in, cy + math.sin(a) * r_in)
        p2 = (cx + math.cos(a + 0.45) * r_out, cy + math.sin(a + 0.45) * r_out)
        p3 = (cx + math.cos(a - 0.45) * r_out, cy + math.sin(a - 0.45) * r_out)
        d.polygon([p1, p2, p3], fill=(0, 180, 220, 180), outline=(120, 240, 255, 255))

    # Glowing core
    core = R * 0.22
    for i, alpha in enumerate([60, 120, 220]):
        rr = core * (1.6 - i * 0.35)
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr],
                  fill=(180, 250, 255, alpha) if i == 2 else (0, 225, 255, alpha))
    return img


def main():
    images = [draw(s) for s in SIZES]
    images[0].save(OUT, format="ICO", sizes=[(s, s) for s in SIZES])
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
