from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MUSIC = ROOT / "test_music"
OUT = ROOT / "output"
OUT.mkdir(exist_ok=True)

def main():
    print("Audio2FL - 第一阶段音频管线检查")
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    print("FFmpeg:", ffmpeg or "未检测到")
    print("FFprobe:", ffprobe or "未检测到")
    tracks = [p for p in MUSIC.glob("*") if p.suffix.lower() in {".mp3", ".wav", ".flac", ".m4a"}]
    if not tracks:
        print(f"\n尚未找到测试音频。请将 MP3/WAV 放入：{MUSIC}")
        print("然后再次运行 Start_Audio2FL.bat。")
        return
    if not ffmpeg or not ffprobe:
        print("\n检测到音频文件，但缺少 FFmpeg/FFprobe，暂时无法可靠读取 MP3。")
        print("请安装 FFmpeg 后重新打开终端。")
        return
    for src in tracks:
        print(f"\n检查：{src.name}")
        cmd = [ffprobe, "-v", "error", "-show_entries",
               "format=duration,format_name:stream=codec_name,sample_rate,channels",
               "-of", "default=noprint_wrappers=1", str(src)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode:
            print("读取失败：", result.stderr.strip())
            continue
        print(result.stdout.strip())
        wav = OUT / (src.stem + "_audio2fl.wav")
        convert = [ffmpeg, "-y", "-i", str(src), "-vn", "-acodec", "pcm_s16le",
                   "-ar", "44100", str(wav)]
        done = subprocess.run(convert, capture_output=True, text=True)
        if done.returncode == 0 and wav.exists() and wav.stat().st_size > 44:
            print("WAV 转换成功：", wav)
        else:
            print("转换失败：", done.stderr[-1200:])
    print("\n基础检查结束。当前版本不会上传音频，也不会调用云端 API。")

if __name__ == "__main__":
    main()
