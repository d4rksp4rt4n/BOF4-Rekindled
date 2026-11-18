# Builds mod\BOF4_Uncut_EN.exe: a GUI installer for a clean English GOG install (no Python, no German patch).
# The installer embeds only what changes (copy-from-original / literal-bytes ops, SHA-256 checked) for every
# combination of options that touches a file.   py build_mod.py
# Build-time inputs (paths in config.py): clean English GOG DAT files and BOF4.exe, Naro's Better Descriptions
# PC zip (Nexus) in the game folder.
import base64, hashlib, itertools, os, subprocess, zipfile, zlib
import config
import patch_uncut_en as P
from steam.mem_list import mem_list

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.dirname(HERE)
OUT = os.path.join(HERE, "mod")
sha = lambda b: hashlib.sha256(b).hexdigest()

OPTIONS = [  # id, label, description (shown in the installer)
    ("uncut", "Restore cut scenes",
     "Checkpoint, Zig's ship, Soniel vs. Fou-Lu and Saldine bath scenes, with English text."),
    ("dengeki", "Unlock the Dengeki Store",
     "The Japanese-only store, with its original English (US PlayStation) text."),
    ("stutter", "Stutter fix",
     "Clears the screen on the GPU instead of reading it back every frame (fixes random hitches)."),
    ("reverb", "PlayStation reverb",
     "Adds the PS1's reverb back to the music; the PC recordings are dry (adds bof4_reverb.dll)."),
    ("loops", "Correct music loops",
     "Songs loop from their loop point instead of replaying the intro (uses bof4_reverb.dll)."),
    ("identify", "Scias learns Identify",
     "Restores the cut Identify ability (level 3), with element icons on its screen as in the PS1 hack."),
    ("desc", "Better Descriptions (by Naro)",
     "Item, equipment and master descriptions list hidden effects and resistances."),
    ("fps60", "60 fps (experimental)",
     "Draws an in-between frame for each 30 fps frame (uses bof4_reverb.dll). Scroll Lock: off/on.", "off"),
]   # id, label, description[, "off" = unticked by default]

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
    """[(path, key, original, patched)], key = tuple of option ids applied."""
    en = lambda f: open(os.path.join(config.CLEAN_DAT, f), "rb").read()
    v = []
    exe = open(config.CLEAN_EXE, "rb").read()
    for n in range(1, len(P.EXE_PARTS) + 1):
        for key in itertools.combinations(P.EXE_PARTS, n):
            patched = P.patch_exe(exe, key)
            v.append(("BOF4.exe", key, exe, patched))
            # Steam: the same patch, applied in memory by the loader (steam\version.dll)
            v.append(("BOF4_Uncut_EN.mem", key, b"", mem_list(exe, patched).encode()))
    v.append(("version.dll", ("loader",), b"", open(os.path.join(HERE, "steam", "version.dll"), "rb").read()))
    for f, msgs in P.LINES.items():
        v.append(("DAT\\" + f, ("uncut",), en(f), P.patch_text(en(f), msgs)))
    for f in P.STORE:
        v.append(("DAT\\" + f, ("dengeki",), en(f), P.patch_store(en(f))))
    dll = open(os.path.join(HERE, "reverb", "bof4_reverb.dll"), "rb").read()
    for n in range(1, 4):                                              # same DLL serves all three options
        for key in itertools.combinations(("reverb", "loops", "fps60"), n):
            v.append(("bof4_reverb.dll", key, b"", dll))
    for f, patch in P.IDENTIFY_DATS.items():
        v.append(("DAT\\" + f, ("identify",), en(f), patch(en(f))))
    z = zipfile.ZipFile(DESC_ZIP)
    for n in z.namelist():
        f = n.replace(".bps", ".DAT")
        d = bps(en(f), z.read(n))
        v.append(("DAT\\" + f, ("desc",), en(f), d))
        if f in P.IDENTIFY_DATS:                                       # both options touch this file
            v.append(("DAT\\" + f, ("identify", "desc"), en(f), P.IDENTIFY_DATS[f](d)))
    return v

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
    ents = P.table(dst)                                    # DAT container: per chunk
    out = [("L", dst[:ents[0][0]])]
    for o, s, f, t in ents:
        c = dst[o:o + s]; k = src.find(c) if s >= 64 else -1
        out.append(("C", k, s) if k >= 0 else ("L", c))
    return out

def manifest():
    lines = ["O " + "|".join(o) for o in OPTIONS]
    for path, key, src, dst in build_variants():
        o = ops(src, dst)
        assert b"".join(src[a[1]:a[1] + a[2]] if a[0] == "C" else a[1] for a in o) == dst
        lines.append(f"F {path} {','.join(key)} {sha(src)} {sha(dst)}")
        lines += [f"C {a[1]} {a[2]}" if a[0] == "C" else "L " + base64.b64encode(a[1]).decode() for a in o]
    return "\n".join(lines) + "\n"

CSC = r"C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe"
ART = os.path.join(HERE, "art")
BANNER = (640, 230)                         # must match the banner size in installer.cs
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
    man = os.path.join(tmp, "manifest.txt")
    open(man, "w", encoding="ascii", newline="\n").write(manifest())
    banner, icon = make_art(tmp)
    exe = os.path.join(OUT, "BOF4_Uncut_EN.exe")
    subprocess.run([CSC, "/nologo", "/target:winexe", "/optimize+", f"/out:{exe}", f"/win32icon:{icon}",
                    f"/resource:{man},manifest.txt", f"/resource:{banner},banner.png",
                    "/r:System.Windows.Forms.dll", "/r:System.Drawing.dll",
                    os.path.join(HERE, "installer.cs")], check=True)
    for f in ("BOF4_Uncut_EN.ps1", "Install.bat", "Uninstall.bat"):   # older script-based installer
        if os.path.exists(os.path.join(OUT, f)): os.remove(os.path.join(OUT, f))
    print(f"built {exe} ({os.path.getsize(exe) // 1024} KB, manifest {os.path.getsize(man) // 1024} KB)")

if __name__ == "__main__":
    main()
