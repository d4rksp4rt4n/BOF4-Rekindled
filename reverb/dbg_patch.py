# dbg_patch.py SRC DST [FPS_SRC FPS_DST]: writes a copy of widescreen.c with an F8 primitive dump (ws_dumpNNNN.txt next to the
# exe; F8 toggles it, or a file named ws_dump.on keeps it on). Each F8 press also saves the game's data areas
# (0x6A8000-0x8BE000 and 0x8D4000-0xC78000) to ws_memNN.bin, to find state variables by comparing screens.
# ws_crash.txt logs the start, serious exceptions anywhere in the process (code, address, registers, stack) and the
# exit, to tell a crash from a clean exit when the game simply closes; it writes through a handle opened at start,
# without the C runtime or the heap, so it works inside a crash. Build DST with the other reverb\*.c into a debug
# bof4_reverb.dll; the dumps feed ws_replay.py. Testing aids: F7 switches random encounters (off at start), F6 opens
# the save screen on a map (save anywhere), F2 switches the widescreen exe's screen-bounds checks and depth clamp, F3
# its map block window, each between widescreen and the game's own (tables built from patch_uncut_en and the clean
# exe in config.py). With FPS_SRC FPS_DST it also writes a copy of fps60.c (needs the 60 fps
# option in the exe): F5 pause/resume, F4 one frame while paused, F8 while paused one frame dumped, F9 held fast
# forward, and each F8 press saves a screenshot ws_shotNN.bmp (numbered like ws_memNN.bin; ws_crash.txt lists which
# dump file each press starts at). F11 switches everything between widescreen and the game's own 4:3 (F2, F3 and the
# DLL's pass together); F12 shoots one frame widescreen and the next in 4:3 into ws_abNN.bmp, side by side (paused:
# it runs those frames and one more, then pauses again).
import os, sys
src, dst = sys.argv[1], sys.argv[2]
s = open(src).read()
def rep(a, b):
    global s
    assert s.count(a) == 1, a
    s = s.replace(a, b)

# F2 / F3 tables: each widescreen exe change as (address, game's bytes, widescreen bytes), from patch_uncut_en itself
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config, patch_uncut_en as P
clean = open(config.CLEAN_EXE, "rb").read()
va = lambda o: o - P.TEXT_RAW + P.TEXT_VA
_, otz, span, _, rect = P.window_code()
cull = [(va(o), clean[o:o + len(b)], b) for o, b in P.wide_culls(clean)]
cull += [(a, P.OTZ_CMP, b"\xe8" + P.rel(a + 5, otz) + b"\x90" * 4) for a in P.OTZ_SITES]
dbl = b"".join(b"\x66\xd1\x25" + P.struct.pack("<I", a) for a in (0xB53008, 0xB5300A))   # the radius stub's shl
window = [(P.WIDE_WINDOW + 5, b"\x90" * len(dbl), dbl),
          (P.SPAN_SITE, P.SPAN_LOAD, b"\xe8" + P.rel(P.SPAN_SITE + 5, span) + b"\x90" * (len(P.SPAN_LOAD) - 5)),
          (P.RECT_SITE, b"\xe8" + P.rel(P.RECT_SITE + 5, P.RECT_FN), b"\xe8" + P.rel(P.RECT_SITE + 5, rect))]
def table(name, rows):
    c = lambda b: "{" + ",".join(str(x) for x in b) + "}"
    return (f"static const struct Patch {name}[] = {{\n" +
            ",\n".join(f"    {{0x{a:X}, {len(o)}, {c(o)}, {c(w)}}}" for a, o, w in rows) + "};\n")
SWAP = ("struct Patch { u32 va; int n; u8 own[16], wide[16]; };\n" + table("g_cull", cull) + table("g_window", window) + r'''
static int dbg_swap(const struct Patch *t, int n, int own) {    /* all to the game's own bytes or all to widescreen */
    int i; DWORD o;
    for (i = 0; i < n; i++)
        if (memcmp((void *)(size_t)t[i].va, own ? t[i].wide : t[i].own, t[i].n)) return 0;   /* not the expected state */
    for (i = 0; i < n; i++) {
        void *f = (void *)(size_t)t[i].va;
        if (!VirtualProtect(f, t[i].n, PAGE_EXECUTE_READWRITE, &o)) return 0;
        memcpy(f, own ? t[i].own : t[i].wide, t[i].n);
        VirtualProtect(f, t[i].n, o, &o); FlushInstructionCache(GetCurrentProcess(), f, t[i].n);
    }
    return 1;
}
/* which parts are the game's own (shared with the debug fps60.c): the exe's screen-bounds checks and depth clamp
   (F2), its block window (F3), and this pass (g_dbg_43: the whole picture squeezed into the centre, as on 4:3) */
int g_own2, g_own3, g_dbg_43;
void dbg_set_wide(int own2, int own3, int own43) {
    if (own2 != g_own2 && dbg_swap(g_cull, sizeof g_cull / sizeof *g_cull, own2)) g_own2 = own2;
    if (own3 != g_own3 && dbg_swap(g_window, sizeof g_window / sizeof *g_window, own3)) g_own3 = own3;
    g_dbg_43 = own43;
}
''')

CRASH = r'''
static volatile long g_frames, g_exc, g_busy;
static HANDLE g_log = INVALID_HANDLE_VALUE;
static void log_raw(const char *s) {
    DWORD w;
    if (g_log != INVALID_HANDLE_VALUE) { WriteFile(g_log, s, lstrlenA(s), &w, 0); FlushFileBuffers(g_log); }
}
void crash_log(const char *s) {                              /* (the debug fps60.c logs through it too) */
    static char h[64]; SYSTEMTIME t;
    GetLocalTime(&t);
    wsprintfA(h, "%02d:%02d:%02d frame %ld: ", t.wHour, t.wMinute, t.wSecond, g_frames);
    log_raw(h); log_raw(s); log_raw("\r\n");
}
static LONG CALLBACK crash_veh(EXCEPTION_POINTERS *e) {
    static char b[600];
    DWORD c = e->ExceptionRecord->ExceptionCode;
    CONTEXT *x = e->ContextRecord;
    DWORD *sp = (DWORD *)(size_t)x->Esp;
    char *q; int i;
    if (c < 0x80000000) return EXCEPTION_CONTINUE_SEARCH;            /* warnings and errors, not notices */
    if (InterlockedExchange(&g_busy, 1)) return EXCEPTION_CONTINUE_SEARCH;
    if (InterlockedIncrement(&g_exc) <= 20) {
        wsprintfA(b, "exception %08lX at %08lX info %08lX %08lX", c, (DWORD)(size_t)e->ExceptionRecord->ExceptionAddress,
                  (DWORD)e->ExceptionRecord->ExceptionInformation[0], (DWORD)e->ExceptionRecord->ExceptionInformation[1]);
        crash_log(b);
        wsprintfA(b, "  eax %08lX ebx %08lX ecx %08lX edx %08lX esi %08lX edi %08lX ebp %08lX esp %08lX",
                  x->Eax, x->Ebx, x->Ecx, x->Edx, x->Esi, x->Edi, x->Ebp, x->Esp);
        crash_log(b);
        q = b; q += wsprintfA(q, "  stack");
        if (!IsBadReadPtr(sp, 48 * 4)) for (i = 0; i < 48; i++) q += wsprintfA(q, " %08lX", sp[i]);
        crash_log(b);
    }
    g_busy = 0;
    return EXCEPTION_CONTINUE_SEARCH;
}
static void crash_exit(void) { crash_log("process exit (DLL unloading)"); }
'''
INIT = r'''    { static int init;
      if (!init) {
          init = 1;
          g_log = CreateFileA("ws_crash.txt", FILE_APPEND_DATA, FILE_SHARE_READ, 0, OPEN_ALWAYS, 0, 0);
          AddVectoredExceptionHandler(1, crash_veh); atexit(crash_exit);
          crash_log("started");
      }
      InterlockedIncrement(&g_frames);
      /* testing aid: F7 toggles random encounters (off at start). The step countdown check (0x637A20: counts
         [0xBB65A0] down per step and flags a battle at 0) returns "no encounter"; scripted battles still happen. */
      { static int noenc = 1, k7; int k = GetAsyncKeyState(VK_F7) & 0x8000; u8 *f = (u8 *)(size_t)0x637A20; DWORD o;
        if (k && !k7) noenc ^= 1;
        k7 = k;
        if ((noenc ? f[0] == 0xA1 && f[1] == 0xE4 && f[2] == 0x57 : f[0] == 0x31 && f[1] == 0xC0 && f[2] == 0xC3) &&
            VirtualProtect(f, 3, PAGE_EXECUTE_READWRITE, &o)) {
            if (noenc) { f[0] = 0x31; f[1] = 0xC0; f[2] = 0xC3; } else { f[0] = 0xA1; f[1] = 0xE4; f[2] = 0x57; }
            VirtualProtect(f, 3, o, &o); FlushInstructionCache(GetCurrentProcess(), f, 3);
            crash_log(noenc ? "random encounters off (F7)" : "random encounters on (F7)");
        } }
      /* testing aids: F2 switches the widescreen exe's screen-bounds checks and depth clamp, F3 its map block window
         (radii and block rows), between widescreen and the game's own, to tell what each brings into view */
      /* F11 switches all of it (and this pass) at once: widescreen, or the game's own 4:3 picture */
      { static int k2, k3, k11; int k;
        k = GetAsyncKeyState(VK_F2) & 0x8000;
        if (k && !k2) { dbg_set_wide(!g_own2, g_own3, g_dbg_43);
            crash_log(g_own2 ? "screen-bounds checks and depth clamp: the game's own (F2)" : "screen-bounds checks and depth clamp: widescreen (F2)"); }
        k2 = k;
        k = GetAsyncKeyState(VK_F3) & 0x8000;
        if (k && !k3) { dbg_set_wide(g_own2, !g_own3, g_dbg_43);
            crash_log(g_own3 ? "map block window: the game's own (F3)" : "map block window: doubled (F3)"); }
        k3 = k;
        k = GetAsyncKeyState(VK_F11) & 0x8000;
        if (k && !k11) { int o = !g_dbg_43; dbg_set_wide(o, o, o); crash_log(o ? "all 4:3, the game's own (F11)" : "all widescreen (F11)"); }
        k11 = k; }
      /* testing aid: F6 opens the save screen on a map, as an inn's save point does (its script command at 0x522A08:
         request 7 = the save screen, program 8; 0x520290(4) starts the fade out, unless one is running), to save
         right before a cutscene. Only on a map (program 2) with no request or fade pending. */
      { static int k6; int k = GetAsyncKeyState(VK_F6) & 0x8000;
        if (k && !k6 && MEM(unsigned short, 0xBAB408) == 2 && !MEM(u8, 0xBAB428) && !MEM(unsigned short, 0xBAB480)) {
            MEM(u8, 0xB50A2C) = 0; MEM(u8, 0xBAB428) = 7;
            if (((char (__cdecl *)(int))0x520290)(4)) { MEM(u8, 0xBAB428) = 0; crash_log("save screen busy (F6)"); }
            else crash_log("save screen requested (F6)");
        }
        k6 = k; }
      { static int mv = 6000, mc = 1500; static char m[256]; int cb = (int)(MEM(u32, CMD_PTR) - CMD_BASE) / 8;
        if (nv > mv || cb > mc) {
            if (nv > mv) mv = nv;
            if (cb > mc) mc = cb;
            wsprintfA(m, "record: %d vertices, %d command slots (buffers at %08lX / %08lX: %s), %d map polygons (pools at %08lX / %08lX)",
                      nv, cb, VTX_BASE, CMD_BASE,
                      VTX_BASE == 0xA7C1D0 ? (nv > 8192 || cb > 2048 ? "the game's, OVERFLOW" : "the game's") : "bigger",
                      MEM(unsigned short, 0xB52FE4), MEM(u32, POOL_VARS), MEM(u32, POOL_VARS + 4));
            crash_log(m);
        } } }
'''

rep("typedef unsigned char u8; typedef unsigned int u32;\n", "typedef unsigned char u8; typedef unsigned int u32;\n" + SWAP)
rep("#include <stdlib.h>\n", "#include <stdlib.h>\n#include <stdio.h>\nstatic FILE *g_dbg; static int g_dk, g_bad;\n"
    "int g_dbg_one, g_dbg_shot = -1, g_dbg_w, g_dbg_h;   /* shared with the debug fps60.c: one-frame dump, screenshot */\n" + CRASH)
rep("    memcpy(g_bak, v, (size_t)nv * sizeof(Vtx));\n",
    "    memcpy(g_bak, v, (size_t)nv * sizeof(Vtx));\n" + INIT +
    "    g_dbg_w = rect[2] - rect[0]; g_dbg_h = rect[3] - rect[1];   /* the screenshots' size */\n"
    "    { int k = GetAsyncKeyState(VK_F8) & 0x8000, press = (k && !g_dk) || g_dbg_one; static int set, on, snap; char p[64];\n"
    "      if (k && !g_dk) on ^= 1;\n"
    "      if ((on || g_dbg_one || GetFileAttributesA(\"ws_dump.on\") != INVALID_FILE_ATTRIBUTES) && set < 3000) { sprintf(p, \"ws_dump%04d.txt\", set++); g_dbg = fopen(p, \"w\");\n"
    "        if (g_dbg) fprintf(g_dbg, \"rect %d %d %d %d nv %d bad %d\\n\", rect[0], rect[1], rect[2], rect[3], nv, g_bad);\n"
    "        if (g_dbg) fprintf(g_dbg, \"fishing %d\\nstate %d %d %d\\n\", fishing(),\n"
    "          MEM(u8, PROG_ID), MEM(u8, 0xB5300D), MEM(u8, 0xB56667)); }\n"
    "      if (press) { FILE *m; char b[160]; sprintf(p, \"ws_mem%02d.bin\", snap);\n"
    "        if ((m = fopen(p, \"wb\"))) { fwrite((void *)0x6A8000, 1, 0x8BE000 - 0x6A8000, m);\n"
    "          fwrite((void *)0x8D4000, 1, 0xC78000 - 0x8D4000, m); fclose(m); }\n"
    "        g_dbg_shot = snap; g_dbg_w = rect[2] - rect[0]; g_dbg_h = rect[3] - rect[1];   /* saved at the next present */\n"
    "        wsprintfA(b, \"F8: %s at ws_dump%04d.txt, ws_mem%02d.bin, ws_shot%02d.bmp\", g_dbg_one ? \"one frame\" : on ? \"dumps on\" : \"dumps off\",\n"
    "                  set - (on || g_dbg_one), snap, snap);\n"
    "        crash_log(b); snap++; }\n"
    "      g_dk = k; g_dbg_one = 0; }\n"
    "    if (g_dbg_43) {                                    /* the game's own 4:3: everything squeezed, nothing else */\n"
    "        u32 ce = MEM(u32, CMD_PTR), ve = MEM(u32, VTX_PTR); int bars = VTX_BASE != GAME_VTX && nv + 8 < BIG_VTX &&\n"
    "            (ce - CMD_BASE) / 8 + 2 < BIG_CMD;          /* (black side bars over what reaches past the edges, last) */\n"
    "        if (g_dbg) { fclose(g_dbg); g_dbg = 0; }\n"
    "        for (i = 0; i < nv; i++) v[i].x = cx + (v[i].x - cx) * k;\n"
    "        if (bars) for (j = 0; j < 2; j++) {           /* untextured opaque quads (0x480, a strip of 4) */\n"
    "            float x0 = j ? cx + (r - cx) * k : l, x1 = j ? r : cx - (cx - l) * k;\n"
    "            Vtx *q = v + nv + 4 * j;\n"
    "            MEM(u32, ce + 8 * j) = 0x480; MEM(u32, ce + 8 * j + 4) = 0;\n"
    "            for (i = 0; i < 4; i++) { memset(&q[i], 0, sizeof *q); q[i].x = i & 1 ? x1 : x0; q[i].y = i & 2 ? bt : t;\n"
    "                                       q[i].rhw = 1; q[i].col = 0xFF000000; }\n"
    "        }\n"
    "        if (bars) { MEM(u32, CMD_PTR) = ce + 16; MEM(u32, VTX_PTR) = ve + 8 * sizeof(Vtx); }\n"
    "        exec(surf, rect, flag);\n"
    "        if (bars) { MEM(u32, CMD_PTR) = ce; MEM(u32, VTX_PTR) = ve; }\n"
    "        memcpy(v, g_bak, (size_t)nv * sizeof(Vtx)); return;\n"
    "    }\n")
rep("            u32 *vp = (u32 *)(size_t)(c + 8);\n",
    "            u32 *vp = (u32 *)(size_t)(c + 8);\n"
    "            if (g_dbg) fprintf(g_dbg, \"VP %u %u %u %u\\n\", vp[0], vp[1], vp[2], vp[3]);\n")
rep("        if (vi + n * draws > nv) break;",
    "        if (vi + n * draws > nv) { g_bad++; if (g_dbg) fprintf(g_dbg, \"BAD vi %d n %d\\n\", vi, n); break; }")
rep("            p->keep = p->flat && ((p->x0",
    "            if (g_dbg) {\n"
    "                fprintf(g_dbg, \"P %08X tex %08X n %d rhw %g z %g x %.1f..%.1f y %.1f..%.1f col %08X uv %.3f,%.3f\\n\",\n"
    "                        p->w, p->tex, n, v[vi].rhw, v[vi].z, p->x0, p->x1, p->y0, p->y1, v[vi].col, v[vi].u, v[vi].v);\n"
    "                fprintf(g_dbg, \"V\"); for (i = vi; i < vi + n; i++) fprintf(g_dbg, \" %.1f %.1f %08X\", v[i].x, v[i].y, v[i].col); fprintf(g_dbg, \"\\n\"); }\n"
    "            p->keep = p->flat && ((p->x0")
rep("    exec(surf, rect, flag);\n    memcpy(v, g_bak",
    "    if (g_dbg) { fclose(g_dbg); g_dbg = 0; }\n    exec(surf, rect, flag);\n    memcpy(v, g_bak")
open(dst, "w").write(s)

# fps60.c (the 60 fps hooks, which pace and present every frame): pause, single step, fast forward, screenshots.
if len(sys.argv) > 4:
    s = open(sys.argv[3]).read()
    FPS = r'''
/* debug build: F5 pauses and resumes (the game thread waits in the screen pass, handling window messages); while
   paused F4 runs one frame and F8 runs one frame and dumps it. F9 held fast-forwards: the game's limiter table goes
   to 0, nothing is paced, and one frame in four is drawn and presented. A dump press's screenshot (the back buffer,
   ws_shotNN.bmp) is taken right before the next present, when the frame is complete. */
#pragma comment(lib, "gdi32.lib")
extern int g_dbg_one, g_dbg_shot, g_dbg_w, g_dbg_h;           /* widescreen.c (debug) */
extern int g_own2, g_own3, g_dbg_43;
void dbg_set_wide(int own2, int own3, int own43);
void crash_log(const char *s);
static int g_dpause, g_dk5, g_dk4, g_dk8, g_dff, g_dff_prev, g_dffc, g_dskip, g_dk12, g_dsteps, g_ab, g_ab_n, g_ab_prev[3];
static u8 *g_ab_a; static int g_ab_w, g_ab_h;
static u32 g_dtab[4];
static int dbg_key(int vk) {                                  /* only while the game has the focus */
    DWORD pid = 0;
    GetWindowThreadProcessId(GetForegroundWindow(), &pid);
    return pid == GetCurrentProcessId() && (GetAsyncKeyState(vk) & 0x8000);
}
static int dbg_gate(void) {                                   /* 1: skip this frame (fast forward) */
    int k = dbg_key(VK_F5), i;
    if (k && !g_dk5) g_dpause ^= 1;
    g_dk5 = k;
    k = dbg_key(VK_F12);                                      /* A/B: this frame widescreen, the next one 4:3 */
    if (k && !g_dk12 && !g_ab) { g_ab = 1; if (g_dpause) g_dsteps = 3; }   /* paused: run them, and one more */
    g_dk12 = k;
    while (g_dpause) {
        MSG m;
        if (g_dsteps > 0) { g_dsteps--; break; }
        while (PeekMessageA(&m, 0, 0, 0, PM_REMOVE)) {
            if (m.message == WM_QUIT) { PostQuitMessage((int)m.wParam); g_dpause = 0; return 0; }
            TranslateMessage(&m); DispatchMessageA(&m);
        }
        k = dbg_key(VK_F5); if (k && !g_dk5) g_dpause = 0; g_dk5 = k;
        k = dbg_key(VK_F12); if (k && !g_dk12 && !g_ab) { g_dk12 = k; g_ab = 1; g_dsteps = 2; break; } g_dk12 = k;
        k = dbg_key(VK_F4); if (k && !g_dk4) { g_dk4 = k; break; } g_dk4 = k;
        k = dbg_key(VK_F8);
        if (!k && g_dk8) { g_dk8 = 0; g_dbg_one = 1; break; }  /* on release, so the dump code sees no press */
        g_dk8 = k;
        Sleep(10);
    }
    g_dff = dbg_key(VK_F9);
    if (g_dff && !g_dff_prev) for (i = 0; i < 4; i++) { g_dtab[i] = MEM(u32, MS_TABLE + 4 * i); MEM(u32, MS_TABLE + 4 * i) = 0; }
    if (!g_dff && g_dff_prev) for (i = 0; i < 4; i++) MEM(u32, MS_TABLE + 4 * i) = g_dtab[i];
    g_dff_prev = g_dff;
    return g_dff && ++g_dffc % 4 != 0;
}
static u8 *dbg_grab(int w, int h) {                           /* the back buffer, 24-bit bottom-up rows (malloc) */
    void *ds = *(void **)(size_t)0xABC1E0, *bits = 0;
    HDC sdc, mdc; HBITMAP bm; BITMAPINFO bi; u8 *out = 0;
    int stride = (w * 3 + 3) & ~3;
    if (!ds || w <= 0 || h <= 0 || ((long (__stdcall *)(void *, HDC *))(*(void ***)ds)[17])(ds, &sdc) != 0) return 0;   /* GetDC */
    memset(&bi, 0, sizeof bi);
    bi.bmiHeader.biSize = sizeof bi.bmiHeader; bi.bmiHeader.biWidth = w; bi.bmiHeader.biHeight = h;
    bi.bmiHeader.biPlanes = 1; bi.bmiHeader.biBitCount = 24;
    mdc = CreateCompatibleDC(sdc);
    if ((bm = CreateDIBSection(mdc, &bi, DIB_RGB_COLORS, &bits, 0, 0)) != 0) {
        HGDIOBJ o = SelectObject(mdc, bm);
        BitBlt(mdc, 0, 0, w, h, sdc, 0, 0, SRCCOPY); SelectObject(mdc, o);
    }
    ((long (__stdcall *)(void *, HDC))(*(void ***)ds)[26])(ds, sdc);                                                  /* ReleaseDC */
    if (bm) { GdiFlush(); if ((out = malloc((size_t)stride * h)) != 0) memcpy(out, bits, (size_t)stride * h); DeleteObject(bm); }
    DeleteDC(mdc);
    return out;
}
static void dbg_bmp(const char *path, const u8 *bits, int w, int h) {
    BITMAPFILEHEADER fh; BITMAPINFOHEADER bh; FILE *f; int stride = (w * 3 + 3) & ~3;
    if (!bits || (f = fopen(path, "wb")) == 0) return;
    memset(&bh, 0, sizeof bh); bh.biSize = sizeof bh; bh.biWidth = w; bh.biHeight = h; bh.biPlanes = 1; bh.biBitCount = 24;
    fh.bfType = 0x4D42; fh.bfReserved1 = fh.bfReserved2 = 0; fh.bfOffBits = sizeof fh + sizeof bh; fh.bfSize = fh.bfOffBits + stride * h;
    fwrite(&fh, sizeof fh, 1, f); fwrite(&bh, sizeof bh, 1, f); fwrite(bits, stride, h, f); fclose(f);
}
static void dbg_shot(void) {                                  /* the back buffer to ws_shotNN.bmp */
    char p[32]; u8 *b = dbg_grab(g_dbg_w, g_dbg_h);
    sprintf(p, "ws_shot%02d.bmp", g_dbg_shot); g_dbg_shot = -1;
    dbg_bmp(p, b, g_dbg_w, g_dbg_h); free(b);
}
/* F12, at the presents of two frames in a row: the first (widescreen) is kept, then everything goes to the game's
   own 4:3 for the next one, which is kept too, then back as it was. ws_abNN.bmp: the widescreen frame, and beside it
   the 4:3 frame's middle (the 4:3 picture itself, its sides cut off). */
static void dbg_ab(void) {
    RECT rc; int w, h;
    HWND wnd = GetForegroundWindow();
    w = g_dbg_w; h = g_dbg_h;
    if (w <= 0 || h <= 0) { if (wnd && GetClientRect(wnd, &rc)) { w = rc.right; h = rc.bottom; } }
    if (g_ab == 1) {
        free(g_ab_a); g_ab_a = dbg_grab(w, h); g_ab_w = w; g_ab_h = h;
        g_ab_prev[0] = g_own2; g_ab_prev[1] = g_own3; g_ab_prev[2] = g_dbg_43;
        dbg_set_wide(1, 1, 1); g_ab = 2;
    } else {
        u8 *b = dbg_grab(g_ab_w, g_ab_h), *o;
        int w43 = g_ab_h * 4 / 3, x43 = (g_ab_w - w43) / 2, sa = (g_ab_w * 3 + 3) & ~3, W = g_ab_w + w43, so = (W * 3 + 3) & ~3, y;
        char p[32], m[96];
        dbg_set_wide(g_ab_prev[0], g_ab_prev[1], g_ab_prev[2]); g_ab = 0;
        if (g_ab_a && b && x43 >= 0 && (o = calloc((size_t)so, g_ab_h)) != 0) {
            for (y = 0; y < g_ab_h; y++) {
                memcpy(o + (size_t)y * so, g_ab_a + (size_t)y * sa, (size_t)g_ab_w * 3);
                memcpy(o + (size_t)y * so + (size_t)g_ab_w * 3, b + (size_t)y * sa + (size_t)x43 * 3, (size_t)w43 * 3);
            }
            sprintf(p, "ws_ab%02d.bmp", g_ab_n); dbg_bmp(p, o, W, g_ab_h); free(o);
            wsprintfA(m, "A/B (F12): %s, widescreen left, the game's own 4:3 right", p); crash_log(m); g_ab_n++;
        }
        free(b); free(g_ab_a); g_ab_a = 0;
    }
}

/* PutDrawEnv's present (0x410A47)'''
    a = "\n/* PutDrawEnv's present (0x410A47)"
    assert s.count(a) == 1, a
    s = s.replace(a, FPS)
    a = "    u32 n; double t;\n    init();\n"
    assert s.count(a) == 1, a
    s = s.replace(a, a + "    if (g_dbg_shot >= 0 && !g_dskip) dbg_shot();\n"
                         "    if (g_ab && !g_dskip) dbg_ab();\n"
                         "    if (g_dff || g_dskip) { g_sched = 0; return g_dskip ? 0 : ((int(__cdecl *)(int))PRESENT)(a); }\n")
    a = "    if (!(MEM(u8, FEATURES) & 1)) { exec(surf, rect, flag); return; }\n"
    assert s.count(a) == 1, a
    s = s.replace(a, "    if ((g_dskip = dbg_gate()) != 0) return;\n" + a)
    a = "if (N->valid && g_on && grow("
    assert s.count(a) == 1, a
    s = s.replace(a, "if (N->valid && g_on && !g_dff && grow(")
    open(sys.argv[4], "w").write(s)
print("ok")
