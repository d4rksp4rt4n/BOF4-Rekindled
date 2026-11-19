/* Sprite depth scaling (option "sprites").
 *
 * Characters are fixed-size sprites: on the PS1 a villager far up the street is as big as one next to the camera,
 * while the 3D around them shrinks with distance. Each character is drawn as body strips (packet 0x9C) and a
 * shadow (0x96) around one float anchor at +8/+0xC, the screen point of its feet (actor position projected by
 * 0x6641E0, called only from 0x676C0B). Each corner is anchor + offset * scale, scale at +0x10/+0x14 (always 1.0).
 *
 * bof4_spr_project records anchor -> view depth (SZ) for every projected actor. At draw time a packet whose
 * anchor matches one gets its scale multiplied by ref / depth for that draw. ref = the player's depth: the
 * camera follows the player, so its anchor sits at the projection centre (OFX, OFY); the player keeps its size
 * and everything else is sized as if it stood next to it. The game's own (unused here) sprite scale routine at
 * 0x664250 is 1.0 at depth 5120, the usual camera distance, which is the start value.
 * By default characters only shrink: the fixed size makes far ones look like they grow next to the shrinking
 * floor, while full perspective also blows up the ones near the camera (1.5x at the bottom of the screen). */
#include <windows.h>
#include <math.h>
#include <string.h>

typedef unsigned char u8; typedef unsigned int u32;
#define MEM(t, a) (*(volatile t *)(a))

#define PROJECT 0x6641E0       /* (int world[3], short sxy[2], float fxy[2]) */
#define DRAW96  0x408B30       /* (packet) */
#define DRAW9C  0x409E10
#define GTE_SZ3 0xAE9C54       /* newest SZ: view depth of the point just projected */
#define GTE_OFX 0xAE9C40
#define GTE_OFY 0xAE9C3C
#define CENTRE  2.0f           /* PS1 pixels: an anchor this close to the projection centre is the player */

static struct { u32 x, y; int z; } g_anchor[256];     /* newest last; float bits of the anchor */
static u32 g_head;
static float g_ref = 5120.0f;
/* BOF4_reverb.ini [sprites]: strength = % of the full perspective size change (100); grow = 1: characters
   closer to the camera than the player get bigger too (0: they keep their original size).
   Insert cycles shrink only -> full -> off while playing, starting from the ini's mode; the title shows it. */
enum { SHRINK, FULL, OFF };
static const char *g_mode_name[] = {"shrink only", "full", "off"};
static float g_strength = -1; static int g_mode, g_key;
static char g_title[200];

static void init(void) {
    char ini[MAX_PATH], *p;
    g_strength = 1; g_mode = SHRINK;
    GetModuleFileNameA(NULL, ini, MAX_PATH);
    if ((p = strrchr(ini, '\\')) == 0) return;
    strcpy(p + 1, "BOF4_reverb.ini");
    g_strength = GetPrivateProfileIntA("sprites", "strength", 100, ini) / 100.f;
    g_mode = GetPrivateProfileIntA("sprites", "grow", 0, ini) ? FULL : SHRINK;
}

static void hotkey(void) {
    char t[300]; HWND w;
    int key = GetAsyncKeyState(VK_INSERT) & 0x8000;
    if (key && !g_key && (w = GetForegroundWindow()) != 0) {
        g_mode = (g_mode + 1) % 3;
        if (!g_title[0]) GetWindowTextA(w, g_title, sizeof g_title);
        wsprintfA(t, "%s - sprite depth scaling: %s", g_title, g_mode_name[g_mode]);
        SetWindowTextA(w, t);
    }
    g_key = key;
}

__declspec(dllexport) void __cdecl bof4_spr_project(int *world, short *sxy, float *fxy) {
    int z;
    if (g_strength < 0) init();
    hotkey();
    ((void (__cdecl *)(int *, short *, float *))PROJECT)(world, sxy, fxy);
    z = MEM(int, GTE_SZ3);
    g_head++;
    g_anchor[g_head & 255].x = *(u32 *)&fxy[0]; g_anchor[g_head & 255].y = *(u32 *)&fxy[1]; g_anchor[g_head & 255].z = z;
    if (z > 0 && fabsf(fxy[0] - MEM(int, GTE_OFX)) < CENTRE && fabsf(fxy[1] - MEM(int, GTE_OFY)) < CENTRE)
        g_ref += (z - g_ref) / 8;                       /* smoothed, like HMBTN-ReFarmed's sprite depth */
}

static void draw(u32 fn, u8 *p) {
    float *s = (float *)(p + 0x10), s0 = s[0], s1 = s[1], k = 0;
    u32 x = *(u32 *)(p + 8), y = *(u32 *)(p + 0xC), i;
    for (i = 0; i < 256; i++) {                         /* newest first */
        u32 j = (g_head - i) & 255;
        if (g_anchor[j].x == x && g_anchor[j].y == y) { if (g_anchor[j].z > 0) k = g_ref / g_anchor[j].z; break; }
    }
    if (k && g_mode != OFF) {
        k = 1 + g_strength * (k - 1);
        if (g_mode == SHRINK && k > 1) k = 1;
        s[0] = s0 * k; s[1] = s1 * k;
    }
    ((void (__cdecl *)(u8 *))fn)(p);
    s[0] = s0; s[1] = s1;                               /* the packet may be drawn again */
}

__declspec(dllexport) void __cdecl bof4_spr_draw96(u8 *p) { draw(DRAW96, p); }
__declspec(dllexport) void __cdecl bof4_spr_draw9c(u8 *p) { draw(DRAW9C, p); }
