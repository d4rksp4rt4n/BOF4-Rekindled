# dbg_patch.py SRC DST: writes a copy of widescreen.c with an F8 primitive dump (ws_dumpNNNN.txt next to the
# exe; F8 toggles it, or a file named ws_dump.on keeps it on). Each F8 press also saves the game's data areas
# (0x6A8000-0x8BE000 and 0x8D4000-0xC78000) to ws_memNN.bin, to find state variables by comparing screens.
# ws_crash.txt logs the start, serious exceptions anywhere in the process (code, address, registers, stack) and the
# exit, to tell a crash from a clean exit when the game simply closes; it writes through a handle opened at start,
# without the C runtime or the heap, so it works inside a crash. Build DST with the other reverb\*.c into a debug
# bof4_reverb.dll; the dumps feed ws_replay.py. Testing aids: F7 switches random encounters (off at start), F6 opens
# the save screen on a map (save anywhere).
import sys
src, dst = sys.argv[1], sys.argv[2]
s = open(src).read()
def rep(a, b):
    global s
    assert s.count(a) == 1, a
    s = s.replace(a, b)

CRASH = r'''
static volatile long g_frames, g_exc, g_busy;
static HANDLE g_log = INVALID_HANDLE_VALUE;
static void log_raw(const char *s) {
    DWORD w;
    if (g_log != INVALID_HANDLE_VALUE) { WriteFile(g_log, s, lstrlenA(s), &w, 0); FlushFileBuffers(g_log); }
}
static void crash_log(const char *s) {
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

rep("#include <stdlib.h>\n", "#include <stdlib.h>\n#include <stdio.h>\nstatic FILE *g_dbg; static int g_dk, g_bad;\n" + CRASH)
rep("    memcpy(g_bak, v, (size_t)nv * sizeof(Vtx));\n",
    "    memcpy(g_bak, v, (size_t)nv * sizeof(Vtx));\n" + INIT +
    "    { int k = GetAsyncKeyState(VK_F8) & 0x8000; static int set; char p[64];\n"
    "      static int on; if (k && !g_dk) on ^= 1; if ((on || GetFileAttributesA(\"ws_dump.on\") != INVALID_FILE_ATTRIBUTES) && set < 3000) { sprintf(p, \"ws_dump%04d.txt\", set++); g_dbg = fopen(p, \"w\");\n"
    "        if (g_dbg) fprintf(g_dbg, \"rect %d %d %d %d nv %d bad %d\\n\", rect[0], rect[1], rect[2], rect[3], nv, g_bad);\n"
    "        if (g_dbg) fprintf(g_dbg, \"fishing %d\\nstate %d %d %d\\n\", fishing(),\n"
    "          MEM(u8, PROG_ID), MEM(u8, 0xB5300D), MEM(u8, 0xB56667)); }\n"
    "      if (k && !g_dk) { static int snap; FILE *m; sprintf(p, \"ws_mem%02d.bin\", snap++);\n"
    "        if ((m = fopen(p, \"wb\"))) { fwrite((void *)0x6A8000, 1, 0x8BE000 - 0x6A8000, m);\n"
    "          fwrite((void *)0x8D4000, 1, 0xC78000 - 0x8D4000, m); fclose(m); } }\n"
    "      g_dk = k; }\n")
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
print("ok")
