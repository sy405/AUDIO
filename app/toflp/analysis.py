"""Lightweight BPM / beat estimation with numpy only (no librosa/numba)."""
from __future__ import annotations

import numpy as np


def _t(key: str) -> str:
    """取当前语言的文案。"""
    try:
        from app.i18n import get_i18n
        return get_i18n().t(key)
    except Exception:
        return "?"


def load_mono(path: str, target_sr: int = 22050) -> tuple[np.ndarray, int]:
    import soundfile as sf

    data, sr = sf.read(path, dtype="float32", always_2d=True)
    mono = data.mean(axis=1)
    if sr != target_sr:
        mono = _resample(mono, sr, target_sr)
        sr = target_sr
    return mono, sr


def _resample(x: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    if sr_in == sr_out:
        return x
    n_out = int(round(len(x) * sr_out / sr_in))
    # windowed-sinc (Kaiser) resampling, cheap and adequate for beat detection
    ratio = sr_out / sr_in
    n_win = 16
    t_out = np.arange(n_out)
    pos = t_out / ratio
    i0 = np.floor(pos).astype(np.int64)
    frac = pos - i0
    taps = np.arange(-n_win, n_win + 1)
    idx = i0[:, None] + taps[None, :]
    np.clip(idx, 0, len(x) - 1, out=idx)
    d = frac[:, None] - taps[None, :]
    w = np.sinc(d) * np.kaiser(2 * n_win + 1, 8.0)[None, :] if False else np.sinc(d)
    y = (x[idx] * w).sum(axis=1) / np.maximum(w.sum(axis=1), 1e-9)
    return y.astype(np.float32)


def onset_envelope(x: np.ndarray, sr: int = 22050, hop: int = 256, n_fft: int = 1024) -> np.ndarray:
    if len(x) < n_fft:
        x = np.pad(x, (0, n_fft - len(x)))
    n_frames = 1 + (len(x) - n_fft) // hop
    window = np.hanning(n_fft).astype(np.float32)
    # stride trick instead of a loop
    frames = np.lib.stride_tricks.as_strided(
        x, shape=(n_frames, n_fft), strides=(x.strides[0] * hop, x.strides[0]), writeable=False
    )
    spec = np.abs(np.fft.rfft(frames * window, axis=1))
    # log compression, then half-wave rectified spectral flux
    logspec = np.log1p(10.0 * spec)
    flux = np.diff(logspec, axis=0, prepend=logspec[:1])
    flux = np.maximum(flux, 0).sum(axis=1)
    # remove DC / smooth
    flux = flux - np.mean(flux)
    kernel = np.ones(3, dtype=np.float32) / 3.0
    flux = np.convolve(flux, kernel, mode="same")
    return flux.astype(np.float32)


def _peak_times(env: np.ndarray, fps: float, min_gap_s: float = 0.11) -> np.ndarray:
    """Frame indices of onset peaks."""
    if env.size < 4:
        return np.array([], dtype=int)
    thr = float(np.median(env) + 0.6 * np.std(env))
    min_gap = max(1, int(min_gap_s * fps))
    peaks = []
    last = -min_gap
    for i in range(1, len(env) - 1):
        if env[i] < thr:
            continue
        if env[i] < env[i - 1] or env[i] < env[i + 1]:
            continue
        if i - last < min_gap:
            continue
        peaks.append(i)
        last = i
    return np.array(peaks, dtype=int)


def estimate_bpm(x: np.ndarray, sr: int = 22050, hop: int = 256,
                 bpm_min: float = 60.0, bpm_max: float = 190.0) -> tuple[float, float]:
    """Return (bpm, confidence).

    Tempo comes from the median inter-onset interval (robust to the
    strong/weak alternation that makes plain autocorrelation report a
    half or double tempo), then gets snapped onto the autocorrelation
    peak nearby.
    """
    if isinstance(x, (str, bytes)) or hasattr(x, "__fspath__"):
        x, sr = load_mono(str(x), sr)
    env = onset_envelope(x, sr, hop)
    if env.size < 8 or not np.any(np.isfinite(env)):
        return 120.0, 0.0
    env = np.nan_to_num(env)
    fps = sr / hop

    # --- autocorrelation of the (mean removed) envelope --------------
    centred = env - env.mean()
    ac = np.correlate(centred, centred, mode="full")[centred.size - 1:]
    ac /= max(ac[0], 1e-9)

    def ac_at(lag_value: float) -> float:
        if lag_value <= 0:
            return 0.0
        pos = lag_value
        i = int(pos)
        if i >= len(ac) - 1:
            return 0.0
        f = pos - i
        return float(ac[i] * (1 - f) + ac[i + 1] * f)

    # --- candidate tempo from inter-onset intervals ------------------
    bpm = None
    peaks = _peak_times(env, fps)
    if peaks.size >= 6:
        iois = np.diff(peaks) / fps
        iois = iois[(iois > 0.18) & (iois < 1.4)]
        if iois.size >= 5:
            med = float(np.median(iois))
            if med > 0:
                bpm = 60.0 / med

    # --- beat-grid fit ("tempogram") ---------------------------------
    # For each candidate beat period, measure how well the onset peaks line
    # up with a pulse train of that period.  Unlike autocorrelation this is
    # phase aware, so a half-tempo grid that leaves half the onsets off the
    # beat scores lower.
    grid_bpm, grid_score = None, -1.0
    if peaks.size >= 6:
        times = peaks / fps
        weights = np.clip(env[peaks], 0, None).astype(np.float64)
        weights = weights / (weights.sum() + 1e-9)
        cands = np.arange(bpm_min, bpm_max, 0.5)
        periods = 60.0 / cands
        phases = np.exp(-2j * np.pi * times[None, :] / periods[:, None])
        strength = np.abs((phases * weights[None, :]).sum(axis=1))

        # coverage: a grid at twice the real tempo leaves every second pulse
        # without an onset, which is what disambiguates octave errors.
        nz = np.clip(env, 0, None)
        nz = nz / (nz.max() + 1e-9)
        smoothed = np.convolve(nz, np.ones(5) / 5.0, mode="same")
        duration = len(env) / fps
        coverage = np.empty_like(cands)
        for i, period in enumerate(periods):
            if period <= 0 or period > duration:
                coverage[i] = 0.0
                continue
            pulse_frames = np.arange(0, duration, period) * fps
            idx = np.clip(pulse_frames.astype(int), 0, len(smoothed) - 1)
            coverage[i] = float(smoothed[idx].mean())

        prior = np.exp(-0.5 * (np.log2(cands / 120.0) / 0.75) ** 2)
        score = strength * coverage * prior
        k = int(np.argmax(score))
        grid_bpm = float(cands[k])
        grid_score = float(score[k])

    if grid_bpm is not None:
        bpm = grid_bpm
    if bpm is None:
        lag_min = max(1, int(round(fps * 60.0 / bpm_max)))
        lag_max = min(len(ac) - 1, int(round(fps * 60.0 / bpm_min)))
        if lag_max <= lag_min:
            return 120.0, 0.0
        seg = ac[lag_min:lag_max + 1]
        lags = np.arange(lag_min, lag_max + 1)
        prior = np.exp(-0.5 * (np.log2((60.0 * fps / lags) / 120.0) / 0.8) ** 2)
        best = int(np.argmax(seg * prior))
        bpm = 60.0 * fps / lags[best]

    # --- fold into the supported range -------------------------------
    while bpm < bpm_min:
        bpm *= 2.0
    while bpm > bpm_max:
        bpm /= 2.0

    # --- refine on the autocorrelation around that tempo -------------
    best_bpm, best_score = bpm, ac_at(fps * 60.0 / bpm)
    for candidate in np.arange(bpm * 0.94, bpm * 1.06, bpm * 0.002):
        s = ac_at(fps * 60.0 / candidate)
        if s > best_score:
            best_bpm, best_score = float(candidate), s
    bpm = best_bpm

    return round(float(bpm), 2), float(np.clip(best_score, 0.0, 1.0))


def detect_key(x: np.ndarray, sr: int = 22050) -> str:
    """Rough key detection via chroma fold + Krumhansl profiles (best effort)."""
    if len(x) < 4096:
        return _t("key_unknown")
    n_fft = 4096
    hop = 2048
    n_frames = 1 + (len(x) - n_fft) // hop
    if n_frames <= 0:
        return _t("key_unknown")
    frames = np.lib.stride_tricks.as_strided(
        x, shape=(n_frames, n_fft), strides=(x.strides[0] * hop, x.strides[0]), writeable=False
    )
    spec = np.abs(np.fft.rfft(frames * np.hanning(n_fft), axis=1))
    freqs = np.fft.rfftfreq(n_fft, 1.0 / sr)
    mask = (freqs >= 65) & (freqs <= 2000)
    spec, freqs = spec[:, mask], freqs[mask]
    if spec.size == 0:
        return _t("key_unknown")
    midi = np.round(69 + 12 * np.log2(np.maximum(freqs, 1) / 440.0)).astype(int)
    pc = midi % 12
    chroma = np.zeros(12)
    for k in range(12):
        chroma[k] = spec[:, pc == k].sum()
    if chroma.sum() <= 0:
        return _t("key_unknown")
    chroma /= chroma.sum()

    major = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
    minor = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    best = (-1e9, "C", "major")
    for root in range(12):
        for prof, mode in ((major, "major"), (minor, "minor")):
            r = np.roll(prof, root)
            score = float(np.corrcoef(chroma, r)[0, 1])
            if score > best[0]:
                best = (score, names[root], mode)
    return f"{best[1]} {best[2]}"
