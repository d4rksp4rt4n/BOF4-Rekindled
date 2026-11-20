/* Widescreen (option "widescreen", experimental).
 *
 * The game draws the PS1's 320x240 picture stretched to the render size from bof4.cfg (SetScale: x * W / 320,
 * y * H / 240), so at 16:9 everything is a third too wide. Every frame is one batch of screen-space D3DTLVERTEX
 * (0xA7C1D0) and a command list (0xA758B8); right before the screen pass replays it, every x is squeezed toward
 * the centre by (4/3) / (W/H). The 3D scene then has correct proportions and fills the sides (the exe's culls are
 * widened so the polygons there exist); 2D (menus, text, HUD) stays in the centred 4:3 area.
 * Exceptions, so the picture has no 4:3 frame:
 *  - 2D primitives covering the whole width (fades, flashes, letterbox bars) are not squeezed, nor are runs of
 *    textured 2D tiles that together span exactly the 4:3 width (backdrops such as the Sand Flier
 *    race's, summon skies, cloud layers drawn for the 4:3 frame): they are stretched with the screen;
 *  - nor is a full-screen picture on the sprite layer (rhw 0.1: the Camp menu's background);
 *  - nor are full-height 2D primitives flagged 0x2000: the previous screen redrawn from a capture texture (the battle
 *    swirl, two half-screen quads), which already holds the full widescreen picture;
 *  - untextured 2D keeps the corners it has at or beyond the left/right edge: masks reach the screen edges (the world
 *    map's vignette, the battle target scope, wipes, a spell's dark fade). Semi-transparent untextured 2D is
 *    squeezed whole unless it is that wide fade (a quarter of the screen, a corner on the edge): the Shrine's laser
 *    beams and lamp glows, drawn in 2D, would bend or flicker there (their corners land on the edge now and then);
 *  - textured plain 2D (rhw 1, z 0.01) is cut to the 4:3 area, as a 4:3 screen would: menus sliding off past its
 *    edge would otherwise show up in the side bars; except runs of tiles reaching past both edges (sky panoramas such
 *    as the plains', spell effects such as Gigaflare, Blizzard's backdrop) and single-pass semi-transparent pictures
 *    (effects such as Blizzard's snow), which only get squeezed;
 *  - a big backdrop in pieces (big opaque tiles in one row covering the 4:3 width, such as the Breath attacks' skies
 *    and Kaiser Breath's Earth) is fitted: squeezed only as far as it still covers the screen, and slid to close a
 *    gap, so a panning or zooming picture never jumps between squeezed and stretched;
 *  - HUD panels (with their text and icons) move to the screen edges: all of them in the fishing minigame (but its
 *    depth gauge, whose marker is drawn apart from it, at the bottom right), the
 *    bottom ones on maps (the world map's Menu panel and road box), top-left ones (the compass in towns and
 *    fields), the Enemy(s) box in battle;
 *  - viewports (the command list can switch to a sub-rectangle) are squeezed with their contents, unless they
 *    span the whole width.
 * At 4:3 (or narrower) nothing changes. The batch is restored after the replay. */
#include <windows.h>
#include <string.h>
#include <stdlib.h>
#include <math.h>

typedef unsigned char u8; typedef unsigned int u32;
#define MEM(t, a) (*(t *)(size_t)(a))
/* the frame's vertex buffer and command list: the exe (widescreen part) reads their addresses from its variables
   [vertex base][command base][pending vertex][pending command], switching to the pending ones at a frame start */
#define BUF_VARS 0x6A7C60
#define VTX_BASE MEM(u32, BUF_VARS)
#define VTX_PTR  0x96DA70
#define CMD_BASE MEM(u32, BUF_VARS + 4)
#define CMD_PTR  0x96DA7C
#define BIG_VTX  65536         /* the game's own: 8192 vertices and 2048 commands, too few once the sides are drawn */
#define BIG_CMD  16384         /* (a busy town such as Synesta overflowed both into the game's variables) */
#define POOL_VARS (BUF_VARS + 16) /* [pool 0][pool 1]: the map's polygon packets, 2048 of 84 bytes each by frame parity */
#define BIG_POLY 8192          /* (Synesta overflowed them too, into the program number at 0xBAB408) */
#define GAME_VTX 0xA7C1D0u     /* the game's own vertex buffer */
#define EXEC     0x40A8A0      /* replays the batch: (surface, rect, flag) */
#define MAX_VP   64
#define UI_Z     0.01f         /* z of plain 2D (menus, text, HUD); 2D sorted into the 3D scene (map dots) has its own */

typedef struct { float x, y, z, rhw; u32 col, spec; float u, v; } Vtx;

static Vtx *g_bak; static int g_cap;
static struct { u32 *r, x, w; } g_vp[MAX_VP];

static void exec(void *surf, int *rect, int flag) { ((void (__cdecl *)(void *, int *, int))EXEC)(surf, rect, flag); }

/* cut a (squeezed) 2D primitive to [cl, cr]: gone if outside; an axis-aligned quad partly outside gets its x and
   texture coordinates clamped (others are left as they are) */
static void clip(Vtx *p, int n, float cl, float cr) {
    float x0 = 1e30f, x1 = -1e30f, du, dv;
    int i, a = -1, b = -1;
    for (i = 0; i < n; i++) { if (p[i].x < x0) x0 = p[i].x; if (p[i].x > x1) x1 = p[i].x; }
    if (x1 <= cl || x0 >= cr) { for (i = 0; i < n; i++) p[i].x = cl; return; }
    if (x0 >= cl && x1 <= cr) return;
    for (i = 0; i < n; i++) {
        if (fabsf(p[i].x - x0) > 0.01f && fabsf(p[i].x - x1) > 0.01f) return;     /* not axis-aligned */
        if (fabsf(p[i].x - x0) <= 0.01f) a = i;
    }
    for (i = 0; i < n; i++) if (fabsf(p[i].x - x1) <= 0.01f && fabsf(p[i].y - p[a].y) < 0.01f) b = i;
    if (b < 0) return;
    du = (p[b].u - p[a].u) / (x1 - x0); dv = (p[b].v - p[a].v) / (x1 - x0);
    for (i = 0; i < n; i++) {
        float x = p[i].x < cl ? cl : p[i].x > cr ? cr : p[i].x;
        p[i].u += (x - p[i].x) * du; p[i].v += (x - p[i].x) * dv; p[i].x = x;
    }
}

typedef struct { u32 w, tex; int v0, n; float x0, x1, y0, y1, fk, fs, push; u8 flat, keep, pair; } Prim;
static Prim *g_p; static int g_cap_p;

/* per frame: texture -> x range of its 2D primitives (open addressing; a full table just means "not found") */
#define TEX_SLOTS 2048
typedef struct { u32 tex; float x0, x1; int n, edge; } TexSpan;
static TexSpan g_tex[TEX_SLOTS];
static TexSpan *tex_span(u32 tex) {
    u32 h = (tex * 2654435761u) >> 21, i;                       /* 11 bits */
    for (i = 0; i < TEX_SLOTS; i++, h = (h + 1) & (TEX_SLOTS - 1)) {
        TexSpan *s = &g_tex[h];
        if (s->tex == tex + 1) return s;                         /* stored + 1: 0 marks an empty slot */
        if (!s->tex) { s->tex = tex + 1; s->x0 = 1e30f; s->x1 = -1e30f; return s; }
    }
    return NULL;
}

/* a tile of a sky picture: a quarter of the screen wide and high, on screen vertically (a ground mesh drawn with the
   same command word has huge pieces below the screen), and a plain rectangle (Mudflow's ground is a grid of skewed
   2D quads, some as big: fitting a few rows of it opened square holes between them) */
static int big_tile(const Prim *p, const Vtx *v, float l, float r, float t, float bt) {
    int i;
    if (!(p->x1 - p->x0 >= 0.25f * (r - l) && p->y1 - p->y0 >= 0.25f * (bt - t) && p->y0 < bt && p->y1 > t)) return 0;
    for (i = p->v0; i < p->v0 + p->n; i++)
        if ((fabsf(v[i].x - p->x0) > 0.5f && fabsf(v[i].x - p->x1) > 0.5f) ||
            (fabsf(v[i].y - p->y0) > 0.5f && fabsf(v[i].y - p->y1) > 0.5f)) return 0;
    return 1;
}

/* The fishing minigame's HUD (compass, location name, the Cast/Menu/Help panel) sits at the edges of the 4:3 frame;
   on a wide screen it moves to the screen edges. The PS1 game loads each mode's data at 0x6B0000; the fishing
   minigame's starts with this table (the same at every fishing spot, never on a map, in battle or in menus). */
#define FISH_DATA 0x6B0000
static const u8 FISH_SIG[16] = { 0x20, 0x03, 0x20, 0x03, 0x43, 0x03, 0x60, 0x03, 0x71, 0x03, 0x92, 0x03, 0xAC, 0x03, 0xC8, 0x03 };
static int fishing(void) { return !memcmp((const void *)(size_t)FISH_DATA, FISH_SIG, sizeof FISH_SIG); }

/* Which HUD panels move, by screen. The main program number is 2 on maps (towns, fields, the world map, fishing
   spots), 1 while a map is entered, 6 while the camera turns, 4 during a talk or event on a map, 3 in the Camp menu
   (whose first and last frames still show the map, before its full-screen background is drawn), 5 in battle, 7 in
   a shop's menu (its first and last frames still show the compass). */
#define PROG_ID    0xBAB408
enum { HUD_ALL = 1, HUD_BOTTOM = 2, HUD_TOPLEFT = 4, HUD_TOPRIGHT = 8 };
static int hud_mode(int menu_bg) {
    int prog = MEM(u8, PROG_ID);
    if (fishing()) return HUD_ALL;                               /* compass, location name, Cast/Menu/Help panel */
    if (prog == 5) return HUD_TOPRIGHT | HUD_TOPLEFT;            /* battle: the Enemy(s) box; the map's compass */
    if ((prog == 1 || prog == 2 || prog == 6 || prog == 3) && !menu_bg)   /* not behind the Camp background */
        return HUD_TOPLEFT | HUD_BOTTOM;     /* maps: the compass of towns and fields, the world map's bottom panels */
    if (prog == 4 || prog == 7) return HUD_TOPLEFT;  /* talking, shops: the compass; dialogue, choices, shop stay */
    return 0;
}

/* a piece of the UI layer: plain 2D, or a two-pass frame on the sprite layer (rhw 0.1: the fishing panel's and the
   Enemy(s) box's backdrops; single sprites there are characters and NPCs, which stay where they stand; on maps no
   HUD is drawn there, and a chimney's smoke there would join the compass), not taken by a
   backdrop rule (single-pass translucent labels, such as battle's "Enemy(s)", are squeezed but not cut: keep 2) */
static int g_spr;                                             /* sprite-layer frames count (fishing, battle) */
static int ui_piece(const Prim *p, const Vtx *v) {
    return (!p->keep || p->keep == 2) && fabsf(v[p->v0].z - UI_Z) < 1e-6f &&
           (p->flat || (g_spr && p->pair && fabsf(v[p->v0].rhw - 0.1f) < 1e-6f));
}

/* HUD panels to the screen edges: windows (two-pass frames, or tiles flagged 0x4000) that touch or overlap are one
   panel (neighbouring panels a few pixels apart, such as battle's Enemy(s) and turn boxes, stay separate); a panel
   left of the centre moves left by the width of the side bar, one right of it moves right, one across the centre (a
   message box) stays. Every UI piece lying within a panel (its text and icons) moves with it, as does a sprite lying
   wholly inside one and drawn after it (the world map's road arrows, on the map's sprite layer, unlike the roads
   drawn before the HUD); untextured pieces only when they
   are rectangles (a box's dark fill). Anything else stays: the hero's sprite, the fishing line, the black shapes of a
   screen wipe or of the world map's vignette that happen to lie over a panel.
   Outside the fishing minigame only the panels of some regions move (sel: bottom, top-left, top-right), and any
   textured box of some size counts as a window too (the world map's empty road boxes). A UI piece follows the
   panel of the smallest window it lies in (text overlaps its box, so it is part of the box's panel), not the
   outline of a merged panel: battle's submenu joins the command menu and turn box into one L-shaped panel whose
   outline covers the Enemy(s) box. A sprite (the road arrows, between the road boxes) uses the outline.
   Spell sparkles and screen captures (flagged 0x2000) are never windows, nor are sprites on the UI layer by size
   alone (the party running past the compass in a field), and a top-left panel only moves when it has
   a two-pass window frame (the compass), not for a cloud of a summon drawn there. */
static int in_box(const Prim *p, const float *b, float m) {
    return p->x0 >= b[0] - m && p->x1 <= b[1] + m && p->y0 >= b[2] - m && p->y1 <= b[3] + m;
}
static int upright(const Vtx *q, int n) {                  /* every corner on its bounding box's sides */
    float x0 = q[0].x, x1 = q[0].x, y0 = q[0].y, y1 = q[0].y;
    int i;
    for (i = 1; i < n; i++) { x0 = fminf(x0, q[i].x); x1 = fmaxf(x1, q[i].x); y0 = fminf(y0, q[i].y); y1 = fmaxf(y1, q[i].y); }
    for (i = 0; i < n; i++)
        if ((fabsf(q[i].x - x0) > 0.5f && fabsf(q[i].x - x1) > 0.5f) || (fabsf(q[i].y - y0) > 0.5f && fabsf(q[i].y - y1) > 0.5f))
            return 0;
    return 1;
}
static int member(const Prim *p, const Vtx *v, const float *b, float m, int after) {
    if (!ui_piece(p, v))                                         /* a sprite of another layer: wholly inside */
        return after && p->flat && p->w & 4 && (!p->keep || p->keep == 2) && in_box(p, b, 0);
    if (!(p->w & 4) && p->w & 0x20 && p->x1 - p->x0 < 0.5f * m)   /* (m: 2% of the width) a see-through speck: */
        return 0;                                                 /* spray (the waterfall's, over the compass) */
    if ((!(p->w & 4) || p->keep == 2) && !upright(v + p->v0, p->n))  /* untextured or translucent: only a rectangle
                                              (not the vignette, nor North Chamba's fog of diamond tiles over the water) */
        return 0;
    if (!after && !upright(v + p->v0, p->n))    /* slanted and drawn before the panel: the scene (the Tomb's ghost */
        return 0;                               /* blocks); the compass needle comes after its box */
    return in_box(p, b, m);
}
#define MAX_PANEL 2048                                       /* windows per frame (the Settings screen has 600) */
static int g_par[MAX_PANEL], g_pi[MAX_PANEL];
static float g_bx[MAX_PANEL][4];
static int g_first[MAX_PANEL];                                /* first container of each panel, in drawing order */
static u8 g_frame[MAX_PANEL];                                 /* the panel has a two-pass window frame */
static int g_cnt[MAX_PANEL], *g_gi, g_gi_cap;                 /* plain 2D pieces per panel; panel of each piece */
static int grow(void **p, int *cap, int n, int size);
static int root(int a) { while (g_par[a] != a) a = g_par[a] = g_par[g_par[a]]; return a; }
static void hud_push(Prim *pw, int np, const Vtx *v, float l, float r, float t, float bt, float cx, float k, int sel) {
    float m = (g_spr = (sel & (HUD_ALL | HUD_TOPRIGHT)) != 0, 0.02f * (r - l)), mj = 0.005f * (r - l), dl = cx - (cx - l) * k - l, dr = r - (cx + (r - cx) * k), h = bt - t;
    int n = 0, i, j;
    for (j = 0; j < np && n < MAX_PANEL; j++)
        if (ui_piece(&pw[j], v) && !(pw[j].w & 0x2000) && pw[j].w & 4 &&
            !(pw[j].pair && pw[j].w & 0x20 && (pw[j].x1 - pw[j].x0 > 0.1f * (r - l) || pw[j].x0 < l ||  /* not a */
                pw[j].x1 > r || pw[j].y0 < t || pw[j].y1 > bt)) &&      /* two-pass puff of mist (the waterfall's) */
            (pw[j].pair || pw[j].w & 0x4000 ||
            (sel != HUD_ALL && pw[j].flat && pw[j].x1 - pw[j].x0 >= 0.03f * (r - l) && pw[j].y1 - pw[j].y0 >= 0.03f * h &&
             pw[j].x0 >= l && pw[j].x1 <= r && pw[j].y0 >= t && pw[j].y1 <= bt &&    /* on screen: not a sky tile, */
             upright(v + pw[j].v0, pw[j].n)))) {                 /* upright: not the Tomb's ghost blocks */
            g_pi[n] = j; g_par[n] = n; n++;
        }
    for (i = 0; i < n; i++)
        for (j = i + 1; j < n; j++) {
            const Prim *a = &pw[g_pi[i]], *b = &pw[g_pi[j]];
            if (a->x0 - mj <= b->x1 && b->x0 - mj <= a->x1 && a->y0 - mj <= b->y1 && b->y0 - mj <= a->y1)
                g_par[root(i)] = root(j);
        }
    for (i = 0; i < n; i++) { g_bx[i][0] = g_bx[i][2] = 1e30f; g_bx[i][1] = g_bx[i][3] = -1e30f; g_first[i] = np; g_frame[i] = 0; }
    for (i = 0; i < n; i++) {
        const Prim *a = &pw[g_pi[i]];
        float *b = g_bx[root(i)];
        b[0] = fminf(b[0], a->x0); b[1] = fmaxf(b[1], a->x1); b[2] = fminf(b[2], a->y0); b[3] = fmaxf(b[3], a->y1);
        if (g_pi[i] < g_first[root(i)]) g_first[root(i)] = g_pi[i];
        if (a->pair && !a->keep) g_frame[root(i)] = 1;
    }
    if (!grow((void **)&g_gi, &g_gi_cap, np, sizeof(int))) return;
    for (i = 0; i < n; i++) g_cnt[i] = 0;
    for (j = 0; j < np; j++) {                                /* the panel of each piece */
        Prim *p = &pw[j];
        const float *b = NULL;
        float best = 1e30f;
        if (ui_piece(p, v)) {
            for (i = 0; i < n; i++) {                            /* the smallest window it lies in */
                const Prim *c = &pw[g_pi[i]];
                float cb[4] = { c->x0, c->x1, c->y0, c->y1 }, a = (c->x1 - c->x0) * (c->y1 - c->y0);
                if (a < best && member(p, v, cb, m, j > g_first[root(i)])) { best = a; b = g_bx[root(i)]; }
            }
            for (i = 0; i < n && !b && upright(v + p->v0, p->n); i++) /* else the smallest panel outline (a box's dark */
                if (root(i) == i && member(p, v, g_bx[i], m, 1)) {   /* fill, across its tiles) */
                    float a = (g_bx[i][1] - g_bx[i][0]) * (g_bx[i][3] - g_bx[i][2]);
                    int k2;
                    const float *c = g_bx[i];
                    for (k2 = i + 1; k2 < n; k2++)
                        if (root(k2) == k2 && member(p, v, g_bx[k2], m, 1) &&
                            (g_bx[k2][1] - g_bx[k2][0]) * (g_bx[k2][3] - g_bx[k2][2]) < a) {
                            a = (g_bx[k2][1] - g_bx[k2][0]) * (g_bx[k2][3] - g_bx[k2][2]); c = g_bx[k2];
                        }
                    b = c;
                }
        } else
            for (i = 0; i < n && !b; i++)                        /* a sprite: inside a panel's outline */
                if (root(i) == i && member(p, v, g_bx[i], m, j > g_first[i])) b = g_bx[i];
        g_gi[j] = b ? (int)((b - g_bx[0]) / 4) : -1;
        if (b && p->flat && p->w & 4) g_cnt[g_gi[j]]++;       /* textured plain 2D pieces per panel */
    }
    for (j = 0; j < np; j++) {
        int g = g_gi[j];
        const float *b;
        if (g < 0) continue;
        b = g_bx[g];
        /* fishing: all panels but the depth gauge (bottom right; its marker is drawn apart from it) and those with
           at most two textured plain 2D pieces: a bare frame (the box around the hero while reeling, drawn around his
           spot in the scene) and the scene's sprites on the sprite layer (dragonflies, splashes and their untextured
           droplets), even when they touch */
        if ((sel & HUD_ALL && !(b[2] >= t + 0.6f * h && b[0] >= cx) && g_cnt[g] > 2) ||
            (sel & HUD_BOTTOM && b[2] >= t + 0.6f * h) ||
            (sel & HUD_TOPLEFT && b[3] <= t + 0.25f * h && b[1] <= cx && g_frame[g]) ||
            (sel & HUD_TOPRIGHT && b[3] <= t + 0.25f * h && b[0] >= cx))
            pw[j].push = b[1] <= cx ? -dl : b[0] >= cx ? dr : 0;
    }
}

static int grow(void **p, int *cap, int n, int size) {
    void *q;
    if (n <= *cap) return 1;
    if (!(q = realloc(*p, (size_t)n * size))) return 0;
    *p = q; *cap = n; return 1;
}

static void *low_alloc(u32 n) {                     /* memory below 16 MB, where the game's 24-bit packet links reach */
    MEMORY_BASIC_INFORMATION m;
    u32 a = 0x10000;
    while (a < 0x1000000 && VirtualQuery((void *)(size_t)a, &m, sizeof m)) {
        u32 b = ((u32)(size_t)m.BaseAddress + 0xFFFF) & ~0xFFFFu, e = (u32)(size_t)m.BaseAddress + (u32)m.RegionSize;
        void *p;
        if (m.State == MEM_FREE && b + n <= e && b + n <= 0x1000000 &&
            (p = VirtualAlloc((void *)(size_t)b, n, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE))) return p;
        a = e;
    }
    return 0;
}

void wide_exec(void *surf, int *rect, int flag) {
    static int bufs;
    float l = (float)rect[0], r = (float)rect[2], t = (float)rect[1], bt = (float)rect[3], cx = (l + r) * 0.5f, k;
    int nv = (int)(MEM(u32, VTX_PTR) - VTX_BASE) / 32, vi = 0, nvp = 0, np = 0, i, j, m, menu_bg = 0;
    u32 c = CMD_BASE, end = MEM(u32, CMD_PTR);
    Vtx *v = (Vtx *)VTX_BASE;
    k = r > l ? 4.0f / 3 * (bt - t) / (r - l) : 1;
    if (!bufs) {                                                /* bigger frame buffers from the next frame on */
        void *vb = VirtualAlloc(0, BIG_VTX * sizeof(Vtx), MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
        void *cb = VirtualAlloc(0, BIG_CMD * 8, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
        bufs = 1;
        if (vb && cb) { MEM(u32, BUF_VARS + 12) = (u32)(size_t)cb; MEM(u32, BUF_VARS + 8) = (u32)(size_t)vb; }
    }
    if (bufs == 1 && VTX_BASE != GAME_VTX) {                   /* bigger polygon pools once the game's vertex buffer is free */
        void *p0 = low_alloc(BIG_POLY * 0x54), *p1 = low_alloc(BIG_POLY * 0x54);
        bufs = 2;     /* else: the game's vertex buffer (3120 polygons) and both old pools as one (4096) */
        MEM(u32, POOL_VARS) = p0 ? (u32)(size_t)p0 : GAME_VTX;
        MEM(u32, POOL_VARS + 4) = p1 ? (u32)(size_t)p1 : 0xB57400;
    }
    if (k > 0.999f || nv <= 0 || nv > 1 << 18 || end < CMD_BASE || end - CMD_BASE > 1 << 20 ||
        !grow((void **)&g_bak, &g_cap, nv, sizeof(Vtx)) || !grow((void **)&g_p, &g_cap_p, (end - CMD_BASE) / 8 + 1, sizeof(Prim))) {
        exec(surf, rect, flag); return;
    }
    memcpy(g_bak, v, (size_t)nv * sizeof(Vtx));
    while (c < end && vi < nv) {                                /* collect the primitives; squeeze viewports */
        u32 w = MEM(u32, c);
        int n = (w >> 8) & 7, draws = w & 0x800 ? 2 : 1, d;
        if (w & 0x1000) {                                       /* viewport: x, y, w, h at +8 */
            u32 *vp = (u32 *)(size_t)(c + 8);
            if (nvp < MAX_VP && !(vp[0] <= l && vp[0] + vp[2] >= r)) {
                g_vp[nvp].r = vp; g_vp[nvp].x = vp[0]; g_vp[nvp++].w = vp[2];
                vp[0] = (u32)(cx + (vp[0] - cx) * k + 0.5f); vp[2] = (u32)(vp[2] * k + 0.5f);
            }
            c += 0x18; vi += n; continue;
        }
        if (vi + n * draws > nv) break;                          /* inconsistent batch: leave the rest */
        for (d = 0; d < draws; d++, vi += n, c += 8) {           /* a second draw has its own entry and vertices */
            Prim *p = &g_p[np++];
            p->w = MEM(u32, c); p->tex = MEM(u32, c + 4); p->v0 = vi; p->n = n; p->flat = 1; p->pair = draws == 2; p->push = 0;
            p->x0 = p->y0 = 1e30f; p->x1 = p->y1 = -1e30f;
            for (i = vi; i < vi + n; i++) {
                if (v[i].x < p->x0) p->x0 = v[i].x; if (v[i].x > p->x1) p->x1 = v[i].x;
                if (v[i].y < p->y0) p->y0 = v[i].y; if (v[i].y > p->y1) p->y1 = v[i].y;
                if (v[i].rhw != 1.0f) p->flat = 0;
            }
            p->keep = p->flat && ((p->x0 <= l + 0.5f && p->x1 >= r - (r - l) / 320 - 0.5f) ||   /* full width (to a
                                     PS1 pixel: the plains' haze over the far ground is 319 wide) */
                                  (p->w & 0x2000 && p->y0 <= t + 0.05f * (bt - t) && p->y1 >= bt - 0.05f * (bt - t)));
                                  /* 0x2000 at full height: the screen redrawn from a capture (the battle swirl);
                                     small 0x2000 quads are sparkles and get squeezed like the rest */
            /* a picture on the sprite layer (rhw 0.1) covering the whole screen: the Camp menu's background */
            if (!p->flat && p->w & 4 && fabsf(v[vi].rhw - 0.1f) < 1e-6f && p->x0 <= l + 0.5f && p->x1 >= r - 0.5f &&
                p->y0 <= t + 0.5f && p->y1 >= bt - 0.5f) p->keep = 1, menu_bg = 1;
        }
    }
    /* a layer made for the 4:3 frame: a run of consecutive textured 2D tiles (one command word) covering the 4:3 width
       and starting or ending exactly at its edge (backdrops, summon skies, cloud layers whose art ends at the edges, a
       sky scrolled from the left edge such as Meteor Strike's), like a single full-width quad:
       keep = 1, stretched with the screen. Full-width quads in the run don't count (they are kept already): the title
       screen draws its logo and text in one run with its full-screen background, and they stay 4:3. No menu draws
       such a layer (checked on the title, Camp and Settings screens).
       Also a run whose tiles are all exactly one 4:3 width wide: a strip scrolled by copies placed side by side, which
       always covers the 4:3 screen but leaves gaps at the 16:9 edges when squeezed (the dark-sky summon's clouds). */
    for (i = 0; i < np; i = j > i ? j : i + 1) {
        float x0 = 1e30f, x1 = -1e30f;
        int tiles = 0, strips = 0;
        for (j = i; j < np && g_p[j].flat && g_p[j].w & 4 && g_p[j].w == g_p[i].w; j++) {
            if (g_p[j].keep) continue;
            x0 = fminf(x0, g_p[j].x0); x1 = fmaxf(x1, g_p[j].x1); tiles++;
            strips += fabsf(g_p[j].x1 - g_p[j].x0 - (r - l)) <= 0.5f;
        }
        if (tiles > 1 && ((fabsf(x0 - l) <= 0.5f && fabsf(x1 - r) <= 0.5f) || strips == tiles))
            for (m = i; m < j; m++) g_p[m].keep = 1;
    }
    /* a big picture in pieces: big opaque tiles (a quarter of the screen each way, on screen) in one row (same top and
       bottom) that join without gaps and cover the 4:3 width, wherever they are in the command list (other layers can
       be drawn between them: Kaiser Breath's Earth has a translucent copy after each half; MetaStrike's sky follows the
       ground's small pieces). Fitted (keep = 3): squeezed as far as it can be while still as wide as the screen, then
       moved just enough to cover it. A wide panorama (the plains) is simply squeezed; a picture made for the 4:3 view,
       scrolled or zoomed (Meteor Strike's and MetaStrike's skies, Kaiser Breath's Earth), is squeezed less and slid
       to the edge it would leave bare. Both amounts change smoothly while the picture pans or zooms, so it never jumps
       between squeezed and stretched. Other 2D in the same row inside the picture (the Earth's translucent copies)
       moves with it. An effect's mesh of small pieces that touches an edge (Gigaflare's shock wave) has no big
       tiles. */
    for (i = 0; i < np; i++) {
        Prim *p = &g_p[i];
        float bx0 = 1e30f, bx1 = -1e30f, sum = 0;
        float fk, fa, fb, fs;
        int n = 0;
        if (p->keep || !p->flat || !(p->w & 4) || p->w & 0x20 || !big_tile(p, v, l, r, t, bt)) continue;
        for (j = 0; j < np; j++) {
            Prim *q = &g_p[j];
            if (q->keep || !q->flat || !(q->w & 4) || q->w & 0x20 || !big_tile(q, v, l, r, t, bt) ||
                fabsf(q->y0 - p->y0) > 0.5f || fabsf(q->y1 - p->y1) > 0.5f) continue;
            bx0 = fminf(bx0, q->x0); bx1 = fmaxf(bx1, q->x1); sum += q->x1 - q->x0; n++;
        }
        if (n < 2 || sum < bx1 - bx0 - 1 || bx0 > l + 0.5f || bx1 < r - 0.5f) continue;
        fk = fmaxf(k, (r - l) / (bx1 - bx0));
        fa = cx + (bx0 - cx) * fk; fb = cx + (bx1 - cx) * fk;
        fs = fa > l ? l - fa : fb < r ? r - fb : 0;
        for (j = 0; j < np; j++) {
            Prim *q = &g_p[j];
            if (!q->keep && q->flat && q->w & 4 && fabsf(q->y0 - p->y0) <= 0.5f && fabsf(q->y1 - p->y1) <= 0.5f &&
                q->x0 >= bx0 - 0.5f && q->x1 <= bx1 + 0.5f) { q->keep = 3; q->fk = fk; q->fs = fs; }
        }
    }
    /* runs of consecutive textured 2D tiles (one command word) reaching past both 4:3 edges belong to the scene, even
       when each tile has its own texture (a summon's sky in two halves): squeezed but not cut (keep = 2). Except a floor
       drawn in 2D in perspective (the plains' far ground below the sky: a fan of trapezoids whose top edge, at the
       horizon, spans exactly the 4:3 width): squeezed, its top would leave the 16:9 corners bare, so it is stretched
       with the screen (keep = 1). */
    for (i = 0; i < np; i = j > i ? j : i + 1) {
        float x0 = 1e30f, x1 = -1e30f;
        int q, o;
        for (j = i; j < np && g_p[j].flat && g_p[j].w & 4 && g_p[j].w == g_p[i].w; j++) {
            x0 = fminf(x0, g_p[j].x0); x1 = fmaxf(x1, g_p[j].x1);
        }
        if (j - i > 1 && x0 < l - 0.5f && x1 > r + 0.5f)
            for (m = i; m < j; m++) {                            /* row by row (same top and bottom) */
                float tx0 = 1e30f, tx1 = -1e30f, y0 = g_p[m].y0, y1 = g_p[m].y1;
                if (g_p[m].keep) continue;
                for (o = m; o < j; o++)
                    if (!g_p[o].keep && fabsf(g_p[o].y0 - y0) <= 0.5f && fabsf(g_p[o].y1 - y1) <= 0.5f)
                        for (q = g_p[o].v0; q < g_p[o].v0 + g_p[o].n; q++)
                            if (fabsf(v[q].y - y0) <= 0.5f) { tx0 = fminf(tx0, v[q].x); tx1 = fmaxf(tx1, v[q].x); }
                for (o = m; o < j; o++)
                    if (!g_p[o].keep && fabsf(g_p[o].y0 - y0) <= 0.5f && fabsf(g_p[o].y1 - y1) <= 0.5f)
                        g_p[o].keep = fabsf(tx0 - l) <= 0.5f && fabsf(tx1 - r) <= 0.5f ? 1 : 2;
            }
    }
    /* likewise all 2D primitives of a texture that together reach past both 4:3 edges (sky panoramas, spell
       effects and their backdrops): squeezed but not cut (keep = 2). Menus sliding off reach past one edge only. */
    memset(g_tex, 0, sizeof g_tex);
    for (j = 0; j < np; j++) if (g_p[j].flat && g_p[j].w & 4) {
        TexSpan *s = tex_span(g_p[j].tex);
        if (s) { s->x0 = fminf(s->x0, g_p[j].x0); s->x1 = fmaxf(s->x1, g_p[j].x1); s->n++;
                 s->edge += fabsf(g_p[j].x0 - l) <= 0.5f || fabsf(g_p[j].x1 - r) <= 0.5f; }
    }
    for (j = 0; j < np; j++) if (g_p[j].flat && g_p[j].w & 4 && !g_p[j].keep) {
        TexSpan *s = tex_span(g_p[j].tex);
        if (s && s->x0 < l - 0.5f && s->x1 > r + 0.5f) g_p[j].keep = 2;
    }
    /* a single large picture drawn to an edge of the 4:3 frame (a summon's first cloud, before the rest of its layer
       is on screen): stretched too, when every piece of its texture touches an edge (a picture drifting across the
       edge, such as Flood Tide's light, ends on it for a few frames while its other copy does not). UI windows are
       drawn as two-pass pairs (the world map's corner frames touch the edges the same way) and are left alone. */
    for (j = 0; j < np; j++) {
        Prim *p = &g_p[j];
        TexSpan *s;
        if (!p->keep && p->flat && p->w & 4 && !p->pair && (fabsf(p->x0 - l) <= 0.5f || fabsf(p->x1 - r) <= 0.5f) &&
            p->x1 - p->x0 >= 0.25f * (r - l) && p->y1 - p->y0 >= 0.1f * (bt - t) &&
            (s = tex_span(p->tex)) && s->edge == s->n) p->keep = 1;
        /* single-pass semi-transparent pictures are effects (Blizzard's snow puffs drifting past one edge): squeezed
           but not cut. Menu windows and their text are drawn opaque or as pairs. */
        else if (!p->keep && p->flat && p->w & 4 && p->w & 0x20 && !p->pair) p->keep = 2;
    }
    if ((m = hud_mode(menu_bg)) != 0) hud_push(g_p, np, v, l, r, t, bt, cx, k, m);
    for (j = 0; j < np; j++) {
        Prim *p = &g_p[j];
        int untex = !(p->w & 4);
        if (p->keep == 1) continue;
        if (p->keep == 3) { for (i = p->v0; i < p->v0 + p->n; i++) v[i].x = cx + (v[i].x - cx) * p->fk + p->fs; continue; }
        if (p->flat && untex && p->w & 0x20)    /* see-through: a mask only when wide with a corner on the edge (a */
            for (i = p->v0, untex = 0; i < p->v0 + p->n; i++)  /* fade; a beam's or a glow's corner lands there too) */
                untex |= p->x1 - p->x0 >= 0.25f * (r - l) && (fabsf(v[i].x - l) <= 0.5f || fabsf(v[i].x - r) <= 0.5f);
        for (i = p->v0; i < p->v0 + p->n; i++)
            if (!(p->flat && untex && (v[i].x <= l + 0.5f || v[i].x >= r - 0.5f))) v[i].x = cx + (v[i].x - cx) * k;
        untex = !(p->w & 4);
        if (p->push != 0) {                                     /* HUD at the screen edges: cut there instead */
            for (i = p->v0; i < p->v0 + p->n; i++) v[i].x += p->push;
            if (p->flat && !untex) clip(v + p->v0, p->n, l, r);
            continue;
        }
        if (p->flat && !untex && !p->keep && fabsf(v[p->v0].z - UI_Z) < 1e-6f && upright(v + p->v0, p->n))
            clip(v + p->v0, p->n, cx - (cx - l) * k, cx + (r - cx) * k);   /* (a slanted face is the scene: the
                                                                          Tomb's ghost blocks, drawn in 2D) */
    }
    exec(surf, rect, flag);
    memcpy(v, g_bak, (size_t)nv * sizeof(Vtx));
    for (i = 0; i < nvp; i++) { g_vp[i].r[0] = g_vp[i].x; g_vp[i].r[2] = g_vp[i].w; }
}

/* Movies (0x40DDF0) are drawn outside the frame batch, by their own DrawPrimitive from one or two quads at 0x8D4198,
 * placed with the video's pixel size taken as PS1 pixels (320 x 240 fills the screen; a larger video runs off it).
 * The exe calls this instead of that routine's BeginScene: the quads are fitted to the largest centred rectangle with
 * the video's own aspect (a 4:3 movie is pillarboxed at 16:9, a 16:9 one fills the screen, at any resolution), and
 * the screen is cleared so the bars are black. The fit maps the quads onto themselves once done, so the routine
 * setting them up only on a movie's first frame is fine. */
#define MOVIE_VTX  0x8D4198
#define MOVIE_W    0xA798C8    /* the video's size in pixels */
#define MOVIE_H    0xA798CC
#define MOVIE_TEX2 0xA798DC    /* second texture: set when the video is split into two quads */
#define DEVICE     0xABC200    /* IDirect3DDevice7* */
#define RENDER_W   0x8D40D8
#define RENDER_H   0x8D40DC

__declspec(dllexport) void __cdecl bof4_movie(void) {
    Vtx *v = (Vtx *)MOVIE_VTX;
    void **dev = MEM(void **, DEVICE), **vt = *(void ***)dev;
    int n = MEM(u32, MOVIE_TEX2) ? 8 : 4, i;
    float W = (float)MEM(int, RENDER_W), H = (float)MEM(int, RENDER_H);
    float vw = (float)MEM(int, MOVIE_W), vh = (float)MEM(int, MOVIE_H);
    float x0 = 1e30f, x1 = -1e30f, y0 = 1e30f, y1 = -1e30f, tw, th;
    for (i = 0; i < n; i++) {
        x0 = fminf(x0, v[i].x); x1 = fmaxf(x1, v[i].x); y0 = fminf(y0, v[i].y); y1 = fmaxf(y1, v[i].y);
    }
    if (vw > 0 && vh > 0 && W > 0 && H > 0 && x1 > x0 && y1 > y0) {
        tw = H * vw / vh; th = H;
        if (tw > W) { tw = W; th = W * vh / vw; }
        for (i = 0; i < n; i++) {
            v[i].x = (W - tw) / 2 + (v[i].x - x0) * tw / (x1 - x0);
            v[i].y = (H - th) / 2 + (v[i].y - y0) * th / (y1 - y0);
        }
    }
    ((long (__stdcall *)(void *))vt[5])(dev);                                     /* BeginScene */
    ((long (__stdcall *)(void *, u32, void *, u32, u32, float, u32))vt[10])(dev, 0, NULL, 1, 0, 1.0f, 0);   /* Clear */
}
