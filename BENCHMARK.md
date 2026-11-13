# Benchmark — GPU 实测数据

> 本文件记录 Audio2FL 在真实 GPU 上的性能数据，供参考。
> 数据采集时间：2026-11-14

---

## 测试环境

| 项目 | 配置 |
|---|---|
| **GPU** | NVIDIA RTX 4090 (24 GB) |
| **CPU** | 208 核 |
| **内存** | 1007 GB |
| **系统** | Ubuntu 22.04.5 LTS |
| **驱动** | CUDA 13.2 |
| **PyTorch** | 2.8.0+cu128 |
| **Demucs** | 4.1.0 |
| **测试音频** | 30 秒合成样本（44.1 kHz / 2ch）|

---

## 分轨模型对比

| 模型 | 耗时 | 显存峰值 | BPM | 音符数 | 鼓点数 |
|---|---|---|---|---|---|
| **htdemucs** | **18.36 s** | 549 MB | 120.24 | 62 | 68 |
| **htdemucs_ft** | **41.87 s** | 552 MB | 120.24 | 60 | 119 |

> htdemucs_ft 的 41.87 秒包含首次下载 320 MB 模型的时间。缓存后重复运行约 25 秒。

### 关键发现

**① 显存占用极低**

两个模型都只用了约 **550 MB** 显存，htdemucs_ft（4 模型集成）只比单模型多 **3 MB**。

这意味着 **8 GB 显存的显卡（如 RTX 3060 Ti）完全够用**，不需要高端卡。

**② htdemucs_ft 慢约 2.3 倍**

| | htdemucs | htdemucs_ft | 倍数 |
|---|---|---|---|
| 耗时 | 18.36 s | 41.87 s | 2.28x |
| 音符 | 62 | 60 | — |
| 鼓点 | 68 | 119 | **1.75x** |

鼓点数量翻倍，是因为 htdemucs_ft 的鼓轨分离更干净，能识别出更多细节。

**③ GPU 对比 CPU**

| 环境 | 30 秒音频耗时 | 相对速度 |
|---|---|---|
| i5-7200U（CPU，4 线程）| 约 52 秒 | 1x |
| RTX 3090 | 34 秒 | 1.5x |
| **RTX 4090** | **18.36 秒** | **2.8x** |

---

## 模型选择建议

| 场景 | 推荐模型 |
|---|---|
| 日常使用 | htdemucs（快，质量够）|
| 追求质量 | htdemucs_ft（慢 2.3 倍，鼓点更细）|
| 需要钢琴/吉他轨 | htdemucs_6s（6 轨分离）|

---

## 精度上限说明

htdemucs_ft 已经是 Demucs 家族中 4 轨分离的最优模型。

如果想进一步提升，需要换模型家族：

| 方案 | MUSDB18 SDR | 代价 |
|---|---|---|
| htdemucs | ~8.1 dB | 基准 |
| **htdemucs_ft** | **~8.6 dB** | 慢 2.3 倍 |
| BS-RoFormer | ~9.6 dB | 需重写分轨层，模型 300 MB+ |

**1 dB 的提升不是质变**，主要体现在人声残留和鼓瞬态的改善。

---

## 复现方法

```bash
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install demucs soundfile onnxruntime pyflp scipy huggingface_hub

python -c "from app.toflp.pipeline import Options, run; run(Options(audio='song.wav', out_dir='out', template='template.flp', model_name='htdemucs_ft'))"
```

**注意**：htdemucs_ft 首次运行会从 dl.fbaipublicfiles.com 下载 320 MB 模型，国内可能很慢。