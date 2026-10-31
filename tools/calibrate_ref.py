# -*- coding: utf-8 -*-
"""参考分轨校准: 检查官方分轨之和与 Master 的
   时长 / 时间偏移 / 相关性 / 最佳增益 / 残差
"""
import sys
import wave
from pathlib import Path

import numpy as np


def read_wav(path):
    with wave.open(str(path), "rb") as w:
        sr = w.getframerate()
        ch = w.getnchannels()
        sw = w.getsampwidth()
        n = w.getnframes()
        raw = w.readframes(n)
    if sw != 2:
        raise ValueError(f"{path.name}: 需要 16-bit")
    data = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    if ch > 1:
        data = data.reshape(-1, ch).mean(axis=1)
    return data, sr


def dbfs(x):
    return 20.0 * np.log10(x) if x > 1e-12 else -120.0


def rms(x):
    return float(np.sqrt(np.mean(x ** 2)))


base = Path(sys.argv[1])

# ---------------------------------------------------------------
# 加载
# ---------------------------------------------------------------
master, sr = read_wav(base / "1.Hydrogen_Master.wav")
print("=" * 72)
print("  参考校准: 官方分轨之和 vs Master")
print("=" * 72)
print(f"  Master: {len(master)/sr:.4f}s  {sr}Hz  RMS {dbfs(rms(master)):.2f} dBFS")

stem_files = sorted(base.glob("1.Hydrogen_Stem_*.wav"))
stems = {}
for p in stem_files:
    a, _ = read_wav(p)
    stems[p.stem.replace("1.Hydrogen_Stem_", "")] = a
print(f"  分轨数: {len(stems)}")
for name, a in stems.items():
    tag = "静音" if rms(a) < 1e-5 else f"{dbfs(rms(a)):7.2f}"
    print(f"    {name:<22} {len(a)/sr:8.4f}s  {tag}")

# ---------------------------------------------------------------
# 时长对齐
# ---------------------------------------------------------------
n_min = min(len(x) for x in stems.values())
n_master = len(master)
n = min(n_min, n_master)
print()
print("-" * 72)
print("  1. 时长对齐")
print("-" * 72)
print(f"  Master 长度:  {n_master} 样本 ({n_master/sr:.4f}s)")
print(f"  分轨长度:     {n_min} 样本 ({n_min/sr:.4f}s)")
print(f"  差值:         {n_master - n_min} 样本 ({(n_master-n_min)/sr*1000:+.1f} ms)")

m = master[:n]
s_sum = np.sum([a[:n] for a in stems.values()], axis=0)

# ---------------------------------------------------------------
# 2. 时间偏移搜索
# ---------------------------------------------------------------
print()
print("-" * 72)
print("  2. 时间偏移 (互相关, ±2000 样本 = ±45ms)")
print("-" * 72)

max_lag = 2000
best_lag, best_corr = 0, -2.0
# 用子采样加速
step = 4
m_ds = m[::step]
s_ds = s_sum[::step]
max_lag_ds = max_lag // step

for lag in range(-max_lag_ds, max_lag_ds + 1):
    if lag >= 0:
        a = m_ds[lag:]
        b = s_ds[:len(a)]
    else:
        b = s_ds[-lag:]
        a = m_ds[:len(b)]
    L = min(len(a), len(b))
    a, b = a[:L], b[:L]
    den = np.sqrt(np.sum(a*a) * np.sum(b*b))
    if den < 1e-15:
        continue
    c = float(np.sum(a*b) / den)
    if c > best_corr:
        best_corr, best_lag = c, lag * step

print(f"  最佳 lag: {best_lag} 样本 ({best_lag/sr*1000:+.2f} ms)")
print(f"  该 lag 下零延迟相关系数: {best_corr:.5f}")
print(f"  (lag=0 时相关系数: 计算中...)")

# lag=0 的相关
den0 = np.sqrt(np.sum(m*m) * np.sum(s_sum*s_sum))
corr0 = float(np.sum(m*s_sum) / den0) if den0 > 1e-15 else 0.0
print(f"  lag=0 相关系数:          {corr0:.5f}")

# ---------------------------------------------------------------
# 3. 最佳增益 (最小二乘)
# ---------------------------------------------------------------
print()
print("-" * 72)
print("  3. 最佳增益 (最小二乘: gain = <m,s>/<s,s>)")
print("-" * 72)

denom = float(np.sum(s_sum * s_sum))
gain = float(np.sum(m * s_sum) / denom) if denom > 1e-15 else 0.0
gain_db = 20 * np.log10(abs(gain)) if gain != 0 else -120

print(f"  线性增益: {gain:.5f}")
print(f"  增益 dB:  {gain_db:+.2f} dB")
print(f"  Master RMS:  {dbfs(rms(m)):7.2f} dBFS")
print(f"  分轨和 RMS:  {dbfs(rms(s_sum)):7.2f} dBFS")
print(f"  RMS 差:      {dbfs(rms(m)) - dbfs(rms(s_sum)):+.2f} dB")

# ---------------------------------------------------------------
# 4. 校准后残差
# ---------------------------------------------------------------
print()
print("-" * 72)
print("  4. 校准后残差")
print("-" * 72)

calibrated = gain * s_sum
residual = m - calibrated

print(f"  校准后 RMS: {dbfs(rms(calibrated)):7.2f} dBFS")
print(f"  残差 RMS:   {dbfs(rms(residual)):7.2f} dBFS")
print(f"  残差/Master: {dbfs(rms(residual)) - dbfs(rms(m)):+.2f} dB")

# 校准后相关系数
den_c = np.sqrt(np.sum(m*m) * np.sum(calibrated*calibrated))
corr_cal = float(np.sum(m*calibrated) / den_c) if den_c > 1e-15 else 0.0
print(f"  校准后相关系数: {corr_cal:.5f}")

# 能量解释度 (R^2)
ss_tot = float(np.sum((m - np.mean(m))**2))
ss_res = float(np.sum(residual**2))
r2 = 1 - ss_res/ss_tot if ss_tot > 0 else 0
print(f"  R^2 (能量解释度): {r2:.5f}")
print(f"  未解释能量占比:   {(1-r2)*100:.2f}%")

# ---------------------------------------------------------------
# 结论
# ---------------------------------------------------------------
print()
print("=" * 72)
print("  判读")
print("=" * 72)
if abs(best_lag) <= 2:
    print("  ✓ 时间基本对齐 (偏移 <= 2 样本)")
else:
    print(f"  ! 存在 {best_lag} 样本偏移 ({best_lag/sr*1000:.1f} ms)")

if r2 > 0.95:
    print(f"  ✓ 分轨完整解释混音 (R^2={r2:.4f} > 0.95), 可直接作参考")
elif r2 > 0.85:
    print(f"  ~ 分轨大部分解释混音 (R^2={r2:.4f}), 有额外处理")
else:
    print(f"  ✗ 分轨不能解释混音 (R^2={r2:.4f}), 不适合直接作参考")

if abs(gain_db) > 0.5:
    print(f"  ! 存在 {gain_db:+.2f} dB 系统增益差, 计算 SDR 前必须补偿")
else:
    print(f"  ✓ 增益基本匹配 ({gain_db:+.2f} dB)")
