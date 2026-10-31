# Audio2FL

> 把一首 mp3 一键拆成 FL Studio 工程。

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.15.0-EE4C2C?logo=pytorch&logoColor=white)](https://pytorch.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 这是什么

Audio2FL 接收一首音频，自动完成五件事：

1. **分轨** —— 拆成人声 / 鼓 / 贝斯 / 其他四条音轨
2. **测速** —— 检测 BPM
3. **转谱** —— 把旋律转成 MIDI 音符
4. **鼓点识别** —— 把鼓转成底鼓 / 军鼓 / 镲的 MIDI
5. **生成工程** —— 输出可直接在 FL Studio 打开的 `.flp` 文件

它**不会**还原原作者用的音色、和弦编配和混音参数。给你的是一个「可以接着往下做」的分轨工程，不是原工程复刻。

---

## 特性

- **完全离线** —— 处理全程本机进行，不上传任何音频
- **开箱即用** —— 提供打包好的 .exe，无需安装 Python / PyTorch / FFmpeg
- **速度优化** —— PyTorch FP32 + 4 线程，比 ONNX FP16 快 **37%**
- **液态玻璃界面** —— CustomTkinter + Windows Acrylic 毛玻璃效果
- **轻量 MIDI 模型** —— Basic Pitch ONNX 仅 **225 KB**，不依赖 TensorFlow

---

## 性能基准

在 **i5-7200U (2C4T) / 8 GB 内存** 上实测：

| 音频长度 | 耗时 | 实时倍率 | 内存峰值 |
|:---:|:---:|:---:|:---:|
| 30 秒 | 52 秒 | 0.57× | 918 MB |
| 90 秒 | 117 秒 | 0.77× | 1081 MB |
| 5:15 全曲 | 363 秒 | 0.87× | 1598 MB |

**经验公式**：`耗时 ≈ 20 秒 + 音频秒数 × 1.08`

> 内存呈锯齿波动，无持续增长（分块处理，每块释放）。

### 分离质量（BSSEval v4）

| 类别 | SDR | SIR | SAR |
|:---:|:---:|:---:|:---:|
| drums | **16.74 dB** | 31.10 dB | 17.68 dB |
| other | 10.45 dB | 20.62 dB | 10.59 dB |
| vocals | 6.46 dB | 13.85 dB | 8.00 dB |

*参考：Demucs 在 MUSDB18 官方测试集上 SDR 约 8–9 dB。*

---

## 安装

### 方式一：直接使用打包版（推荐）

从 [Releases](https://github.com/YOUR_USERNAME/Audio2FL/releases) 下载 `Audio2FL-v1.0-win64.zip`，解压后双击 `Audio2FL.exe`。

**不需要安装任何依赖。**

### 方式二：从源码运行

需要 **Python 3.11**（3.10 / 3.12 也可以）：

```bash
git clone https://github.com/YOUR_USERNAME/Audio2FL.git
cd Audio2FL

python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux / macOS

pip install -r requirements.txt
python a2fl_entry.py
```

> **注意**：安装 PyTorch 时务必使用 CPU 索引源（已在 `requirements.txt` 中配置），否则会下载 2 GB+ 的 CUDA 版本。

---

## 使用

### 图形界面

```bash
python a2fl_entry.py
```

或者把 mp3 直接拖到 `Audio2FL.exe` 图标上。

界面元素：

| 字段 | 说明 |
|---|---|
| **音频文件** | 支持 mp3 / wav / flac / ogg |
| **输出目录** | 默认 `音乐\Audio2FL` |
| **FL 模板** | 可选，留空自动用同目录 `template.flp` |
| **BPM** | 留空自动检测，不准可以手动填 |

### 命令行

```bash
python -c "from app.toflp.pipeline import Options, run; \
run(Options(audio='song.mp3', out_dir='out', template='template.flp'))"
```

---

## 输出

处理完成后，输出目录里有：

```
song.flp              FL 工程（四条分轨铺在 Playlist，BPM 已写入）
song.mid              MIDI（旋律轨 + 鼓轨）
song_stems/           四条 wav
├── drums.wav
├── bass.wav
├── other.wav
└── vocals.wav
```

**四条 wav 是最有价值的产出**，即使不用 FL Studio 也可以单独使用。

---

## 项目结构

```
Audio2FL/
├── app/
│   ├── a2fl_gui.py          GUI（CustomTkinter + Acrylic）
│   ├── audio_probe.py       音频探测工具
│   └── toflp/
│       ├── pipeline.py      主流程（PyTorch 分轨）
│       ├── flp.py           FLP 工程生成
│       ├── transcribe.py    MIDI 转谱（Basic Pitch ONNX）
│       ├── analysis.py      BPM 检测
│       ├── drums.py         鼓点识别
│       └── models/
│           └── nmp.onnx     MIDI 模型（225 KB）
├── tools/                   开发用评估工具
│   ├── eval_sdr.py          SDR/SIR/SAR 评估
│   ├── calibrate_ref.py     参考分轨校准
│   └── benchmark_demucs.py  性能基准测试
├── a2fl_entry.py            入口
├── template.flp             FL 工程模板
├── requirements.txt
├── LICENSE
└── README.md
```

---

## 技术选型

| 环节 | 方案 | 理由 |
|---|---|---|
| **分轨** | PyTorch Demucs (FP32, 4 线程) | 比 ONNX FP16 快 37% |
| **MIDI** | Basic Pitch ONNX | 不依赖 TensorFlow，模型仅 225 KB |
| **BPM** | 自研节拍检测 | 轻量，实测误差 < 1 BPM |
| **FLP** | [pyflp](https://github.com/demberto/pyflp) | 纯 Python 读写 FL Studio 工程 |
| **GUI** | CustomTkinter + Windows Acrylic | 液态玻璃风格 |

### 为什么不用 ONNX 分轨

| 后端 | 精度 | 线程 | 30 秒音频耗时 |
|---|---|:---:|---:|
| PyTorch | FP32 | 2 | 70.33 秒 |
| **PyTorch** | **FP32** | **4** | **52.21 秒** |
| ONNX Runtime | FP16 | 2 | 83 秒 |

两个因素叠加：线程数 2→4 快 26%；ONNX FP16 在 x86 CPU 上反而更慢（要转 FP32 再算）。

净效果：**PyTorch 4 线程比 ONNX 2 线程快 37%**。

代价是体积——ONNX 分轨模型 158 MB，PyTorch 运行时 518 MB。

---

## 已知限制

- **不支持 m4a / aac / wma / opus** —— 解码器限制，请先转成 mp3 或 wav
- **内存需求** —— 分轨至少需要 1 GB 可用内存
- **FLP 依赖模板** —— 必须提供 `template.flp`，缺失时跳过工程生成
- **鼓点精度** —— 底鼓 / 军鼓 / 镲的分类有一定误差
- **人声残留** —— 复杂混音下 vocals 轨可能含有乐器残留

---

## 常见问题

<details>
<summary><b>提示「找不到 FL 模板工程」</b></summary>

确认 `template.flp` 与 exe 在同一目录，或在界面「FL 模板」栏手动选择。

忽略也可以——只是跳过 .flp 生成，分轨和 MIDI 照常输出。
</details>

<details>
<summary><b>提示「可用内存不足」</b></summary>

分轨至少需要 1 GB 可用内存。关掉浏览器、聊天软件等再试。
</details>

<details>
<summary><b>处理速度能更快吗</b></summary>

当前已用 4 线程（实测比 2 线程快 26%）。换更强的 CPU 耗时大致成正比下降。

想要更快可以考虑：
- 降低 `overlap`（默认 0.1，改 0 会略快但有轻微接缝）
- 用 `htdemucs` 以外的轻量模型（质量会降）
</details>

<details>
<summary><b>能用 GPU 加速吗</b></summary>

可以。修改 `app/toflp/pipeline.py` 里的 `_separate()`：

```python
out = apply_model(model, wav.unsqueeze(0), device="cuda", ...)
```

需要先安装 CUDA 版 PyTorch。
</details>

---

## 致谢

本项目基于以下开源项目构建：

- [Demucs](https://github.com/facebookresearch/demucs) — Meta 的音源分离模型
- [Basic Pitch](https://github.com/spotify/basic-pitch) — Spotify 的音频转 MIDI 模型
- [pyflp](https://github.com/demberto/pyflp) — FL Studio 工程文件读写
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) — 现代化 Tkinter 封装

---

## License

[MIT](LICENSE)

---

## 免责声明

本工具仅供个人学习与创作使用。分离质量受原始音频影响很大，**不要期望完美还原**。

请尊重原作者的版权，不要将分离结果用于商业用途或二次发行。
