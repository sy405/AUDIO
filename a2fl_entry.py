# -*- coding: utf-8 -*-
"""Audio2FL 入口 (支持 PyInstaller 打包)"""
import os
import sys


def _setup_paths():
    """保证 app 包可导入"""
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
        if base not in sys.path:
            sys.path.insert(0, base)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if base not in sys.path:
            sys.path.insert(0, base)
    return base


def main():
    base = _setup_paths()
    try:
        from app.a2fl_gui import main as gui_main
    except ImportError:
        from a2fl_gui import main as gui_main
    return gui_main()


if __name__ == "__main__":
    raise SystemExit(main())
