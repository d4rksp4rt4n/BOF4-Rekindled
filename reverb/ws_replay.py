# ws_replay.py [--old OLD.c] [--new NEW.c] [DUMP_DIR ...]
# Dump sets: reverb\ws_dumps\<name>\ws_dumpNNNN.txt (not committed), made with a debug DLL (dbg_patch.py).
# Regression check for the widescreen rules: compiles the real wide_exec from two versions of reverb/widescreen.c
# (default: the last commit vs the working copy) into a small x86 program, replays every saved F8 dump through both,
# and lists every primitive whose final x range on screen changes (with its keep value), grouped by dump set,
# command word and texture. "keep" 0 = squeezed (textured UI-z 2D also cut at the 4:3 edge), 1 = stretched with the
# screen, 2 = squeezed but not cut. With only --new it prints a summary of what each set's cut primitives are.
import glob, os, re, subprocess, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
VCVARS = r"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat"
OUT = os.path.join(REPO, "build_tmp", "ws_replay")

HARNESS = r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static unsigned int g_vtx_mem[(1 << 18) * 8], g_vtx_end, g_cmd_mem[1 << 18], g_cmd_end;
static int g_n_prim, g_pv0[1 << 16], g_pn[1 << 16];
static void on_exec(void);
#include "ws_src.c"
static void on_exec(void) {
    Vtx *v = (Vtx *)g_vtx_mem; int j, i;
    for (j = 0; j < g_n_prim; j++) {
        float x0 = 1e30f, x1 = -1e30f;
        for (i = g_pv0[j]; i < g_pv0[j] + g_pn[j]; i++) { if (v[i].x < x0) x0 = v[i].x; if (v[i].x > x1) x1 = v[i].x; }
        printf("%d %.1f %.1f\n", g_p[j].keep, x0, x1);
    }
}
/* stdin: per frame "F l t r b nprim", then per primitive "w tex n rhw z u v x y x y ..." or "VP x y w h" */
int main(void) {
    int rect[4], np, j, i, nv, nc;
    while (scanf(" F %d %d %d %d %d", &rect[0], &rect[1], &rect[2], &rect[3], &np) == 5) {
        Vtx *v = (Vtx *)g_vtx_mem; nv = nc = g_n_prim = 0;
        for (j = 0; j < np; j++) {
            char k[16]; unsigned int w, tex; int n; float rhw, z, u, vv;
            scanf(" %15s", k);
            if (!strcmp(k, "VP")) {
                unsigned int *c = g_cmd_mem + nc; c[0] = 0x1000; c[1] = 0;
                scanf(" %u %u %u %u", &c[2], &c[3], &c[4], &c[5]); nc += 6; continue;
            }
            w = (unsigned int)strtoul(k, 0, 16);
            scanf(" %x %d %f %f %f %f", &tex, &n, &rhw, &z, &u, &vv);
            g_cmd_mem[nc++] = w; g_cmd_mem[nc++] = tex;
            g_pv0[g_n_prim] = nv; g_pn[g_n_prim++] = n;
            for (i = 0; i < n; i++, nv++) {
                scanf(" %f %f", &v[nv].x, &v[nv].y);
                v[nv].z = z; v[nv].rhw = rhw; v[nv].col = 0; v[nv].spec = 0; v[nv].u = u; v[nv].v = vv;
            }
        }
        g_vtx_end = (unsigned int)(size_t)(v + nv); g_cmd_end = (unsigned int)(size_t)(g_cmd_mem + nc);
        printf("F\n");
        wide_exec(0, rect, 0);
        fflush(stdout);
    }
    return 0;
}
"""

def sub(s, a, b):
    assert s.count(a) == 1, a
    return s.replace(a, b)

def build(src_text, name):
    d = os.path.join(OUT, name); os.makedirs(d, exist_ok=True)
    s = src_text.replace("\r\n", "\n")
    s = sub(s, "#define VTX_BASE 0xA7C1D0", "#define VTX_BASE ((u32)(size_t)g_vtx_mem)")
    s = sub(s, "#define VTX_PTR  0x96DA70", "#define VTX_PTR  ((size_t)&g_vtx_end)")
    s = sub(s, "#define CMD_BASE 0xA758B8", "#define CMD_BASE ((u32)(size_t)g_cmd_mem)")
    s = sub(s, "#define CMD_PTR  0x96DA7C", "#define CMD_PTR  ((size_t)&g_cmd_end)")
    s = sub(s, "{ ((void (__cdecl *)(void *, int *, int))EXEC)(surf, rect, flag); }", "{ on_exec(); }")
    open(os.path.join(d, "ws_src.c"), "w").write(s)
    open(os.path.join(d, "replay.c"), "w").write(HARNESS)
    bat = os.path.join(d, "b.bat")
    open(bat, "w").write('@echo off\ncall "%s" x64_x86 >nul\ncd /d "%%~dp0"\n'
                         'cl /nologo /O2 /W3 /D_CRT_SECURE_NO_WARNINGS replay.c /Fe:replay.exe >build.log || exit /b 1\n' % VCVARS)
    r = subprocess.run(["cmd", "/c", bat], capture_output=True, text=True)
    if r.returncode: sys.exit(open(os.path.join(d, "build.log")).read())
    return os.path.join(d, "replay.exe")

PL = re.compile(r"P (\S+) tex (\S+) n (\d) rhw (\S+) z (\S+) x \S+ y \S+ col \S+ uv ([-\d.]+),([-\d.]+)")

def frames(path):
    """-> (stdin text for the harness, list of (w, tex) per primitive) for one dump file"""
    rect, items, ids, pend = None, [], [], None
    for l in open(path):
        if l.startswith("rect "): rect = l.split()[1:5]
        elif l.startswith("VP "): items.append(l.strip())
        elif l.startswith("P "):
            m = PL.match(l); pend = m.groups()
        elif l.startswith("V") and pend:
            xs = l.split()[1:]
            xy = " ".join("%s %s" % (xs[i], xs[i + 1]) for i in range(0, len(xs), 3))
            w, tex, n, rhw, z, u, v = pend
            items.append("%s %s %s %s %s %s %s %s" % (w, tex, n, rhw, z, u, v, xy)); ids.append((w, tex)); pend = None
    if not rect: return None, None
    return "F %s %d\n%s\n" % (" ".join(rect), len(items), "\n".join(items)), ids

def run(exe, inputs):
    r = subprocess.run([exe], input="".join(inputs), capture_output=True, text=True)
    out, cur = [], None
    for l in r.stdout.splitlines():
        if l == "F": cur = []; out.append(cur)
        else: cur.append(tuple(l.split()))
    return out

def main():
    args = sys.argv[1:]
    old = new = None
    if "--old" in args: i = args.index("--old"); old = open(args[i + 1]).read(); del args[i:i + 2]
    if "--new" in args: i = args.index("--new"); new = open(args[i + 1]).read(); del args[i:i + 2]
    if new is None: new = open(os.path.join(REPO, "reverb", "widescreen.c")).read()
    if old is None:
        old = subprocess.run(["git", "-C", REPO, "show", "HEAD:reverb/widescreen.c"], capture_output=True, text=True, check=True).stdout
    dirs = args or sorted(glob.glob(os.path.join(HERE, "ws_dumps", "*")))
    e_old, e_new = build(old, "old"), build(new, "new")
    total = changed = 0
    for d in dirs:
        files = sorted(glob.glob(os.path.join(d, "ws_dump*.txt")))
        inp, ids, names = [], [], []
        for f in files:
            t, i = frames(f)
            if t: inp.append(t); ids.append(i); names.append(os.path.basename(f))
        a, b = run(e_old, inp), run(e_new, inp)
        assert len(a) == len(b) == len(inp), (d, len(a), len(b), len(inp))
        groups = collections.defaultdict(list)
        for k in range(len(inp)):
            for j, (x, y) in enumerate(zip(a[k], b[k])):
                total += 1
                if x[1:] != y[1:]: changed += 1; groups[ids[k][j]].append((names[k], x, y))
        tag = os.path.basename(d)
        if not groups: print("%-14s %4d frames: no change" % (tag, len(inp))); continue
        print("%-14s %4d frames: CHANGED" % (tag, len(inp)))
        for (w, tex), L in sorted(groups.items(), key=lambda g: -len(g[1])):
            nf = len({n for n, _, _ in L})
            f, x, y = L[0]
            print("    %s tex %s: %d prims in %d frames, e.g. %s keep %s x %s..%s -> keep %s x %s..%s" % (w, tex, len(L), nf, f, *x, *y))
    print("%d primitives replayed, %d changed" % (total, changed))

if __name__ == "__main__":
    main()
