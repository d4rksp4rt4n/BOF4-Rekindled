# Controller button icons in place of the circled numbers 1-10.
# The PC port numbers joystick buttons 1-10 and shows them as circled digits: on the Key/Pad Setting screen and
# in help text (where they replaced the PS1's button symbols: "1: Confirm  2: Cancel", "5/6: Change lure"...).
# GOG's input wrapper reports every pad in Xbox order, so button n is always the same physical button:
#   1 A / cross   2 B / circle   3 X / square   4 Y / triangle   5 LB / L1   6 RB / R1
#   7 View / Select   8 Menu / Start   9 LS / L3   10 RS / R3
# Glyphs 0x5E-0x67 of INIT.DAT font 1 (chunk 9; text chars 0x7E-0x87) are redrawn in place: the game's own ring
# (from its circled 1) with new contents drawn at 8x and reduced to the font's 8 ink levels (1 = full colour ...
# 8 = faint, 0 = transparent). Same size, same metrics, so this composes with identify_icons.patch_font.
#   py button_icons.py    writes button_icons.png (preview) and checks the build
import os, struct
from PIL import Image, ImageDraw, ImageFont

FIRST_GLYPH, FONT_CHUNK, CELL, N = 0x5E, 9, 288, 24
FONT = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "timesbd.ttf")   # build time only
SETS = {"xbox": ["A", "B", "X", "Y", "LB", "RB", "view", "menu", "LS", "RS"],
        "ps": ["cross", "circle", "square", "triangle", "L1", "R1", "select", "start", "L3", "R3"]}
S = 8                                   # supersampling
C = 12 * S                              # centre of the cell (ring centre 11.5 + half a pixel)

def table(d):
    n = struct.unpack_from("<I", d, 0)[0] // 16
    return [list(struct.unpack_from("<4I", d, i * 16)) for i in range(n)]

def unpack(g):
    return [[g[(y * N + x) // 2] >> (4 * (x & 1)) & 15 for x in range(N)] for y in range(N)]

def ring(font):
    """The circled 1 without its digit."""
    px = unpack(font[FIRST_GLYPH * CELL:(FIRST_GLYPH + 1) * CELL])
    return [[0 if (x - 11.5) ** 2 + (y - 11.5) ** 2 < 8.3 ** 2 else px[y][x] for x in range(N)] for y in range(N)]

def text(im, s, size, squeeze=1.0, stroke=0):
    f = ImageFont.truetype(FONT, size * S)
    l, t, r, b = f.getbbox(s, stroke_width=stroke)
    img = Image.new("L", (r - l + 2, b - t + 2))
    ImageDraw.Draw(img).text((1 - l, 1 - t), s, font=f, fill=255, stroke_width=stroke, stroke_fill=255)
    if squeeze != 1.0: img = img.resize((round(img.width * squeeze), img.height), Image.LANCZOS)
    im.paste(255, (C - img.width // 2, C - img.height // 2), img)

def draw(kind):
    im = Image.new("L", (N * S, N * S)); d = ImageDraw.Draw(im)
    r, lw = 6.2 * S, round(1.8 * S)
    if len(kind) == 1: text(im, kind, 15, stroke=S // 3)                       # A B X Y
    elif len(kind) == 2: text(im, kind, 11, squeeze=0.74, stroke=S // 4)       # LB RB LS RS L1 R1 L3 R3
    elif kind == "cross":
        k = r * 0.72
        for a, b in ((-k, k), (k, -k)): d.line((C - k, C + a, C + k, C + b), fill=255, width=lw)
    elif kind == "circle":
        k = r * 0.82; d.ellipse((C - k, C - k, C + k, C + k), outline=255, width=lw)
    elif kind == "square":
        k = r * 0.7; d.rectangle((C - k, C - k, C + k, C + k), outline=255, width=lw)
    elif kind == "triangle":
        k = r * 0.95
        d.polygon([(C, C - k), (C + k * 0.95, C + k * 0.62), (C - k * 0.95, C + k * 0.62)], outline=255, width=lw)
    elif kind == "view":                                                        # two overlapping windows
        k = r * 0.45
        d.rectangle((C - k * 1.5, C - k * 1.5, C + k * 0.5, C + k * 0.5), outline=255, width=round(1.4 * S))
        d.rectangle((C - k * 0.5, C - k * 0.5, C + k * 1.5, C + k * 1.5), fill=255)
    elif kind == "menu":                                                        # three bars
        k = r * 0.7
        for dy in (-k * 0.7, 0, k * 0.7): d.line((C - k, C + dy, C + k, C + dy), fill=255, width=round(1.5 * S))
    elif kind == "select":                                                      # PS1 Select: flat pill
        d.rounded_rectangle((C - r * 0.8, C - r * 0.35, C + r * 0.8, C + r * 0.35), radius=r * 0.35,
                            outline=255, width=round(1.4 * S))
    elif kind == "start":                                                       # PS1 Start: arrow
        k = r * 0.75; d.polygon([(C - k * 0.7, C - k), (C + k, C), (C - k * 0.7, C + k)], fill=255)
    return im.resize((N, N), Image.BOX)

def glyphs(font, set_):
    """10 glyph cells (288 bytes each) for SETS[set_]."""
    base, out = ring(font), b""
    for kind in SETS[set_]:
        cov = draw(kind).load()
        px = [row[:] for row in base]
        for y in range(N):
            for x in range(N):
                if cov[x, y] > 24: px[y][x] = max(1, min(8, 9 - round(cov[x, y] / 255 * 8)))
        out += bytes(px[y][x] | px[y][x + 1] << 4 for y in range(N) for x in range(0, N, 2))
    return out

def patch_font(init, set_):
    """INIT.DAT with the circled 1-10 replaced by SETS[set_]."""
    o, s, f, t = table(init)[FONT_CHUNK]
    assert (f, t) == (5, 0x1801) and s >= (FIRST_GLYPH + 10) * CELL, "INIT.DAT font chunk not as expected"
    a = o + FIRST_GLYPH * CELL
    return init[:a] + glyphs(init[o:o + s], set_) + init[a + 10 * CELL:]

def preview(path, init):
    """Original row, then each set: black (normal) and red (selected) ramps on the window colour."""
    o, s, f, t = table(init)[FONT_CHUNK]
    font = init[o:o + s]
    rows = [font[FIRST_GLYPH * CELL:(FIRST_GLYPH + 10) * CELL]] + [glyphs(font, k) for k in SETS]
    Z, bg = 4, (0xD8, 0xD0, 0xB0)
    ramps = [lambda v: (30 + (v - 1) * 22,) * 3, lambda v: (0xC0 + (v - 1) * 3, 0x20 + (v - 1) * 20, 0x18 + (v - 1) * 20)]
    im = Image.new("RGB", (10 * 26 * Z * 2, len(rows) * 26 * Z), bg)
    for r, row in enumerate(rows):
        for h, ramp in enumerate(ramps):
            for i in range(10):
                px = unpack(row[i * CELL:(i + 1) * CELL])
                for y in range(N):
                    for x in range(N):
                        if px[y][x]:
                            X, Y = ((h * 10 + i) * 26 + 1 + x) * Z, (r * 26 + 1 + y) * Z
                            im.paste(ramp(px[y][x]), (X, Y, X + Z, Y + Z))
    im.save(path)

if __name__ == "__main__":
    import config, identify_icons
    here = os.path.dirname(os.path.abspath(__file__))
    init = open(os.path.join(config.CLEAN_DAT, "INIT.DAT"), "rb").read()
    preview(os.path.join(here, "button_icons.png"), init)
    for k in SETS:
        p = patch_font(init, k)
        assert len(p) == len(init) and sum(a != b for a, b in zip(init, p)) <= 10 * CELL
        both = identify_icons.patch_font(p)                                    # composes with Identify
        assert table(both)[FONT_CHUNK][1] == 116 * CELL
    print("ok; preview in button_icons.png")
