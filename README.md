# Audio2FL

> Turn any mp3 into a ready-to-open FL Studio project — stems, BPM, MIDI and all.

**v1.1** — 中文 / English / 日本語 / 한국어 · GPU acceleration · batch processing

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.x-EE4C2C?logo=pytorch&logoColor=white)](https://pytorch.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows-blue)](https://github.com/sy405/AUDIO/releases)

**[English](README.md) | [中文](README.zh.md)**

---

## What it does

Feed it one mp3. It will:

1. **Separate** the track into vocals / drums / bass / other
2. **Detect** the tempo (BPM)
3. **Transcribe** the melody into MIDI
4. **Detect** drum hits (kick / snare / hi-hat)
5. **Generate** a `.flp` you can open directly in FL Studio

> Built with AI assistance. Currently in beta — for learning and personal use.
>
> Everything runs locally. No audio is ever uploaded.

---

## Features

- **Four-language UI** — 中文 / English / 日本語 / 한국어, switch live from the top right
- **Automatic GPU** — uses CUDA when available, falls back to CPU otherwise
- **Batch mode** — point it at a folder, it processes every audio file inside
- **High-quality model** — optionally use `htdemucs_ft` (4-model ensemble, ~4x slower, GPU recommended)
- **Cancellable** — stop a run at any point
- **Self-healing templates** — if the FLP template goes missing, it restores itself
- **Fully offline** — no network calls during processing
- **Zero setup** — ships as a standalone exe, no Python/PyTorch/FFmpeg required

---

## Download

Grab the latest build from [Releases](https://github.com/sy405/AUDIO/releases):

| File | Size | Notes |
|---|---|---|
| **`Audio2FL-v1.1.exe`** | 203 MB | Single-file build. Double-click to run (first launch takes 30-60s, splash screen shown) |
| `Audio2FL-v1.0-win64.zip` | 241 MB | v1.0 folder build, starts fast |
| `Audio2FL-v1.0-cpu-offline.zip` | 321 MB | v1.0 offline build (models bundled) |

---

## Run from source

Requires **Python 3.11+** (3.12 / 3.13 also work):

```bash
git clone https://github.com/sy405/AUDIO.git
cd AUDIO

python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux / macOS

pip install -r requirements.txt
python a2fl_entry.py
```

> **Note**: `requirements.txt` points PyTorch at the CPU index. NVIDIA users can swap in the CUDA build for acceleration.

---

## Usage

### GUI

```bash
python a2fl_entry.py
```

Or drop an mp3 onto `Audio2FL.exe`.

| Field | Description |
|---|---|
| **Audio file** | mp3 / wav / flac / ogg |
| **Pick folder** | Batch mode — processes every audio file in that directory |
| **Output folder** | Defaults to `Music\Audio2FL` |
| **FL template** | Pick from the dropdown, or browse manually |
| **Make .flp / .mid / detect drums** | Toggle as needed |
| **High-quality model** | Uses `htdemucs_ft` (4x slower, best with a GPU) |
| **BPM** | Leave blank to auto-detect, or type a value |
| **Cancel** | Stop mid-run |

### Language switching

Top-right dropdown. Changes apply immediately — no restart needed.

### CLI

```bash
python -c "from app.toflp.pipeline import Options, run; \
run(Options(audio='song.mp3', out_dir='out', template='template.flp'))"
```

### Environment variables

| Variable | Purpose |
|---|---|
| `A2FL_DEVICE` | Force a device: `cpu` / `cuda` / `mps` |
| `HF_ENDPOINT` | HuggingFace mirror (e.g. `https://hf-mirror.com` in China) |

---

## Output

```
song.flp              FL Studio project (4 stems on the playlist, BPM set)
song.mid              MIDI (melody + drums)
song_stems/           four wav files
├── drums.wav
├── bass.wav
├── other.wav
└── vocals.wav
```

**The four wav files are the real deliverable** — useful even without FL Studio.

---

## Tech stack

| Stage | Choice | Why |
|---|---|---|
| **Separation** | PyTorch Demucs | Best open-source quality/speed balance |
| **MIDI** | Basic Pitch ONNX | No TensorFlow dependency, 225 KB model |
| **BPM** | Custom beat detection | Lightweight, < 1 BPM error in practice |
| **FLP** | [pyflp](https://github.com/demberto/pyflp) | Pure-Python FL Studio project I/O |
| **GUI** | CustomTkinter + Windows Acrylic | Glassmorphism look |

### Why not ONNX for separation

PyTorch is **faster** than ONNX FP16 on x86 CPU (ONNX has to upcast to FP32 internally). The trade-off is a larger bundle (~518 MB runtime), but the speed win is real.

---

## Known limitations

- **No m4a / aac / wma / opus input** — convert to mp3 or wav first
- **1 GB RAM minimum** for separation
- **FLP needs a template** — auto-recovers, but fails on read-only program directories
- **Drum classification is approximate** — kick/snare/hat detection has some error
- **Vocal bleed** — busy mixes may leave instruments in the vocals stem
- **Slow first launch** — the single-file build unpacks ~500 MB to a temp folder (30-60s, splash screen shown)
- **High-quality model downloads** — `htdemucs_ft` needs ~320 MB on first use

---

## Roadmap

| Item | Status |
|---|---|
| Batch processing | ✅ v1.1 |
| High-quality model | ✅ v1.1 |
| Multi-language UI | ✅ v1.1 (zh / en / ja / ko) |
| GPU acceleration | ✅ v1.1 (auto CUDA detection) |
| Windows 11 validation | ⏳ pending |
| More input formats (m4a / aac / opus) | ⏳ planned |
| API integration | ⏳ optional, for harder mixes |

---

## FAQ

<details>
<summary><b>The splash progress bar is stuck</b></summary>

The single-file build unpacks ~500 MB before the UI appears — **30-60 seconds on first launch**. The progress bar is decorative; it doesn't reflect actual progress. Second launches are faster thanks to OS caching.
</details>

<details>
<summary><b>"FL template not found"</b></summary>

Normally it restores itself from the bundled copy. If it still fails, the program directory is probably read-only — move the app somewhere writable (e.g. Desktop).
</details>

<details>
<summary><b>"Not enough memory"</b></summary>

Separation needs at least 1 GB free. Close browsers and chat apps, then retry.
</details>

<details>
<summary><b>Can I use my GPU?</b></summary>

Yes — the app auto-detects CUDA. The shipped exe bundles **CPU-only PyTorch**, so to actually use a GPU you need to run from source with the CUDA build:

```bash
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
```

You can also force a device:

```bash
set A2FL_DEVICE=cuda    # or cpu
```
</details>

<details>
<summary><b>How does batch mode work?</b></summary>

Click **Pick folder**, select a directory, and the app will scan it for mp3 / wav / flac / ogg, then process each in order into the same output folder. **Cancel** stops the queue.
</details>

---

## Credits

- [Demucs](https://github.com/facebookresearch/demucs) — Meta's source separation model
- [Basic Pitch](https://github.com/spotify/basic-pitch) — Spotify's audio-to-MIDI model
- [pyflp](https://github.com/demberto/pyflp) — FL Studio project I/O
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) — modern Tkinter wrapper

---

## License

[MIT](LICENSE)

---

## Disclaimer

For personal learning and creative work. Separation quality depends heavily on the source material — **don't expect a perfect reconstruction**.

Respect the original artists' copyright. Don't use separated stems commercially or redistribute them.
