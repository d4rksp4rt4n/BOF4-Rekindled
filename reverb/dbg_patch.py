# dbg_patch.py SRC DST: writes a copy of widescreen.c with an F8 primitive dump (ws_dumpNNNN.txt next to the
# exe; F8 toggles it, or a file named ws_dump.on keeps it on). Each F8 press also saves the game's data areas
# (0x6A8000-0x8BE000 and 0x8D4000-0xC78000) to ws_memNN.bin, to find state variables by comparing screens. Build DST with the other reverb\*.c into a debug
# bof4_reverb.dll; the dumps feed ws_replay.py.
import shutil, sys
src, dst = sys.argv[1], sys.argv[2]
s = open(src).read()
def rep(a, b):
    global s
    assert s.count(a) == 1, a
    s = s.replace(a, b)
rep("#include <stdlib.h>\n", "#include <stdlib.h>\n#include <stdio.h>\nstatic FILE *g_dbg; static int g_dk, g_bad;\n")
rep("    memcpy(g_bak, v, (size_t)nv * sizeof(Vtx));\n",
    "    memcpy(g_bak, v, (size_t)nv * sizeof(Vtx));\n"
    "    { int k = GetAsyncKeyState(VK_F8) & 0x8000; static int set; char p[64];\n"
    "      static int on; if (k && !g_dk) on ^= 1; if ((on || GetFileAttributesA(\"ws_dump.on\") != INVALID_FILE_ATTRIBUTES) && set < 3000) { sprintf(p, \"ws_dump%04d.txt\", set++); g_dbg = fopen(p, \"w\");\n"
    "        if (g_dbg) fprintf(g_dbg, \"rect %d %d %d %d nv %d bad %d\\n\", rect[0], rect[1], rect[2], rect[3], nv, g_bad);\n"
    "        if (g_dbg) fprintf(g_dbg, \"fishing %d\\nstate %d %d %d\\n\", fishing(),\n"
    "          MEM(u8, PROG_ID), MEM(u8, 0xB5300D), MEM(u8, CAMP_MENU)); }\n"
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
