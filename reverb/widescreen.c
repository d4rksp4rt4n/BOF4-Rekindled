/* Widescreen (option "widescreen", experimental).
 *
 * The game draws the PS1's 320x240 picture stretched to the render size from bof4.cfg (SetScale: x * W / 320,
 * y * H / 240), so at 16:9 everything is a third too wide. Every frame is one batch of screen-space D3DTLVERTEX
 * (0xA7C1D0) and a command list (0xA758B8); right before the screen pass replays it, every x is squeezed toward
 * the centre by (4/3) / (W/H). The 3D scene then has correct proportions and fills the sides (the exe's culls are
 * widened so the polygons there exist); 2D (menus, text, HUD) stays in the centred 4:3 area.
 * Exceptions, so the picture has no 4:3 frame:
 *  - 2D primitives covering the whole width (fades, flashes, letterbox bars) are not squeezed, nor are runs of
 *    textured 2D tiles that together cover the screen behind a 3D scene (the Sand Flier race's backdrop);
 *  - nor are 2D primitives flagged 0x2000: the previous screen redrawn from a capture texture (the battle swirl, two
 *    half-screen quads), which already holds the full widescreen picture;
 *  - untextured 2D keeps the corners it has at or beyond the left/right edge: masks reach the screen edges (the world
 *    map's vignette, the battle target scope, wipes);
 *  - textured plain 2D (rhw 1, z 0.01) is cut to the 4:3 area, as a 4:3 screen would: menus sliding off past its
 *    edge would otherwise show up in the side bars; except runs of tiles reaching past both edges in a 3D scene
 *    (scrolling sky panoramas, e.g. the plains), which only get squeezed;
 *  - viewports (the command list can switch to a sub-rectangle) are squeezed with their contents, unless they
 *    span the whole width.
 * At 4:3 (or narrower) nothing changes. The batch is restored after the replay. */
#include <windows.h>
#include <string.h>
#include <stdlib.h>
#include <math.h>

typedef unsigned char u8; typedef unsigned int u32;
#define MEM(t, a) (*(t *)(size_t)(a))
#define VTX_BASE 0xA7C1D0
#define VTX_PTR  0x96DA70
#define CMD_BASE 0xA758B8
#define CMD_PTR  0x96DA7C
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

typedef struct { u32 w, tex; int v0, n; float x0, x1, y0, y1; u8 flat, keep; } Prim;
static Prim *g_p; static int g_cap_p;

static int grow(void **p, int *cap, int n, int size) {
    void *q;
    if (n <= *cap) return 1;
    if (!(q = realloc(*p, (size_t)n * size))) return 0;
    *p = q; *cap = n; return 1;
}

void wide_exec(void *surf, int *rect, int flag) {
    float l = (float)rect[0], r = (float)rect[2], t = (float)rect[1], bt = (float)rect[3], cx = (l + r) * 0.5f, k;
    int nv = (int)(MEM(u32, VTX_PTR) - VTX_BASE) / 32, vi = 0, nvp = 0, np = 0, has3d = 0, i, j, m;
    u32 c = CMD_BASE, end = MEM(u32, CMD_PTR);
    Vtx *v = (Vtx *)VTX_BASE;
    k = r > l ? 4.0f / 3 * (bt - t) / (r - l) : 1;
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
            p->w = MEM(u32, c); p->tex = MEM(u32, c + 4); p->v0 = vi; p->n = n; p->flat = 1;
            p->x0 = p->y0 = 1e30f; p->x1 = p->y1 = -1e30f;
            for (i = vi; i < vi + n; i++) {
                if (v[i].x < p->x0) p->x0 = v[i].x; if (v[i].x > p->x1) p->x1 = v[i].x;
                if (v[i].y < p->y0) p->y0 = v[i].y; if (v[i].y > p->y1) p->y1 = v[i].y;
                if (v[i].rhw != 1.0f) p->flat = 0;
            }
            p->keep = p->flat && ((p->x0 <= l + 0.5f && p->x1 >= r - 0.5f) || p->w & 0x2000);
            has3d |= !p->flat;
        }
    }
    /* runs of consecutive textured 2D tiles (one command word) in a 3D scene: covering the screen, a backdrop
       (keep = 1: as it is); reaching past both 4:3 edges, a scrolling panorama (keep = 2: squeezed but not cut) */
    for (i = 0; has3d && i < np; i = j > i ? j : i + 1) {
        float x0 = 1e30f, x1 = -1e30f, y0 = 1e30f, y1 = -1e30f, area = 0;       /* area: not scattered sprites (map dots) */
        for (j = i; j < np && g_p[j].flat && g_p[j].w & 4 && g_p[j].w == g_p[i].w; j++) {
            x0 = fminf(x0, g_p[j].x0); x1 = fmaxf(x1, g_p[j].x1); y0 = fminf(y0, g_p[j].y0); y1 = fmaxf(y1, g_p[j].y1);
            area += (g_p[j].x1 - g_p[j].x0) * (g_p[j].y1 - g_p[j].y0);
        }
        if (j - i > 1 && j - i <= 64 && x0 <= l + 0.5f && x1 >= r - 0.5f && y0 <= t + 0.5f && y1 >= bt - 0.5f && area >= 0.9f * (r - l) * (bt - t))
            for (m = i; m < j; m++) g_p[m].keep = 1;
        else if (j - i > 1 && j - i <= 64 && x0 < l - 0.5f && x1 > r + 0.5f)
            for (m = i; m < j; m++) g_p[m].keep = 2;
    }
    for (j = 0; j < np; j++) {
        Prim *p = &g_p[j];
        int untex = !(p->w & 4);
        if (p->keep == 1) continue;
        for (i = p->v0; i < p->v0 + p->n; i++)
            if (!(p->flat && untex && (v[i].x <= l + 0.5f || v[i].x >= r - 0.5f))) v[i].x = cx + (v[i].x - cx) * k;
        if (p->flat && !untex && !p->keep && fabsf(v[p->v0].z - UI_Z) < 1e-6f)
            clip(v + p->v0, p->n, cx - (cx - l) * k, cx + (r - cx) * k);
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
