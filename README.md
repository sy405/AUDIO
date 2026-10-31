# Audio2FL

> 把 mp3 自动拆成四轨分轨，检测 BPM，转 MIDI，生成 FL Studio 工程。

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.15.0-EE4C2C?logo=pytorch&logoColor=white)](https://pytorch.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 这是什么

把 mp3 自动拆成人声 / 鼓 / 贝斯 / 其他四条分轨，检测 BPM，把旋律转成 MIDI，最后生成可直接在 FL Studio 打开的 `.flp` 工程。

> 基于 AI 辅助开发，目前处于初步测试阶段，仅供学习交流。
>
> 全部处理在本机完成，不上传任何音频。

---

## 后续计划

| 方向 | 说明 |
|---|---|
| **Windows 11 适配** | 当前在 Windows 10 测试通过，后续验证 Win11 的兼容性与视觉表现 |
| **批量处理** | 支持选择整个文件夹，队列式处理多个文件 |
| **API 接入** | 可选接入云端分离模型，提升复杂混音的分离准确性 |
| **质量优化** | 增加高精度模型选项（`htdemucs_ft` 等），牺牲速度换质量 |
| **更多格式** | 支持 m4a / aac / opus 等输入格式 |

---

## 特性

- **完全离线** —— 处理全程本机进行，不上传任何音频
- **开箱即用** —— 提供打包好的 .exe，无需安装 Python / PyTorch / FFmpeg
- **速度优化** —— PyTorch FP32 + 4 线程，比 ONNX FP16 快 **37%**
- **液态玻璃界面** —— CustomTkinter + Windows Acrylic 毛玻璃效果
- **轻量 MIDI 模型** —— Basic Pitch ONNX 仅 **225 KB**，不依赖 TensorFlow

---

## 安装

### 方式一：直接使用打包版（推荐）

从 [Releases](https://github.com/sy405/AUDIO/releases) 下载 `Audio2FL-v1.0-win64.zip`，解压后双击 `Audio2FL.exe`。

**不需要安装任何依赖。**

### 方式二：从源码运行

需要 **Python 3.11**（3.10 / 3.12 也可以）：

```bash
git clone https://github.com/sy405/AUDIO.git
cd AUDIO

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
├── CHANGELOG.md
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
- **单文件处理** —— 目前一次只能处理一个音频

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
