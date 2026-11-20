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
 *  - nor are full-height 2D primitives flagged 0x2000: the previous screen redrawn from a capture texture (the battle
 *    swirl, two half-screen quads), which already holds the full widescreen picture;
 *  - untextured 2D keeps the corners it has at or beyond the left/right edge: masks reach the screen edges (the world
 *    map's vignette, the battle target scope, wipes);
 *  - textured plain 2D (rhw 1, z 0.01) is cut to the 4:3 area, as a 4:3 screen would: menus sliding off past its
 *    edge would otherwise show up in the side bars; except runs of tiles reaching past both edges (sky panoramas such
 *    as the plains', spell effects such as Gigaflare, Blizzard's backdrop) and single-pass semi-transparent pictures
 *    (effects such as Blizzard's snow), which only get squeezed;
 *  - a big backdrop in pieces (big opaque tiles in one row covering the 4:3 width, such as the Breath attacks' skies
 *    and Kaiser Breath's Earth) is fitted: squeezed only as far as it still covers the screen, and slid to close a
 *    gap, so a panning or zooming picture never jumps between squeezed and stretched;
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

typedef struct { u32 w, tex; int v0, n; float x0, x1, y0, y1, fk, fs; u8 flat, keep, pair; } Prim;
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

/* a tile of a sky picture: a quarter of the screen wide and high, and on screen vertically (a ground mesh drawn with
   the same command word has huge pieces below the screen) */
static int big_tile(const Prim *p, float l, float r, float t, float bt) {
    return p->x1 - p->x0 >= 0.25f * (r - l) && p->y1 - p->y0 >= 0.25f * (bt - t) && p->y0 < bt && p->y1 > t;
}

static int grow(void **p, int *cap, int n, int size) {
    void *q;
    if (n <= *cap) return 1;
    if (!(q = realloc(*p, (size_t)n * size))) return 0;
    *p = q; *cap = n; return 1;
}

void wide_exec(void *surf, int *rect, int flag) {
    float l = (float)rect[0], r = (float)rect[2], t = (float)rect[1], bt = (float)rect[3], cx = (l + r) * 0.5f, k;
    int nv = (int)(MEM(u32, VTX_PTR) - VTX_BASE) / 32, vi = 0, nvp = 0, np = 0, i, j, m;
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
            p->w = MEM(u32, c); p->tex = MEM(u32, c + 4); p->v0 = vi; p->n = n; p->flat = 1; p->pair = draws == 2;
            p->x0 = p->y0 = 1e30f; p->x1 = p->y1 = -1e30f;
            for (i = vi; i < vi + n; i++) {
                if (v[i].x < p->x0) p->x0 = v[i].x; if (v[i].x > p->x1) p->x1 = v[i].x;
                if (v[i].y < p->y0) p->y0 = v[i].y; if (v[i].y > p->y1) p->y1 = v[i].y;
                if (v[i].rhw != 1.0f) p->flat = 0;
            }
            p->keep = p->flat && ((p->x0 <= l + 0.5f && p->x1 >= r - 0.5f) ||      /* full width */
                                  (p->w & 0x2000 && p->y0 <= t + 0.05f * (bt - t) && p->y1 >= bt - 0.05f * (bt - t)));
                                  /* 0x2000 at full height: the screen redrawn from a capture (the battle swirl);
                                     small 0x2000 quads are sparkles and get squeezed like the rest */
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
        if (p->keep || !p->flat || !(p->w & 4) || p->w & 0x20 || !big_tile(p, l, r, t, bt)) continue;
        for (j = 0; j < np; j++) {
            Prim *q = &g_p[j];
            if (q->keep || !q->flat || !(q->w & 4) || q->w & 0x20 || !big_tile(q, l, r, t, bt) ||
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
       when each tile has its own texture (a summon's sky in two halves): squeezed but not cut (keep = 2) */
    for (i = 0; i < np; i = j > i ? j : i + 1) {
        float x0 = 1e30f, x1 = -1e30f;
        for (j = i; j < np && g_p[j].flat && g_p[j].w & 4 && g_p[j].w == g_p[i].w; j++) {
            x0 = fminf(x0, g_p[j].x0); x1 = fmaxf(x1, g_p[j].x1);
        }
        if (j - i > 1 && x0 < l - 0.5f && x1 > r + 0.5f)
            for (m = i; m < j; m++) if (!g_p[m].keep) g_p[m].keep = 2;
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
    for (j = 0; j < np; j++) {
        Prim *p = &g_p[j];
        int untex = !(p->w & 4);
        if (p->keep == 1) continue;
        if (p->keep == 3) { for (i = p->v0; i < p->v0 + p->n; i++) v[i].x = cx + (v[i].x - cx) * p->fk + p->fs; continue; }
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
