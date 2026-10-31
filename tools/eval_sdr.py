# -*- coding: utf-8 -*-
"""A 阶段: SDR/SIR/SAR 评估 (BSSEval v4 via museval)
参考: 官方分轨合并 (增益校准)
估计: Demucs 输出 (不做增益归一化)
类别置换: 显式关闭
"""
import sys
import wave
from pathlib import Path

import numpy as np
from museval.metrics import bss_eval

# 增益校准系数 (来自参考校准: +7.01 dB)
REF_GAIN = 2.24084

# 本轮评估的类别 (bass 为空, 排除)
TRACKS = ["vocals", "drums", "other"]

# 官方分轨 -> 类别映射
MAP = {
    "vocals": ["VOX LEAD", "BGVOX AAHH", "BGVOX ECHO", "BGVOX HARMONY"],
    "drums":  ["MAIN DRUMS", "HH", "DRUMS BREAK 1", "DRUMS BREAK 2"],
    "other":  ["BEEPS", "SWEEPS", "MINILOGUE SYNTH", "MICROCOSM EFFECT"],
}


def read_stereo(path):
    """读 WAV -> (samples, 2) float64, 保留立体声"""
    with wave.open(str(path), "rb") as w:
        sr = w.getframerate()
        ch = w.getnchannels()
        sw = w.getsampwidth()
        n = w.getnframes()
        raw = w.readframes(n)
    if sw != 2:
        raise ValueError(f"{path.name}: 需要 16-bit")
    data = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    if ch == 1:
        data = np.stack([data, data], axis=1)
    else:
        data = data.reshape(-1, ch)[:, :2]
    return data, sr


def rms_db(x):
    v = float(np.sqrt(np.mean(x ** 2)))
    return 20.0 * np.log10(v) if v > 1e-12 else -120.0


ref_dir = Path(sys.argv[1])
dem_dir = Path(sys.argv[2])

print("=" * 74)
print("  A 阶段: SDR / SIR / SAR (BSSEval v4)")
print("=" * 74)

# ---------- 加载参考 ----------
print()
print("【参考信号】(官方分轨合并, 立体声)")
ref_sources = []
for track in TRACKS:
    parts = []
    for pname in MAP[track]:
        p = ref_dir / f"1.Hydrogen_Stem_{pname}.wav"
        if p.exists():
            a, sr = read_stereo(p)
            parts.append(a)
    if not parts:
        raise RuntimeError(f"{track}: 没有找到分轨")
    n = min(len(x) for x in parts)
    merged = np.sum([x[:n] for x in parts], axis=0)
    ref_sources.append(merged)
    print(f"  {track:<10} {len(merged)/sr:7.3f}s  RMS {rms_db(merged):7.2f} dBFS  ({len(parts)} 条合并)")

# 时长统一
n_min = min(len(x) for x in ref_sources)
ref_arr = np.stack([x[:n_min] for x in ref_sources], axis=0)  # (nsrc, nsamp, 2)

# ---------- 加载估计 ----------
print()
print("【估计信号】(Demucs 输出, 原始电平, 未归一化)")
est_sources = []
for track in TRACKS:
    p = dem_dir / f"{track}.wav"
    if not p.exists():
        raise RuntimeError(f"{track}: Demucs 输出缺失")
    a, sr_e = read_stereo(p)
    est_sources.append(a)
    print(f"  {track:<10} {len(a)/sr_e:7.3f}s  RMS {rms_db(a):7.2f} dBFS")

n_est = min(len(x) for x in est_sources)
n_final = min(n_min, n_est)
est_arr = np.stack([x[:n_final] for x in est_sources], axis=0)
ref_arr = ref_arr[:, :n_final, :]

# ---------- 增益校准 (仅参考) ----------
print()
print("【增益校准】")
print(f"  参考乘以 {REF_GAIN} ({(20*np.log10(REF_GAIN)):+.2f} dB)")
print(f"  校准前参考 RMS: {rms_db(ref_arr):7.2f} dBFS")
ref_arr = ref_arr * REF_GAIN
print(f"  校准后参考 RMS: {rms_db(ref_arr):7.2f} dBFS")
print("  Demucs 输出: 不做任何调整")

# ---------- 形状确认 ----------
print()
print("【数组形状】")
print(f"  reference: {ref_arr.shape}  (sources, samples, channels)")
print(f"  estimate:  {est_arr.shape}  (sources, samples, channels)")
print(f"  时长: {n_final/sr:.4f}s @ {sr}Hz")

# ---------- 评估 ----------
print()
print("=" * 74)
print("  运行 bss_eval (compute_permutation=False)")
print("=" * 74)

sdr, isr, sir, sar, perm = bss_eval(
    ref_arr,
    est_arr,
    window=2 * sr,
    hop=1 * sr,
    compute_permutation=False,   # 关键: 不允许交换类别
    framewise_filters=False,
    bsseval_sources_version=False,
)

def describe(name, arr):
    a = np.asarray(arr, dtype=float)
    flat = a[np.isfinite(a)]
    nan_c = int(np.isnan(a).sum())
    inf_c = int(np.isinf(a).sum())
    print(f"\n  {name}: shape={a.shape}")
    if flat.size:
        print(f"    均值 {flat.mean():7.2f} dB   中位数 {np.median(flat):7.2f} dB")
        print(f"    最小 {flat.min():7.2f} dB   最大 {flat.max():7.2f} dB")
    else:
        print("    无有限值")
    if nan_c or inf_c:
        print(f"    ! NaN={nan_c}  Inf={inf_c}")
    return flat

print()
print("-" * 74)
print(f"  {'类别':<10}{'SDR':>10}{'ISR':>10}{'SIR':>10}{'SAR':>10}")
print("-" * 74)
for i, track in enumerate(TRACKS):
    sdr_i = sdr[i][np.isfinite(sdr[i])]
    isr_i = isr[i][np.isfinite(isr[i])]
    sir_i = sir[i][np.isfinite(sir[i])]
    sar_i = sar[i][np.isfinite(sar[i])]
    fmt = lambda x: f"{x.mean():9.2f}" if x.size else "      nan"
    print(f"  {track:<10}{fmt(sdr_i)}{fmt(isr_i)}{fmt(sir_i)}{fmt(sar_i)}")

print()
print("【统计详情】")
describe("SDR", sdr)
describe("ISR", isr)
describe("SIR", sir)
describe("SAR", sar)

print()
print(f"  置换矩阵 perm: {perm}")

print()
print("=" * 74)
print("  说明")
print("=" * 74)
print(f"  评估帧数: SDR shape[1] = {np.asarray(sdr).shape[1]}")
print(f"  window={2*sr} 样本 ({2.0}s), hop={sr} 样本 ({1.0}s)")
print("  compute_permutation=False: 强制 vocals->vocals, drums->drums, other->other")
