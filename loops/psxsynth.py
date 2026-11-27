# Offline PS1 music renderer: a BGM song (SEP sequence) played with a VAB, the way the SPU would, at 44.1 kHz.
# Dry (no reverb: the "reverb" option adds the SPU reverb to all music at runtime).
#   ADPCM samples with their loop flags; pitch = 44100 * 2^((key - centre + fine/128 + bend) / 12) (the PC port's
#   convention for the same VAB data), capped at 4x; ADSR per psx-spx; libsnd volume (velocity x tone x program x
#   channel) and pan; 4-point Gaussian-like interpolation.
#   python psxsynth.py <seq BGM n> <song> <vab BGM n> <out.wav> [passes]
import os, struct, sys, wave
import numpy as np
import sep, config

SR = 44100
FINE_SIGN = 1                                   # tone fine tune (1/128 semitone): added to the pitch
FILT =[(0, 0), (60, 0), (115, -52), (98, -55), (122, -60)]

def emi_parts(n):
    """{kind: data} of BGMnnn.EMI: 'pBAV' VAB header, 'pQES' sequences, 0 VAB body (samples)"""
    d = open(os.path.join(config.PS1_BGM, f"BGM{n:03d}.EMI"), "rb").read()
    out, off = {}, 0x800
    for i in range(struct.unpack_from("<I", d)[0]):
        size, _, kind, _ = struct.unpack_from("<4I", d, 16 + 16 * i)
        out.setdefault(kind, d[off:off + size]); off = (off + size + 0x7FF) & ~0x7FF
    return out

def vag(b):
    """decoded samples (float), loop start (None: one-shot)"""
    s1 = s2 = 0; out = []; loop = None
    for i in range(0, len(b) - 15, 16):
        sh, flt, fl = b[i] & 15, b[i] >> 4, b[i + 1]
        if fl & 4 and loop is None: loop = len(out)
        f0, f1 = FILT[flt] if flt < 5 else (0, 0)
        for j in range(28):
            nib = (b[i + 2 + j // 2] >> (4 * (j & 1))) & 15
            v = ((nib - 16 if nib >= 8 else nib) << 12) >> sh if sh <= 12 else 0
            v += (s1 * f0 + s2 * f1 + 32) >> 6
            v = max(-32768, min(32767, v)); out.append(v); s2, s1 = s1, v
        if fl & 1:
            if not fl & 2: loop = None
            break
    return np.array(out, np.float64) / 32768, loop

class Vab:
    def __init__(self, n):
        p = emi_parts(n); h, body = p[0x56414270], p[0]
        ps, ts, vs = struct.unpack_from("<HHH", h, 0x12)
        self.progs = [h[0x20 + i * 16:0x30 + i * 16] for i in range(128)]
        t0 = 0x20 + 0x800
        self.tones = {}
        for pr in range(ps):
            for i in range(16):
                t = h[t0 + (pr * 16 + i) * 32:t0 + (pr * 16 + i) * 32 + 32]
                vg = struct.unpack_from("<h", t, 22)[0]
                if vg <= 0: continue
                a1, a2 = struct.unpack_from("<HH", t, 16)
                self.tones.setdefault(pr, []).append(dict(mode=t[1], vol=t[2], pan=t[3], center=t[4], fine=t[5], lo=t[6],
                    hi=t[7], pbmin=t[12], pbmax=t[13], adsr1=a1, adsr2=a2, vag=vg))
        sizes = [x * 8 for x in struct.unpack_from("<256H", h, t0 + ps * 512)]
        self.samples, off = {}, 0
        for k in range(1, vs + 1):
            self.samples[k] = vag(body[off:off + sizes[k]]); off += sizes[k]

# ---- ADSR (psx-spx): level changes by `step` every `cycles` samples
def _rate(r, increase, exp, level):
    shift, s = r >> 2, (r & 3)
    step = (7 - s) if increase else (-8 + s)
    cycles = 1 << max(0, shift - 11)
    step = step << max(0, 11 - shift)
    if exp and increase and level > 0x6000: cycles *= 4
    if exp and not increase: step = step * level / 32768
    return step / cycles                        # per sample

def adsr(a1, a2, n_on, n_total):
    """envelope (0..1) for a note held n_on samples, rendered for n_total samples"""
    env = np.empty(n_total); lvl = 0.0; i = 0
    ar, aexp = (a1 >> 8) & 0x7F, a1 >> 15
    dr, sl = ((a1 >> 4) & 15) * 4, ((a1 & 15) + 1) * 0x800
    sr_, sexp, sdec = (a2 >> 6) & 0x7F, a2 >> 15, (a2 >> 14) & 1
    rr, rexp = (a2 & 31) * 4, (a2 >> 5) & 1
    phase = 0                                   # 0 attack, 1 decay, 2 sustain, 3 release
    BLK = 16                                    # update the rate every 16 samples (exact enough, fast)
    while i < n_total:
        if i >= n_on and phase < 3: phase = 3
        if phase == 0: d = _rate(ar, True, aexp, lvl)
        elif phase == 1: d = _rate(dr, False, True, lvl)
        elif phase == 2: d = _rate(sr_, not sdec, sexp, lvl)
        else: d = _rate(rr, False, rexp, lvl)
        k = min(BLK, n_total - i, (n_on - i) if phase < 3 and n_on > i else BLK)
        seg = lvl + d * np.arange(1, k + 1)
        seg = np.clip(seg, 0, 32767)
        if phase == 1 and seg[-1] <= sl: seg = np.maximum(seg, sl)
        env[i:i + k] = seg; lvl = seg[-1]; i += k
        if phase == 0 and lvl >= 32767: phase = 1
        elif phase == 1 and lvl <= sl: phase = 2
        elif phase == 3 and lvl <= 0: env[i:] = 0; break
    return env / 32767

# ---- sequence
def events(sep_data, song):
    songs = {sid: (res, tempo, data) for sid, res, tempo, data in sep.songs(sep_data)}
    res, tempo, data = songs[song]
    i, tick, status, out, tmap = 0, 0, 0, [], [(0, tempo)]
    def secs(t):
        s, pt, pv = 0.0, 0, tempo
        for mt, mv in tmap:
            if mt > t: break
            s += (mt - pt) * pv / res / 1e6; pt, pv = mt, mv
        return s + (t - pt) * pv / res / 1e6
    while i < len(data):
        dt, i = sep.vlq(data, i); tick += dt; b = data[i]
        if b & 0x80: status = b; i += 1
        if status == 0xFF:
            typ = data[i]; i += 1
            if typ == 0x2F: break
            if typ == 0x51: tmap.append((tick, int.from_bytes(data[i:i + 3], "big"))); i += 3
            else: ln, i = sep.vlq(data, i); i += ln
            continue
        hi, ch = status & 0xF0, status & 15
        if hi in (0xC0, 0xD0):
            if hi == 0xC0: out.append((secs(tick), ch, "prog", data[i], 0))
            i += 1; continue
        a, v = data[i], data[i + 1]; i += 2
        t = secs(tick)
        if hi == 0x90 and v: out.append((t, ch, "on", a, v))
        elif hi in (0x80, 0x90): out.append((t, ch, "off", a, 0))
        elif hi == 0xB0: out.append((t, ch, f"cc{a}", v, 0))
        elif hi == 0xE0: out.append((t, ch, "bend", a | v << 7, 0))
    return out, sep.loops(res, tempo, data)

def unroll(ev, ls, le, passes):
    """the event list played through the loop `passes` times (loop start/end in seconds)"""
    if ls is None or le is None: return ev
    L, out = le - ls, [e for e in ev if e[0] < le]
    for k in range(1, passes):
        out += [(e[0] + k * L,) + e[1:] for e in ev if ls <= e[0] < le]
    return sorted(out, key=lambda e: e[0])

def interp(x, pos):
    """4-tap smooth interpolation (stand-in for the SPU's Gaussian table)"""
    i = np.floor(pos).astype(np.int64); f = pos - i
    xp = np.concatenate([[0.0], x, [0.0, 0.0, 0.0]])
    # Gaussian-shaped weights for taps at -1, 0, 1, 2 (sigma ~0.75 sample, normalised)
    w = [np.exp(-((f - o) ** 2) / (2 * 0.75 ** 2)) for o in (-1, 0, 1, 2)]
    s = w[0] + w[1] + w[2] + w[3]
    return (xp[i] * w[0] + xp[i + 1] * w[1] + xp[i + 2] * w[2] + xp[i + 3] * w[3]) / s

def render(seq_n, song, vab_n, passes=2, tail=2.0, channels=None):
    vb = Vab(vab_n)
    ev, (ls, le, tot) = events(emi_parts(seq_n)[0x53455170], song)
    ev = unroll(ev, ls, le, passes)
    if channels is not None: ev = [e for e in ev if e[1] in channels or e[2] not in ("on", "off")]
    length = (ls + passes * (le - ls) if ls is not None and le is not None else tot) + tail
    N = int(length * SR); out = np.zeros((N + SR * 4, 2))
    prog, vol, pan = {}, {}, {}
    bends = {}                                  # channel -> [(time, value)]
    for t, ch, kind, a, v in ev:
        if kind == "bend": bends.setdefault(ch, []).append((t, a))
    active = {}
    def bend_curve(ch, t0, n, pbmin, pbmax):
        b = bends.get(ch)
        if not b: return np.zeros(n)
        ts = t0 + np.arange(n) / SR
        b = [x for x in b if x[0] >= t0]                # a new note starts unbent: bends move sounding notes only
        if not b: return np.zeros(n)                    # (the PC recordings: new notes 6 cents below the last bend)
        times = np.array([x[0] for x in b]); vals = np.array([x[1] for x in b], float)
        idx = np.searchsorted(times, ts, side="right") - 1
        cur = np.where(idx >= 0, vals[np.clip(idx, 0, None)], 8192.0)
        return np.where(cur >= 8192, (cur - 8192) / 8191 * pbmax, (cur - 8192) / 8192 * pbmin)
    def play(t0, t1, ch, key, velo, pr):
        for tn in vb.tones.get(pr, []):
            if not tn["lo"] <= key <= tn["hi"]: continue
            x, loop = vb.samples[tn["vag"]]
            if not len(x): continue
            n_on = int((t1 - t0) * SR) if t1 is not None else N
            n = min(N - int(t0 * SR), n_on + SR * 3)
            if n <= 0: continue
            semis = key - tn["center"] + FINE_SIGN * tn["fine"] / 128 + bend_curve(ch, t0, n, tn["pbmin"], tn["pbmax"])
            step = np.minimum(2 ** (semis / 12), 4.0)          # 44.1 kHz sample rate = pitch 0x1000
            pos = np.concatenate([[0.0], np.cumsum(step)[:-1]])
            if loop is not None and len(x) - loop > 1:
                L = len(x) - loop; pos = np.where(pos >= len(x), loop + np.mod(pos - loop, L), pos)
            else:
                n = min(n, int(np.searchsorted(pos, len(x) - 1))); pos = pos[:n]
            if n <= 0: continue
            y = interp(x, pos) * adsr(tn["adsr1"], tn["adsr2"], n_on, n)
            g = velo / 127 * tn["vol"] / 127 * vb.progs[pr][1] / 127 * (vol.get(ch, 127) / 127) ** 2   # CC7 squared (fitted)
            p = max(0, min(127, tn["pan"] + pan.get(ch, 64) - 64 + vb.progs[pr][4] - 64))
            gl, gr = (g, g * p / 63) if p < 64 else (g * (127 - p) / 63, g)
            s = int(t0 * SR); e = min(len(out), s + n)
            out[s:e, 0] += y[:e - s] * gl; out[s:e, 1] += y[:e - s] * gr
    for t, ch, kind, a, v in ev:
        if kind == "prog": prog[ch] = a
        elif kind == "cc7": vol[ch] = a
        elif kind == "cc10": pan[ch] = a
        elif kind == "on":
            if (ch, a) in active:                       # retrigger: the old note ends here
                t0, vv, pr = active.pop((ch, a)); play(t0, t, ch, a, vv, pr)
            active[(ch, a)] = (t, v, prog.get(ch, 0))
        elif kind == "off" and (ch, a) in active:
            t0, vv, pr = active.pop((ch, a)); play(t0, t, ch, a, vv, pr)
    for (ch, a), (t0, vv, pr) in active.items(): play(t0, None, ch, a, vv, pr)
    return out[:N], (ls, le)

def write_wav(path, y, gain):
    z = np.clip(y * gain * 32767, -32768, 32767).astype("<i2")
    w = wave.open(path, "wb"); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(z.tobytes()); w.close()

if __name__ == "__main__":
    seq_n, song, vab_n, path = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
    passes = int(sys.argv[5]) if len(sys.argv) > 5 else 2
    y, (ls, le) = render(seq_n, song, vab_n, passes)
    write_wav(path, y, 0.9 / (np.abs(y).max() or 1))
    print(path, f"{len(y) / SR:.1f} s, loop {ls}..{le}")
