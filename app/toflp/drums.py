"""Drum hit detection: kick / snare / hat from a drum stem (numpy only).

Band-energy onset detection is crude but works well on an isolated drum
stem, which is exactly what we feed it (demucs' ``drums`` output).
"""
from __future__ import annotations

import numpy as np

# General MIDI percussion notes
KICK, SNARE, CLOSED_HAT = 36, 38, 42

BANDS = {
    "low": (30.0, 140.0),
    "mid": (200.0, 2200.0),
    "high": (5000.0, 12000.0),
}


def _stft_mag(x: np.ndarray, n_fft: int, hop: int) -> np.ndarray:
    if len(x) < n_fft:
        x = np.pad(x, (0, n_fft - len(x)))
    n_frames = 1 + (len(x) - n_fft) // hop
    frames = np.lib.stride_tricks.as_strided(
        x, shape=(n_frames, n_fft), strides=(x.strides[0] * hop, x.strides[0]), writeable=False
    )
    window = np.hanning(n_fft).astype(np.float32)
    return np.abs(np.fft.rfft(frames * window, axis=1))


def detect_hits(x: np.ndarray, sr: int, hop: int = 256, n_fft: int = 1024,
                min_gap_s: float = 0.055) -> list[tuple[float, int, float]]:
    """Return ``[(time_seconds, midi_note, strength), ...]`` sorted by time."""
    mag = _stft_mag(x, n_fft, hop)
    freqs = np.fft.rfftfreq(n_fft, 1.0 / sr)
    fps = sr / hop

    energy = {}
    onset = {}
    for name, (lo, hi) in BANDS.items():
        mask = (freqs >= lo) & (freqs < hi)
        band = mag[:, mask]
        if band.size == 0:
            energy[name] = np.zeros(mag.shape[0], dtype=np.float32)
            onset[name] = np.zeros(mag.shape[0], dtype=np.float32)
            continue
        e = np.log1p(band.sum(axis=1))
        energy[name] = e
        onset[name] = np.maximum(np.diff(e, prepend=e[:1]), 0.0)

    total = onset["low"] + onset["mid"] + onset["high"]
    if not np.any(total > 0):
        return []

    thr = float(np.percentile(total, 92))
    thr = max(thr, float(total.max()) * 0.12, 1e-6)
    min_gap = max(1, int(min_gap_s * fps))

    hits: list[tuple[float, int, float]] = []
    last = -min_gap
    for i in range(1, len(total) - 1):
        if total[i] < thr:
            continue
        if total[i] < total[i - 1] or total[i] < total[i + 1]:
            continue
        if i - last < min_gap:
            continue
        last = i
        low, mid, high = onset["low"][i], onset["mid"][i], onset["high"][i]
        s = low + mid + high
        if low / s > 0.45:
            note = KICK
        elif high / s > 0.40:
            note = CLOSED_HAT
        else:
            note = SNARE
        hits.append((i / fps, note, float(min(1.0, total[i] / (total.max() + 1e-9)))))

    return hits


def hits_to_notes(hits: list[tuple[float, int, float]], bpm: float,
                  length_s: float) -> list[dict]:
    """Convert hit times into beat-based note descriptors."""
    spb = 60.0 / max(bpm, 1.0)
    out = []
    for t, note, strength in hits:
        if t > length_s:
            break
        start = t / spb
        # quantise to 1/16 beat grid, keep it musical
        start_q = round(start * 4) / 4
        out.append({
            "pitch": note,
            "start_beats": start_q,
            "length_beats": 0.25,
            "velocity": int(70 + 55 * strength),
        })
    return out
