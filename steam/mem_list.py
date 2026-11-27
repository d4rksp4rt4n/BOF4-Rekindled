# The in-memory patch list for the dsound.dll loader (GOG and Steam): what patch_exe changes in the exe's sections,
# per option, so the loader can apply any combination (chosen in BOF4_Rekindled.ini) without a list per combination.
#   [always]            sites applied whenever the loader runs
#   [id]                sites of one installer option
#   VA ORIGHEX NEWHEX   a run of bytes (a byte may already hold the new value: options share stubs)
#   | VA HH             a feature byte the stubs read: OR-ed in after all sites (several options set bits of it)
# Header-only changes (section flags) are left out: the loader leaves the pages it writes writable.
# check() verifies that the loader's result equals patch_exe's for every combination of options.
import itertools, struct

def sections(exe):
    pe = struct.unpack_from("<I", exe, 0x3C)[0]
    n = struct.unpack_from("<H", exe, pe + 6)[0]
    base = struct.unpack_from("<I", exe, pe + 52)[0]
    sec = pe + 24 + struct.unpack_from("<H", exe, pe + 20)[0]
    for i in range(n):
        vs, va, rs, raw = struct.unpack_from("<4I", exe, sec + 40 * i + 8)
        yield base + va, raw, rs

def _va(secs, off):
    return next((v + off - raw for v, raw, rs in secs if raw <= off < raw + rs), None)

def _changes(orig, patched, secs):
    """{file offset: new byte} inside the sections"""
    return {i: patched[i] for i in range(len(orig)) if orig[i] != patched[i] and _va(secs, i) is not None}

def option_mem(exe, patch, options, always=(), max_run=1024):
    """patch(parts) -> patched exe; options: [(id, parts)]. Returns the .mem text."""
    secs = list(sections(exe))
    diffs = [("always", _changes(exe, patch(list(always)), secs))]
    for oid, parts in options:
        d = _changes(exe, patch(list(parts) + list(always)), secs)
        diffs.append((oid, {k: v for k, v in d.items() if diffs[0][1].get(k) != v}))
    seen, ors = {}, set()                                  # bytes written differently by two lists: feature bytes
    for _, d in diffs:
        for k, v in d.items():
            if k in seen and seen[k] != v: ors.add(k)
            seen.setdefault(k, v)
    out = []
    for oid, d in diffs:
        out.append(f"[{oid}]")
        keys = sorted(k for k in d if k not in ors)
        i = 0
        while i < len(keys):
            j = i
            while j + 1 < len(keys) and keys[j + 1] == keys[j] + 1 and keys[j + 1] - keys[i] < max_run: j += 1
            a, b = keys[i], keys[j] + 1
            out.append(f"{_va(secs, a):08X} {exe[a:b].hex()} {bytes(d[k] for k in range(a, b)).hex()}")
            i = j + 1
        out += [f"| {_va(secs, k):08X} {d[k]:02x}" for k in sorted(k for k in d if k in ors)]
    return "\n".join(out) + "\n"

def apply_mem(exe, mem, chosen):
    """what the loader does, on a copy of the exe file (sections only)"""
    secs = list(sections(exe)); off = lambda va: next(raw + va - v for v, raw, rs in secs if v <= va < v + rs)
    d = bytearray(exe); sec, ors = None, []
    for line in mem.splitlines():
        if line.startswith("["): sec = line[1:-1]; continue
        if sec != "always" and sec not in chosen: continue
        if line.startswith("|"):
            _, va, v = line.split(); ors.append((off(int(va, 16)), int(v, 16))); continue
        va, o, n = line.split(); o, n, k = bytes.fromhex(o), bytes.fromhex(n), off(int(va, 16))
        assert all(d[k + i] in (o[i], n[i]) for i in range(len(o))), f"site {va} holds unexpected bytes"
        d[k:k + len(n)] = n
    for k, v in ors: d[k] |= v
    return bytes(d)

def check(exe, patch, options, always, mem):
    secs = list(sections(exe))
    ids = [oid for oid, _ in options]
    for n in range(len(ids) + 1):
        for combo in itertools.combinations(ids, n):
            want = patch([p for oid, parts in options if oid in combo for p in parts] + list(always))
            got = apply_mem(exe, mem, set(combo))
            bad = [i for v, raw, rs in secs for i in range(raw, raw + rs) if got[i] != want[i]]
            assert not bad, f"loader result differs from patch_exe for {combo} at file offsets {[hex(b) for b in bad[:8]]}"
    return 2 ** len(ids)

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import config, patch_uncut_en as P, build_mod as B
    exe = open(config.CLEAN_EXE, "rb").read()
    opts = [(i, B.PARTS.get(i, (i,))) for i in B.EXE_OPTS]
    mem = option_mem(exe, lambda parts: P.patch_exe(exe, parts), opts, B.ALWAYS)
    print(check(exe, lambda parts: P.patch_exe(exe, parts), opts, B.ALWAYS, mem), "combinations match patch_exe;",
          sum(1 for l in mem.splitlines() if l and l[0] not in "[|"), "sites,", mem.count("\n|"), "feature bytes")
    open(sys.argv[1] if len(sys.argv) > 1 else "BOF4_Rekindled.mem", "w", newline="\n").write(mem)
