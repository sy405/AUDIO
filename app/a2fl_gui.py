# -*- coding: utf-8 -*-
"""Audio2FL - mp3 一键拆成 FL Studio 工程

Liquid Glass GUI (CustomTkinter + Windows Acrylic)
"""
from __future__ import annotations

import ctypes
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

# ----------------------------------------------------------------------
COL = {
    "bg":         "#0B0F1A",
    "card":       "#161C2E",
    "card_hi":    "#1E263C",
    "border":     "#2E3A56",
    "primary":    "#5B8DEF",
    "primary_hi": "#7BA5FF",
    "success":    "#3DD68C",
    "warn":       "#FFB020",
    "error":      "#FF5C5C",
    "text":       "#EEF2FA",
    "muted":      "#9AA3B8",
    "dim":        "#5C657A",
}

FONT_BOLD  = ("Microsoft YaHei UI", 15, "bold")
FONT_TITLE = ("Microsoft YaHei UI", 24, "bold")
FONT_SM    = ("Microsoft YaHei UI", 12)
FONT_MONO  = ("Consolas", 10)


def enable_acrylic(hwnd: int, tint: int = 0xE00B0F1A) -> bool:
    """Windows 10/11 亚克力模糊"""
    try:
        class AP(ctypes.Structure):
            _fields_ = [("AccentState", ctypes.c_int), ("AccentFlags", ctypes.c_int),
                        ("GradientColor", ctypes.c_uint), ("AnimationId", ctypes.c_int)]
        class WD(ctypes.Structure):
            _fields_ = [("Attribute", ctypes.c_int), ("Data", ctypes.POINTER(AP)),
                        ("SizeOfData", ctypes.c_size_t)]
        a = AP(); a.AccentState = 4; a.AccentFlags = 2; a.GradientColor = tint
        d = WD(); d.Attribute = 19; d.SizeOfData = ctypes.sizeof(a); d.Data = ctypes.pointer(a)
        return bool(ctypes.windll.user32.SetWindowCompositionAttribute(hwnd, ctypes.byref(d)))
    except Exception:
        return False


def dark_titlebar(hwnd: int) -> None:
    try:
        v = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(v), ctypes.sizeof(v))
    except Exception:
        pass


def abgr(hexcolor: str, alpha: int = 0xE0) -> int:
    h = hexcolor.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (alpha << 24) | (b << 16) | (g << 8) | r


class Card(ctk.CTkFrame):
    def __init__(self, master, **kw):
        super().__init__(master, fg_color=COL["card"], corner_radius=14,
                         border_width=1, border_color=COL["border"], **kw)


class App(ctk.CTk):
    def __init__(self, audio=None):
        ctk.set_appearance_mode("dark")
        super().__init__()
        self.title("Audio2FL  ·  mp3 一键拆成 FL Studio 工程")

        # 适配屏幕: 工作区 1366x728 -> 窗口 920x700
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w = min(920, sw - 80)
        h = min(700, sh - 80)
        x = (sw - w) // 2
        y = max(0, (sh - h) // 2 - 20)
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(820, 600)
        self.configure(fg_color=COL["bg"])

        self._busy = False
        self._t0 = 0.0

        self.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
        dark_titlebar(hwnd)
        enable_acrylic(hwnd, tint=abgr("#0B0F1A", 0xE8))

        self._build()
        if audio:
            self.v_audio.set(audio)

    # ------------------------------------------------------------------
    def _build(self):
        self.grid_rowconfigure(4, weight=1)
        self.grid_columnconfigure(0, weight=1)
        pad = {"padx": 20}

        # ---- 标题 ----
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", pady=(14, 10), **pad)
        ctk.CTkLabel(head, text="Audio2FL", font=FONT_TITLE,
                     text_color=COL["text"]).pack(side="left")
        ctk.CTkLabel(head, text="   mp3 → 分轨 · 转谱 · FL Studio 工程",
                     font=FONT_SM, text_color=COL["muted"]).pack(side="left", pady=(6, 0))

        # ---- 文件卡片 ----
        c1 = Card(self)
        c1.grid(row=1, column=0, sticky="ew", pady=(0, 10), **pad)
        c1.grid_columnconfigure(1, weight=1)

        self.v_audio = tk.StringVar()
        self.v_out = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "Music", "Audio2FL"))
        self.v_tpl = tk.StringVar()

        for r, (label, var, cmd, ph) in enumerate([
            ("音频文件", self.v_audio, self._pick_audio, "选择 mp3 / wav / flac"),
            ("输出目录", self.v_out,   self._pick_out,   ""),
            ("FL 模板",  self.v_tpl,   self._pick_tpl,   "可选：默认用同目录 template.flp"),
        ]):
            ctk.CTkLabel(c1, text=label, font=FONT_SM, text_color=COL["muted"],
                         width=72, anchor="w").grid(row=r, column=0, padx=(16, 6), pady=7, sticky="w")
            ctk.CTkEntry(c1, textvariable=var, height=34, corner_radius=8,
                         fg_color=COL["card_hi"], border_color=COL["border"],
                         text_color=COL["text"], font=FONT_SM,
                         placeholder_text=ph).grid(row=r, column=1, sticky="ew", pady=7)
            ctk.CTkButton(c1, text="浏览", command=cmd, width=60, height=34, corner_radius=8,
                          fg_color=COL["card_hi"], hover_color=COL["border"],
                          text_color=COL["text"], font=FONT_SM,
                          border_width=1, border_color=COL["border"]
                          ).grid(row=r, column=2, padx=(6, 16), pady=7)

        # ---- 选项 ----
        c2 = Card(self)
        c2.grid(row=2, column=0, sticky="ew", pady=(0, 10), **pad)
        opt = ctk.CTkFrame(c2, fg_color="transparent")
        opt.pack(fill="x", padx=16, pady=11)

        self.v_flp = tk.BooleanVar(value=True)
        self.v_mid = tk.BooleanVar(value=True)
        self.v_drum = tk.BooleanVar(value=True)
        self.v_bpm = tk.StringVar()

        for text, var in (("生成 .flp", self.v_flp), ("生成 .mid", self.v_mid), ("识别鼓点", self.v_drum)):
            ctk.CTkCheckBox(opt, text=text, variable=var, font=FONT_SM,
                            text_color=COL["text"], fg_color=COL["primary"],
                            hover_color=COL["primary_hi"], border_color=COL["border"],
                            corner_radius=5, checkbox_width=18, checkbox_height=18,
                            ).pack(side="left", padx=(0, 18))

        ctk.CTkLabel(opt, text="BPM", font=FONT_SM,
                     text_color=COL["muted"]).pack(side="left", padx=(14, 5))
        ctk.CTkEntry(opt, textvariable=self.v_bpm, width=70, height=30, corner_radius=8,
                     fg_color=COL["card_hi"], border_color=COL["border"],
                     text_color=COL["text"], font=FONT_SM,
                     placeholder_text="自动").pack(side="left")
        ctk.CTkLabel(opt, text="留空自动", font=FONT_SM,
                     text_color=COL["dim"]).pack(side="left", padx=(6, 0))

        # ---- 按钮 + 进度 ----
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=3, column=0, sticky="ew", pady=(0, 8), **pad)
        bar.grid_columnconfigure(0, weight=1)

        self.btn = ctk.CTkButton(bar, text="▶   开始处理", command=self._run,
                                 height=46, corner_radius=12, font=FONT_BOLD,
                                 fg_color=COL["primary"], hover_color=COL["primary_hi"],
                                 text_color="#FFFFFF")
        self.btn.grid(row=0, column=0, sticky="ew")

        self.pbar = ctk.CTkProgressBar(bar, height=5, corner_radius=3,
                                       fg_color=COL["card"], progress_color=COL["primary"])
        self.pbar.grid(row=1, column=0, sticky="ew", pady=(8, 3))
        self.pbar.set(0)

        self.lbl = ctk.CTkLabel(bar, text="就绪", font=FONT_SM,
                                text_color=COL["muted"], anchor="w")
        self.lbl.grid(row=2, column=0, sticky="w")

        # ---- 日志 ----
        c3 = Card(self)
        c3.grid(row=4, column=0, sticky="nsew", pady=(0, 10), **pad)
        c3.grid_rowconfigure(0, weight=1)
        c3.grid_columnconfigure(0, weight=1)

        self.log = ctk.CTkTextbox(c3, font=FONT_MONO, fg_color="#070A12",
                                  text_color=COL["text"], corner_radius=10,
                                  border_width=1, border_color=COL["border"], wrap="word")
        self.log.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.log.configure(state="disabled")
        self.log.tag_config("ok", foreground=COL["success"])
        self.log.tag_config("err", foreground=COL["error"])
        self.log.tag_config("info", foreground=COL["muted"])
        self.log.tag_config("hi", foreground=COL["primary_hi"])

        # ---- 底栏 ----
        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.grid(row=5, column=0, sticky="ew", pady=(0, 12), **pad)

        ctk.CTkButton(foot, text="打开输出目录", command=self._open_out,
                      width=120, height=32, corner_radius=8, font=FONT_SM,
                      fg_color=COL["card_hi"], hover_color=COL["border"],
                      text_color=COL["text"], border_width=1, border_color=COL["border"]
                      ).pack(side="left")
        ctk.CTkLabel(foot, text="提示：也可以把 mp3 拖到 exe 图标上",
                     font=FONT_SM, text_color=COL["dim"]).pack(side="right")

    # ------------------------------------------------------------------
    def _pick_audio(self):
        p = filedialog.askopenfilename(
            title="选择音频",
            filetypes=[("音频", "*.mp3 *.wav *.flac *.ogg"), ("全部", "*.*")])
        if p:
            self.v_audio.set(p)

    def _pick_out(self):
        p = filedialog.askdirectory(title="选择输出目录")
        if p:
            self.v_out.set(p)

    def _pick_tpl(self):
        p = filedialog.askopenfilename(title="选择 FL 模板", filetypes=[("FL 工程", "*.flp")])
        if p:
            self.v_tpl.set(p)

    def _open_out(self):
        d = self.v_out.get()
        if d and os.path.isdir(d):
            os.startfile(d)
        else:
            messagebox.showinfo("提示", "输出目录还不存在。")

    def _append(self, text, tag=None):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n", tag)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _status(self, t, c=None):
        self.lbl.configure(text=t, text_color=c or COL["muted"])

    # ------------------------------------------------------------------
    def _run(self):
        if self._busy:
            return
        audio = self.v_audio.get().strip()
        if not audio or not os.path.exists(audio):
            messagebox.showwarning("缺少音频", "请先选择要处理的音频文件。")
            return

        out = self.v_out.get().strip() or os.path.join(os.path.dirname(audio), "Audio2FL_out")
        os.makedirs(out, exist_ok=True)

        bpm = self.v_bpm.get().strip()
        if bpm:
            try:
                float(bpm)
            except ValueError:
                messagebox.showwarning("BPM 无效", "BPM 需要是数字，或留空自动检测。")
                return

        self._busy = True
        self._t0 = time.time()
        self.btn.configure(state="disabled", text="处理中…")
        self.pbar.set(0)
        self._append("─" * 56, "info")
        self._append(f"输入: {audio}", "hi")
        self._append(f"输出: {out}", "hi")

        threading.Thread(target=self._worker, args=(audio, out, bpm), daemon=True).start()

    def _worker(self, audio, out, bpm):
        try:
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from app.toflp.pipeline import Options, run

            tpl = self.v_tpl.get().strip()
            if not tpl:
                roots = [os.path.dirname(sys.executable), os.getcwd()]
                if getattr(sys, "_MEIPASS", None):
                    roots.insert(0, sys._MEIPASS)
                for r in roots:
                    cand = os.path.join(r, "template.flp")
                    if os.path.exists(cand):
                        tpl = cand
                        break

            opts = Options(audio=audio, out_dir=out, template=tpl,
                           make_midi=self.v_mid.get(), make_flp=self.v_flp.get(),
                           make_drums=self.v_drum.get(),
                           bpm_override=float(bpm) if bpm else None)

            res = run(opts, progress=lambda m, f: self.after(0, lambda: self._prog(m, f)))
            self.after(0, lambda: self._done(res))
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self.after(0, lambda: self._err(str(e), tb))

    def _prog(self, msg, frac):
        self.pbar.set(max(0.0, min(1.0, frac)))
        elapsed = time.time() - self._t0
        if frac > 0.05:
            eta = elapsed / frac * (1 - frac)
            tail = f"  已用 {elapsed:.0f}s / 预计剩 {eta:.0f}s"
        else:
            tail = f"  已用 {elapsed:.0f}s"
        self._status(f"{frac*100:5.1f}%   {msg}{tail}")
        self._append(f"[{frac*100:5.1f}%] {msg}")

    def _done(self, res):
        self.pbar.set(1)
        total = time.time() - self._t0
        self._status(f"完成，耗时 {total:.1f} 秒", COL["success"])
        for line in (res.log or []):
            self._append(line, "ok")
        self._append(f"✓ 全部完成（{total:.1f} 秒）", "ok")
        self._busy = False
        self.btn.configure(state="normal", text="▶   开始处理")

    def _err(self, msg, tb):
        self._status("出错了", COL["error"])
        self._append("✗ " + msg, "err")
        for line in tb.splitlines()[-5:]:
            self._append("  " + line, "err")
        self._busy = False
        self.btn.configure(state="normal", text="▶   开始处理")
        messagebox.showerror("处理失败", msg)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    audio = None
    for a in argv:
        if a.lower().endswith((".mp3", ".wav", ".flac", ".ogg")) and os.path.exists(a):
            audio = a
            break
    app = App(audio)
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
