# Controller button icons in place of the circled numbers 1-10.
# The PC port numbers joystick buttons 1-10 and shows them as circled digits on the Key/Pad Setting screen. With the
# Start/Back option, keycap hints show the button too (patch_labels, below) while a controller is in use.
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

# Button hint labels (with the Start/Back option): in controller mode a keycap hint is sized for "0" (one slot) or
# "00" (two), and its letters are drawn from these glyphs instead: 2 per button (1-10), appended to the keycap fonts
# (chunk 8: 16x16 cells, big keycaps; chunk 10: 12x12, small ones), with palette 14 (INIT.DAT chunk 1) for colour.
# A slot shows cell columns u..u+w-1 of '0' and advances w-1, so a 2-slot label is 2(w-1)+1 columns wide.
LABEL_FONTS = {8: (16, 104, 3, 10), 10: (12, 91, 2, 8)}   # chunk: cell, glyphs before, '0' u and width (exe tables)
DOUBLE = {5, 6, 9, 10}                                     # buttons with a 2-slot label (as in the exe)
P14 = {"white": 8, "grey": 2, "green": 7, "red": 14, "blue": 4, "yellow": 5, "pink": 11}
LABELS = {"numbers": [(str(n), "white") for n in range(1, 11)],
          "xbox": [("A", "green"), ("B", "red"), ("X", "blue"), ("Y", "yellow"), ("LB", "white"), ("RB", "white"),
                   ("view", "white"), ("menu", "white"), ("LS", "white"), ("RS", "white")],
          "ps": [("cross", "blue"), ("circle", "red"), ("square", "pink"), ("triangle", "green"), ("L1", "white"),
                 ("R1", "white"), ("select", "white"), ("start", "white"), ("L3", "white"), ("R3", "white")]}

def label_canvas(font, cw, u, w, text, colour, slots):
    """Label art as rows of palette 14 indices, slots * (w - 1) + 1 columns wide."""
    W = slots * (w - 1) + 1
    cell = lambda ch: [[font[((ord(ch) - 0x20) * cw * cw + y * cw + x) // 2] >> (4 * (x & 1)) & 15 for x in range(cw)]
                       for y in range(cw)]
    rows = [y for y in range(cw) if any(cell("0")[y])]
    top, bot = rows[0], rows[-1]
    out = [[0] * W for _ in range(cw)]
    if len(text) <= 2:                                     # letters and digits: the font's own glyphs, side by side
        parts = [cell(ch) for ch in text]
        cols = [[x for x in range(cw) if any(p[y][x] for y in range(cw))] for p in parts]
        total = sum(c[-1] - c[0] + 1 for c in cols) + len(parts) - 1
        x0 = (W - total) // 2
        for p, c in zip(parts, cols):
            for y in range(cw):
                for x in c:
                    v = p[y][x]
                    if v and 0 <= x0 + x - c[0] < W: out[y][x0 + x - c[0]] = v
            x0 += c[-1] - c[0] + 2
    else:                                                  # symbols, drawn at 8x like the circled icons
        Z = 8; h = bot - top + 1; s = min(W, h)
        im = Image.new("L", (W * Z, cw * Z)); d = ImageDraw.Draw(im)
        cx, cy, r, lw = W * Z / 2, (top + bot + 1) * Z / 2, s * Z / 2 - Z * 0.6, round(Z * 1.4)
        if text == "cross":
            k = r * 0.8
            for a, b in ((-k, k), (k, -k)): d.line((cx - k, cy + a, cx + k, cy + b), fill=255, width=lw)
        elif text == "circle": d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=255, width=lw)
        elif text == "square": k = r * 0.85; d.rectangle((cx - k, cy - k, cx + k, cy + k), outline=255, width=lw)
        elif text == "triangle":
            d.polygon([(cx, cy - r), (cx + r, cy + r * 0.75), (cx - r, cy + r * 0.75)], outline=255, width=lw)
        elif text == "view":
            k = r * 0.5
            d.rectangle((cx - k * 1.6, cy - k * 1.6, cx + k * 0.4, cy + k * 0.4), outline=255, width=Z)
            d.rectangle((cx - k * 0.4, cy - k * 0.4, cx + k * 1.6, cy + k * 1.6), fill=255)
        elif text == "menu":
            for dy in (-r * 0.6, 0, r * 0.6): d.line((cx - r * 0.8, cy + dy, cx + r * 0.8, cy + dy), fill=255, width=Z)
        elif text == "select":
            d.rounded_rectangle((cx - r, cy - r * 0.45, cx + r, cy + r * 0.45), radius=r * 0.45, fill=255)
        elif text == "start": d.polygon([(cx - r * 0.7, cy - r), (cx + r, cy), (cx - r * 0.7, cy + r)], fill=255)
        cov = im.resize((W, cw), Image.BOX).load()
        for y in range(cw):
            for x in range(W):
                if cov[x, y] > 40: out[y][x] = 1 if cov[x, y] > 150 else 6
    main = P14[colour]
    res = [[0] * W for _ in range(cw)]
    for y in range(cw):                                    # full ink: the colour; faint ink and a 1-pixel rim: grey
        for x in range(W):
            if out[y][x] and out[y][x] <= 5: res[y][x] = main
            elif out[y][x] or any(0 <= y + b < cw and 0 <= x + a < W and 0 < out[y + b][x + a] <= 5
                                  for a in (-1, 0, 1) for b in (-1, 0, 1)):
                res[y][x] = P14["grey"]
    return res

def label_glyphs(init, chunk, set_):
    """2 cells per button for SETS-style label set_ ("numbers", "xbox", "ps") in font chunk."""
    cw, n, u, w = LABEL_FONTS[chunk]
    o, s, f, t = table(init)[chunk]
    assert f == 5 and s == n * cw * cw // 2, f"INIT.DAT font chunk {chunk} not as expected"
    font, out = init[o:o + s], b""
    for b, (text, colour) in enumerate(LABELS[set_], 1):
        slots = 2 if b in DOUBLE else 1
        art = label_canvas(font, cw, u, w, text, colour, slots)
        for k in range(2):
            px = [[0] * cw for _ in range(cw)]
            if k < slots:
                for y in range(cw):
                    for x in range(w):
                        if k * (w - 1) + x < len(art[0]): px[y][u + x] = art[y][k * (w - 1) + x]
            out += bytes(px[y][x] | px[y][x + 1] << 4 for y in range(cw) for x in range(0, cw, 2))
    return out

def patch_labels(init, set_):
    """INIT.DAT with the hint labels appended to both keycap fonts."""
    ents = table(init); out = init
    for chunk in sorted(LABEL_FONTS, reverse=True):        # later chunk first: earlier offsets stay valid
        o, s, f, t = ents[chunk]
        add = label_glyphs(init, chunk, set_)
        out = out[:o + s] + add + out[o + s:]
        ents[chunk][1] += len(add)
        for e in ents[chunk + 1:]: e[0] += len(add)
    out = bytearray(out)
    for i, e in enumerate(ents): struct.pack_into("<4I", out, i * 16, *e)
    return bytes(out)

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
    for k in LABELS:                                                           # hint labels, also with Identify
        p = identify_icons.patch_font(patch_labels(init, k))
        for chunk, (cw, n, u, w) in LABEL_FONTS.items():
            assert table(p)[chunk][1] == (n + 20) * cw * cw // 2
    print("ok; preview in button_icons.png")
