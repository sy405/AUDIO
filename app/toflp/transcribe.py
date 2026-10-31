"""MIDI transcription with the Basic Pitch ONNX model (no TensorFlow).

The model takes 43 844 raw samples (22 050 Hz mono) and returns
``(frames, 88)`` note / onset activations plus ``(frames, 264)`` pitch
contours.  We decode notes from the activations and write a type-1 MIDI
file ourselves, so no pretty_midi / librosa dependency is pulled in.
"""
from __future__ import annotations

import os
import struct
from dataclasses import dataclass

import numpy as np

SAMPLE_RATE = 22050
HOP = 256
WINDOW = 43844
N_KEYS = 88
MIDI_A0 = 21


@dataclass
class Note:
    pitch: int
    start_s: float
    end_s: float
    velocity: int = 90

    @property
    def length_s(self) -> float:
        return max(0.0, self.end_s - self.start_s)


def _load_mono(path: str) -> np.ndarray:
    import soundfile as sf

    data, sr = sf.read(path, dtype="float32", always_2d=True)
    mono = data.mean(axis=1)
    if sr != SAMPLE_RATE:
        mono = _resample(mono, sr, SAMPLE_RATE)
    return np.ascontiguousarray(mono, dtype=np.float32)


def _resample(x: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    if sr_in == sr_out:
        return x
    n_out = int(round(len(x) * sr_out / sr_in))
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
    w = np.sinc(d)
    y = (x[idx] * w).sum(axis=1) / np.maximum(w.sum(axis=1), 1e-9)
    return y.astype(np.float32)


def _session(model_path: str):
    import onnxruntime as ort

    opts = ort.SessionOptions()
    opts.enable_cpu_mem_arena = False
    opts.intra_op_num_threads = 2
    return ort.InferenceSession(model_path, sess_options=opts,
                                providers=["CPUExecutionProvider"])


def _run_model(sess, audio: np.ndarray, batch: int = 8) -> tuple[np.ndarray, np.ndarray]:
    """Slide the 2 s window over ``audio`` and average activations."""
    n = len(audio)
    hop = WINDOW // 2
    starts = list(range(0, max(n - WINDOW, 0) + 1, hop))
    if not starts or starts[-1] + WINDOW < n:
        starts.append(max(0, n - WINDOW))

    frames = int(np.ceil(n / HOP)) + 2
    note_acc = np.zeros((frames, N_KEYS), dtype=np.float32)
    onset_acc = np.zeros((frames, N_KEYS), dtype=np.float32)
    weight = np.zeros(frames, dtype=np.float32)

    padded = np.pad(audio, (0, max(0, WINDOW - n)))
    chunks = [padded[s:s + WINDOW] for s in starts]

    for i in range(0, len(chunks), batch):
        group = np.stack(chunks[i:i + batch])[:, :, None]
        outs = sess.run(None, {sess.get_inputs()[0].name: group})
        # identify note vs onset by mean activation (onset is sparser)
        a, b = outs[0], outs[1]
        if float(b.mean()) > float(a.mean()):
            a, b = b, a
        for j, s in enumerate(starts[i:i + batch]):
            f0 = int(round(s / HOP))
            nf = a.shape[1]
            end = min(f0 + nf, frames)
            note_acc[f0:end] += a[j, :end - f0]
            onset_acc[f0:end] += b[j, :end - f0]
            weight[f0:end] += 1.0

    weight[weight == 0] = 1.0
    return note_acc / weight[:, None], onset_acc / weight[:, None]


def _decode(note: np.ndarray, onset: np.ndarray, *, frame_thr: float = 0.3,
            onset_thr: float = 0.5, min_note_frames: int = 11,
            max_freq: float | None = 2093.0) -> list[Note]:
    fps = SAMPLE_RATE / HOP
    notes: list[Note] = []
    active = np.zeros(N_KEYS, dtype=bool)
    starts = np.zeros(N_KEYS, dtype=int)

    for t in range(note.shape[0]):
        frame = note[t] > frame_thr
        on = onset[t] > onset_thr
        for k in range(N_KEYS):
            if not active[k]:
                if frame[k] and (on[k] or t == 0):
                    active[k] = True
                    starts[k] = t
            else:
                if on[k] and t - starts[k] > 2:
                    _push(notes, k, starts[k], t, fps, min_note_frames, max_freq)
                    starts[k] = t
                elif not frame[k]:
                    _push(notes, k, starts[k], t, fps, min_note_frames, max_freq)
                    active[k] = False
    for k in range(N_KEYS):
        if active[k]:
            _push(notes, k, starts[k], note.shape[0], fps, min_note_frames, max_freq)
    notes.sort(key=lambda n: (n.start_s, n.pitch))
    return notes


def _push(out: list, key: int, start: int, end: int, fps: float,
          min_frames: int, max_freq: float | None) -> None:
    pitch = MIDI_A0 + key
    freq = 440.0 * 2 ** ((pitch - 69) / 12)
    if max_freq and freq > max_freq:
        return
    if end - start < min_frames:
        return
    out.append(Note(pitch=pitch, start_s=start / fps, end_s=end / fps))


def transcribe(path: str, model_path: str) -> list[Note]:
    sess = _session(model_path)
    audio = _load_mono(path)
    if len(audio) < WINDOW:
        audio = np.pad(audio, (0, WINDOW - len(audio)))
    note, onset = _run_model(sess, audio)
    return _decode(note, onset)


# --- minimal Standard MIDI File writer --------------------------------
def write_midi(notes: list[Note], out_path: str, bpm: float = 120.0,
               name: str = "ToFLP", drums: list[dict] | None = None) -> str:
    """Write a type-1 MIDI file; optional second track for drum hits."""
    ppq = 96
    tpb = 60.0 / bpm  # seconds per beat

    def to_ticks(sec: float) -> int:
        return max(0, int(round(sec / tpb * ppq)))

    def melodic_track() -> bytearray:
        events: list[tuple[int, int, bytes]] = []
        for n in notes:
            start = to_ticks(n.start_s)
            end = max(start + 1, to_ticks(n.end_s))
            vel = max(1, min(127, n.velocity))
            events.append((start, 1, bytes([0x90, n.pitch & 0x7F, vel])))
            events.append((end, 0, bytes([0x80, n.pitch & 0x7F, 64])))
        events.sort(key=lambda e: (e[0], e[1]))

        track = bytearray()
        track += b"\x00\xff\x03" + bytes([len(name) & 0x7F]) + name.encode("ascii", "replace")
        tempo_us = int(round(60_000_000 / bpm))
        track += b"\x00\xff\x51\x03" + tempo_us.to_bytes(3, "big")
        track += b"\x00\xff\x58\x04" + bytes([4, 2, 24, 8])
        last = 0
        for tick, _pri, data in events:
            track += _varint(tick - last) + data
            last = tick
        track += b"\x00\xff\x2f\x00"
        return track

    def drum_track() -> bytearray:
        events: list[tuple[int, int, bytes]] = []
        for d in drums or []:
            start = max(0, int(round(d["start_beats"] * ppq)))
            length = max(1, int(round(d.get("length_beats", 0.25) * ppq)))
            vel = max(1, min(127, int(d.get("velocity", 100))))
            events.append((start, 1, bytes([0x99, d["pitch"] & 0x7F, vel])))
            events.append((start + length, 0, bytes([0x89, d["pitch"] & 0x7F, 64])))
        events.sort(key=lambda e: (e[0], e[1]))
        track = bytearray()
        track += b"\x00\xff\x03\x05Drums"
        last = 0
        for tick, _pri, data in events:
            track += _varint(tick - last) + data
            last = tick
        track += b"\x00\xff\x2f\x00"
        return track

    tracks = [melodic_track()]
    if drums:
        tracks.append(drum_track())

    header = b"MThd" + struct.pack(">IHHH", 6, 1, len(tracks), ppq)
    with open(out_path, "wb") as f:
        f.write(header)
        for tr in tracks:
            f.write(b"MTrk" + struct.pack(">I", len(tr)) + bytes(tr))
    return out_path


def _varint(value: int) -> bytes:
    out = bytearray([value & 0x7F])
    value >>= 7
    while value:
        out.insert(0, (value & 0x7F) | 0x80)
        value >>= 7
    return bytes(out)
