# Audio2FL

> 把 mp3 自动拆成四轨分轨，检测 BPM，转 MIDI，生成 FL Studio 工程。

**v1.1** — 中文 / English / 日本語 / 한국어 · GPU 加速 · 批量处理

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.x-EE4C2C?logo=pytorch&logoColor=white)](https://pytorch.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows-blue)](https://github.com/sy405/AUDIO/releases)

**[English](README.md) | [中文](README.zh.md)**

---

## 这是什么

把 mp3 自动拆成人声 / 鼓 / 贝斯 / 其他四条分轨，检测 BPM，把旋律转成 MIDI，最后生成可直接在 FL Studio 打开的 `.flp` 工程。

> 基于 AI 辅助开发，目前处于测试阶段，仅供学习交流。
>
> 全部处理在本机完成，不上传任何音频。

---

## 特性

- **四语言界面** —— 中文 / English / 日本語 / 한국어，右上角实时切换
- **GPU 自动加速** —— 检测到 CUDA 就用 GPU，没有则自动回落 CPU
- **批量处理** —— 选中一个文件夹，队列式处理其中所有音频
- **高质量模型** —— 可切换 `htdemucs_ft`（4 模型集成，慢约 4 倍，建议配 GPU）
- **随时取消** —— 处理途中可中止
- **模板自愈** —— 模板文件丢失时自动从程序内恢复
- **完全离线** —— 处理全程本机进行，不上传任何音频
- **开箱即用** —— 提供打包好的 exe，无需安装 Python / PyTorch / FFmpeg

---

## 下载

从 [Releases](https://github.com/sy405/AUDIO/releases) 下载：

| 文件 | 大小 | 说明 |
|---|---|---|
| **`Audio2FL-v1.1.exe`** | 203 MB | 单文件版，双击运行（首次启动约 30-60 秒，有启动画面）|
| `Audio2FL-v1.0-win64.zip` | 241 MB | v1.0 文件夹版，启动快 |
| `Audio2FL-v1.0-cpu-offline.zip` | 321 MB | v1.0 离线版（内置模型）|

**不需要安装任何依赖。**

---

## 从源码运行

需要 **Python 3.11+**（3.12 / 3.13 也可以）：

```bash
git clone https://github.com/sy405/AUDIO.git
cd AUDIO

python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux / macOS

pip install -r requirements.txt
python a2fl_entry.py
```

> **注意**：安装 PyTorch 时务必使用 CPU 索引源（已在 `requirements.txt` 中配置），否则会下载 2 GB+ 的 CUDA 版本。有 NVIDIA 显卡的用户可改装 CUDA 版以获得加速。

---

## 使用

### 图形界面

```bash
python a2fl_entry.py
```

或者直接把 mp3 拖到 `Audio2FL.exe` 图标上。

| 字段 | 说明 |
|---|---|
| **音频文件** | 支持 mp3 / wav / flac / ogg |
| **选文件夹** | 批量模式，处理该目录下所有音频 |
| **输出目录** | 默认 `音乐\Audio2FL` |
| **FL 模板** | 下拉选择，或点「浏览」手动指定 |
| **生成 .flp / .mid / 识别鼓点** | 按需勾选 |
| **高质量模型** | 勾选后使用 `htdemucs_ft`（慢 4 倍，建议有 GPU 时开）|
| **BPM** | 留空自动检测，不准可手动填 |
| **取消** | 处理途中随时中止 |

### 语言切换

右上角下拉框，切换后界面立即刷新，无需重启。

### 命令行

```bash
python -c "from app.toflp.pipeline import Options, run; \
run(Options(audio='song.mp3', out_dir='out', template='template.flp'))"
```

### 环境变量

| 变量 | 作用 |
|---|---|
| `A2FL_DEVICE` | 强制指定设备：`cpu` / `cuda` / `mps` |
| `HF_ENDPOINT` | HuggingFace 镜像地址（国内建议 `https://hf-mirror.com`）|

---

## 输出

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

## 技术选型

| 环节 | 方案 | 理由 |
|---|---|---|
| **分轨** | PyTorch Demucs | 目前质量与速度平衡最好的开源方案 |
| **MIDI** | Basic Pitch ONNX | 不依赖 TensorFlow，模型仅 225 KB |
| **BPM** | 自研节拍检测 | 轻量，实测误差 < 1 BPM |
| **FLP** | [pyflp](https://github.com/demberto/pyflp) | 纯 Python 读写 FL Studio 工程 |
| **GUI** | CustomTkinter + Windows Acrylic | 液态玻璃风格 |

### 为什么不用 ONNX 分轨

PyTorch 后端比 ONNX FP16 **更快**（在 x86 CPU 上 ONNX 需要转 FP32 再算）。代价是体积更大（PyTorch 运行时 518 MB），但换来明显的速度优势。

---

## 已知限制

- **不支持 m4a / aac / wma / opus** —— 解码器限制，请先转成 mp3 或 wav
- **内存需求** —— 分轨至少需要 1 GB 可用内存
- **FLP 依赖模板** —— 模板丢失时会自动恢复，但如果程序目录只读则可能失败
- **鼓点精度** —— 底鼓 / 军鼓 / 镲的分类有一定误差
- **人声残留** —— 复杂混音下 vocals 轨可能含有乐器残留
- **首次启动慢** —— 单文件版要解压约 500 MB 到临时目录，约 30-60 秒（有启动画面提示）
- **高质量模型需下载** —— 首次使用 `htdemucs_ft` 需下载约 320 MB

---

## 后续计划

| 方向 | 状态 |
|---|---|
| 批量处理 | ✅ v1.1 已完成 |
| 质量优化（htdemucs_ft）| ✅ v1.1 已完成 |
| 多语言界面 | ✅ v1.1 已完成（中 / 英 / 日 / 韩）|
| GPU 加速 | ✅ v1.1 已完成（自动检测 CUDA）|
| Windows 11 适配 | ⏳ 待验证 |
| 更多格式（m4a / aac / opus）| ⏳ 计划中 |
| API 接入 | ⏳ 可选，用于提升复杂混音的分离质量 |

---

## 常见问题

<details>
<summary><b>启动时进度条卡住不动</b></summary>

单文件版启动需要先解压约 500 MB 到临时目录，**首次启动约 30-60 秒**。启动画面上的进度条是装饰性的，不会真实反映进度。

第二次启动会快一些（系统缓存）。
</details>

<details>
<summary><b>提示「找不到 FL 模板工程」</b></summary>

正常情况下程序会自动从内部恢复模板。如果仍然失败，可能是程序目录没有写入权限——把程序放到用户目录（如桌面）再试。
</details>

<details>
<summary><b>提示「可用内存不足」</b></summary>

分轨至少需要 1 GB 可用内存。关掉浏览器、聊天软件等再试。
</details>

<details>
<summary><b>能用 GPU 加速吗</b></summary>

**可以。** 程序会自动检测 CUDA。当前发布的 exe 打包的是 **CPU 版 PyTorch**，想用 GPU 需要从源码运行并装 CUDA 版：

```bash
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
```

也可以强制指定设备：

```bash
set A2FL_DEVICE=cuda    # 或用 cpu
```
</details>

<details>
<summary><b>批量处理怎么用</b></summary>

点「选文件夹」，选中包含音频的目录，程序会扫描该目录下所有 mp3 / wav / flac / ogg，按顺序逐个处理，全部输出到同一个输出目录。

处理途中可点「取消」中止。
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
