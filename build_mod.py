# Builds mod\BOF4_Rekindled.exe: a GUI installer for a clean English GOG install (no Python, no German patch).
# The installer embeds only what changes (copy-from-original / literal-bytes ops, SHA-256 checked) for every
# combination of options that touches a file.   py build_mod.py
# Build-time inputs (paths in config.py): clean English GOG DAT files and BOF4.exe, Naro's Better Descriptions
# PC zip (Nexus) in the game folder.
import base64, gzip, hashlib, itertools, os, subprocess, zipfile, zlib
import config
import patch_uncut_en as P
import button_icons, identify_icons
from steam.mem_list import option_mem, check as check_mem
import sys; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "loops"))
import boss_victory                                            # loops/: renders from the PS1 disc (config.py)

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.dirname(HERE)
OUT = os.path.join(HERE, "mod")
sha = lambda b: hashlib.sha256(b).hexdigest()

CONTENT, FIXES, MORE, PAD = "Restored content", "Fixes", "Enhancements (experimental)", "Controller (experimental)"
OPTIONS = [  # group, id, label, description, on/off by default[, choices "id=label" for a dropdown]
    (CONTENT, "content", "Restore cut content",
     "Puts back what the English release removed: four cut scenes (Ryu and Ursula at the checkpoint, Ursula on "
     "Zig's ship, Soniel's attack on Fou-Lu, the Saldine bath scene) with English text, the Japan-only Dengeki "
     "Store, and Scias' Identify ability (learned at level 3, takes effect in a new game). Note: saves made past "
     "the Saldine creek in the unmodded game freeze at the bath scene.", "on"),
    (CONTENT, "desc", "Better Descriptions (by Naro)",
     "Item, equipment and master descriptions also list hidden effects and resistances.", "on"),
    (FIXES, "fixes", "PC port fixes",
     "Fixes random stutters (the screen was read back from the GPU every frame), the swimming 3D in rooms "
     "with lighting effects, such as North Chamba, and darkening effects drawn black over their solid parts "
     "(Fou-Lu's sword swipe, white on the PS1).", "on"),
    (FIXES, "loops", "Correct music loops",
     "Songs loop from their real loop point instead of restarting the intro, without the click at each restart. "
     "Also brings back the PS1's boss versions of the victory theme (Ryu's and Fou-Lu's boss battles), rebuilt "
     "from the PS1 music data.", "on"),
    (FIXES, "reverb", "PlayStation reverb",
     "Adds back the reverb the PS1's sound chip put on the music. The PC recordings are dry. Strength adjustable "
     "in BOF4_reverb.ini.", "on"),
    (MORE, "fps60", "60 fps",
     "Draws an in-between frame for each of the game's 30 frames per second, so camera and characters move "
     "smoothly. Scroll Lock turns it off and on while playing.", "off"),
    (MORE, "widescreen", "Widescreen",
     "At a 16:9 resolution, the 3D fills the screen with correct proportions and more view at the sides instead "
     "of being stretched. Menus stay 4:3.", "off"),
    (MORE, "sprites", "Sprite depth scaling",
     "Characters far from the camera shrink like the 3D around them, instead of seeming to grow. Insert switches "
     "the mode while playing.", "off"),
    (PAD, "startback", "Start/Back as Start/Select",
     "A controller's Start and Back work as the PS1 Start and Select (Press Enter, the world map's travel menu). "
     "New key setups put the camera on LB/RB. While you play with a controller, button hints show its buttons.", "off"),
    (PAD, "icons", "Button icons:",
     "Shows Xbox or PlayStation button symbols instead of the circled numbers 1–10 on the Key/Pad Setting "
     "screen, and in the controller's button hints (A green, B red...).", "off", "=Numbers (original)", "xbox=Xbox", "ps=PlayStation"),
]
# Installer options that stand for several patch_exe parts; the others are one part of the same name.
PARTS = {"content": ("uncut", "dengeki", "identify"), "fixes": ("stutter", "wobble", "blend")}
ALWAYS = ("ffwd",)          # exe parts in every patched exe (fast-forward: Home, works whenever bof4_reverb.dll is there)
# Option ids as variant keys use them, in manifest order (a dropdown contributes its choices).
IDS = [c.split("=")[0] for o in OPTIONS for c in (o[5:] or [o[1]]) if c[0] != "="]
EXE_OPTS = [i for i in IDS if set(PARTS.get(i, (i,))) <= set(P.EXE_PARTS)]
assert sorted([p for i in EXE_OPTS for p in PARTS.get(i, (i,))] + list(ALWAYS)) == sorted(P.EXE_PARTS)

# ---------------------------------------------------------------- Better Descriptions (build time only)
# Naro's PC release (Nexus): one BPS patch per DAT file, against the English GOG files.
DESC_ZIP = config.DESC_ZIP                 # Naro's PC release zip (see config.py)

def bps(src, p):
    assert p[:4] == b"BPS1"
    i = 4
    def num():
        nonlocal i
        d, s = 0, 1
        while True:
            x = p[i]; i += 1
            d += (x & 0x7F) * s
            if x & 0x80: return d
            s <<= 7; d += s
    ssize, tsize, msize = num(), num(), num(); i += msize
    assert zlib.crc32(src) == int.from_bytes(p[-12:-8], "little"), "BPS source CRC mismatch"
    out, so, to = bytearray(), 0, 0
    while i < len(p) - 12:
        d = num(); act, n = d & 3, (d >> 2) + 1
        if act == 0: out += src[len(out):len(out) + n]
        elif act == 1: out += p[i:i + n]; i += n
        else:
            d = num(); off = (-1 if d & 1 else 1) * (d >> 1)
            if act == 2: so += off; out += src[so:so + n]; so += n
            else:
                to += off
                for _ in range(n): out.append(out[to]); to += 1
    assert len(out) == tsize and zlib.crc32(out) == int.from_bytes(p[-8:-4], "little"), "BPS target CRC mismatch"
    return bytes(out)

# ---------------------------------------------------------------- variants
def build_variants():
    """Yields (path, key, original, patched), key = tuple of option ids applied, in IDS order (255 exe variants)."""
    en = lambda f: open(os.path.join(config.CLEAN_DAT, f), "rb").read()
    # BOF4.exe stays untouched (GOG and Steam): dsound.dll applies the exe options in memory, per option, from
    # BOF4_Rekindled.mem; the installer writes the chosen ones into BOF4_Rekindled.ini
    exe = open(config.CLEAN_EXE, "rb").read()
    patch = lambda parts: P.patch_exe(exe, parts)
    opts = [(i, PARTS.get(i, (i,))) for i in EXE_OPTS]
    mem = option_mem(exe, patch, opts, ALWAYS)
    print(check_mem(exe, patch, opts, ALWAYS, mem), "option combinations: loader result = patch_exe")
    yield ("BOF4_Rekindled.mem", ("loader",), b"", mem.encode())
    yield ("dsound.dll", ("loader",), b"", open(os.path.join(HERE, "steam", "dsound.dll"), "rb").read())
    # boss victory themes: song 1 of the two boss music files, rendered from the PS1 disc (loops/boss_victory.py)
    table = open(os.path.join(HERE, "reverb", "loops_table.h")).read()
    for name, mp3 in boss_victory.mp3s().items():
        assert f"{{{len(mp3)}, 0x{zlib.crc32(mp3[:4096]):08X}u," in table, \
            f"{name}: rendered song not in reverb/loops_table.h - run loops/make_table.py and reverb/build.bat"
        yield ("DAT\\" + name + ".DAT", ("loops",), en(name + ".DAT"), P.patch_bgm(en(name + ".DAT"), 1, mp3))
    # DAT files of "content" (scenes, store, Identify) are disjoint, so each has the one key
    assert not (set(P.LINES) & set(P.STORE) or set(P.LINES) & set(P.IDENTIFY_DATS) or set(P.STORE) & set(P.IDENTIFY_DATS))
    for f, msgs in P.LINES.items():
        yield ("DAT\\" + f, ("content",), en(f), P.patch_text(en(f), msgs))
    for f in P.STORE:
        yield ("DAT\\" + f, ("content",), en(f), P.patch_store(en(f)))
    dll = open(os.path.join(HERE, "reverb", "bof4_reverb.dll"), "rb").read()
    dll_parts = [i for i in IDS if i in ("reverb", "loops", "fps60", "sprites", "widescreen")]  # same DLL serves all
    for n in range(1, len(dll_parts) + 1):
        for key in itertools.combinations(dll_parts, n):
            yield ("bof4_reverb.dll", key, b"", dll)
    for f, patch in P.IDENTIFY_DATS.items():
        if f != "INIT.DAT": yield ("DAT\\" + f, ("content",), en(f), patch(en(f)))
    assert IDS.index("content") < IDS.index("desc")
    assert IDS.index("content") < IDS.index("startback") < min(IDS.index(k) for k in button_icons.SETS)
    init = en("INIT.DAT")          # fonts: Identify's element icons, the icon set, the hint labels (Start/Back)
    for ident, sb, icons in itertools.product((False, True), (False, True), (None, *button_icons.SETS)):
        key = ("content",) * ident + ("startback",) * sb + ((icons,) if icons else ())
        if not key: continue
        d = button_icons.patch_font(init, icons) if icons else init
        if sb: d = button_icons.patch_labels(d, icons or "numbers")
        if ident: d = identify_icons.patch_font(d)
        yield ("DAT\\INIT.DAT", key, init, d)
    z = zipfile.ZipFile(DESC_ZIP)
    for n in z.namelist():
        f = n.replace(".bps", ".DAT")
        d = bps(en(f), z.read(n))
        yield ("DAT\\" + f, ("desc",), en(f), d)
        if f in P.IDENTIFY_DATS:                                       # both options touch this file
            yield ("DAT\\" + f, ("content", "desc"), en(f), P.IDENTIFY_DATS[f](d))

def ops(src, dst):
    if not src:                                            # new file (not in the original game)
        return [("L", dst)]
    if len(src) == len(dst):                               # byte diff
        out, i = [], 0
        while i < len(dst):
            j, same = i, src[i] == dst[i]
            while j < len(dst) and (src[j] == dst[j]) == same: j += 1
            out.append(("C", i, j - i) if same else ("L", dst[i:j])); i = j
        return out
    if dst[:4] == b"\x10\0\0\0" and dst[0x10] in (0x30, 0x31):   # music file: header literal, songs copied if unchanged
        ents = P.bgm_parts(dst); start = 0x10 + 16 * len(ents)
        out = [("L", dst[:start])]
        for flag, tag, off, size in ents:
            c = dst[0x10 + off:0x10 + off + size]; k = src.find(c)
            out.append(("C", k, size) if k >= 0 else ("L", c))
        return out
    ents = P.table(dst)                                    # DAT container: per chunk
    out = [("L", dst[:ents[0][0]])]
    for o, s, f, t in ents:
        c = dst[o:o + s]; k = src.find(c) if s >= 64 else -1
        out.append(("C", k, s) if k >= 0 else ("L", c))
    return out

def manifest():
    lines = ["O " + "|".join(o) for o in OPTIONS]
    assert not any("|" in s for o in OPTIONS for s in o)
    exe = open(config.CLEAN_EXE, "rb").read()
    lines.append("E " + sha(exe) + " " + " ".join(EXE_OPTS))   # untouched GOG exe; options the loader applies
    for path, key, src, dst in build_variants():
        o = ops(src, dst)
        assert b"".join(src[a[1]:a[1] + a[2]] if a[0] == "C" else a[1] for a in o) == dst
        lines.append(f"F {path} {','.join(key)} {sha(src)} {sha(dst)}")
        lines += [f"C {a[1]} {a[2]}" if a[0] == "C" else "L " + base64.b64encode(a[1]).decode() for a in o]
    return "\n".join(lines) + "\n"

CSC = r"C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe"
ART = os.path.join(HERE, "art")
BANNER = (640, 180)                        # must match the banner size in installer.cs
WINDOW_BG = (24, 22, 28)                    # Installer.Bg

def make_art(tmp):
    from PIL import Image, ImageDraw
    w, h = BANNER
    bg = Image.open(os.path.join(ART, "background.png")).convert("RGB")
    s = h / bg.height * 1.12                                   # a little zoom; party shifted right of the logo
    b = bg.resize((round(bg.width * s), round(bg.height * s)), Image.LANCZOS)
    b = b.crop((0, b.height - h, w, b.height)).convert("RGBA")
    fade = Image.new("RGBA", (w, h)); d = ImageDraw.Draw(fade)
    for y in range(h):                                         # blend into the window colour at the bottom
        a = max(0.0, (y - h * 0.6) / (h * 0.4))
        d.line([(0, y), (w, y)], fill=WINDOW_BG + (int(255 * a ** 1.6),))
    b = Image.alpha_composite(b, fade)
    logo = Image.open(os.path.join(ART, "logo.png")).convert("RGBA")
    logo = logo.resize((250, round(logo.height * 250 / logo.width)), Image.LANCZOS)
    b.alpha_composite(logo, (12, 8))
    banner = os.path.join(tmp, "banner.png"); b.convert("RGB").save(banner)

    # icon.png is 70x70 pixel art drawn at ~7.3x: sample it back to its native grid, then only integer
    # scaling. Small sizes show Ryu's head and shoulders; large sizes the whole sprite.
    nat = Image.open(os.path.join(ART, "icon.png")).convert("RGBA").resize((70, 70), Image.NEAREST)
    full = nat.crop(nat.getbbox()); n = 64
    sq = Image.new("RGBA", (n, n)); sq.alpha_composite(full, ((n - full.width) // 2, (n - full.height) // 2))
    frames = [nat.crop((x, y, x + s, y + s)) for x, y, s in ((14, 21, 16), (11, 18, 24), (8, 17, 32), (2, 12, 48))]
    frames += [sq, sq.resize((128, 128), Image.NEAREST), sq.resize((256, 256), Image.NEAREST)]
    icon = os.path.join(tmp, "icon.ico")
    frames[-1].save(icon, sizes=[f.size for f in frames], append_images=frames[:-1])
    return banner, icon

def main():
    os.makedirs(OUT, exist_ok=True)
    tmp = os.path.join(HERE, "build_tmp"); os.makedirs(tmp, exist_ok=True)
    man = os.path.join(tmp, "manifest.gz")             # deflate: 8 MB -> 2 MB (15 identical DLL variants etc.)
    with gzip.open(man, "wb", 9) as f: f.write(manifest().encode("utf-8"))
    banner, icon = make_art(tmp)
    exe = os.path.join(OUT, "BOF4_Rekindled.exe")
    subprocess.run([CSC, "/nologo", "/target:winexe", "/optimize+", f"/out:{exe}", f"/win32icon:{icon}",
                    f"/resource:{man},manifest.gz", f"/resource:{banner},banner.png",
                    "/r:System.Windows.Forms.dll", "/r:System.Drawing.dll",
                    os.path.join(HERE, "installer.cs")], check=True)
    for f in ("BOF4_Uncut_EN.exe", "BOF4_Uncut_EN.ps1", "Install.bat", "Uninstall.bat"):   # pre-rename / script installers
        if os.path.exists(os.path.join(OUT, f)): os.remove(os.path.join(OUT, f))
    print(f"built {exe} ({os.path.getsize(exe) // 1024} KB, manifest {os.path.getsize(man) // 1024} KB)")

if __name__ == "__main__":
    main()
