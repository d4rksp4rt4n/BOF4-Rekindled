# Boss victory themes (option "bossvic"). On the PS1 the victory after a boss battle is the normal victory sequence
# (song 1 of the loaded music file) played with the boss music file's own instruments: BGM008 (Ryu's party,
# eastern theme) and BGM016 (Fou-Lu's party, western theme) carry different samples for every program the victory
# uses. The PC port's recordings of those two slots are copies of the normal victory recordings.
# This renders them from the PS1 disc (psxsynth), calibrated to the PC recordings of the normal versions (same
# sequence, same channels: per-channel balance and the recording's tone curve), and encodes them like the
# originals (MPEG-1 Layer III, 128 kbps CBR, 44.1 kHz stereo, no tags), intro + two passes of the loop.
# Output: build_tmp/boss_victory/BGMnnn_1.mp3 and boss_victory.json (size, loop E/P for loops/make_table.py).
#   python boss_victory.py [wav]      (wav: also write the calibrated WAVs for listening)
import json, os, subprocess, sys, zlib
import numpy as np
import align, config, psxsynth

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "build_tmp", "boss_victory")
JSON = os.path.join(HERE, "boss_victory.json")
SR = psxsynth.SR
SONGS = (("BGM008", 0, 8), ("BGM016", 12, 16))     # (boss file, file with the normal recording, boss bank); song 1
# by ear: the eastern boss bank's drum hit (channel 1, key 46) is 3.3 dB louder than the normal one, on top of the
# boost fitted for the normal hit, and covered the brass; it plays at the normal version's level
TWEAK = {"BGM008": {1: 0.68}}                       # channel gain multipliers
FRAME = 1152

def pc_recording(n, part):
    d, pcs = align.pc_parts(n); f, t, o, s = pcs[part]
    r = subprocess.run([config.FFMPEG, "-v", "error", "-i", "pipe:0", "-f", "s16le", "-ac", "2", "-ar", "44100", "pipe:1"],
                       input=d[o:o + s], capture_output=True, check=True)
    return np.frombuffer(r.stdout, "<i2").reshape(-1, 2).astype(float) / 32768

def stft(m, hop=1024, win=4096):
    n = (len(m) - win) // hop
    fr = np.lib.stride_tricks.as_strided(m, (n, win), (m.strides[0] * hop, m.strides[0])) * np.hanning(win)
    return np.abs(np.fft.rfft(fr, axis=1))

def align_lag(Sx, Sy):
    """frames by which the recording lags the render (onset envelopes)"""
    ox, oy = np.log1p(Sx[:, 4:600]).sum(1), np.log1p(Sy[:, 4:600]).sum(1)
    def cc(k):
        m = min(len(ox) - max(0, k), len(oy) - max(0, -k)); return np.corrcoef(ox[max(0, k):][:m], oy[max(0, -k):][:m])[0, 1]
    return max(range(-40, 41), key=cc)

def calibrate(seq_n, rec):
    """per-channel gains and a tone curve (gain per rfft bin of 4096) that bring the normal render to the recording"""
    ev, _ = psxsynth.events(psxsynth.emi_parts(seq_n)[0x53455170], 1)
    chans = sorted({e[1] for e in ev if e[2] == "on"})
    parts = {c: psxsynth.render(seq_n, 1, seq_n, channels={c})[0] for c in chans}
    Sx = stft(rec.mean(1)); S = {c: stft(parts[c].mean(1)) for c in chans}
    k = align_lag(Sx, sum(S.values()))
    m = min(len(Sx) - max(0, k), len(S[chans[0]]) - max(0, -k)) - 2
    X = Sx[max(0, k):][:m, 4:900].ravel()
    A = np.stack([S[c][max(0, -k):][:m, 4:900].ravel() for c in chans], 1)
    g, *_ = np.linalg.lstsq(A, X, rcond=None)
    g = np.clip(g / np.median(g), 0.5, 2.0)                  # balance only: +-6 dB at most
    mix = sum(parts[c] * gc for c, gc in zip(chans, g))
    Sm = stft(mix.mean(1))
    a, b = Sx[max(0, k):][:m].mean(0), Sm[max(0, -k):][:m].mean(0)
    f = np.fft.rfftfreq(4096, 1 / SR); curve = np.ones_like(f)
    edges = 25 * 2 ** (np.arange(0, 30) / 3)                  # third-octave bands from 25 Hz
    centres, gains = [], []
    for lo, hi in zip(edges, edges[1:]):
        sel = (f >= lo) & (f < hi)
        if sel.sum() and b[sel].sum() > 0: centres.append(np.sqrt(lo * hi)); gains.append(a[sel].sum() / b[sel].sum())
    gains = np.clip(np.array(gains) / np.median(gains), 0.5, 2.0)
    curve = np.interp(np.log(np.maximum(f, 1)), np.log(centres), gains)
    level = np.sqrt((rec ** 2).mean())
    return dict(zip(chans, g)), curve, level

def apply_curve(y, curve):
    n = 1 << int(np.ceil(np.log2(len(y) + 4096)))
    f = np.fft.rfftfreq(n, 1 / SR); h = np.interp(f, np.fft.rfftfreq(4096, 1 / SR), curve)
    return np.stack([np.fft.irfft(np.fft.rfft(y[:, c], n) * h, n)[:len(y)] for c in (0, 1)], 1)

def make(write_wav=False):
    os.makedirs(OUT, exist_ok=True)
    table = {}
    for name, seq_n, bank in SONGS:
        rec = pc_recording(seq_n, 1)
        gains, curve, level = calibrate(seq_n, rec)
        ev, (ls, le, tot) = psxsynth.events(psxsynth.emi_parts(seq_n)[0x53455170], 1)
        boss = sum(psxsynth.render(seq_n, 1, bank, channels={c})[0] * g * TWEAK.get(name, {}).get(c, 1.0)
                   for c, g in gains.items())
        normal = sum(psxsynth.render(seq_n, 1, seq_n, channels={c})[0] * g for c, g in gains.items())
        boss, normal = apply_curve(boss, curve), apply_curve(normal, curve)
        scale = level / np.sqrt((normal[:len(rec)] ** 2).mean())    # the normal version at the recording's level
        boss = boss * scale
        peak = np.abs(boss).max()
        if peak > 1.5: boss *= 1.5 / peak                            # ponytail: soft knee for a few dB only
        knee = 0.8; a = np.abs(boss)                                 # louder boss mix: soft-limit the peaks
        boss = np.where(a > knee, np.sign(boss) * (knee + (1 - knee) * np.tanh((a - knee) / (1 - knee))), boss)
        print(f"{name}: boss peak {20 * np.log10(peak):+.1f} dBFS before limiting, "
              f"{100 * (a > knee).mean():.2f}% of samples above the knee")
        wav = os.path.join(OUT, f"{name}_1.wav")
        psxsynth.write_wav(wav, boss, 1.0)
        if write_wav: psxsynth.write_wav(os.path.join(OUT, f"{name}_1_normal_check.wav"), normal, scale)
        mp3 = os.path.join(OUT, f"{name}_1.mp3")
        subprocess.run([config.FFMPEG, "-v", "error", "-y", "-i", wav, "-c:a", "libmp3lame", "-b:a", "128k", "-ar", "44100",
                        "-ac", "2", "-write_xing", "0", "-id3v2_version", "0", "-write_id3v1", "0", "-map_metadata", "-1", mp3],
                       check=True)
        if not write_wav: os.remove(wav)
        data = open(mp3, "rb").read()
        L = round((le - ls) * SR)
        # jump point E (frame-aligned, in the second pass): where the decoded audio around E matches the first pass's
        x = np.frombuffer(subprocess.run([config.FFMPEG, "-v", "error", "-i", mp3, "-f", "s16le", "-ac", "1", "-ar", "44100",
                                          "pipe:1"], capture_output=True, check=True).stdout, "<i2").astype(float)
        def match(E):
            w = 2048
            return min(np.corrcoef(x[E - w:E], x[E - L - w:E - L])[0, 1], np.corrcoef(x[E:E + w], x[E - L:E - L + w])[0, 1])
        first = int(np.ceil((le * SR + 0.5 * SR) / FRAME)); last = int(((le + (le - ls)) * SR - 1.0 * SR) / FRAME)
        E = max((f * FRAME for f in range(first, last)), key=match)
        table[f"{name}/1"] = dict(size=len(data), crc=zlib.crc32(data[:4096]), E=E, P=E - L, L=L,
                                  gains={str(c): round(float(g), 3) for c, g in gains.items()})
        print(f"{name}/1: {len(data)} bytes, loop {ls:.3f}..{le:.3f} s, E {E} P {E - L} (splice match {match(E):.4f}), "
              f"channel gains {table[f'{name}/1']['gains']}")
    json.dump(table, open(JSON, "w"), indent=1)

def mp3s():
    """{BGM file name: rendered song 1}, rendering first if needed"""
    if not all(os.path.exists(os.path.join(OUT, f"{n}_1.mp3")) for n, _, _ in SONGS) or not os.path.exists(JSON): make()
    return {n: open(os.path.join(OUT, f"{n}_1.mp3"), "rb").read() for n, _, _ in SONGS}

if __name__ == "__main__":
    make("wav" in sys.argv[1:])
