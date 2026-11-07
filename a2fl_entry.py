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


def _close_splash():
    """关闭 PyInstaller 启动画面。

    --splash 生成的画面必须显式关闭，否则会一直留在桌面上。
    """
    try:
        import pyi_splash  # type: ignore
        pyi_splash.close()
    except Exception:
        pass


def main():
    base = _setup_paths()
    try:
        from app.a2fl_gui import main as gui_main
    except ImportError:
        from a2fl_gui import main as gui_main

    # 兜底：如果 GUI 里没来得及关，这里再关一次
    try:
        from app.a2fl_gui import App as _App  # noqa: F401
    except Exception:
        pass

    _close_splash()
    return gui_main()


if __name__ == "__main__":
    raise SystemExit(main())
