/* 60 fps by interpolation (option "fps60", experimental).
 *
 * The game runs logic and drawing in lockstep at 30 fps (VSync(2), [0xB50978] = 2) and presents each frame
 * at the start of the next main-loop pass (PutDrawEnv -> 0x4028D0), one vblank after it was drawn. That
 * skipped vblank gets an in-between frame: when frame N's screen pass runs (0x40AC03 -> bof4_fps_screen),
 * we draw a blend of frames N-1 and N, present it, then draw N as usual. Presents are paced here
 * (bof4_fps_present): the game's limiter alternated 32 and 34 ms frames for whole seconds.
 *
 * Every frame is one batch of D3DTLVERTEX (0xA7C1D0) plus a command list (0xA758B8). Per primitive:
 *  - 3D (the PC port's extended packets: rhw != 1, sz = view Z / [0xBBFAC0]): unproject, and look for the
 *    same texture/UVs in N-1 where the previous camera would have put it. Found there -> static in the
 *    world: move it by half the camera change (camera = MATRIX at 0xBAD7F4, averaged element-wise; H/OFX/OFY
 *    from the GTE state). Found elsewhere -> it moved on its own: blend toward its old screen position.
 *    Not found -> camera blend.
 *  - sprites in the 3D scene (rhw != 1, fixed sz 0.01): matched to N-1 (twin where the ground under them
 *    went, or near their own spot), grouped into characters (parts sharing corners) that move as one;
 *    a character with no match stays, follows the ground, or follows the character it overlaps.
 *  - 2D (UI, map layers): matched to N-1 by texture, UVs and colour, nearest and unambiguous only, one to
 *    one; a layer moving as one lends its motion to tiles that disagree; UI that jumps is not blended.
 *  - finally, vertices shared by neighbouring primitives get one move (no cracks).
 * No in-between frame (N is simply shown twice, as before) on: not consecutive logic frames, VSync count
 * != 2, a camera cut, projection/scale changes, or when too few primitives match.
 * Scroll Lock switches the in-between frames off/on. BOF4_reverb.ini [fps60]: log=1 (BOF4_fps60.log),
 * dump=1 (Pause writes the last 32 frames to fps60_dump\ for fps60_test).
 *
 * FPS_TEST builds an offline tester that replays those dumps (or bof4_diag's): .psxseg + .data snapshots. */
#include <windows.h>
#include <math.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>

typedef unsigned char u8; typedef unsigned int u32;

#define VTX_BASE 0xA7C1D0
#define VTX_PTR  0x96DA70
#define CMD_BASE 0xA758B8
#define CMD_PTR  0x96DA7C
#define CAMERA   0xBAD7F4      /* MATRIX: short R[3][3], pad, long T[3] at +0x14 */
#define GTE_H    0xAE9C30
#define GTE_OFX  0xAE9C40
#define GTE_OFY  0xAE9C3C
#define SCALE_X  0xA73FF8
#define SCALE_Y  0xA73FF4
#define Z_SCALE  0xBBFAC0
#define COUNTER  0xBB6640      /* +1 per logic step */
#define VSYNC_N  0xB50978
#define RFLAGS   0x96DA78
#define EXEC     0x40A8A0      /* replays the batch: (surface, rect, flag) */
#define PRESENT  0x4028D0      /* Flip / Blt, then clears Z */
#define FEATURES 0x6A7D01      /* set by the exe's stub: bit 0 = 60 fps, bit 1 = widescreen (widescreen.c) */

#define NEAR_Z     16.0f       /* view Z below this: vertex left as in N */
#define TOL_STATIC 1.5f        /* PS1 pixels: matched where the camera predicts -> static in the world */
#define TOL_MOVE   40.0f       /* PS1 pixels: furthest a primitive may move on its own in one frame */
#define TOL_LOOSE  16.0f       /* PS1 pixels: same texture, new UVs (sprite animation): moved by its centre */
#define TOL_BILL   12.0f       /* PS1 pixels: furthest a sprite in the 3D scene moves in a frame (running party ~5);
                                  identical sprites further away (another member's shadow) are not it */
#define FLAT_Z     0.01f       /* sz of sprites: rhw != 1 but no real depth */
#define UI_JUMP    3.0f        /* PS1 pixels: a 2D (UI) quad moving this far in one frame jumped (menu list scrolling a
                                  row, text re-flowing); smooth UI motion is slower (world map layer ~2, damage numbers ~2.5) */
#define GROUND_R   80.0f       /* PS1 pixels: furthest static 3D geometry that predicts a billboard's motion */
#define MIN_MATCH  0.25f       /* below this share of matched primitives: treat as a cut */
#define CUT_ROT    0.15f       /* relative change of the camera rotation */
#define CUT_TRANS  2000.0f     /* camera translation jump */
#define HBITS 12

#ifdef FPS_TEST
static u8 *g_ram;              /* dump: .psxseg (0x6A8000, 0x216000) then .data (0x8D4000) */
static u8 *gmem(u32 a) { return g_ram + (a < 0x8BE000 ? a - 0x6A8000 : 0x216000 + a - 0x8D4000); }
#else
static u8 *gmem(u32 a) { return (u8 *)(size_t)a; }
#endif
#define MEM(t, a) (*(t *)gmem(a))

typedef struct { float x, y, z, rhw; u32 col, spec; float u, v; } Vtx;
#ifdef FPS_TEST
static char g_cat[1 << 16];
#define CAT(k, c) (g_cat[k] = (c))
#else
#define CAT(k, c) ((void)0)
#endif
typedef struct { int v0, n, next, lnext; u32 key, lkey; float cx, cy, w, h; u8 depth, bill, ui; } Prim;
typedef struct {
    Vtx *v; Prim *p; int nv, np, cap_v, cap_p;
    int head[1 << HBITS], lhead[1 << HBITS];      /* by key (texture + UVs), by loose key (texture only) */
    float R[9], Ri[9], T[3], H, ofx, ofy, sx, sy, zs;
    u32 counter, vsync_n, flags;
    int valid, cam;
} Frame;
typedef struct { int frames, mid, skip_seq, skip_cut, skip_match; long cam_static, moved, cam_only, flat_moved, flat_still, flat_shift, flat_none, welded; } Stats;

static int grow(void **p, int *cap, int n, int size) {
    void *q;
    if (n <= *cap) return 1;
    if (!(q = realloc(*p, (size_t)n * size))) return 0;
    *p = q; *cap = n; return 1;
}

static u32 hash_loose(int n, u32 word, u32 tex) {
    u32 h = 2166136261u ^ word;
    h = (h ^ tex) * 16777619u; return (h ^ (u32)n) * 16777619u;
}
/* texture, UVs and, for flat primitives, colours (3D ones change colour with depth cueing) */
static u32 hash_prim(const Vtx *v, int n, u32 word, u32 tex, int depth) {
    u32 h = hash_loose(n, word, tex), i;
    const u32 *w;
    for (i = 0; i < (u32)n; i++) {
        w = (const u32 *)&v[i].u; h = (h ^ w[0]) * 16777619u; h = (h ^ w[1]) * 16777619u;
        if (!depth) h = (h ^ v[i].col) * 16777619u;
    }
    return h;
}

static int inv3(const float *m, float *r) {
    float d = m[0] * (m[4] * m[8] - m[5] * m[7]) - m[1] * (m[3] * m[8] - m[5] * m[6]) + m[2] * (m[3] * m[7] - m[4] * m[6]);
    if (fabsf(d) < 1e-9f) return 0;
    d = 1.0f / d;
    r[0] = (m[4] * m[8] - m[5] * m[7]) * d; r[1] = (m[2] * m[7] - m[1] * m[8]) * d; r[2] = (m[1] * m[5] - m[2] * m[4]) * d;
    r[3] = (m[5] * m[6] - m[3] * m[8]) * d; r[4] = (m[0] * m[8] - m[2] * m[6]) * d; r[5] = (m[2] * m[3] - m[0] * m[5]) * d;
    r[6] = (m[3] * m[7] - m[4] * m[6]) * d; r[7] = (m[1] * m[6] - m[0] * m[7]) * d; r[8] = (m[0] * m[4] - m[1] * m[3]) * d;
    return 1;
}

static int add_prim(Frame *f, int v0, int n, u32 word, u32 tex) {
    Prim *p; int i, depth = 1, bill = 1, ui = 1; u32 b; float x0 = 1e30f, x1 = -1e30f, y0 = 1e30f, y1 = -1e30f;
    if (n <= 0) return 1;
    if (!(word & 4)) tex = 0;                                  /* untextured: the slot holds a stale texture */
    if (v0 + n > f->nv || !grow((void **)&f->p, &f->cap_p, f->np + 1, sizeof(Prim))) return 0;
    p = &f->p[f->np];
    p->v0 = v0; p->n = n; p->cx = p->cy = 0;
    for (i = 0; i < n; i++) {
        const Vtx *v = &f->v[v0 + i];
        p->cx += v->x; p->cy += v->y;
        if (v->x < x0) x0 = v->x; if (v->x > x1) x1 = v->x; if (v->y < y0) y0 = v->y; if (v->y > y1) y1 = v->y;
        if (v->rhw == 1.0f || v->z <= 0 || v->z == FLAT_Z) depth = 0;
        if (v->rhw == 1.0f || v->z != FLAT_Z) bill = 0;
        if (v->rhw != 1.0f) ui = 0;
    }
    p->cx /= n; p->cy /= n; p->w = x1 - x0; p->h = y1 - y0; p->depth = (u8)depth; p->bill = (u8)bill; p->ui = (u8)ui;
    p->key = hash_prim(&f->v[v0], n, word, tex, depth);
    p->lkey = hash_loose(n, word, tex);
    b = p->key & ((1 << HBITS) - 1); p->next = f->head[b]; f->head[b] = f->np;
    b = p->lkey & ((1 << HBITS) - 1); p->lnext = f->lhead[b]; f->lhead[b] = f->np;
    f->np++;
    return 1;
}

/* copy the frame the game just built; walks the command list the way EXEC does */
static int capture(Frame *f) {
    int nv = (int)(MEM(u32, VTX_PTR) - VTX_BASE) / 32, vi = 0, i;
    u32 c = CMD_BASE, end = MEM(u32, CMD_PTR), w;
    short *r;
    f->valid = 0; f->np = 0;
    if (nv < 0 || nv > 1 << 18 || end < CMD_BASE || end - CMD_BASE > 1 << 20) return 0;
    if (!grow((void **)&f->v, &f->cap_v, nv + 1, sizeof(Vtx))) return 0;
    f->nv = nv;
    memcpy(f->v, gmem(VTX_BASE), (size_t)nv * sizeof(Vtx));
    memset(f->head, -1, sizeof f->head); memset(f->lhead, -1, sizeof f->lhead);
    while (c < end) {
        int n;
        w = MEM(u32, c); n = (w >> 8) & 7;
        if (w & 0x1000) { c += 0x18; vi += n; continue; }               /* viewport change */
        if (!add_prim(f, vi, n, w, MEM(u32, c + 4))) return 0;
        vi += n;
        if (w & 0x800) {                                                  /* second draw, own entry */
            c += 8; w = MEM(u32, c);
            if (!add_prim(f, vi, n, w, MEM(u32, c + 4))) return 0;
            vi += n;
        }
        c += 8;
    }
    if (vi != nv) return 0;
    r = &MEM(short, CAMERA);
    for (i = 0; i < 9; i++) f->R[i] = r[i];
    for (i = 0; i < 3; i++) f->T[i] = (float)MEM(int, CAMERA + 0x14 + 4 * i);
    f->cam = inv3(f->R, f->Ri);
    f->H = (float)MEM(int, GTE_H); f->ofx = (float)MEM(int, GTE_OFX); f->ofy = (float)MEM(int, GTE_OFY);
    f->sx = MEM(float, SCALE_X); f->sy = MEM(float, SCALE_Y); f->zs = MEM(float, Z_SCALE);
    f->counter = MEM(u32, COUNTER); f->vsync_n = MEM(u32, VSYNC_N); f->flags = MEM(u32, RFLAGS);
    f->valid = f->H > 0 && f->sx > 0 && f->sy > 0 && f->zs > 0;
    return f->valid;
}

/* view-space point of a vertex with depth, and back */
static void unproject(const Frame *f, const Vtx *v, float *o) {
    o[2] = v->z * f->zs;
    o[0] = (v->x / f->sx - f->ofx) * o[2] / f->H;
    o[1] = (v->y / f->sy - f->ofy) * o[2] / f->H;
}
static void xform(const float *M, const float *K, const float *a, float *o) {
    o[0] = M[0] * a[0] + M[1] * a[1] + M[2] * a[2] + K[0];
    o[1] = M[3] * a[0] + M[4] * a[1] + M[5] * a[2] + K[1];
    o[2] = M[6] * a[0] + M[7] * a[1] + M[8] * a[2] + K[2];
}
/* M, K such that a view point of N maps to view space of camera (R, T): M = R * N.Ri, K = T - M * N.T */
static void cam_map(const Frame *N, const float *R, const float *T, float *M, float *K) {
    int i, j, k;
    for (i = 0; i < 3; i++) for (j = 0; j < 3; j++) {
        M[i * 3 + j] = 0;
        for (k = 0; k < 3; k++) M[i * 3 + j] += R[i * 3 + k] * N->Ri[k * 3 + j];
    }
    for (i = 0; i < 3; i++) K[i] = T[i] - (M[i * 3] * N->T[0] + M[i * 3 + 1] * N->T[1] + M[i * 3 + 2] * N->T[2]);
}

/* the closest and second-closest primitive of P with the same key (loose: same texture) around (x, y) */
/* P primitives already paired with an unchanged one in N (same spot, same everything): they can't also be the
   previous position of something else (a newly typed letter would otherwise match the same letter further back) */
static u8 *g_used; static int g_cap_used, g_skip_used;
static int find(const Frame *P, const Prim *q, int loose, float x, float y, float *d1, float *d2) {
    int j = loose ? P->lhead[q->lkey & ((1 << HBITS) - 1)] : P->head[q->key & ((1 << HBITS) - 1)], best = -1;
    float b1 = 1e30f, b2 = 1e30f, dx, dy, dd;
    for (; j >= 0; j = loose ? P->p[j].lnext : P->p[j].next) {
        const Prim *p = &P->p[j];
        if ((loose ? p->lkey != q->lkey : p->key != q->key) || p->n != q->n || (g_skip_used && g_used[j])) continue;
        dx = p->cx - x; dy = p->cy - y; dd = dx * dx + dy * dy;
        if (dd < b1) { b2 = b1; b1 = dd; best = j; } else if (dd < b2) b2 = dd;
    }
    *d1 = sqrtf(b1); *d2 = sqrtf(b2);
    return best;
}
/* a match counts only if no other twin is nearly as close (identical particles, glyphs, path tiles) */
#define UNIQUE(d1, d2, px) ((d2) >= 2 * (d1) + (px))

static void lerp_prim(const Frame *N, const Frame *P, const Prim *q, const Prim *p, Vtx *out, float t) {
    int i;
    for (i = 0; i < q->n; i++) {
        const Vtx *a = &N->v[q->v0 + i], *b = &P->v[p->v0 + i];
        Vtx *o = &out[q->v0 + i];
        o->x = a->x + t * (b->x - a->x);
        o->y = a->y + t * (b->y - a->y);
        if (q->depth && p->depth) {
            o->z = a->z + t * (b->z - a->z);
            if (o->z > 0) o->rhw = a->rhw * a->z / o->z;
        }
    }
}

/* per-primitive decision */
enum { K_CAM = 1, K_CAM_ONLY, K_MOVED, K_STILL, K_INPLACE, K_FLAT, K_AMBIG, K_SHIFT, K_FLOW, K_GROUND, K_BILL, K_SHADOWED, K_NONE };
typedef struct { float x, y, dx, dy; } Smp;     /* screen motion of static 3D geometry (camera only) */
static Smp *g_smp, *g_gm; static int g_cap_smp, g_cap_gm, g_nsmp;
static int cmp_f(const void *a, const void *b);
static float *g_med; static int g_cap_med;
static int *g_uf, *g_root, *g_res, g_cap_uf, g_cap_root, g_cap_res;
static int uf_find(int a) { while (g_uf[a] != a) a = g_uf[a] = g_uf[g_uf[a]]; return a; }
/* median screen motion of the static 3D geometry within r of (x, y) (the ground and walls around a sprite's feet) */
static int ground(int nsmp, float x, float y, float r, float *gx, float *gy) {
    int i, n = 0;
    if (!grow((void **)&g_med, &g_cap_med, 2 * nsmp + 2, sizeof(float))) return 0;
    for (i = 0; i < nsmp; i++) if (hypotf(g_smp[i].x - x, g_smp[i].y - y) < r) { g_med[n] = g_smp[i].dx; g_med[nsmp + n] = g_smp[i].dy; n++; }
    if (!n) return 0;
    qsort(g_med, n, sizeof(float), cmp_f); qsort(g_med + nsmp, n, sizeof(float), cmp_f);
    *gx = g_med[n / 2]; *gy = g_med[nsmp + n / 2];
    return 1;
}
typedef struct { u32 g; float dx, dy; int coherent; } Flow;
#define COHERENT 0.8f          /* share of a texture group's unique matches that agree with its median motion */
static int cmp_flow(const void *a, const void *b) {
    const Flow *x = a, *y = b;
    return x->g < y->g ? -1 : x->g > y->g;
}
static int cmp_f(const void *a, const void *b) { float x = *(const float *)a, y = *(const float *)b; return (x > y) - (x < y); }
static u8 *g_kind; static int *g_mj, g_cap_k, g_cap_j, g_cap_fl, g_cap_tmp; static Flow *g_fl; static float *g_tmp;

/* median motion of the uniquely matched flat primitives of each texture group; coherent = a layer that
   moves as one (scrolling map), not a swarm (particles) */
static int make_flow(int n, float tol) {
    int i = 0, j, k, m, agree;
    float mx, my;
    qsort(g_fl, n, sizeof(Flow), cmp_flow);
    if (!grow((void **)&g_tmp, &g_cap_tmp, n + 1, sizeof(float))) return 0;
    for (m = 0; i < n; i = j) {
        for (j = i; j < n && g_fl[j].g == g_fl[i].g; j++) g_tmp[j - i] = g_fl[j].dx;
        qsort(g_tmp, j - i, sizeof(float), cmp_f); mx = g_tmp[(j - i) / 2];
        for (k = i; k < j; k++) g_tmp[k - i] = g_fl[k].dy;
        qsort(g_tmp, j - i, sizeof(float), cmp_f); my = g_tmp[(j - i) / 2];
        for (agree = 0, k = i; k < j; k++) agree += fabsf(g_fl[k].dx - mx) < tol && fabsf(g_fl[k].dy - my) < tol;
        g_fl[m].g = g_fl[i].g; g_fl[m].dx = mx; g_fl[m].dy = my;
        g_fl[m++].coherent = j - i >= 8 && agree >= COHERENT * (j - i);
    }
    return m;
}
static const Flow *get_flow(int m, u32 g) {
    int lo = 0, hi = m - 1, mid;
    while (lo <= hi) { mid = (lo + hi) / 2; if (g_fl[mid].g == g) return &g_fl[mid]; if (g_fl[mid].g < g) lo = mid + 1; else hi = mid - 1; }
    return NULL;
}

/* Cracks: neighbouring primitives that share a corner can get different decisions (a 3D effect moving on
   its own, a shrinking iris wipe whose wedges only partly match). Vertices at the same spot in N (x, y, z)
   all get the average move of the best-supported ones: camera-confirmed or unchanged > other matches >
   unconfirmed camera move > no match. One wrong match can't drag confirmed static geometry. */
typedef struct { u32 x, y, z; int i; } VKey;
static VKey *g_vk; static u8 *g_vconf; static int g_cap_vk, g_cap_vc;
static int cmp_vk(const void *a, const void *b) {
    const VKey *p = a, *q = b;
    return p->x != q->x ? (p->x < q->x ? -1 : 1) : p->y != q->y ? (p->y < q->y ? -1 : 1) : p->z != q->z ? (p->z < q->z ? -1 : 1) : 0;
}
static void weld(const Frame *N, Vtx *out, Stats *s) {
    int a, b, c, n, i, differ, top;
    float mx, my;
    for (i = 0; i < N->nv; i++) {
        g_vk[i].x = *(const u32 *)&N->v[i].x; g_vk[i].y = *(const u32 *)&N->v[i].y; g_vk[i].z = *(const u32 *)&N->v[i].z; g_vk[i].i = i;
    }
    qsort(g_vk, N->nv, sizeof(VKey), cmp_vk);
    for (a = 0; a < N->nv; a = b) {
        for (b = a + 1; b < N->nv && !cmp_vk(&g_vk[a], &g_vk[b]); b++);
        if (b - a < 2) continue;
        for (top = 0, c = a; c < b; c++) if (g_vconf[g_vk[c].i] > top) top = g_vconf[g_vk[c].i];
        for (mx = my = 0, n = 0, c = a; top && c < b; c++) {
            i = g_vk[c].i;
            if (g_vconf[i] == top) { mx += out[i].x - N->v[i].x; my += out[i].y - N->v[i].y; n++; }
        }
        if (!n) continue;
        mx /= n; my /= n;
#ifdef FPS_TEST
        if (getenv("FPS_WELD")) for (c = a; c < b; c++) {
            i = g_vk[c].i;
            printf("  weld grp %5d at (%7.1f %7.1f) z %.6f conf %d moved (%6.2f %6.2f)\n", a, N->v[i].x, N->v[i].y, N->v[i].z,
                   g_vconf[i], out[i].x - N->v[i].x, out[i].y - N->v[i].y);
        }
#endif
        for (differ = 0, c = a; c < b; c++) {
            i = g_vk[c].i;
            if (fabsf(out[i].x - N->v[i].x - mx) > 0.05f || fabsf(out[i].y - N->v[i].y - my) > 0.05f) differ = 1;
            out[i].x = N->v[i].x + mx; out[i].y = N->v[i].y + my;
        }
        s->welded += differ;
    }
}

/* out = N's vertices moved a fraction t of the way back toward frame P. 1 = in-between frame made. */
static int fps_mid(const Frame *P, const Frame *N, Vtx *out, float t, Stats *s) {
    float Mp[9], Kp[3], Mm[9], Km[3], Rm[9], Tm[3], v[3], w[3], dr = 0, nr = 0, dt, px1 = N->sx;
    int i, k, cam, matched = 0, nfl = 0, j, pass, nsmp = 0;
    memcpy(out, N->v, (size_t)N->nv * sizeof(Vtx));
    s->frames++;
    if (!P->valid || !N->valid || N->counter != P->counter + 1) { s->skip_seq++; return 0; }
    if (N->vsync_n != 2 || P->vsync_n != 2 || N->flags != P->flags || N->H != P->H || N->ofx != P->ofx ||
        N->ofy != P->ofy || N->sx != P->sx || N->sy != P->sy || N->zs != P->zs) { s->skip_cut++; return 0; }
    if (!grow((void **)&g_kind, &g_cap_k, N->np + 1, 1) || !grow((void **)&g_mj, &g_cap_j, N->np + 1, sizeof(int)) ||
        !grow((void **)&g_fl, &g_cap_fl, N->np + 1, sizeof(Flow)) || !grow((void **)&g_vk, &g_cap_vk, N->nv + 1, sizeof(VKey)) ||
        !grow((void **)&g_vconf, &g_cap_vc, N->nv + 1, 1) || !grow((void **)&g_smp, &g_cap_smp, N->np + 1, sizeof(Smp)) ||
        !grow((void **)&g_gm, &g_cap_gm, N->np + 1, sizeof(Smp)) || !grow((void **)&g_uf, &g_cap_uf, N->np + 1, sizeof(int)) ||
        !grow((void **)&g_root, &g_cap_root, N->np + 1, sizeof(int)) || !grow((void **)&g_res, &g_cap_res, N->np + 1, sizeof(int)) || !grow((void **)&g_med, &g_cap_med, 2 * N->np + 2, sizeof(float))) return 0;
    cam = N->cam && P->cam;
    if (cam) {
        for (i = 0; i < 9; i++) { dr += fabsf(N->R[i] - P->R[i]); nr += fabsf(N->R[i]); }
        dt = sqrtf((N->T[0] - P->T[0]) * (N->T[0] - P->T[0]) + (N->T[1] - P->T[1]) * (N->T[1] - P->T[1]) +
                   (N->T[2] - P->T[2]) * (N->T[2] - P->T[2]));
        if (dr > CUT_ROT * nr || dt > CUT_TRANS) { s->skip_cut++; return 0; }
        for (i = 0; i < 9; i++) Rm[i] = N->R[i] + t * (P->R[i] - N->R[i]);
        for (i = 0; i < 3; i++) Tm[i] = N->T[i] + t * (P->T[i] - N->T[i]);
        cam_map(N, P->R, P->T, Mp, Kp);
        cam_map(N, Rm, Tm, Mm, Km);
    }
    /* pass 0: flat primitives that didn't change at all claim their twin in P first */
    if (!grow((void **)&g_used, &g_cap_used, P->np + 1, 1)) return 0;
    memset(g_used, 0, P->np); g_skip_used = 0;
    for (k = 0; k < N->np; k++) {
        const Prim *q = &N->p[k];
        float d1, d2;
        g_kind[k] = 0; g_mj[k] = -1;
        if (q->depth && cam) continue;
        j = find(P, q, 0, q->cx, q->cy, &d1, &d2);
        if (j >= 0 && d1 < 0.01f && !g_used[j]) { g_kind[k] = K_STILL; g_used[j] = 1; }
    }
    g_skip_used = 1;
    /* pass 1: unambiguous matches; 3D primitives first, they give the camera motion under billboards */
    for (pass = 0; pass < 2; pass++) for (k = 0; k < N->np; k++) {
        const Prim *q = &N->p[k];
        float d1, d2, px = 0, py = 0;
        int ok = 1;
        if ((q->depth && cam) != (pass == 0) || g_kind[k] == K_STILL) continue;
        g_mj[k] = -1;
        if (q->depth && cam) {
            for (i = 0; i < q->n; i++) {                       /* where camera P would have drawn it */
                unproject(N, &N->v[q->v0 + i], v); xform(Mp, Kp, v, w);
                if (w[2] < NEAR_Z) { ok = 0; break; }
                px += (w[0] * N->H / w[2] + N->ofx) * N->sx; py += (w[1] * N->H / w[2] + N->ofy) * N->sy;
            }
            j = ok ? find(P, q, 0, px / q->n, py / q->n, &d1, &d2) : -1;
            if (j >= 0 && d1 < TOL_STATIC * px1 && UNIQUE(d1, d2, px1)) {
                g_kind[k] = K_CAM;
                g_smp[nsmp].x = q->cx; g_smp[nsmp].y = q->cy; g_smp[nsmp].dx = px / q->n - q->cx; g_smp[nsmp++].dy = py / q->n - q->cy;
            } else if (j >= 0 && UNIQUE(d1, d2, px1) && hypotf(P->p[j].cx - q->cx, P->p[j].cy - q->cy) < TOL_MOVE * px1) {
                g_kind[k] = K_MOVED; g_mj[k] = j;
            } else g_kind[k] = K_CAM_ONLY;
            continue;
        }
        j = find(P, q, 0, q->cx, q->cy, &d1, &d2);
        if (j >= 0 && d1 < 0.01f) { g_kind[k] = K_STILL; continue; }
        {   /* same texture, same size, same spot, different UVs/colour: content changed in place (digits) */
            float e1, e2; int l = find(P, q, 1, q->cx, q->cy, &e1, &e2);
            if (l >= 0 && e1 < 0.25f * px1 && fabsf(P->p[l].w - q->w) < 0.5f * px1 && fabsf(P->p[l].h - q->h) < 0.5f * px1) {
                g_kind[k] = K_INPLACE; continue;
            }
        }
        if (q->bill && nsmp && ground(nsmp, q->cx, q->cy + q->h * 0.5f, GROUND_R * px1, &g_gm[k].dx, &g_gm[k].dy)) {
            /* sprite in the 3D scene: its twin right where the ground under its feet went (standing still in
               the world), else its twin near its own spot (walking, or following the camera). Identical sprites
               in a line (a running party's shadows) fail the uniqueness test here instead of swapping places. */
            j = find(P, q, 0, q->cx + g_gm[k].dx, q->cy + g_gm[k].dy, &d1, &d2);
            if (j >= 0 && d1 < 2 * TOL_STATIC * px1 && UNIQUE(d1, d2, px1)) { g_kind[k] = K_FLAT; g_mj[k] = j; continue; }
            j = find(P, q, 0, q->cx, q->cy, &d1, &d2);
            if (j >= 0 && d1 < TOL_BILL * px1 && UNIQUE(d1, d2, px1)) { g_kind[k] = K_FLAT; g_mj[k] = j; }
            else g_kind[k] = K_BILL;                               /* animation frame changed: pass 3 */
            continue;
        }
        if (j >= 0 && d1 < TOL_MOVE * px1 && UNIQUE(d1, d2, px1)) {
            g_kind[k] = K_FLAT; g_mj[k] = j;
            g_fl[nfl].g = q->lkey; g_fl[nfl].dx = P->p[j].cx - q->cx; g_fl[nfl].dy = P->p[j].cy - q->cy; nfl++;
        } else g_kind[k] = K_AMBIG;
    }
    g_nsmp = nsmp;
    nfl = make_flow(nfl, 2 * px1);
    /* pass 2: flat primitives that disagree with their layer or had no clear match: search where their
       texture group moved, take the layer's motion, or (sprite animation) a same-size sprite nearby */
    for (k = 0; k < N->np; k++) {
        const Prim *q = &N->p[k];
        const Flow *f = 0;
        float d1, d2;
        if (g_kind[k] == K_FLAT && (f = get_flow(nfl, q->lkey)) != 0 && f->coherent &&
            hypotf(P->p[g_mj[k]].cx - q->cx - f->dx, P->p[g_mj[k]].cy - q->cy - f->dy) >= 1.5f * px1) {
            g_kind[k] = K_FLOW; continue;
        }
        if (g_kind[k] != K_AMBIG) continue;
        if ((f = get_flow(nfl, q->lkey)) != 0) {
            j = find(P, q, 0, q->cx + f->dx, q->cy + f->dy, &d1, &d2);
            if (j >= 0 && d1 < 2 * px1 && UNIQUE(d1, d2, px1)) { g_kind[k] = K_FLAT; g_mj[k] = j; continue; }
            if (f->coherent) { g_kind[k] = K_FLOW; continue; }
        }
        j = find(P, q, 1, q->cx, q->cy, &d1, &d2);              /* new UVs: same-size sprite of that texture nearby */
        if (j >= 0 && d1 < TOL_LOOSE * px1 && UNIQUE(d1, d2, px1) &&
            fabsf(P->p[j].w - q->w) < 0.5f * px1 && fabsf(P->p[j].h - q->h) < 0.5f * px1) { g_kind[k] = K_SHIFT; g_mj[k] = j; }
        else g_kind[k] = K_NONE;
    }
    /* pass 3: sprite characters. A character = billboard parts sharing corner vertices (stacked head, body,
       legs); it moves as one: by the median motion of its parts that matched (exact twin, same-size previous
       frame, unchanged), else by what the previous frame shows for the whole character (its texture still at
       its feet -> it follows the camera, the player; where the ground went -> it stands in the world), else
       like the character overlapping it most that has a result (a body and the separate shadow at its feet),
       else not at all. Parts of one character never get different motions, so welding has nothing to tear. */
    for (k = 0; k < N->np; k++) {                              /* animation frame changed, same size nearby */
        const Prim *q = &N->p[k];
        float d1, d2;
        if (g_kind[k] != K_BILL) continue;
        j = find(P, q, 1, q->cx, q->cy, &d1, &d2);
        if (j >= 0 && d1 < TOL_BILL * px1 && UNIQUE(d1, d2, px1) &&
            fabsf(P->p[j].w - q->w) < 0.5f * px1 && fabsf(P->p[j].h - q->h) < 0.5f * px1) { g_kind[k] = K_SHIFT; g_mj[k] = j; }
    }
    {
        int nb = 0, a, b, c, n, stay, gnd;
        for (k = 0; k < N->np; k++) g_uf[k] = k;
        for (k = 0; k < N->np; k++) if (N->p[k].bill) for (i = 0; i < N->p[k].n; i++) {   /* shared corners -> one character */
            const Vtx *v = &N->v[N->p[k].v0 + i];
            g_vk[nb].x = *(const u32 *)&v->x; g_vk[nb].y = *(const u32 *)&v->y; g_vk[nb].z = 0; g_vk[nb++].i = k;
        }
        qsort(g_vk, nb, sizeof(VKey), cmp_vk);
        for (a = 1; a < nb; a++) if (!cmp_vk(&g_vk[a - 1], &g_vk[a])) {
            int r1 = uf_find(g_vk[a - 1].i), r2 = uf_find(g_vk[a].i);
            if (r1 != r2) g_uf[r1] = r2;
        }
        for (k = 0; k < N->np; k++) g_root[k] = N->p[k].bill ? uf_find(k) : -1;
        for (k = 0; k < N->np; k++) {                          /* result per character, kept at its root */
            float fx = 0, fy = -1e30f, gx = 0, gy = 0;
            int has_g;
            if (g_root[k] != k) continue;
            for (n = 0, b = 0; b < N->np; b++) {               /* motions of the parts with evidence */
                if (g_root[b] != k) continue;
                if (g_kind[b] == K_FLAT || g_kind[b] == K_SHIFT) {
                    g_med[n] = P->p[g_mj[b]].cx - N->p[b].cx; g_med[N->np + n] = P->p[g_mj[b]].cy - N->p[b].cy; n++;
                } else if (g_kind[b] == K_STILL || g_kind[b] == K_INPLACE) { g_med[n] = 0; g_med[N->np + n] = 0; n++; }
                if (N->p[b].cy + N->p[b].h * 0.5f > fy) { fy = N->p[b].cy + N->p[b].h * 0.5f; fx = N->p[b].cx; }
            }
            if (n) {
                qsort(g_med, n, sizeof(float), cmp_f); qsort(g_med + N->np, n, sizeof(float), cmp_f);
                gx = g_med[n / 2]; gy = g_med[N->np + n / 2]; g_res[k] = K_GROUND;
            } else {                                            /* no part matched: ask the previous frame */
                has_g = nsmp && ground(nsmp, fx, fy, GROUND_R * px1, &gx, &gy);
                for (stay = gnd = 0, b = 0; b < N->np; b++) {
                    const Prim *q = &N->p[b]; float ds = 1e30f, dg = 1e30f, dd, qx = q->cx, qy = q->cy + q->h * 0.5f;
                    if (g_root[b] != k) continue;
                    for (c = P->lhead[q->lkey & ((1 << HBITS) - 1)]; c >= 0; c = P->p[c].lnext) {
                        const Prim *o = &P->p[c];
                        if (o->lkey != q->lkey || !o->bill) continue;
                        dd = hypotf(o->cx - qx, o->cy + o->h * 0.5f - qy); if (dd < ds) ds = dd;
                        if (has_g) { dd = hypotf(o->cx - qx - gx, o->cy + o->h * 0.5f - qy - gy); if (dd < dg) dg = dd; }
                    }
                    if (fminf(ds, dg) < 6 * px1) { if (ds <= dg) stay++; else gnd++; }
                }
                if (gnd > stay) g_res[k] = K_GROUND;
                else if (stay) { g_res[k] = K_GROUND; gx = gy = 0; }
                else g_res[k] = K_NONE;
            }
            g_gm[k].dx = gx; g_gm[k].dy = gy;
        }
        for (k = 0; k < N->np; k++) {                          /* no result: like the character overlapping it most */
            float best = 0, ar;
            int from = -1;
            if (g_root[k] != k || g_res[k] != K_NONE) continue;
            for (a = 0; a < N->np; a++) if (g_root[a] == k) for (b = 0; b < N->np; b++) {
                const Prim *p1 = &N->p[a], *p2 = &N->p[b];
                float ox, oy;
                if (g_root[b] < 0 || g_root[b] == k || g_res[g_root[b]] == K_NONE) continue;
                ox = fminf(p1->cx + p1->w * 0.5f, p2->cx + p2->w * 0.5f) - fmaxf(p1->cx - p1->w * 0.5f, p2->cx - p2->w * 0.5f);
                oy = fminf(p1->cy + p1->h * 0.5f, p2->cy + p2->h * 0.5f) - fmaxf(p1->cy - p1->h * 0.5f, p2->cy - p2->h * 0.5f);
                if (ox <= 0 || oy <= 0) continue;
                ar = ox * oy / fminf(p1->w * p1->h, p2->w * p2->h);
                if (ar >= 0.5f && ar > best) { best = ar; from = g_root[b]; }
            }
            if (from >= 0) { g_res[k] = K_SHADOWED; g_gm[k] = g_gm[from]; }
        }
        for (b = 0; b < N->np; b++) if ((k = g_root[b]) >= 0) {
            float gx = g_gm[k].dx, gy = g_gm[k].dy;
            if ((g_kind[b] == K_STILL || g_kind[b] == K_INPLACE) && gx == 0 && gy == 0) continue;
            g_kind[b] = g_res[k] == K_NONE ? K_NONE : K_GROUND;
            if (b != k) g_gm[b] = g_gm[k];
        }
    }
    /* UI quads that jumped (a menu list scrolling by a row, text re-flowing) are not blended: the game drew no
       motion in between, and a half-row blend splits rows into letters that moved and letters that didn't */
    for (k = 0; k < N->np; k++) {
        const Prim *q = &N->p[k];
        float mx, my;
        if (!q->ui) continue;
        if (g_kind[k] == K_FLAT || g_kind[k] == K_SHIFT) { mx = P->p[g_mj[k]].cx - q->cx; my = P->p[g_mj[k]].cy - q->cy; }
        else if (g_kind[k] == K_FLOW) { const Flow *f = get_flow(nfl, q->lkey); mx = f->dx; my = f->dy; }
        else continue;
        if (hypotf(mx, my) >= UI_JUMP * px1) g_kind[k] = K_INPLACE;
    }
    /* apply */
    for (k = 0; k < N->np; k++) {
        const Prim *q = &N->p[k];
        CAT(k, " cmofsilng"[g_kind[k] == K_CAM ? 1 : g_kind[k] == K_CAM_ONLY ? 3 : g_kind[k] == K_MOVED ? 2 :
                            g_kind[k] == K_FLAT ? 4 : g_kind[k] == K_STILL ? 5 : g_kind[k] == K_INPLACE ? 6 :
                            g_kind[k] == K_SHIFT || g_kind[k] == K_FLOW ? 7 : g_kind[k] == K_GROUND ? 9 : 8]);
        switch (g_kind[k]) {
        case K_CAM: s->cam_static++; matched++; /* fall through */
        case K_CAM_ONLY:
            if (g_kind[k] == K_CAM_ONLY) s->cam_only++;
            for (i = 0; i < q->n; i++) {
                const Vtx *a = &N->v[q->v0 + i]; Vtx *o = &out[q->v0 + i];
                unproject(N, a, v); xform(Mm, Km, v, w);
                if (w[2] < NEAR_Z) continue;
                o->x = (w[0] * N->H / w[2] + N->ofx) * N->sx; o->y = (w[1] * N->H / w[2] + N->ofy) * N->sy;
                o->z = w[2] / N->zs; o->rhw = a->rhw * v[2] / w[2];
            }
            break;
        case K_MOVED: s->moved++; matched++; lerp_prim(N, P, q, &P->p[g_mj[k]], out, t); break;
        case K_FLAT: s->flat_moved++; matched++; lerp_prim(N, P, q, &P->p[g_mj[k]], out, t); break;
        case K_STILL: case K_INPLACE: s->flat_still++; matched++; break;
        case K_SHIFT:
            s->flat_shift++; matched++;
            for (i = 0; i < q->n; i++) {
                out[q->v0 + i].x += t * (P->p[g_mj[k]].cx - q->cx); out[q->v0 + i].y += t * (P->p[g_mj[k]].cy - q->cy);
            }
            break;
        case K_GROUND:
            s->flat_shift++; matched++;
            for (i = 0; i < q->n; i++) { out[q->v0 + i].x += t * g_gm[k].dx; out[q->v0 + i].y += t * g_gm[k].dy; }
            break;
        case K_FLOW: {
            const Flow *f = get_flow(nfl, q->lkey);
            s->flat_shift++; matched++;
            for (i = 0; i < q->n; i++) { out[q->v0 + i].x += t * f->dx; out[q->v0 + i].y += t * f->dy; }
            break;
        }
        default: s->flat_none++;
        }
        for (i = 0; i < q->n; i++)       /* how well supported this primitive's move is, for welding */
            g_vconf[q->v0 + i] = g_kind[k] == K_CAM || g_kind[k] == K_STILL || g_kind[k] == K_INPLACE ? 3 :
                                 g_kind[k] == K_CAM_ONLY ? 1 : g_kind[k] == K_NONE ? 0 : 2;
    }
    g_skip_used = 0;
    if (N->np > 32 && matched < MIN_MATCH * N->np) { memcpy(out, N->v, (size_t)N->nv * sizeof(Vtx)); s->skip_match++; return 0; }
    weld(N, out, s);
    s->mid++;
    return 1;
}

#ifndef FPS_TEST
/* ---------------------------------------------------------------- in the game */
/* Pacing: the game's limiter (0x60C550) waits on GetTickCount for n x [ms table] per frame, and the table
 * (16,17,17,17) steps once a second, so the game alternates 32 ms and 34 ms frames for whole seconds. With
 * the table at 16 the limiter never holds a frame too long; the game's present is then paced here to
 * exactly n vblanks (QueryPerformanceCounter) and the in-between frame goes out halfway. */
#define VBLANK_MS (1000.0 / 60)
#define MS_TABLE  0x952998

static Frame g_fr[2]; static int g_cur;
static Vtx *g_mid; static int g_cap_mid;
static Stats g_st;
static int g_on = 1, g_key_prev, g_log, g_off_n, g_late_n, g_dump, g_dump_key, g_dump_set;
static LARGE_INTEGER g_qf;
static double g_sched, g_frame = 2 * VBLANK_MS, g_t_log, g_off_sum, g_off_max, g_late;   /* ms */
static char g_logpath[MAX_PATH], g_dumpdir[MAX_PATH];

/* debug ([fps60] dump=1): the last DUMP_N frames are kept (the part of memory capture() reads); Pause writes
   them in bof4_diag's format (.psxseg + .data image, zero elsewhere, plus a header line) for fps60_test */
#define DUMP_N   32
#define WIN_LO   0x96DA70
#define WIN_HI   0xBBFAC8
static u8 *g_ring[DUMP_N]; static Frame g_ring_hdr[DUMP_N]; static int g_ring_pos, g_ring_n;
static void ring_add(const Frame *f) {
    int i = g_ring_pos;
    if (!g_ring[i] && !(g_ring[i] = malloc(WIN_HI - WIN_LO))) return;
    memcpy(g_ring[i], (void *)WIN_LO, WIN_HI - WIN_LO);
    g_ring_hdr[i] = *f;
    g_ring_pos = (i + 1) % DUMP_N; if (g_ring_n < DUMP_N) g_ring_n++;
}
static void ring_write(void) {
    static u8 *zero; char path[MAX_PATH]; FILE *o; int k;
    if (!zero && !(zero = calloc(1, 0x3A4000))) return;
    CreateDirectoryA(g_dumpdir, NULL);
    for (k = 0; k < g_ring_n; k++) {
        int i = (g_ring_pos - g_ring_n + k + DUMP_N) % DUMP_N; const Frame *f = &g_ring_hdr[i];
        sprintf(path, "%s\\s%02d_f%d_trace.txt", g_dumpdir, g_dump_set, k);
        if ((o = fopen(path, "w")) != 0) {
            fprintf(o, "frame %u t 0 ms n %u flags %08X H %d OFX %d OFY %d verts %d cmds 0 ot 0 scale %f %f\n", f->counter,
                    f->vsync_n, f->flags, (int)f->H, (int)f->ofx, (int)f->ofy, f->nv, f->sx, f->sy);
            fclose(o);
        }
        sprintf(path, "%s\\s%02d_f%d_ram.bin", g_dumpdir, g_dump_set, k);
        if ((o = fopen(path, "wb")) != 0) {
            fwrite(zero, 1, 0x216000, o);                                     /* .psxseg: not needed */
            fwrite(zero, 1, WIN_LO - 0x8D4000, o);
            fwrite(g_ring[i], 1, WIN_HI - WIN_LO, o);
            fwrite(zero, 1, 0x8D4000 + 0x3A4000 - WIN_HI, o);
            fclose(o);
        }
    }
}

static double now_ms(void) { LARGE_INTEGER t; QueryPerformanceCounter(&t); return t.QuadPart * 1000.0 / g_qf.QuadPart; }
static void wait_until(double t) { double n; while ((n = now_ms()) < t && t - n < 200) SwitchToThread(); }

static void init(void) {
    char ini[MAX_PATH], *p; int i;
    if (g_qf.QuadPart) return;
    QueryPerformanceFrequency(&g_qf); g_t_log = now_ms();
    if (MEM(u8, FEATURES) & 1) for (i = 0; i < 4; i++) MEM(u32, MS_TABLE + 4 * i) = 16;
    GetModuleFileNameA(NULL, ini, MAX_PATH);
    if ((p = strrchr(ini, '\\')) != 0) {
        strcpy(p + 1, "BOF4_reverb.ini");
        g_log = GetPrivateProfileIntA("fps60", "log", 0, ini);
        g_dump = GetPrivateProfileIntA("fps60", "dump", 0, ini);
        strcpy(g_logpath, ini); strcpy(g_logpath + (p + 1 - ini), "BOF4_fps60.log");
        strcpy(g_dumpdir, ini); strcpy(g_dumpdir + (p + 1 - ini), "fps60_dump");
    }
}

static void log_stats(void) {
    double now = now_ms(); FILE *f;
    if (!g_log || now - g_t_log < 1000) return;
    g_t_log = now;
    if ((f = fopen(g_logpath, "a")) != 0) {
        fprintf(f, "%s frames %d mid %d | skip seq %d cut %d match %d | prims: cam %ld moved %ld cam-only %ld flat moved %ld "
                   "still %ld shift %ld none %ld welded %ld | frame %.1f ms, in-between at +%.1f (max %.1f), late %d (%.1f ms)\n",
                g_on ? "on " : "off", g_st.frames, g_st.mid, g_st.skip_seq, g_st.skip_cut, g_st.skip_match, g_st.cam_static,
                g_st.moved, g_st.cam_only, g_st.flat_moved, g_st.flat_still, g_st.flat_shift, g_st.flat_none, g_st.welded, g_frame,
                g_off_n ? g_off_sum / g_off_n : 0, g_off_max, g_late_n, g_late_n ? g_late / g_late_n : 0);
        fclose(f);
    }
    memset(&g_st, 0, sizeof g_st); g_off_sum = g_off_max = g_late = 0; g_off_n = g_late_n = 0;
}

/* PutDrawEnv's present (0x410A47): every n vblanks, on a steady schedule */
__declspec(dllexport) int __cdecl bof4_fps_present(int a) {
    u32 n; double t;
    init();
    n = MEM(u32, VSYNC_N);
    if (n < 1) n = 1; if (n > 8) n = 8;
    g_frame = n * VBLANK_MS;
    t = now_ms();
    if (g_sched > 0 && t < g_sched + g_frame) { wait_until(g_sched + g_frame); g_sched += g_frame; }
    else {                                              /* late (slow frame, loading): restart the schedule */
        if (g_sched > 0) { g_late += t - g_sched - g_frame; g_late_n++; }
        g_sched = t;
    }
    return ((int(__cdecl *)(int))PRESENT)(a);
}

/* the screen pass of the frame flush (0x40AC03); also the widescreen option's, with or without 60 fps */
void wide_exec(void *surf, int *rect, int flag);             /* widescreen.c */
static void exec(void *surf, void *rect, int flag) {
    if (MEM(u8, FEATURES) & 2) wide_exec(surf, rect, flag);
    else ((void (__cdecl *)(void *, void *, int))EXEC)(surf, rect, flag);
}
__declspec(dllexport) void __cdecl bof4_fps_screen(void *surf, void *rect, int flag) {
    Frame *N = &g_fr[g_cur], *P = &g_fr[g_cur ^ 1];
    int key = GetAsyncKeyState(VK_SCROLL) & 0x8000;          /* Scroll Lock: in-between frames off/on */
    if (!(MEM(u8, FEATURES) & 1)) { exec(surf, rect, flag); return; }
    init();
    if (key && !g_key_prev) g_on ^= 1;
    g_key_prev = key;
    capture(N);
    if (g_dump) {
        int dk = GetAsyncKeyState(VK_PAUSE) & 0x8000;
        ring_add(N);
        if (dk && !g_dump_key) {
            char path[MAX_PATH];                                /* continue after earlier sessions' sets */
            do { g_dump_set++; sprintf(path, "%s\\s%02d_f0_trace.txt", g_dumpdir, g_dump_set); }
            while (g_dump_set < 99 && GetFileAttributesA(path) != INVALID_FILE_ATTRIBUTES);
            ring_write(); g_ring_n = 0;
        }
        g_dump_key = dk;
    }
    if (N->valid && g_on && grow((void **)&g_mid, &g_cap_mid, N->nv + 1, sizeof(Vtx)) && fps_mid(P, N, g_mid, 0.5f, &g_st)) {
        double o;
        memcpy((void *)VTX_BASE, g_mid, (size_t)N->nv * sizeof(Vtx));
        exec(surf, rect, flag);
        if (g_sched > 0) wait_until(g_sched + g_frame * 0.5);
        ((int(__cdecl *)(int))PRESENT)(0);
        o = now_ms() - g_sched; g_off_sum += o; g_off_n++; if (o > g_off_max) g_off_max = o;
        memcpy((void *)VTX_BASE, N->v, (size_t)N->nv * sizeof(Vtx));
    }
    exec(surf, rect, flag);
    g_cur ^= 1;
    log_stats();
}

#else
/* ---------------------------------------------------------------- offline: fps60_test <dir> <set> <fA> <fB> [t] [out.bin] */
static u8 *load(const char *path) {
    FILE *f = fopen(path, "rb"); u8 *b; long n;
    if (!f) { printf("cannot open %s\n", path); exit(1); }
    fseek(f, 0, SEEK_END); n = ftell(f); fseek(f, 0, SEEK_SET);
    b = malloc(n); fread(b, 1, n, f); fclose(f); return b;
}
int main(int argc, char **argv) {
    static Frame A, B; Stats s = {0}; char p[512]; Vtx *out; int r, i; float t = argc > 5 ? (float)atof(argv[5]) : 0.5f;
    double sum = 0; int cnt = 0, near1 = 0;
    if (argc < 5) { printf("fps60_test <diag dir> <set> <fA> <fB> [t] [out.bin]\n"); return 1; }
    sprintf(p, "%s\\s%s_f%s_ram.bin", argv[1], argv[2], argv[3]); g_ram = load(p); capture(&A);
    sprintf(p, "%s\\s%s_f%s_ram.bin", argv[1], argv[2], argv[4]); g_ram = load(p); capture(&B);
    out = malloc((B.nv + 1) * sizeof(Vtx));
    r = fps_mid(&A, &B, out, t, &s);
    printf("set %s f%s->f%s t=%.2f: %s  prims %d (A %d)  cam %ld moved %ld cam-only %ld | flat moved %ld still %ld shift %ld none %ld welded %ld | skip seq %d cut %d match %d\n",
           argv[2], argv[3], argv[4], t, r ? "MID" : "no mid", B.np, A.np, s.cam_static, s.moved, s.cam_only,
           s.flat_moved, s.flat_still, s.flat_shift, s.flat_none, s.welded, s.skip_seq, s.skip_cut, s.skip_match);
    if (r && t == 1.0f) {                 /* at t=1 every vertex should land on a vertex of frame A */
        for (i = 0; i < B.nv; i++) {
            int j; float bd = 1e30f;
            for (j = 0; j < A.nv; j++) { float dx = out[i].x - A.v[j].x, dy = out[i].y - A.v[j].y, d = dx * dx + dy * dy; if (d < bd) bd = d; }
            bd = sqrtf(bd); sum += bd; cnt++; if (bd < 1) near1++;
        }
        printf("  t=1 vs frame A: mean nearest %.2f px, <1px %.1f%%\n", sum / cnt, 100.0 * near1 / cnt);
    }
    if (getenv("FPS_BILL")) for (i = 0; i < B.np; i++) if (B.p[i].bill) {    /* billboards: decision and motion */
        const Prim *q = &B.p[i]; float mx = 0, my = 0;
        int v; for (v = 0; v < q->n; v++) { mx += out[q->v0 + v].x - B.v[q->v0 + v].x; my += out[q->v0 + v].y - B.v[q->v0 + v].y; }
        { float fx = q->cx, fy = q->cy + q->h * 0.5f, bd = 1e30f, gx = 0, gy = 0; int b;
          for (b = 0; b < g_nsmp; b++) { float dd = hypotf(g_smp[b].x - fx, g_smp[b].y - fy); if (dd < bd) { bd = dd; gx = g_smp[b].dx * t; gy = g_smp[b].dy * t; } }
          printf("  bill %4d %c at (%7.1f %7.1f) %3.0fx%-3.0f  mid moved (%6.2f %6.2f)  ground (%6.2f %6.2f) %4.0f px away  char %d\n",
                 i, g_cat[i], q->cx, q->cy, q->w, q->h, mx / q->n, my / q->n, gx, gy, bd, r ? g_root[i] : -1); }
    }
    if (getenv("FPS_CAT")) for (i = 0; i < B.np; i++) if (strchr(getenv("FPS_CAT"), g_cat[i])) {
        const Prim *q = &B.p[i]; int v;
        printf("  %c prim %4d n %d c (%7.1f %7.1f) z", g_cat[i], i, q->n, q->cx, q->cy);
        for (v = 0; v < q->n; v++) printf(" %.5f", B.v[q->v0 + v].z * B.zs);
        printf("  xy"); for (v = 0; v < q->n; v++) printf(" (%.0f,%.0f)", B.v[q->v0 + v].x, B.v[q->v0 + v].y);
        printf("\n");
    }
    if (argc > 6) { FILE *f = fopen(argv[6], "wb"); fwrite(out, sizeof(Vtx), B.nv, f); fclose(f); }
    return 0;
}
#endif
