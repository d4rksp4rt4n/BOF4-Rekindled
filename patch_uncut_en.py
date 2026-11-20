# Breath of Fire IV (GOG): English "uncut", standalone.
#   py patch_uncut_en.py            switch the game to English and restore the cut content
#   py patch_uncut_en.py --restore  put back everything this script changed (German DAT, exe)
#
# 1. DAT\       English files from DAT_backup\ replace the German ones (German copies -> backup\german\).
# 2. Text       English lines the US release removed, from navarchos' PS1 "Uncensored" hack v1.12a:
#               Zig's ship AREAM027 70-78, Soniel AREAD157 29, Saldine bath AREAD145 67-76.
#               (Ryu/Ursula at the checkpoint, AREAM031, already has its text in the US release.)
# 3. BOF4.exe   a) re-adds the Saldine Island entry branch the US build dropped (flag B2 set, B3 clear ->
#                  set up the bath scene). Same branch navarchos restored in the PS1 overlay, in x86.
#               b) event-script redirects (AREAM031, AREAM027, AREAD157) that undo the US script cuts
#                  with navarchos' PS1 scripts; table derived by derive_scenes.py.
#               c) stutter fix: the per-frame colour-fill clear (which GOG's ddraw.dll does by reading
#                  the frame back from the GPU) becomes a Direct3D Clear.
#               d) Dengeki Store unlocked (event flags 0x8D/0xA5 held every frame).
#               e) Scias learns Identify; its element names become icons (identify_icons.py: INIT.DAT font,
#                  AB000_00/BTLEND labels, glyph metrics in the exe).
#               Dengeki Store text (AREAD068/AREAS052) = US PS1 English; missing chunks from the JP GOG release.
import base64, os, shutil, struct, sys, zlib
import identify_icons

GAME = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAT, EN = os.path.join(GAME, "DAT"), os.path.join(GAME, "DAT_backup")
BAK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backup")
EXE = os.path.join(GAME, "BOF4.exe")

H = bytes.fromhex
LINES = {
    "AREAM027.DAT": {
        70: H("0c06148242224e6f74207965742e2e2e0154686572652773206f6e65206d6f7265017468696e672e2e2e2200"),
        71: H("0c06148242225768656e2061207361696c6f72206d6573736573017468696e67732075702e2e2e0249276d20737570706f73656420746f01736d61636b2068696d206f6e207468652062757474017769746820746869732e2200"),
        72: H("0c0614824222496e206f7468657220776f7264732c01696620796f75277265206e6f7420726561647920746f017765617220796f75722070616e74696573206174026869702d6c6576656c20616c6c207468652074696d652e2e2e017765277265206e6f7420676f6e6e61206c657420796f75016f6e2074686520736869702e2200"),
        73: H("0c0614824222536f2c20686f772061626f757420796f752073686f7701757320796f757220627574743f2200"),
        74: H("140a0522492e2e2e0b492e2e2e200b0149206861766520746f2073686f7720796f75016d792062757474213f2200"),
        75: H("0c061480432259656168212055732067757973206c6f766520736f6d65016275747473212200"),
        76: H("0c06148242225365652c20796f752063616e277420646f2069742c0163616e2079613f024a757374206769766520757020616e6420676574017573656420746f2073746179696e2720686572652e2200"),
        77: H("0c0514440022596f75206a7573742077616e7420746f20736565016d7920627574742c2072696768743f2200"),
        78: H("14824222412e2e2e0b416c7269676874207468656e2c204920736565017468617420796f752074776f2061726520766572790164657465726d696e65642e2e2e024e6f772070757420796f75722070616e7473016f6e2e2e2e2200"),
    },
    "AREAD157.DAT": {
        29: H("1402022257656c6c21204a757374206173206578706563746564016f6620746865200956012e024576656e20696620616e20616d617465757201757365732069742c2069742063616e20656173696c790164616d616765206120676f642e2200"),
    },
    "AREAD145.DAT": {
        67: H("0c0514070122492e2e2e0b736d656c6c206c696b6520666973682e2200"),
        68: H("0c051441002249742773206265656e2061206c6f6e672074696d650173696e6365204927766520686164206120626174682e02497420636f756c64206265206e69636520746f20676f01666f722061206469702e2200"),
        # 2nd page speaker 0x0f -> 0x07 (Nina, as on page 1); 0x15 showed a broken Cray portrait on PC
        69: H("0c0514070122556d6d2e2e2e20796f752063616e2774206a757374016e6f6420616c6f6e672c2004002e0214070149276d20676f696e6720746f2074616b65206101626174682e20506c656173652c2067697665206d652001736f6d652070726976616379212200"),
        70: H("0c05140701225468616e6b20796f752c2004002e2200"),
        71: H("0c0214410022556d2c20636f756c6420796f7520706c65617365017374616e6420677561726420616e64206d616b650173757265206e6f206f6e6502636f6d6573206f7665723f014920646f6e27742077616e7420736f6d656f6e6501746f20736565206d652e2200"),
        72: H("0c02149041224168682c206974277320736f206e69636520616e6401636f6c642e0204042c20636f6d6520616e64206a6f696e016d65212200"),
        73: H("0c021491412241682c2074686973206665656c7320736f01676f6f64212200"),
        74: H("0c021492412249206e6576657220657870656374656420796f75276401626520736f2062656175746966756c2c0104042e2e2e2200"),
        75: H("0c0214130322486d70682e2054686572652773206d6f726520746f01626561757479207468616e2061016269672063686573742c2079276b6e6f772e2200"),
        76: H("0c021494412204002120592d0b596f75207374757069640170657276657274212200"),
    },
}


# Dengeki Store (AREAD068 / AREAS052): the English PC port shipped these with untranslated Japanese
# text and without two resources. Text = the US PS1 release's English (control codes converted to
# PC, same 32 message slots); the two missing chunks come from the Japanese GOG release (below).
STORE_TEXT = zlib.decompress(base64.b64decode("""
eNrtVcFuI0UQdbeVbFCAw2ovuZXNIZfZUVbRcuBiZQlaWewuIIeNklt7puxpedxtuntixtrTii9AICHxBfwAdz6CKwf+gC9YqrrH
jvcXEBlFcaarut579arckx/LC/mr/FN+1P+0P+n/3P/q4M3BjwefHH55+NfhzYPfH/y997w++uXot6M/jv75//mPPJdo5rjQMAnW
Ye9Rrze8xrqwS8xgnT4MxLOmhdY2zmM9AwVBFwsMmWjRj4acckJJlQpQWg6DtTIBghWlHQ0fvv3wJ07fZokXqJwB19ToxWuNa1g1
rqiUx7KL8OK5teW0TWDyPP+iGsmJda6FZQszp9GUVJvqlNacBjhVdwhobDOvxNIabPPhNvP4WzOzLjRGBazbTKzx1CGougZv6xJs
E8DOxIaQ64DLLu/zylqPkS+YZjlF5zOhZ5HZqkZC2gWOPWy0B6fnVYhE394Qp1c2Hn4dI6GKdQypARtEkRjmQ/no3bsbum9uw2fi
oP/ChoDE7yoeHw7iDRedHlBYHzycn52JDRrTAqqiyuV1hSZimjZtFj8UyogVpSToM3VnHdESHQdQfo/CQF7AutI1qTGj0jFFbDvB
nYe1rmuhDOlqCmTwcq2N0Wa+FSWXt8hq0u9TmGnng1g5vUGfwTl4LKwpdy+UKeGJDJV2JcR3uby6/wdIxfPsbEsw67J3h+L8jE8h
nUq+jPCkmvtBMaoLG8A3DbOfqWlT24YwGDuS+y4lNGYxEuPUWaLBZiIxiaKgvmaS7iGNKIH6R6YNVdKEo/2KTJh0jpYT1mRQLdM0
HEfrjQPRwGUUnSaByndW3U7C1m40YaDmStMNu4EasjlidKBJaYHHUCQPJb9RG1VBXbwl6YLmYeWj2pr5Y6HWipiX8H6/BIOHKdXq
elqSh/jVntH5mG1aN8WijfnoOkC0FGpWNoNxlAGKCouF4Kr7dJj58fBW81/GRn1xuFRuoaY1wX35+OVuhJO2XCpKWhHbgTzp0VTp
ENXiu+dObW1Eowpdj5NPRgN5xepwazdMFGuaOJ4CkmtFDe0UvqgGsK3AO4PcQstrt0tyKnqL73uOtsK+59igcf8N5E3yCnzH7opi
+QXJsdtewBOIrit9fEm4sk7JVAihGwNu4J5776vl8jIutmQyEoMXljaCkces+wVHJiNoCsqmzMUz5C0SFQWD34doDI4V4t5PRbRb
dIpYqzaNxUnvGtPxUhFbnoy5F91OISQzTU2gk3XFE88yD4YPf4iLXUzIGOLKqRLFK7yj+ksK7nTf7aWkPS3aXCbIwQZi1dL3gCer
ZmLcVfJsM81m2luPH0wE7cSofO1QlW26jvQgCXoQf7ZfY2Na5DCp7Eqk93AgnzwFKrIinSpK7vX+BcXtH3s=
"""))
STORE = ("AREAD068.DAT", "AREAS052.DAT")
# The two chunks the English port dropped from both store files, from the Japanese GOG release (whose
# files are otherwise identical): the clerk's portrait texture (LZHUF, 3 tiles -> VRAM 0x1E080200) and
# its 16-colour palette (-> RAM 0x2FC00).
_jp = zlib.decompress(base64.b64decode("""
eNoBrQNS/P38D3ztPbD1QMCNwAOJn5IOvOtpHP3YWvgg7P/Q+E/J//2aO7hh44Lw/6WGYz6l/u9+VJaL/h/7qXr/pmxl0deaT5X+L+oqyIhF
6j8X/+/xKd7/w3z60BI3LvylrtnAp8R/b8rxHAlxvmQBs+32P/LJ2t+Idt0gJaSxdOBbsf3VT9Z/9wmTr/OAl01UfnbkXvtk/7dShTIlhQUo
DPzO6p9s9xslMsmFOKGfxHkFEA7Us5Sqagf9E/pPOs9R3PcrA53FmdQaUoj4P6H/4NDi+HL1yx0lWlYeSPH//ynzvxrjB7+LrTgGUfzbu/eH
93/SJ3T/chmI2DxPg3YvwixSEw3Q/8+nu3+5OyWHWom+jv8ggojg//ent39Pe41UT6TzL3qx9QkUj22v9ydQfzW4A5sX+srLg/GD+/jv8IPe
T3r+k3RTUH/8CuT1/VT4H//7GCyMBoT/M6AbzZ/jf86npP/LznWpGAHGXpSWvTL/9xPT//XXuu2rHnf+ztl2Cu+nq/5g0/RccbQwmj0aPa+y
l+Kn+7+UvQ9DdRyYa7fto9MVP9XKP3z2P327nnbP9yTzp/r/C+ecgwewl1oIFueJ0w/5U5P+p1OkYxJ1O7Px+K9zV1X6NLb/sf0/fEQ+kEed
9GnP/GdmSa0/9J/bnOaf+2n7PxrujAc23C35pvjTPt3lz2TvjL7Ou6qEguQzq1pkJH6ysMBeB0IecDzQd0B9wH+gfmB0QDtgH/AOBAeqA/WB
7sBwgB9QB8wBe8AdcAf8AX+gHCgHyoF6oB1oB846UK8lVHPic8OqSmeC3HFQTv2nP+mR/yTVUTYu/JKZcrY2M1VG/tpPBvGv+KtGOpf7/q3K
8dN0/zlLcZLoOiVbJf9tPtn3787nKzOetir7Wz91+6+2vEjV/7pP8f1HUNvVeq3mGpFtKUARPuX/M33dCURf9dfk/OMG/CcV8k+EcXEb2n8a
qOVjGgPE/pMK/rf5+l+gaCqQzSAXL+A/Of+72f/8kh6YAlCJTWH1W4dPDvCfapvO/ug8e5mUvmd85yoWPnn/C9cI4TTvC/PG0qaZOxjlC59u
/Reze+OHjguKy2aDI1JU3Rc+3f0HZL2EA77KH+Cv255PsQp8/nBZ5q/1P7kD7sA6sA6cA+fAOXAPvAPvwDvwD/wD/wAcSOGcAPwAADnT0sKU
vlO6MroRtlPKNqoUvnfC9qmzqZKxTrEMqQAAe9u33njGN7ozvhK6M7JuxjHO0s4NwszFbblsqS2poXMGTw==
"""))
STORE_CHUNKS = [(_jp[:0x36D], 0x180001, 0x1E080200), (_jp[0x36D:], 0, 0x2FC00)]

def patch_store(en):
    e = table(en)
    ti = text_chunk(e)
    assert len(e) == ti + 1, "store file not as expected"
    chunks = [en[o:o + s] for o, s, f, t in e] + [c for c, f, t in STORE_CHUNKS]
    kinds = [(f, t) for o, s, f, t in e] + [(f, t) for c, f, t in STORE_CHUNKS]
    chunks[ti] = STORE_TEXT
    out, pos = bytearray(len(chunks) * 16), len(chunks) * 16
    for i, (c, (f, t)) in enumerate(zip(chunks, kinds)):
        struct.pack_into("<4I", out, i * 16, pos, len(c), f, t)
        out += c; pos += len(c)
    return bytes(out)

# ---------------------------------------------------------------- text chunks
def table(d):
    n = struct.unpack_from("<I", d, 0)[0] // 16
    return [list(struct.unpack_from("<4I", d, i * 16)) for i in range(n)]

def text_chunk(ents):
    # the message block is the untyped chunk right after the type-3 chunk
    i = next(i for i, e in enumerate(ents) if e[2] == 3 and e[3] == 3) + 1
    assert ents[i][2] == 0 and ents[i][3] == 0, "unexpected chunk layout"
    return i

def patch_text(d, msgs):
    ents = table(d)
    assert ents[0][0] == len(ents) * 16
    for a, b in zip(ents, ents[1:]):
        assert a[0] + a[1] == b[0], "chunks not contiguous"
    ti = text_chunk(ents)
    off, size = ents[ti][:2]
    t = bytearray(d[off:off + size])
    for idx, msg in sorted(msgs.items()):          # append, then repoint the message slot
        assert len(t) + len(msg) < 0x10000
        struct.pack_into("<H", t, idx * 2, len(t))
        t += msg
    out = bytearray(d[:off] + t + d[off + size:])
    delta = len(t) - size
    ents[ti][1] = len(t)
    for e in ents[ti + 1:]:
        e[0] += delta
    for i, e in enumerate(ents):
        struct.pack_into("<4I", out, i * 16, *e)
    # self-check: other chunks and existing text untouched, new lines where expected
    new = bytes(out)
    for i, (a, b) in enumerate(zip(table(d), table(new))):
        if i != ti:
            assert d[a[0]:a[0] + a[1]] == new[b[0]:b[0] + b[1]], f"chunk {i} changed"
    assert bytes(t[0x200:size]) == d[off + 0x200:off + size]
    for idx, msg in msgs.items():
        o = struct.unpack_from("<H", t, idx * 2)[0]
        assert bytes(t[o:o + len(msg)]) == msg
    return new

# ---------------------------------------------------------------- BOF4.exe
TEXT_VA, TEXT_RAW = 0x401000, 0x1200
def fo(va): return va - TEXT_VA + TEXT_RAW

SITE, RET = 0x454063, 0x4540EE      # "jne <return>" after the flag 0x1b/0x1c checks in the AREAD145 setup
CAVE = 0x6A7800                     # unused zero padding at the end of .text
FLAG_TEST, SCENE_START = 0x655AD0, 0x655C00

def rel(src_next, dst): return struct.pack("<i", dst - src_next)

def cave_code():
    c = bytearray()
    def emit(b): c.extend(b)
    def call(dst): emit(b"\xe8" + rel(CAVE + len(c) + 5, dst))
    def jcc(op, dst): emit(b"\x0f" + bytes([op]) + rel(CAVE + len(c) + 6, dst))
    def mov_w(addr, v): emit(b"\x66\xc7\x05" + struct.pack("<IH", addr, v & 0xffff))
    def mov_b(addr, v): emit(b"\xc6\x05" + struct.pack("<IB", addr, v))
    for flag, op in ((2, 0x84), (3, 0x85)):     # if (!flagB(2) || flagB(3)) return
        emit(bytes([0x6a, flag]) + b"\x68" + struct.pack("<I", 0xB566C4)); call(FLAG_TEST)
        emit(b"\x83\xc4\x08\x84\xc0"); jcc(op, RET)
    emit(b"\x80\x0d" + struct.pack("<I", 0xB557E4) + b"\x48")   # or byte [0xb557e4], 0x48
    emit(b"\x31\xc0")                                           # xor eax, eax
    for a in (0xB5665B, 0xB5665A, 0xB56659, 0xB56658):
        emit(b"\xa2" + struct.pack("<I", a))                    # mov [a], al
    mov_w(0xBAB530, 0x1A00); mov_w(0xBAB534, 0x1800); mov_w(0xBAB532, -0x200)
    mov_w(0xBAB538, 0x0A40); mov_w(0xBAB53A, -0x200); mov_w(0xBAB53C, 0)
    mov_w(0xBAB546, 0x1000); mov_w(0xBAB52E, 1)
    mov_b(0xB56656, 1); mov_b(0xB56657, 7); mov_b(0xB50611, 0x11)
    emit(b"\x6a\x04\x6a\x01\x6a\x00"); call(SCENE_START); emit(b"\x83\xc4\x0c")
    emit(b"\xe9" + rel(CAVE + len(c) + 5, RET))
    return bytes(c)

# Event-script redirects that undo the US release's script cuts, using navarchos' PS1 hack's scripts.
# Generated and checked by derive_scenes.py (US disc vs hack, mapped onto the exe's script data).
# When the script interpreter's next opcode is at `trigger`, continue at `insert` (or straight at
# `resume` for a skip); at the end of `insert`, continue at `resume`.
#   (trigger, insert, resume, check_va, original bytes at check_va)
DIVERTS = [
    (0x9241A5, H("180c080501c10f1001420744c26102c10f10030806011b071812"), 0x9241A7,      # AREAM031 checkpoint
     0x9241A1, H("0ad001041812020b0318")),
    (0x924653, None, 0x924654, 0x92464F, H("c3610017c4c01e4b98")),                        # AREAM031: early end
    (0x922906, None, 0x922922, 0x922902,                                                  # AREAM027 Zig's ship
     H("45000cc2c345024630c33119003f0f3d0e1448ff03471b1000000000000081c417180d42")),
    (0x90192B, H("17181042054418110f09001812c00cd0040217080e011814370f0810001e000b0f0901081001181614"),
     0x90193D, 0x901927, H("0d1c000cc0204802035431ff5c473510000000000000c4000014")),       # AREAD157 Soniel
]
FETCH_SITES = (0x4BC7FD, 0x4BEF7C, 0x4BEF8D)       # each: mov eax, [esi+0xc0] (script PC)
FETCH = b"\x8b\x86\xc0\x00\x00\x00"
REDIR = 0x6A7900                                   # after the bath branch, same padding
DATA_VA, DATA_RAW = 0x8D4000, 0x2BE200

def redirect_code():
    """Script inserts followed by the fetch hook. Returns (bytes, hook address)."""
    c, ends, jumps = bytearray(), [], []
    for trig, ins, resume, *_ in DIVERTS:
        start = REDIR + len(c)
        if ins: c += ins
        ends.append((trig, start if ins else None, REDIR + len(c) if ins else None, resume))
        if ins: c += bytes(4)   # gap: an insert's end must never be the next insert's start
    while len(c) % 16: c.append(0)
    hook = REDIR + len(c)
    here = lambda: REDIR + len(c)
    def jcc_to(label):                          # je rel32, target fixed up below
        c.extend(b"\x0f\x84\0\0\0\0"); jumps.append((len(c) - 4, label))
    c += FETCH                                  # eax = script PC
    for i, (trig, ins, end, resume) in enumerate(ends):
        c += b"\x3d" + struct.pack("<I", trig); jcc_to(("go", i))
        if ins: c += b"\x3d" + struct.pack("<I", end); jcc_to(("back", i))
    c += b"\xc3"                                # no match: original behaviour
    labels, store_jumps = {}, []
    for i, (trig, ins, end, resume) in enumerate(ends):
        labels[("go", i)] = here(); c += b"\xb8" + struct.pack("<I", ins or resume)
        c += b"\xe9\0\0\0\0"; store_jumps.append(len(c) - 4)
        if ins:
            labels[("back", i)] = here(); c += b"\xb8" + struct.pack("<I", resume)
            c += b"\xe9\0\0\0\0"; store_jumps.append(len(c) - 4)
    store = here(); c += b"\x89\x86\xc0\x00\x00\x00\xc3"   # [esi+0xc0] = eax; ret
    for pos, label in jumps:
        struct.pack_into("<i", c, pos, labels[label] - (REDIR + pos + 4))
    for pos in store_jumps:
        struct.pack_into("<i", c, pos, store - (REDIR + pos + 4))
    return bytes(c), hook

def make_text_writable(d):
    # script inserts now live in .text; the interpreter may write to script memory like it can in .data
    pe = struct.unpack_from("<I", d, 0x3C)[0]
    sec = pe + 24 + struct.unpack_from("<H", d, pe + 20)[0]
    assert d[sec:sec + 5] == b".text"
    struct.pack_into("<I", d, sec + 36, struct.unpack_from("<I", d, sec + 36)[0] | 0x80000000)

# Stutter fix: every frame the game black-fills its draw surface with a DirectDraw colour-fill Blt
# (0x40ABA1). GOG's ddraw.dll does that by reading the whole surface back from the GPU, which makes
# the CPU wait for the GPU every frame; a GPU hiccup then freezes the game. Instead: remember that a
# clear is due, and clear with IDirect3DDevice7::Clear right after the draw routine's BeginScene,
# when that surface is the render target and its viewport is the frame's draw area.
FILL_SITE = 0x40ABA1               # call 0x4096A0 (colour fill of the frame surface)
FILL_FN = 0x4096A0
BEGIN_SITE = 0x40A8F5              # mov eax,[dev]; push eax; mov edx,[eax]; call [edx+0x14] (BeginScene)
BEGIN_ORIG = bytes.fromhex("a100c2ab0050"          "8b10" "ff5214")
CLEAR = 0x6A7A40                   # flag byte, then the two stubs
DEVICE = 0xABC200                  # IDirect3DDevice7*

# Dengeki Store: the game opens it when event flags 0x8D and 0xA5 are set (BOF4+0x66E16F sets them
# when Japanese Dengeki memory-card data is found). Keep them set every frame (survives loading a save;
# saving writes them). Flag n = bit (n & 7) of byte 0xB5672C + (n >> 3).
DENGEKI_FLAGS = [(0xB5672C + (n >> 3), 1 << (n & 7)) for n in (0x8D, 0xA5)]

def clear_code(stutter=True, dengeki=True):
    flag = CLEAR
    c = bytearray(16)                               # [flag][pad]
    set_flag = CLEAR + len(c)
    c += b"\xc6\x05" + struct.pack("<I", flag) + b"\x01\xc3"           # mov byte [flag],1 ; ret
    while len(c) % 16: c.append(0xCC)
    begin = CLEAR + len(c)
    if dengeki:
        for byte, bit in DENGEKI_FLAGS:                                   # hold the Dengeki Store flags
            c += b"\x80\x0d" + struct.pack("<I", byte) + bytes([bit])     # or byte [flag byte], bit
    c += BEGIN_ORIG                                                       # BeginScene(device), as before
    if stutter:
        c += b"\x80\x3d" + struct.pack("<I", flag) + b"\x00"              # cmp byte [flag],0
        j = len(c); c += b"\x74\x00"                                      # je done
        c += b"\xc6\x05" + struct.pack("<I", flag) + b"\x00"              # mov byte [flag],0
        c += b"\xa1" + struct.pack("<I", DEVICE)                          # mov eax,[device]
        c += b"\x6a\x00\x68\x00\x00\x80\x3f\x6a\x00\x6a\x01\x6a\x00\x6a\x00"  # stencil 0, z 1.0, black, TARGET, NULL, 0
        c += b"\x50\x8b\x10\xff\x52\x28"                                  # push eax; mov edx,[eax]; call [edx+0x28] (Clear)
        c[j + 1] = len(c) - (j + 2)
    c += b"\xc3"                                                          # done: ret
    return bytes(c), set_flag, begin

# Music fixes in bof4_reverb.dll, loaded by a stub in the code cave on first use:
#   reverb: every decoded block (0x40FDB0 -> 0xABC6AC) goes through bof4_reverb_block(stream, flags)
#           (flags bit 1 = first block of a new stream, bit 0 = started by the music player)
#   loops:  0x40FD20 (new MP3 decoder) and 0x695030 (decode one frame) go through bof4_new_decoder /
#           bof4_decode, which jump from each recording's loop end to its loop start.
# No DLL (or a missing export): the stub falls back to the original functions.
MUSIC = 0x6A7B00                   # [music_next][features][pad2][fn_block][fn_newdec][fn_decode][loaded] code
STREAM_NEW, DECODE, NEW_DEC, DEC_FRAME = 0x40FC20, 0x40FDB0, 0x40FD20, 0x695030
MUSIC_SITE, FIRST_SITE, REFILL_SITE = 0x4D07A6, 0x40FC78, 0x41015F
NEWDEC_SITE, FRAME_SITE = 0x40FC6C, 0x40FDCD
LOADLIB, GETPROC = 0x8BE054, 0x8BE0E0          # kernel32 IAT entries

def music_code(reverb, loops):
    mn, feat, f_block, f_new, f_dec, loaded = MUSIC, MUSIC + 1, MUSIC + 4, MUSIC + 8, MUSIC + 12, MUSIC + 16
    c = bytearray(32); c[1] = (1 if reverb else 0) | (2 if loops else 0)
    a32 = lambda v: struct.pack("<I", v)
    here = lambda: MUSIC + len(c)
    fix = []                                            # (pos, label) absolute address fixups
    def ref(label): c.extend(b"\0\0\0\0"); fix.append((len(c) - 4, label))
    labels = {}
    ensure = here()                                     # load the DLL once; keeps all registers
    c += b"\x80\x3d" + a32(loaded) + b"\x00"            # cmp byte [loaded], 0
    j_done = len(c); c += b"\x75\x00"                   # jne done
    c += b"\x60"                                        # pushad
    c += b"\xc7\x05" + a32(f_block); ref("noop")        # defaults: originals / no-op
    c += b"\xc7\x05" + a32(f_new) + a32(NEW_DEC)
    c += b"\xc7\x05" + a32(f_dec) + a32(DEC_FRAME)
    c += b"\x68"; ref("dll"); c += b"\xff\x15" + a32(LOADLIB)
    c += b"\x89\xc6\x85\xf6"                            # mov esi, eax; test esi, esi
    j_fin = len(c); c += b"\x74\x00"                    # jz fin
    for name, slot in (("p_block", f_block), ("p_new", f_new), ("p_dec", f_dec)):
        c += b"\x68"; ref(name); c += b"\x56\xff\x15" + a32(GETPROC)   # GetProcAddress(esi, name)
        c += b"\x85\xc0\x74\x05" + b"\xa3" + a32(slot)  # test eax; jz +5; mov [slot], eax
    fin = len(c); c[j_fin + 1] = fin - (j_fin + 2)
    c += b"\xc6\x05" + a32(loaded) + b"\x01"            # mov byte [loaded], 1
    c += b"\x61"                                        # popad
    done = len(c); c[j_done + 1] = done - (j_done + 2)
    c += b"\xc3"
    labels["noop"] = here(); c += b"\xc3"
    call_ensure = lambda: c.extend(b"\xe8" + rel(here() + 5, ensure))

    create = here()                                     # music player's stream create
    c += b"\xc6\x05" + a32(mn) + b"\x01"                # music_next = 1
    call_ensure(); c += b"\xe9" + rel(here() + 5, STREAM_NEW)
    first = here()                                      # first block of a stream
    c += b"\xff\x74\x24\x04" + b"\xe8" + rel(here() + 9, DECODE) + b"\x83\xc4\x04"
    c += b"\x0f\xb6\x05" + a32(mn) + b"\xc6\x05" + a32(mn) + b"\x00" + b"\x83\xc8\x02"
    j_c = len(c); c += b"\xeb\x00"
    refill = here()                                     # later blocks
    c += b"\xff\x74\x24\x04" + b"\xe8" + rel(here() + 9, DECODE) + b"\x83\xc4\x04" + b"\x31\xc0"
    c[j_c + 1] = len(c) - (j_c + 2)
    call_ensure()                                       # eax (flags) kept by pushad/popad
    c += b"\x50\xff\x74\x24\x08\xff\x15" + a32(f_block) + b"\x83\xc4\x08\xc3"   # block(stream, flags)
    newdec = here(); call_ensure(); c += b"\xff\x25" + a32(f_new)              # jmp [fn_newdec]
    decode = here(); call_ensure(); c += b"\xff\x25" + a32(f_dec)              # jmp [fn_decode]
    for name, s in (("dll", b"bof4_reverb.dll"), ("p_block", b"bof4_reverb_block"),
                    ("p_new", b"bof4_new_decoder"), ("p_dec", b"bof4_decode")):
        labels[name] = here(); c += s + b"\0"
    for pos, label in fix: struct.pack_into("<I", c, pos, labels[label])
    return bytes(c), dict(create=create, first=first, refill=refill, newdec=newdec, decode=decode)

# Identify: the US release removed Scias' Identify (ability 0xEF, MAGIC239) from his level-up table; the
# PS1 Uncensored hack (navarchos' identify_3) puts it back at level 3. Entries are 8 bytes, the first is the
# ability learned; the screen itself is still in the PC exe. New games then start Scias with Identify.
# Its element names overlap on the PC too; identify_icons.py turns them into icons (IDENTIFY_DATS + metrics).
IDENTIFY_DATS = {"INIT.DAT": identify_icons.patch_font,
                 "AB000_00.DAT": identify_icons.patch_labels, "BTLEND.DAT": identify_icons.patch_labels}
SCIAS_LEVELS = bytes.fromhex("0700060017101322" "1f000b001e102131")   # his level 1 and 2 entries
IDENTIFY = 0xEF

# PS1 wobble: the map mesh renderer keeps each quad's screen corners twice, rounded (int16 0xB52F90..9F, what
# the PS1 drew) and exact (float 0xB52FA0..BF, what the PC port draws). On maps with a per-vertex effect
# ([0xB53029] != 0: North Chamba and a few others) it runs the effect and then rebuilds all eight floats from
# the rounded ints, so every corner snaps to whole PS1 pixels (up to 4 screen pixels at 1280x960) and the room
# swims like on a PS1. The rebuild (three copies, one per renderer) becomes: float += int - trunc(float).
# The ints are the truncated floats (ftol), so untouched corners stay exact and effects that move corners keep
# their offset.
WOBBLE_BLOCKS = (0x65F740, 0x660230, 0x661434)    # each: 8x movsx/fild/fstp, 0xA8 bytes, after call 0x6656B0
WOBBLE_LEN = 0xA8
SXY_INT, SXY_FLOAT, FTOL = 0xB52F90, 0xB52FA0, 0x69E924

def wobble_code():
    """[(va, bytes)]: the shared routine lives in the first block; every block calls it and skips the rest."""
    a32 = lambda v: struct.pack("<I", v)
    fix = WOBBLE_BLOCKS[0] + 10
    r = bytearray(b"\x56\x31\xf6")                                  # push esi; xor esi, esi
    loop = len(r)
    r += b"\xd9\x04\xb5" + a32(SXY_FLOAT)                          # fld dword [esi*4 + float]
    r += b"\xe8" + rel(fix + len(r) + 5, FTOL)                      # call ftol (truncates; eax)
    r += b"\x0f\xbf\xc0"                                            # movsx eax, ax
    r += b"\x0f\xbf\x0c\x75" + a32(SXY_INT)                        # movsx ecx, word [esi*2 + int]
    r += b"\x29\xc1"                                                # sub ecx, eax
    skip = len(r); r += b"\x74\x00"                                 # je next
    r += b"\x51\xdb\x04\x24"                                        # push ecx; fild dword [esp]
    r += b"\xd8\x04\xb5" + a32(SXY_FLOAT)                          # fadd dword [esi*4 + float]
    r += b"\xd9\x1c\xb5" + a32(SXY_FLOAT)                          # fstp dword [esi*4 + float]
    r += b"\x59"                                                    # pop ecx
    r[skip + 1] = len(r) - (skip + 2)
    r += b"\x46\x83\xfe\x08\x72" + bytes([(loop - (len(r) + 6)) & 0xFF])  # inc esi; cmp esi, 8; jb loop
    r += b"\x5e\xc3"                                                # pop esi; ret
    out = []
    for i, b in enumerate(WOBBLE_BLOCKS):
        c = b"\xe8" + rel(b + 5, fix) + b"\xe9" + rel(b + 10, b + WOBBLE_LEN)
        if i == 0: c += r
        out.append((b, c + b"\x90" * (WOBBLE_LEN - len(c))))
    return out

def wobble_orig_ok(d, b):              # call 0x6656B0; movsx r, [int x0] ... 8x fild [esp+n] ... fstp [float y3]
    blk = d[fo(b):fo(b) + WOBBLE_LEN]
    return (d[fo(b) - 5:fo(b)] == b"\xe8" + rel(b, 0x6656B0) and blk[:2] == b"\x0f\xbf"
            and blk[3:7] == struct.pack("<I", SXY_INT) and blk.count(b"\xdb\x44\x24") == 8
            and blk[-6:] == b"\xd9\x1d" + struct.pack("<I", SXY_FLOAT + 0x1C))

# 60 fps (reverb\fps60.c): the frame flush's screen pass (0x40AC03) and PutDrawEnv's present (0x410A47) go
# through bof4_fps_screen / bof4_fps_present in bof4_reverb.dll, which draw and present an interpolated
# in-between frame. A stub loads the DLL once; without it (or its exports) the original calls run.
FPS = 0x6A7D00                     # [loaded][features][pad2][fn_screen][fn_present][pad4] code
SCREEN_SITE, EXEC = 0x40AC03, 0x40A8A0
PRESENT_SITE, PRESENT = 0x410A47, 0x4028D0

def fps_code(fps60=True, wide=False):
    """features (read by the DLL): bit 0 = in-between frames and pacing, bit 1 = widescreen."""
    loaded, f_screen, f_present = FPS, FPS + 4, FPS + 8
    c = bytearray(16); c[1] = (1 if fps60 else 0) | (2 if wide else 0)
    a32 = lambda v: struct.pack("<I", v)
    here = lambda: FPS + len(c)
    fix, labels = [], {}
    def ref(label): c.extend(b"\0\0\0\0"); fix.append((len(c) - 4, label))
    ensure = here()
    c += b"\x80\x3d" + a32(loaded) + b"\x00"            # cmp byte [loaded], 0
    j_done = len(c); c += b"\x75\x00"                   # jne done
    c += b"\x60"                                        # pushad
    c += b"\xc7\x05" + a32(f_screen) + a32(EXEC)        # defaults: the original functions
    c += b"\xc7\x05" + a32(f_present) + a32(PRESENT)
    c += b"\x68"; ref("dll"); c += b"\xff\x15" + a32(LOADLIB)
    c += b"\x89\xc6\x85\xf6"                            # mov esi, eax; test esi, esi
    j_fin = len(c); c += b"\x74\x00"                    # jz fin
    c += b"\x68"; ref("p_screen"); c += b"\x56\xff\x15" + a32(GETPROC)
    c += b"\x89\xc3\x85\xdb"                            # mov ebx, eax; test ebx, ebx
    j_fin2 = len(c); c += b"\x74\x00"                   # jz fin (both exports or neither)
    c += b"\x68"; ref("p_present"); c += b"\x56\xff\x15" + a32(GETPROC)
    c += b"\x85\xc0"                                    # test eax, eax
    j_fin3 = len(c); c += b"\x74\x00"
    c += b"\x89\x1d" + a32(f_screen) + b"\xa3" + a32(f_present)
    fin = len(c)
    for j in (j_fin, j_fin2, j_fin3): c[j + 1] = fin - (j + 2)
    c += b"\xc6\x05" + a32(loaded) + b"\x01"            # mov byte [loaded], 1
    c += b"\x61"                                        # popad
    c[j_done + 1] = len(c) - (j_done + 2)
    c += b"\xc3"
    screen = here(); c += b"\xe8" + rel(here() + 5, ensure) + b"\xff\x25" + a32(f_screen)
    present = here(); c += b"\xe8" + rel(here() + 5, ensure) + b"\xff\x25" + a32(f_present)
    for name, s in (("dll", b"bof4_reverb.dll"), ("p_screen", b"bof4_fps_screen"), ("p_present", b"bof4_fps_present")):
        labels[name] = here(); c += s + b"\0"
    for pos, label in fix: struct.pack_into("<I", c, pos, labels[label])
    return bytes(c), screen, present

# Sprite depth scaling (reverb\sprites.c): characters are fixed-size sprites, so they look too big far away and
# too small up close next to the perspective-correct 3D. Three calls go through bof4_reverb.dll: the actor
# projection (anchor -> view depth) and the draw calls of the two character sprite packets (body 0x9C, shadow
# 0x96), which get their scale fields multiplied for the draw. Without the DLL (or its exports) the original
# calls run.
SPR = 0x6A7DC0                     # [loaded][fn x3] code
SPR_SITES = ((0x676C0B, 0x6641E0, b"bof4_spr_project"),    # call: project actor position (world, &sxy, &fxy)
             (0x402B48, 0x408B30, b"bof4_spr_draw96"),     # DrawOTag case 0x96: call draw(packet)
             (0x402B56, 0x409E10, b"bof4_spr_draw9c"))     # DrawOTag case 0x9C

def spr_code():
    """Stub that loads bof4_reverb.dll once and resolves all exports (or none); one jump stub per site."""
    a32 = lambda v: struct.pack("<I", v)
    loaded, fn = SPR, [SPR + 4 + 4 * i for i in range(len(SPR_SITES))]
    c = bytearray(4 + 4 * len(SPR_SITES))
    here = lambda: SPR + len(c)
    fix, labels = [], {}
    def ref(label): c.extend(b"\0\0\0\0"); fix.append((len(c) - 4, label))
    ensure = here()
    c += b"\x80\x3d" + a32(loaded) + b"\x00"            # cmp byte [loaded], 0
    j_done = len(c); c += b"\x0f\x85\0\0\0\0"           # jne done (near)
    c += b"\x60\x89\xe5"                                # pushad; mov ebp, esp
    for f, (_, orig, _) in zip(fn, SPR_SITES):
        c += b"\xc7\x05" + a32(f) + a32(orig)           # defaults: the original functions
    c += b"\x68"; ref("dll"); c += b"\xff\x15" + a32(LOADLIB)
    c += b"\x89\xc6\x85\xf6"                            # mov esi, eax; test esi, esi
    j_fin = [len(c)]; c += b"\x74\x00"                  # jz fin
    for i in range(len(SPR_SITES)):
        c += b"\x68"; ref(i); c += b"\x56\xff\x15" + a32(GETPROC)   # GetProcAddress(dll, name)
        c += b"\x85\xc0"; j_fin.append(len(c)); c += b"\x74\x00\x50"  # test eax, eax; jz fin; push eax
    for f in reversed(fn):
        c += b"\x58\xa3" + a32(f)                       # pop eax; mov [fn], eax
    fin = len(c)
    for j in j_fin: c[j + 1] = fin - (j + 2)
    c += b"\x89\xec"                                    # mov esp, ebp
    c += b"\xc6\x05" + a32(loaded) + b"\x01"            # mov byte [loaded], 1
    c += b"\x61"                                        # popad
    struct.pack_into("<i", c, j_done + 2, len(c) - (j_done + 6))
    c += b"\xc3"
    stubs = []
    for f in fn:
        stubs.append(here()); c += b"\xe8" + rel(here() + 5, ensure) + b"\xff\x25" + a32(f)
    labels["dll"] = here(); c += b"bof4_reverb.dll\0"
    for i, (_, _, name) in enumerate(SPR_SITES):
        labels[i] = here(); c += name + b"\0"
    for pos, label in fix: struct.pack_into("<I", c, pos, labels[label])
    return bytes(c), stubs

# Widescreen (reverb\widescreen.c): the game's render size comes from bof4.cfg (dxcfg.exe), and SetScale stretches the
# PS1's 320x240 to it, so at 16:9 everything is 33% too wide. The screen pass (same hook as 60 fps) squeezes each frame
# back to 4:3 proportions around the centre; the 3D scene then fills the sides (Hor+). That needs polygons the PS1
# culled: the renderers drop a polygon whose projected corners all fail "(x + 16) < 352" (unsigned 16-bit, PS1
# pixels, x in [-16, 336)). Each check is "add/lea r, [r + 0x10]" right before "cmp r16, 0x160"; both become
# x + 112 < 752 (x in [-112, 640): the left margin covers about 20:9, as far as the add's 8-bit immediate goes; the
# right one is wider so a polygon reaching past both sides still passes by its right corners). The list below is
# every such check in the exe; the one other
# "cmp ?x, 0x160" (0x475D09) is a loop counter. One more on-screen test (0x50C7E0, a point in [-32, 352]) widens too.
WIDE_CULLS = (                     # address of each cmp
    0x417F80, 0x417F9B, 0x417FB6, 0x417FD8, 0x4266FA, 0x426715, 0x426737, 0x426759,
    0x439983, 0x4399A5, 0x4399C7, 0x4399E9, 0x449FAC, 0x46E6E1, 0x46E702, 0x46E722,
    0x46E743, 0x5F31B1, 0x5F31CC, 0x5F31EE, 0x5F3210, 0x65F249, 0x65F269, 0x65F28A,
    0x65F2AB, 0x65FEE6, 0x65FF07, 0x65FF28, 0x65FF48, 0x661155, 0x661176, 0x661196,
    0x6611B7, 0x6625A7, 0x6625C2, 0x6625E4, 0x662606, 0x66317F, 0x66319A, 0x6631BC,
    0x6631DE, 0x66365E, 0x66367F, 0x66369F, 0x6636C0, 0x6660F0, 0x66610B, 0x66612D,
    0x66614F, 0x667340, 0x667362, 0x667384, 0x6673A6)
# The same checks' y half, "(y + 16) < 272": a big polygon over a screen corner can have no corner inside both, so it
# vanished from the far corners of a tilted view; its top margin becomes 112 too, and the bottom goes to 480 (y + 112
# < 592, y in [-112, 480)): a tall polygon reaching from above the screen to below it (a pillar beside the view in
# Meteor Strike) otherwise has no corner inside and vanishes.
# The add is "add r32, 0x10" or "add ax, 0x0010" right before "cmp r16, 0x110".
WIDE_YCULLS = (
    0x417F8B, 0x417FA6, 0x417FC8, 0x417FE7, 0x426705, 0x426727, 0x426749, 0x426768, 0x439995, 0x4399B7, 0x4399D9,
    0x4399FF, 0x449FBB, 0x46E6F2, 0x46E713, 0x46E734, 0x46E758, 0x5F31BC, 0x5F31DE, 0x5F3200, 0x5F321F, 0x65F25A,
    0x65F27B, 0x65F29B, 0x65F2C0, 0x65FEF8, 0x65FF18, 0x65FF39, 0x65FF5E, 0x661166, 0x661187, 0x6611A8, 0x6611CC,
    0x6625B2, 0x6625D4, 0x6625F6, 0x662615, 0x66318A, 0x6631AC, 0x6631CE, 0x6631ED, 0x66366F, 0x663690, 0x6636B1,
    0x6636D5, 0x6660FB, 0x66611D, 0x66613F, 0x66615E, 0x667352, 0x667374, 0x667396, 0x6673B5)
WIDE_ADD = {b"\x8d\x4a\x10": 1, b"\x8d\x48\x10": 1, b"\x83\xc1\x10": 1, b"\x83\xc0\x10": 0, b"\x83\xc2\x10": 2}
WIDE_CMP = {b"\x66\x81\xf9\x60\x01": 1, b"\x66\x81\xfa\x60\x01": 2, b"\x66\x3d\x60\x01": 0}   # cmp cx/dx/ax, 0x160
WIDE_CODE = ((0x50C835, b"\x66\x3d\x60\x01", b"\x66\x3d\xb0\x01"),       # cmp ax, 352 -> 432
             (0x50C83B, b"\x66\x3d\xe0\xff", b"\x66\x3d\x90\xff"),       # cmp ax, -32 -> -112
             # map vertex wave effect (0x555DE0): applied to corners with x + 16 < 352 only
             (0x555E10, H("83c010"), H("83c070")), (0x555E15, H("3d60010000"), H("3d20020000")),
             (0x555E66, H("83c110"), H("83c170")), (0x555E69, H("81f960010000"), H("81f920020000")),
             (0x555EAF, H("83c210"), H("83c270")), (0x555EB2, H("81fa60010000"), H("81fa20020000")),
             (0x555EF2, H("83c610"), H("83c670")), (0x555EF5, H("81fe60010000"), H("81fe20020000")))

# Map blocks are drawn only inside a window around the camera focus (0x660AD0 tests each block against the radii
# [0xB53008] / [0xB5300A], world units), sized for 4:3: at 16:9 the far corners stay empty when the camera turns.
# 0x660A20 copies the radii from 0xBAD81C/E (set by many scenes) every frame; its three callers go through a stub
# that doubles both afterwards (the far top corners of a tilted view need much more than the 4/3 of the width).
# Before that, 0x65ED60 / 0x65EF90 list the block rows to consider from the same radii in blocks (14 x 8 by default; a
# diamond |dx| + |dz| <= r for some maps, which left a diagonal staircase at the top corners): the load at 0x65ECF9 goes
# through a stub that doubles them too (28 rows each way; the list holds 64).
WIDE_WINDOW = 0x6A7F00             # after the sprites stub, same .text padding
WINDOW_FN, WINDOW_CALLS = 0x660A20, (0x65ED3C, 0x65ED4C, 0x660926)
SPAN_SITE = 0x65ECF9
SPAN_LOAD = H("66a11cd8ba00" "668b0d1ed8ba00")          # mov ax, [0xBAD81C]; mov cx, [0xBAD81E]
# Movies (0x40DDF0) are drawn by their own DrawPrimitive, not through the frame batch, with the video's pixel size taken
# as PS1 pixels. Their BeginScenes go through a stub that loads bof4_reverb.dll once and calls bof4_movie
# (reverb\widescreen.c), which fits the movie to the screen at its own aspect (4:3 pillarboxed, 16:9 filling the screen,
# any resolution) and clears the bars; without the DLL or the export, the original BeginScene runs.
MOVIE_SITES = (0x40E1A2, 0x40E23E)                         # two-texture and one-texture branch
MOVIE_ORIG = H("a100c2ab00" "50" "8b08" "ff5114")        # mov eax, [dev]; push eax; mov ecx, [eax]; call [ecx+0x14]

# Map polygons further away than the ordering table reaches (index = (deepest corner - offset) >> shift, [0xB52FE8],
# >= 0x400) were dropped: a 4:3 view never reached that far, a 16:9 one does at its top corners when the camera
# turns. Each renderer's "cmp word [0xB52FE8], 0x400; jae skip" calls a stub that first clamps a too-far index to
# 0x3FE (the back of the table; 0x3FF is a special value); negative ones (behind the camera) are still skipped.
OTZ = 0xB52FE8
OTZ_SITES = (0x42685A, 0x5F3311, 0x65F47B, 0x660122, 0x66134C, 0x662707, 0x6632DF, 0x666250, 0x6674A7)
OTZ_CMP = b"\x66\x81\x3d" + struct.pack("<I", OTZ) + b"\x00\x04"         # cmp word [OTZ], 0x400 (then jae)

# Frame buffers: every frame is built in a vertex buffer of 8192 D3DTLVERTEX (0xA7C1D0) and a command list of 2048
# entries (0xA758B8), with no bounds check and the game's own variables right after each (0xABC1D0..: the D3D device,
# the draw routine index at 0xABC234). The 4:3 view never filled them; with the sides drawn, a busy town (Synesta)
# overflows both and the game calls a null pointer and closes. The code that uses their addresses (9 + 5 places) reads
# them from variables instead ([vertex base][command base] at BUFS, initially the original buffers); the DLL puts
# bigger buffers in [pending vertex][pending command], and the frame start (where both pointers are reset) switches.
# The map renderers' PS1 packets (84 bytes per polygon, [0xB52FEC] the next one) go in two pools of 2048 at 0xB57400
# and 0xB81400 (by frame parity), again unchecked and right before the game's variables (0xBAB408: the program
# number). The pool start (0x65E9B1: shl ecx, 13; add ecx, 0xB57400; ecx = parity * 21) comes from [pool 0][pool 1]
# after the buffer variables instead; the DLL puts bigger pools there. They must lie below 16 MB (packets link by
# 24-bit address), where the game leaves no big free block, so they are the game's own vertex buffer once the bigger
# one is in use (3120 polygons) and both old pools as one (4096); Synesta's busiest view needs about 2250.
BUFS = 0x6A7C60                    # after the music stub, same .text padding
POOL_SITE, POOL0, POOL1 = 0x65E9B1, 0xB57400, 0xB81400
POOL_ORIG = H("c1e10d81c1") + struct.pack("<I", POOL0)
VTX_BUF, CMD_BUF = 0xA7C1D0, 0xA758B8
BUF_RESETS = (0x4029CC, 0x40B3DC)  # mov [cmd ptr], CMD_BUF; mov [vtx ptr], VTX_BUF (10 + 10 bytes)
BUF_RESET_ORIG = (H("c7057cda9600") + struct.pack("<I", CMD_BUF) + H("c70570da9600") + struct.pack("<I", VTX_BUF))
VTX_LOADS = (0x4042F3, 0x404366, 0x40AB59, 0x40ABD0, 0x40B1BD, 0x40B202)    # mov eax, VTX_BUF
VTX_ESP28, CMD_EBP, CMD_ESP34, CMD_CMP = 0x40A91E, 0x40A917, 0x40A92E, 0x40AB2F

def bufs_code():
    """Returns (code at BUFS, reset stub, esp28 stub, ebp stub, esp34 stub, cmp stub, pool stub)."""
    a32 = lambda v: struct.pack("<I", v)
    vb, cb, pv, pc, p0, p1 = BUFS, BUFS + 4, BUFS + 8, BUFS + 12, BUFS + 16, BUFS + 20
    c = bytearray(a32(VTX_BUF) + a32(CMD_BUF) + bytes(8) + a32(POOL0) + a32(POOL1))
    here = lambda: BUFS + len(c)
    reset = here()
    c += b"\x50" + b"\xa1" + a32(pv) + b"\x85\xc0"                      # push eax; mov eax, [pv]; test eax, eax
    j = len(c); c += b"\x74\x00"                                        # jz keep
    c += b"\xa3" + a32(vb) + b"\xa1" + a32(pc) + b"\xa3" + a32(cb)       # vb = pv; cb = pc
    c += b"\x31\xc0" + b"\xa3" + a32(pv)                                # pv = 0
    c[j + 1] = len(c) - (j + 2)
    c += b"\xa1" + a32(cb) + b"\xa3" + a32(0x96DA7C)                    # keep: cmd ptr = cb
    c += b"\xa1" + a32(vb) + b"\xa3" + a32(0x96DA70) + b"\x58\xc3"      # vtx ptr = vb; pop eax; ret
    esp28 = here()                                                      # [esp+0x28] = vb (no flags touched)
    c += b"\x50\xa1" + a32(vb) + H("89442430") + b"\x58\xc3"
    ebp = here(); c += b"\x8b\x2d" + a32(cb) + b"\xc3"                  # mov ebp, [cb]
    esp34 = here()                                                      # [esp+0x34] = cb + 8 (lea: flags kept)
    c += b"\x50\xa1" + a32(cb) + H("8d4008") + H("8944243c") + b"\x58\xc3"
    cmp = here(); c += b"\x3b\x05" + a32(cb) + b"\xc3"                  # cmp eax, [cb]
    pool = here()                                                       # ecx = ecx ? [p1] : [p0]
    c += H("85c98b0d") + a32(p0) + H("74068b0d") + a32(p1) + b"\xc3"
    assert BUFS + len(c) <= FPS
    return bytes(c), reset, esp28, ebp, esp34, cmp, pool

def window_code():
    """Returns (code, otz stub address, span stub address, movie stub address)."""
    c = bytearray(b"\xe8" + rel(WIDE_WINDOW + 5, WINDOW_FN))
    for a in (0xB53008, 0xB5300A):
        c += b"\x66\xd1\x25" + struct.pack("<I", a)      # shl word [a], 1
    c += b"\xc3"
    otz = WIDE_WINDOW + len(c)
    c += b"\x50\xa1" + struct.pack("<I", OTZ)            # push eax; mov eax, [OTZ]
    c += b"\x3d\x00\x04\x00\x00\x7c\x0a"                # cmp eax, 0x400; jl +10
    c += b"\xc7\x05" + struct.pack("<I", OTZ) + struct.pack("<I", 0x3FE)   # mov dword [OTZ], 0x3FE
    c += b"\x58" + OTZ_CMP + b"\xc3"                     # pop eax; cmp word [OTZ], 0x400; ret
    span = WIDE_WINDOW + len(c)
    c += SPAN_LOAD + b"\x66\x01\xc0\x66\x01\xc9\xc3"     # (the two loads); add ax, ax; add cx, cx; ret
    a32 = lambda v: struct.pack("<I", v)
    here = lambda: WIDE_WINDOW + len(c)
    loaded = here(); c += bytes(4)                                         # [loaded][pad3]
    f_movie = here(); c += bytes(4)                                        # bof4_movie, or the original BeginScene
    orig = here(); c += MOVIE_ORIG + b"\xc3"
    c[f_movie - WIDE_WINDOW:f_movie - WIDE_WINDOW + 4] = a32(orig)
    fix = []
    def ref(label): c.extend(bytes(4)); fix.append((len(c) - 4, label))
    movie = here()
    c += b"\x80\x3d" + a32(loaded) + b"\x00"                              # cmp byte [loaded], 0
    j_go = len(c); c += b"\x75\x00"                                        # jne go
    c += b"\x60\xc6\x05" + a32(loaded) + b"\x01"                          # pushad; mov byte [loaded], 1
    c += b"\x68"; ref("dll"); c += b"\xff\x15" + a32(LOADLIB)              # LoadLibraryA("bof4_reverb.dll")
    c += b"\x85\xc0"; j1 = len(c); c += b"\x74\x00"                        # test eax, eax; jz fin
    c += b"\x68"; ref("fn"); c += b"\x50\xff\x15" + a32(GETPROC)           # GetProcAddress(dll, "bof4_movie")
    c += b"\x85\xc0"; j2 = len(c); c += b"\x74\x00"                        # test eax, eax; jz fin
    c += b"\xa3" + a32(f_movie)                                            # mov [f_movie], eax
    for j in (j1, j2): c[j + 1] = len(c) - (j + 2)
    c += b"\x61"                                                           # fin: popad
    c[j_go + 1] = len(c) - (j_go + 2)
    c += b"\xff\x25" + a32(f_movie)                                        # go: jmp [f_movie]
    labels = {"dll": here()}; c += b"bof4_reverb.dll\0"
    labels["fn"] = here(); c += b"bof4_movie\0"
    for pos, label in fix: c[pos:pos + 4] = a32(labels[label])
    return bytes(c), otz, span, movie

def wide_culls(d):
    """[(file offset, new bytes)]; asserts every site's original instructions."""
    out = []
    for va in WIDE_CULLS:
        o = fo(va)
        cmp = [c for c in WIDE_CMP if d[o:o + len(c)] == c]
        assert len(cmp) == 1 and WIDE_ADD.get(bytes(d[o - 3:o])) == WIDE_CMP[cmp[0]], f"unexpected cull at {va:#x}"
        out += [(o - 1, b"\x70"), (o + len(cmp[0]) - 2, struct.pack("<H", 0x70 + 640))]
    for va in WIDE_YCULLS:
        o = fo(va)
        if d[o:o + 4] == b"\x66\x3d\x10\x01": n, reg = 4, 0                      # cmp ax, 0x110
        else:
            assert d[o:o + 3] in (b"\x66\x81" + bytes([0xf8 + r]) for r in range(8)) and d[o + 3:o + 5] == b"\x10\x01", \
                f"unexpected y cull at {va:#x}"
            n, reg = 5, d[o + 2] - 0xf8                                              # cmp r16, 0x110
        if d[o - 4:o] == b"\x66\x05\x10\x00": assert reg == 0; imm = o - 2           # add ax, 0x0010
        else:
            assert d[o - 3] == 0x83 and d[o - 2] == 0xc0 + reg and d[o - 1] == 0x10, f"unexpected y cull at {va:#x}"
            imm = o - 1                                                              # add r32, 0x10
        out += [(imm, b"\x70"), (o + n - 2, struct.pack("<H", 0x70 + 480))]
    for va, orig, new in WIDE_CODE:
        assert d[fo(va):fo(va) + len(orig)] == orig, f"unexpected code at {va:#x}"
        out.append((fo(va), new))
    return out

EXE_PARTS = ("uncut", "dengeki", "stutter", "reverb", "loops", "identify", "fps60", "wobble", "sprites", "widescreen")

def patch_exe(d, parts=EXE_PARTS):
    d = bytearray(d)
    orig_jne = b"\x0f\x85" + rel(SITE + 6, RET)
    assert d[fo(SITE):fo(SITE) + 6] == orig_jne, "BOF4.exe is not the expected GOG build"
    code = cave_code()
    assert REDIR >= CAVE + len(code)
    redir, hook = redirect_code()
    clear, set_flag, begin = clear_code("stutter" in parts, "dengeki" in parts)
    assert CLEAR >= REDIR + len(redir) + 16
    assert d[fo(CAVE):fo(CLEAR) + len(clear) + 16] == bytes(CLEAR - CAVE + len(clear) + 16), "code cave not free"
    assert d[fo(FILL_SITE):fo(FILL_SITE) + 5] == b"\xe8" + rel(FILL_SITE + 5, FILL_FN), "unexpected code at fill site"
    assert d[fo(BEGIN_SITE):fo(BEGIN_SITE) + 11] == BEGIN_ORIG, "unexpected code at BeginScene site"
    for site in FETCH_SITES:
        assert d[fo(site):fo(site) + 6] == FETCH, f"unexpected code at {site:#x}"
    for trig, ins, resume, va, orig in DIVERTS:
        o = va - DATA_VA + DATA_RAW
        assert d[o:o + len(orig)] == orig, f"unexpected event script at {va:#x}"
    music = "reverb" in parts or "loops" in parts
    mc, at = music_code("reverb" in parts, "loops" in parts)
    assert MUSIC >= CLEAR + len(clear_code()[0]) + 16 and MUSIC + len(mc) <= 0x6A8000
    sites = ((MUSIC_SITE, STREAM_NEW, "create"), (FIRST_SITE, DECODE, "first"), (REFILL_SITE, DECODE, "refill"),
             (NEWDEC_SITE, NEW_DEC, "newdec"), (FRAME_SITE, DEC_FRAME, "decode"))
    for site, fn, _ in sites:
        assert d[fo(site):fo(site) + 5] == b"\xe8" + rel(site + 5, fn), f"unexpected code at {site:#x}"
    if music:
        assert d[fo(MUSIC):fo(MUSIC) + len(mc)] == bytes(len(mc)), "music cave not free"
        d[fo(MUSIC):fo(MUSIC) + len(mc)] = mc
        want = {"create"} | ({"first", "refill"} if "reverb" in parts else set()) | ({"newdec", "decode"} if "loops" in parts else set())
        for site, fn, name in sites:
            if name in want: d[fo(site):fo(site) + 5] = b"\xe8" + rel(site + 5, at[name])
        make_text_writable(d)                              # stub data lives in the cave
    if "stutter" in parts or "dengeki" in parts:          # per-frame hook after BeginScene
        d[fo(CLEAR):fo(CLEAR) + len(clear)] = clear
        d[fo(BEGIN_SITE):fo(BEGIN_SITE) + 11] = b"\xe8" + rel(BEGIN_SITE + 5, begin) + b"\x90" * 6
    if "stutter" in parts:
        d[fo(FILL_SITE):fo(FILL_SITE) + 5] = b"\xe8" + rel(FILL_SITE + 5, set_flag)
        make_text_writable(d)                              # its flag byte lives in the cave
    fc, f_screen, f_present = fps_code("fps60" in parts, "widescreen" in parts)
    assert FPS >= MUSIC + len(mc) and FPS + len(fc) <= 0x6A8000
    assert d[fo(SCREEN_SITE):fo(SCREEN_SITE) + 5] == b"\xe8" + rel(SCREEN_SITE + 5, EXEC), "unexpected code at screen pass"
    assert d[fo(PRESENT_SITE):fo(PRESENT_SITE) + 5] == b"\xe8" + rel(PRESENT_SITE + 5, PRESENT), "unexpected code at present"
    culls = wide_culls(d)
    if "fps60" in parts or "widescreen" in parts:         # both go through the screen pass hook
        assert d[fo(FPS):fo(FPS) + len(fc)] == bytes(len(fc)), "fps60 cave not free"
        d[fo(FPS):fo(FPS) + len(fc)] = fc
        d[fo(SCREEN_SITE):fo(SCREEN_SITE) + 5] = b"\xe8" + rel(SCREEN_SITE + 5, f_screen)
        make_text_writable(d)                              # stub data lives in the cave
    if "fps60" in parts:
        d[fo(PRESENT_SITE):fo(PRESENT_SITE) + 5] = b"\xe8" + rel(PRESENT_SITE + 5, f_present)
    wc, otz, span, movie = window_code()
    assert WIDE_WINDOW >= SPR + len(spr_code()[0]) and WIDE_WINDOW + len(wc) <= 0x6A8000
    assert d[fo(SPAN_SITE):fo(SPAN_SITE) + len(SPAN_LOAD)] == SPAN_LOAD, f"unexpected code at {SPAN_SITE:#x}"
    for site in MOVIE_SITES:
        assert d[fo(site):fo(site) + len(MOVIE_ORIG)] == MOVIE_ORIG, f"unexpected code at {site:#x}"
    for site in WINDOW_CALLS:
        assert d[fo(site):fo(site) + 5] == b"\xe8" + rel(site + 5, WINDOW_FN), f"unexpected code at {site:#x}"
    for site in OTZ_SITES:
        assert d[fo(site):fo(site) + 11] == OTZ_CMP + b"\x0f\x83", f"unexpected code at {site:#x}"
    if "widescreen" in parts:
        for o, b in culls: d[o:o + len(b)] = b
        assert d[fo(WIDE_WINDOW):fo(WIDE_WINDOW) + len(wc)] == bytes(len(wc)), "widescreen cave not free"
        d[fo(WIDE_WINDOW):fo(WIDE_WINDOW) + len(wc)] = wc
        for site in WINDOW_CALLS:
            d[fo(site):fo(site) + 5] = b"\xe8" + rel(site + 5, WIDE_WINDOW)
        for site in OTZ_SITES:                              # call stub; nop x4; (jae skip as before)
            d[fo(site):fo(site) + 9] = b"\xe8" + rel(site + 5, otz) + b"\x90" * 4
        d[fo(SPAN_SITE):fo(SPAN_SITE) + len(SPAN_LOAD)] = b"\xe8" + rel(SPAN_SITE + 5, span) + b"\x90" * 8
        for site in MOVIE_SITES:
            d[fo(site):fo(site) + len(MOVIE_ORIG)] = b"\xe8" + rel(site + 5, movie) + b"\x90" * 6
        bc, reset, esp28, ebp, esp34, cmp, pool = bufs_code()   # frame buffers through variables (bigger from the DLL)
        assert d[fo(BUFS):fo(BUFS) + len(bc)] == bytes(len(bc)), "frame buffer cave not free"
        d[fo(BUFS):fo(BUFS) + len(bc)] = bc
        for site in BUF_RESETS:
            assert d[fo(site):fo(site) + 20] == BUF_RESET_ORIG, f"unexpected code at {site:#x}"
            d[fo(site):fo(site) + 20] = b"\xe8" + rel(site + 5, reset) + b"\x90" * 15
        for site in VTX_LOADS:
            assert d[fo(site):fo(site) + 5] == b"\xb8" + struct.pack("<I", VTX_BUF), f"unexpected code at {site:#x}"
            d[fo(site):fo(site) + 5] = b"\xa1" + struct.pack("<I", BUFS)
        for site, orig, stub in ((VTX_ESP28, H("c7442428") + struct.pack("<I", VTX_BUF), esp28),
                                 (CMD_EBP, b"\xbd" + struct.pack("<I", CMD_BUF), ebp),
                                 (CMD_ESP34, H("c7442434") + struct.pack("<I", CMD_BUF + 8), esp34),
                                 (CMD_CMP, b"\x3d" + struct.pack("<I", CMD_BUF), cmp)):
            assert d[fo(site):fo(site) + len(orig)] == orig, f"unexpected code at {site:#x}"
            d[fo(site):fo(site) + len(orig)] = b"\xe8" + rel(site + 5, stub) + b"\x90" * (len(orig) - 5)
        assert d[fo(POOL_SITE):fo(POOL_SITE) + 9] == POOL_ORIG, f"unexpected code at {POOL_SITE:#x}"
        d[fo(POOL_SITE):fo(POOL_SITE) + 9] = b"\xe8" + rel(POOL_SITE + 5, pool) + b"\x90" * 4
        make_text_writable(d)                              # the movie stub and the frame buffer variables live in the cave
    sc, stubs = spr_code()
    assert SPR >= FPS + len(fc) and SPR + len(sc) <= 0x6A8000
    for site, fn, _ in SPR_SITES:
        assert d[fo(site):fo(site) + 5] == b"\xe8" + rel(site + 5, fn), f"unexpected code at {site:#x}"
    if "sprites" in parts:
        assert d[fo(SPR):fo(SPR) + len(sc)] == bytes(len(sc)), "sprites cave not free"
        d[fo(SPR):fo(SPR) + len(sc)] = sc
        for (site, _, _), stub in zip(SPR_SITES, stubs):
            d[fo(site):fo(site) + 5] = b"\xe8" + rel(site + 5, stub)
        make_text_writable(d)                              # stub data lives in the cave
    for b in WOBBLE_BLOCKS:
        assert wobble_orig_ok(d, b), f"unexpected code at {b:#x}"
    if "wobble" in parts:
        for va, c in wobble_code(): d[fo(va):fo(va) + len(c)] = c
    lv = d.find(SCIAS_LEVELS)
    assert lv > 0 and d.count(SCIAS_LEVELS) == 1 and d[lv + 16] == 0, "Scias' level-up table not as expected"
    if "identify" in parts:
        d[lv + 16] = IDENTIFY                              # level 3 entry
        d[:] = identify_icons.patch_metrics(d, lambda va: va - DATA_VA + DATA_RAW)
        d[:] = identify_icons.patch_code(d, fo)            # unknown-item "?" spacing
    if "uncut" in parts:
        d[fo(CAVE):fo(CAVE) + len(code)] = code
        d[fo(SITE):fo(SITE) + 6] = b"\x0f\x85" + rel(SITE + 6, CAVE)
        d[fo(REDIR):fo(REDIR) + len(redir)] = redir
        for site in FETCH_SITES:                # mov eax,[esi+0xc0] -> call hook; nop
            d[fo(site):fo(site) + 6] = b"\xe8" + rel(site + 5, hook) + b"\x90"
        make_text_writable(d)
    return bytes(d)

# ---------------------------------------------------------------- main
def same(a, b):
    return os.path.getsize(a) == os.path.getsize(b) and open(a, "rb").read() == open(b, "rb").read()

def install():
    assert os.path.isdir(EN), "DAT_backup (English GOG files) not found"
    os.makedirs(os.path.join(BAK, "german"), exist_ok=True)
    switched = 0
    for f in os.listdir(EN):
        src, dst = os.path.join(EN, f), os.path.join(DAT, f)
        if not os.path.isfile(src) or f in LINES or f in STORE or f in IDENTIFY_DATS:
            continue
        if os.path.exists(dst) and not same(src, dst):
            keep = os.path.join(BAK, "german", f)
            if not os.path.exists(keep):
                shutil.copy2(dst, keep)
            shutil.copy2(src, dst)
            switched += 1
    for f, msgs in LINES.items():
        dst, keep = os.path.join(DAT, f), os.path.join(BAK, "german", f)
        if not os.path.exists(keep):
            shutil.copy2(dst, keep)
        open(dst, "wb").write(patch_text(open(os.path.join(EN, f), "rb").read(), msgs))
    for f in STORE:
        dst, keep = os.path.join(DAT, f), os.path.join(BAK, "german", f)
        if not os.path.exists(keep):
            shutil.copy2(dst, keep)
        open(dst, "wb").write(patch_store(open(os.path.join(EN, f), "rb").read()))
    for f, patch in IDENTIFY_DATS.items():
        dst, keep = os.path.join(DAT, f), os.path.join(BAK, "german", f)
        if not os.path.exists(keep):
            shutil.copy2(dst, keep)
        open(dst, "wb").write(patch(open(os.path.join(EN, f), "rb").read()))
    print(f"DAT: {switched} files switched to English, {len(LINES)} areas patched with restored lines, "
          f"Dengeki Store in English")

    exe_bak = os.path.join(BAK, "BOF4.exe")
    if not os.path.exists(exe_bak):
        shutil.copy2(EXE, exe_bak)
    open(EXE, "wb").write(patch_exe(open(exe_bak, "rb").read()))
    print("BOF4.exe: Saldine Island bath branch, scene redirects, GPU clear instead of readback")


def restore():
    g = os.path.join(BAK, "german")
    for f in os.listdir(g):
        shutil.copy2(os.path.join(g, f), os.path.join(DAT, f))
    for name, dst in (("BOF4.exe", EXE),):
        if os.path.exists(os.path.join(BAK, name)):
            shutil.copy2(os.path.join(BAK, name), dst)
    print("restored German DAT files and BOF4.exe")

if __name__ == "__main__":
    restore() if "--restore" in sys.argv else install()
