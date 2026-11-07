# -*- coding: utf-8 -*-
"""轻量国际化：从 app/locales/*.json 加载文案。

用法：
    from app.i18n import I18N
    i18n = I18N()                 # 自动选系统语言
    i18n.set("ja")                # 切换
    i18n.t("btn_start")           # 取文案
    i18n.t("status_done", n=12)   # 带格式化
"""
from __future__ import annotations

import json
import os
import sys

# 支持的语言（顺序即界面下拉框顺序）
LANGS = ("zh", "en", "ja", "ko")

# 语言代码 -> 展示名（不依赖 json，供下拉框用）
LANG_NAMES = {
    "zh": "中文",
    "en": "English",
    "ja": "日本語",
    "ko": "한국어",
}

_FALLBACK = "zh"


def _resolve_locale_dir() -> str:
    """兼容源码运行与 PyInstaller 打包。"""
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, "locales"),                       # 源码布局
        os.path.join(here, "_internal", "app", "locales"),   # onedir 兜底
    ]
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.insert(0, os.path.join(meipass, "app", "locales"))
    exe_dir = os.path.dirname(sys.executable)
    candidates.append(os.path.join(exe_dir, "_internal", "app", "locales"))

    for c in candidates:
        if os.path.isdir(c) and os.path.isfile(os.path.join(c, "zh.json")):
            return c
    return candidates[0]


def detect_system_lang() -> str:
    """按系统语言猜测；猜不到回落到中文。"""
    try:
        import locale
        loc = (locale.getdefaultlocale()[0] or "").lower()
    except Exception:
        loc = ""
    if loc.startswith("zh"):
        return "zh"
    if loc.startswith("ja"):
        return "ja"
    if loc.startswith("ko"):
        return "ko"
    if loc.startswith("en"):
        return "en"
    return _FALLBACK


class I18N:
    """极简翻译器：所有语言一次性载入，切换零成本。"""

    def __init__(self, lang: str | None = None):
        self._dir = _resolve_locale_dir()
        self._data: dict[str, dict] = {}
        self._load_all()
        self.lang = lang if lang in self._data else detect_system_lang()
        if self.lang not in self._data:
            self.lang = _FALLBACK

    def _load_all(self) -> None:
        for code in LANGS:
            path = os.path.join(self._dir, code + ".json")
            if not os.path.isfile(path):
                continue
            try:
                with open(path, encoding="utf-8") as f:
                    self._data[code] = json.load(f)
            except Exception:
                continue

    # -- 对外接口 ------------------------------------------------------
    @property
    def available(self) -> list[str]:
        """已成功加载的语言代码。"""
        return [c for c in LANGS if c in self._data]

    def name(self, code: str | None = None) -> str:
        return LANG_NAMES.get(code or self.lang, (code or self.lang))

    def set(self, lang: str) -> bool:
        if lang in self._data:
            self.lang = lang
            return True
        return False

    def t(self, key: str, **fmt) -> str:
        """取文案；缺失时回落到中文，再缺就返回 key。"""
        table = self._data.get(self.lang, {})
        text = table.get(key)
        if text is None:
            text = self._data.get(_FALLBACK, {}).get(key, key)
        if fmt:
            try:
                return text.format(**fmt)
            except Exception:
                return text
        return text

    def all_lang_names(self) -> list[tuple[str, str]]:
        """给下拉框用：[('zh','中文'), ('en','English'), ...]"""
        return [(c, LANG_NAMES[c]) for c in self.available]


# 全局单例（GUI 直接用）
_instance: I18N | None = None


def get_i18n(lang: str | None = None) -> I18N:
    global _instance
    if _instance is None:
        _instance = I18N(lang)
    elif lang and lang in _instance.available:
        _instance.set(lang)
    return _instance
