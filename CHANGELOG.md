# Changelog

本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [1.0.0] - 2026-10-31

### 新增

- **四轨分离** —— 基于 Demucs htdemucs，拆成人声 / 鼓 / 贝斯 / 其他
- **BPM 检测** —— 轻量节拍检测，实测误差 < 1 BPM
- **MIDI 转谱** —— Basic Pitch ONNX 模型，仅 225 KB
- **鼓点识别** —— 底鼓 / 军鼓 / 镲分类
- **FLP 生成** —— 通过 pyflp 生成可打开的 FL Studio 工程
- **图形界面** —— CustomTkinter + Windows Acrylic 液态玻璃风格
- **屏幕自适应** —— 窗口尺寸根据屏幕工作区自动调整
- **进度反馈** —— 显示百分比、已用时间、预计剩余

### 技术要点

- 分轨使用 PyTorch FP32 + 4 线程，比 ONNX FP16 快 37%
- MIDI 转谱绕过 TensorFlow，只用 onnxruntime（15 MB）
- 内存呈锯齿波动，无持续增长（分块处理）

### 已知限制

- 不支持 m4a / aac / wma / opus
- 分轨至少需要 1 GB 可用内存
- FLP 生成依赖 template.flp
- 复杂混音下 vocals 轨可能有乐器残留

---

## 版本说明

### v1.0.0 性能基准

测试环境：i5-7200U (2C4T) / 8 GB 内存 / Windows 10

| 音频长度 | 耗时 | 实时倍率 | 内存峰值 |
|:---:|:---:|:---:|:---:|
| 30 秒 | 52 秒 | 0.57× | 918 MB |
| 90 秒 | 117 秒 | 0.77× | 1081 MB |
| 5:15 全曲 | 363 秒 | 0.87× | 1598 MB |
