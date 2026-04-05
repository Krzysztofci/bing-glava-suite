#!/usr/bin/env python3
"""
gradient_compare.py
Generuje obraz PNG porównujący gradienty RGB i HSV dla zadanych kolorów.
Użycie: python3 gradient_compare.py [bottom_hex] [mid_hex] [top_hex]
Przykład: python3 gradient_compare.py "#00ff00" "#ffffff" "#ff0000"
"""

import sys
import struct
import zlib
import os

# ─────────────────────────────────────────────────────────────────────────────

def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) / 255.0 for i in (0, 2, 4))

def rgb_to_hex(r, g, b):
    return "#{:02x}{:02x}{:02x}".format(int(r*255), int(g*255), int(b*255))

# ─── RGB interpolacja ────────────────────────────────────────────────────────

def gradient_rgb(t, bottom, mid, top):
    if t < 0.5:
        lt = t * 2.0
        return tuple(bottom[i] + (mid[i] - bottom[i]) * lt for i in range(3))
    else:
        lt = (t - 0.5) * 2.0
        return tuple(mid[i] + (top[i] - mid[i]) * lt for i in range(3))

# ─── HSV interpolacja ────────────────────────────────────────────────────────

def rgb2hsv(r, g, b):
    mx = max(r, g, b)
    mn = min(r, g, b)
    d = mx - mn
    s = 0.0 if mx == 0 else d / mx
    v = mx
    if d == 0:
        h = 0.0
    elif mx == r:
        h = (g - b) / d % 6
    elif mx == g:
        h = (b - r) / d + 2
    else:
        h = (r - g) / d + 4
    h /= 6.0
    return h, s, v

def hsv2rgb(h, s, v):
    if s == 0:
        return v, v, v
    h6 = h * 6.0
    i = int(h6)
    f = h6 - i
    p = v * (1 - s)
    q = v * (1 - s * f)
    t = v * (1 - s * (1 - f))
    return [(v,t,p),(q,v,p),(p,v,t),(p,q,v),(t,p,v),(v,p,q)][i % 6]

def lerp_hsv(a, b, t):
    ha, sa, va = rgb2hsv(*a)
    hb, sb, vb = rgb2hsv(*b)
    dh = hb - ha
    if dh > 0.5:  dh -= 1.0
    if dh < -0.5: dh += 1.0
    h = ha + dh * t
    s = sa + (sb - sa) * t
    v = va + (vb - va) * t
    return hsv2rgb(h, s, v)

def gradient_hsv(t, bottom, mid, top):
    if t < 0.5:
        return lerp_hsv(bottom, mid, t * 2.0)
    else:
        return lerp_hsv(mid, top, (t - 0.5) * 2.0)

# ─── Zapis PNG ────────────────────────────────────────────────────────────────

def write_png(filename, pixels, width, height):
    def chunk(name, data):
        c = struct.pack('>I', len(data)) + name + data
        return c + struct.pack('>I', zlib.crc32(name + data) & 0xffffffff)

    raw = b''
    for row in pixels:
        raw += b'\x00'
        for r, g, b in row:
            raw += bytes([min(255,max(0,int(r*255))), min(255,max(0,int(g*255))), min(255,max(0,int(b*255)))])

    compressed = zlib.compress(raw)
    ihdr = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    png = b'\x89PNG\r\n\x1a\n'
    png += chunk(b'IHDR', ihdr)
    png += chunk(b'IDAT', compressed)
    png += chunk(b'IEND', b'')
    with open(filename, 'wb') as f:
        f.write(png)

# ─── Główna logika ────────────────────────────────────────────────────────────

def main():
    bottom_hex = sys.argv[1] if len(sys.argv) > 1 else "#00ff00"
    mid_hex    = sys.argv[2] if len(sys.argv) > 2 else "#ffffff"
    top_hex    = sys.argv[3] if len(sys.argv) > 3 else "#ff0000"

    bottom = hex_to_rgb(bottom_hex)
    mid    = hex_to_rgb(mid_hex)
    top    = hex_to_rgb(top_hex)

    WIDTH  = 600
    HEIGHT = 80
    GAP    = 4
    LABEL  = 20

    total_h = LABEL + HEIGHT + GAP + HEIGHT + LABEL
    pixels = [[(1.0, 1.0, 1.0)] * WIDTH for _ in range(total_h)]

    # RGB pasek
    for x in range(WIDTH):
        t = x / (WIDTH - 1)
        col = gradient_rgb(t, bottom, mid, top)
        for y in range(LABEL, LABEL + HEIGHT):
            pixels[y][x] = col

    # HSV pasek
    for x in range(WIDTH):
        t = x / (WIDTH - 1)
        col = gradient_hsv(t, bottom, mid, top)
        for y in range(LABEL + HEIGHT + GAP, LABEL + HEIGHT + GAP + HEIGHT):
            pixels[y][x] = col

    # Znaczniki bottom/mid/top
    for row in range(total_h):
        pixels[row][0] = hex_to_rgb(bottom_hex)
        pixels[row][WIDTH//2] = (0.5, 0.5, 0.5)
        pixels[row][WIDTH-1] = hex_to_rgb(top_hex)

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gradient_compare.png")
    write_png(out, pixels, WIDTH, total_h)
    print(f"Zapisano: {out}")
    print(f"Bottom: {bottom_hex}  Mid: {mid_hex}  Top: {top_hex}")
    print(f"Górny pasek = RGB,  Dolny pasek = HSV")

    # Porównanie pikseli w punktach kluczowych
    print("\nPorównanie wartości w t=0.25, t=0.5, t=0.75:")
    for t in [0.25, 0.5, 0.75]:
        rgb = gradient_rgb(t, bottom, mid, top)
        hsv = gradient_hsv(t, bottom, mid, top)
        print(f"  t={t:.2f}  RGB={rgb_to_hex(*rgb)}  HSV={rgb_to_hex(*hsv)}  {'RÓŻNE' if rgb_to_hex(*rgb) != rgb_to_hex(*hsv) else 'IDENTYCZNE'}")

if __name__ == "__main__":
    main()
