# -*- coding: utf-8 -*-
"""End-to-end pipeline (Audio2FL): mp3 -> stems + BPM + MIDI -> .flp

分轨后端: PyTorch Demucs (FP32, 4 线程)
基准数据 (i5-7200U, 30s 片段):
    PyTorch 52.21s  vs  ONNX FP16 83s   -> 快 37%
"""
from __future__ import annotations

import os
import shutil
import sys
import time
import traceback
from dataclasses import dataclass, field
from typing import Callable

Progress = Callable[[str, float], None]  # (message, fraction 0..1)


def _t(key: str, **fmt) -> str:
    """取当前语言的文案；i18n 不可用时回退到 key。"""
    try:
        from app.i18n import get_i18n
        return get_i18n().t(key, **fmt)
    except Exception:
        return key

# 分轨线程数 (实测 4 线程比 2 线程快 26%)
DEMUCS_THREADS = 4


def pick_device() -> str:
    """自动选择推理设备：cuda > mps > cpu。

    可用环境变量 A2FL_DEVICE 强制指定（cpu / cuda / mps）。
    """
    forced = os.environ.get("A2FL_DEVICE", "").strip().lower()
    if forced in ("cpu", "cuda", "mps"):
        return forced
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
        mps = getattr(torch.backends, "mps", None)
        if mps is not None and mps.is_available():
            return "mps"
    except Exception:
        pass
    return "cpu"


@dataclass
class Options:
    audio: str
    out_dir: str
    template: str
    make_midi: bool = True
    make_flp: bool = True
    make_drums: bool = True
    bpm_override: float | None = None
    keep_stems: bool = True
    # 分轨模型：htdemucs(快) / htdemucs_ft(高质量, 慢约 4 倍, 建议 GPU)
    model_name: str = "htdemucs"


@dataclass
class Result:
    out_dir: str
    flp: str | None = None
    mid: str | None = None
    stems: dict[str, str] = field(default_factory=dict)
    bpm: float = 120.0
    key: str = "未知"
    notes: int = 0
    drums: int = 0
    seconds: float = 0.0
    log: list[str] = field(default_factory=list)


def resource_path(rel: str) -> str:
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, rel)


def find_model(name: str) -> str | None:
    for root in (
        getattr(sys, "_MEIPASS", ""),
        os.path.dirname(sys.executable),
        os.path.dirname(os.path.abspath(__file__)),
        os.getcwd(),
    ):
        if not root:
            continue
        p = os.path.join(root, "models", name)
        if os.path.exists(p):
            return p
    return None


def list_templates() -> list[tuple[str, str]]:
    """返回可用的 FL 模板 [(显示名, 路径)]。

    搜索顺序：exe 同目录 -> _MEIPASS -> 包内 templates/ -> 当前工作目录
    """
    roots = []
    exe_dir = os.path.dirname(sys.executable)
    roots.append(exe_dir)
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        roots.append(meipass)
    roots.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    roots.append(os.getcwd())

    seen = {}
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        # 单文件（返回语言无关的 key，显示名交给 GUI 翻译）
        p = os.path.join(root, "template.flp")
        if os.path.isfile(p) and p not in seen:
            seen[p] = "@default"
        # templates/ 目录里的全部
        tdir = os.path.join(root, "templates")
        if os.path.isdir(tdir):
            for f in sorted(os.listdir(tdir)):
                if f.lower().endswith(".flp"):
                    fp = os.path.join(tdir, f)
                    if fp not in seen:
                        seen[fp] = os.path.splitext(f)[0]
    return [(name, path) for path, name in seen.items()]


def ensure_template(preferred: str | None = None) -> str | None:
    """确保有一个可用的模板。

    1. preferred 存在 -> 直接用
    2. 否则找任意一个可用模板
    3. 都找不到 -> 从包内复制一份到 exe 目录（自愈）
    """
    if preferred and os.path.isfile(preferred):
        return preferred

    found = list_templates()
    if found:
        return found[0][1]

    # 尝试从 _MEIPASS 恢复
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        src = os.path.join(meipass, "template.flp")
        if os.path.isfile(src):
            dst = os.path.join(os.path.dirname(sys.executable), "template.flp")
            try:
                import shutil
                shutil.copy2(src, dst)
                return dst
            except Exception:
                return src
    return None


def available_memory_gb() -> float:
    try:
        import ctypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
            return stat.ullAvailPhys / (1024 ** 3)
    except Exception:
        pass
    return 0.0


# ----------------------------------------------------------------------
# 分轨: PyTorch Demucs
# ----------------------------------------------------------------------
def _separate(audio: str, out_dir: str, report: Progress, model_name: str = "htdemucs") -> dict:
    """用 PyTorch Demucs 分离四轨, 返回 {stem: (samples, channels) ndarray}"""
    import numpy as np
    import soundfile as sf
    import torch

    from demucs.apply import apply_model
    from demucs.pretrained import get_model

    device = pick_device()
    if device == "cpu":
        torch.set_num_threads(DEMUCS_THREADS)

    _dev = pick_device()
    _tag = "GPU" if _dev in ("cuda", "mps") else "CPU"
    report(_t("pr_sep_loading", model=model_name, dev=_tag), 0.10)
    model = get_model(model_name)
    model.eval()

    sr_model = int(getattr(model, "samplerate", 44100))
    sources_names = list(getattr(model, "sources", ["drums", "bass", "other", "vocals"]))

    # 读音频为 (channels, samples) float32
    data, sr = sf.read(audio, dtype="float32", always_2d=True)
    wav = torch.from_numpy(np.ascontiguousarray(data.T))
    if wav.shape[0] == 1:
        wav = wav.repeat(2, 1)
    elif wav.shape[0] > 2:
        wav = wav[:2]

    # 重采样到模型采样率
    if sr != sr_model:
        try:
            import torchaudio
            wav = torchaudio.functional.resample(wav, sr, sr_model)
        except Exception:
            pass  # 交给 demucs 内部处理

    report(_t("pr_sep_running"), 0.15)

    with torch.no_grad():
        out = apply_model(
            model, wav.unsqueeze(0),
            device=device,
            shifts=0,
            overlap=0.1,
            progress=False,
            split=True,
        )[0]  # -> (n_sources, channels, samples)

    report(_t("pr_sep_writing"), 0.66)

    stems: dict[str, np.ndarray] = {}
    for i, name in enumerate(sources_names):
        src = out[i]
        if sr_model != sr:
            try:
                import torchaudio
                src = torchaudio.functional.resample(src, sr_model, sr)
            except Exception:
                pass
        stems[name] = src.numpy().T  # (samples, channels)

    return stems


def run(opts: Options, progress: Progress | None = None,
        cancel: Callable[[], bool] | None = None) -> Result:
    def report(msg: str, frac: float) -> None:
        if progress:
            progress(msg, frac)

    def check_cancel() -> None:
        if cancel and cancel():
            raise RuntimeError(_t("err_cancelled"))

    t0 = time.time()
    res = Result(out_dir=opts.out_dir)

    libs = resource_path("libs")
    if os.path.isdir(libs) and libs not in sys.path:
        sys.path.insert(0, libs)
    pkg_root = os.path.dirname(os.path.abspath(__file__))
    if pkg_root not in sys.path:
        sys.path.insert(0, pkg_root)

    import numpy as np

    from . import analysis, transcribe

    os.makedirs(opts.out_dir, exist_ok=True)
    _probe_audio(opts.audio)
    base = os.path.splitext(os.path.basename(opts.audio))[0]
    work = os.path.join(opts.out_dir, f"{base}_stems")
    os.makedirs(work, exist_ok=True)
    res.log.append(_t("log_input", path=opts.audio))
    res.log.append(_t("log_output", path=opts.out_dir))

    # --- 1. BPM ------------------------------------------------------
    report(_t("pr_bpm"), 0.03)
    try:
        bpm, conf = analysis.estimate_bpm(opts.audio)
        res.bpm = opts.bpm_override or bpm
        res.log.append(_t("log_bpm", bpm="%.2f" % bpm))
    except Exception as exc:
        res.bpm = opts.bpm_override or 120.0
        res.log.append(_t("log_bpm_fail", err=exc))
    if opts.bpm_override:
        res.bpm = opts.bpm_override
    # 模板自愈：找不到就自动恢复
    opts.template = ensure_template(opts.template)

    check_cancel()

    # --- 2. separation ----------------------------------------------
    free = available_memory_gb()
    if free and free < 1.1:
        raise RuntimeError(
            f"可用内存只有 {free:.1f} GB，分轨至少需要 1 GB。"
            f"请先关掉其他程序（浏览器、聊天软件）再试。")
    report(_t("pr_sep_pytorch"), 0.08)
    stems = {}
    sep_error = None
    try:
        stems = _separate(opts.audio, work, report, model_name=opts.model_name)
    except Exception as exc:
        sep_error = exc
        res.log.append(_t("err_sep_fail", err=exc))
    check_cancel()

    stem_paths: dict[str, str] = {}
    names = {"drums": "Drums", "bass": "Bass", "other": "Other", "vocals": "Vocals"}
    for key, arr in stems.items():
        p = os.path.join(work, f"{key}.wav")
        if not os.path.exists(p):
            import soundfile as sf
            sf.write(p, arr, 44100)
        stem_paths[key] = p
        res.stems[key] = p
    if stem_paths:
        res.log.append(_t("log_stems", names=", ".join(sorted(stem_paths))))
    if sep_error is not None and not stem_paths:
        raise RuntimeError(_t("err_sep_fatal", err=sep_error))

    # --- 3. transcription -------------------------------------------
    notes = []
    drum_notes: list[dict] = []
    if opts.make_midi:
        report(_t("pr_transcribe"), 0.70)
        model = find_model(os.path.join("basic_pitch", "nmp.onnx")) or find_model("nmp.onnx")
        if model is None:
            res.log.append(_t("log_no_model"))
        else:
            src = stem_paths.get("other") or stem_paths.get("vocals") or next(iter(stem_paths.values()))
            try:
                notes = transcribe.transcribe(src, model)
                res.notes = len(notes)
                res.log.append(_t("log_notes", n=len(notes), src=os.path.basename(src)))
            except Exception as exc:
                res.log.append(_t("log_trans_fail", err=exc))
    check_cancel()

    # --- 3b. drum hits -----------------------------------------------
    if opts.make_drums and "drums" in stem_paths:
        report(_t("pr_drums"), 0.80)
        try:
            from . import drums as drums_mod

            data, sr = _read_mono(stem_paths["drums"])
            hits = drums_mod.detect_hits(data, sr)
            drum_notes = drums_mod.hits_to_notes(hits, res.bpm, len(data) / sr)
            kick = sum(1 for n in drum_notes if n["pitch"] == 36)
            snare = sum(1 for n in drum_notes if n["pitch"] == 38)
            hat = sum(1 for n in drum_notes if n["pitch"] == 42)
            res.drums = len(drum_notes)
            res.log.append(_t("log_drums", n=len(drum_notes), kick=kick, snare=snare, hat=hat))
        except Exception as exc:
            res.log.append(_t("log_drum_fail", err=exc))
    check_cancel()

    # --- 3c. MIDI file ------------------------------------------------
    if opts.make_midi and (notes or drum_notes):
        try:
            mid = os.path.join(opts.out_dir, f"{base}.mid")
            transcribe.write_midi(notes, mid, res.bpm, drums=drum_notes or None)
            res.mid = mid
            res.log.append(f"MIDI：{mid}")
        except Exception as exc:
            res.log.append(_t("log_midi_fail", err=exc))
    check_cancel()

    # --- 4. FLP ------------------------------------------------------
    if opts.make_flp:
        report(_t("pr_flp"), 0.88)
        if not opts.template or not os.path.exists(opts.template):
            res.log.append(_t("log_no_template"))
        else:
            from . import flp as flp_mod

            try:
                duration = _duration(opts.audio)
                beats = duration / (60.0 / res.bpm)
                stem_objs = [flp_mod.Stem(names.get(k, k.title()), v) for k, v in stem_paths.items()]
                note_objs = [
                    flp_mod.NoteEvent(n.pitch, n.start_s / (60.0 / res.bpm),
                                      max(0.05, n.length_s / (60.0 / res.bpm)),
                                      n.velocity)
                    for n in notes
                ]
                out_flp = os.path.join(opts.out_dir, f"{base}.flp")
                drum_objs = [
                    flp_mod.NoteEvent(int(d["pitch"]), float(d["start_beats"]),
                                      float(d.get("length_beats", 0.25)),
                                      int(d.get("velocity", 100)))
                    for d in drum_notes
                ]
                info = flp_mod.build_project(
                    template=opts.template, out=out_flp, stems=stem_objs,
                    bpm=res.bpm, length_beats=beats, title=base,
                    notes=note_objs if notes else None,
                    drum_notes=drum_objs if drum_objs else None,
                )
                res.flp = out_flp
                res.log.append(_t("log_flp", path=out_flp, n=info["items"]))
            except Exception as exc:
                res.log.append(_t("log_flp_fail", err=exc))
                res.log.append(traceback.format_exc(limit=2))

    report(_t("pr_done"), 1.0)
    res.seconds = time.time() - t0
    res.log.append(_t("log_total", n="%.0f" % res.seconds))
    return res


def _duration(path: str) -> float:
    import soundfile as sf

    info = sf.info(path)
    return float(info.frames) / float(info.samplerate)


SUPPORTED = (".mp3", ".wav", ".flac", ".ogg", ".aiff", ".aif")


def _probe_audio(path: str) -> None:
    import soundfile as sf

    ext = os.path.splitext(path)[1].lower()
    if not os.path.exists(path):
        raise RuntimeError(_t("err_file_missing", path=path))
    if ext in (".m4a", ".aac", ".wma", ".mp4", ".opus"):
        raise RuntimeError(
            f"暂不支持 {ext} 格式（解码器不支持）。请先用任意转换工具把它转成 mp3 或 wav 再试。")
    try:
        info = sf.info(path)
    except Exception as exc:
        raise RuntimeError(
            f"读不了这个音频文件，可能已损坏或格式不受支持。\n"
            f"支持：mp3 / wav / flac / ogg。\n原始错误：{exc}") from exc
    if info.frames <= 0:
        raise RuntimeError(_t("err_no_audio_data"))
    if info.samplerate < 8000:
        raise RuntimeError(_t("err_sr_low", sr=info.samplerate))


def _read_mono(path: str):
    import soundfile as sf

    data, sr = sf.read(path, dtype="float32", always_2d=True)
    return data.mean(axis=1), int(sr)
