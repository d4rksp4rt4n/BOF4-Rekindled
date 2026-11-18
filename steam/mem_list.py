# The in-memory patch list for the Steam loader: every run of bytes patch_exe changes in the GOG exe's
# sections, as "VA ORIGHEX NEWHEX" lines (header-only changes such as section flags are left out; the
# loader leaves the pages it writes writable instead).
import struct

def sections(exe):
    pe = struct.unpack_from("<I", exe, 0x3C)[0]
    n = struct.unpack_from("<H", exe, pe + 6)[0]
    base = struct.unpack_from("<I", exe, pe + 52)[0]
    sec = pe + 24 + struct.unpack_from("<H", exe, pe + 20)[0]
    for i in range(n):
        vs, va, rs, raw = struct.unpack_from("<4I", exe, sec + 40 * i + 8)
        yield base + va, raw, rs

def mem_list(orig, patched, max_run=1024):
    assert len(orig) == len(patched)
    secs = list(sections(orig))
    lines, i = [], 0
    while i < len(orig):
        if orig[i] == patched[i]: i += 1; continue
        j = i
        while j < len(orig) and orig[j] != patched[j] and j - i < max_run: j += 1
        va = next((v + i - raw for v, raw, rs in secs if raw <= i < raw + rs), None)
        if va is not None: lines.append(f"{va:08X} {orig[i:j].hex()} {patched[i:j].hex()}")
        i = j
    return "\n".join(lines) + "\n"

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import config, patch_uncut_en as P
    exe = open(config.CLEAN_EXE, "rb").read()
    out = mem_list(exe, P.patch_exe(exe))
    assert out.count("\n") > 100
    for line in out.splitlines():                          # round trip: applying the list gives patch_exe's sections
        va, o, n = line.split(); assert len(o) == len(n) and o != n
    open(sys.argv[1] if len(sys.argv) > 1 else "BOF4_Uncut_EN.mem", "w", newline="\n").write(out)
    print(out.count("\n"), "sites")
