# -*- coding: utf-8 -*-
"""Demucs 线程数基准测试"""
import sys
import time
import torch
from demucs.separate import main


def main_entry():
    if len(sys.argv) != 4:
        print("用法: python benchmark_demucs.py <线程数> <输入文件> <输出目录>")
        raise SystemExit(1)

    threads = int(sys.argv[1])
    input_file = sys.argv[2]
    output_dir = sys.argv[3]

    torch.set_num_threads(threads)
    print("=" * 60)
    print(f"PyTorch 线程数: {torch.get_num_threads()}")
    print(f"输入文件: {input_file}")
    print(f"输出目录: {output_dir}")
    print("=" * 60)

    sys.argv = [
        "demucs",
        "-n", "htdemucs",
        "--shifts", "0",
        "--overlap", "0.1",
        "--out", output_dir,
        input_file,
    ]

    start = time.perf_counter()
    try:
        main()
    finally:
        elapsed = time.perf_counter() - start
        print()
        print("=" * 60)
        print(f"总耗时: {elapsed:.2f} 秒")
        print("=" * 60)


if __name__ == "__main__":
    main_entry()
